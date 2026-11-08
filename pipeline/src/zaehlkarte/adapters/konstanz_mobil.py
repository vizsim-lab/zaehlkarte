"""Konstanz: mobile Verkehrszählungen der Stadt 2020 (Rad, Fuß, teils Kfz; Open Data, CC0).

Quelle: offenedaten-konstanz.de, Datensatz „Mobile Verkehrszählungen Rad- und Fußverkehr“, je
Standort eine CSV (`;`, UTF-8 mit BOM) mit Werten je 5 oder 15 Minuten und Richtung, über ein bis
sechs Wochen. Die Spalten heißen je Datei anders („Fahrradfahrer inkl. Lastenraeder
(stadteinwaerts)“, „Stadteinwaerts_PKW“, „Fussgaenger-Ri-Schweiz“ …).

- Verkehrsart je Spalte aus dem Namen: Fahrrad/Rad -> Rad, Fußgänger -> Fuß, Auto/Pkw/Kfz -> Kfz.
  Summenspalten (Summe, Total, Insgesamt, eine Richtung ohne Verkehrsart) fallen weg, „Andere“
  (weder zu Fuß noch mit dem Rad) auch. Nennt keine Spalte eine Verkehrsart (Alte Rheinbrücke),
  gilt die Art aus sources.yaml für die Richtungsspalten.
- Zeitstempel (`zeitstempel` in sources.yaml): Die 15-Minuten-Dateien stehen auf vollen
  Viertelstunden – Beginn des Intervalls, wie in Exporten von Zählgeräten üblich. Die
  5-Minuten-Dateien sind Protokolle des Geräts: Es schreibt jede Zeile ein paar Sekunden nach
  dem Ende ihres Intervalls, und die erste Zeile nach dem Einschalten ist leer (dort, wo sonst
  um diese Uhrzeit 8–16 Fußgänger je 5 Minuten stehen). Die Karte rundet auf die volle
  5. Minute und nimmt die Zeile als Ende ihres Intervalls (`ende`).
- Doppelte Zeilen (gleicher Zeitpunkt): gleiche Werte oder eine davon ohne Zählung -> einmal
  gezählt; widersprechen sie sich, gilt die Stunde als nicht gezählt. Zeilen ohne Werte fallen
  weg.
- Je Kalendertag eine Zählung (Querschnitt, beide Richtungen). Eine Stunde zählt nur, wenn alle
  ihre Intervalle da sind – die Geräte fielen öfter für Stunden oder Tage aus.
- Lage: aus sources.yaml (OpenStreetMap, Genauigkeit je Standort); die Daten nennen nur Straße,
  Brücke oder Hausnummer.
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from zaehlkarte.config import Pfade
from zaehlkarte.modell import GRUPPEN, Zaehlung

_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_ZEIT = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?")
_HOCHGELADEN = re.compile(r"_\d+$")  # „Schottenstrasse_2.csv“: Zähler des Portals je Upload


@dataclass
class Bericht:
    dateien: int = 0
    spalten: dict[str, str] = field(default_factory=dict)
    unvollstaendig: int = 0
    doppelt: int = 0
    widerspruch: int = 0
    leer: int = 0

    def zeilen(self) -> list[str]:
        return [
            f"{self.dateien} Standorte",
            *[f"{d}: {s}" for d, s in self.spalten.items()],
            f"Stunden mit fehlenden Intervallen (weggelassen): {self.unvollstaendig}",
            f"doppelte Zeilen: {self.doppelt}, davon widersprüchlich (Stunde weggelassen): "
            f"{self.widerspruch}; Zeilen ohne Werte: {self.leer}",
        ]


def _norm(text: str) -> str:
    t = text.lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    return re.sub(r"[^a-z]+", " ", t).strip()


def gruppe_der_spalte(name: str) -> str | None:
    """Verkehrsart einer Wertespalte oder None (Summe, Andere, Zeit- und Quellenspalte)."""
    n = _norm(name)
    if re.search(r"\b(andere|summe|total|insgesamt|quelle|datum|uhrzeit)\b", n):
        return None
    if "fuss" in n:  # vor „fahrrad“: „Fussgaenger Ri Fahrradbruecke“
        return "fuss"
    if re.search(r"fahrrad|\brad\b", n):
        return "rad"
    if re.search(r"\b(auto|pkw|kfz)\b", n):
        return "kfz"
    return None


def zuordnung_der_spalten(kopf: list[str], art_ohne_name: str | None) -> dict[int, str]:
    """{Spaltennummer: Gruppe}; ohne Verkehrsart im Namen die Richtungsspalten als `art`."""
    zuordnung = {i: g for i, s in enumerate(kopf) if (g := gruppe_der_spalte(s))}
    if not zuordnung and art_ohne_name:
        zuordnung = {
            i: art_ohne_name
            for i, s in enumerate(kopf)
            if re.search(r"einw|ausw", _norm(s))
            and not re.search(r"summe|total|insgesamt", _norm(s))
        }
    return zuordnung


def _zeitpunkt(zeile: list[str]) -> datetime | None:
    """Datum und Uhrzeit aus den ersten Spalten („28.07.2020 00:00“ oder Datum; Uhrzeit)."""
    text = " ".join(zeile[:3])
    md = _DATUM.search(text)
    mz = _ZEIT.search(text[md.end():]) if md else None
    if not md or not mz:
        return None
    try:
        return datetime(int(md[3]), int(md[2]), int(md[1]), int(mz[1]), int(mz[2]),
                        int(mz[3] or 0))
    except ValueError:
        return None


def intervall_beginn(t: datetime, intervall: int, zeitstempel: str = "beginn") -> datetime:
    """Zeitstempel einer Zeile -> Beginn ihres Intervalls (auf das Raster gerundet)."""
    schritt = intervall * 60
    mitternacht = t.replace(hour=0, minute=0, second=0, microsecond=0)
    n = round((t - mitternacht).total_seconds() / schritt)
    marke = mitternacht + timedelta(seconds=n * schritt)
    return marke - timedelta(minutes=intervall) if zeitstempel == "ende" else marke


def lese_standort(
    text: str,
    art_ohne_name: str | None,
    intervall: int,
    zeitstempel: str = "beginn",
    bericht: Bericht | None = None,
) -> tuple[dict[date, dict[int, dict[str, int]]], dict[str, str]]:
    """CSV -> ({Tag: {Stunde: {Gruppe: Summe}}}, {Spalte: Gruppe})."""
    bericht = bericht if bericht is not None else Bericht()
    zeilen = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    if not zeilen:
        return {}, {}
    kopf = zeilen[0]
    zuordnung = zuordnung_der_spalten(kopf, art_ohne_name)
    gruppen = sorted(set(zuordnung.values()), key=GRUPPEN.index)
    # Beginn des Intervalls -> Werte je Gruppe; None = widersprüchliche Zeilen
    intervalle: dict[datetime, dict[str, int] | None] = {}
    for zeile in zeilen[1:]:
        t = _zeitpunkt(zeile)
        if t is None:
            continue
        roh = [(zeile[i].strip() if i < len(zeile) else "") for i in zuordnung]
        if not roh or not all(v.isdigit() for v in roh):
            bericht.leer += 1
            continue
        werte = dict.fromkeys(gruppen, 0)
        for g, v in zip(zuordnung.values(), roh, strict=True):
            werte[g] += int(v)
        beginn = intervall_beginn(t, intervall, zeitstempel)
        if beginn not in intervalle:
            intervalle[beginn] = werte
            continue
        bericht.doppelt += 1
        alt = intervalle[beginn]
        if alt is None or alt == werte or not any(werte.values()):
            continue
        if not any(alt.values()):
            intervalle[beginn] = werte
            continue
        bericht.widerspruch += 1
        intervalle[beginn] = None
    je_stunde: dict[datetime, list[dict[str, int] | None]] = defaultdict(list)
    for beginn, werte in intervalle.items():
        je_stunde[beginn.replace(minute=0)].append(werte)
    tage: dict[date, dict[int, dict[str, int]]] = defaultdict(dict)
    for stunde, liste in sorted(je_stunde.items()):
        if len(liste) != 60 // intervall or any(w is None for w in liste):
            bericht.unvollstaendig += 1
            continue
        tage[stunde.date()][stunde.hour] = {g: sum(w[g] for w in liste) for g in gruppen}
    return dict(tage), {kopf[i].strip(): g for i, g in zuordnung.items()}


def _fenster(stunden: list[int]) -> list[tuple[int, int]]:
    fenster: list[tuple[int, int]] = []
    for h in sorted(stunden):
        if fenster and fenster[-1][1] == h * 60:
            fenster[-1] = (fenster[-1][0], h * 60 + 60)
        else:
            fenster.append((h * 60, h * 60 + 60))
    return fenster


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "konstanz"
    for st in quelle["standorte"]:
        pfad = ordner / st["datei"]
        if not pfad.exists():
            continue
        zeitstempel = st.get("zeitstempel", "beginn")
        tage, zuordnung = lese_standort(
            pfad.read_text(encoding="utf-8-sig", errors="replace"),
            st.get("art"),
            st["intervall"],
            zeitstempel,
            bericht,
        )
        bericht.dateien += 1
        bericht.spalten[st["datei"]] = ", ".join(f"{s} -> {g}" for s, g in zuordnung.items())
        gruppen = sorted(set(zuordnung.values()), key=GRUPPEN.index)
        stamm = _HOCHGELADEN.sub("", st["datei"].rsplit(".", 1)[0])
        hinweise = list(st.get("hinweise", []))
        if zeitstempel == "ende":
            hinweise.append(f"Uhrzeiten der Rohdatei = Ende des {st['intervall']}-Minuten-"
                            "Intervalls (das Gerät schreibt jede Zeile kurz danach).")
        bemerkung = f"Mobile Zählung, {st['intervall']}-Minuten-Werte je Richtung"
        if st.get("richtungen"):
            bemerkung += f" ({st['richtungen']})"
        # Hinweise nur für einen Teil der Tage (von/bis als Datum, bis offen = bis zum Ende)
        zeitraeume = [
            (str(h["von"]), str(h.get("bis", "9999-12-31")), h["text"])
            for h in st.get("hinweise_zeitraum", [])
        ]
        lon, lat = st.get("lon"), st.get("lat")
        for tag, stunden in sorted(tage.items()):
            dazu = [t for von, bis, t in zeitraeume if von <= tag.isoformat() <= bis]
            h0, h1 = min(stunden), max(stunden)
            reihen = {
                g: [stunden[h][g] if h in stunden else None for h in range(h0, h1 + 1)]
                for g in gruppen
            }
            yield Zaehlung(
                quelle=quelle["code"],
                kennung=f"{stamm}_{tag:%Y%m%d}",
                stelle_roh=stamm,
                name=st["name"],
                typ="Q",
                lon=lon,
                lat=lat,
                lage="geokodiert" if lon is not None else None,
                datum=tag,
                fenster=_fenster(list(stunden)),
                intervall=st["intervall"],
                h0=h0,
                stunden=reihen,
                land=quelle["land"],
                richtungen=2,
                kategorien=st.get("kategorien") or ", ".join(zuordnung),
                rohdatei=st.get("url"),
                bemerkung=bemerkung,
                hinweise=[*hinweise, *dazu],
                zusatz={"datei": st["datei"], "genauigkeit": st.get("genauigkeit")},
            )
