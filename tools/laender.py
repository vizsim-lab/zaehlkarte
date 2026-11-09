"""Werkzeug: alle Länder durchsuchen (wie BW in bw_suche2.py).

1. GovData: viele Suchbegriffe, je Paket Herausgeber und Regionalschlüssel (Land).
2. Landes- und Stadtportale (CKAN, Opendatasoft, piveau) mit wenigen Begriffen.
3. FragDenStaat: Volltextsuche, Zuständigkeiten, Anhänge der beantworteten Anfragen.
Ergebnis: ergebnis/laender/*.json (große Listen gzip).
"""

import gzip
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/laender")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
protokoll = {}
START = time.time()

ZAEHL = re.compile(r"z(ä|ae)hl|verkehrsmeng|verkehrsst(ä|ae)rk|verkehrsbelast|knotenstrom|querschnitt|"
                   r"seitenradar|radar|dtv|verkehrsaufkommen|verkehrserheb|verkehrsdaten|messstelle", re.I)


def hole(url, roh=False, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as a:
        daten = a.read()
    return daten if roh else json.loads(daten)


def schreibe(name, obj, gz=False):
    text = json.dumps(obj, ensure_ascii=False, indent=None if gz else 1)
    if gz:
        (ZIEL / (name + ".gz")).write_bytes(gzip.compress(text.encode("utf-8")))
    else:
        (ZIEL / name).write_text(text, encoding="utf-8")


EXTRAS = ("contributorID", "politicalGeocodingURI", "politicalGeocodingLevelURI", "publisher_name",
          "publisher_url", "spatial", "geocodingText", "issued", "modified", "temporal_start",
          "temporal_end", "licenseAttributionByText")


def kurz(paket):
    extras = {e.get("key"): e.get("value") for e in paket.get("extras") or []
              if e.get("key") in EXTRAS}
    return {
        "name": paket.get("name"), "titel": paket.get("title"),
        "org": (paket.get("organization") or {}).get("title"),
        "org_name": (paket.get("organization") or {}).get("name"),
        "autor": paket.get("author"), "pflege": paket.get("maintainer"),
        "lizenz": paket.get("license_id") or paket.get("license_title"),
        "geaendert": paket.get("metadata_modified"), "extras": extras,
        "tags": [t.get("name") for t in paket.get("tags") or []][:20],
        "notiz": re.sub(r"\s+", " ", paket.get("notes") or "")[:800],
        "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url")}
                       for r in paket.get("resources", [])][:25],
    }


def ckan_suche(api, begriffe, seiten=1, rows=1000, schluessel=""):
    funde = {}
    for b in begriffe:
        for s in range(seiten):
            q = {"q": b, "rows": rows, "start": s * rows}
            try:
                r = hole(api + "package_search?" + urllib.parse.urlencode(q), timeout=180)["result"]
                protokoll[f"{schluessel}:{b}:{s}"] = r["count"]
                for p in r["results"]:
                    e = funde.setdefault(p["name"], kurz(p))
                    if b not in e.setdefault("treffer", []):
                        e["treffer"].append(b)
                if (s + 1) * rows >= r["count"]:
                    break
            except Exception as e:  # noqa: BLE001
                protokoll[f"{schluessel}:{b}:{s}"] = repr(e)[:200]
                break
    return funde


# 1. GovData -------------------------------------------------------------------------------
BEGRIFFE = ["Verkehrszählung", "Verkehrszählungen", "Verkehrszähldaten", "Zähldaten", "Zählstelle",
            "Zählstellen", "Knotenpunktzählung", "Knotenstrom", "Querschnittszählung", "Verkehrsmengen",
            "Verkehrsstärke", "Verkehrsbelastung", "Verkehrserhebung", "Verkehrsuntersuchung",
            "Seitenradar", "Geschwindigkeitsmessung", "Verkehrsmessung", "Radverkehrszählung",
            "Fußverkehr Zählung", "Passantenzählung", "Verkehrsmonitoring", "Verkehrsmengenkarte",
            "DTV"]
gov = ckan_suche("https://www.govdata.de/ckan/api/3/action/", BEGRIFFE, seiten=2, schluessel="govdata")
schreibe("govdata_alle.json", gov, gz=True)
schreibe("govdata_zaehl.json", {n: p for n, p in gov.items()
                                if ZAEHL.search((p["titel"] or "") + " " + (p["notiz"] or ""))})
protokoll["zeit_govdata"] = round(time.time() - START)

