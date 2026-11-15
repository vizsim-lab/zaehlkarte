"""Pfade der Nürnberg-Werkzeuge; über Umgebungsvariablen änderbar.

- NBG_ERGEBNIS: Overpass-Abzüge (Standard: ergebnis/ohne_lizenz dieses Branchs, Runden holen23–30)
- NBG_BERICHTE: die 16 Berichte als bericht_JJJJ.pdf (Standard: pipeline/data/raw/nuernberg eines
  Checkouts von main neben diesem; `uv run zaehlkarte fetch` holt sie mit Prüfsumme)
- NBG_ARBEIT:   Zwischenstände (Standard: arbeit/ neben diesen Dateien, nicht im Git)
"""
import os
from pathlib import Path

HIER = Path(__file__).resolve().parent
ERGEBNIS = Path(os.environ.get("NBG_ERGEBNIS", HIER.parents[1] / "ergebnis" / "ohne_lizenz"))
BERICHTE = Path(os.environ.get("NBG_BERICHTE", HIER.parents[2] / "zaehlkarte" / "pipeline" / "data" / "raw" / "nuernberg"))
ARBEIT = Path(os.environ.get("NBG_ARBEIT", HIER / "arbeit"))
ARBEIT.mkdir(parents=True, exist_ok=True)
