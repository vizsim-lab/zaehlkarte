"""Dauerzählstellen holen und bauen: je Quelle aus `dauer:` in sources.yaml der Adapter
(`hole` -> pipeline/data/raw/, `lese` -> Messreihe), dann site.schreibe -> public/data/dauer/."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade, dauerquellen
from zaehlkarte.dauer import berlin_viz
from zaehlkarte.dauer import site as site_
from zaehlkarte.dauer.modell import Messreihe

ADAPTER = {"berlin_viz": berlin_viz}


def hole(pfade: Pfade | None = None, nur: list[str] | None = None) -> list[str]:
    pfade = pfade or Pfade()
    log: list[str] = []
    for code, q in dauerquellen(pfade).items():
        if not nur or code in nur:
            log += ADAPTER[q["adapter"]].hole(q, pfade)
    return log


def baue(pfade: Pfade | None = None, nur: list[str] | None = None
         ) -> tuple[list[tuple[dict, Messreihe]], dict[str, list[str]]]:
    pfade = pfade or Pfade()
    gelesen, berichte = [], {}
    for code, q in dauerquellen(pfade).items():
        if nur and code not in nur:
            continue
        modul = ADAPTER[q["adapter"]]
        bericht = modul.Bericht()
        gelesen.append((q, modul.lese(q, pfade, bericht)))
        berichte[code] = bericht.zeilen()
    return gelesen, berichte


def site(pfade: Pfade | None = None, erzeugt: date | None = None) -> tuple[list[Path], list[str]]:
    gelesen, berichte = baue(pfade)
    dateien, zeilen = site_.schreibe(gelesen, pfade, erzeugt)
    alle = [f"{c}: {z}" for c, zs in berichte.items() for z in zs]
    return dateien, [*alle, *zeilen, *site_.statistik(gelesen)]
