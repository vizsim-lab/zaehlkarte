"""Moers: Verkehrszählungen der Stadt mit Seitenradar-Messgeräten (Open Data, 2010–2022).

Quelle: offenesdatenportal.de, je Jahr ein Datensatz „Verkehrszählungen 20xx (Stadt Moers)“,
je Messstelle eine Textdatei mit einer Zeile je Fahrzeug:
`TT.MM.JJ hh:mm:ss;00;Geschwindigkeit;Länge;Fahrspur` (Fahrspur 0 = gerätnah, 1 = gerätfern).
Das Gerät (Impactor) hängt an einem Mast und misst meist zwei Tage am Stück; die Stadt nutzt es
für Geschwindigkeitsmessungen, es zählt dabei jedes Fahrzeug.

- Je Kalendertag eine Zählung (Querschnitt, beide Fahrspuren). Gezählt sind die vollen Stunden
  zwischen der ersten und der letzten Zeile der Datei – das Gerät lief dazwischen durch, eine
  Stunde ohne Fahrzeug ist eine echte 0. Angefangene Stunden am Anfang und Ende zählen nicht.
- Kfz = alle Zeilen; Schwerverkehr = Länge ab 8 m (Mindestlänge Lkw laut Stadt). Radfahrende
  trennt das Gerät nicht ab.
- Lage: aus der Adresse der Messung geokodiert (`pipeline/geokodierung/moers.csv`, Werkzeug
  `werkzeuge/geokodiere_moers.py`, OpenStreetMap). Genauigkeit `strasse` = Mitte der Straße.
- Uhr des Geräts: Liegt das Jahr in den Daten neben dem des Datensatzes, Tag und Monat aber
  passen zum Datum im Dateinamen (Gerät auf 2007 statt 2017 gestellt), gilt das Jahr des
  Datensatzes (mit Hinweis).
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

_ZEILE = re.compile(
    r"^(\d{2})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2}):(\d{2});\d+;(\d+);(\d+);([01])\s*$"
)
_JAHR = re.compile(r"\b(20\d{2})\b")
SV_AB_M = 8


@dataclass
class Bericht:
    dateien: int = 0
    fahrzeuge: int = 0
    unlesbar: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)
    jahr_korrigiert: list[str] = field(default_factory=list)
    genauigkeit: dict[str, int] = field(default_factory=dict)

    def zeilen(self) -> list[str]:
        return [
            f"{self.dateien} Dateien, {self.fahrzeuge} Fahrzeuge",
            "Lage je Datei: " + ", ".join(f"{n} {g}" for g, n in sorted(self.genauigkeit.items())),
            f"Jahr korrigiert (Uhr des Geräts): {', '.join(self.jahr_korrigiert) or '–'}",
            *[f"ohne Lage: {d}" for d in self.ohne_lage[:10]],
            *[f"nicht lesbar: {d}" for d in self.unlesbar[:10]],
        ]


def lese_fahrzeuge(text: str) -> list[tuple[datetime, int, int, int]]:
    """Textdatei -> [(Zeitpunkt, Geschwindigkeit, Länge, Fahrspur)]; unlesbare Zeilen fallen weg."""
    out = []
    for z in text.lstrip("﻿").splitlines():
        m = _ZEILE.match(z.strip("﻿"))
        if not m:
            continue
        t, mo, j, h, mi, s, v, laenge, spur = (int(x) for x in m.groups())
        try:
            out.append((datetime(2000 + j, mo, t, h, mi, s), v, laenge, spur))
        except ValueError:
            continue
    return sorted(out)


def _datum_im_namen(datei: str) -> tuple[int, int] | None:
    """(Tag, Monat) aus Namen wie 'kirschenallee117t30250117' oder '..._t30_11.06.2021'."""
    stamm = Path(datei).stem.lower()
    for muster in (
        r"(\d{2})\.(\d{2})\.(?:\d{4}|\d{2})$",
        r"t\d{2}_?(\d{2})(\d{2})(?:\d{4}|\d{2})$",
    ):
        m = re.search(muster, stamm)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def jahr_korrektur(fahrzeuge: list, datensatz_jahr: int | None, datei: str) -> int:
    """Jahre, um die die Uhr des Geräts falsch ging (0 = keine Korrektur)."""
    if not fahrzeuge or datensatz_jahr is None:
        return 0
    erstes = fahrzeuge[0][0]
    if erstes.year == datensatz_jahr or _datum_im_namen(datei) != (erstes.day, erstes.month):
        return 0
    return datensatz_jahr - erstes.year


def stunden_je_tag(fahrzeuge: list) -> dict[date, dict[int, tuple[int, int]]]:
    """{Tag: {Stunde: (Kfz, Schwerverkehr)}} über die vollen Stunden der Messung."""
    if not fahrzeuge:
        return {}
    start = fahrzeuge[0][0].replace(minute=0, second=0) + timedelta(hours=1)
    ende = fahrzeuge[-1][0].replace(minute=0, second=0)
    zaehler: dict[datetime, list[int]] = defaultdict(lambda: [0, 0])
    for zeit, _v, laenge, _spur in fahrzeuge:
        stunde = zeit.replace(minute=0, second=0)
        if start <= stunde < ende:
            zaehler[stunde][0] += 1
            zaehler[stunde][1] += laenge >= SV_AB_M
    out: dict[date, dict[int, tuple[int, int]]] = defaultdict(dict)
    stunde = start
    while stunde < ende:
        kfz, sv = zaehler.get(stunde, [0, 0])
        out[stunde.date()][stunde.hour] = (kfz, sv)
        stunde += timedelta(hours=1)
    return dict(out)


def lese_lagen(pfad: Path) -> dict[str, dict]:
    if not pfad.exists():
        return {}
    with pfad.open(encoding="utf-8", newline="") as f:
        return {r["datei"]: r for r in csv.DictReader(f) if r.get("lon")}


def name_aus(ressource: dict, datei: str) -> str:
    """'Verkehrszählung Eupener Straße 26' -> 'Eupener Straße 26'."""
    name = re.sub(r"^\s*Verkehr\w*\s+", "", ressource.get("name") or Path(datei).stem)
    return " ".join(name.replace("_", " ").split())


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "moers"
    lagen = lese_lagen(pfade.pipeline / quelle["geokodierung"]["datei"])
    for paket_pfad in sorted(ordner.glob("*/paket.json")):
        paket = json.loads(paket_pfad.read_text(encoding="utf-8"))
        m = _JAHR.search(paket.get("title") or "")
        datensatz_jahr = int(m.group(1)) if m else None
        for r in paket.get("resources", []):
            datei = unquote((r.get("url") or "").rsplit("/", 1)[-1])
            pfad = paket_pfad.parent / datei
            if not datei or not pfad.exists():
                continue
            fahrzeuge = lese_fahrzeuge(pfad.read_text(encoding="utf-8", errors="replace"))
            if not fahrzeuge:
                bericht.unlesbar.append(datei)
                continue
            bericht.dateien += 1
            bericht.fahrzeuge += len(fahrzeuge)
            hinweise = []
            if versatz := jahr_korrektur(fahrzeuge, datensatz_jahr, datei):
                fahrzeuge = [(z.replace(year=z.year + versatz), *rest) for z, *rest in fahrzeuge]
                bericht.jahr_korrigiert.append(datei)
                hinweise.append(f"Die Uhr des Messgeräts stand auf {datensatz_jahr - versatz}; die "
                                f"Karte nimmt das Jahr des Datensatzes ({datensatz_jahr}).")
            lage = lagen.get(datei)
            genau = lage["genauigkeit"] if lage else ""
            bericht.genauigkeit[genau or "ohne"] = bericht.genauigkeit.get(genau or "ohne", 0) + 1
            if genau == "strasse":
                hinweise.append("Lage: nur die Straße ist bekannt (Punkt in der Straßenmitte).")
            if not lage:
                bericht.ohne_lage.append(datei)
            name = name_aus(r, datei)
            # dieselbe Adresse in mehreren Jahren = eine Stelle
            stelle = re.sub(r"\W+", "", name.lower()) or Path(datei).stem
            for tag, stunden in sorted(stunden_je_tag(fahrzeuge).items()):
                h0, h1 = min(stunden), max(stunden)
                kfz = [stunden[h][0] if h in stunden else None for h in range(h0, h1 + 1)]
                sv = [stunden[h][1] if h in stunden else None for h in range(h0, h1 + 1)]
                yield Zaehlung(
                    quelle=quelle["code"],
                    kennung=f"{Path(datei).stem}_{tag:%Y%m%d}",
                    stelle_roh=stelle,
                    name=name,
                    typ="Q",
                    lon=float(lage["lon"]) if lage else None,
                    lat=float(lage["lat"]) if lage else None,
                    lage="geokodiert" if lage else None,
                    datum=tag,
                    fenster=[(h0 * 60, (h1 + 1) * 60)],
                    intervall=60,
                    h0=h0,
                    stunden={"kfz": kfz, "sv": sv},
                    land=quelle["land"],
                    richtungen=2,
                    kategorien="Kfz (Radar), Schwerverkehr = Länge ab 8 m",
                    rohdatei=r.get("url"),
                    bemerkung=f"Messung {paket.get('title', '')}: {datei}",
                    hinweise=list(hinweise),
                    zusatz={"datei": datei, "paket": paket_pfad.parent.name,
                            "genauigkeit": genau},
                )
