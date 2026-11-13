"""Nur die Rad-Quellen bauen (Code von app/), Ausgabe nach <ziel>/public/data/dauer; Bericht."""
import resource
import sys
import time
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bau, site

RAD = ["mobidata_rad", "muenster_rad", "aachen_rad", "berlin_rad", "muenchen_rad"]
ziel = Path(sys.argv[1])
pfade = Pfade(repo=ziel)
t0 = time.time()
gelesen, berichte = bau.baue(pfade, nur=RAD)
print(f"gelesen in {time.time() - t0:.0f} s")
for c, zs in berichte.items():
    for z in zs:
        print(f"{c}: {z}")
dateien, zeilen = site.schreibe(gelesen, pfade)
for z in [*zeilen, *site.statistik(gelesen)]:
    print(z)
print(f"fertig in {time.time() - t0:.0f} s, RSS-Spitze "
      f"{resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6:.2f} GB, {len(dateien)} Dateien")
