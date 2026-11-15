"""Erkundung (15.11.2026), Teil 4: Die Seite „Dauerzählstellen“ von BAYSIS lädt die Auswahl als
Web-Komponente <dauzergebnisseinternet> aus /resources/js/baysis.js (über 10 MB). Wohin fragt sie?
Ablage: das Skript (gz) und die Stellen darin, die nach Schnittstellen aussehen.

Aufruf: python3 tools/bw_fl4.py ergebnis/bw/fl4
"""

import gzip
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def main():
    url = "https://www.baysis.bayern.de/resources/js/baysis.js"
    for versuch in range(3):
        try:
            inhalt, _, art = R.oeffne(url, zeit=300, grenze=150_000_000)
            log("ok", url, len(inhalt), art)
            break
        except Exception as e:  # noqa: BLE001
            log("Fehler", versuch + 1, repr(e)[:200])
            time.sleep(10)
    else:
        return
    (ZIEL / "baysis.js.gz").write_bytes(gzip.compress(inhalt, 9))
    t = inhalt.decode("utf-8", "replace")
    aus = []
    # Zeichenketten, die nach Pfaden oder Adressen aussehen
    pfade = sorted(set(re.findall(r"""["'`]((?:https?:)?/[A-Za-z0-9_./{}$:-]*(?:api|rest|dauz|zaehl|verdat|svz|daten|download|csv|json|service)[A-Za-z0-9_./{}$:?=&-]*)["'`]""", t, re.I)))
    aus.append(f"## Pfade ({len(pfade)})")
    aus += pfade[:400]
    for wort in ["dauzergebnisseinternet", "dauz", "Zaehlstellennummer", "zaehlstellennummer",
                 "csv", "Stundenwerte", "stundenwerte", "apiUrl", "baseUrl", "environment"]:
        treffer = [m.start() for m in re.finditer(re.escape(wort), t)]
        aus.append(f"## {wort}: {len(treffer)} Treffer")
        for i in treffer[:25]:
            aus.append(repr(t[max(0, i - 250):i + 350]))
    (ZIEL / "stellen.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    with open(ZIEL / "log.txt", "a") as f:
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
