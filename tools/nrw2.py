"""Werkzeug: Verkehrszählungen in Nordrhein-Westfalen (Teil 2: gezielt lesen).

- CKAN-Portale der Kommunen und Regionen (offenesdatenportal.de, opendata.ruhr, Köln, …) nach
  Zähl-Begriffen, samt Ressourcen und Lizenz,
- Mobilithek-Angebote aus NRW (Metadaten je Angebot),
- Seiten aus einer Liste („Kommune | URL“) als Text samt Links; PDFs mit pdftotext; verlinkte
  Zähl-Dokumente (PDF, XLSX, CSV) eine Ebene tief.

Jeder Abruf (auch APIs) nur, wenn robots.txt ihn erlaubt – auch für die Kennungen von Claude.
Nur Standardbibliothek (+ pdftotext).
Aufruf: python3 tools/nrw2.py ergebnis/nrw2 tools/nrw2_seiten.txt [ckan,mobilithek,seiten,mdk]
"""

import gzip
import json
import pathlib
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import hessen2 as h  # noqa: E402  (Leser, robots.txt-Prüfung)

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/nrw2")
ZIEL.mkdir(parents=True, exist_ok=True)
(ZIEL / "dateien").mkdir(exist_ok=True)
h.ZIEL = ZIEL
LISTE = sys.argv[2] if len(sys.argv) > 2 else str(pathlib.Path(__file__).parent / "nrw2_seiten.txt")
TEILE = (sys.argv[3] if len(sys.argv) > 3 else "ckan,mobilithek,seiten").split(",")
protokoll: dict = {}

CKAN = {
    "offenesdatenportal": "https://www.offenesdatenportal.de/api/3/action/",
    "opendata_ruhr": "https://opendata.ruhr/api/3/action/",
    "koeln": "https://www.offenedaten-koeln.de/api/3/action/",
    "muenster": "https://opendata.stadt-muenster.de/api/3/action/",
    "aachen": "https://offenedaten.aachen.de/api/3/action/",
    "wuppertal": "https://www.offenedaten-wuppertal.de/api/3/action/",
    "open_nrw": "https://ckan.open.nrw.de/api/3/action/",
}
BEGRIFFE = ("Verkehrszählung", "Verkehrszaehlung", "Zählung", "Zählstelle", "Verkehrsmessung",
            "Verkehrsmengen", "Geschwindigkeit", "Verkehrsüberwachung", "Radverkehr", "Fußgänger",
            "Passanten", "Detektor", "Verkehrsdaten", "Seitenradar")


def ckan():
    aus, fehler = {}, {}
    for name, api in CKAN.items():
        for q in BEGRIFFE:
            url = api + "package_search?" + urllib.parse.urlencode({"q": q, "rows": 500})
            try:
                inhalt = h.seite(url, zeit=60)[0]
                r = json.loads(inhalt)["result"]
            except h.Gesperrt:
                fehler.setdefault(name, {})[q] = "robots.txt"
                break
            except Exception as e:  # noqa: BLE001
                fehler.setdefault(name, {})[q] = repr(e)[:200]
                if len(fehler[name]) >= 2:
                    break
                continue
            for p in r["results"]:
                eintrag = aus.setdefault(name, {}).setdefault(p["name"], {
                    "titel": p.get("title"), "org": (p.get("organization") or {}).get("title"),
                    "lizenz": p.get("license_id"), "lizenz_titel": p.get("license_title"),
                    "erstellt": p.get("metadata_created"), "geaendert": p.get("metadata_modified"),
                    "notiz": re.sub(r"\s+", " ", p.get("notes") or "")[:1500],
                    "ressourcen": [{"name": x.get("name"), "format": x.get("format"), "url": x.get("url"),
                                    "lizenz": x.get("license"), "geaendert": x.get("last_modified")}
                                   for x in p.get("resources", [])][:40],
                    "begriffe": []})
                eintrag["begriffe"].append(q)
            time.sleep(0.5)
    h.schreibe("ckan.json", aus)
    h.schreibe("ckan_fehler.json", fehler)
    protokoll["ckan"] = {k: len(v) for k, v in aus.items()} | {"fehler": {k: list(v.values())[:1] for k, v in fehler.items()}}


