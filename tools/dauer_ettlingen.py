"""Ettlingen (re@di): Datastore „Verkehrszählung Ettlingen – Stundenwerte pro Fahrzeugtyp und
Standort“ erkunden. Holt Metadaten und den ganzen Dump, schreibt Zusammenfassungen und kleine
Stichproben nach ergebnis/ (den Dump selbst nur gepackt und nur, wenn er klein bleibt).
Aufruf: uv run --no-project --with pandas python tools/dauer_ettlingen.py <ziel> <tmp>"""
from __future__ import annotations

import gzip
import json
import shutil
import sys
import time
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}
BASIS = "https://opendata.readi.de"
RID = "a903967d-9177-4db6-977c-267fd745a390"
PAKET = "automatisierte-verkehrszahlung-in-ettlingen"


def hole(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def js(url):
    return json.loads(hole(url))


def versuch(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return {"fehler": repr(e)[:300], "spur": traceback.format_exc()[-600:]}


def api(aktion, **p):
    return f"{BASIS}/api/3/action/{aktion}?" + urllib.parse.urlencode(p)


def main(ziel: Path, tmp: Path, lokal_dump: Path | None = None):
    ziel.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    out: dict = {}

    def sichern():
        (ziel / "ettlingen.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))

    # 1. Metadaten
    out["paket"] = versuch(lambda: js(api("package_show", id=PAKET))["result"])
    out["ressource"] = versuch(lambda: js(api("resource_show", id=RID))["result"])
    out["erste_zeilen"] = versuch(lambda: js(api("datastore_search", resource_id=RID, limit=5))["result"])
    out["sql"] = versuch(lambda: js(api("datastore_search_sql", sql=f'SELECT count(*) AS n FROM "{RID}"'))["result"])
    sichern()
    print("metadaten ok", flush=True)

    # 2. Dump (CSV) holen
    dump = lokal_dump or tmp / "ettlingen.csv"
    t0 = time.time()
    try:
        if lokal_dump:
            raise StopIteration
        req = urllib.request.Request(f"{BASIS}/datastore/dump/{RID}", headers=UA)
        with urllib.request.urlopen(req, timeout=600) as r, open(dump, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        out["dump"] = {"bytes": dump.stat().st_size, "sekunden": round(time.time() - t0)}
    except StopIteration:
        out["dump"] = {"bytes": dump.stat().st_size, "lokal": True}
    except Exception as e:  # noqa: BLE001
        out["dump"] = {"fehler": repr(e)[:300], "sekunden": round(time.time() - t0)}
        sichern()
        return
    sichern()
    print("dump ok", out["dump"], flush=True)
    gz = ziel / "ettlingen.csv.gz"
    with open(dump, "rb") as f, gzip.open(gz, "wb", compresslevel=9) as g:
        shutil.copyfileobj(f, g, 1 << 20)
    if gz.stat().st_size > 45_000_000:
        out["dump"]["gepackt_nicht_abgelegt"] = gz.stat().st_size
        gz.unlink()
    else:
        out["dump"]["gepackt"] = gz.stat().st_size
    sichern()

    # 3. Auswerten
    import pandas as pd

    df = pd.read_csv(dump, dtype=str, keep_default_na=False)
    out["spalten"] = list(df.columns)
    out["zeilen"] = len(df)
    for c in df.columns:
        werte = df[c].value_counts()
        out[f"spalte {c}"] = {"verschieden": int(werte.size), "leer": int((df[c] == "").sum()),
                              "haeufigste": werte.head(12).to_dict()}
    sichern()
    print("spalten ok", flush=True)

    ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce", format="mixed")
    out["zeit"] = {"unlesbar": int(ts.isna().sum()), "von": str(ts.min()), "bis": str(ts.max()),
                   "beispiele": df["timestamp"].head(5).tolist(),
                   "nicht_volle_stunde": int(((ts.dt.minute != 0) | (ts.dt.second != 0)).sum())}
    df["ts"] = ts
    df["yn"] = pd.to_numeric(df["y"], errors="coerce")
    out["y"] = {"unlesbar": int(df["yn"].isna().sum()), "null": int((df["yn"] == 0).sum()),
                "negativ": int((df["yn"] < 0).sum()), "nicht_ganz": int((df["yn"] % 1 != 0).sum()),
                "max": float(df["yn"].max())}
    sichern()

    schluessel = ["source", "dataset_id", "label", "sensor_id", "sid", "lane_index", "direction"]
    df["strom"] = df["dataset_id"] + "|" + df["sid"]
    stroeme = df.groupby(schluessel, dropna=False).agg(
        zeilen=("y", "size"), von=("ts", "min"), bis=("ts", "max"), lat=("latitude", "first"),
        lon=("longitude", "first"), link=("link", "first"), klassen=("series_name", lambda s: sorted(set(s))),
        stunden=("ts", "nunique")).reset_index()
    stroeme["erwartet"] = ((stroeme["bis"] - stroeme["von"]).dt.total_seconds() // 3600 + 1).astype(int)
    out["stroeme"] = stroeme.astype(str).to_dict(orient="records")
    sichern()
    print("stroeme ok", len(stroeme), flush=True)

    out["klassen"] = df.groupby(["source", "series_name", "classification"]).size().reset_index(
        name="n").astype(str).to_dict(orient="records")
    # Zeilen je Strom und Stunde (stehen alle Klassen in jeder Stunde, auch mit 0?)
    je_stunde = df.groupby(["strom", "ts"]).size()
    out["zeilen_je_stunde"] = je_stunde.groupby(level=0).value_counts().rename("n").reset_index().astype(
        str).to_dict(orient="records")
    out["doppelt"] = int(df.duplicated(["strom", "ts", "series_name"], keep=False).sum())
    dop = df[df.duplicated(["strom", "ts", "series_name"], keep=False)].sort_values(["strom", "ts"])
    out["doppelt_beispiele"] = dop.head(20).drop(columns=["ts", "yn"]).to_dict(orient="records")
    sichern()
    print("stunden ok", flush=True)

    # Stunden je Ortstag und Strom (für die Vollständigkeit): Verteilung
    lokal = df["ts"].dt.tz_convert("Europe/Berlin")
    df["tag"] = lokal.dt.date.astype(str)
    df["h"] = lokal.dt.hour
    tage = df.groupby(["strom", "tag"])["ts"].nunique()
    out["stunden_je_tag"] = tage.value_counts().sort_index().astype(int).to_dict()
    out["volle_tage_je_strom"] = (tage[tage >= 23].groupby(level=0).size()).astype(int).to_dict()
    out["tage_je_strom"] = tage.groupby(level=0).size().astype(int).to_dict()
    # Monate: Zeilen je Strom und Monat
    df["monat"] = lokal.dt.strftime("%Y-%m")
    out["monate"] = df.groupby(["strom", "monat"]).size().unstack(fill_value=0).astype(int).to_dict(orient="index")
    sichern()
    print("tage ok", flush=True)

    # Alte Kennungen gegen neue Ströme: Stundensummen je Bezeichnung und Quelle vergleichen
    summe = df.groupby(["label", "source", "ts"])["yn"].sum().unstack("source")
    out["vergleich_quellen"] = {}
    if summe.shape[1] >= 2:
        q = list(summe.columns)
        for lab, block in summe.groupby(level=0):
            b = block.dropna()
            if len(b):
                out["vergleich_quellen"][lab] = {"stunden": len(b), "summen": b.sum().to_dict(),
                                                 "beispiel": b.head(5).reset_index().astype(str).to_dict(orient="records"),
                                                 "quellen": q}
    sichern()

    # Stichproben: zwei ganze Tage aller Ströme, je ein Tag alt und neu
    for tag in ("2025-06-03", "2026-09-15", "2026-10-28"):
        s = df[df["tag"] == tag].drop(columns=["ts", "yn", "strom", "tag", "h", "monat"])
        s.to_csv(ziel / f"stichprobe_{tag}.csv", index=False)
    # Zeitumstellung (Rückstellung 25.10.2026, Umstellung 29.03.2026)
    for tag in ("2025-10-26", "2026-03-29", "2026-10-25"):
        s = df[df["tag"] == tag]
        out[f"umstellung {tag}"] = s.groupby("strom")["ts"].nunique().astype(int).to_dict()
    sichern()
    print("fertig", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]) if len(sys.argv) > 3 else None)
