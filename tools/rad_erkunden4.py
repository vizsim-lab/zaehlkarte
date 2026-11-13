"""Erkundung (13.11.2026), Teil 4: Stichproben für die Rad-Adapter und der Kieler Zugang.

- Kiel: Mobilithek (Metadaten, Suche, Abruf ohne Konto), DatenDock der KielRegion, Landesportal SH.
- MobiData BW (Eco-Counter, v2): verfügbare Monate, Zeitumstellung (2 Uhr am Rückstelltag),
  Vergleich mit dem alten Format (Spalte `stand`), Anleitung (PDF-Text), Monatsdatei als Stichprobe.
- Aachen, Berlin, München, Münster (Standorte): Ressourcen und Dateien als Stichprobe.
Stichproben nach ergebnis/rad4/daten/ (für die Adapter-Tests von Hand), Berichte nach ergebnis/rad4/.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import statistics
import traceback
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ZIEL = Path("ergebnis/rad4")
DATEN = ZIEL / "daten"
DATEN.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str, timeout: int = 120, daten: bytes | None = None, kopf: dict | None = None) -> bytes:
    req = urllib.request.Request(url, headers={**UA, **(kopf or {})}, data=daten)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def probe(url: str, daten: bytes | None = None, kopf: dict | None = None, n: int = 600) -> str:
    req = urllib.request.Request(url, headers={**UA, **(kopf or {})}, data=daten)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            t = r.read(200000)
            return (f"{r.status} {r.headers.get('Content-Type')} {len(t)} B: "
                    + t[:n].decode("utf-8", "replace").replace("\n", " "))
    except urllib.error.HTTPError as e:
        try:
            t = e.read(2000).decode("utf-8", "replace").replace("\n", " ")
        except Exception:  # noqa: BLE001
            t = ""
        return f"HTTP {e.code}: {t[:n]}"
    except Exception as e:  # noqa: BLE001
        return f"Fehler {e!r}"


def teil(name, f):
    aus: list[str] = []
    try:
        f(aus)
    except Exception:  # noqa: BLE001
        aus.append(traceback.format_exc())
    (ZIEL / f"{name}.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


def speichere(name: str, daten: bytes, packen: bool = True) -> Path:
    if packen and not name.endswith(".gz"):
        p = DATEN / (name + ".gz")
        with gzip.GzipFile(p, "wb", mtime=0) as f:
            f.write(daten)
    else:
        p = DATEN / name
        p.write_bytes(daten)
    return p


def rueckstellung(jahr: int) -> date:
    d = date(jahr, 10, 31)
    return d - timedelta(days=(d.weekday() - 6) % 7)


# ---------------------------------------------------------------------------------------- Kiel
def kiel(aus):
    basis = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/"
    oid = "995318989663924224"
    aus.append("## Metadaten: " + probe(basis + oid, n=300))
    for url in [
        f"https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{oid}/clientPullService",
        f"https://mobilithek.info/mdp-api/mdp-conn-server/v1/publication/{oid}/clientPullService?subscriptionID={oid}",
        f"https://mobilithek.info/mdp-api/mdp-conn-server/v1/subscription/{oid}/clientPullService",
        f"https://mobilithek.info/mdp-api/files/aux/{oid}/",
        f"https://mobilithek.info/offers/{oid}",
    ]:
        aus.append(f"## {url}\n   " + probe(url))
    # Suche nach neueren Kieler Angeboten
    for url, daten in [
        ("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers?searchString=Kiel&page=0&size=50", None),
        ("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search?searchString=Kiel", None),
        ("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search",
         json.dumps({"searchString": "Kiel Dauerzählstellen", "page": 0, "size": 50}).encode()),
        ("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search/filtered",
         json.dumps({"searchString": "Kiel", "page": 0, "size": 50}).encode()),
    ]:
        aus.append(f"## Suche {url}\n   " + probe(url, daten, {"Content-Type": "application/json"} if daten else None, n=1500))
    # DatenDock
    try:
        t = hole("https://datendock.civora.org/app/dashboards/30", 60).decode("utf-8", "replace")
        aus.append(f"## DatenDock-Seite: {len(t)} Zeichen; Titel: {re.findall(r'<title>([^<]*)', t)[:1]}")
        aus.append("   Skripte: " + ", ".join(re.findall(r'src="([^"]+)"', t)[:10]))
        aus.append("   API-Treffer: " + ", ".join(sorted(set(re.findall(r'["\'](/?api[^"\']{0,80})["\']', t)))[:20]))
        aus.append("   Anfang: " + t[:800].replace("\n", " "))
        for s in re.findall(r'src="([^"]+\.js)"', t)[:3]:
            js_url = urllib.parse.urljoin("https://datendock.civora.org/app/dashboards/30", s)
            try:
                js = hole(js_url, 60).decode("utf-8", "replace")
                treffer = sorted(set(re.findall(r'["\'`](/api/[^"\'`]{1,80}|https?://[^"\'`]{5,80}api[^"\'`]{0,60})["\'`]', js)))
                aus.append(f"   {js_url}: {len(js)} Zeichen, API-Pfade: {treffer[:40]}")
            except Exception as e:  # noqa: BLE001
                aus.append(f"   {js_url}: {e!r}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## DatenDock-Seite: {e!r}")
    for url in ["https://datendock.civora.org/api/", "https://datendock.civora.org/api/v1/",
                "https://datendock.civora.org/api/dashboards/30", "https://datendock.civora.org/api/public/dashboards",
                "https://datendock.civora.org/v1.1/Things", "https://datendock.civora.org/FROST-Server/v1.1/Things",
                "https://datendock.civora.org/sta/v1.1/Things", "https://datendock.civora.org/ngsi-ld/v1/entities",
                "https://datendock.civora.org/"]:
        aus.append(f"## {url}\n   " + probe(url, n=400))
    # Landesportal SH und Stadt Kiel
    for q in ("Dauerzählstellen Kiel", "KielRegion", "Verkehrszählung Kiel", "MIV Kiel"):
        url = "https://opendata.schleswig-holstein.de/api/3/action/package_search?" + urllib.parse.urlencode({"q": q, "rows": 20})
        try:
            r = json.loads(hole(url, 60))["result"]
            aus.append(f"## SH-Portal {q!r}: {r['count']} Treffer: " + " | ".join(
                f"{p['title']} ({p['name']}, {p.get('license_id')})" for p in r["results"][:20]))
        except Exception as e:  # noqa: BLE001
            aus.append(f"## SH-Portal {q!r}: {e!r}")


# ------------------------------------------------------------------------------------ MobiData
MD = "https://mobidata-bw.de/daten/eco-counter/v2/"


def _md_monat(jjjjmm: str, sichern: bool = False) -> list[dict]:
    gz = hole(f"{MD}fahrradzaehler_stundenwerten_{jjjjmm}.csv.gz", 300)
    if sichern:
        speichere(f"mobidata_{jjjjmm}.csv.gz", gz, packen=False)
    roh = gzip.decompress(gz)
    return list(csv.DictReader(io.StringIO(roh.decode("utf-8-sig"))))


def mobidata(aus):
    # verfügbare Monate (HEAD)
    da, fehlt = [], []
    for j in range(2012, 2027):
        for m in range(1, 13):
            if (j, m) > (2026, 11):
                break
            url = f"{MD}fahrradzaehler_stundenwerten_{j}{m:02d}.csv.gz"
            req = urllib.request.Request(url, headers=UA, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    da.append(f"{j}-{m:02d}:{int(r.headers.get('Content-Length') or 0) // 1000}k")
            except Exception:  # noqa: BLE001
                fehlt.append(f"{j}-{m:02d}")
    aus.append(f"## Monate vorhanden ({len(da)}): {' '.join(da)}")
    aus.append(f"## Monate fehlen ({len(fehlt)}): {' '.join(fehlt)}")
    # Zeitumstellung: 2 Uhr am Rückstelltag gegen 1 und 3 Uhr, verglichen mit normalen Sonntagen
    for jjjjmm in ("202310", "202410", "202510", "202610"):
        try:
            z = _md_monat(jjjjmm, sichern=jjjjmm in ("202610", "202510"))
        except Exception as e:  # noqa: BLE001
            aus.append(f"## {jjjjmm}: {e!r}")
            continue
        rt =rueckstellung(int(jjjjmm[:4])).isoformat()
        je = defaultdict(lambda: defaultdict(dict))
        offs = Counter()
        for r in z:
            ts = r["iso_timestamp"]
            tag, uhr = ts[:10], int(ts[11:13])
            if tag == rt and uhr in (1, 2, 3):
                offs[ts[11:]] += 1
            if r["channels_all"] not in ("", "na"):
                je[r["counter_site_id"]][tag][uhr] = float(r["channels_all"])
        rr, rn = [], []
        for _, tage in je.items():
            for tag, hs in tage.items():
                if date.fromisoformat(tag).weekday() != 6 or not all(h in hs for h in (1, 2, 3)):
                    continue
                a = (hs[1] + hs[3]) / 2
                if a >= 3:
                    (rr if tag == rt else rn).append(hs[2] / a)
        aus.append(f"## {jjjjmm}: Rückstelltag {rt}: Zeitstempel 1–3 Uhr {dict(offs)}; "
                   f"2 Uhr / Mittel(1, 3 Uhr): Rückstelltag Median "
                   f"{statistics.median(rr) if rr else None} ({len(rr)} Stellen), normale Sonntage "
                   f"{statistics.median(rn) if rn else None} ({len(rn)})")
        # Summe in+out+unknown = all?
        ungleich = sum(1 for r in z if r["channels_all"] not in ("", "na") and all(
            r[k] not in ("", "na") for k in ("channels_in", "channels_out", "channels_unknown"))
            and abs(float(r["channels_in"]) + float(r["channels_out"]) + float(r["channels_unknown"])
                    - float(r["channels_all"])) > 0.5)
        leer = Counter((r["channels_in"] in ("", "na"), r["channels_out"] in ("", "na"),
                        r["channels_unknown"] in ("", "na"), r["channels_all"] in ("", "na")) for r in z)
        aus.append(f"   in+out+unknown != all: {ungleich}; leer (in, out, unknown, all): {dict(leer)}")
    # Sommerzeit-Beginn 2026: Zeilen um 2 Uhr?
    try:
        z = _md_monat("202603")
        um2 = Counter(r["iso_timestamp"] for r in z if r["iso_timestamp"].startswith("2026-03-29T0"))
        aus.append(f"## 29.03.2026 Zeitstempel 0–9 Uhr: {sorted(um2.items())}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## 202603: {e!r}")
    # altes Format (7 Tage, je Kanal, mit `stand`) gegen v2 (7 Tage)
    try:
        alt = list(csv.DictReader(io.StringIO(hole("https://mobidata-bw.de/daten/eco-counter/eco_counter_fahrradzaehler.csv", 300).decode("utf-8-sig"))))
        neu = list(csv.DictReader(io.StringIO(hole(f"{MD}fahrradzaehler_stundenwerten.csv", 300).decode("utf-8-sig"))))
        aus.append(f"## altes Format: {len(alt)} Zeilen, stand: {Counter(r['stand'] for r in alt).most_common()}, "
                   f"interval: {Counter(r['interval'] for r in alt).most_common()}")
        summe_alt = defaultdict(float)
        stand_je = defaultdict(set)
        for r in alt:
            k = (r["counter_site_id"], r["iso_timestamp"][:13])
            summe_alt[k] += float(r["zählstand"] or 0)
            stand_je[k].add(r["stand"])
        gleich = ungleich = 0
        bsp = []
        for r in neu:
            k = (r["counter_site_id"], r["iso_timestamp"][:13])
            if k in summe_alt and r["channels_all"] not in ("", "na"):
                if abs(summe_alt[k] - float(r["channels_all"])) < 0.5:
                    gleich += 1
                else:
                    ungleich += 1
                    if len(bsp) < 8:
                        bsp.append((k, summe_alt[k], r["channels_all"], sorted(stand_je[k])))
        nicht0 = [(k, sorted(v)) for k, v in stand_je.items() if v - {"0"}][:10]
        aus.append(f"   v2 gegen alt (gleiche Stelle/Stunde): gleich {gleich}, ungleich {ungleich}; Beispiele {bsp}")
        aus.append(f"   Stunden mit stand != 0 im alten Format: {nicht0}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## altes Format: {e!r}")
    # Anleitung (PDF) nach Stichworten
    try:
        pdf = hole("https://www.mobidata-bw.de/data/Tutorial_EcoCounter-Daten.pdf", 120)
        speichere("mobidata_anleitung.pdf", pdf, packen=False)
        aus.append(f"## Anleitung: {len(pdf)} B gespeichert")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## Anleitung: {e!r}")


# ------------------------------------------------------------------------------- Aachen
def aachen(aus):
    p = json.loads(hole("https://offenedaten.aachen.de/api/3/action/package_show?id=radzaehlstellen-der-stadt-aachen", 60))["result"]
    aus.append(f"## {p['title']} | {p.get('license_id')} | {p.get('license_title')} | geändert {p.get('metadata_modified')}")
    aus.append("   " + (p.get("notes") or "")[:1500].replace("\n", " "))
    for r in p["resources"]:
        aus.append(f"   - {r.get('name')} | {r.get('format')} | {r.get('url')} | {r.get('last_modified') or r.get('created')}")
        try:
            d = hole(r["url"], 300)
            name = r["url"].rstrip("/").split("/")[-1] or r["id"]
            speichere(f"aachen_{name}", d, packen=not name.lower().endswith(".pdf"))
            aus.append(f"     gespeichert {len(d)} B")
        except Exception as e:  # noqa: BLE001
            aus.append(f"     {e!r}")


# ------------------------------------------------------------------------------- Berlin
def berlin(aus):
    url = ("https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/weitere-radinfrastruktur/"
           "zaehlstellen-und-fahrradbarometer/gesamtdatei-stundenwerte.xlsx")
    d = hole(url, 300)
    speichere("berlin_gesamtdatei-stundenwerte.xlsx", d, packen=False)
    aus.append(f"## {url}: {len(d)} B gespeichert")


# ------------------------------------------------------------------------------ München
def muenchen(aus):
    basis = "https://opendata.muenchen.de/api/3/action/"
    r = json.loads(hole(basis + "package_search?" + urllib.parse.urlencode({"q": "raddauerzählstellen", "rows": 100}), 60))["result"]
    pakete = []
    for p in r["results"]:
        pakete.append({"name": p["name"], "title": p["title"], "license_id": p.get("license_id"),
                       "modified": p.get("metadata_modified"),
                       "resources": [{"name": x.get("name"), "url": x.get("url"), "format": x.get("format")} for x in p["resources"]]})
    (DATEN / "muenchen_pakete.json").write_text(json.dumps(pakete, ensure_ascii=False, indent=1), encoding="utf-8")
    aus.append(f"## {r['count']} Pakete: " + " | ".join(f"{p['title']} ({len(p['resources'])})" for p in pakete))
    alle = [x for p in pakete for x in p["resources"]]
    for muster in ("rad_2025_10_15min", "rad_2026_07_15min", "rad_2026_03_15min", "rad_2008_15min", "rad_2016_15min",
                   "rad_2021_15min", "rad_2026_08_15min", "rad_2026_09_15min"):
        treffer = [x for x in alle if muster in (x["url"] or "")]
        if not treffer:
            aus.append(f"## {muster}: nicht gefunden")
            continue
        d = hole(treffer[0]["url"], 300)
        speichere(f"muenchen_{muster}.csv", d)
        aus.append(f"## {muster}: {len(d)} B; Kopf: {d[:300].decode('utf-8', 'replace')!r}")
    wfs = ("https://geoportal.muenchen.de/geoserver/mor_wfs/ows?service=WFS&version=1.0.0&request=GetFeature"
           "&typeName=mor_wfs:raddauerzaehlstellen&outputFormat=application/json")
    d = hole(wfs, 60)
    speichere("muenchen_wfs.json", d, packen=False)
    aus.append(f"## WFS: {len(d)} B")


# ------------------------------------------------------------------------------ Münster
def muenster(aus):
    basis = "https://opendata.stadt-muenster.de/api/3/action/"
    for q in ("Fahrradverkehr tagesaktuelle", "Zählstellen Fahrradverkehr Standorte", "Radverkehr Zählstellen"):
        try:
            r = json.loads(hole(basis + "package_search?" + urllib.parse.urlencode({"q": q, "rows": 30}), 60))["result"]
            aus.append(f"## Suche {q!r}: " + " | ".join(f"{p['title']} ({p['name']}, {p.get('license_id')})" for p in r["results"]))
            for p in r["results"]:
                for x in p["resources"]:
                    u = x.get("url") or ""
                    if any(s in u.lower() for s in (".geojson", ".json", "standort", "zaehlstellen.csv", "wfs")):
                        aus.append(f"   - {p['name']}: {x.get('name')} | {x.get('format')} | {u}")
        except Exception as e:  # noqa: BLE001
            aus.append(f"## Suche {q!r}: {e!r}")
    try:
        p = json.loads(hole(basis + "package_show?id=" + urllib.parse.quote("verkehrszählung-fahrradverkehr-tagesaktuelle-daten"), 60))["result"]
        aus.append(f"## Paket: {p['title']} | {p.get('license_id')} | {p.get('license_title')}")
        aus.append("   " + (p.get("notes") or "")[:1200].replace("\n", " "))
        for x in p["resources"]:
            aus.append(f"   - {x.get('name')} | {x.get('format')} | {x.get('url')}")
            u = x.get("url") or ""
            if any(s in u.lower() for s in (".geojson", ".json", ".csv")) and "github" not in u:
                try:
                    d = hole(u, 120)
                    speichere("muenster_" + u.rstrip("/").split("/")[-1], d)
                    aus.append(f"     gespeichert {len(d)} B: {d[:300].decode('utf-8', 'replace')!r}")
                except Exception as e:  # noqa: BLE001
                    aus.append(f"     {e!r}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## Paket: {e!r}")


if __name__ == "__main__":
    for name, f in [("kiel", kiel), ("mobidata", mobidata), ("aachen", aachen), ("berlin", berlin),
                    ("muenchen", muenchen), ("muenster", muenster)]:
        teil(name, f)
