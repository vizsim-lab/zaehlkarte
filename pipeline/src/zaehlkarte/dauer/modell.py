"""Schema der Dauerzählstellen: Stellen und ihre Stundenwerte als Felder (Stelle × Tag × Stunde).

Werte sind Anzahlen je Stunde in Ortszeit (Stunde 8 = 8:00–8:59); -1 heißt „nicht gezählt“,
nie 0. Eine Tagessumme gibt es nur, wenn jede Stunde des Tages gezählt ist – am Tag der
Umstellung auf Sommerzeit hat der Tag 23 Stunden (2–3 Uhr gibt es nicht), am Tag der
Rückstellung steht in Stunde 2 die Summe beider Stunden 2–3 Uhr (`doppelt`).

Gruppen (wie die Quelle sie zählt, nicht umgerechnet):
- kfz  alle Kraftfahrzeuge
- lkw  Lkw laut Detektor (Klasse des Detektors, nicht der Schwerverkehr der Kurzzeitzählungen)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

GRUPPEN = ("kfz", "lkw")
LEER = -1


@dataclass
class Dauerstelle:
    quelle: str  # Code aus sources.yaml (Abschnitt `dauer:`)
    kennung: str  # stabil je Quelle (Berlin: Kurzname des Messquerschnitts, „TE001“)
    name: str  # Straße
    abschnitt: str | None  # Lage auf der Straße („zwischen … und …“)
    richtung: str | None  # Fahrtziel und Himmelsrichtung, wie die Quelle sie nennt
    lon: float
    lat: float
    land: str
    fahrstreifen: list[str] = field(default_factory=list)  # Spuren laut Stammdaten
    hinweise: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.quelle}:{self.kennung}"


@dataclass
class Messreihe:
    """Stundenwerte einer Quelle. `werte[gruppe]`: int32-Feld [Stellen, Tage, 24], -1 = nicht
    gezählt; `doppelt`: bool [Stellen, Tage] – Stunde 2 enthält zwei Stunden (Rückstellung)."""

    quelle: str
    von: date
    tage: int
    stellen: list[Dauerstelle]
    werte: dict[str, np.ndarray]
    doppelt: np.ndarray
    # Abschnitte der Reihe mit eigenem Verfahren, für die Hinweise: [(von, bis, Text)]
    verfahren: list[tuple[date, date, str]] = field(default_factory=list)

    @classmethod
    def leer(cls, quelle: str, von: date, bis: date, stellen: list[Dauerstelle],
             gruppen: tuple[str, ...] = GRUPPEN) -> Messreihe:
        tage = (bis - von).days + 1
        form = (len(stellen), tage, 24)
        return cls(quelle, von, tage, stellen,
                   {g: np.full(form, LEER, dtype=np.int32) for g in gruppen},
                   np.zeros(form[:2], dtype=bool))

    def tag(self, i: int) -> date:
        return self.von + timedelta(days=i)

    def index(self, tag: date) -> int:
        return (tag - self.von).days


def umstellungen(jahr: int) -> tuple[date, date]:
    """(Sommerzeit-Beginn, Sommerzeit-Ende): letzter Sonntag im März bzw. Oktober (seit 1996)."""

    def letzter_sonntag(monat: int) -> date:
        d = date(jahr, monat, 31)
        return d - timedelta(days=(d.weekday() - 6) % 7)

    return letzter_sonntag(3), letzter_sonntag(10)


def erwartete_stunden(von: date, tage: int) -> np.ndarray:
    """bool [Tage, 24]: Stunden, die es am Tag in Ortszeit gibt (Sommerzeit-Beginn ohne 2 Uhr)."""
    erwartet = np.ones((tage, 24), dtype=bool)
    for jahr in range(von.year, (von + timedelta(days=tage - 1)).year + 1):
        beginn, _ = umstellungen(jahr)
        i = (beginn - von).days
        if 0 <= i < tage:
            erwartet[i, 2] = False
    return erwartet


def tagessummen(reihe: Messreihe, gruppe: str) -> tuple[np.ndarray, np.ndarray]:
    """(Summe [Stellen, Tage] mit -1 = nicht vollständig gezählt, gezählte Stunden [Stellen, Tage]).

    Vollständig heißt: jede Stunde, die es an dem Tag gibt, hat einen Wert."""
    w = reihe.werte[gruppe]
    erwartet = erwartete_stunden(reihe.von, reihe.tage)[None, :, :]
    gezaehlt = (w >= 0) & erwartet
    n = gezaehlt.sum(axis=2).astype(np.int16)
    summe = np.where(gezaehlt, w, 0).sum(axis=2, dtype=np.int64)
    voll = n == erwartet.sum(axis=2)
    return np.where(voll, summe, LEER).astype(np.int64), n