# 2. Landes- und Stadtportale ----------------------------------------------------------------
KURZ = ["Verkehrszählung", "Zählung", "Verkehrsmengen", "Zählstelle", "Verkehrsdaten", "Knotenpunkt"]
CKAN = {
    "open_nrw": "https://ckan.open.nrw.de/api/3/action/",
    "opendata_ruhr": "https://opendata.ruhr/api/3/action/",
    "offenesdatenportal": "https://www.offenesdatenportal.de/api/3/action/",
    "berlin": "https://datenregister.berlin.de/api/3/action/",
    "hamburg": "https://suche.transparenz.hamburg.de/api/3/action/",
    "bremen": "https://transparenz.bremen.de/api/3/action/",
    "schleswig_holstein": "https://opendata.schleswig-holstein.de/api/3/action/",
    "rlp": "https://daten.rlp.de/api/3/action/",
    "niedersachsen": "https://opendata.niedersachsen.de/api/3/action/",
    "brandenburg": "https://daten.brandenburg.de/api/3/action/",
    "thueringen": "https://opendata.thueringen.de/api/3/action/",
    "mv": "https://www.opendata-mv.de/api/3/action/",
    "sachsen": "https://www.opendata.sachsen.de/api/3/action/",
    "leipzig": "https://opendata.leipzig.de/api/3/action/",
    "muenchen": "https://opendata.muenchen.de/api/3/action/",
    "frankfurt": "https://www.offenedaten.frankfurt.de/api/3/action/",
    "darmstadt": "https://opendata.darmstadt.de/api/3/action/",
    "koeln": "https://www.offenedaten-koeln.de/api/3/action/",
    "bonn": "https://opendata.bonn.de/api/3/action/",
    "duesseldorf": "https://opendata.duesseldorf.de/api/3/action/",
    "aachen": "https://offenedaten.aachen.de/api/3/action/",
    "bielefeld": "https://open-data.bielefeld.de/api/3/action/",
    "wuppertal": "https://www.offenedaten-wuppertal.de/api/3/action/",
    "hannover": "https://opendata.hannover.de/api/3/action/",
    "braunschweig": "https://opendata.braunschweig.de/api/3/action/",
    "rostock": "https://www.opendata-hro.de/api/3/action/",
    "kiel": "https://opendata.kiel.de/api/3/action/",
    "jena": "https://opendata.jena.de/api/3/action/",
    "erfurt": "https://opendata.erfurt.de/api/3/action/",
    "mainz": "https://opendata.mainz.de/api/3/action/",
}
portale = {}
for name, api in CKAN.items():
    if time.time() - START > 25 * 60:
        protokoll["abbruch_portale"] = name
        break
    portale[name] = ckan_suche(api, KURZ, rows=200, schluessel=name)
ODS = ["open-data.dortmund.de", "opendata.wuerzburg.de", "opendata.erlangen.de", "opendata.kassel.de",
       "opendata.regensburg.de", "opendata.bamberg.de", "opendata.leverkusen.de", "opendata.duisburg.de",
       "opendata.gelsenkirchen.de", "opendata.bochum.de", "opendata.muelheim-ruhr.de",
       "opendata.saarbruecken.de", "data.wolfsburg.de", "opendata.oldenburg.de"]
for host in ODS:
    for b in ("Verkehrszählung", "Zählung", "Verkehrsmengen", "Zählstelle"):
        try:
            r = hole(f"https://{host}/api/explore/v2.1/catalog/datasets?"
                     + urllib.parse.urlencode({"where": f'search("{b}")', "limit": 100}), timeout=30)
            protokoll[f"ods:{host}:{b}"] = r.get("total_count")
            for d in r.get("results", []):
                m = d.get("metas", {}).get("default", {})
                portale.setdefault("ods:" + host, {})[d.get("dataset_id")] = {
                    "titel": m.get("title"), "lizenz": m.get("license"), "geaendert": m.get("modified"),
                    "herausgeber": m.get("publisher"), "notiz": re.sub(r"<[^>]+>|\s+", " ",
                                                                      m.get("description") or "")[:800]}
        except Exception as e:  # noqa: BLE001
            protokoll[f"ods:{host}:{b}"] = repr(e)[:160]
            break
for b in ("Verkehrszählung", "Zählstelle", "Verkehrsmengen"):
    try:
        r = hole("https://open.bydata.de/api/hub/search/search?"
                 + urllib.parse.urlencode({"q": b, "filter": "dataset", "limit": 200}), timeout=60)
        erg = r.get("result", {})
        protokoll[f"bydata:{b}"] = erg.get("count")
        for d in erg.get("results", []):
            titel = d.get("title") or {}
            beschr = d.get("description") or {}
            portale.setdefault("bydata", {})[d.get("id")] = {
                "titel": titel.get("de") if isinstance(titel, dict) else titel,
                "herausgeber": (d.get("publisher") or {}).get("name"),
                "katalog": (d.get("catalog") or {}).get("id"),
                "notiz": re.sub(r"\s+", " ", (beschr.get("de") if isinstance(beschr, dict) else beschr) or "")[:800]}
    except Exception as e:  # noqa: BLE001
        protokoll[f"bydata:{b}"] = repr(e)[:160]
