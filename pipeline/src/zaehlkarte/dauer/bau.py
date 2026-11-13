"""Dauerzählstellen holen und bauen: je Quelle aus `dauer:` in sources.yaml der Adapter
(`hole` -> pipeline/data/raw/, `lese` -> Messreihe), dann site.schreibe -> public/data/dauer/."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade, dauerquellen
from zaehlkarte.dauer import (
    aachen_rad,
    berlin_rad,
    berlin_viz,
    bochum_rad,
    bonn_rad,
    dortmund_rad,
    duesseldorf_rad,
    essen_rad,
    hamburg_sta,
    leipzig_rad,
    mobidata_eco,
    muenchen_rad,
    muenster_rad,
    ods_eco,
    readi_urbanpulse,
    rostock_rad,
)
from zaehlkarte.dauer import site as site_
from zaehlkarte.dauer.modell import Messreihe

ADAPTER = {"berlin_viz": berlin_viz, "hamburg_sta": hamburg_sta,
           "readi_urbanpulse": readi_urbanpulse, "mobidata_eco": mobidata_eco,
           "muenster_rad": muenster_rad, "aachen_rad": aachen_rad, "berlin_rad": berlin_rad,
           "muenchen_rad": muenchen_rad, "ods_eco": ods_eco, "dortmund_rad": dortmund_rad,
           "essen_rad": essen_rad, "leipzig_rad": leipzig_rad, "rostock_rad": rostock_rad,
           "bochum_rad": bochum_rad, "bonn_rad": bonn_rad, "duesseldorf_rad": duesseldorf_rad}


def hole(pfade: Pfade | None = None, nur: list[str] | None = None) -> tuple[list[str], list[str]]:
    """-> (Log, Quellen mit Fehler). Scheitert eine Quelle, laufen die anderen weiter – gebaut
    wird dann mit dem, was schon da ist (Rohdaten im Cache, Gedächtnis aus dem Release)."""
    import traceback

    pfade = pfade or Pfade()
    log: list[str] = []
    fehler: list[str] = []
    for code, q in dauerquellen(pfade).items():
        if nur and code not in nur:
            continue
        try:
            log += ADAPTER[q["adapter"]].hole(q, pfade)
        except Exception as e:  # noqa: BLE001 – eine Quelle darf die anderen nicht aufhalten
            fehler.append(code)
            log.append(f"FEHLER {code}: {e!r}")
            log += [f"  {z}" for z in traceback.format_exc().splitlines()[-6:]]
    return log, fehler


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
