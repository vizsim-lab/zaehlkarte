"""Werkzeug: Potsdam – Nutzungsbedingungen und einige Zählplan-ZIPs zum Ansehen holen."""

import io
import json
import pathlib
import sys
import urllib.request
import zipfile

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/potsdam")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
ZIEL.mkdir(parents=True, exist_ok=True)
protokoll = {}


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as a:
        return a.read()


for name, url in {"nutzung.html": "https://potsdam.opendatasoft.com/terms/terms-of-use/",
                  "nutzung2.html": "https://opendata.potsdam.de/terms/terms-of-use/",
                  "info.html": "https://opendata.potsdam.de/explore/dataset/verkehrszahlungen/information/"}.items():
    try:
        (ZIEL / name).write_bytes(hole(url))
        protokoll[name] = "ok"
    except Exception as e:  # noqa: BLE001
        protokoll[name] = repr(e)[:200]

export = json.loads(pathlib.Path("ergebnis/staedte/potsdam/export.json").read_text())
zips = [x["zahlplan"] for x in export if x.get("zahlplan")]
groessen = {}
for i, url in enumerate(zips):
    try:
        daten = hole(url)
        groessen[url] = len(daten)
        with zipfile.ZipFile(io.BytesIO(daten)) as zf:
            protokoll[url] = [(z.filename, z.file_size) for z in zf.infolist()]
            if i < 8:
                zf.extractall(ZIEL / "zip" / url.rsplit("/", 1)[-1].removesuffix(".zip"))
    except Exception as e:  # noqa: BLE001
        protokoll[url] = repr(e)[:200]
protokoll["summe_bytes"] = sum(groessen.values())
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, indent=1, ensure_ascii=False))
print(protokoll["summe_bytes"], "Bytes in", len(groessen), "ZIPs")
