"""Erkundung (13.11.2026), Teil 9: MobiData BW – zählt `channels_all` im Bündel auch Pkw- und
Personen-Kanäle mit? Vergleich je Stelle und Stunde: älteres Format (Juni 2025, je Kanal) gegen
v2 (Monatsdatei 2025-06), getrennt nach Rad-, Pkw- und Personen-Kanälen."""
from __future__ import annotations

import csv
import gzip
import io
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ZIEL = Path("ergebnis/rad9")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


alt = list(csv.DictReader(io.StringIO(hole("https://mobidata-bw.de/daten/eco-counter/eco_counter_fahrradzaehler.csv").decode("utf-8-sig"))))
neu = list(csv.DictReader(io.StringIO(gzip.decompress(hole("https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_202506.csv.gz")).decode("utf-8-sig"))))


def art(kanal: str) -> str:
    k = kanal.lower()
    if "pkw" in k:
        return "pkw"
    if "personen" in k or "fußg" in k or "fussg" in k:
        return "fuss"
    if "fahrr" in k or "bike" in k or "cycl" in k or "rad" in k:
        return "rad"
    return "sonst"


summe = defaultdict(lambda: defaultdict(float))
arten_je = defaultdict(set)
for z in alt:
    k = (z["counter_site_id"], z["iso_timestamp"][:13])
    a = art(z["channel_name"])
    summe[k][a] += float(z["zählstand"] or 0)
    arten_je[z["counter_site_id"]].add((a, z["channel_name"]))
v2 = {(r["counter_site_id"], r["iso_timestamp"][:13]): r for r in neu}
aus = []
gemischt = sorted(s for s, ks in arten_je.items() if {a for a, _ in ks} - {"rad"})
for sid in gemischt:
    vergleich = Counter()
    for k, teile in summe.items():
        if k[0] != sid or k not in v2 or v2[k]["channels_all"] in ("", "na"):
            continue
        w = float(v2[k]["channels_all"])
        alle = sum(teile.values())
        nur_rad = teile.get("rad", 0) + teile.get("sonst", 0)
        if abs(w - alle) < 0.5 and abs(w - nur_rad) < 0.5:
            vergleich["beides gleich (Pkw/Personen 0)"] += 1
        elif abs(w - alle) < 0.5:
            vergleich["v2 = alle Kanäle"] += 1
        elif abs(w - nur_rad) < 0.5:
            vergleich["v2 = nur Rad"] += 1
        else:
            vergleich["anders"] += 1
    namen = sorted(n for _, n in arten_je[sid])
    name = next((z["counter_site"] for z in alt if z["counter_site_id"] == sid), "")
    aus.append(f"{sid} {name}: Kanäle {namen}; Vergleich {dict(vergleich)}")
# Stellen in v2 (Oktober 2026), die das ältere Format nicht kennt
okt = list(csv.DictReader(io.StringIO(gzip.decompress(hole("https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_202610.csv.gz")).decode("utf-8-sig"))))
stellen = {}
tag = defaultdict(float)
for r in okt:
    stellen[r["counter_site_id"]] = (r["domain_name"], r["counter_site"])
    if r["channels_all"] not in ("", "na") and r["iso_timestamp"][:10] == "2026-10-14":
        tag[r["counter_site_id"]] += float(r["channels_all"])
bekannt = set(arten_je)
aus.append(f"## Stellen im Oktober 2026: {len(stellen)}, davon im älteren Format: {len(set(stellen) & bekannt)}")
for sid, (d, n) in sorted(stellen.items(), key=lambda x: -tag.get(x[0], 0)):
    aus.append(f"   {'alt ' if sid in bekannt else 'NEU '} {sid} {d} | {n} | 14.10.: {tag.get(sid)}")
(ZIEL / "kanaele.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
