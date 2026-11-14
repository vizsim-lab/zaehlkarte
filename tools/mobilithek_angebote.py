"""Werkzeug: Metadaten einzelner Mobilithek-Angebote (Lizenz, Zugang, Verteilungen) ablegen.
Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py).
Aufruf: python3 tools/mobilithek_angebote.py ergebnis/runde3/angebote <id> [<id> …]
"""

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
for i in sys.argv[2:]:
    try:
        inhalt, _, _ = R.oeffne(f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{i}", zeit=60)
        (ZIEL / f"{i}.json").write_text(json.dumps(json.loads(inhalt), ensure_ascii=False, indent=1))
        print(i, "ok")
    except Exception as e:  # noqa: BLE001
        (ZIEL / f"{i}.fehler").write_text(repr(e)[:300])
        print(i, repr(e)[:200])
    time.sleep(1)
