"""Werkzeug: Verkehrszählungen in einem Land suchen, Kommune für Kommune (Teil 1: Durchsicht).
Verallgemeinert aus tools/hessen.py; jeder Abruf (auch APIs) nur, wenn robots.txt ihn erlaubt.

Holt
- die Gemeinden und Kreise Hessens aus Wikidata (AGS, Einwohner, Webseite, Lage),
- FragDenStaat: Behörden und Gesetze (auch Informationsfreiheitssatzungen) im Land Hessen und
  alle Anfragen dort, die Zählungen betreffen,
- GovData (CKAN), das Geoportal Hessen und die Mobilithek nach Zähl-Begriffen,
- Zählstellen aus OpenStreetMap (man_made=monitoring_station),
- je Gemeinde-Webseite die Sitemap und die Suche der Seite nach Zähl-Begriffen.

Webseiten der Gemeinden nur mit ehrlicher Kennung und nur, was ihre robots.txt erlaubt (auch für
die Kennungen von Claude – was dem Abruf-Werkzeug verboten ist, holt dieses Werkzeug auch nicht).

Nur Standardbibliothek. Aufruf: python3 tools/land.py ergebnis/nrw [portale|webseiten|alle] NW
"""

import concurrent.futures as cf
import gzip
import json
import pathlib
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

LAENDER = {
    "NW": {"ags": "05", "iso": "DE-NW", "name": "Nordrhein-Westfalen",
           "staedte": ["Köln", "Düsseldorf", "Dortmund", "Essen", "Duisburg", "Bochum", "Wuppertal",
                       "Bielefeld", "Bonn", "Münster", "Mönchengladbach", "Gelsenkirchen", "Aachen",
                       "Krefeld", "Oberhausen", "Hagen", "Hamm", "Mülheim", "Leverkusen", "Solingen",
                       "Herne", "Neuss", "Paderborn", "Bottrop", "Recklinghausen", "Bergisch Gladbach",
                       "Moers", "Siegen", "Gütersloh", "Remscheid", "Witten", "Iserlohn", "Düren"],
           "extra": [("RVR", "Regionalverband Ruhr", "https://www.rvr.ruhr/"),
                     ("ZNM", "Zukunftsnetz Mobilität NRW", "https://www.zukunftsnetz-mobilitaet.nrw.de/"),
                     ("AGFS", "AGFS NRW (fahrrad- und fußgängerfreundliche Städte)", "https://www.agfs-nrw.de/")]},
}
LAND = LAENDER[sys.argv[3] if len(sys.argv) > 3 else "NW"]
ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/nrw")
ZIEL.mkdir(parents=True, exist_ok=True)
TEILE = (sys.argv[2] if len(sys.argv) > 2 else "alle").split(",")
UA = "zaehlkarte-werkzeug/0.2 (+https://github.com/vizsim-lab/zaehlkarte)"
ROBOT_KENNUNGEN = ("zaehlkarte-werkzeug", "ClaudeBot", "Claude-User", "Claude-SearchBot", "anthropic-ai", "*")
protokoll: dict = {}
START = time.time()
_ROBOTS: dict = {}
_ROBOTS_SPERRE = threading.Lock()

# Begriffe für Zählungen in URLs, Titeln und Linktexten
MUSTER = re.compile(
    r"verkehrsz(?:ae|ä|a)hl|z(?:ae|ä|a)hlstell|z(?:ae|ä|a)hldat|verkehrsmeng|verkehrsdaten"
    r"|radz(?:ae|ä|a)hl|radverkehrsz(?:ae|ä|a)hl|fahrradz(?:ae|ä|a)hl|verkehrserheb|verkehrsbelast"
    r"|verkehrsst(?:ae|ä|a)rke|geschwindigkeitsmess|geschwindigkeitsanzeig|verkehrsstatistik"
    r"|dialog-?displ|messtafel|verkehrsmessung|knotenpunktz|querschnittsz|verkehrsuntersuchung"
    r"|verkehrsgutachten|verkehrsentwicklungsplan|mobilit(?:ae|ä|a)tskonzept|verkehrskonzept"
    r"|passantenz|fu(?:ss|ß)g(?:ae|ä|a)ngerz|z(?:ae|ä|a)hlung|verkehrsfluss|dauerz(?:ae|ä|a)hl",
    re.I,
)
STARK = re.compile(  # enger: was wirklich nach Zählwerten klingt
    r"verkehrsz(?:ae|ä|a)hl|z(?:ae|ä|a)hlstell|z(?:ae|ä|a)hldat|verkehrsmeng|radz(?:ae|ä|a)hl"
    r"|radverkehrsz(?:ae|ä|a)hl|fahrradz(?:ae|ä|a)hl|verkehrserheb|knotenpunktz|querschnittsz"
    r"|verkehrsst(?:ae|ä|a)rke|verkehrsbelast|dauerz(?:ae|ä|a)hl|passantenz|fu(?:ss|ß)g(?:ae|ä|a)ngerz",
    re.I,
)


