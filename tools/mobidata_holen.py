"""Einmaliger Abruf: alle Zähldaten-Pakete von MobiData BW (CKAN) samt ZIP-Inhalt.

Läuft in GitHub Actions (aus der Entwicklungsumgebung ist mobidata-bw.de nicht erreichbar).
Schreibt je Paket package.json, die Übersichts-Excel und aus den ZIPs alle Tabellen
(xlsx/xls/csv); PDFs werden nur gelistet. Nur Standardbibliothek.
"""

import hashlib
import io
import json
import pathlib
import sys
import urllib.parse
import urllib.request
import zipfile

API = "https://mobidata-bw.de/api/3/action/"
UA = {"User-Agent": "zaehlkarte-datenabruf (+https://github.com/vizsim-lab/zaehlkarte)"}
BEKANNT = {
    "zaehldaten-ravensburg",
    "zaehldaten-stadt-weingarten",
    "zaehldaten-gemeinde-berg",
    "zaehldaten-gemeinde-baienfurt",
    "zaehldaten-gemeinde-baindt",
}
TABELLE = (".xlsx", ".xls", ".xlsm", ".csv")


def hole(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def api(action: str, **params) -> dict:
    url = API + action + "?" + urllib.parse.urlencode(params)
    return json.loads(hole(url))["result"]


def main(ziel: pathlib.Path) -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    namen = set(BEKANNT)
    for q in ({"fq": "groups:verkehrszaehldaten"}, {"q": "Verkehrszählungen"}, {"q": "Zähldaten"}):
        try:
            for p in api("package_search", rows=200, **q)["results"]:
                if "zaehl" in p["name"]:
                    namen.add(p["name"])
        except Exception as e:  # noqa: BLE001
            print("Suche", q, "fehlgeschlagen:", e)
    index = []
    for name in sorted(namen):
        try:
            paket = api("package_show", id=name)
        except Exception as e:  # noqa: BLE001
            print(name, "fehlt:", e)
            continue
        ordner = ziel / name
        ordner.mkdir(exist_ok=True)
        (ordner / "package.json").write_text(json.dumps(paket, ensure_ascii=False, indent=1))
        for res in paket.get("resources", []):
            url = res.get("url") or ""
            if not url.startswith("http"):
                continue
            try:
                daten = hole(url)
            except Exception as e:  # noqa: BLE001
                print(url, "nicht abrufbar:", e)
                index.append({"paket": name, "url": url, "fehler": str(e)})
                continue
            datei = urllib.parse.unquote(url.rsplit("/", 1)[-1])
            eintrag = {
                "paket": name,
                "url": url,
                "datei": datei,
                "bytes": len(daten),
                "sha256": hashlib.sha256(daten).hexdigest(),
            }
            if datei.lower().endswith(".zip"):
                inhalt = []
                with zipfile.ZipFile(io.BytesIO(daten)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        inhalt.append({"name": info.filename, "bytes": info.file_size})
                        if info.filename.lower().endswith(TABELLE):
                            pfad = ordner / "zip" / info.filename
                            pfad.parent.mkdir(parents=True, exist_ok=True)
                            pfad.write_bytes(zf.read(info))
                eintrag["inhalt"] = inhalt
            elif not datei.lower().endswith(".pdf"):
                (ordner / datei).write_bytes(daten)
            index.append(eintrag)
            print(name, datei, len(daten))
    (ziel / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))
