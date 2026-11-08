"""Werkzeug: Potsdam – alle Zählplan-PDFs (ein ZIP je Knoten), die Knotenliste und die
Nutzungsbedingungen der LHP (die Seite rendert erst im Browser, daher Playwright)."""

import hashlib
import io
import json
import pathlib
import sys
import urllib.request
import zipfile

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/potsdam")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
BASIS = "https://opendata.potsdam.de/api/explore/v2.1/catalog/datasets/verkehrszahlungen"
ZIEL.mkdir(parents=True, exist_ok=True)
protokoll = {}


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as a:
        return a.read()


# 1. Nutzungsbedingungen gerendert (Text, HTML und die Anfragen der Seite)
try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(locale="de-DE")
        anfragen = []
        seite.on("request", lambda r: anfragen.append(r.url))
        for name, url in {
            "nutzung_lhp": "https://opendata.potsdam.de/terms/terms-of-use/",
            "nutzung_ods": "https://potsdam.opendatasoft.com/terms/terms-of-use/",
            "bedingungen": "https://opendata.potsdam.de/terms/terms-and-conditions/",
            "datensatz": "https://opendata.potsdam.de/explore/dataset/verkehrszahlungen/information/",
        }.items():
            anfragen.clear()
            try:
                seite.goto(url, wait_until="networkidle", timeout=90000)
                seite.wait_for_timeout(4000)
                (ZIEL / f"{name}.txt").write_text(seite.inner_text("body"), encoding="utf-8")
                (ZIEL / f"{name}.gerendert.html").write_text(seite.content(), encoding="utf-8")
                protokoll[name] = [u for u in anfragen if "/static/" not in u][:80]
            except Exception as e:  # noqa: BLE001
                protokoll[name] = repr(e)[:300]
        browser.close()
except Exception as e:  # noqa: BLE001
    protokoll["playwright"] = repr(e)[:300]

for name, url in {"bedingungen.pdf": "https://opendata.potsdam.de/terms/terms-and-conditions.pdf"}.items():
    try:
        (ZIEL / name).write_bytes(hole(url))
    except Exception as e:  # noqa: BLE001
        protokoll[name] = repr(e)[:200]

# 2. Knotenliste (Export) und Metadaten frisch
export = json.loads(hole(f"{BASIS}/exports/json"))
(ZIEL / "export.json").write_text(json.dumps(export, ensure_ascii=False, indent=1), encoding="utf-8")
(ZIEL / "meta.json").write_bytes(hole(BASIS))

# 3. alle ZIPs -> pdf/<Knotennummer>/<Datei>
for x in export:
    url = x.get("zahlplan")
    if not url:
        continue
    knoten = str(x.get("kpnr") or url.rsplit("/", 1)[-1].removesuffix(".zip"))
    try:
        daten = hole(url)
        dateien = []
        with zipfile.ZipFile(io.BytesIO(daten)) as zf:
            for z in zf.infolist():
                if z.is_dir():
                    continue
                name = z.filename.rsplit("/", 1)[-1]
                ordner = ZIEL / "pdf" / knoten
                ordner.mkdir(parents=True, exist_ok=True)
                (ordner / name).write_bytes(zf.read(z))
                dateien.append(z.filename)
        protokoll[url] = {"bytes": len(daten), "sha256": hashlib.sha256(daten).hexdigest(),
                          "dateien": dateien}
    except Exception as e:  # noqa: BLE001
        protokoll[url] = repr(e)[:200]
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, indent=1, ensure_ascii=False))
print(sum(1 for v in protokoll.values() if isinstance(v, dict)), "ZIPs geholt")
