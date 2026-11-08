"""Werkzeug: Anhänge der Rostocker FragDenStaat-Anfrage „Verkehrszählung“ (2020) als PDF und
Text (die /anhang/-Seiten sind HTML; die Dateien liegen auf media.frag-den-staat.de)."""

import pathlib
import subprocess
import sys
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/rostock")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
ZIEL.mkdir(parents=True, exist_ok=True)
ANHAENGE = [
    "519369/Anschreiben_konvertiert_geschwaerzt.pdf", "519369/Z_1250_konvertiert.pdf",
    "519369/ZUS_alle_Jahre_konvertiert.pdf", "519369/ZUS_pro_Jahr_konvertiert.pdf",
    "519697/K_0824.pdf", "519697/K_0828.pdf", "519697/Z_0824_konvertiert.pdf",
    "519697/Z_0828_konvertiert.pdf",
]
for a in ANHAENGE:
    url = "https://media.frag-den-staat.de/files/foi/" + a
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
            daten = r.read()
        pfad = ZIEL / a.rsplit("/", 1)[-1]
        pfad.write_bytes(daten)
        subprocess.run(["pdftotext", "-layout", str(pfad), str(pfad.with_suffix(".txt"))], check=False)
        print(len(daten), url)
    except Exception as e:  # noqa: BLE001
        print("Fehler", url, repr(e)[:200])
