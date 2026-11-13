"""Erkundung (13.11.2026), Teil 13: die Rad-Quellen des Artefakts „Offene Radzähldaten“, die in die
Karte sollen, im Detail – Vollständigkeit je Stunde, Zeitumstellung, Kanäle, Status, Nullen,
Lizenz je Ressource. Dazu die offenen Fragen: wo Bonns Dateien liegen, Rostocks Datendatei,
Düsseldorfs Jahresdateien, Kölns ältere Jahre, Bochums Lizenz im Katalog, Kiels altes Angebot,
Konstanz' eigene Jahres-CSV. Ergebnisse in ergebnis/rad13/<quelle>.txt."""
from __future__ import annotations

import collections
import io
import json
import re
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

ZIEL = Path("ergebnis/rad13")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}
ORT = "Europe/Berlin"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)


def hole(url: str, grenze: int | None = 600_000_000, daten: bytes | None = None, kopf: dict | None = None) -> bytes:
    req = urllib.request.Request(url, data=daten, headers={**UA, **(kopf or {})})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read() if grenze is None else r.read(grenze)


def js(url: str, **kw):
    return json.loads(hole(url, **kw).decode("utf-8"))


def text(b: bytes) -> str:
    for kod in ("utf-8-sig", "cp1252"):
        try:
            return b.decode(kod).replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1")


class Protokoll:
    def __init__(self, name: str):
        self.name = name
        self.z: list[str] = []

    def __call__(self, *teile):
        self.z.append(" ".join(str(t) for t in teile))

    def schreibe(self):
        (ZIEL / f"{self.name}.txt").write_text("\n".join(self.z) + "\n", encoding="utf-8")
        print(f"== {self.name}: {len(self.z)} Zeilen", flush=True)


def lauf(name, f):
    p = Protokoll(name)
    try:
        f(p)
    except Exception:  # noqa: BLE001
        p("FEHLER:", traceback.format_exc()[-3000:])
    p.schreibe()


def zeilen(p: Protokoll, t: str, n: int = 6, breite: int = 400):
    zz = t.rstrip("\n").split("\n")
    p(f"    {len(zz)} Zeilen; erste {n}:")
    for z in zz[:n]:
        p("     |", z[:breite])
    p("    letzte:", " || ".join(z[:breite] for z in zz[-3:]))
    return zz


def probe(p: Protokoll, url: str, n: int = 6, grenze: int = 5_000_000):
    try:
        b = hole(url, grenze)
    except Exception as e:  # noqa: BLE001
        p(f"  ! {url}: {e!r}")
        return None
    p(f"  > {url}: {len(b)} Bytes")
    if b[:2] == b"PK":
        p("    (ZIP/XLSX – nicht weiter gelesen)")
        return None
    t = text(b)
    if t.lstrip().startswith(("{", "[")):
        p("    JSON:", t[:2500].replace("\n", " "))
        return t
    zeilen(p, t, n)
    return t


def ckan_paket(p: Protokoll, basis: str, paket: str, notiz: int = 4000):
    r = js(f"{basis}/api/3/action/package_show?id={urllib.parse.quote(paket)}")["result"]
    if isinstance(r, list):
        r = r[0]
    p(f"\n# Paket {r.get('name')}: {r.get('title')}")
    p(f"  Lizenz: {r.get('license_id')} / {r.get('license_title')} / {r.get('license_url')}")
    p(f"  Herausgeber: {(r.get('organization') or {}).get('title')} · geändert {r.get('metadata_modified')}")
    p("  Beschreibung:", (r.get("notes") or "").replace("\n", " ")[:notiz])
    for ex in r.get("extras", []):
        p(f"  extra {ex.get('key')}: {str(ex.get('value'))[:300]}")
    for x in r.get("resources", []):
        p(f"   - {x.get('name')} | {x.get('format')} | {x.get('url')} | Lizenz {x.get('license') or ''}")
    return r


def ods_export(basis: str, ds: str, select: str) -> pd.DataFrame:
    url = (f"{basis}/api/explore/v2.1/catalog/datasets/{ds}/exports/csv?select={urllib.parse.quote(select)}"
           "&delimiter=%3B&timezone=UTC")
    b = hole(url, None)
    return pd.read_csv(io.BytesIO(b), sep=";", dtype=str, keep_default_na=False)


