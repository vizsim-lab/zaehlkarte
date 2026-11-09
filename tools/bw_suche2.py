"""Werkzeug: BW, zweite Runde.

1. Ettlingen (READI-CKAN): Paket, CSVs, Datastore samt Zusammenfassung je Standort; READI-Suche.
2. Freiburg: WFS der Verkehrssensoren, FR.ITZ-Katalog, Stadtseiten (Links), VU Schlossbergring,
   Meldung „Moderne Verkehrszählung“ (gerendert).
3. FragDenStaat: Volltextsuche je Stadt, Behörden (Funktionsadressen).
4. Weitere Portale: GovData (nur „Open Data Baden-Württemberg“), Karlsruhe, Ulm, Heidelberg,
   Mannheim.
"""

import csv
import gzip
import io
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/bw2")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
protokoll = {}


def hole(url, roh=False, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as a:
        daten = a.read()
    return daten if roh else json.loads(daten)


def schreibe(pfad, obj):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def kurz(paket):
    return {
        "name": paket.get("name"), "titel": paket.get("title"),
        "org": (paket.get("organization") or {}).get("title"),
        "autor": paket.get("author"), "pflege": paket.get("maintainer"),
        "lizenz": paket.get("license_id") or paket.get("license_title"),
        "geaendert": paket.get("metadata_modified"),
        "notiz": re.sub(r"\s+", " ", paket.get("notes") or "")[:700],
        "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url")}
                       for r in paket.get("resources", [])][:30],
    }


def ckan_suche(api, begriffe, fq=None, schluessel=""):
    funde = {}
    for b in begriffe:
        q = {"q": b, "rows": 1000}
        if fq:
            q["fq"] = fq
        try:
            r = hole(api + "?" + urllib.parse.urlencode(q))["result"]
            protokoll[f"{schluessel}{api}:{b}"] = r["count"]
            for p in r["results"]:
                eintrag = funde.setdefault(p["name"], kurz(p))
                eintrag.setdefault("treffer", []).append(b)
        except Exception as e:  # noqa: BLE001
            protokoll[f"{schluessel}{api}:{b}"] = repr(e)[:200]
    return funde


def links(html, muster):
    """(Text, URL) der Links, deren URL oder Text auf muster passt."""
    funde = []
    for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.S):
        text = re.sub(r"<[^>]+>|\s+", " ", text).strip()
        if re.search(muster, href + " " + text, flags=re.I):
            funde.append([text[:160], href])
    return funde