class Gesperrt(Exception):
    """robots.txt verbietet den Abruf."""


def hole(url, *, daten=None, kopf=None, roh=False, zeit=60, ua=UA):
    if not erlaubt(url):
        raise Gesperrt(url)
    return _roh(url, daten=daten, kopf=kopf, roh=roh, zeit=zeit, ua=ua)


def _roh(url, *, daten=None, kopf=None, roh=False, zeit=60, ua=UA):
    k = {"User-Agent": ua, "Accept-Language": "de"}
    k.update(kopf or {})
    if daten is not None and not isinstance(daten, bytes):
        daten = json.dumps(daten).encode()
        k.setdefault("Content-Type", "application/json")
    with urllib.request.urlopen(urllib.request.Request(url, data=daten, headers=k), timeout=zeit) as a:
        inhalt = a.read()
        if a.headers.get("Content-Encoding") == "gzip" or inhalt[:2] == b"\x1f\x8b":
            try:
                inhalt = gzip.decompress(inhalt)
            except OSError:
                pass
        return (inhalt, a.geturl(), a.headers.get("Content-Type", "")) if roh else json.loads(inhalt)


def schreibe(name, obj):
    (ZIEL / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))


def erlaubt(url):
    """robots.txt des Hosts für alle ROBOT_KENNUNGEN; ohne robots.txt (404) ist alles erlaubt."""
    t = urllib.parse.urlsplit(url)
    basis = f"{t.scheme}://{t.netloc}"
    with _ROBOTS_SPERRE:
        rp = _ROBOTS.get(basis)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            inhalt, _, _ = _roh(basis + "/robots.txt", roh=True, zeit=15)
            rp.parse(inhalt.decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.allow_all = True
        except Exception:  # noqa: BLE001
            rp.allow_all = True
        with _ROBOTS_SPERRE:
            _ROBOTS[basis] = rp
    return all(rp.can_fetch(k, url) for k in ROBOT_KENNUNGEN)


def schritt(name):
    def deko(f):
        def innen(*a, **kw):
            t0 = time.time()
            try:
                f(*a, **kw)
                protokoll[name] = protokoll.get(name, {}) | {"ok": True}
            except Exception as e:  # noqa: BLE001
                protokoll[name] = protokoll.get(name, {}) | {"fehler": repr(e)[:400]}
            protokoll[name]["sekunden"] = round(time.time() - t0)
            schreibe(f"protokoll_{'_'.join(TEILE)}.json", protokoll)
            print(name, json.dumps(protokoll[name], ensure_ascii=False)[:300], flush=True)
        return innen
    return deko


# ---------------------------------------------------------------- 1. Gemeinden und Kreise
SPARQL_GEMEINDEN = """
SELECT ?item ?name ?ags ?einw ?datum ?web ?coord ?kreis ?kreisName WHERE {
  ?item wdt:P439 ?ags . FILTER(STRSTARTS(?ags, "%(ags)s") && STRLEN(?ags) = 8)
  FILTER NOT EXISTS { ?item wdt:P576 [] }
  ?item rdfs:label ?name . FILTER(LANG(?name) = "de")
  OPTIONAL { ?item p:P1082 ?st . ?st ps:P1082 ?einw . OPTIONAL { ?st pq:P585 ?datum } }
  OPTIONAL { ?item wdt:P856 ?web }
  OPTIONAL { ?item wdt:P625 ?coord }
  OPTIONAL { ?item wdt:P131 ?kreis . ?kreis wdt:P440 [] .
             ?kreis rdfs:label ?kreisName . FILTER(LANG(?kreisName) = "de") }
}"""
SPARQL_KREISE = """
SELECT ?item ?name ?ks ?einw ?datum ?web WHERE {
  ?item wdt:P440 ?ks . FILTER(STRSTARTS(?ks, "%(ags)s") && STRLEN(?ks) = 5)
  FILTER NOT EXISTS { ?item wdt:P576 [] }
  ?item rdfs:label ?name . FILTER(LANG(?name) = "de")
  OPTIONAL { ?item p:P1082 ?st . ?st ps:P1082 ?einw . OPTIONAL { ?st pq:P585 ?datum } }
  OPTIONAL { ?item wdt:P856 ?web }
}"""
GEMEINDEN: dict = {}
KREISE: dict = {}


def sparql(abfrage):
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": abfrage, "format": "json"})
    return hole(url, kopf={"Accept": "application/sparql-results+json"}, zeit=180)["results"]["bindings"]


def wert(z, k):
    return z[k]["value"] if k in z else None


OVERPASS_GRENZEN = """[out:json][timeout:600];
area["ISO3166-2"="%s"][admin_level=4]->.land;
rel(area.land)["boundary"="administrative"]["admin_level"~"^(6|8)$"]["de:amtlicher_gemeindeschluessel"];
out center tags;"""


def grenzen_osm():
    """Gemeinden und Kreise aus OSM (admin_level 8 bzw. 6), wenn Wikidata gesperrt ist."""
    for server in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            inhalt, _, _ = hole(server, daten=urllib.parse.urlencode({"data": OVERPASS_GRENZEN % LAND["iso"]}).encode(),
                                kopf={"Content-Type": "application/x-www-form-urlencoded"}, roh=True, zeit=660)
            break
        except Exception as e:  # noqa: BLE001
            protokoll.setdefault("grenzen_osm", {})[server] = repr(e)[:200]
    else:
        return
    for e in json.loads(inhalt).get("elements", []):
        t, c = e.get("tags", {}), e.get("center") or {}
        ags = t.get("de:amtlicher_gemeindeschluessel", "")
        web = {t[k] for k in ("website", "contact:website", "url") if t.get(k)}
        einw = int(t["population"]) if str(t.get("population", "")).isdigit() else None
        if t.get("admin_level") == "8" or (t.get("admin_level") == "6" and ags.endswith("000")):
            GEMEINDEN[ags] = {"ags": ags, "name": t.get("name"), "osm": f"relation/{e['id']}", "einw": einw,
                              "einw_datum": t.get("source:population", ""), "web": web, "kreis": None,
                              "lon": c.get("lon"), "lat": c.get("lat")}
        if t.get("admin_level") == "6":
            ks = ags[:5]
            KREISE[ks] = {"ks": ks, "name": t.get("name"), "osm": f"relation/{e['id']}", "einw": einw,
                          "einw_datum": "", "web": web}


@schritt("wikidata")
def wikidata():
    try:
        zeilen = sparql(SPARQL_GEMEINDEN % LAND)
    except Exception as e:  # noqa: BLE001
        protokoll["wikidata_fehler"] = repr(e)[:200]
        zeilen = []
    if not zeilen:
        grenzen_osm()
        for x in list(GEMEINDEN.values()) + list(KREISE.values()):
            x["web"] = sorted(x["web"])
        schreibe("gemeinden.json", sorted(GEMEINDEN.values(), key=lambda g: g["ags"]))
        schreibe("kreise.json", sorted(KREISE.values(), key=lambda k: k["ks"]))
        protokoll["wikidata"] = {"quelle": "osm", "gemeinden": len(GEMEINDEN), "kreise": len(KREISE)}
        return
    for z in zeilen:
        ags = wert(z, "ags")
        g = GEMEINDEN.setdefault(ags, {"ags": ags, "name": wert(z, "name"), "wikidata": wert(z, "item"),
                                       "einw": None, "einw_datum": "", "web": set(), "kreis": None})
        if wert(z, "einw"):
            d = wert(z, "datum") or ""
            if d >= g["einw_datum"]:
                g["einw"], g["einw_datum"] = int(float(wert(z, "einw"))), d
        if wert(z, "web"):
            g["web"].add(wert(z, "web"))
        if wert(z, "coord") and "lon" not in g:
            m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", wert(z, "coord"))
            if m:
                g["lon"], g["lat"] = float(m[1]), float(m[2])
        if wert(z, "kreisName"):
            g["kreis"] = wert(z, "kreisName")
    for z in sparql(SPARQL_KREISE % LAND):
        ks = wert(z, "ks")
        k = KREISE.setdefault(ks, {"ks": ks, "name": wert(z, "name"), "wikidata": wert(z, "item"),
                                   "einw": None, "einw_datum": "", "web": set()})
        if wert(z, "einw"):
            d = wert(z, "datum") or ""
            if d >= k["einw_datum"]:
                k["einw"], k["einw_datum"] = int(float(wert(z, "einw"))), d
        if wert(z, "web"):
            k["web"].add(wert(z, "web"))
    for x in list(GEMEINDEN.values()) + list(KREISE.values()):
        x["web"] = sorted(x["web"])
    schreibe("gemeinden.json", sorted(GEMEINDEN.values(), key=lambda g: g["ags"]))
    schreibe("kreise.json", sorted(KREISE.values(), key=lambda k: k["ks"]))
    protokoll["wikidata"] = {"gemeinden": len(GEMEINDEN), "kreise": len(KREISE),
                             "ohne_web": sum(1 for g in GEMEINDEN.values() if not g["web"])}


# ---------------------------------------------------------------- 2. FragDenStaat
FDS = "https://fragdenstaat.de/api/v1/"
_JURIS: dict = {}


def juris():
    if "id" not in _JURIS:
        for j in hole(FDS + "jurisdiction/?limit=50")["objects"]:
            if j.get("name") == LAND["name"]:
                _JURIS["id"] = j["id"]
    return _JURIS["id"]


def fds_alle(pfad, params, grenze=400):
    url = FDS + pfad + "?" + urllib.parse.urlencode(params | {"limit": 50})
    alle, n = [], 0
    while url and n < grenze:
        for versuch in range(4):
            try:
                r = hole(url, zeit=90)
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and versuch < 3:
                    time.sleep(20 * (versuch + 1))
                    continue
                raise
        alle += r.get("objects", [])
        url = (r.get("meta") or {}).get("next")
        n += 1
        time.sleep(0.4)
    return alle, (r.get("meta") or {}).get("total_count")


@schritt("fds_gesetze")
def fds_gesetze():
    gesetze, gesamt = fds_alle("law/", {"jurisdiction": juris()})
    schreibe("fds_gesetze.json", [{k: g.get(k) for k in ("id", "name", "short", "law_type", "site_url",
                                                         "url", "description", "created")} for g in gesetze])
    protokoll["fds_gesetze"] = {"anzahl": len(gesetze), "gesamt": gesamt}


@schritt("fds_behoerden")
def fds_behoerden():
    behoerden, gesamt = fds_alle("publicbody/", {"jurisdiction": juris()}, grenze=200)
    aus = []
    for b in behoerden:
        aus.append({
            "id": b.get("id"), "name": b.get("name"), "other_names": b.get("other_names"),
            "klasse": (b.get("classification") or {}).get("name"), "email": b.get("email"),
            "url": b.get("url"), "site_url": b.get("site_url"), "anfragen": b.get("number_of_requests"),
            "gesetze": b.get("laws"), "regionen": b.get("regions"), "parent": b.get("parent"),
        })
    schreibe("fds_behoerden.json", aus)
    protokoll["fds_behoerden"] = {"anzahl": len(aus), "gesamt": gesamt}


ANFRAGE_MUSTER = re.compile(
    r"z(?:ae|ä)hl|verkehrsmeng|verkehrsdaten|verkehrsbelast|verkehrsst(?:ae|ä)rk|verkehrsaufkommen"
    r"|verkehrserheb|verkehrsgutacht|verkehrsuntersuch|geschwindigkeitsmess|geschwindigkeitsanzeig"
    r"|dtv\b|kfz pro|fahrzeuge pro|radverkehr|lkw-verkehr|schwerverkehr|durchgangsverkehr"
    r"|verkehrsentwicklungsplan|verkehrsmodell|messstelle|messung",
    re.I,
)


def anfrage_kurz(o):
    pb = o.get("public_body")
    return {
        "id": o.get("id"), "titel": o.get("title"), "status": o.get("status"),
        "ergebnis": o.get("resolution"), "url": "https://fragdenstaat.de" + (o.get("url") or ""),
        "erstellt": (o.get("created_at") or "")[:10], "letzte": (o.get("last_message") or "")[:10],
        "behoerde": pb.get("name") if isinstance(pb, dict) else pb,
        "behoerde_id": pb.get("id") if isinstance(pb, dict) else None,
        "land": ((pb.get("jurisdiction") or {}).get("name") if isinstance(pb, dict)
                 and isinstance(pb.get("jurisdiction"), dict) else None),
        "text": re.sub(r"\s+", " ", o.get("description") or "")[:500],
    }


@schritt("fds_anfragen")
def fds_anfragen():
    funde = {}
    # a) alle Anfragen im Land, gefiltert nach Begriffen (wenn der Filter greift)
    erste = hole(FDS + "request/?" + urllib.parse.urlencode({"jurisdiction": juris(), "limit": 1}))
    gesamt = (erste.get("meta") or {}).get("total_count")
    protokoll["fds_anfragen"] = {"im_land": gesamt}
    if gesamt and gesamt < 40000:
        alle, _ = fds_alle("request/", {"jurisdiction": juris()}, grenze=900)
        protokoll["fds_anfragen"]["gelesen"] = len(alle)
        for o in alle:
            if ANFRAGE_MUSTER.search((o.get("title") or "") + " " + (o.get("description") or "")):
                funde[o["id"]] = anfrage_kurz(o) | {"weg": "liste"}
    # b) Volltextsuche (findet auch Anfragen an Behörden anderer Zuständigkeit mit Hessen-Bezug)
    for q in ("Verkehrszählung", "Verkehrszählungen", "Verkehrsmengen", "Zählstelle", "Zähldaten",
              "Radverkehrszählung", "Verkehrsbelastung", "Knotenpunktzählung", "Verkehrserhebung",
              "Geschwindigkeitsmessung", "Verkehrsdaten", "Zählung Verkehr", "Dauerzählstelle"):
        try:
            treffer, n = fds_alle("request/search/", {"q": q, "jurisdiction": juris()}, grenze=6)
            protokoll["fds_anfragen"][f"suche:{q}"] = n
            for o in treffer:
                funde.setdefault(o["id"], anfrage_kurz(o) | {"weg": f"suche:{q}"})
        except Exception as e:  # noqa: BLE001
            protokoll["fds_anfragen"][f"suche:{q}"] = repr(e)[:200]
    schreibe("fds_anfragen.json", sorted(funde.values(), key=lambda a: a["erstellt"]))
    protokoll["fds_anfragen"]["funde"] = len(funde)


# ---------------------------------------------------------------- 3. Portale
BEGRIFFE = ["Verkehrszählung", "Verkehrszählungen", "Verkehrsmengen", "Zählstellen", "Zählstelle",
            "Zähldaten", "Verkehrsstärke", "Verkehrsbelastung", "Radverkehrszählung", "Radzählstelle",
            "Fahrradzählstelle", "Radverkehr Zählung", "Knotenpunktzählung", "Verkehrsdaten",
            "Verkehrserhebung", "Dauerzählstelle", "Geschwindigkeitsmessung", "Verkehrsmessung",
            "Fußverkehr Zählung", "Passantenfrequenz", "Kfz-Verkehr", "Verkehrsaufkommen"]


def ckan_kurz(p):
    extras = {e.get("key"): e.get("value") for e in p.get("extras", []) if isinstance(e, dict)}
    return {
        "name": p.get("name"), "titel": p.get("title"),
        "org": (p.get("organization") or {}).get("title"), "org_name": (p.get("organization") or {}).get("name"),
        "lizenz": p.get("license_id"), "geaendert": (p.get("metadata_modified") or "")[:10],
        "notiz": re.sub(r"\s+", " ", p.get("notes") or "")[:400],
        "extras": {k: v[:300] for k, v in extras.items() if isinstance(v, str) and k in (
            "contributorID", "politicalGeocodingURI", "politicalGeocodingLevelURI", "spatial",
            "publisher_name", "maintainer", "author", "spatial_text", "geocodingText", "dcat_publisher_name")},
        "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url")}
                       for r in p.get("resources", [])][:12],
    }