MOBILITHEK = {
    "-5042567686068911126": "Münster Ampelkreuzungen (Monatswerte)",
    "-5525199905227696263": "Düsseldorf Verkehrszähldaten 2024",
    "-1611162702897177411": "Neuss Radverkehrszählstelle RS5",
    "681123204783038464": "Gelsenkirchen Verkehrsdaten",
    "-1425387091592081516": "Bielefeld Radverkehrszählstellen",
    "767690308516229120": "FH Aachen Datenpool",
    "110000000002899003": "Köln Detektordaten dynamisch",
    "110000000002899002": "Köln Detektordaten statisch",
    "110000000002055001": "Düsseldorf Detektordaten",
}


def mobilithek():
    aus = {}
    for oid, titel in MOBILITHEK.items():
        try:
            aus[oid] = {"titel": titel, "daten": json.loads(h.seite(
                f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{oid}", zeit=60)[0])}
        except h.Gesperrt:
            aus[oid] = {"titel": titel, "fehler": "robots.txt"}
        except Exception as e:  # noqa: BLE001
            aus[oid] = {"titel": titel, "fehler": repr(e)[:200]}
        time.sleep(0.5)
    h.schreibe("mobilithek.json", aus)
    protokoll["mobilithek"] = {k: ("fehler" if "fehler" in v else "ok") for k, v in aus.items()}


MDK_PROJEKT = "fitko/govdata/tools/musterdatenkatalog-pipeline"


def mdk():
    """Musterdatenkatalog (GovData/FITKO): Rohdaten (CSV/XLSX) aus dem Repository auf openCode –
    ordnet die offenen Datensätze der Kommunen Themen zu (etwa Verkehrszählung)."""
    api = "https://gitlab.opencode.de/api/v4/projects/" + urllib.parse.quote(MDK_PROJEKT, safe="")
    aus = {}
    try:
        baum = json.loads(h.seite(api + "/repository/tree?" + urllib.parse.urlencode(
            {"path": "musterdatenkatalog", "ref": "main", "per_page": 100, "recursive": "true"}), zeit=60)[0])
    except h.Gesperrt:
        protokoll["mdk"] = "robots.txt"
        return
    aus["baum"] = baum
    (ZIEL / "mdk").mkdir(exist_ok=True)
    for b in baum:
        if b.get("type") != "blob" or not b["path"].lower().endswith((".csv", ".xlsx", ".json")):
            continue
        url = (f"https://gitlab.opencode.de/{MDK_PROJEKT}/-/raw/main/"
               + urllib.parse.quote(b["path"]))
        try:
            inhalt = h.seite(url, zeit=120, grenze=200_000_000)[0]
            # gepackt, damit der Branch klein bleibt
            (ZIEL / "mdk" / (pathlib.Path(b["path"]).name + ".gz")).write_bytes(gzip.compress(inhalt))
            aus.setdefault("dateien", {})[b["path"]] = len(inhalt)
        except h.Gesperrt:
            aus.setdefault("dateien", {})[b["path"]] = "robots.txt"
        except Exception as e:  # noqa: BLE001
            aus.setdefault("dateien", {})[b["path"]] = repr(e)[:200]
    h.schreibe("mdk.json", aus)
    protokoll["mdk"] = aus.get("dateien")


def seiten():
    sys.argv = [sys.argv[0], str(ZIEL), LISTE]
    h.protokoll = protokoll
    h.seiten()


if __name__ == "__main__":
    for name in TEILE:
        f = {"ckan": ckan, "mobilithek": mobilithek, "seiten": seiten, "mdk": mdk}[name]
        t0 = time.time()
        try:
            f()
        except Exception as e:  # noqa: BLE001
            protokoll[name + "_fehler"] = repr(e)[:300]
        protokoll[name + "_sekunden"] = round(time.time() - t0)
        h.schreibe("protokoll.json", protokoll)
        print(name, json.dumps(protokoll.get(name), ensure_ascii=False)[:400], flush=True)
