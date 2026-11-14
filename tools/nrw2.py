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
    basis = "https://gitlab.opencode.de/api/v4/projects/"
    aus = {}
    try:
        proj = json.loads(h.seite(basis + urllib.parse.quote(MDK_PROJEKT, safe=""), zeit=60)[0])
    except h.Gesperrt:
        protokoll["mdk"] = "robots.txt"
        return
    except Exception as e:  # noqa: BLE001
        protokoll["mdk"] = f"Projekt: {e!r}"[:200]
        return
    aus["projekt"] = {k: proj.get(k) for k in ("id", "default_branch", "visibility", "last_activity_at",
                                                "web_url")}
    zweig = proj.get("default_branch") or "main"
    baum = []
    for seite_nr in range(1, 30):
        try:
            teil = json.loads(h.seite(f"{basis}{proj['id']}/repository/tree?" + urllib.parse.urlencode(
                {"ref": zweig, "per_page": 100, "page": seite_nr, "recursive": "true"}), zeit=60)[0])
        except Exception as e:  # noqa: BLE001
            aus["baum_fehler"] = repr(e)[:200]
            break
        baum += teil
        if len(teil) < 100:
            break
    aus["baum"] = [b["path"] for b in baum]
    (ZIEL / "mdk").mkdir(exist_ok=True)
    for b in baum:
        if b.get("type") != "blob" or not b["path"].lower().endswith((".csv", ".xlsx", ".json")):
            continue
        if not b["path"].startswith("musterdatenkatalog"):
            continue
        url = f"{basis}{proj['id']}/repository/files/{urllib.parse.quote(b['path'], safe='')}/raw?ref={zweig}"
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
    protokoll["mdk"] = aus.get("dateien") or aus.get("baum_fehler") or len(aus.get("baum", []))

# Portale, die die Pipeline abruft (sources.yaml), und was robots.txt je Kennung erlaubt
ROBOTS_PRUEFEN = [
    "https://www.offenesdatenportal.de/api/3/action/package_show?id=verkehrszahlung-in-moers-2021",
    "https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021",
    "https://opendata.olpe.de/api/3/action/package_search?q=Verkehrsmessung&rows=200",
    "https://offenedaten.aachen.de/api/3/action/package_show?id=radzaehlstellen-der-stadt-aachen",
    "https://offenedaten.aachen.de/dataset/radzaehlstellen-der-stadt-aachen",
    "https://opendata.muenchen.de/api/3/action/package_show?id=x",
    "https://open.nrw/api/3/action/package_show?id=radverkehrszahlungen-e",
    "https://open.nrw/api/3/action/package_search?q=x",
    "https://opendata.rhein-kreis-neuss.de/api/explore/v2.1/catalog/datasets/eco-counter-data/exports/csv",
    "https://opendata.rhein-kreis-neuss.de/api/v2/catalog/datasets/stadt-neuss-radzaehlstelle-radschnellweg-hammer-landstrasse/exports/csv?use_labels=true",
    "https://open-data.dortmund.de/api/explore/v2.1/catalog/datasets/fb61-dauerzaehlstelle-radverkehr-schnettkerbruecke/exports/csv",
    "https://opendata.bonn.de/data.json",
    "https://opendata.stadt-muenster.de/sites/default/files/Verkehrsz%C3%A4hlung.zip",
    "https://opendata.ruhr/api/3/action/package_show?id=mobilitatskonzept",
    "https://opendata.ruhr/dataset/mobilitatskonzept",
    "https://opendata.duesseldorf.de/api/3/action/package_show?id=x",
    "https://opendata.mobidata-bw.de/x",
]
KENNUNGEN = ("zaehlkarte-pipeline", "zaehlkarte-werkzeug", "ClaudeBot", "Claude-User", "Claude-SearchBot",
             "anthropic-ai", "*")