@schritt("govdata")
def govdata():
    api = "https://www.govdata.de/ckan/api/3/action/package_search"
    funde = {}
    for b in BEGRIFFE[:16] + [LAND["name"] + " Verkehr", LAND["name"] + " Zählung"]:
        try:
            r = hole(api + "?" + urllib.parse.urlencode({"q": b, "rows": 1000}), zeit=120)["result"]
            protokoll.setdefault("govdata", {})[b] = r["count"]
            for p in r["results"]:
                funde.setdefault(p["name"], ckan_kurz(p) | {"treffer": []})["treffer"].append(b)
        except Exception as e:  # noqa: BLE001
            protokoll.setdefault("govdata", {})[b] = repr(e)[:200]
        time.sleep(0.5)
    schreibe("govdata.json", funde)
    protokoll["govdata"]["pakete"] = len(funde)


@schritt("opennrw")
def opennrw():
    """Open.NRW (CKAN) direkt – lief 2026 aus Actions oft in Zeitüberschreitungen."""
    api = "https://ckan.open.nrw.de/api/3/action/package_search"
    funde, fehler = {}, 0
    for b in BEGRIFFE:
        try:
            r = hole(api + "?" + urllib.parse.urlencode({"q": b, "rows": 1000}), zeit=40)["result"]
            protokoll.setdefault("opennrw", {})[b] = r["count"]
            fehler = 0
            for p in r["results"]:
                funde.setdefault(p["name"], ckan_kurz(p) | {"treffer": []})["treffer"].append(b)
        except Exception as e:  # noqa: BLE001
            protokoll.setdefault("opennrw", {})[b] = repr(e)[:200]
            fehler += 1
            if fehler >= 3 or isinstance(e, Gesperrt):
                break
        time.sleep(0.5)
    schreibe("opennrw.json", funde)


