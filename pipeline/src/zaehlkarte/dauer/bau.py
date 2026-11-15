"""Dauerzählstellen holen und bauen: je Quelle aus config/quellen/dauer/ der Adapter
(`hole` -> pipeline/data/raw/, `lese` -> Messreihe), dann site.schreibe -> public/data/dauer/."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from zaehlkarte import gemeinden as gemeinden_
from zaehlkarte.config import Pfade, dauerquellen
from zaehlkarte.dauer import (
    aachen_rad,
    augsburg_fuss,
    augsburg_rad,
    berlin_rad,
    berlin_viz,
    bochum_rad,
    bonn_rad,
    bw_land,
    dortmund_rad,
    dresden_rad,
    duesseldorf_rad,
    essen_rad,
    hamburg_sta,
    leipzig_rad,
    mobidata_eco,
    moers_fuss,
    muenchen_rad,
    muenster_rad,
    ods_eco,
    ods_stunden,
    readi_urbanpulse,
    rostock_rad,
    vmz_rad,
)
from zaehlkarte.dauer import site as site_
from zaehlkarte.dauer.modell import Messreihe

ADAPTER = {"berlin_viz": berlin_viz, "hamburg_sta": hamburg_sta,
           "readi_urbanpulse": readi_urbanpulse, "mobidata_eco": mobidata_eco,
           "muenster_rad": muenster_rad, "aachen_rad": aachen_rad, "berlin_rad": berlin_rad,
           "muenchen_rad": muenchen_rad, "ods_eco": ods_eco, "dortmund_rad": dortmund_rad,
           "essen_rad": essen_rad, "leipzig_rad": leipzig_rad, "rostock_rad": rostock_rad,
           "bochum_rad": bochum_rad, "bonn_rad": bonn_rad, "duesseldorf_rad": duesseldorf_rad,
           "vmz_rad": vmz_rad, "dresden_rad": dresden_rad, "augsburg_fuss": augsburg_fuss,
           "ods_stunden": ods_stunden, "augsburg_rad": augsburg_rad, "bw_land": bw_land,
           "moers_fuss": moers_fuss}


def mit_gedaechtnis(pfade: Pfade | None = None) -> list[str]:
    """Codes der live-Quellen, deren Adapter die Stunden selbst aufhebt (`GEDAECHTNIS = True` im
    Modul) – für sie prüft `zaehlkarte dauer frische`, ob das Gedächtnis noch wächst."""
    return [c for c, q in dauerquellen(pfade).items()
            if getattr(ADAPTER[q["adapter"]], "GEDAECHTNIS", False)]


def hole(pfade: Pfade | None = None, nur: list[str] | None = None) -> tuple[list[str], list[str]]:
    """-> (Log, Quellen mit Fehler). Scheitert eine Quelle, laufen die anderen weiter – gebaut
    wird dann mit dem, was schon da ist (Rohdaten im Cache, Gedächtnis aus dem Release)."""
    import traceback

    from zaehlkarte import abruf

    pfade = pfade or Pfade()
    log: list[str] = []
    fehler: list[str] = []
    abruf.ausnahmen_setzen(dauerquellen(pfade), pfade=pfade)
    try:  # Gemeindegrenzen (ags je Stelle): ohne sie baut die Karte trotzdem, nur ags bleibt leer
        log += gemeinden_.hole(pfade)
    except Exception as e:  # noqa: BLE001
        log.append(f"FEHLER gemeinden: {e!r}")
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
    gemeinden, fehlt = gemeinden_.lese(pfade)
    dateien, zeilen = site_.schreibe(gelesen, pfade, erzeugt, gemeinden)
    alle = [f"{c}: {z}" for c, zs in berichte.items() for z in zs]
    return dateien, [*alle, *fehlt, *zeilen, *site_.statistik(gelesen)]