def ortstag(t: pd.Series) -> pd.Series:
    return t.dt.tz_convert(ORT).dt.date


def verteilung(s: pd.Series) -> dict:
    return {int(k): int(v) for k, v in s.value_counts().sort_index().items()}


# ------------------------------------------------------------------ Würzburg (Eco-Counter, UTC-Stunden)
def wuerzburg(p):
    basis = "https://opendata.wuerzburg.de"
    r = js(f"{basis}/api/explore/v2.1/catalog/datasets/bicycle_counter_sites/records?limit=100")
    p(f"Zählstellen: {r.get('total_count')}")
    for x in r["results"]:
        p("  ", json.dumps({k: x.get(k) for k in ("id", "name", "description", "location", "firstdata", "lastdata",
                                                  "granularity", "travelmodes", "directional", "sens")}, ensure_ascii=False))
    df = ods_export(basis, "fahrrad-zaehlung-daten", "id,date,counts,status,name")
    p(f"Daten: {df.shape}, Spalten {df.columns.tolist()}")
    p(df.head(3).to_string())
    p("Status:", df.status.value_counts().to_dict())
    df["t"] = pd.to_datetime(df.date, utc=True)
    p("Minuten:", df.t.dt.minute.value_counts().to_dict())
    dup = df.duplicated(["id", "t"], keep=False)
    p("Doppelte (id, Zeit):", int(dup.sum()))
    if dup.any():
        p(df[dup].sort_values(["id", "t"]).head(16).to_string())
        gl = df[dup].groupby(["id", "t"]).counts.nunique()
        p("   davon mit verschiedenen Werten:", int((gl > 1).sum()))
    df["c"] = pd.to_numeric(df.counts, errors="coerce")
    p("leere counts:", int(df.c.isna().sum()), "negative:", int((df.c < 0).sum()))
    df["tag"] = ortstag(df.t)
    for sid, g in df.groupby("id"):
        n = g.groupby("tag").size()
        s = g.groupby("tag").c.sum()
        p(f"Stelle {sid} {g['name'].iloc[0]}: {len(g)} Zeilen, {g.t.min()} – {g.t.max()}, {len(n)} Ortstage;"
          f" Stunden je Ortstag {verteilung(n)}")
        p(f"   Status {g.status.value_counts().to_dict()}; Nullstunden {int((g.c == 0).sum())};"
          f" Tage mit 24 Stunden und Summe 0: {int(((n >= 23) & (s == 0)).sum())}")
        # Jahre mit Daten
        p("   je Jahr:", g.t.dt.year.value_counts().sort_index().to_dict())
    # Rückstelltag 2025-10-26 an einer Stelle
    m = (df.t >= "2025-10-25T22:00:00Z") & (df.t <= "2025-10-26T04:00:00Z")
    p("Rückstellung 2025 (UTC):")
    p(df[m].sort_values(["id", "t"])[["id", "date", "counts", "status"]].head(30).to_string())


# ------------------------------------------------------------------ Rhein-Kreis Neuss (Eco-Counter je Kanal)
def neuss(p):
    basis = "https://opendata.rhein-kreis-neuss.de"
    df = ods_export(basis, "eco-counter-data", "id,date,counts,status,channel_id,counter_name")
    p(f"Daten: {df.shape}")
    p(df.head(3).to_string())
    p("Status:", df.status.value_counts().to_dict())
    df["t"] = pd.to_datetime(df.date, utc=True)
    p("Minuten:", df.t.dt.minute.value_counts().to_dict())
    dup = df.duplicated(["channel_id", "t"], keep=False)
    p("Doppelte (Kanal, Zeit):", int(dup.sum()))
    if dup.any():
        p(df[dup].sort_values(["channel_id", "t"]).head(12).to_string())
    df["c"] = pd.to_numeric(df.counts, errors="coerce")
    p("leere counts:", int(df.c.isna().sum()), "Nullen:", int((df.c == 0).sum()))
    df["tag"] = ortstag(df.t)
    for (sid, name), g in df.groupby(["id", "counter_name"]):
        kan = sorted(g.channel_id.unique())
        p(f"Stelle {sid} {name}: Kanäle {kan}, {g.t.min()} – {g.t.max()}")
        for k, gk in g.groupby("channel_id"):
            n = gk.groupby("tag").size()
            p(f"   Kanal {k}: {len(gk)} Zeilen, {gk.t.min()} – {gk.t.max()}, {len(n)} Tage, Stunden je Tag {verteilung(n)};"
              f" Nullen {int((gk.c == 0).sum())}")
        je = g.groupby(["tag", "channel_id"]).size().unstack()
        voll = (je.notna().all(axis=1) & (je.min(axis=1) >= 23)).sum()
        p(f"   Tage, an denen alle Kanäle ≥ 23 Stunden haben: {int(voll)} von {len(je)}")
        p("   je Jahr (Zeilen):", g.t.dt.year.value_counts().sort_index().to_dict())
    for sid in sorted(df.id.unique()):
        try:
            r = js(f"{basis}/api/explore/v2.1/catalog/datasets/eco-counter-data/records?limit=1&where=id%3D%22{sid}%22")
            x = r["results"][0]
            p(f"Lage {sid}: {x.get('coordinates')} {x.get('counter_name')}")
        except Exception as e:  # noqa: BLE001
            p(f"! Lage {sid}: {e!r}")
    m = (df.t >= "2025-10-25T22:00:00Z") & (df.t <= "2025-10-26T04:00:00Z")
    p("Rückstellung 2025 (UTC):")
    p(df[m].sort_values(["channel_id", "t"])[["channel_id", "date", "counts", "status"]].head(24).to_string())


