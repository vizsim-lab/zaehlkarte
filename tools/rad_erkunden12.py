"""Erkundung (13.11.2026), Teil 12: die übrigen Quellen des Artefakts „Offene Radzähldaten“ –
Bonn, Leipzig, Würzburg, Rhein-Kreis Neuss, Dortmund, Essen, Düsseldorf, Köln, Bochum, Kiel (Rad),
Rostock, Jena, Augsburg, Oldenburg. Je Quelle: Metadaten (Lizenz, Ressourcen), Kopf und erste
Zeilen der Daten, Zeitraum und Auflösung. Ergebnisse in ergebnis/rad12/<quelle>.txt."""
from __future__ import annotations

import csv
import gzip
import io
import json
import traceback
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ZIEL = Path("ergebnis/rad12")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}
GRENZE = 3_000_000  # Bytes je Probe


def hole(url: str, grenze: int = GRENZE, daten: bytes | None = None, kopf: dict | None = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, data=daten, headers={**UA, **(kopf or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, dict(r.headers), r.read(grenze)


def js(url: str, **kw):
    _, _, b = hole(url, 20_000_000, **kw)
    return json.loads(b.decode("utf-8"))


class Protokoll:
    def __init__(self, name: str):
        self.name = name
        self.z: list[str] = []

    def __call__(self, *teile):
        s = " ".join(str(t) for t in teile)
        self.z.append(s)

    def schreibe(self):
        (ZIEL / f"{self.name}.txt").write_text("\n".join(self.z) + "\n", encoding="utf-8")
        print(f"== {self.name}: {len(self.z)} Zeilen")


def probe(p: Protokoll, url: str, n: int = 8):
    """Datei anfassen: Typ, Größe, Kopf und erste Zeilen (CSV/JSON/ZIP/XLSX)."""
    try:
        st, hd, b = hole(url)
    except Exception as e:  # noqa: BLE001
        p(f"  ! {url}: {e!r}")
        return
    p(f"  > {url}: HTTP {st}, {hd.get('Content-Type')}, Länge {hd.get('Content-Length')}, gelesen {len(b)}")
    if b[:2] == b"\x1f\x8b":
        try:
            b = gzip.decompress(b)
        except Exception:  # noqa: BLE001
            b = gzip.GzipFile(fileobj=io.BytesIO(b)).read(GRENZE)
    if b[:2] == b"PK":
        try:
            zf = zipfile.ZipFile(io.BytesIO(b))
            namen = zf.namelist()
            p(f"    ZIP mit {len(namen)} Dateien: {namen[:15]}")
            for nm in namen[:2]:
                if nm.lower().endswith((".csv", ".txt", ".json")):
                    zeigen(p, zf.read(nm)[:200_000], n)
            if any(x.startswith("xl/") for x in namen):
                p("    (XLSX)")
                xlsx(p, b)
        except zipfile.BadZipFile:
            p("    ZIP unvollständig (Probe abgeschnitten)")
        return
    zeigen(p, b, n)


def zeigen(p: Protokoll, b: bytes, n: int):
    for kod in ("utf-8-sig", "cp1252"):
        try:
            t = b.decode(kod)
            break
        except UnicodeDecodeError:
            continue
    t = t.replace("\r\n", "\n")
    if t.lstrip().startswith(("{", "[")):
        p("    JSON:", t[:1500].replace("\n", " "))
        return
    zeilen = t.split("\n")
    p(f"    {len(zeilen)} Zeilen in der Probe; erste {n}:")
    for z in zeilen[:n]:
        p("     |", z[:400])
    p("    letzte:", " || ".join(z[:300] for z in zeilen[-4:-1]))


def xlsx(p: Protokoll, b: bytes):
    try:
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(b), read_only=True)
        for ws in wb.worksheets[:3]:
            p(f"    Blatt {ws.title}:")
            for i, row in enumerate(ws.iter_rows(values_only=True)):
                p("     |", [str(x)[:30] for x in row[:14]])
                if i > 6:
                    break
    except Exception as e:  # noqa: BLE001
        p("    XLSX nicht lesbar:", repr(e))


def ckan(p: Protokoll, basis: str, *, paket: str | None = None, suche: str | None = None, proben: int = 3):
    try:
        if paket:
            pakete = [js(f"{basis}/api/3/action/package_show?id={urllib.parse.quote(paket)}")["result"]]
        else:
            r = js(f"{basis}/api/3/action/package_search?q={urllib.parse.quote(suche)}&rows=50")["result"]
            p(f"Suche „{suche}“: {r['count']} Treffer")
            pakete = r["results"]
    except Exception as e:  # noqa: BLE001
        p(f"! CKAN {basis} ({paket or suche}): {e!r}")
        return []
    for pk in pakete:
        p(f"\n# Paket {pk.get('name')}: {pk.get('title')}")
        p(f"  Lizenz: {pk.get('license_id')} / {pk.get('license_title')} / {pk.get('license_url')}")
        p(f"  Herausgeber: {(pk.get('organization') or {}).get('title')} · geändert {pk.get('metadata_modified')}")
        notiz = (pk.get("notes") or "").replace("\n", " ")
        p(f"  Beschreibung: {notiz[:1200]}")
        for ex in pk.get("extras", [])[:30]:
            if any(k in ex.get("key", "").lower() for k in ("licen", "lizenz", "rights", "temporal", "contact", "zeit")):
                p(f"  extra {ex['key']}: {str(ex['value'])[:200]}")
        res = pk.get("resources", [])
        p(f"  {len(res)} Ressourcen:")
        for r in res:
            p(f"   - {r.get('name')} | {r.get('format')} | {r.get('url')} | geändert {r.get('last_modified') or r.get('created')} | Lizenz {r.get('license') or ''}")
    return pakete


def ods(p: Protokoll, basis: str, ds: str, zeitfeld: str | None = None):
    url = f"{basis}/api/explore/v2.1/catalog/datasets/{ds}"
    try:
        m = js(url)
    except Exception as e:  # noqa: BLE001
        p(f"! ODS {url}: {e!r}")
        return None
    metas = m.get("metas", {}).get("default", {})
    p(f"\n# ODS {basis} {ds}: {metas.get('title')}")
    p(f"  Lizenz: {metas.get('license')} / {metas.get('license_url')} · Herausgeber {metas.get('publisher')} · geändert {metas.get('modified')} · Daten geändert {metas.get('data_processed')} · Datensätze {metas.get('records_count')}")
    p(f"  Beschreibung: {(metas.get('description') or '')[:1200]}")
    felder = m.get("fields", [])
    p("  Felder:", [(f["name"], f["type"], f.get("label")) for f in felder])
    try:
        r = js(f"{url}/records?limit=6")
        p(f"  total_count {r.get('total_count')}")
        for x in r.get("results", []):
            p("   ", json.dumps(x, ensure_ascii=False)[:700])
    except Exception as e:  # noqa: BLE001
        p(f"  ! records: {e!r}")
    zf = zeitfeld or next((f["name"] for f in felder if f["type"] in ("datetime", "date")), None)
    if zf:
        for ordnung in (zf, f"-{zf}"):
            try:
                r = js(f"{url}/records?limit=2&order_by={urllib.parse.quote(ordnung)}")
                p(f"  order_by {ordnung}:", [x.get(zf) for x in r.get("results", [])])
            except Exception as e:  # noqa: BLE001
                p(f"  ! order_by {ordnung}: {e!r}")
    return m


def lauf(name, f):
    p = Protokoll(name)
    try:
        f(p)
    except Exception:  # noqa: BLE001
        p("FEHLER:", traceback.format_exc()[-2000:])
    p.schreibe()


# ------------------------------------------------------------------ Bonn
def bonn(p):
    pk = ckan(p, "https://opendata.bonn.de", suche="Fahrradmessstellen")
    gesehen = 0
    for x in pk:
        for r in x.get("resources", []):
            if (r.get("format") or "").upper() in ("CSV", "JSON", "XLSX", "ZIP") and gesehen < 5:
                gesehen += 1
                probe(p, r["url"])


# ------------------------------------------------------------------ Leipzig
def leipzig(p):
    pk = ckan(p, "https://opendata.leipzig.de", suche="Dauerzählstellen Radverkehr")
    for x in pk:
        for r in x.get("resources", []):
            u = r.get("url") or ""
            if "GetCapabilities" in u or (r.get("format") or "").upper() in ("WFS", "CSV", "JSON", "GEOJSON"):
                probe(p, u, n=12)


# ------------------------------------------------------------------ Opendatasoft
def wuerzburg(p):
    for basis in ("https://opendata.wuerzburg.de", "https://wuerzburg.opendatasoft.com"):
        try:
            kat = js(f"{basis}/api/explore/v2.1/catalog/datasets?where=search(%22fahrrad%22)&limit=20")
            p(f"Katalog {basis}:", [(d.get("dataset_id"), d.get("metas", {}).get("default", {}).get("title")) for d in kat.get("results", [])])
        except Exception as e:  # noqa: BLE001
            p(f"! Katalog {basis}: {e!r}")
            continue
        for d in kat.get("results", []):
            ods(p, basis, d["dataset_id"])
        break


def neuss(p):
    basis = "https://opendata.rhein-kreis-neuss.de"
    for ds in ("eco-counter-sites", "eco-counter-data"):
        ods(p, basis, ds)
    ckan(p, "https://open.nrw", paket="rhein-kreis-neuss-radzahlstationen-auswertung-ne")


def dortmund(p):
    ods(p, "https://open-data.dortmund.de", "fb61-dauerzaehlstelle-radverkehr-schnettkerbruecke")


# ------------------------------------------------------------------ NRW (open.nrw)
def essen(p):
    pk = ckan(p, "https://open.nrw", paket="radverkehrszahlungen-e")
    for x in pk:
        for r in x.get("resources", [])[:3]:
            probe(p, r["url"])


def duesseldorf(p):
    pk = ckan(p, "https://open.nrw", suche="Dauerzählstellen Radverkehr Düsseldorf")
    n = 0
    for x in pk:
        if "sseldorf" not in (x.get("title") or "") and "sseldorf" not in str(x.get("organization")):
            continue
        for r in x.get("resources", []):
            if n < 3 and (r.get("format") or "").upper() in ("CSV", "XLSX", "JSON", "ZIP"):
                n += 1
                probe(p, r["url"])


def koeln(p):
    pk = ckan(p, "https://open.nrw", paket="fahrrad-verkehrsdaten-koln-2022-k")
    for x in pk:
        for r in x.get("resources", [])[:2]:
            probe(p, r["url"])


def bochum(p):
    proj = urllib.parse.quote("StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter", safe="")
    api = f"https://gitlab.opencode.de/api/v4/projects/{proj}"
    try:
        info = js(api)
        p("Projekt:", info.get("name_with_namespace"), "| Lizenz laut GitLab:", info.get("license"), "| zuletzt", info.get("last_activity_at"))
        p("Beschreibung:", (info.get("description") or "")[:800])
    except Exception as e:  # noqa: BLE001
        p("! Projekt:", repr(e))
    try:
        baum = js(f"{api}/repository/tree?recursive=true&per_page=100")
        p(f"Baum ({len(baum)} Einträge, erste 100):", [b["path"] for b in baum][:100])
        for nm in ("LICENSE", "LICENSE.md", "README.md"):
            if any(b["path"] == nm for b in baum):
                _, _, t = hole(f"{api}/repository/files/{urllib.parse.quote(nm, safe='')}/raw?ref=main")
                p(f"--- {nm} ---\n" + t.decode("utf-8", "replace")[:3000])
        daten = [b["path"] for b in baum if b["path"].lower().endswith(".csv")]
        for d in daten[:2]:
            probe(p, f"{api}/repository/files/{urllib.parse.quote(d, safe='')}/raw?ref=main")
    except Exception as e:  # noqa: BLE001
        p("! Baum:", repr(e))
    ckan(p, "https://open.nrw", suche="Bochum Radverkehr Zählstelle")


# ------------------------------------------------------------------ übrige
def kiel(p):
    for oid in ("784002906756923392",):
        try:
            m = js(f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{oid}")
            p(json.dumps(m, ensure_ascii=False)[:6000])
        except Exception as e:  # noqa: BLE001
            p(f"! Mobilithek {oid}: {e!r}")
    try:
        r = js("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search", daten=json.dumps({"searchString": "Radverkehr Kiel"}).encode(), kopf={"Content-Type": "application/json"})
        p("Suche Radverkehr Kiel:", json.dumps(r, ensure_ascii=False)[:4000])
    except Exception as e:  # noqa: BLE001
        p(f"! Suche: {e!r}")


def rostock(p):
    pk = ckan(p, "https://www.opendata-hro.de", paket="radmonitore")
    for x in pk:
        for r in x.get("resources", [])[:4]:
            probe(p, r["url"])


def jena(p):
    for suche in ("Fahrrad", "Radverkehr", "Zählstelle"):
        ckan(p, "https://wissensallmende.jena.de", suche=suche)
    for u in ("https://wissensallmende.jena.de/", "https://wissensallmende.jena.de/api/3/action/status_show"):
        probe(p, u, n=5)


def augsburg(p):
    probe(p, "https://www.augsburg.de/fileadmin/user_upload/buergerservice_rathaus/Smart_City/opendata/fahrradzaehler_augsburg-seit-start.csv", n=12)


def oldenburg(p):
    pk = ckan(p, "https://opendata.oldenburg.de", paket="radzähldaten")
    for x in pk:
        for r in x.get("resources", [])[:3]:
            probe(p, r["url"])


for name, f in [("bonn", bonn), ("leipzig", leipzig), ("wuerzburg", wuerzburg), ("neuss", neuss),
                ("dortmund", dortmund), ("essen", essen), ("duesseldorf", duesseldorf), ("koeln", koeln),
                ("bochum", bochum), ("kiel", kiel), ("rostock", rostock), ("jena", jena),
                ("augsburg", augsburg), ("oldenburg", oldenburg)]:
    lauf(name, f)
