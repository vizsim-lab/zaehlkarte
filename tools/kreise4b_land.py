"""Runde 4b: nur die Landkreise eines Landes prüfen – tools/runde4.py (Startseite, Plausibilität
des Kreises, Links, Sitemap, Suche, neue Begriffe) mit den Kreis-Webseiten aus tools/kreise4b.py
(ergebnis/runde4b/kreise_web.json), ohne Gemeinden und Verbände (die prüft Runde 4).

    python3 tools/kreise4b_land.py ergebnis/runde4b/<LAND> <LAND>
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import runde4 as R4  # noqa: E402  (liest beim Import sys.argv: Ziel, Land)

R4.ZIELE = {"kreise": R4.ZIELE["kreise"], "gemeinden": [], "verbaende": []}
R4.EXTRA = {}
R4.main()