def robots():
    import urllib.robotparser
    aus = {}
    for url in ROBOTS_PRUEFEN:
        t_ = urllib.parse.urlsplit(url)
        basis = f"{t_.scheme}://{t_.netloc}"
        if basis not in aus:
            try:
                inhalt = h.roh(basis + "/robots.txt", zeit=30)[0].decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                inhalt = f"(Fehler: {e!r})"
            aus[basis] = {"robots": inhalt[:8000], "urls": {}}
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(aus[basis]["robots"].splitlines() if not aus[basis]["robots"].startswith("(Fehler") else [])
        aus[basis]["urls"][url] = {k: rp.can_fetch(k, url) for k in KENNUNGEN}
    h.schreibe("robots.json", aus)
    protokoll["robots"] = {b: {u.split(b)[-1][:50]: [k for k, ok in v.items() if not ok]
                               for u, v in x["urls"].items()} for b, x in aus.items()}


def nachpruefen():
    """Frühere Abrufe gegen robots.txt nach RFC 9309 prüfen (urllib.robotparser in Python 3.12
    kannte * und $ nicht): welche abgerufenen Seiten wären gesperrt gewesen?"""
    import glob

    import robots as R
    urls = set()
    for f in glob.glob("ergebnis/*/webseiten.json"):
        for e in json.load(open(f)):
            if e.get("web"):
                urls.add(e["web"] if isinstance(e["web"], str) else e["web"][0])
            if (e.get("suche") or {}).get("url"):
                urls.add(e["suche"]["url"])
    for f in glob.glob("ergebnis/*/seiten.json"):
        for e in json.load(open(f)):
            if "fehler" not in e:
                urls.add(e["url"])
            for u in e.get("unter") or []:
                if "fehler" not in u:
                    urls.add(u["url"])
    gesperrt = []
    for u in sorted(urls):
        try:
            if not R.erlaubt(u):
                gesperrt.append(u)
        except Exception as e:  # noqa: BLE001
            gesperrt.append(f"{u} (Prüfung: {e!r})"[:300])
    h.schreibe("nachpruefen.json", {"geprueft": len(urls), "gesperrt": gesperrt})
    protokoll["nachpruefen"] = {"geprueft": len(urls), "gesperrt": len(gesperrt)}


def seiten():
    """Wie hessen2.seiten; „Kommune | URL | pdf“ holt zusätzlich bis zu vier verlinkte PDFs."""
    import concurrent.futures as cf
    ziele = []
    for z in pathlib.Path(LISTE).read_text().splitlines():
        if " | " in z and not z.startswith("#"):
            teile = [x.strip() for x in z.split(" | ")]
            ziele.append((teile[0], teile[1], len(teile) > 2 and teile[2] == "pdf"))

    def lies(k, u, pdf):
        e = h.lies(k, u)
        if pdf and "fehler" not in e:
            schon = {x["url"] for x in e.get("unter") or []}
            pdfs = [lk[0] for lk in e.get("links") or [] if re.search(r"\.pdf(\?|$)", lk[0], re.I)
                    and lk[0] not in schon][:4]
            e["unter"] = (e.get("unter") or []) + [h.lies(k, x, 1) for x in pdfs]
        return e

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        aus = list(pool.map(lambda z: lies(*z), ziele))
    h.schreibe("seiten.json", aus)
    protokoll["seiten"] = {"ziele": len(ziele), "gelesen": sum(1 for e in aus if "fehler" not in e),
                           "robots": sum(1 for e in aus if e.get("fehler") == "robots.txt")}


if __name__ == "__main__":
    for name in TEILE:
        f = {"ckan": ckan, "mobilithek": mobilithek, "seiten": seiten, "mdk": mdk, "robots": robots, "nachpruefen": nachpruefen}[name]
        t0 = time.time()
        try:
            f()
        except Exception as e:  # noqa: BLE001
            protokoll[name + "_fehler"] = repr(e)[:300]
        protokoll[name + "_sekunden"] = round(time.time() - t0)
        h.schreibe("protokoll.json", protokoll)
        print(name, json.dumps(protokoll.get(name), ensure_ascii=False)[:400], flush=True)
