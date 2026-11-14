"""Erlaubte Wege zu den Quellen der Pipeline suchen (robots.txt nach RFC 9309, tools/robots.py).

Je Kandidat: erlaubt für die Kennung der Pipeline (Gruppe `*`) und für die Werkzeuge (samt
Claude)? Wenn ja und `holen` gesetzt ist: Abruf (höchstens 300 kB) und eine kurze Auswertung
(JSON-LD/RDF: Ressourcen mit Download-URL und Lizenz; HTML: Links auf Ressourcen und Downloads).
Aufruf: python3 tools/wege.py ergebnis/wege
"""

import json
import pathlib
import re
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/wege")
ZIEL.mkdir(parents=True, exist_ok=True)

# (Quelle, URL, holen?)
KANDIDATEN = [
    ("moers", "https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021.jsonld", True),
    ("moers", "https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021.rdf", True),
    ("moers", "https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021", True),
    ("moers", "https://www.offenesdatenportal.de/catalog.jsonld?q=Verkehrsz%C3%A4hlung", True),
    ("olpe", "https://opendata.olpe.de/dataset/verkehrsmessungen-k18.jsonld", True),
    ("olpe", "https://opendata.olpe.de/dataset/verkehrsmessungen-k18", True),
    ("olpe", "https://opendata.olpe.de/dataset/?q=Verkehrsmessung", True),
    ("olpe", "https://opendata.olpe.de/catalog.jsonld?q=Verkehrsmessung", True),
    ("aachen_rad", "https://offenedaten.aachen.de/dataset/radzaehlstellen-der-stadt-aachen.jsonld", True),
    ("aachen_rad", "https://offenedaten.aachen.de/dataset/radzaehlstellen-der-stadt-aachen", True),
    ("muenchen_rad", "https://opendata.muenchen.de/dataset/x.jsonld", False),
    ("muenchen_rad", "https://opendata.muenchen.de/dataset/?q=Raddauerz%C3%A4hlstellen", False),
    ("potsdam", "https://de.ftp.opendatasoft.com/potsdam/Verkehrszaehlungen/2300.zip", False),
    ("potsdam", "https://opendata.potsdam.de/explore/dataset/verkehrszahlungen/export/", False),
    ("bochum_rad", "https://gitlab.opencode.de/StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter.git/info/refs?service=git-upload-pack", False),
    ("bochum_rad", "https://gitlab.opencode.de/StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter/-/archive/main/radverkehr-zaehlstellen-eco-counter-main.tar.gz", False),
    ("bochum_rad", "https://gitlab.opencode.de/StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter/-/raw/main/README.md", False),
    ("bochum_rad", "https://gitlab.opencode.de/StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter", True),
    ("bochum_rad", "https://opendata.ruhr/dataset/bochum-radverkehr-wittener-strasse", True),
    ("hamburg (OSM)", "https://download.openstreetmap.fr/extracts/europe/germany/hamburg-latest.osm.pbf", False),
    ("hamburg (OSM)", "https://download.bbbike.org/osm/bbbike/Hamburg/Hamburg.osm.pbf", False),
    ("hamburg (OSM)", "https://overpass.kumi.systems/api/interpreter", False),
    ("hamburg (OSM)", "https://overpass.private.coffee/api/interpreter", False),
    ("rostock_rad", "https://www.opendata-hro.de/dataset/radmonitore", True),
    ("rostock_rad", "https://opendata-hro.de/dataset/radmonitore", True),
    ("wuerzburg/neuss/dortmund (ODS)", "https://opendata.wuerzburg.de/explore/dataset/fahrrad-zaehlung-daten/export/", False),
    ("wuerzburg/neuss/dortmund (ODS)", "https://opendata.wuerzburg.de/explore/dataset/fahrrad-zaehlung-daten/download/?format=csv", False),
]
PIPELINE = ("zaehlkarte-pipeline", "*")


def auswerten(inhalt: bytes, typ: str, url: str) -> dict:
    text = inhalt.decode("utf-8", "replace")
    aus = {"typ": typ, "bytes": len(inhalt), "anfang": text[:300]}
    if url.endswith(".jsonld") or "json" in typ:
        try:
            j = json.loads(text)
        except ValueError:
            return aus
        knoten = j.get("@graph", [j]) if isinstance(j, dict) else j
        verteilungen = [k for k in knoten if isinstance(k, dict) and "dcat:Distribution" in str(k.get("@type"))]
        aus["verteilungen"] = [{"titel": k.get("dct:title"), "download": k.get("dcat:downloadURL"),
                                "zugang": k.get("dcat:accessURL"), "lizenz": k.get("dct:license")}
                               for k in verteilungen][:8]
        aus["verteilungen_n"] = len(verteilungen)
        aus["datensaetze_n"] = sum(1 for k in knoten if isinstance(k, dict) and "dcat:Dataset" in str(k.get("@type")))
    else:
        links = re.findall(r'href="([^"]+)"', text)
        links = [urllib.parse.urljoin(url, x) for x in links]
        aus["downloads"] = sorted({x for x in links if "/download/" in x or re.search(r"\.(csv|txt|json|zip|xlsx?)(\?|$)", x)})[:15]
        aus["ressourcen"] = sorted({x for x in links if "/resource/" in x})[:10]
        aus["datensaetze"] = sorted({x for x in links if re.search(r"/dataset/[^/?#]+$", x)})[:40]
    return aus


def main():
    aus = []
    for quelle, url, holen in KANDIDATEN:
        r = R.regeln(url)
        e = {"quelle": quelle, "url": url,
             "pipeline": all(r.erlaubt(k, url) for k in PIPELINE),
             "werkzeug": R.erlaubt(url), "crawl_delay": r.verzoegerung(PIPELINE)}
        if holen and e["werkzeug"]:
            try:
                inhalt, end, typ = R.oeffne(url, zeit=60, grenze=300_000)
                e |= {"end": end} | auswerten(inhalt, typ, end)
            except Exception as ex:  # noqa: BLE001
                e["fehler"] = repr(ex)[:200]
        aus.append(e)
        print(quelle, url[:90], "pipeline", e["pipeline"], "werkzeug", e["werkzeug"], e.get("fehler", ""), flush=True)
    (ZIEL / "wege.json").write_text(json.dumps(aus, ensure_ascii=False, indent=1))
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