# ------------------------------------------------------------------ Dortmund (15 Minuten, Ortszeit mit Versatz)
def dortmund(p):
    basis = "https://open-data.dortmund.de"
    df = ods_export(basis, "fb61-dauerzaehlstelle-radverkehr-schnettkerbruecke",
                    "zeitpunkt,zeitpunkt_utc,radfahrer,aus_fahrtrichtung_tu,in_fahrtrichtung_tu,kommune")
    p(f"Daten: {df.shape}")
    p(df.head(4).to_string())
    p("Versatz in zeitpunkt_utc:", df.zeitpunkt_utc.str[-6:].value_counts().to_dict())
    t = pd.to_datetime(df.zeitpunkt_utc, utc=True, errors="coerce")
    p("unlesbare zeitpunkt_utc:", int(t.isna().sum()))
    df["t"] = t
    p("Minuten:", df.t.dt.minute.value_counts().to_dict())
    dup = df.duplicated(["t"], keep=False)
    p("Doppelte Zeitpunkte:", int(dup.sum()))
    if dup.any():
        p(df[dup].sort_values("t").head(12).to_string())
    for sp in ("radfahrer", "aus_fahrtrichtung_tu", "in_fahrtrichtung_tu"):
        df[sp + "_n"] = pd.to_numeric(df[sp], errors="coerce")
        p(f"{sp}: leer {int(df[sp + '_n'].isna().sum())}, Nullen {int((df[sp + '_n'] == 0).sum())}")
    ab = df.radfahrer_n != df.aus_fahrtrichtung_tu_n + df.in_fahrtrichtung_tu_n
    p("radfahrer ≠ Summe der Richtungen:", int(ab.sum()))
    if ab.any():
        p(df[ab].head(8).to_string())
    df["tag"] = ortstag(df.t)
    n = df.groupby("tag").size()
    p("Viertelstunden je Ortstag:", verteilung(n))
    p("Tage mit weniger als 92:", [str(x) for x in n[n < 92].index[:40]])
    for von, bis in (("2025-10-25T23:00:00Z", "2025-10-26T03:00:00Z"), ("2026-03-29T00:00:00Z", "2026-03-29T02:30:00Z"),
                     ("2026-10-24T23:00:00Z", "2026-10-25T03:00:00Z")):
        m = (df.t >= von) & (df.t <= bis)
        p(f"Zeitumstellung {von}–{bis}:")
        p(df[m].sort_values("t")[["zeitpunkt", "zeitpunkt_utc", "radfahrer", "aus_fahrtrichtung_tu", "in_fahrtrichtung_tu"]].to_string())
    p("je Jahr:", df.t.dt.year.value_counts().sort_index().to_dict())