@schritt("geoportal")
def geoportal():
    aus = {}
    for b in ["Verkehrszählung", "Verkehrsmengen", "Zählstelle", "Verkehrsstärke", "Radverkehr",
              "Verkehrsbelastung", "Verkehrsdaten", "DTV", "Zählung"]:
        for res in ("dataset", "wms", "wfs"):
            url = ("https://www.geoportal.hessen.de/mapbender/php/mod_callMetadata.php?"
                   + urllib.parse.urlencode({"searchText": b, "searchResources": res, "outputFormat": "json",
                                             "resultTarget": "web", "maxResults": 100, "searchPages": 1}))
            try:
                inhalt, _, typ = hole(url, roh=True, zeit=90)
                aus[f"{b}|{res}"] = json.loads(inhalt) if "json" in typ or inhalt[:1] in b"{[" else inhalt[:3000].decode("utf-8", "replace")
            except Exception as e:  # noqa: BLE001
                aus[f"{b}|{res}"] = repr(e)[:300]
            time.sleep(0.3)
    schreibe("geoportal.json", aus)


@schritt("mobilithek")
def mobilithek():
    aus = {}
    for b in (["Verkehrszählung", "Zählstelle", "Zähldaten", "Verkehrsmengen", "Verkehrsstärke", "Radverkehr",
               "Fahrrad Zählung", "Detektordaten", "Verkehrsdaten " + LAND["name"], LAND["name"]]
              + LAND["staedte"]):
        try:
            r = hole("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search",
                     daten={"searchString": b}, zeit=90)
            aus[b] = r
        except Exception as e:  # noqa: BLE001
            aus[b] = repr(e)[:300]
        time.sleep(0.5)
    schreibe("mobilithek.json", aus)


