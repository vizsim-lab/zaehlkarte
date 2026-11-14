"""Werkzeug: Seiten aus einer Liste („Kommune | URL“) gezielt lesen – wie tools/land_lesen.py, aber
mit mehr Auszügen je Seite und Datei. Jeder Abruf nur, wenn robots.txt ihn erlaubt.
Aufruf: python3 tools/gezielt_lesen.py ergebnis/runde3/gezielt1 tools/r3_gezielt_1.txt
"""

import concurrent.futures as cf
import json
import pathlib
import sys

sys.argv = [sys.argv[0], sys.argv[1], "40"] + sys.argv[2:]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import land_lesen as L  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
LISTE = pathlib.Path(sys.argv[3])
_auszuege = L.auszuege
L.auszuege = lambda text, n: _auszuege(text, n * 3)  # mehr Auszüge als in der Durchsicht

ziele = [[x.strip() for x in z.split(" | ", 1)] for z in LISTE.read_text().splitlines()
         if " | " in z and not z.startswith("#")]
with cf.ThreadPoolExecutor(max_workers=8) as pool:
    aus = list(pool.map(lambda kz: {"kommune": kz[0]} | L.lies(kz[1]), ziele))
(ZIEL / "seiten.json").write_text(json.dumps(aus, ensure_ascii=False, indent=0))
print(len(aus), "gelesen", sum(1 for a in aus if "fehler" not in a))
