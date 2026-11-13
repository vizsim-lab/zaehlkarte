"""Erkundung (13.11.2026), Teil 14: offene Punkte der Rad-Quellen aus dem Artefakt – Bonns
Jahresdateien und Standorte, Rostocks Radmonitore (Doppelte, Saarplatz), Düsseldorfs Jahresdateien
(Formate je Jahr, Zeitumstellung, Summenstellen), Lage der Dortmunder Zählstelle (OSM), die
Rückstellung der Uhr (enthält die eine 2-Uhr-Stunde beide Stunden?), Leipzigs doppelte Stunden,
Bochums übrige Stellen. Ergebnisse in ergebnis/rad14/<thema>.txt."""
from __future__ import annotations

import collections
import io
import json
import re
import time
import traceback
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ZIEL = Path("ergebnis/rad14")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}
ORT = "Europe/Berlin"
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 30)


def hole(url: str, grenze: int | None = None, versuche: int = 4, daten: bytes | None = None,
         kopf: dict | None = None) -> bytes:
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, data=daten, headers={**UA, **(kopf or {})})
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read() if grenze is None else r.read(grenze)
        except Exception:  # noqa: BLE001
            if i == versuche - 1:
                raise
            time.sleep(8 * (i + 1))
    raise RuntimeError("unerreichbar")


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


def rueck_tage(von: int, bis: int) -> list[date]:
    out = []
    for j in range(von, bis + 1):
        d = date(j, 10, 31)
        out.append(d - timedelta(days=(d.weekday() - 6) % 7))
    return out


def verhaeltnis(p: Protokoll, name: str, stunden: pd.DataFrame):
    """stunden: Spalten tag (date, Ortszeit), h (Ortsstunde), w (Summe der Stunde; am Rückstelltag
    die eine Zeile um 2 Uhr). Verhältnis 2 Uhr / Mittel aus 1 und 3 Uhr am Rückstelltag gegen
    andere Oktober-/November-Sonntage."""
    g = stunden.groupby(["tag", "h"]).w.sum().unstack()
    if not {1, 2, 3} <= set(g.columns):
        p(f"{name}: Stunden 1–3 fehlen")
        return
    q = g[2] / ((g[1] + g[3]) / 2)
    tage = pd.Series(g.index, index=g.index)
    sonntage = tage.map(lambda d: d.weekday() == 6 and d.month in (10, 11))
    rueck = set(rueck_tage(2012, 2026))
    am_rueck = tage.map(lambda d: d in rueck)
    p(f"{name}: 2 Uhr/Mittel(1, 3) am Rückstelltag {q[am_rueck].round(2).to_dict()} · "
      f"andere Okt./Nov.-Sonntage Median {q[sonntage & ~am_rueck].median():.2f} (n={int((sonntage & ~am_rueck).sum())})")


# ------------------------------------------------------------------ Bonn
def bonn(p):
    d = js("https://opendata.bonn.de/data.json")
    liste = d.get("dataset", [])
    for x in liste:
        if "Fahrradmess" not in (x.get("title") or ""):
            continue
        p(f"\n# {x.get('title')} | {x.get('license')} | geändert {x.get('modified')} | {x.get('landingPage') or x.get('identifier')}")
        for y in x.get("distribution", []):
            url = y.get("downloadURL") or y.get("accessURL")
            p(f"  - {y.get('title')} | {url}")
            if not url:
                continue
            try:
                b = hole(url)
            except Exception as e:  # noqa: BLE001
                p(f"    ! {e!r}")
                continue
            t = text(b)
            zz = t.rstrip("\n").split("\n")
            p(f"    {len(b)} Bytes, {len(zz)} Zeilen; Kopf: {zz[0][:600]}")
            for z in zz[1:4]:
                p("     |", z[:300])
            p("     … |", " || ".join(z[:200] for z in zz[-2:]))
            # Zeilen je Tag und an den Tagen der Zeitumstellung
            tage = collections.Counter()
            for z in zz[1:]:
                m = re.match(r"\s*\"?(\d{1,2}\.\d{1,2}\.\d{4}|\d{4}-\d{2}-\d{2})", z)
                if m:
                    tage[m.group(1)] += 1
            if tage:
                p(f"    Zeilen je Tag: {dict(collections.Counter(tage.values()).most_common(6))}")
                for k, n in tage.items():
                    if n not in (24, 96) and any(s in k for s in ("03.", "10.", "-03-", "-10-")):
                        p(f"    {k}: {n} Zeilen")
    for url in ("https://stadtplan.bonn.de/geojson?Thema=22640", "https://stadtplan.bonn.de/csv?OD=4285"):
        try:
            t = text(hole(url))
            p(f"\n{url}: {len(t)} Zeichen")
            p(t[:6000])
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")


