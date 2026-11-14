"""Eine Dauer-Quelle mit dem Adapter eines App-Branches prüfen: holen, lesen, Kennzahlen je
Zählstelle, Jahresgrenzen und Zeitumstellung, Kartendaten nur dieser Quelle (zuerst für die VMZ
Niedersachsen, `vmz_rad`).

Läuft im Ordner `app/pipeline` des geklonten App-Branches (siehe tools/lauf.sh):
    uv run python <pfad>/tools/quelle_pruefen.py <code> <zielordner>
"""

from __future__ import annotations

import json
import sys
import tarfile
import time
from datetime import date
from pathlib import Path

import numpy as np

from zaehlkarte import abruf
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bau
from zaehlkarte.dauer import site as site_
from zaehlkarte.dauer.modell import tagessummen, umstellungen

CODE = sys.argv[1]
ziel = Path(sys.argv[2])
ziel.mkdir(parents=True, exist_ok=True)
pfade = Pfade()
out: list[str] = []


def schreib() -> None:
    (ziel / "bericht.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


t0 = time.time()
log, fehler = bau.hole(pfade, nur=[CODE])
out += ["== Abruf", *log, f"Fehler: {fehler}", f"Dauer: {time.time() - t0:.0f} s",
        *abruf.bericht()]
roh = pfade.roh / CODE
groesse = sum(p.stat().st_size for p in roh.rglob("*") if p.is_file())
out.append(f"Rohdaten: {len(list(roh.rglob('*')))} Dateien, {groesse / 1e6:.1f} MB")
if (roh / "abruf.json").exists():
    out.append((roh / "abruf.json").read_text(encoding="utf-8"))
if (roh / "metadaten.json").exists():  # Opendatasoft: Felder des Datensatzes
    meta = json.loads((roh / "metadaten.json").read_text(encoding="utf-8"))
    out.append("Felder: " + json.dumps([{k: f.get(k) for k in ("name", "type", "label")}
                                        for f in meta.get("fields") or []], ensure_ascii=False))
    m = (meta.get("metas") or {}).get("default") or {}
    out.append("Metadaten: " + json.dumps({k: m.get(k) for k in ("title", "records_count", "modified", "data_processed", "timezone", "license")}, ensure_ascii=False))
    import html
    import re
    text = html.unescape(re.sub(r"<[^>]+>", " ", m.get("description") or ""))
    out.append("Beschreibung: " + re.sub(r"\s+", " ", text).strip()[:3000])
    for k in ("publisher", "attributions", "keyword", "theme", "territory", "geographic_reference"):
        if m.get(k):
            out.append(f"{k}: {m.get(k)}")
for p in sorted(roh.rglob("*.csv"))[:3]:
    with p.open(encoding="utf-8", errors="replace") as f:
        out.append(f"Kopf {p.name}: " + " | ".join(next(f, "").rstrip() for _ in range(6)))
schreib()

# Opendatasoft mit Kennzeichen (Würzburg: `unverified`): wie verteilen sich die gekennzeichneten
# Stunden – nach Ortszeit, Monat, Standort, Länge der Folgen – und wie hoch sind ihre Werte?
from zaehlkarte.config import dauerquellen  # noqa: E402

try:
    _q = dauerquellen(pfade)[CODE]
except Exception as e:  # noqa: BLE001
    _q = {}
    out.append(f"(Quelldatei nicht gelesen: {e!r})")
if _q.get("ungeprueft") and (roh / "export.csv").exists():
    import pandas as pd

    d = pd.read_csv(roh / "export.csv", sep=";", encoding="utf-8-sig", dtype=str)
    f = _q["ungeprueft"]
    d["k"] = d[f].str.strip().str.lower().isin(["1", "true"])
    t = pd.to_datetime(d[_q["zeit"]], utc=True).dt.tz_convert("Europe/Berlin")
    d["stunde"] = t.dt.hour
    d["monat"] = t.dt.strftime("%Y-%m")
    d["wert"] = pd.to_numeric(d[_q["werte"][0]], errors="coerce")
    st = _q.get("stelle")
    out.append(f"== Kennzeichen {f}: Anteil gekennzeichnet")
    out.append("je Stunde (Ortszeit): " + ", ".join(
        f"{h}: {a:.0%}" for h, a in d.groupby("stunde")["k"].mean().items()))
    out.append("je Monat: " + ", ".join(
        f"{m}: {a:.0%}" for m, a in d.groupby("monat")["k"].mean().items()))
    if st:
        out.append("je Standort: " + ", ".join(
            f"{s_}: {a:.0%}" for s_, a in d.groupby(st)["k"].mean().items()))
    out.append("Median der Werte je Stunde (Ortszeit), geprüft / gekennzeichnet: " + ", ".join(
        f"{h}: {int(g[~g.k].wert.median()) if (~g.k).any() else '-'}/"
        f"{int(g[g.k].wert.median()) if g.k.any() else '-'}"
        for h, g in d.groupby("stunde")))
    # Folgen gekennzeichneter Stunden je Standort (Länge in Stunden)
    d["zeit_utc"] = pd.to_datetime(d[_q["zeit"]], utc=True)
    for s_, g in d.sort_values("zeit_utc").groupby(st or (lambda _: "")):
        lauf = (g["k"] != g["k"].shift()).cumsum()
        laengen = g[g["k"]].groupby(lauf[g["k"]]).size()
        if len(laengen):
            out.append(f"{s_}: {len(laengen)} Folgen, Länge Median {int(laengen.median())} h, "
                       f"größte {sorted(laengen.tolist())[-5:]} h; Anteil ganzer Ortstage "
                       f"gekennzeichnet: {g.groupby(g.zeit_utc.dt.tz_convert('Europe/Berlin').dt.date)['k'].all().mean():.0%}")
    # Beispieltag: Stunden eines Standorts mit Kennzeichen
    if st:
        erster = d[st].iloc[0]
        g = d[d[st] == erster].sort_values("zeit_utc").tail(72)
        out.append(f"jüngste 72 Stunden {erster}: " + " ".join(
            f"{z:%d.%m %H}h={w}{'*' if k else ''}" for z, w, k in
            zip(g.zeit_utc.dt.tz_convert("Europe/Berlin"), g.wert, g.k)))
    schreib()

gelesen, berichte = bau.baue(pfade, nur=[CODE])
q, r = gelesen[0]
out += ["== Lesen", *berichte[CODE], f"Reihe {r.von} – {r.tag(r.tage - 1)}, {len(r.stellen)} Stellen"]
for gruppe in r.werte:
    out.append(f"=== Gruppe {gruppe}")
    summen, n = tagessummen(r, gruppe)
    voll = summen >= 0
    out.append("== Je Zählstelle: Kennung | Name | Abschnitt | erster/letzter Tag mit Wert | "
               "vollständige Tage | jüngster vollständiger Tag | Median der vollen Tage")
    for i, s in enumerate(r.stellen):
        mit = np.flatnonzero(n[i] > 0)
        v = np.flatnonzero(voll[i])
        erster = r.tag(int(mit[0])) if len(mit) else None
        letzter = r.tag(int(mit[-1])) if len(mit) else None
        juengst = r.tag(int(v[-1])) if len(v) else None
        median = int(np.median(summen[i, v])) if len(v) else None
        out.append(f"{s.kennung} | {s.name} | {s.abschnitt} | {erster} – {letzter} | {len(v)} | "
                   f"{juengst} | {median}")
    out.append("== Jahresgrenzen: Stellen mit vollständigem 31.12. bzw. 1.1. (von Stellen mit Werten)")
    for jahr in range(r.von.year, r.tag(r.tage - 1).year + 1):
        zeile = []
        for t in (date(jahr, 1, 1), date(jahr, 12, 31)):
            if r.von <= t <= r.tag(r.tage - 1):
                k = r.index(t)
                zeile.append(f"{t}: {int(voll[:, k].sum())}/{int((n[:, k] > 0).sum())}")
        out.append(f"{jahr}: " + ", ".join(zeile))
    out.append("== Zeitumstellung: Stellen vollständig am Tag der Sommerzeit (23 h) / der Rückstellung")
    for jahr in range(r.von.year, r.tag(r.tage - 1).year + 1):
        zeile = []
        for t in umstellungen(jahr):
            if r.von <= t <= r.tag(r.tage - 1):
                k = r.index(t)
                stunden = sorted({int(x) for x in n[:, k] if x > 0})
                zeile.append(f"{t}: voll {int(voll[:, k].sum())}/{int((n[:, k] > 0).sum())}, "
                             f"gezählte Stunden {stunden}")
        out.append(f"{jahr}: " + "; ".join(zeile))
    out.append("== Vollständige Tage je Jahr (alle Stellen)")
    for jahr in range(r.von.year, r.tag(r.tage - 1).year + 1):
        a, b = max(r.von, date(jahr, 1, 1)), min(r.tag(r.tage - 1), date(jahr, 12, 31))
        ks = slice(r.index(a), r.index(b) + 1)
        out.append(f"{jahr}: {int(voll[:, ks].sum())} von {int((n[:, ks] > 0).sum())} Tagen mit Werten")
schreib()

dateien, zeilen = site_.schreibe(gelesen, pfade, date.today())
out += [f"== Kartendaten (nur {CODE})", *zeilen, *site_.statistik(gelesen)]
dauer = pfade.repo / "public" / "data" / "dauer"
with tarfile.open(ziel / f"dauer_{CODE}.tar.gz", "w:gz") as tar:
    tar.add(dauer, arcname="dauer")
index = json.loads((dauer / "index.json").read_text(encoding="utf-8"))
out.append("index.json quellen: " + json.dumps(index.get("quellen"), ensure_ascii=False)[:1500])
out.append("index.json lizenzen: " + json.dumps(index.get("lizenzen"), ensure_ascii=False)[:800])
schreib()