def text_von(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


# 1. Ettlingen -------------------------------------------------------------------------------
READI = "https://opendata.readi.de/api/3/action/"
ETTL = ZIEL / "ettlingen"
ETTL.mkdir(exist_ok=True)
DS = "a903967d-9177-4db6-977c-267fd745a390"
try:
    paket = hole(READI + "package_show?id=automatisierte-verkehrszahlung-in-ettlingen")["result"]
    schreibe(ETTL / "paket.json", paket)
    for r in paket.get("resources", []):
        url = r.get("url") or ""
        if url.lower().endswith(".csv"):
            try:
                (ETTL / url.rsplit("/", 1)[-1]).write_bytes(hole(url, roh=True))
            except Exception as e:  # noqa: BLE001
                protokoll[url] = repr(e)[:200]
except Exception as e:  # noqa: BLE001
    protokoll["ettlingen:paket"] = repr(e)[:200]

try:
    schreibe(ETTL / "datastore_info.json",
             hole(READI + f"datastore_search?resource_id={DS}&limit=3")["result"])
except Exception as e:  # noqa: BLE001
    protokoll["ettlingen:datastore_search"] = repr(e)[:200]

try:
    daten = hole(f"https://opendata.readi.de/datastore/dump/{DS}", roh=True, timeout=900)
    protokoll["ettlingen:dump_bytes"] = len(daten)
    gz = gzip.compress(daten)
    if len(gz) < 90_000_000:
        (ETTL / "datastore.csv.gz").write_bytes(gz)
    else:
        (ETTL / "datastore_anfang.csv").write_bytes(b"\n".join(daten.split(b"\n")[:5000]))
    je = defaultdict(lambda: {"zeilen": 0, "von": None, "bis": None, "serien": Counter(),
                              "richtungen": Counter(), "spuren": Counter(), "lage": Counter(),
                              "quelle": Counter(), "klassen": Counter(), "sensoren": Counter(),
                              "tage": Counter(), "summe_y": 0.0})
    for z in csv.DictReader(io.StringIO(daten.decode("utf-8-sig"))):
        s = je[(z.get("dataset_id") or "") + " | " + (z.get("label") or "")]
        s["zeilen"] += 1
        t = z.get("timestamp") or ""
        s["von"] = t if s["von"] is None or t < s["von"] else s["von"]
        s["bis"] = t if s["bis"] is None or t > s["bis"] else s["bis"]
        s["tage"][t[:10]] += 1
        for feld, ziel in (("series_name", "serien"), ("direction", "richtungen"),
                           ("lane_index", "spuren"), ("source", "quelle"),
                           ("classification", "klassen"), ("sensor_id", "sensoren")):
            s[ziel][z.get(feld) or ""] += 1
        s["lage"][f"{z.get('latitude')},{z.get('longitude')}"] += 1
        try:
            s["summe_y"] += float(z.get("y") or 0)
        except ValueError:
            pass
    zus = {}
    for k, s in je.items():
        zus[k] = {**{f: s[f] for f in ("zeilen", "von", "bis", "summe_y")},
                  "tage": len(s["tage"]), "tage_liste": sorted(s["tage"])[:400],
                  **{f: s[f].most_common(30) for f in ("serien", "richtungen", "spuren", "lage",
                                                       "quelle", "klassen", "sensoren")}}
    schreibe(ETTL / "standorte.json", zus)
except Exception as e:  # noqa: BLE001
    protokoll["ettlingen:dump"] = repr(e)[:200]

schreibe(ZIEL / "readi.json", ckan_suche(READI + "package_search", [
    "Verkehrszählung", "Verkehr", "Zählung", "Radar", "Geschwindigkeit", "UrbanPulse",
    "Messstelle", "Mobilität", "Fahrrad", "Kfz"]))
try:
    schreibe(ZIEL / "readi_organisationen.json",
             [{"name": o.get("name"), "titel": o.get("title"), "pakete": o.get("package_count")}
              for o in hole(READI + "organization_list?all_fields=true")["result"]])
except Exception as e:  # noqa: BLE001
    protokoll["readi:organisationen"] = repr(e)[:200]

# 2. Freiburg --------------------------------------------------------------------------------
FR = ZIEL / "freiburg"
FR.mkdir(exist_ok=True)
WFS = "https://geoportal.freiburg.de/wfs/digit_verkehrszaehl/digit_verkehrszaehl"
try:
    cap = hole(WFS + "?REQUEST=GetCapabilities&SERVICE=WFS", roh=True).decode("utf-8", "replace")
    (FR / "wfs_capabilities.xml").write_text(cap, encoding="utf-8")
    typen = re.findall(r"<(?:wfs:)?FeatureType>.*?<(?:wfs:)?Name>([^<]+)<", cap, flags=re.S)
    protokoll["freiburg:typen"] = typen
    for t in typen[:20]:
        for fmt in ("geojson", "application/json", "GML3"):
            url = (f"{WFS}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={t}"
                   f"&OUTPUTFORMAT={urllib.parse.quote(fmt)}&COUNT=20000&SRSNAME=EPSG:4326")
            try:
                inhalt = hole(url, roh=True, timeout=300)
                (FR / f"wfs_{t.replace(':', '_')}.{'json' if 'json' in fmt else 'gml'}").write_bytes(
                    inhalt[:40_000_000])
                protokoll[f"freiburg:{t}:{fmt}"] = len(inhalt)
                break
            except Exception as e:  # noqa: BLE001
                protokoll[f"freiburg:{t}:{fmt}"] = repr(e)[:200]
except Exception as e:  # noqa: BLE001
    protokoll["freiburg:wfs"] = repr(e)[:200]

for name, url in {
    "geoportal_wfs_index": "https://geoportal.freiburg.de/wfs/",
    "fritz_katalog": "https://fritz.freiburg.de/duva2dcat/",
    "fritz_opendata": "https://www.freiburg.de/pb/541381.html",
    "radzaehlstellen": "https://www.freiburg.de/pb/336245.html",
    "vep": "https://www.freiburg.de/pb/231652.html",
    "mobilitaet": "https://www.freiburg.de/pb/1649864.html",
    "verkehrsbehoerde_fds": "https://fragdenstaat.de/behoerde/15609/verkehrsbehorde-stadt-freiburg-im-breisgau/",
}.items():
    try:
        html = hole(url, roh=True).decode("utf-8", "replace")
        (FR / f"{name}.html").write_text(html, encoding="utf-8")
        schreibe(FR / f"{name}_links.json",
                 links(html, r"z(ä|ae)hl|verkehr|mobil|daten|\.pdf|\.xlsx?|\.csv|\.zip|dataset"))
        (FR / f"{name}.txt").write_text(text_von(html)[:200_000], encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        protokoll[url] = repr(e)[:200]

for name, url in {
    "vu_schlossbergring.pdf": "https://www.freiburg.de/pb/site/Freiburg/get/params_E-138366714/2151489/231205_Bericht_VU%20Schlossberring.pdf",
}.items():
    try:
        (FR / name).write_bytes(hole(url, roh=True, timeout=300))
        subprocess.run(["pdftotext", "-layout", str(FR / name), str(FR / name) + ".txt"], check=False)
    except Exception as e:  # noqa: BLE001
        protokoll[url] = repr(e)[:200]

# Gerendert: Meldung und Ulmer Datenhub
try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(locale="de-DE")
        for name, url in {
            "meldung_verkehrszaehlung": "https://digital.freiburg.de/neuigkeiten/detail/moderne-verkehrszaehlung-in-freiburg",
            "ulm_datenhub": "https://datenhub.ulm.de/",
            "ulm_suche": "https://datenhub.ulm.de/suche?q=Verkehr",
        }.items():
            try:
                seite.goto(url, wait_until="networkidle", timeout=60_000)
                (FR / f"{name}.txt").write_text(seite.inner_text("body"), encoding="utf-8")
                schreibe(FR / f"{name}_links.json", seite.eval_on_selector_all(
                    "a", "els => els.map(e => [e.innerText.trim().slice(0, 160), e.href])"))
            except Exception as e:  # noqa: BLE001
                protokoll[f"playwright:{name}"] = repr(e)[:200]
        browser.close()
except Exception as e:  # noqa: BLE001
    protokoll["playwright"] = repr(e)[:300]

# 3. FragDenStaat ----------------------------------------------------------------------------
fds = {}
for stadt in ("Freiburg", "Ettlingen", "Karlsruhe", "Mannheim", "Heidelberg", "Ulm", "Heilbronn",
              "Pforzheim", "Reutlingen", "Tübingen", "Esslingen", "Ludwigsburg", "Stuttgart"):
    try:
        r = hole("https://fragdenstaat.de/api/v1/request/search/?" + urllib.parse.urlencode(
            {"q": f"Verkehrszählung {stadt}", "limit": 50}))
        fds[stadt] = {"anzahl": (r.get("meta") or {}).get("total_count"), "funde": [
            {k: o.get(k) for k in ("title", "url", "status", "resolution", "first_message",
                                   "last_message", "jurisdiction")}
            | {"behoerde": (o.get("public_body") or {}).get("name")
               if isinstance(o.get("public_body"), dict) else o.get("public_body")}
            for o in r.get("objects", [])]}
    except Exception as e:  # noqa: BLE001
        fds[stadt] = repr(e)[:200]
schreibe(ZIEL / "fragdenstaat_suche.json", fds)

behoerden = {}
for q in ("Stadt Freiburg im Breisgau", "Freiburg im Breisgau", "Stadt Ettlingen", "Ettlingen"):
    try:
        r = hole("https://fragdenstaat.de/api/v1/publicbody/?" + urllib.parse.urlencode(
            {"q": q, "limit": 50}))
        behoerden[q] = [{k: o.get(k) for k in ("id", "name", "email", "url", "site_url",
                                               "classification", "jurisdiction")}
                        for o in r.get("objects", [])]
    except Exception as e:  # noqa: BLE001
        behoerden[q] = repr(e)[:200]
for nr in (15609,):
    try:
        o = hole(f"https://fragdenstaat.de/api/v1/publicbody/{nr}/")
        behoerden[str(nr)] = {k: o.get(k) for k in ("id", "name", "email", "url", "site_url",
                                                    "classification", "jurisdiction", "parent")}
    except Exception as e:  # noqa: BLE001
        behoerden[str(nr)] = repr(e)[:200]
schreibe(ZIEL / "fragdenstaat_behoerden.json", behoerden)

# 4. Weitere Portale -------------------------------------------------------------------------
GOV = "https://www.govdata.de/ckan/api/3/action/"
try:
    org = hole(GOV + "package_show?id=automatisierte-verkehrszahlung-in-ettlingen")["result"]
    slug = (org.get("organization") or {}).get("name")
    protokoll["govdata:bw_slug"] = slug
    schreibe(ZIEL / "govdata_bw.json", ckan_suche(GOV + "package_search", [
        "Zählung", "Zählstelle", "Zählstellen", "Verkehrsmengen", "Verkehrsbelastung",
        "Verkehrsstärke", "Radar", "Geschwindigkeit", "Verkehrsdaten", "Messstelle", "Kfz",
        "Verkehrserhebung", "Verkehrsuntersuchung", "Verkehrszählung"],
        fq=f"organization:{slug}", schluessel="bw:"))
except Exception as e:  # noqa: BLE001
    protokoll["govdata:bw"] = repr(e)[:200]

for name, api in {
    "karlsruhe": "https://transparenz.karlsruhe.de/api/3/action/package_search",
    "ulm": "https://datenhub.ulm.de/ckan/api/3/action/package_search",
    "heidelberg": "https://ckan.datenplattform.heidelberg.de/api/3/action/package_search",
}.items():
    schreibe(ZIEL / f"{name}.json", ckan_suche(api, [
        "Verkehrszählung", "Zählung", "Verkehrsmengen", "Verkehr", "Radar"]))
try:
    schreibe(ZIEL / "mannheim.json", hole(
        "https://mannheim.opendatasoft.com/api/explore/v2.1/catalog/datasets?"
        + urllib.parse.urlencode({"where": 'search("Verkehr")', "limit": 100})))
except Exception as e:  # noqa: BLE001
    protokoll["mannheim"] = repr(e)[:200]

schreibe(ZIEL / "protokoll.json", protokoll)
print(json.dumps(protokoll, ensure_ascii=False, indent=1)[:6000])