# ------------------------------------------------------------------ Rostock
def rostock(p):
    t = text(hole("https://geo.sv.rostock.de/download/opendata/radmonitore/radmonitore_standorte.json"))
    g = json.loads(t)
    for f in g["features"]:
        p("Standort:", json.dumps(f["properties"], ensure_ascii=False), f["geometry"]["coordinates"])
    df = pd.read_csv(io.BytesIO(hole("https://geo.sv.rostock.de/download/opendata/radmonitore/radmonitore_daten.csv")),
                     dtype=str, keep_default_na=False)
    p(f"Daten: {df.shape}")
    df["t"] = pd.to_datetime(df.zeitpunkt.str.replace("/", "-") + ":00", utc=True, errors="coerce", format="ISO8601")
    p("unlesbar:", int(df.t.isna().sum()), "Beispiele Zeit:", df.zeitpunkt.head(3).tolist(),
      "Versätze:", df.zeitpunkt.str[-3:].value_counts().to_dict())
    p("Minuten:", df.t.dt.minute.value_counts().to_dict())
    df["w"] = pd.to_numeric(df.summe, errors="coerce")
    p("Werte leer/negativ:", int(df.w.isna().sum()), int((df.w < 0).sum()))
    dup = df.duplicated(["standort_id", "t"], keep=False)
    p("Doppelte (Stelle, Zeit):", int(dup.sum()))
    if dup.any():
        p(df[dup].sort_values(["standort_id", "t"]).head(12).to_string())
    df["tag"] = df.t.dt.tz_convert(ORT).dt.date
    df["h"] = df.t.dt.tz_convert(ORT).dt.hour
    for sid, x in df.groupby("standort_id"):
        n = x.groupby("tag").size()
        s = x.groupby("tag").w.sum()
        p(f"{sid}: {len(x)} Zeilen, {x.t.min()} – {x.t.max()}, Viertelstunden je Tag {dict(n.value_counts().sort_index().tail(8))},"
          f" Tage ≥ 92 mit Summe 0: {int(((n >= 92) & (s == 0)).sum())}, Tagesmittel {s[n >= 92].mean():.0f}")
    # Saarplatz und Graal-Müritz: Tagessummen nebeneinander
    tag = df[df.groupby(["standort_id", "tag"]).t.transform("size") >= 92].groupby(["tag", "standort_id"]).w.sum().unstack()
    for a, b in (("300041920", "300066029"), ("100037010", "100037011"), ("100037011", "100037012"),
                 ("300026702", "300026703")):
        if a in tag and b in tag:
            beide = tag[[a, b]].dropna()
            p(f"Vergleich {a}/{b}: {len(beide)} gemeinsame Tage; gleich {int((beide[a] == beide[b]).sum())}; "
              f"Korrelation {beide[a].corr(beide[b]):.3f}; Mittel {beide[a].mean():.0f} / {beide[b].mean():.0f}")
            p("   letzte:", beide.tail(5).to_dict())
    # Rückstellung: eine Stunde zweimal (zwei Versätze) oder einmal?
    m = df.zeitpunkt.str.startswith(("2025/10/26 02", "2024/10/27 02"))
    p("Rückstellung 2 Uhr:", df[m].groupby(["standort_id", df.zeitpunkt.str[:10], df.zeitpunkt.str[-3:]]).size().head(12).to_dict())
    m = df.zeitpunkt.str.startswith(("2026/03/29 02", "2025/03/30 02"))
    p("Sommerzeit 2 Uhr (gibt es nicht):", int(m.sum()))


