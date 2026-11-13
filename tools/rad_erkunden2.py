"""Erkundung (13.11.2026), Teil 2: Formate, Lizenzen und Vollständigkeit der Kandidaten aus der
Katalogsuche (ergebnis/rad/). Für die Zählkarte zählt ein Tag nur, wenn jede Stunde gezählt ist.

Rad: MobiData BW (Eco-Counter, gebündelt), Berlin (Gesamtdatei Stundenwerte), Bonn, München,
Aachen, Bochum (GitLab), Opendatasoft-Portale (Mannheim, Würzburg, Dortmund, Rhein-Kreis Neuss),
Oldenburg, Braunschweig, Konstanz, Heidelberg, Leipzig (WFS), Freiburg (FR.ITZ).
Kfz: Stundenwerte der Landes-Dauerzählstellen BW, Darmstadt (Verkehrsdaten im Rohformat),
Osnabrück (Mobilithek), Kiel (Mobilithek), BASt-Rohdaten (nur Größe).
Jeder Teil schreibt sofort nach ergebnis/rad2/<teil>.txt; Fehler nach <teil>.fehler.txt.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ZIEL = Path("ergebnis/rad2")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}
BEGINN = time.time()


def hole(url: str, timeout: int = 60, max_mb: float = 400) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        daten = r.read(int(max_mb * 1e6) + 1)
    if len(daten) > max_mb * 1e6:
        raise ValueError(f"größer als {max_mb} MB")
    return daten


def kopf(url: str) -> str:
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return f"{r.status} {r.headers.get('Content-Length')} {r.headers.get('Content-Type')} {r.headers.get('Last-Modified')}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001
        return f"Fehler {e}"


def tabelle(daten: bytes) -> list[list[str]]:
    text = daten.decode("utf-8-sig", errors="replace")
    erste = text.splitlines()[0] if text else ""
    trenner = max([";", ",", "\t"], key=erste.count)
    return list(csv.reader(io.StringIO(text), delimiter=trenner))


def zeige(aus: list[str], zeilen: list[list[str]], n: int = 6, spalten_werte: int = 40) -> None:
    if not zeilen:
        aus.append("  (leer)")
        return
    k, d = zeilen[0], zeilen[1:]
    aus.append(f"  {len(d)} Zeilen; Kopf: {k}")
    aus += [f"  {z}" for z in d[:n]]
    for j, name in enumerate(k):
        werte = {z[j] for z in d if len(z) > j}
        if 1 < len(werte) <= spalten_werte:
            aus.append(f"  Spalte {name!r}: {sorted(werte)[:spalten_werte]}")


def teil(name: str):
    def deko(f):
        def lauf():
            if time.time() - BEGINN > 45 * 60:
                (ZIEL / f"{name}.fehler.txt").write_text("übersprungen: Zeit", encoding="utf-8")
                return
            aus: list[str] = []
            try:
                f(aus)
            except Exception:  # noqa: BLE001
                aus.append(traceback.format_exc())
                (ZIEL / f"{name}.fehler.txt").write_text(traceback.format_exc(), encoding="utf-8")
            (ZIEL / f"{name}.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
        return lauf
    return deko


@teil("bw_stundenwerte")
def bw_stundenwerte(aus):
    for m in ["202610", "202609", "202608"]:
        url = f"https://mobidata-bw.de/vm/Stundenwerte_Dauerzaehlstellen_BW/Stundenwerte_{m}.zip"
        k = kopf(url)
        aus.append(f"{url}: {k}")
        if not k.startswith("200"):
            continue
        z = zipfile.ZipFile(io.BytesIO(hole(url, 300)))
        infos = z.infolist()
        aus.append(f"  {len(infos)} Dateien, z. B.: " + ", ".join(f"{i.filename} ({i.file_size})" for i in infos[:12]))
        for i in infos[:2]:
            roh = z.read(i)
            aus.append(f"  == {i.filename}: erste Zeilen")
            aus += ["   " + s for s in roh.decode("latin-1", errors="replace").splitlines()[:12]]
        break
    for jahr in ["2026", "2025", "2015", "2010"]:
        aus.append(f"Monat {jahr}-01: {kopf(f'https://mobidata-bw.de/vm/Stundenwerte_Dauerzaehlstellen_BW/Stundenwerte_{jahr}01.zip')}")
    try:
        p = json.loads(hole("https://mobidata-bw.de/api/3/action/package_search?q=Stundenwerte%20Dauerz%C3%A4hlstellen&rows=10"))
        for x in p["result"]["results"]:
            aus.append(f"MobiData: {x['title']} | {x.get('license_id')} | {x['name']} | {(x.get('notes') or '')[:800]}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"MobiData-Suche: {e}")


@teil("mobidata_eco")
def mobidata_eco(aus):
    roh = gzip.decompress(hole("https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_202610.csv.gz", 300))
    zeilen = tabelle(roh)
    k, d = zeilen[0], zeilen[1:]
    i = {n: j for j, n in enumerate(k)}
    je = defaultdict(list)
    for z in d:
        je[z[i["counter_site_id"]]].append(z)
    kommunen = Counter(zz[0][i["domain_name"]] for zz in je.values())
    voll = Counter()
    luecken = Counter()
    fuss = []
    for sid, zz in je.items():
        tage = Counter(z[i["iso_timestamp"]][:10] for z in zz)
        voll[sum(1 for n in tage.values() if n >= 23)] += 1
        luecken[744 - len(zz) if len(zz) <= 745 else -1] += 1
        name = zz[0][i["counter_site"]]
        if any(w in name.lower() for w in ("fuß", "fuss", "fußg", "passant", "fußgänger")):
            fuss.append(name)
        na = sum(1 for z in zz if z[i["channels_all"]] in ("", "na"))
        if na:
            luecken[f"na:{na}"] += 1
    aus += [f"Oktober 2026: {len(je)} Zählstellen in {len(kommunen)} Kommunen/Kreisen",
            "je Kommune: " + ", ".join(f"{n} {c}" for n, c in kommunen.most_common()),
            "Tage mit ≥ 23 Stunden je Stelle (Anzahl Tage: Stellen): " + ", ".join(f"{a}:{b}" for a, b in sorted(voll.items())),
            "fehlende Stunden je Stelle (744 = voll): " + ", ".join(f"{a}:{b}" for a, b in sorted(luecken.items(), key=str)),
            f"Stellen mit Fuß im Namen ({len(fuss)}): {fuss}"]
    # Zeitumstellung 25.10.2026: Stunden um 2 Uhr
    um2 = Counter(z[i["iso_timestamp"]] for z in d if z[i["iso_timestamp"]].startswith("2026-10-25T02"))
    aus.append(f"25.10.2026 2 Uhr: {um2.most_common(4)}")
    # Monate, die es gibt
    monate = []
    for j in (2013, 2016, 2019, 2022, 2024):
        monate.append(f"{j}-06:{kopf(f'https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_{j}06.csv.gz')[:3]}")
    aus.append("Monatsdateien: " + " ".join(monate))


@teil("berlin_rad")
def berlin_rad(aus):
    import openpyxl

    url = ("https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/weitere-radinfrastruktur/"
           "zaehlstellen-und-fahrradbarometer/gesamtdatei-stundenwerte.xlsx")
    aus.append(f"{url}: {kopf(url)}")
    wb = openpyxl.load_workbook(io.BytesIO(hole(url, 300)), read_only=True, data_only=True)
    aus.append(f"Blätter: {wb.sheetnames}")
    for ws in wb.worksheets[:3]:
        aus.append(f"-- {ws.title} ({ws.max_row} x {ws.max_column})")
        for n, z in enumerate(ws.iter_rows(values_only=True)):
            if n >= 6:
                break
            aus.append("   " + " | ".join("" if v is None else str(v) for v in z[:14]))
    letztes = wb.worksheets[-1]
    aus.append(f"letztes Blatt {letztes.title}: {letztes.max_row} Zeilen")


@teil("bonn")
def bonn(aus):
    for jahr in (2025, 2024):
        url = f"https://opendata.bonn.de/sites/default/files/Fahrradzaehlstellen{jahr}_stuendlich.csv"
        k = kopf(url)
        aus.append(f"{url}: {k}")
        if k.startswith("200"):
            zeige(aus, tabelle(hole(url)))
            break
    try:
        p = json.loads(hole("https://ckan.open.nrw/api/3/action/package_search?q=Fahrradmessstellen%20Bonn&rows=30", 90))
        for x in p["result"]["results"]:
            aus.append(f"- {x['name']} | {x.get('license_id')} | " + "; ".join(str(r.get("url")) for r in x["resources"][:2]))
    except Exception as e:  # noqa: BLE001
        aus.append(f"open.nrw: {e}")


@teil("muenchen")
def muenchen(aus):
    url = ("https://opendata.muenchen.de/dataset/20d08df2-203a-4f99-968f-add90f86818a/resource/"
           "43f464bd-2302-4e41-a4bd-a412aec87108/download/rad_2026_07_15min.csv")
    z = tabelle(hole(url, 120))
    zeige(aus, z)
    k, d = z[0], z[1:]
    if "zaehlstelle" in k and "datum" in k:
        tage = defaultdict(Counter)
        for r in d:
            tage[r[k.index("zaehlstelle")]][r[k.index("datum")]] += 1
        aus.append("Tage mit 96 Viertelstunden je Stelle: " + str({s: sum(1 for n in t.values() if n >= 96) for s, t in tage.items()}))
    geo = json.loads(hole("https://geoportal.muenchen.de/geoserver/mor_wfs/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=mor_wfs:raddauerzaehlstellen&outputFormat=application/json", 60))
    aus.append(f"Stellen (WFS): {len(geo['features'])}; Felder {list(geo['features'][0]['properties'])}")
    aus += [f"  {f['properties']}" for f in geo["features"][:8]]
    p = json.loads(hole("https://opendata.muenchen.de/api/3/action/package_show?id=daten-der-raddauerzahlstellen-munchen-2026", 60))
    aus.append(f"Lizenz 2026: {p['result'].get('license_id')} {p['result'].get('license_title')}")


@teil("aachen")
def aachen(aus):
    url = ("https://offenedaten.aachen.de/dataset/c81cc173-5302-45d9-9b9d-87bea105f77e/resource/"
           "a9b788c8-f8bb-490d-8a18-443c76cddf05/download/radzaehlstellen_2026.csv")
    z = tabelle(hole(url, 120))
    zeige(aus, z)


@teil("bochum")
def bochum(aus):
    api = "https://gitlab.opencode.de/api/v4/projects/" + urllib.parse.quote("StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter", safe="")
    info = json.loads(hole(api, 60))
    aus.append(f"Projekt: {info.get('name_with_namespace')} | {info.get('description')} | zuletzt {info.get('last_activity_at')}")
    baum = json.loads(hole(api + "/repository/tree?recursive=true&per_page=100", 60))
    aus.append("Dateien: " + ", ".join(x["path"] for x in baum[:60]))
    for x in baum:
        if x["path"].lower() in ("license", "license.md", "readme.md"):
            aus.append(f"== {x['path']}")
            aus.append(hole(api + "/repository/files/" + urllib.parse.quote(x["path"], safe="") + "/raw?ref=main", 60).decode("utf-8", "replace")[:1500])
    roh = hole("https://gitlab.opencode.de/StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter/-/raw/main/data/universitaetsstrasse/bochum_ecocounter_universitaetsstrasse.csv", 120)
    z = tabelle(roh)
    zeige(aus, z, n=4)
    aus.append(f"  letzte Zeilen: {z[-2:]}")


def ods(aus, basis: str, ds: str) -> None:
    meta = json.loads(hole(f"{basis}/api/explore/v2.1/catalog/datasets/{ds}", 60))
    m = meta.get("metas", {}).get("default", {})
    aus.append(f"## {basis} {ds}: {m.get('title')} | Lizenz {m.get('license')} | {m.get('records_count')} Datensätze | geändert {m.get('modified')}")
    aus.append("  Felder: " + ", ".join(f"{f['name']}({f['type']})" for f in meta.get("fields", [])))
    rec = json.loads(hole(f"{basis}/api/explore/v2.1/catalog/datasets/{ds}/records?limit=4&order_by=" + urllib.parse.quote(meta["fields"][0]["name"] + " desc"), 60))
    for r in rec.get("results", [])[:4]:
        aus.append(f"  {r}")


@teil("opendatasoft")
def opendatasoft(aus):
    for basis, ds in [("https://mannheim.opendatasoft.com", "verkehrszahler-daten-eco-counter-v2"),
                      ("https://wuerzburg.opendatasoft.com", "fahrrad-zaehlung-daten"),
                      ("https://open-data.dortmund.de", "fb61-dauerzaehlstelle-radverkehr-schnettkerbruecke"),
                      ("https://opendata.rhein-kreis-neuss.de", "eco-counter-data")]:
        try:
            ods(aus, basis, ds)
        except Exception as e:  # noqa: BLE001
            aus.append(f"## {basis} {ds}: {e}")


@teil("weitere_rad")
def weitere_rad(aus):
    for name, url in [("Oldenburg 2025", "https://opendata.oldenburg.de/sites/default/files/Rad_2025.csv"),
                      ("Konstanz Herose 2021", "https://offenedaten-konstanz.de/sites/default/files/Zaehlstelle_Herose_2021_stuendlich_Wetter.csv"),
                      ("Freiburg FR.ITZ", "https://fritz.freiburg.de/duva2dcat/dataset/de-bw-freiburg-fahrrad-zaehlstellen_zeitreihe/content.csv")]:
        aus.append(f"## {name}: {url}")
        try:
            zeige(aus, tabelle(hole(url, 120, max_mb=200)), n=4, spalten_werte=30)
        except Exception as e:  # noqa: BLE001
            aus.append(f"  {e}")
    try:
        p = json.loads(hole("https://opendata.braunschweig.de/api/3/action/package_show?id=automatische-radverkehrsz%C3%A4hlung", 60))
        x = p["result"]
        aus.append(f"## Braunschweig: {x['title']} | {x.get('license_id')} | {(x.get('notes') or '')[:600]}")
        for r in x["resources"][:8]:
            aus.append(f"  - {r.get('name')} | {r.get('format')} | {r.get('url')}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## Braunschweig: {e}")
    try:
        g = json.loads(hole("https://geodienste.leipzig.de/l3/OpenData/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=OpenData%3Aradverkehr_dauerzaehlstelle_anzahl_stunde_zeitreihe&outputFormat=application%2Fjson&count=5", 60))
        aus.append(f"## Leipzig (Stunden, 31 Tage): Felder {list(g['features'][0]['properties'])}")
        aus += [f"  {f['properties']}" for f in g["features"][:5]]
    except Exception as e:  # noqa: BLE001
        aus.append(f"## Leipzig: {e}")
    try:
        p = json.loads(hole("https://ckan.datenplattform.heidelberg.de/api/3/action/package_search?q=Fahrradz%C3%A4hl&rows=10", 60))
        for x in p["result"]["results"]:
            aus.append(f"## Heidelberg: {x['title']} | {x.get('license_id')} | " + "; ".join(f"{r.get('name')} {r.get('url')}" for r in x["resources"][:3]))
    except Exception as e:  # noqa: BLE001
        aus.append(f"## Heidelberg: {e}")


@teil("kfz")
def kfz(aus):
    # Darmstadt: Verkehrsdaten im Rohformat (je Knoten ein ZIP)
    for url in ["https://opendata.darmstadt.de/sites/default/files/A110_1.zip",
                "https://opendata.darmstadt.de/sites/default/files/A126_4.zip"]:
        aus.append(f"## Darmstadt {url}: {kopf(url)}")
        try:
            z = zipfile.ZipFile(io.BytesIO(hole(url, 180, max_mb=150)))
            infos = z.infolist()
            aus.append(f"  {len(infos)} Dateien: " + ", ".join(f"{i.filename} ({i.file_size})" for i in infos[:10]))
            for i in infos[:1]:
                aus += ["   " + s for s in z.read(i).decode("utf-8", "replace").splitlines()[:10]]
        except Exception as e:  # noqa: BLE001
            aus.append(f"  {e}")
    for q in ("Verkehrsdaten im Rohformat", "Verkehrsdaten"):
        try:
            p = json.loads(hole("https://opendata.darmstadt.de/api/3/action/package_search?" + urllib.parse.urlencode({"q": q, "rows": 5}), 60))
            for x in p["result"]["results"]:
                aus.append(f"## Darmstadt-Katalog: {x['title']} | {x.get('license_id')} | {(x.get('notes') or '')[:700]}")
            break
        except Exception as e:  # noqa: BLE001
            aus.append(f"## Darmstadt-Katalog ({q}): {e}")
    # Osnabrück (Mobilithek, Hilfsdatei)
    url = "https://mobilithek.info/mdp-api/files/aux/903287344194932736/teu_dataset.zip"
    aus.append(f"## Osnabrück {url}: {kopf(url)}")
    try:
        z = zipfile.ZipFile(io.BytesIO(hole(url, 300, max_mb=300)))
        infos = z.infolist()
        aus.append(f"  {len(infos)} Dateien: " + ", ".join(f"{i.filename} ({i.file_size})" for i in infos[:10]))
        for i in infos[:1]:
            aus += ["   " + s for s in z.read(i).decode("utf-8", "replace").splitlines()[:8]]
    except Exception as e:  # noqa: BLE001
        aus.append(f"  {e}")
    for name, url in [("Mobilithek Osnabrück", "https://mobilithek.info/offers/903287344194932736"),
                      ("Mobilithek Kiel", "https://mobilithek.info/offers/995318989663924224"),
                      ("BASt Rohdaten 2026-07", "https://files.bast.de/index.php/s/9ocwEABdpFZCcjD/download/DZ_2026_07_Rohdaten.zip")]:
        aus.append(f"## {name}: {kopf(url)}")
    # Mobilithek-Metadaten über die öffentliche Suche (falls ohne Anmeldung erreichbar)
    for offer in ("903287344194932736", "995318989663924224"):
        try:
            t = hole(f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{offer}", 60).decode("utf-8", "replace")
            aus.append(f"## Angebot {offer}: {t[:2500]}")
        except Exception as e:  # noqa: BLE001
            aus.append(f"## Angebot {offer}: {e}")


if __name__ == "__main__":
    for f in (bw_stundenwerte, kfz, berlin_rad, mobidata_eco, bochum, opendatasoft, muenchen, aachen, bonn, weitere_rad):
        f()