# ------------------------------------------------------------------ Essen (Quartals-CSV, Stunden je Richtung)
def essen(p):
    pk = ckan_paket(p, "https://open.nrw", "radverkehrszahlungen-e", notiz=3000)
    quartal, kumuliert = [], []
    for r in pk["resources"]:
        lz = r.get("license") or ""
        name = (r.get("name") or "").strip()
        ziel = kumuliert if "umuliert" in name else quartal
        ziel.append((name, r["url"], lz))
    p(f"\nQuartale: {len(quartal)}, kumuliert: {len(kumuliert)}")
    dfs = {}
    for name, url, lz in quartal:
        try:
            t = text(hole(url, None))
        except Exception as e:  # noqa: BLE001
            p(f"! {name}: {e!r}")
            continue
        zz = t.rstrip("\n").split("\n")
        leer = collections.Counter()
        for z in zz[1:]:
            for i, w in enumerate(z.split(";")):
                if w.strip() == "":
                    leer[i] += 1
        p(f"{name} [{lz}]: {len(zz) - 1} Zeilen, Kopf {zz[0]!r}, erste {zz[1][:40]!r}, letzte {zz[-1][:40]!r}, leer je Spalte {dict(leer)}")
        # Tage mit mehr oder weniger als 24 Zeilen (Zeitumstellung)
        je_tag = collections.Counter(z[:10] for z in zz[1:])
        for d, k in je_tag.items():
            if k != 24:
                p(f"   {d}: {k} Zeilen: {[y[:40] for y in zz if y.startswith(d)][:5]}")
        if "dl-by-de" in lz:
            rows = [z.split(";") for z in zz[1:]]
            dfs[name] = (zz[0].split(";"), rows)
    # Zuordnung der Spalten: Tagessummen der Stundenspalten gegen die kumulierte Datei
    for name, url, lz in kumuliert:
        try:
            t = text(hole(url, None))
        except Exception as e:  # noqa: BLE001
            p(f"! {name}: {e!r}")
            continue
        zz = t.rstrip("\n").split("\n")
        p(f"{name} [{lz.rsplit('/', 1)[-1]}]: {len(zz) - 1} Zeilen, Kopf {zz[0]!r}, erste {zz[1]!r}")
        jahr = re.search(r"20\d\d", name).group(0)
        kum = {z.split(";")[0][:10]: z.split(";")[1:] for z in zz[1:]}
        summen = collections.defaultdict(lambda: collections.defaultdict(int))
        for qn, (kopf, rows) in dfs.items():
            if jahr not in qn:
                continue
            for row in rows:
                d = row[0][:10]
                for i, w in enumerate(row[1:]):
                    if w.strip():
                        summen[d][i] += int(float(w.replace(",", ".")))
        for d in list(kum)[:200:20]:
            p(f"   {d}: kumuliert {kum[d]} · Stundenspalten {dict(summen.get(d, {}))}")


# ------------------------------------------------------------------ Düsseldorf (Jahresdateien je Stelle)
def duesseldorf(p):
    ckan_paket(p, "https://open.nrw", "standorte-der-dauerzahlstellen-radverkehr-in-dusseldorf-d", notiz=3000)
    probe(p, "https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_2.csv", n=30)
    probe(p, "https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_1.geojson")
    for jahr in (2025, 2024, 2023, 2021, 2020):
        try:
            pk = ckan_paket(p, "https://open.nrw", f"wetterabhangige-jahresubersicht-der-dauerzahlstellen-radverkehr-{jahr}-d", notiz=1500)
        except Exception as e:  # noqa: BLE001
            p(f"! {jahr}: {e!r}")
            continue
        lz = collections.Counter((r.get("license") or "") for r in pk["resources"])
        p(f"  Lizenzen der Ressourcen {jahr}: {dict(lz)}")
        csvs = [r for r in pk["resources"] if r["url"].lower().endswith(".csv")]
        for r in csvs[:2] + [x for x in csvs if "Mischverkehr" in x["url"]][:1]:
            t = probe(p, r["url"], n=8)
            if t:
                zz = t.rstrip("\n").split("\n")
                # Zeitumstellung: Zeilen am letzten Sonntag im Oktober
                for d in ("27.10.2024", "26.10.2025", "26.10.2023", "31.10.2021", "25.10.2020",
                          "2024-10-27", "2025-10-26", "2023-10-29", "2021-10-31", "2020-10-25"):
                    tag = [z for z in zz if d in z]
                    if tag:
                        p(f"   {d}: {len(tag)} Zeilen, z. B. {[z[:60] for z in tag[:4]]}")


