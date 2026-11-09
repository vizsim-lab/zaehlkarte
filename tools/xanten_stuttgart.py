"""Werkzeug: Xanten (Mobilitätskonzept, opendata.ruhr) und Stuttgart (Ergebnisse der
Verkehrszählungen, opendata.stuttgart.de) – Metadaten über die CKAN-API und alle Ressourcen
(PDF als Text dazu)."""

import json
import pathlib
import subprocess
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
PAKETE = {
    "xanten": "https://opendata.ruhr/api/3/action/package_show?id=mobilitatskonzept",
    "stuttgart": "https://opendata.stuttgart.de/api/3/action/package_show?id=ergebnisse-der-verkehrszaehlungen",
}


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as a:
        return a.read()


for name, api in PAKETE.items():
    ordner = ZIEL / name
    ordner.mkdir(parents=True, exist_ok=True)
    try:
        paket = json.loads(hole(api))["result"]
    except Exception as e:  # noqa: BLE001
        (ordner / "fehler.txt").write_text(repr(e))
        continue
    (ordner / "paket.json").write_text(json.dumps(paket, ensure_ascii=False, indent=1))
    for r in paket.get("resources", []):
        url = r.get("url") or ""
        datei = urllib.parse.unquote(url.rsplit("/", 1)[-1])[:120] or r["id"]
        if not url.startswith("http"):
            continue
        try:
            daten = hole(url)
            if len(daten) > 40_000_000:
                print("zu groß", url, len(daten))
                continue
            pfad = ordner / datei
            pfad.write_bytes(daten)
            if daten.startswith(b"%PDF"):
                subprocess.run(["pdftotext", "-layout", str(pfad), str(pfad) + ".txt"], check=False)
            print(len(daten), url)
        except Exception as e:  # noqa: BLE001
            print("Fehler", url, repr(e)[:200])