# ------------------------------------------------------------------ Düsseldorf
def duesseldorf(p):
    pakete = {}
    r = js("https://open.nrw/api/3/action/package_search?q=" + urllib.parse.quote("Wetterabhängige Jahresübersicht Dauerzählstellen Radverkehr") + "&rows=40")["result"]
    for x in r["results"]:
        m = re.search(r"radverkehr-(\d{4})-d$", x["name"])
        if m:
            pakete[int(m.group(1))] = x
    p("Jahrespakete:", sorted(pakete), {j: x.get("license_id") for j, x in sorted(pakete.items())})
    for url in ("https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_2.csv",
                "https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_1.geojson"):
        try:
            t = text(hole(url, versuche=6))
            p(f"\n{url}:\n{t[:8000]}")
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")
    reihen = {}
    for jahr in sorted(pakete):
        x = pakete[jahr]
        csvs = [y for y in x["resources"] if y["url"].lower().endswith(".csv")]
        lz = collections.Counter(y.get("license") or "" for y in csvs)
        p(f"\n## {jahr}: {len(csvs)} CSV, Lizenzen {dict(lz)}")
        for y in csvs:
            name = y.get("name") or ""
            try:
                t = text(hole(y["url"], versuche=6))
            except Exception as e:  # noqa: BLE001
                p(f"  ! {name}: {e!r}")
                continue
            time.sleep(1.5)
            zz = t.rstrip("\n").split("\n")
            kopf = zz[0]
            werte = [z.split(";") for z in zz[1:]]
            leer = sum(1 for z in werte if len(z) > 1 and z[1].strip() == "")
            p(f"  {name} [{(y.get('license') or '').rsplit('/', 2)[-2]}] {len(zz) - 1} Zeilen, Kopf {kopf[:160]!r}, erste {zz[1][:50]!r}, leer {leer}")
            reihen[(jahr, name)] = (kopf, werte)
    # Zeit je Jahr: Zeilen am Tag der Sommerzeit und der Rückstellung (Bilker Allee)
    for (jahr, name), (kopf, werte) in reihen.items():
        if "Bilker" not in name:
            continue
        for d in [*rueck_tage(jahr, jahr)]:
            s = d.strftime("%d.%m.%Y"), d.strftime("%d-%m-%Y")
            tag = [";".join(z[:4]) for z in werte if z and z[0].startswith(s)]
            p(f"  {jahr} {name[:40]} Rückstelltag {d}: {len(tag)} Zeilen {tag[:4]}")
        so = date(jahr, 3, 31) - timedelta(days=(date(jahr, 3, 31).weekday() - 6) % 7)
        s = so.strftime("%d.%m.%Y"), so.strftime("%d-%m-%Y")
        tag = [";".join(z[:4]) for z in werte if z and z[0].startswith(s)]
        p(f"  {jahr} {name[:40]} Sommerzeit {so}: {len(tag)} Zeilen {tag[1:4]}")
    # Tagesgang im Juni (Werktage): Spitzenstunde je Jahr – Ortszeit oder Winterzeit?
    for (jahr, name), (kopf, werte) in reihen.items():
        if "Bilker" not in name and "Christoph" not in name:
            continue
        je_h = collections.defaultdict(list)
        for z in werte:
            try:
                if "." in z[0][:6] and len(z) > 2 and re.match(r"\d", z[1]):  # datum;stunde;anzahl
                    d = pd.Timestamp(pd.to_datetime(z[0], dayfirst=True))
                    h, w = int(z[1].split(":")[0]), z[2]
                else:
                    d = pd.Timestamp(pd.to_datetime(z[0], dayfirst=True))
                    h, w = d.hour, z[1]
                if d.month == 6 and d.weekday() < 5 and w.strip():
                    je_h[h].append(float(w.replace(",", ".")))
            except Exception:  # noqa: BLE001
                continue
        mittel = {h: round(sum(v) / len(v), 1) for h, v in sorted(je_h.items()) if v}
        if mittel:
            p(f"  Juni-Werktage {jahr} {name[:50]}: Spitze {max(mittel, key=mittel.get)} Uhr, 6–9 Uhr {[mittel.get(h) for h in range(5, 10)]}, 16–19 Uhr {[mittel.get(h) for h in range(15, 20)]}")
    # Summenstellen 2025: Tagessummen der Dateien nebeneinander
    tage = {}
    for (jahr, name), (kopf, werte) in reihen.items():
        if jahr != 2025:
            continue
        s = collections.Counter()
        for z in werte:
            if len(z) >= 3:
                try:
                    s[z[0][:10]] += sum(int(v) for v in z[1:3] if v.strip())
                except ValueError:
                    continue
        tage[name[:45]] = s
    namen = sorted(tage)
    p("\n2025 Stellen:", namen)
    df = pd.DataFrame({k: pd.Series(v) for k, v in tage.items()})
    p(df.sum().to_string())
    for a in namen:
        for b in namen:
            for c in namen:
                if a < b and c not in (a, b) and df[[a, b, c]].dropna().shape[0] > 30:
                    x = df[[a, b, c]].dropna()
                    if ((x[a] + x[b] - x[c]).abs() <= 2).mean() > 0.9:
                        p(f"  Summe? {a} + {b} ≈ {c} an {((x[a] + x[b] - x[c]).abs() <= 2).mean():.0%} der Tage")


