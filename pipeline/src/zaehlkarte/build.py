"""Alle Quellen lesen -> Zählungen im gemeinsamen Schema, verortet und zu Stellen gruppiert.

1. Jeder live-Adapter aus sources.yaml liefert Zählungen (`adapters/`).
2. Zähltag einordnen (Schultag, Ferien, Feiertag, Wochenende) mit dem Kalender der Quelle.
3. Lage übertragen: Zählungen ohne Lage bekommen die Lage ihrer Zählstellen-Kennung, wenn alle
   verorteten Zählungen dieser Kennung an einem Ort liegen (oder genau eine Gruppe davon den
   gleichen Namen trägt).
4. Stellen bilden: je Quelle und Kennung die Zählungen, die nah beieinander liegen (150 m).
   Liegt eine Kennung an mehreren Orten (Berlin vergibt Kennungen neu), heißen die weiteren
   Stellen „K10921-2“, „K10921-3“ … in der Reihenfolge ihrer ersten Zählung. Die Nummern hängen
   von allen Zählungen der Kennung ab; neue Daten können sie verschieben.
"""

from __future__ import annotations

import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from zaehlkarte import adapters
from zaehlkarte.config import Pfade, quellen
from zaehlkarte.kalender import ferienkalender, schuljahr, tagtyp
from zaehlkarte.modell import Zaehlung

NAH_M = 150  # Zählungen einer Kennung, die so nah liegen, sind eine Stelle
EINDEUTIG_M = 300  # Lage übertragen nur, wenn alle verorteten Zählungen so nah liegen
LAGE_RANG = {"gps": 0, "quelle": 1, "geokodiert": 2, "uebertragen": 3}


def abstand_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Näherung für kurze Strecken (äquirektangulär) in Metern."""
    lon1, lat1 = a
    lon2, lat2 = b
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6371000 * math.hypot(x, y)


def gruppiere(punkte: list[tuple[float, float]], radius: float) -> list[list[int]]:
    """Single-Linkage-Gruppen (Indizes) – Punkte, die über Nachbarn ≤ radius verbunden sind."""
    eltern = list(range(len(punkte)))

    def wurzel(i: int) -> int:
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]
            i = eltern[i]
        return i

    for i in range(len(punkte)):
        for j in range(i + 1, len(punkte)):
            if abstand_m(punkte[i], punkte[j]) <= radius:
                eltern[wurzel(j)] = wurzel(i)
    gruppen: dict[int, list[int]] = defaultdict(list)
    for i in range(len(punkte)):
        gruppen[wurzel(i)].append(i)
    return list(gruppen.values())


def _median(punkte: list[tuple[float, float]]) -> tuple[float, float]:
    return (
        round(statistics.median(p[0] for p in punkte), 6),
        round(statistics.median(p[1] for p in punkte), 6),
    )


@dataclass
class Stelle:
    id: str
    quelle: str
    name: str
    typ: str
    lon: float
    lat: float
    lage: str
    zaehlungen: list[Zaehlung] = field(default_factory=list)


@dataclass
class Gebaut:
    stellen: list[Stelle]
    ohne_lage: list[Zaehlung]
    berichte: dict[str, list[str]]


def uebertrage_lage(zaehlungen: list[Zaehlung]) -> int:
    """Lage von Zählungen derselben Kennung übernehmen, wo das eindeutig ist. -> Anzahl."""
    je_kennung: dict[tuple, list[Zaehlung]] = defaultdict(list)
    for z in zaehlungen:
        if z.stelle_roh:
            je_kennung[(z.quelle, z.stelle_roh)].append(z)
    n = 0
    for gruppe in je_kennung.values():
        mit = [z for z in gruppe if z.lon is not None]
        ohne = [z for z in gruppe if z.lon is None]
        if not mit or not ohne:
            continue
        orte = gruppiere([(z.lon, z.lat) for z in mit], EINDEUTIG_M)
        for z in ohne:
            if len(orte) == 1:
                ziel = orte[0]
            else:  # mehrere Orte: nur, wenn genau einer den gleichen Namen trägt
                name = z.name.casefold()
                passend = [o for o in orte if any(mit[i].name.casefold() == name for i in o)]
                if len(passend) != 1:
                    continue
                ziel = passend[0]
            z.lon, z.lat = _median([(mit[i].lon, mit[i].lat) for i in ziel])
            z.lage = "uebertragen"
            n += 1
    return n


def bilde_stellen(zaehlungen: list[Zaehlung]) -> list[Stelle]:
    je_kennung: dict[tuple, list[Zaehlung]] = defaultdict(list)
    for z in zaehlungen:
        if z.lon is None:
            continue
        schluessel = z.stelle_roh or f"_{z.kennung}"
        je_kennung[(z.quelle, schluessel)].append(z)
    stellen = []
    for (quelle, kennung), gruppe in sorted(je_kennung.items()):
        gruppe.sort(key=lambda z: (z.datum or date.min, z.kennung))
        teile = gruppiere([(z.lon, z.lat) for z in gruppe], NAH_M)
        teile.sort(key=lambda t: min(t))  # erste Zählung bestimmt die Reihenfolge
        for n, teil in enumerate(teile):
            glieder = [gruppe[i] for i in sorted(teil)]
            letzte = glieder[-1]
            stellen.append(
                Stelle(
                    id=f"{quelle}:{kennung}" + (f"-{n + 1}" if n else ""),
                    quelle=quelle,
                    name=letzte.name,
                    typ=letzte.typ,
                    lon=_median([(z.lon, z.lat) for z in glieder])[0],
                    lat=_median([(z.lon, z.lat) for z in glieder])[1],
                    lage=min((z.lage or "uebertragen" for z in glieder), key=LAGE_RANG.get),
                    zaehlungen=glieder,
                )
            )
    return stellen


def baue(pfade: Pfade | None = None, nur: list[str] | None = None) -> Gebaut:
    pfade = pfade or Pfade()
    zaehlungen: list[Zaehlung] = []
    berichte: dict[str, list[str]] = {}
    for code, q in quellen(pfade).items():
        if nur and code not in nur:
            continue
        modul = adapters.ADAPTER[q["adapter"]]
        bericht = modul.Bericht()
        kalender = ferienkalender(q["land"], pfade.config)
        anzahl = 0
        ohne_kalender: Counter[str] = Counter()  # Werktage, deren Schuljahr der Kalender nicht hat
        for z in modul.lese(q, pfade, bericht):
            z.tagtyp, z.tagname = tagtyp(z.datum, q["land"], kalender, z.gebiet)
            if z.datum and z.tagtyp is None:
                ohne_kalender[schuljahr(z.datum)] += 1
            zaehlungen.append(z)
            anzahl += 1
        berichte[code] = [f"{anzahl} Zählungen", *bericht.zeilen()]
        if ohne_kalender:
            berichte[code].append(
                f"ohne Ferienkalender ({q['land']}, Tag unbekannt): {ohne_kalender.total()} "
                f"Zählungen in den Schuljahren {', '.join(sorted(ohne_kalender))}")
    n = uebertrage_lage(zaehlungen)
    berichte["lage"] = [f"Lage übertragen: {n}"]
    stellen = bilde_stellen(zaehlungen)
    ohne = [z for z in zaehlungen if z.lon is None]
    berichte["lage"].append(f"nicht verortet: {len(ohne)} von {len(zaehlungen)}")
    return Gebaut(stellen, ohne, berichte)
