"""Werkzeug: die PDFs aus dem Münster-ZIP („Verkehrszählung“) auf den Branch legen."""

import io
import pathlib
import sys
import urllib.request
import zipfile

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/muenster_pdf")
URL = "https://opendata.stadt-muenster.de/sites/default/files/Verkehrsz%C3%A4hlung.zip"
anfrage = urllib.request.Request(URL, headers={"User-Agent": "zaehlkarte-werkzeug/0.1"})
with urllib.request.urlopen(anfrage, timeout=300) as antwort:
    daten = antwort.read()
ZIEL.mkdir(parents=True, exist_ok=True)
n = 0
with zipfile.ZipFile(io.BytesIO(daten)) as zf:
    for info in zf.infolist():
        if info.is_dir() or not info.filename.lower().endswith(".pdf"):
            continue
        name = pathlib.PurePosixPath(info.filename).name
        (ZIEL / name).write_bytes(zf.read(info))
        n += 1
print(n, "PDFs")
