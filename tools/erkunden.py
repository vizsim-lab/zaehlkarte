"""Erkundung (Entwicklungswerkzeug): Open-Data-Portale nach Verkehrszählungen durchsuchen und
Kandidaten herunterladen. Läuft in GitHub Actions, weil viele Portale aus der
Entwicklungsumgebung nicht erreichbar sind. Nur Standardbibliothek.

Ergebnis in ergebnis/: index.json (alle Treffer mit Ressourcen), status.json (welche Portale
antworten), je Paket die Tabellen (xls/xlsx/csv/json) und aus ZIPs die Tabellen plus bis zu
zwei Beispiel-PDFs.
"""

import io
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import zipfile

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}
CKAN = {
    "opennrw": "https://ckan.open.nrw.de/api/3/action/package_search",
    "govdata": "https://www.govdata.de/ckan/api/3/action/package_search",
    "leipzig": "https://opendata.leipzig.de/api/3/action/package_search",
    "dresden": "https://opendata.dresden.de/api/3/action/package_search",
    "hamburg": "https://suche.transparenz.hamburg.de/api/3/action/package_search",
    "mobidata": "https://mobidata-bw.de/api/3/action/package_search",
    "rostock": "https://www.opendata-hro.de/api/3/action/package_search",
    "bonn": "https://opendata.bonn.de/api/3/action/package_search",
}
SUCHE = ["Verkehrszählung", "Verkehrszählungen", "Knotenpunktzählung", "Knotenstromzählung",
         "Verkehrserhebung", "Zähldaten", "Verkehrsmengen"]
ODS = {"potsdam": "https://opendata.potsdam.de", "mannheim": "https://mannheim.opendatasoft.com",
       "dortmund": "https://open-data.dortmund.de", "bonn_ods": "https://opendata.bonn.de"}
TABELLE = (".xlsx", ".xls", ".xlsm", ".csv", ".json", ".geojson", ".ods")
MAX_BYTES = 80_000_000
ziel = pathlib.Path(sys.argv[1])
status: dict = {}


def hole(url: str, limit: int = MAX_BYTES) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        daten = r.read(limit + 1)
    if len(daten) > limit:
        raise ValueError(f"größer als {limit} Bytes")
    return daten


def sicher(name: str) -> str:
    return re.sub(r"[^\w.\-äöüÄÖÜß]+", "_", name)[:120]


def passt(titel: str) -> bool:
    t = titel.lower()
    return any(w in t for w in ("zähl", "zaehl", "verkehrsmeng", "verkehrserheb", "knotenstrom"))


def ckan_suche() -> list[dict]:
    pakete: dict[str, dict] = {}
    for portal, api in CKAN.items():
        for q in SUCHE:
            url = api + "?" + urllib.parse.urlencode({"q": q, "rows": 500})
            try:
                res = json.loads(hole(url, 30_000_000))["result"]["results"]
                status[f"{portal}:{q}"] = len(res)
            except Exception as e:  # noqa: BLE001
                status[f"{portal}:{q}"] = f"Fehler: {e}"
                continue
            for p in res:
                if not passt(p.get("title", "") + " " + p.get("name", "")):
                    continue
                pakete[f"{portal}/{p['name']}"] = {
                    "portal": portal,
                    "name": p["name"],
                    "titel": p.get("title"),
                    "organisation": (p.get("organization") or {}).get("title"),
                    "lizenz": p.get("license_id"),
                    "geaendert": p.get("metadata_modified"),
                    "notizen": (p.get("notes") or "")[:600],
                    "ressourcen": [
                        {"name": r.get("name"), "format": r.get("format"), "url": r.get("url"),
                         "groesse": r.get("size")}
                        for r in p.get("resources", [])
                    ],
                }
    return list(pakete.values())