schreibe("portale.json", portale)
protokoll["zeit_portale"] = round(time.time() - START)

# 3. FragDenStaat ----------------------------------------------------------------------------
FDS = "https://fragdenstaat.de/api/v1/"
try:
    zust = hole(FDS + "jurisdiction/?limit=100")
    schreibe("fds_zustaendigkeiten.json", {str(j["id"]): j.get("name") for j in zust.get("objects", [])})
except Exception as e:  # noqa: BLE001
    protokoll["fds:zust"] = repr(e)[:200]
anfragen = {}
for b in ("Verkehrszählung", "Verkehrszählungen", "Verkehrsmengen", "Verkehrszahlen", "Zähldaten",
          "Knotenpunkt Zählung", "Verkehrsaufkommen Zählung", "Verkehrsbelastung", "Verkehrserhebung",
          "Verkehrsstärke", "Radverkehr Zählung", "Verkehrsdaten Zählung"):
    for offset in range(0, 600, 50):
        try:
            r = hole(FDS + "request/search/?" + urllib.parse.urlencode(
                {"q": b, "limit": 50, "offset": offset}), timeout=60)
            objs = r.get("objects", [])
            protokoll[f"fds:{b}"] = (r.get("meta") or {}).get("total_count")
            for o in objs:
                pb = o.get("public_body") if isinstance(o.get("public_body"), dict) else {}
                e = anfragen.setdefault(str(o.get("id")), {
                    "titel": o.get("title"), "url": o.get("url"), "status": o.get("status"),
                    "ergebnis": o.get("resolution"), "erste": o.get("first_message"),
                    "letzte": o.get("last_message"), "zust": o.get("jurisdiction"),
                    "behoerde": pb.get("name"), "behoerde_id": pb.get("id"),
                    "behoerde_zust": (pb.get("jurisdiction") or {}).get("name")
                    if isinstance(pb.get("jurisdiction"), dict) else pb.get("jurisdiction"),
                    "behoerde_art": (pb.get("classification") or {}).get("name")
                    if isinstance(pb.get("classification"), dict) else pb.get("classification"),
                    "treffer": []})
                e["treffer"].append(b)
            if len(objs) < 50:
                break
            time.sleep(0.4)
        except Exception as e:  # noqa: BLE001
            protokoll[f"fds:{b}:{offset}"] = repr(e)[:200]
            break
protokoll["fds_anzahl"] = len(anfragen)

# Anhänge der beantworteten Anfragen mit Zähl-Bezug im Titel
details = 0
for rid, e in sorted(anfragen.items(), key=lambda kv: kv[1].get("letzte") or "", reverse=True):
    if time.time() - START > 38 * 60 or details >= 450:
        protokoll["fds_details_abbruch"] = details
        break
    if not ZAEHL.search(e["titel"] or "") and not re.search(r"verkehr", e["titel"] or "", re.I):
        continue
    if e["ergebnis"] not in ("successful", "partially_successful") and e["status"] != "resolved":
        continue
    try:
        d = hole(FDS + f"request/{rid}/", timeout=60)
        details += 1
        nachrichten = []
        for m in d.get("messages", []):
            anh = [{"name": a.get("name"), "typ": a.get("filetype"), "groesse": a.get("size"),
                    "url": a.get("file_url") or a.get("site_url")} for a in m.get("attachments") or []]
            if m.get("is_response") or anh:
                nachrichten.append({"datum": m.get("timestamp"), "betreff": m.get("subject"),
                                    "antwort": m.get("is_response"), "anhaenge": anh,
                                    "text": re.sub(r"\s+", " ", m.get("content") or "")[:700]})
        e["nachrichten"] = nachrichten
        e["kosten"] = d.get("costs")
        e["gesetz"] = (d.get("law") or {}).get("name") if isinstance(d.get("law"), dict) else d.get("law")
        time.sleep(0.4)
    except Exception as ex:  # noqa: BLE001
        e["fehler"] = repr(ex)[:200]
schreibe("fds_anfragen.json", anfragen)
protokoll["zeit_ende"] = round(time.time() - START)
schreibe("protokoll.json", protokoll)
print(json.dumps(protokoll, ensure_ascii=False, indent=1)[:5000])
