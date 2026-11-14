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