def ods_suche() -> list[dict]:
    out = []
    for portal, basis in ODS.items():
        url = basis + "/api/explore/v2.1/catalog/datasets?" + urllib.parse.urlencode(
            {"where": 'search("verkehr")', "limit": 100})
        try:
            res = json.loads(hole(url, 20_000_000))["results"]
            status[f"{portal}:ods"] = len(res)
        except Exception as e:  # noqa: BLE001
            status[f"{portal}:ods"] = f"Fehler: {e}"
            continue
        for d in res:
            titel = (d.get("metas") or {}).get("default", {}).get("title") or d["dataset_id"]
            if not passt(titel + " " + d["dataset_id"]):
                continue
            did = d["dataset_id"]
            ressourcen = [
                {"name": "export.csv", "format": "CSV",
                 "url": f"{basis}/api/explore/v2.1/catalog/datasets/{did}/exports/csv?delimiter=%3B"},
                {"name": "export.geojson", "format": "GEOJSON",
                 "url": f"{basis}/api/explore/v2.1/catalog/datasets/{did}/exports/geojson"},
            ]
            try:
                anh = json.loads(hole(f"{basis}/api/explore/v2.1/catalog/datasets/{did}/attachments"))
                for a in anh.get("attachments", []):
                    ressourcen.append({"name": a.get("title") or a.get("id"), "format": "ANHANG",
                                       "url": a.get("href") or a.get("url")})
            except Exception as e:  # noqa: BLE001
                status[f"{portal}:{did}:anhang"] = f"Fehler: {e}"
            out.append({"portal": portal, "name": did, "titel": titel,
                        "lizenz": (d.get("metas") or {}).get("default", {}).get("license"),
                        "ressourcen": ressourcen})
    return out


def lade(pakete: list[dict]) -> None:
    gesamt = 0
    for p in pakete:
        ordner = ziel / p["portal"] / sicher(p["name"])
        for r in p["ressourcen"]:
            url = r.get("url") or ""
            if not url.startswith("http") or gesamt > 600_000_000:
                continue
            datei = sicher(urllib.parse.unquote(url.split("?")[0].rsplit("/", 1)[-1]) or r["name"] or "datei")
            fmt = (r.get("format") or "").lower()
            if not (datei.lower().endswith(TABELLE + (".zip",)) or fmt in ("csv", "xlsx", "xls", "zip", "json", "geojson", "anhang")):
                continue
            try:
                daten = hole(url)
            except Exception as e:  # noqa: BLE001
                r["fehler"] = str(e)
                continue
            gesamt += len(daten)
            r["bytes"] = len(daten)
            ordner.mkdir(parents=True, exist_ok=True)
            if daten[:2] == b"PK" and not datei.lower().endswith((".xlsx", ".xlsm", ".ods")):
                inhalt, pdfs = [], 0
                try:
                    with zipfile.ZipFile(io.BytesIO(daten)) as zf:
                        for info in zf.infolist():
                            if info.is_dir():
                                continue
                            inhalt.append([info.filename, info.file_size])
                            n = info.filename.lower()
                            if n.endswith(TABELLE) or (n.endswith(".pdf") and pdfs < 2):
                                pdfs += n.endswith(".pdf")
                                pfad = ordner / "zip" / sicher(datei) / sicher(info.filename.replace("/", "__"))
                                pfad.parent.mkdir(parents=True, exist_ok=True)
                                pfad.write_bytes(zf.read(info))
                except Exception as e:  # noqa: BLE001
                    r["fehler"] = f"ZIP: {e}"
                r["inhalt"] = inhalt[:2000]
            else:
                if not datei.lower().endswith(TABELLE + (".pdf",)):
                    datei += ".bin"
                if not datei.lower().endswith(".pdf") or daten[:4] == b"%PDF":
                    (ordner / datei).write_bytes(daten)


def main() -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    pakete = ckan_suche() + ods_suche()
    lade(pakete)
    (ziel / "index.json").write_text(json.dumps(pakete, ensure_ascii=False, indent=1))
    (ziel / "status.json").write_text(json.dumps(status, ensure_ascii=False, indent=1))
    print(len(pakete), "Pakete")


if __name__ == "__main__":
    main()