@schritt("osm")
def osm():
    abfrage = """[out:json][timeout:300];
area["ISO3166-2"="%s"][admin_level=4]->.he;
(
  nwr(area.he)["man_made"="monitoring_station"]["monitoring:bicycle"="yes"];
  nwr(area.he)["man_made"="monitoring_station"]["monitoring:traffic"="yes"];
  nwr(area.he)["man_made"="monitoring_station"]["monitoring:foot"="yes"];
  nwr(area.he)["man_made"="monitoring_station"]["monitoring:pedestrian"="yes"];
  nwr(area.he)["monitoring:bicycle"="yes"];
);
out center tags;""" % LAND["iso"]
    for server in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            inhalt, _, _ = hole(server, daten=urllib.parse.urlencode({"data": abfrage}).encode(),
                                kopf={"Content-Type": "application/x-www-form-urlencoded"}, roh=True, zeit=360)
            r = json.loads(inhalt)
            aus = []
            for e in r.get("elements", []):
                c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
                aus.append({"osm": f"{e['type']}/{e['id']}", "lat": c.get("lat"), "lon": c.get("lon"),
                            "tags": e.get("tags", {})})
            schreibe("osm_zaehlstellen.json", aus)
            protokoll["osm"] = {"anzahl": len(aus), "server": server}
            return
        except Exception as e:  # noqa: BLE001
            protokoll.setdefault("osm", {})[server] = repr(e)[:200]