# ------------------------------------------------------------------ Köln (Jahresdateien)
def koeln(p):
    for jahr, datei in ((2019, "Fahrrad_Zaehlstellen_Koeln_2019.csv"), (2020, "Fahrrad_Zaehlstellen_Koeln_2020.csv"),
                        (2016, "Fahrrad_Zaehlstellen_Koeln_2016.csv")):
        probe(p, f"https://www.offenedaten-koeln.de/sites/default/files/distribution/{datei}", n=6)
    probe(p, "https://www.offenedaten-koeln.de/sites/default/files/distribution/Radverkehr%2520f%25C3%25BCr%2520Offene%2520Daten%2520K%25C3%25B6ln%25202021.csv", n=6)
    probe(p, "https://www.offenedaten-koeln.de/sites/default/files/distribution/Radverkehr%2520f%25C3%25BCr%2520Offene%2520Daten%2520K%25C3%25B6ln%25202012.csv", n=6)


# ------------------------------------------------------------------ Bochum (GitLab, Lizenz im Katalog)
def bochum(p):
    proj = urllib.parse.quote("StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter", safe="")
    api = f"https://gitlab.opencode.de/api/v4/projects/{proj}"
    t = text(hole(f"{api}/repository/files/README.md/raw?ref=main"))
    p("--- README.md (ganz) ---")
    p(t)
    baum, seite = [], 1
    while seite < 40:
        b = js(f"{api}/repository/tree?recursive=true&per_page=100&page={seite}")
        if not b:
            break
        baum += b
        seite += 1
    oben = [x["path"] for x in baum if x["path"].count("/") <= 2 and not x["path"].endswith(".csv")]
    p(f"Baum: {len(baum)} Einträge; Verzeichnisse/Dateien oben: {oben}")
    gesamt = [x["path"] for x in baum if re.fullmatch(r"data/[^/]+/bochum_ecocounter_[^/]+\.csv", x["path"])]
    p("Gesamtdateien:", gesamt)
    for pfad in gesamt:
        try:
            df = pd.read_csv(io.BytesIO(hole(f"{api}/repository/files/{urllib.parse.quote(pfad, safe='')}/raw?ref=main", None)),
                             dtype=str, keep_default_na=False)
        except Exception as e:  # noqa: BLE001
            p(f"! {pfad}: {e!r}")
            continue
        df["t"] = pd.to_datetime(df.timestamp_utc, utc=True, errors="coerce")
        werte = [c for c in df.columns if c.startswith(("radfahrende", "passanten"))]
        voll = df[werte].ne("").any(axis=1)
        p(f"\n{pfad}: {df.shape}, Spalten {df.columns.tolist()}, {df.t.min()} – {df.t.max()}")
        p("   Minuten mit Werten:", df[voll].t.dt.minute.value_counts().to_dict(), "· ohne Werte:", df[~voll].t.dt.minute.value_counts().to_dict())
        p("   Doppelte Zeitpunkte:", int(df.duplicated(["t"]).sum()))
        for c in werte:
            x = df[c]
            komma = int(x.str.contains(r"\.[1-9]").sum())
            p(f"   {c}: leer {int((x == '').sum())}, Nullen {int((x.isin(['0', '0.0'])).sum())}, Nachkomma ≠ 0: {komma}")
        rad = [c for c in werte if c.startswith("radfahrende")]
        if len(rad) == 2:
            eins = (df[rad[0]] == "") != (df[rad[1]] == "")
            p("   Zeilen, in denen genau eine Rad-Richtung fehlt:", int(eins.sum()))
        df["tag"] = ortstag(df.t)
        n = df[voll].groupby("tag").size()
        p("   Zeilen mit Werten je Ortstag:", verteilung(n))
        m = (df.t >= "2025-10-25T23:00:00Z") & (df.t <= "2025-10-26T02:30:00Z")
        if m.any():
            p(df[m][["timestamp", "timestamp_utc"] + werte].to_string())
    # Kataloge
    try:
        r = js("https://open.nrw/api/3/action/package_show?id=bochum-radverkehr-wittener-strasse-rvr")["result"]
        p("\nopen.nrw Wittener Straße, Beschreibung ganz:", (r.get("notes") or "").replace("\n", " "))
        p("   Lizenz:", r.get("license_id"), r.get("license_title"))
    except Exception as e:  # noqa: BLE001
        p("! open.nrw:", repr(e))
    for basis in ("https://bochum.opendata.ruhr", "https://opendata.ruhr"):
        try:
            r = js(f"{basis}/api/3/action/package_search?q={urllib.parse.quote('Radverkehr Zählstelle')}&rows=40")["result"]
            p(f"\n{basis}: {r['count']} Treffer")
            for x in r["results"]:
                if "ecocounter" in json.dumps(x.get("resources", [])) or "Zählstelle" in (x.get("notes") or ""):
                    p(f"  {x.get('name')} | Lizenz {x.get('license_id')} / {x.get('license_title')} | {x.get('metadata_modified')}")
            if r["results"]:
                x = r["results"][0]
                p("  erstes Paket, ganz:", json.dumps({k: x.get(k) for k in ("name", "license_id", "license_title", "license_url", "notes", "extras")}, ensure_ascii=False)[:4000])
            break
        except Exception as e:  # noqa: BLE001
            p(f"! {basis}: {e!r}")


