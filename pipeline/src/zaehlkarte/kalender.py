"""Zähltag einordnen: Schultag, Ferien, Feiertag oder Wochenende – je Bundesland.

Schulferien kommen aus `config/schulferien_<land>.csv` (Spalten von, bis, ferien,
schuljahr, gebiet, quelle). Ein Schuljahr gilt als abgedeckt, wenn es in der Spalte
`schuljahr` vorkommt; fehlt es, ist ein Werktag „unbekannt“ statt „Schultag“.
Berlin hatte bis Sommer 1991 getrennte Ferien für West und Ost (Spalte `gebiet`).

Kalender-Logik portiert aus vizsim/berlin-traffic-counts_schulwege (ferien.py, MIT).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from pathlib import Path

GEBIETE = ("west", "ost")
TAGTYPEN = ("schule", "ferien", "feiertag", "wochenende")


@dataclass(frozen=True)
class Ferien:
    von: date
    bis: date  # einschließlich
    name: str
    gebiet: str = "alle"  # "alle" | "west" | "ost"


def schuljahr(tag: date) -> str:
    """Schuljahr mit Grenze 1. August: 2019-09-02 -> '2019/2020'."""
    y = tag.year if tag.month >= 8 else tag.year - 1
    return f"{y}/{y + 1}"


class Ferienkalender:
    def __init__(self, ferien: list[Ferien], abgedeckt: dict[str, set[str]]):
        self.ferien = sorted(ferien, key=lambda f: f.von)
        self.abgedeckt = abgedeckt  # Gebiet -> Schuljahre

    @classmethod
    def lade(cls, pfad: Path) -> Ferienkalender:
        ferien: list[Ferien] = []
        abgedeckt: dict[str, set[str]] = {g: set() for g in ("alle", *GEBIETE)}
        with pfad.open(encoding="utf-8") as f:
            for row in csv.DictReader(r for r in f if not r.startswith("#")):
                gebiet = row.get("gebiet") or "alle"
                gebiet = "alle" if gebiet in ("berlin", "alle") else gebiet
                ferien.append(
                    Ferien(
                        date.fromisoformat(row["von"]),
                        date.fromisoformat(row["bis"]),
                        row["ferien"],
                        gebiet,
                    )
                )
                if row.get("schuljahr"):
                    for g in ("alle", *GEBIETE) if gebiet == "alle" else (gebiet,):
                        abgedeckt[g].add(row["schuljahr"])
        return cls(ferien, abgedeckt)

    def _treffer(self, tag: date, gebiet: str) -> Ferien | None:
        for f in self.ferien:
            if f.von <= tag <= f.bis and f.gebiet in ("alle", gebiet):
                return f
            if f.von > tag:
                break
        return None

    def status(self, tag: date, gebiet: str | None = None) -> tuple[str | None, str | None]:
        """('ferien', Name) | ('schule', None) | (None, None) = unbekannt.

        Mit getrennten Kalendern (West/Ost) und unbekanntem Gebiet ist ein Tag nur dann
        sicher, wenn beide Kalender dasselbe sagen."""
        if gebiet in GEBIETE:
            gebiete: tuple[str, ...] = (gebiet,)
        else:
            gebiete = GEBIETE if self._getrennt(tag) else ("alle",)
        ergebnisse = set()
        name = None
        for g in gebiete:
            f = self._treffer(tag, g)
            if f:
                ergebnisse.add("ferien")
                name = name or f.name
            elif schuljahr(tag) in self.abgedeckt[g]:
                ergebnisse.add("schule")
            else:
                ergebnisse.add(None)
        s = ergebnisse.pop() if len(ergebnisse) == 1 else None
        return s, (name if s == "ferien" else None)

    def _getrennt(self, tag: date) -> bool:
        sj = schuljahr(tag)
        return sj not in self.abgedeckt["alle"] and any(sj in self.abgedeckt[g] for g in GEBIETE)


def ostersonntag(jahr: int) -> date:
    """Gregorianischer Ostersonntag (anonymer Algorithmus nach Meeus/Jones/Butcher)."""
    a, b, c = jahr % 19, jahr // 100, jahr % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = (h + l - 7 * m + 114) % 31 + 1
    return date(jahr, monat, tag)


@cache
def feiertage(land: str, jahr: int) -> dict[date, str]:
    """Gesetzliche Feiertage (bundesweit + Land BB, BE, BW oder NW)."""
    ostern = ostersonntag(jahr)
    tage = {
        date(jahr, 1, 1): "Neujahr",
        ostern - timedelta(days=2): "Karfreitag",
        ostern + timedelta(days=1): "Ostermontag",
        date(jahr, 5, 1): "Tag der Arbeit",
        ostern + timedelta(days=39): "Christi Himmelfahrt",
        ostern + timedelta(days=50): "Pfingstmontag",
        date(jahr, 12, 25): "1. Weihnachtstag",
        date(jahr, 12, 26): "2. Weihnachtstag",
    }
    if jahr >= 1990:
        tage[date(jahr, 10, 3)] = "Tag der Deutschen Einheit"
    if jahr <= 1990:
        tage[date(jahr, 6, 17)] = "Tag der deutschen Einheit (17. Juni)"
    if jahr <= 1994:  # bis 1994 bundesweit Feiertag
        nov22 = date(jahr, 11, 22)
        tage[nov22 - timedelta(days=(nov22.weekday() - 2) % 7)] = "Buß- und Bettag"
    if jahr == 2017:
        tage[date(2017, 10, 31)] = "Reformationstag (500 Jahre)"
    if land == "BE":
        if jahr >= 2019:
            tage[date(jahr, 3, 8)] = "Internationaler Frauentag"
        if jahr in (2020, 2025):
            tage[date(jahr, 5, 8)] = f"{75 if jahr == 2020 else 80}. Jahrestag der Befreiung"
    elif land == "BW":
        tage[date(jahr, 1, 6)] = "Heilige Drei Könige"
        tage[ostern + timedelta(days=60)] = "Fronleichnam"
        tage[date(jahr, 11, 1)] = "Allerheiligen"
    elif land == "NW":
        tage[ostern + timedelta(days=60)] = "Fronleichnam"
        tage[date(jahr, 11, 1)] = "Allerheiligen"
    elif land == "BB":
        tage[date(jahr, 10, 31)] = "Reformationstag"
    return tage


def tagtyp(
    tag: date | None, land: str, kalender: Ferienkalender | None, gebiet: str | None = None
) -> tuple[str | None, str | None]:
    """('schule' | 'ferien' | 'feiertag' | 'wochenende' | None, Name)."""
    if tag is None:
        return None, None
    if tag.weekday() >= 5:
        return "wochenende", ("Samstag" if tag.weekday() == 5 else "Sonntag")
    name = feiertage(land, tag.year).get(tag)
    if name:
        return "feiertag", name
    if kalender is None:
        return None, None
    return kalender.status(tag, gebiet)