# ---------------------------------------------------------------- 4. Webseiten der Gemeinden
class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links, self.formen, self._a, self._text, self.titel, self._t, self.generator = [], [], None, [], "", False, ""
        self._form = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "a" and a.get("href"):
            self._a, self._text = a["href"], []
        elif tag == "form":
            self._form = {"action": a.get("action") or "", "method": (a.get("method") or "get").lower(),
                          "felder": [], "versteckt": {}}
        elif tag == "input" and self._form is not None:
            typ = (a.get("type") or "text").lower()
            if typ in ("text", "search") and a.get("name"):
                self._form["felder"].append(a["name"])
            elif typ == "hidden" and a.get("name"):
                self._form["versteckt"][a["name"]] = a.get("value") or ""
        elif tag == "title":
            self._t = True
        elif tag == "meta" and (a.get("name") or "").lower() == "generator":
            self.generator = a.get("content") or ""

    def handle_endtag(self, tag):
        if tag == "a" and self._a is not None:
            self.links.append((self._a, " ".join("".join(self._text).split())[:200]))
            self._a = None
        elif tag == "form" and self._form is not None:
            self.formen.append(self._form)
            self._form = None
        elif tag == "title":
            self._t = False

    def handle_data(self, d):
        if self._a is not None:
            self._text.append(d)
        if self._t:
            self.titel += d


