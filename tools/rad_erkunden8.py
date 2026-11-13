"""Erkundung (13.11.2026), Teil 8: MobiData BW – Kanalnamen im älteren Format (zählt eine Stelle
auch Fußverkehr mit?) und Stellen, die dasselbe Gerät teilen."""
from __future__ import annotations

import csv
import io
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ZIEL = Path("ergebnis/rad8")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}
with urllib.request.urlopen(urllib.request.Request(
        "https://mobidata-bw.de/daten/eco-counter/eco_counter_fahrradzaehler.csv", headers=UA), timeout=300) as r:
    alt = list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))
kanaele = defaultdict(set)
for z in alt:
    kanaele[(z["domain_name"], z["counter_site_id"], z["counter_site"])].add(z["channel_name"])
aus = [f"{len(kanaele)} Stellen im älteren Format"]
woerter = Counter(w.lower() for v in kanaele.values() for k in v for w in k.split())
aus.append("häufigste Wörter in Kanalnamen: " + ", ".join(f"{w} {n}" for w, n in woerter.most_common(60)))
for (d, sid, n), ks in sorted(kanaele.items()):
    aus.append(f"{d} | {sid} | {n} | {sorted(ks)}")
(ZIEL / "kanaele.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
