"""Erkundung (13.11.2026), Teil 10: MobiData BW – Form der Zeitstempel in allen Monatsdateien
(seit 2013). Der echte Bau scheiterte an Zeilen ohne Versatz („+01:00“). Je Monat: Formen der
Zeitstempel (Länge, Trennzeichen, Versatz), erste und letzte Zeile; für Monate ohne Versatz an den
Umstellungstagen je Stelle die Zahl der Zeilen um 2 Uhr (Ortszeit: im März 0, im Oktober 1 oder 2;
UTC: je Stunde genau eine) und das Verhältnis 2 Uhr / Mittel aus 1 und 3 Uhr."""
from __future__ import annotations

import csv
import gzip
import io
import re
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ZIEL = Path("ergebnis/rad10")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}
URL = "https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_{m}.csv.gz"


def hole(url: str) -> bytes | None:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def letzter_sonntag(j: int, m: int) -> date:
    d = date(j, m, 31)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def form(ts: str) -> str:
    """Zeitstempel -> Muster (Ziffern als 9)."""
    return re.sub(r"\d", "9", ts)


aus = []
monate = []
j, m = 2013, 1
while (j, m) <= (2026, 11):
    monate.append(f"{j}{m:02d}")
    j, m = (j + 1, 1) if m == 12 else (j, m + 1)

uebersicht = []
for mo in monate:
    roh = hole(URL.format(m=mo))
    if roh is None:
        uebersicht.append(f"{mo}: fehlt (404)")
        continue
    r = csv.reader(io.StringIO(gzip.decompress(roh).decode("utf-8-sig")))
    kopf = next(r)
    i_ts, i_id, i_w = (kopf.index(k) for k in ("iso_timestamp", "counter_site_id", "channels_all"))
    i_tz = kopf.index("timezone") if "timezone" in kopf else None
    zeilen = [{"iso_timestamp": z[i_ts], "counter_site_id": z[i_id], "channels_all": z[i_w],
               "timezone": z[i_tz] if i_tz is not None else ""} for z in r if z]
    formen = Counter(form(z["iso_timestamp"]) for z in zeilen)
    ts = sorted(z["iso_timestamp"] for z in zeilen)
    tz = Counter(z.get("timezone", "") for z in zeilen)
    uebersicht.append(f"{mo}: {len(zeilen)} Zeilen; Formen {dict(formen.most_common(4))}; "
                      f"erste {ts[0]!r}, letzte {ts[-1]!r}; timezone {dict(tz.most_common(2))}")
    ohne = [z for z in zeilen if not re.search(r"[+-]\d\d:\d\d$", z["iso_timestamp"])]
    if ohne and mo[4:] in ("03", "10"):
        jj, mm = int(mo[:4]), int(mo[4:])
        tag = letzter_sonntag(jj, mm).isoformat()
        je = defaultdict(Counter)  # Stelle -> Stunde -> Zeilen
        werte = defaultdict(lambda: defaultdict(list))
        for z in ohne:
            t = z["iso_timestamp"]
            if t[:10] == tag:
                h = int(t[11:13])
                je[z["counter_site_id"]][h] += 1
                if z["channels_all"] not in ("", "na"):
                    werte[z["counter_site_id"]][h].append(float(z["channels_all"]))
        verteilung = Counter(je[s][2] for s in je)
        n_stunden = Counter(sum(1 for h in range(24) if je[s][h]) for s in je)
        q = []
        for s, w in werte.items():
            if w[2] and w[1] and w[3]:
                q.append(sum(w[2]) / ((sum(w[1]) + sum(w[3])) / 2 or 1))
        q.sort()
        mitte = q[len(q) // 2] if q else None
        aus.append(f"{mo} Umstellung {tag}: {len(je)} Stellen; Zeilen um 2 Uhr je Stelle "
                   f"{dict(verteilung)}; Stunden mit Zeilen je Stelle {dict(n_stunden)}; "
                   f"Median 2 Uhr / Mittel(1, 3 Uhr) = {mitte}")
        # Vergleich: gewöhnlicher Sonntag eine Woche vorher
        vorher = (letzter_sonntag(jj, mm) - timedelta(days=7)).isoformat()
        w2 = defaultdict(lambda: defaultdict(float))
        for z in ohne:
            t = z["iso_timestamp"]
            if t[:10] == vorher and z["channels_all"] not in ("", "na"):
                w2[z["counter_site_id"]][int(t[11:13])] += float(z["channels_all"])
        q2 = sorted(w[2] / ((w[1] + w[3]) / 2) for w in w2.values() if w[1] + w[3] > 0)
        aus.append(f"   Sonntag davor {vorher}: Median 2 Uhr / Mittel(1, 3 Uhr) = "
                   f"{q2[len(q2) // 2] if q2 else None}")
    if ohne:
        # Grenzen des Monats: beginnt er um 00 Uhr Ortszeit am 1.? (UTC-Dateien begännen am
        # Vortag 22/23 Uhr oder um 00 Uhr UTC = 01/02 Uhr Ortszeit)
        erste = Counter(z["iso_timestamp"][:13] for z in ohne
                        if z["iso_timestamp"][:10] == f"{mo[:4]}-{mo[4:]}-01")
        aus.append(f"{mo} ohne Versatz: {len(ohne)} Zeilen; am 1. die Stunden "
                   f"{sorted(erste)[:3]}; Formen {dict(Counter(form(z['iso_timestamp']) for z in ohne).most_common(3))}")

(ZIEL / "monate.txt").write_text("\n".join(uebersicht) + "\n", encoding="utf-8")
(ZIEL / "ohne_versatz.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
print("\n".join(uebersicht[:3] + ["…"] + uebersicht[-3:]))
print("\n".join(aus[:60]))