def seite(url, zeit=25):
    if not erlaubt(url):
        raise Gesperrt(url)
    inhalt, end, typ = hole(url, roh=True, zeit=zeit)
    return inhalt, end, typ


def sitemap_urls(basis, frist):
    """Alle URLs aus robots.txt-Sitemaps und üblichen Orten (höchstens 40 Teil-Sitemaps)."""
    kandidaten, gesehen, urls = [], set(), []
    try:
        robots, _, _ = _roh(urllib.parse.urljoin(basis, "/robots.txt"), roh=True, zeit=15)
        kandidaten += re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        pass
    kandidaten += [urllib.parse.urljoin(basis, p) for p in
                   ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap.xml.gz",
                    "/?type=1533906435", "/index.php?id=sitemap.xml")]
    gelesen = 0
    while kandidaten and gelesen < 40 and time.time() < frist:
        u = kandidaten.pop(0)
        if u in gesehen:
            continue
        gesehen.add(u)
        try:
            inhalt, _, _ = seite(u, zeit=20)
            if b"<urlset" not in inhalt[:2000] and b"<sitemapindex" not in inhalt[:2000]:
                continue
            baum = ET.fromstring(inhalt)
            gelesen += 1
        except Exception:  # noqa: BLE001
            continue
        for e in baum.iter():
            if e.tag.endswith("loc") and e.text:
                loc = e.text.strip()
                if baum.tag.endswith("sitemapindex"):
                    kandidaten.append(loc)
                else:
                    urls.append(loc)
        if urls and not kandidaten:
            break
    return urls, gelesen