# ------------------------------------------------------------------ Rostock (Radmonitore)
def rostock(p):
    pk = ckan_paket(p, "https://www.opendata-hro.de", "radmonitore", notiz=3000)
    for r in pk["resources"]:
        if "daten" in r["url"] and r["url"].endswith(".csv"):
            t = text(hole(r["url"], None))
            zz = zeilen(p, t, n=12)
            kopf = zz[0].split(",")
            p("Kopf:", kopf)
            try:
                df = pd.read_csv(io.StringIO(t), dtype=str, keep_default_na=False)
                p(df.describe().to_string())
                for c in df.columns:
                    if df[c].nunique() < 40:
                        p(f"   {c}: {df[c].value_counts().head(40).to_dict()}")
                zs = [c for c in df.columns if "zeit" in c.lower() or "datum" in c.lower() or "time" in c.lower()]
                p("Zeitspalten:", zs, {c: (df[c].min(), df[c].max()) for c in zs})
            except Exception as e:  # noqa: BLE001
                p("! pandas:", repr(e))
        if "daten" in r["url"] and r["url"].endswith(".json"):
            probe(p, r["url"], grenze=4000)


# ------------------------------------------------------------------ Leipzig (Stundenwerte der letzten 31 Tage)
def leipzig(p):
    w = "https://geodienste.leipzig.de/l3/OpenData/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName=OpenData%3A{}&outputFormat=csv"
    t = text(hole(w.format("radverkehr_dauerzaehlstelle_anzahl_stunde_zeitreihe"), None))
    zeilen(p, t, n=6)
    df = pd.read_csv(io.StringIO(t), dtype=str, keep_default_na=False)
    p("Spalten:", df.columns.tolist(), df.shape)
    zf = next(c for c in df.columns if "time" in c.lower())
    p("Zeitformat-Beispiele:", df[zf].head(5).tolist(), "Endungen:", df[zf].str[-6:].value_counts().head(8).to_dict())
    df["t"] = pd.to_datetime(df[zf], utc=True, errors="coerce")
    p("unlesbare Zeiten:", int(df.t.isna().sum()), "Minuten:", df.t.dt.minute.value_counts().to_dict())
    df["c"] = pd.to_numeric(df["count"], errors="coerce")
    p("Doppelte (Stelle, Zeit):", int(df.duplicated(["stationid", zf]).sum()))
    df["tag"] = ortstag(df.t)
    for sid, g in df.groupby("stationid"):
        n = g.groupby("tag").size()
        s = g.groupby("tag").c.sum()
        p(f"{sid} {g.stationname.iloc[0]}: {len(g)} Zeilen, {g[zf].min()} – {g[zf].max()}, Stunden je Ortstag {verteilung(n)},"
          f" Nullstunden {int((g.c == 0).sum())}, Tage mit Summe 0: {int((s == 0).sum())}")
    for sid in sorted(df.stationid.unique())[:2]:
        g = df[df.stationid == sid]
        m = g[zf].str.contains("2026-10-25|2026-10-26")
        p(f"Rückstellung {sid}:")
        p(g[m].sort_values(zf)[[zf, "count"]].head(30).to_string())
    # Tageswerte gegen Stunden-Summen (Ortstag oder UTC-Tag?)
    tt = text(hole(w.format("radverkehr_dauerzaehlstelle_anzahl_tag_zeitreihe"), None))
    dt = pd.read_csv(io.StringIO(tt), dtype=str, keep_default_na=False)
    dt["c"] = pd.to_numeric(dt["count"], errors="coerce")
    tz = next(c for c in dt.columns if "time" in c.lower())
    df["utctag"] = df.t.dt.date
    orts = df.groupby(["stationid", "tag"]).c.agg(["sum", "count"])
    utc = df.groupby(["stationid", "utctag"]).c.agg(["sum", "count"])
    vergleich = collections.Counter()
    beispiele = []
    for _, z in dt.iterrows():
        try:
            d = pd.Timestamp(z[tz][:10]).date()
        except Exception:  # noqa: BLE001
            continue
        k = (z["stationid"], d)
        if k in orts.index and orts.loc[k, "count"] >= 23:
            vergleich["orts_gleich" if orts.loc[k, "sum"] == z.c else "orts_anders"] += 1
            if k in utc.index:
                vergleich["utc_gleich" if utc.loc[k, "sum"] == z.c else "utc_anders"] += 1
            if len(beispiele) < 8:
                beispiele.append((k, z.c, orts.loc[k, "sum"], utc.loc[k, "sum"] if k in utc.index else None))
    p("Tageswerte gegen Stunden:", dict(vergleich), beispiele)


