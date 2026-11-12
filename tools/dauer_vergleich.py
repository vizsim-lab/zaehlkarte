"""Diagnose: Welche Regel für deinstallierte Detektoren passt zur alten Qualitätssicherung?

A = deinstallierte Detektoren zählen mit, wenn sie im Monat Werte liefern (jetziger Adapter)
B = deinstallierte Detektoren zählen nie mit
Vergleich je Monat 2023–2024 (beide Verfahren vorhanden) und Anteil der deinstallierten
Detektoren an den Kfz-Summen 2025. Aufruf aus app/pipeline: uv run python ../../tools/dauer_vergleich.py
"""
import calendar
import json
import sys
from datetime import date

import numpy as np

from zaehlkarte.config import Pfade, dauerquellen
from zaehlkarte.dauer import berlin_viz as b
from zaehlkarte.dauer.modell import Messreihe

q = dauerquellen()["berlin_viz"]
pfade = Pfade()
ordner = pfade.roh / "berlin_viz"
sd = b.lies_stammdaten(ordner / q["stammdaten"], q)
sd_b = b.Stammdaten(sd.stellen, sd.index,
                    {mq: [x for x in d if x not in sd.deinstalliert] for mq, d in sd.detektoren.items()}, set())
out = {"monate": {}, "2025": {}}
for j in (2023, 2024):
    for m in range(1, 13):
        alt_p = ordner / f"{j}/alte_qualitaetssicherung/Messquerschnitte/mq_hr_{j}_{m:02d}.csv.gz"
        neu_p = ordner / f"{j}/neue_qualitaetssicherung/Fahrstreifendetektoren/detektoren_{j}_{m:02d}.tgz"
        if not (alt_p.exists() and neu_p.exists()):
            continue
        t0, t1 = date(j, m, 1), date(j, m, calendar.monthrange(j, m)[1])
        alt = Messreihe.leer("x", t0, t1, sd.stellen)
        b.lies_alte(alt_p, alt, sd, b.Bericht())
        zeile = {}
        for name, s in (("A", sd), ("B", sd_b)):
            neu = Messreihe.leer("x", t0, t1, sd.stellen)
            b.lies_neue(neu_p, neu, s, 75, b.Bericht(), j, m)
            a, n = alt.werte["kfz"], neu.werte["kfz"]
            beide = (a >= 0) & (n >= 0)
            x, y = a[beide].astype(float), n[beide].astype(float)
            gleich = ((np.abs(x - y) <= 1) | (np.abs(x - y) / np.maximum(x, 1) <= 0.02)).sum()
            # je MQ: Anteil gleicher Stunden – betroffen sind MQ mit deinstallierten Detektoren
            mq_mit = [i for mq, i in sd.index.items() if any(d in sd.deinstalliert for d in sd.detektoren[mq])]
            bm = beide[mq_mit]
            xm, ym = a[mq_mit][bm].astype(float), n[mq_mit][bm].astype(float)
            gm = ((np.abs(xm - ym) <= 1) | (np.abs(xm - ym) / np.maximum(xm, 1) <= 0.02)).sum()
            zeile[name] = {"beide": int(beide.sum()), "gleich": round(float(gleich / max(beide.sum(), 1)), 4),
                           "nur_alt": int(((a >= 0) & (n < 0)).sum()), "nur_neu": int(((a < 0) & (n >= 0)).sum()),
                           "mq_mit_deinst_beide": int(bm.sum()), "mq_mit_deinst_gleich": round(float(gm / max(bm.sum(), 1)), 4),
                           "median_rel": round(float(np.median(np.abs(x - y) / np.maximum(x, 1))) if x.size else 0, 4),
                           "mittel_rel_vorzeichen": round(float(np.mean((y - x) / np.maximum(x, 1))) if x.size else 0, 4)}
        out["monate"][f"{j}-{m:02d}"] = zeile
        print(j, m, zeile, flush=True)
# 2025: Welche deinstallierten Detektoren liefern Werte, und wie viel?
import gzip, io, re, tarfile
from pathlib import Path
for m in range(1, 7):
    p = ordner / f"2025/neue_qualitaetssicherung/Fahrstreifendetektoren/detektor_2025_{m:02d}.tgz"
    if not p.exists():
        continue
    mit = {}
    with tarfile.open(p, "r:*") as tf:
        for g in tf.getmembers():
            if not g.isfile():
                continue
            name = re.sub(r"\.csv(\.gz)?$", "", Path(g.name).name)
            if name not in sd.deinstalliert:
                continue
            inhalt = tf.extractfile(g).read()
            if g.name.endswith(".gz"):
                inhalt = gzip.decompress(inhalt)
            d = b._detektor_csv(inhalt, 2025, m, 75, set(), b.Bericht())
            mit[name] = {"stunden": len(d), "kfz_summe": int(d["kfz"].sum()) if len(d) else 0}
    out["2025"][f"2025-{m:02d}"] = {"deinstalliert_mit_werten": sum(1 for v in mit.values() if v["stunden"]),
                                     "beispiele": dict(list(sorted(mit.items(), key=lambda kv: -kv[1]["stunden"]))[:8])}
    print(m, out["2025"][f"2025-{m:02d}"]["deinstalliert_mit_werten"], flush=True)
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1))