def pruefe_seite(g):
    frist = time.time() + 60
    erg = {"ags": g["ags"], "name": g["name"], "web": None, "titel": "", "generator": "",
           "sitemap_urls": 0, "sitemaps": 0, "treffer": [], "suche": None, "start_treffer": []}
    kandidaten = list(g.get("web") or [])
    if not kandidaten:
        slug = re.sub(r"[^a-z0-9]+", "-", g["name"].lower().replace("ä", "ae").replace("ö", "oe")
                      .replace("ü", "ue").replace("ß", "ss")).strip("-")
        kandidaten = [f"https://www.{slug}.de/", f"https://www.stadt-{slug}.de/", f"https://www.gemeinde-{slug}.de/"]
        erg["geraten"] = True
    for k in kandidaten:
        try:
            inhalt, end, typ = seite(k)
            erg["web"] = end
            break
        except Gesperrt:
            erg["gesperrt"] = True
            erg.setdefault("fehler", []).append(f"{k}: robots.txt")
        except Exception as e:  # noqa: BLE001
            erg.setdefault("fehler", []).append(f"{k}: {repr(e)[:120]}")
    if not erg["web"]:
        return erg
    p = Links()
    try:
        p.feed(inhalt.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        pass
    erg["titel"], erg["generator"] = " ".join(p.titel.split())[:150], p.generator[:80]
    for href, text in p.links:
        if MUSTER.search(href + " " + text):
            erg["start_treffer"].append([urllib.parse.urljoin(erg["web"], href), text])
    # Sitemap
    urls, n = sitemap_urls(erg["web"], frist)
    erg["sitemap_urls"], erg["sitemaps"] = len(urls), n
    erg["treffer"] = sorted({u for u in urls if MUSTER.search(urllib.parse.unquote(u))})[:80]
    # Suche der Seite (GET-Formular mit einem Textfeld)
    for f in p.formen:
        if f["method"] != "get" or not f["felder"]:
            continue
        feld = next((x for x in f["felder"] if re.search(r"such|search|query|^q$|keyword|term|text|swr|sword", x, re.I)),
                    None)
        if not feld:
            continue
        ziel = urllib.parse.urljoin(erg["web"], f["action"] or erg["web"])
        for begriff in ("Verkehrszählung", "Zählstelle"):
            if time.time() > frist:
                break
            q = dict(f["versteckt"]) | {feld: begriff}
            url = ziel + ("&" if "?" in ziel else "?") + urllib.parse.urlencode(q)
            try:
                inhalt, end, _ = seite(url, zeit=25)
                s = Links()
                s.feed(inhalt.decode("utf-8", "replace"))
                funde = [[urllib.parse.urljoin(end, h), t] for h, t in s.links if MUSTER.search(h + " " + t)]
                erg["suche"] = {"url": url, "laenge": len(inhalt)}
                erg.setdefault("such_treffer", [])
                for x in funde:
                    if x not in erg["such_treffer"]:
                        erg["such_treffer"].append(x)
            except Gesperrt:
                erg["suche"] = {"url": url, "fehler": "robots.txt"}
                break
            except Exception as e:  # noqa: BLE001
                erg["suche"] = {"url": url, "fehler": repr(e)[:120]}
        break
    if "such_treffer" in erg:
        erg["such_treffer"] = erg["such_treffer"][:60]
    return erg


@schritt("webseiten")
def webseiten():
    ziele = sorted(GEMEINDEN.values(), key=lambda g: -(g.get("einw") or 0))
    ziele += [{"ags": k["ks"], "name": k["name"], "web": k["web"]} for k in KREISE.values()
              if "kreis" in k["name"].lower()]
    ziele += [{"ags": a, "name": n, "web": [w]} for a, n, w in LAND["extra"]]
    aus = []
    with cf.ThreadPoolExecutor(max_workers=24) as pool:
        for erg in pool.map(pruefe_seite, ziele):
            aus.append(erg)
            if len(aus) % 50 == 0:
                schreibe("webseiten.json", aus)
                print("webseiten", len(aus), round(time.time() - START), flush=True)
    schreibe("webseiten.json", aus)
    protokoll["webseiten"] = {
        "seiten": len(aus), "erreicht": sum(1 for e in aus if e["web"]),
        "mit_sitemap": sum(1 for e in aus if e["sitemap_urls"]),
        "mit_suche": sum(1 for e in aus if e.get("suche") and "fehler" not in e["suche"]),
        "mit_treffern": sum(1 for e in aus if e["treffer"] or e.get("such_treffer") or e["start_treffer"]),
    }


def lade_liste():
    """Gemeinden und Kreise aus einem früheren Lauf, sonst aus Wikidata."""
    if (ZIEL / "gemeinden.json").exists() and (ZIEL / "kreise.json").exists():
        for g in json.loads((ZIEL / "gemeinden.json").read_text()):
            GEMEINDEN[g["ags"]] = g
        for k in json.loads((ZIEL / "kreise.json").read_text()):
            KREISE[k["ks"]] = k
    else:
        wikidata()


if __name__ == "__main__":
    if "webseiten" in TEILE or "alle" in TEILE:
        lade_liste()
    if (ZIEL / "protokoll.json").exists():
        protokoll.update(json.loads((ZIEL / "protokoll.json").read_text()))
    if "fds" in TEILE or "alle" in TEILE:
        fds_gesetze()
        fds_behoerden()
        fds_anfragen()
    if "portale" in TEILE or "alle" in TEILE:
        govdata()
        if LAND["iso"] == "DE-NW":
            opennrw()
        mobilithek()
        osm()
    if ("webseiten" in TEILE or "alle" in TEILE) and GEMEINDEN:
        webseiten()
    protokoll[f"gesamt_sekunden_{'_'.join(TEILE)}"] = round(time.time() - START)
    schreibe(f"protokoll_{'_'.join(TEILE)}.json", protokoll)
    print(json.dumps(protokoll, ensure_ascii=False, indent=1)[:6000])