# ------------------------------------------------------------------ Bonn
def bonn(p):
    for url in ("https://opendata.bonn.de/dataset/fahrradmessstellen-ergebnisse-radz%C3%A4hlungen-2025",
                "https://opendata.bonn.de/search/field_topic/verkehr-3101?query=fahrrad"):
        try:
            h = text(hole(url, 3_000_000))
            links = sorted(set(re.findall(r'href="([^"]+)"', h)))
            p(f"{url}: {len(h)} Zeichen; Links mit Daten:", [x for x in links if re.search(r"\.(csv|json|zip|xlsx)|/api/|download|resource", x, re.I)][:80])
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")
    for url in ("https://opendata.bonn.de/data.json", "https://opendata.bonn.de/api/1/metastore/schemas/dataset/items"):
        try:
            d = js(url)
            liste = d.get("dataset", d) if isinstance(d, dict) else d
            treffer = [x for x in liste if "ahrrad" in json.dumps(x, ensure_ascii=False)]
            p(f"{url}: {len(liste)} Datensätze, {len(treffer)} mit „Fahrrad“")
            for x in treffer[:30]:
                p("  ", x.get("title"), "|", x.get("license"), "|", [(y.get("title"), y.get("downloadURL") or y.get("accessURL")) for y in x.get("distribution", [])][:30])
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")
    try:
        r = js("https://open.nrw/api/3/action/package_search?q=Fahrradmessstellen&rows=50")["result"]
        p(f"open.nrw „Fahrradmessstellen“: {r['count']} Treffer")
        for x in r["results"]:
            p(f"  {x.get('name')} | {x.get('license_id')} | {(x.get('organization') or {}).get('title')} | {x.get('metadata_modified')}")
            for y in x.get("resources", [])[:12]:
                p(f"     - {y.get('name')} | {y.get('url')} | {y.get('license') or ''}")
    except Exception as e:  # noqa: BLE001
        p("! open.nrw:", repr(e))


# ------------------------------------------------------------------ Kiel (Mobilithek, altes Angebot)
def kiel(p):
    for oid in ("995322152055894016", "1046783892706476032"):
        try:
            m = js(f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{oid}")
            p(f"Angebot {oid}:", json.dumps(m, ensure_ascii=False)[:6000])
        except Exception as e:  # noqa: BLE001
            p(f"! Angebot {oid}: {e!r}")


# ------------------------------------------------------------------ Konstanz (eigene Jahres-CSV)
def konstanz(p):
    pk = ckan_paket(p, "https://offenedaten-konstanz.de", "fahrrad-dauerz-hlstellen", notiz=2000)
    csvs = [r for r in pk["resources"] if r["url"].lower().endswith(".csv")]
    for r in csvs[-2:]:
        probe(p, r["url"], n=6)


for name, f in [("wuerzburg", wuerzburg), ("neuss", neuss), ("dortmund", dortmund), ("essen", essen),
                ("leipzig", leipzig), ("bochum", bochum), ("rostock", rostock), ("duesseldorf", duesseldorf),
                ("koeln", koeln), ("bonn", bonn), ("kiel", kiel), ("konstanz", konstanz)]:
    lauf(name, f)
