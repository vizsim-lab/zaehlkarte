"""Werkzeug: KMK-Ferienkalender 2026/27 und 2027/28 als PDF ablegen.

Für pipeline/werkzeuge/kmk_ferien.py (Kalender aller 16 Länder): Es liest die Tabelle jetzt mit
pdfplumber aus dem PDF statt aus dem Text von pdftotext – mehrzeilige Zellen lassen sich dort
nicht sicher einem Land zuordnen. Die PDFs bis 2025/26 liegen schon in ergebnis/ferien/; die
beiden jüngeren hat tools/dauer_kmk.py (werkzeug/dauer2) nur als Text behalten. Abruf nur, was
robots.txt erlaubt (tools/robots.py).
"""

import json
import pathlib
import sys

from robots import TEXTE, oeffne

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/ferien")
URLS = {
    "2026_27": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2026_27.pdf",
    "2027_28": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2027_28.pdf",
}

ZIEL.mkdir(parents=True, exist_ok=True)
protokoll = {}
for jahr, url in URLS.items():
    try:
        inhalt, ziel_url, art = oeffne(url, zeit=120)
        if not inhalt.startswith(b"%PDF"):
            raise ValueError(f"kein PDF ({art})")
        (ZIEL / f"kmk_{jahr}.pdf").write_bytes(inhalt)
        protokoll[jahr] = {"url": url, "abgerufen_von": ziel_url, "bytes": len(inhalt)}
        print("ok", url, len(inhalt), flush=True)
    except Exception as e:  # noqa: BLE001 – im Protokoll festhalten, weiter mit dem nächsten
        protokoll[jahr] = {"url": url, "fehler": repr(e)}
        print("fehler", url, repr(e), flush=True)
protokoll["robots.txt"] = {k: v[:2000] for k, v in TEXTE.items()}
(ZIEL / "protokoll_2026-2028.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1))
