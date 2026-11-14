"""Olpe: Verkehrsmessungen der Stadt mit Radar-Messgeräten (Open Data, ab 2025).

Quelle: opendata.olpe.de (CKAN), je Messstelle ein Datensatz „Verkehrsmessung(en) <Ort>“ mit
einer JSON-Datei je Messung, meist ein bis zwei Wochen am Stück. Zwei Formate:

- Geräte-Export: `{"header", "request": {"from", "to"}, "data": [{"devicenr",
  "measurement_data": [{lat, lon, start_date, end_date}], "vehicle_data": [{date, direction,
  lane, code, length, v1, …}]}]}`. Alle Zeiten in UTC (mit oder ohne „Z“); die Karte rechnet in
  Ortszeit um. `measurement_data` ist ein GPS-Punkt je Tag – auch für Tage nach dem Export, als
  das Gerät schon woanders stand; daher zählen nur die Punkte aus der Zeit der Fahrzeuge.
- Tabelle: `[{"Datum": "TT.MM.JJJJ hh:mm:ss", "Richtung", "Klasse",
  "Fahrzeugklassen-Bezeichnung", …}]` in Ortszeit, ohne Lage (Lage aus `orte` in sources.yaml).

Klassen (Codes des Geräts, Bezeichnungen aus der Tabelle): 2 PkwA, 3 Lkw, 5 Bus, 7 Pkw, 8 LkwA,
9 Sattel-Kfz, 10 Krad, 11 Lfw, 230 Radfahrer; 6 und 250 ohne Bezeichnung (nach Länge und Tempo
Kfz). Kfz = alle außer Radfahrenden; Schwerverkehr = Lkw, LkwA, Sattel-Kfz, Bus; Rad = vom Gerät
als Radfahrer erkannt (nur auf der Fahrbahn).

- Je Kalendertag eine Zählung (Querschnitt, beide Richtungen). Gezählt sind die vollen Stunden
  zwischen Beginn (Exportfenster bzw. erstes Fahrzeug) und dem letzten Fahrzeug. Drei oder mehr
  Stunden am Stück ohne jedes Fahrzeug, in denen nach den übrigen Tagen mindestens zehn zu
  erwarten wären, gelten als Ausfall des Geräts („nicht gezählt“, mit Hinweis; ein Tag ganz im
  Ausfall ergibt keine Zählung); leere Nachtstunden in ruhigen Straßen bleiben echte Nullen.
- Lizenz je Datensatz: der Lizenz-Link auf seiner Seite (`license_url`; die CKAN-API mit der
  `license_id` sperrt das Portal per robots.txt, das DCAT-Dokument nennt keine Lizenz) →
  Lieferung in sources.yaml (`lizenz_link`, sonst `lizenz_id`); ein Datensatz mit anderer
  Lizenz kommt nicht in die Karte.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

ORTSZEIT = ZoneInfo("Europe/Berlin")
RAD = {230}
SCHWER = {3, 5, 8, 9}
LUECKE_STUNDEN = 3
LUECKE_ERWARTET = 10


@dataclass
class Fahrzeug:
    zeit: datetime  # Ortszeit, ohne Zeitzone
    richtung: int | None
    code: int | None


@dataclass
class Messung:
    fahrzeuge: list[Fahrzeug]
    beginn: datetime | None = None  # Ortszeit: Beginn des Exportfensters bzw. des Geräts
    lage: tuple[float, float] | None = None
    geraet: int | None = None
    format: str = ""


@dataclass
class Bericht:
    dateien: int = 0
    fahrzeuge: int = 0
    formate: dict[str, int] = field(default_factory=dict)
    lizenz_fremd: list[str] = field(default_factory=list)
    unlesbar: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)
    luecken: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        return [
            f"{self.dateien} Messungen, {self.fahrzeuge} Fahrzeuge "
            f"({', '.join(f'{n} {f}' for f, n in sorted(self.formate.items()))})",
            *[f"andere Lizenz (nicht in der Karte): {d}" for d in self.lizenz_fremd],
            *[f"ohne Lage: {d}" for d in self.ohne_lage],
            *[f"Lücke (nicht gezählt): {d}" for d in self.luecken[:20]],
            *[f"nicht lesbar: {d}" for d in self.unlesbar[:10]],
        ]


def _utc(text: str) -> datetime:
    """'2025-08-27 15:00:05' oder '2025-11-12T09:53:43.736Z' (UTC) -> Ortszeit ohne Zeitzone."""
    t = datetime.fromisoformat(text.strip().replace("Z", "").replace(" ", "T"))
    return t.replace(tzinfo=UTC).astimezone(ORTSZEIT).replace(tzinfo=None)


def _utc_bewusst(text: str) -> datetime:
    t = datetime.fromisoformat(text.strip().replace("Z", "").replace(" ", "T"))
    return t.replace(tzinfo=UTC)


def lese_geraet(d: dict) -> Messung:
    fahrzeuge, punkte, beginn, geraet = [], [], [], None
    for e in d.get("data", []):
        geraet = geraet or e.get("devicenr")
        for v in e.get("vehicle_data", []):
            if v.get("date"):
                fahrzeuge.append(Fahrzeug(_utc(v["date"]), v.get("direction"), v.get("code")))
        for m in e.get("measurement_data", []):
            if m.get("lat") and m.get("lon") and m.get("end_date"):
                punkte.append((_utc_bewusst(m["end_date"]), float(m["lon"]), float(m["lat"])))
            if m.get("start_date"):
                beginn.append(_utc(m["start_date"]))
    fahrzeuge.sort(key=lambda f: f.zeit)
    anfang = None
    if fahrzeuge:
        von = (d.get("request") or {}).get("from")
        kandidaten = [_utc(von)] if von else []
        kandidaten += [min(beginn)] if beginn else []
        anfang = max(kandidaten) if kandidaten else None
        if anfang and anfang > fahrzeuge[0].zeit:
            anfang = None  # Fenster passt nicht zu den Daten: dann ab dem ersten Fahrzeug
    return Messung(fahrzeuge, anfang, lage_aus(punkte, fahrzeuge), geraet, "geraet")


def lage_aus(punkte: list, fahrzeuge: list[Fahrzeug]) -> tuple[float, float] | None:
    """Median der GPS-Punkte aus der Zeit der Fahrzeuge (Tagesende bis einen Tag nach dem
    letzten Fahrzeug); spätere Punkte zeigen schon die nächste Messstelle."""
    if not punkte or not fahrzeuge:
        return None
    erstes = fahrzeuge[0].zeit.replace(tzinfo=ORTSZEIT).astimezone(UTC)
    letztes = fahrzeuge[-1].zeit.replace(tzinfo=ORTSZEIT).astimezone(UTC)
    drin = [(lon, lat) for t, lon, lat in punkte if erstes <= t <= letztes + timedelta(days=1)]
    if not drin:
        return None
    return statistics.median(p[0] for p in drin), statistics.median(p[1] for p in drin)


def lese_tabelle(zeilen: list[dict]) -> Messung:
    fahrzeuge = []
    for z in zeilen:
        try:
            zeit = datetime.strptime(str(z["Datum"]).strip(), "%d.%m.%Y %H:%M:%S")
        except (KeyError, ValueError):
            continue
        fahrzeuge.append(Fahrzeug(zeit, z.get("Richtung"), z.get("Klasse")))
    fahrzeuge.sort(key=lambda f: f.zeit)
    return Messung(fahrzeuge, None, None, None, "tabelle")


def lese_messung(text: str) -> Messung:
    d = json.loads(text.lstrip("﻿"))
    return lese_geraet(d) if isinstance(d, dict) else lese_tabelle(d)


def _volle_stunde_ab(t: datetime) -> datetime:
    h = t.replace(minute=0, second=0, microsecond=0)
    return h if h == t else h + timedelta(hours=1)


def gibt_es(h: datetime) -> bool:
    """Gibt es diese Ortszeit? (Nicht in der Stunde, die bei der Umstellung auf Sommerzeit
    ausfällt.)"""
    zurueck = h.replace(tzinfo=ORTSZEIT).astimezone(UTC).astimezone(ORTSZEIT)
    return zurueck.replace(tzinfo=None) == h


def stunden(m: Messung) -> dict[datetime, tuple[int, int, int]]:
    """{Stunde (Ortszeit): (Kfz, Schwerverkehr, Rad)} über die vollen Stunden der Messung; die
    Stunde, die bei der Umstellung auf Sommerzeit ausfällt, fehlt."""
    if not m.fahrzeuge:
        return {}
    start = _volle_stunde_ab(m.beginn or m.fahrzeuge[0].zeit)
    ende = m.fahrzeuge[-1].zeit.replace(minute=0, second=0, microsecond=0)
    zaehler: dict[datetime, list[int]] = defaultdict(lambda: [0, 0, 0])
    for f in m.fahrzeuge:
        h = f.zeit.replace(minute=0, second=0, microsecond=0)
        if start <= h < ende:
            if f.code in RAD:
                zaehler[h][2] += 1
            else:
                zaehler[h][0] += 1
                zaehler[h][1] += f.code in SCHWER
    out = {}
    h = start
    while h < ende:
        if gibt_es(h):
            out[h] = tuple(zaehler.get(h, [0, 0, 0]))
        h += timedelta(hours=1)
    return out


def _wochenende(t: datetime) -> bool:
    return t.weekday() >= 5


def erwartet(reihe: dict[datetime, tuple[int, int, int]], lauf: list[datetime]) -> float:
    """Fahrzeuge, die in den Stunden `lauf` zu erwarten wären: Mittel je Uhrzeit über die anderen
    Tage derselben Art (Werktag oder Wochenende); gibt es keine, die übrigen Tage zur Hälfte."""
    tage = {h.date() for h in lauf}
    art = _wochenende(lauf[0])
    gleich: dict[int, list[int]] = defaultdict(list)
    andere: dict[int, list[int]] = defaultdict(list)
    for h, werte in reihe.items():
        if h.date() in tage:
            continue
        (gleich if _wochenende(h) == art else andere)[h.hour].append(werte[0] + werte[2])
    summe = 0.0
    for x in lauf:
        if gleich.get(x.hour):
            summe += sum(gleich[x.hour]) / len(gleich[x.hour])
        elif andere.get(x.hour):
            summe += 0.5 * sum(andere[x.hour]) / len(andere[x.hour])
    return summe


def luecken(reihe: dict[datetime, tuple[int, int, int]]) -> list[tuple[datetime, datetime]]:
    """Ausfälle des Geräts: Läufe von mindestens LUECKE_STUNDEN Stunden ohne jedes Fahrzeug, in
    denen nach den übrigen Tagen der Messung mindestens LUECKE_ERWARTET Fahrzeuge zu erwarten
    wären – so bleiben leere Nachtstunden in ruhigen Straßen echte Nullen.
    [(erste, letzte Stunde)]"""
    out, lauf = [], []
    for h in [*sorted(reihe), None]:
        leer = h is not None and sum(reihe[h]) == 0
        if leer and (not lauf or h - lauf[-1] == timedelta(hours=1)):
            lauf.append(h)
            continue
        if len(lauf) >= LUECKE_STUNDEN and erwartet(reihe, lauf) >= LUECKE_ERWARTET:
            out.append((lauf[0], lauf[-1]))
        lauf = [h] if leer else []
    return out


def ort_aus_titel(titel: str) -> str:
    """'Verkehrsmessung Standort „Zum Honigsack 35“' -> 'Zum Honigsack 35'."""
    ort = re.sub(r"^\s*Verkehrsmessung(en)?\s+(Standort\s+)?", "", titel or "")
    return ort.strip(" \"'„“”") or titel


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    lizenzen = {lf[k]: lf["code"] for lf in quelle.get("lieferungen", [])
                for k in ("lizenz_id", "lizenz_link") if lf.get(k)}
    orte = quelle.get("orte") or {}
    for paket_pfad in sorted((pfade.roh / "olpe").glob("*/paket.json")):
        paket = json.loads(paket_pfad.read_text(encoding="utf-8"))
        lizenz = paket.get("license_url") or paket.get("license_id") or ""
        lieferung = lizenzen.get(lizenz)
        for r in paket.get("resources", []):
            datei = unquote((r.get("url") or "").rsplit("/", 1)[-1])
            pfad = paket_pfad.parent / datei
            if not datei.lower().endswith(".json") or not pfad.exists():
                continue
            if lieferung is None:
                bericht.lizenz_fremd.append(f"{datei} ({lizenz or 'ohne Lizenz'})")
                continue
            try:
                m = lese_messung(pfad.read_text(encoding="utf-8", errors="replace"))
            except (json.JSONDecodeError, ValueError, TypeError, KeyError):
                bericht.unlesbar.append(datei)
                continue
            if not m.fahrzeuge:
                bericht.unlesbar.append(datei)
                continue
            bericht.dateien += 1
            bericht.fahrzeuge += len(m.fahrzeuge)
            bericht.formate[m.format] = bericht.formate.get(m.format, 0) + 1
            ort = orte.get(datei) or {}
            yield from _zaehlungen(quelle, paket, r, datei, m, ort, lieferung, bericht)


RAD_HINWEIS = ("Radfahrende nur, soweit das Radargerät sie auf der Fahrbahn erkennt; Fuß nicht "
               "gezählt.")


def spannen(stunden: list[int]) -> list[str]:
    """Aufeinanderfolgende Stunden zusammenfassen: [9, 10, 11, 15] -> ['9–12 Uhr', '15–16 Uhr']."""
    teile, anfang = [], None
    for i, h in enumerate(stunden):
        anfang = h if anfang is None else anfang
        if i + 1 == len(stunden) or stunden[i + 1] != h + 1:
            teile.append(f"{anfang}–{h + 1} Uhr")
            anfang = None
    return teile


def _zaehlungen(quelle: dict, paket: dict, r: dict, datei: str, m: Messung, ort: dict,
                lieferung: str, bericht: Bericht) -> Iterator[Zaehlung]:
    name = ort.get("name") or ort_aus_titel(paket.get("title") or "")
    hinweise = [RAD_HINWEIS]
    if ort.get("lon") is not None:
        lon, lat, lage = float(ort["lon"]), float(ort["lat"]), "geokodiert"
        hinweise.append("Lage nach der Adresse (OpenStreetMap); das Gerät hat hier keine GPS-Lage.")
    elif m.lage:
        (lon, lat), lage = m.lage, "gps"
        hinweise.append("Lage: GPS des Messgeräts.")
    else:
        lon = lat = lage = None
        bericht.ohne_lage.append(datei)
    reihe = stunden(m)
    weg = set()
    for a, b in luecken(reihe):
        weg |= {a + timedelta(hours=i) for i in range(int((b - a) / timedelta(hours=1)) + 1)}
        bis = f"{b.hour + 1:02d}" if b.date() == a.date() else f"{b + timedelta(hours=1):%d.%m. %H}"
        bericht.luecken.append(f"{datei}: {a:%d.%m. %H} bis {bis} Uhr")
    je_tag: dict[date, dict[int, tuple | None]] = defaultdict(dict)
    for h, werte in reihe.items():
        je_tag[h.date()][h.hour] = None if h in weg else werte
    stelle = re.sub(r"\W+", "", name.lower()) or Path(datei).stem
    for tag, std in sorted(je_tag.items()):
        if all(v is None for v in std.values()):
            continue  # ganzer Tag im Ausfall: keine Zählung
        h0, h1 = min(std), max(std)
        reihen = {g: [std[h][i] if std.get(h) is not None else None for h in range(h0, h1 + 1)]
                  for i, g in enumerate(("kfz", "sv", "rad"))}
        lueckentext = spannen([h for h in range(h0, h1 + 1) if h in std and std[h] is None])
        ausfall = [f"Ohne Daten ({', '.join(lueckentext)}), vermutlich ein Ausfall des Geräts – "
                   "als „nicht gezählt“ gewertet."] if lueckentext else []
        geraet = f" (Gerät {m.geraet})" if m.geraet else ""
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=f"{Path(datei).stem}_{tag:%Y%m%d}",
            stelle_roh=stelle,
            name=name,
            typ="Q",
            lon=lon,
            lat=lat,
            lage=lage,
            datum=tag,
            fenster=[(h0 * 60, (h1 + 1) * 60)],
            intervall=60,
            h0=h0,
            stunden=reihen,
            land=quelle["land"],
            richtungen=2,
            kategorien="Kfz nach Fahrzeugklassen des Radargeräts; Schwerverkehr = Lkw, Lkw mit "
                       "Anhänger, Sattelzüge, Busse; Rad = als Radfahrer erkannt",
            rohdatei=r.get("url"),
            lieferung=lieferung,
            bemerkung=f"Messung „{r.get('name') or datei}“{geraet}",
            hinweise=hinweise + ausfall,
            zusatz={"datei": datei, "paket": paket.get("name"), "format": m.format,
                    "klassen": dict(Counter(f.code for f in m.fahrzeuge if f.zeit.date() == tag))},
        )