# ------------------------------------------------------------------ OSM: Dortmund (Lage)
def osm(p):
    for name, lat, lon in (("Dortmund Schnettkerbrücke", 51.4977, 7.4350), ("Essen Huyssenallee", 51.4466, 7.0099),
                           ("Essen Grugatrasse", 51.4266, 7.0382)):
        q = (f'[out:json][timeout:60];(node(around:1500,{lat},{lon})["man_made"="monitoring_station"];'
             f'node(around:1500,{lat},{lon})["monitoring:bicycle"];node(around:1500,{lat},{lon})["traffic_counter"];);out;')
        for basis in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
            try:
                d = js(basis, daten=urllib.parse.urlencode({"data": q}).encode(), kopf={"Content-Type": "application/x-www-form-urlencoded"})
                p(f"{name}: {len(d.get('elements', []))} Knoten")
                for e in d.get("elements", []):
                    p("   ", e.get("id"), e.get("lat"), e.get("lon"), json.dumps(e.get("tags", {}), ensure_ascii=False)[:400])
                break
            except Exception as e:  # noqa: BLE001
                p(f"! {name} {basis}: {e!r}")


# ------------------------------------------------------------------ Rückstellung: eine 2-Uhr-Stunde mit beiden?
def rueckstellung(p):
    # Würzburg (UTC; am Rückstelltag fehlt 0 Uhr UTC)
    for basis, ds, sel, kanal in (("https://opendata.wuerzburg.de", "fahrrad-zaehlung-daten", "id,date,counts,status", None),
                                  ("https://opendata.rhein-kreis-neuss.de", "eco-counter-data", "id,date,counts,status,channel_id", "channel_id")):
        url = (f"{basis}/api/explore/v2.1/catalog/datasets/{ds}/exports/csv?select={urllib.parse.quote(sel)}"
               f"&where={urllib.parse.quote('date>=date' + chr(39) + '2016-09-01' + chr(39))}&delimiter=%3B&timezone=UTC")
        df = pd.read_csv(io.BytesIO(hole(url)), sep=";", dtype=str, keep_default_na=False)
        df["t"] = pd.to_datetime(df.date, utc=True)
        df["w"] = pd.to_numeric(df.counts, errors="coerce")
        df = df[df.w.notna() & (df.t.dt.month.isin([10, 11]))]
        lok = df.t.dt.tz_convert(ORT)
        df["tag"], df["h"] = lok.dt.date, lok.dt.hour
        for sid, x in df.groupby("id"):
            verhaeltnis(p, f"{ds} {sid}", x[["tag", "h", "w"]])
    # Essen (Ortszeit, Quartal 4)
    pk = js("https://open.nrw/api/3/action/package_show?id=radverkehrszahlungen-e")["result"]
    zeilen = []
    for r in pk["resources"]:
        if re.search(r"Q4", r.get("name") or "") and "dl-by-de" in (r.get("license") or ""):
            t = text(hole(r["url"]))
            sep = "\t" if "\t" in t.split("\n")[0] else ";"
            for z in t.split("\n")[1:]:
                f = z.split(sep)
                if len(f) >= 5 and re.match(r"\d{2}\.\d{2}\.\d{4} \d{2}:", f[0]):
                    d = pd.to_datetime(f[0][:10], dayfirst=True).date()
                    for i, v in enumerate(f[1:5]):
                        if v.strip():
                            zeilen.append((i // 2, d, int(f[0][11:13]), int(float(v))))
    df = pd.DataFrame(zeilen, columns=["s", "tag", "h", "w"])
    for s, x in df.groupby("s"):
        verhaeltnis(p, f"Essen Stelle {s}", x[["tag", "h", "w"]])
    # Dortmund (15 Minuten, Versatz im Text)
    url = ("https://open-data.dortmund.de/api/explore/v2.1/catalog/datasets/fb61-dauerzaehlstelle-radverkehr-schnettkerbruecke/exports/csv?"
           "select=zeitpunkt_utc,radfahrer&delimiter=%3B&timezone=UTC")
    df = pd.read_csv(io.BytesIO(hole(url)), sep=";", dtype=str, keep_default_na=False)
    df["w"] = pd.to_numeric(df.radfahrer, errors="coerce")
    df = df[df.w.notna()]
    df["tag"] = pd.to_datetime(df.zeitpunkt_utc.str[:10]).dt.date
    df["h"] = df.zeitpunkt_utc.str[11:13].astype(int)
    df = df[pd.to_datetime(df.zeitpunkt_utc.str[:10]).dt.month.isin([10, 11])]
    verhaeltnis(p, "Dortmund (Wanduhr)", df[["tag", "h", "w"]])


# ------------------------------------------------------------------ Leipzig: doppelte Stunden
def leipzig(p):
    w = ("https://geodienste.leipzig.de/l3/OpenData/wfs?service=WFS&version=2.0.0&request=GetFeature&typeName="
         "OpenData%3Aradverkehr_dauerzaehlstelle_anzahl_stunde_zeitreihe&outputFormat=csv")
    df = pd.read_csv(io.BytesIO(hole(w)), dtype=str, keep_default_na=False)
    dup = df.duplicated(["stationid", "phenomenontime"], keep=False)
    p(f"{df.shape}; doppelte (Stelle, Zeit): {int(dup.sum())}")
    p(df[dup].sort_values(["stationid", "phenomenontime", "objectid"])[["stationid", "phenomenontime", "count", "objectid", "fme_tstamp"]].to_string())
    df["oid"] = df.objectid.astype(int)
    folge = df.sort_values("oid").groupby("stationid").phenomenontime.apply(lambda s: bool((s.values[1:] >= s.values[:-1]).all()))
    p("objectid-Reihenfolge = Zeitreihenfolge je Stelle:", folge.value_counts().to_dict())
    p("Stellen:", df.stationid.nunique(), "Zeiten:", df.phenomenontime.min(), df.phenomenontime.max())


# ------------------------------------------------------------------ Bochum: übrige Stellen
def bochum(p):
    proj = urllib.parse.quote("StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter", safe="")
    api = f"https://gitlab.opencode.de/api/v4/projects/{proj}"
    for nm in ("wittener_strasse", "universitaetsstrasse", "springorumtrasse", "springorumtrasse_sued", "lothringentrasse"):
        pfad = f"data/{nm}/bochum_ecocounter_{nm}.csv"
        try:
            df = pd.read_csv(io.BytesIO(hole(f"{api}/repository/files/{urllib.parse.quote(pfad, safe='')}/raw?ref=main")),
                             dtype=str, keep_default_na=False)
        except Exception as e:  # noqa: BLE001
            p(f"! {pfad}: {e!r}")
            continue
        df["t"] = pd.to_datetime(df.timestamp_utc, utc=True, errors="coerce")
        rad = [c for c in df.columns if c.startswith("radfahrende")]
        voll = df[rad].ne("").all(axis=1)
        tag = df.t.dt.tz_convert(ORT).dt.date
        n = df[voll].groupby(tag[voll]).size()
        p(f"{nm}: {df.shape}, {df.t.min()} – {df.t.max()}, Spalten {df.columns.tolist()}, Viertelstunden mit beiden Rad-Richtungen je Tag {dict(n.value_counts().sort_index().tail(6))}, Doppelte {int(df.duplicated(['t']).sum())}")
        je_jahr = df[voll].assign(j=df.t.dt.year).groupby("j")[rad].apply(lambda x: x.apply(pd.to_numeric).sum().to_dict())
        p("   je Jahr:", je_jahr.to_dict())
    for nm in ("metadata", "docs"):
        try:
            baum = js(f"{api}/repository/tree?path={nm}&per_page=100")
            p(f"{nm}/:", [b["path"] for b in baum])
            for b in baum:
                if b["path"].endswith((".json", ".md")) and b["type"] == "blob":
                    t = text(hole(f"{api}/repository/files/{urllib.parse.quote(b['path'], safe='')}/raw?ref=main"))
                    p(f"--- {b['path']} ---\n{t[:5000]}")
        except Exception as e:  # noqa: BLE001
            p(f"! {nm}: {e!r}")


for name, f in [("bonn", bonn), ("rostock", rostock), ("osm", osm), ("rueckstellung", rueckstellung),
                ("leipzig", leipzig), ("bochum", bochum), ("duesseldorf", duesseldorf)]:
    lauf(name, f)
