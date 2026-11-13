"""Erkundung (13.11.2026), Teil 5: offene Punkte für die Rad-Adapter.

- MobiData BW: enthält das v2-Bündel rekonstruierte Werte? Vergleich des eingefrorenen alten
  Formats (Juni 2025, Spalte `stand`: 0 = roh, 4 = rekonstruiert) mit der v2-Monatsdatei 2025-06.
- Münster: Standorte der Zählstellen (GeoJSON der Stadt).
- Kiel: Metadaten des neuen Mobilithek-Angebots 1045322209798569984.
- KMK-Ferienkalender als Text (pdftotext -layout) für BW und BY: 2007/08–2023/24.
Ergebnisse nach ergebnis/rad5/.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import subprocess
import traceback
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ZIEL = Path("ergebnis/rad5")
(ZIEL / "kmk").mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str, timeout: int = 180) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def teil(name, f):
    aus: list[str] = []
    try:
        f(aus)
    except Exception:  # noqa: BLE001
        aus.append(traceback.format_exc())
    (ZIEL / f"{name}.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


def mobidata(aus):
    alt = list(csv.DictReader(io.StringIO(
        hole("https://mobidata-bw.de/daten/eco-counter/eco_counter_fahrradzaehler.csv").decode("utf-8-sig"))))
    tage = sorted({r["iso_timestamp"][:10] for r in alt})
    aus.append(f"## altes Format: {len(alt)} Zeilen, Tage {tage[0]} … {tage[-1]}")
    roh = gzip.decompress(hole("https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_202506.csv.gz"))
    neu = list(csv.DictReader(io.StringIO(roh.decode("utf-8-sig"))))
    # altes Format: je Stelle und Stunde (Ortszeit laut iso_timestamp) Summe aller Kanäle, getrennt nach stand
    summe = defaultdict(float)
    summe_roh = defaultdict(float)
    stand = defaultdict(Counter)
    for r in alt:
        k = (r["counter_site_id"], r["iso_timestamp"][:13])
        w = float(r["zählstand"] or 0)
        summe[k] += w
        stand[k][r["stand"]] += 1
        if r["stand"] == "0":
            summe_roh[k] += w
    v2 = {(r["counter_site_id"], r["iso_timestamp"][:13]): r["channels_all"] for r in neu}
    vergleich = Counter()
    beispiele = defaultdict(list)
    for k, s in summe.items():
        if k not in v2:
            vergleich["nicht in v2"] += 1
            continue
        w = v2[k]
        art = "mit 4" if "4" in stand[k] else "nur 0"
        if w in ("", "na"):
            vergleich[f"{art}: v2 leer"] += 1
        elif abs(float(w) - s) < 0.5:
            vergleich[f"{art}: v2 = Summe aller"] += 1
        elif abs(float(w) - summe_roh[k]) < 0.5:
            vergleich[f"{art}: v2 = Summe nur roh"] += 1
        else:
            vergleich[f"{art}: v2 anders"] += 1
            if len(beispiele[art]) < 5:
                beispiele[art].append((k, s, summe_roh[k], w, dict(stand[k])))
    aus.append(f"## Vergleich je Stelle/Stunde: {dict(vergleich)}")
    for art, b in beispiele.items():
        aus.append(f"   Beispiele {art}: {b}")
    mit4 = sorted({k[0] for k, c in stand.items() if "4" in c})
    aus.append(f"## Stellen mit stand 4: {mit4}")


def muenster(aus):
    d = hole("https://opendata.stadt-muenster.de/sites/default/files/fahrradzaehl-standorte_0.geojson")
    (ZIEL / "muenster_standorte.geojson").write_bytes(d)
    g = json.loads(d)
    aus.append(f"## GeoJSON: {len(g.get('features', []))} Standorte")
    for f in g.get("features", []):
        aus.append(f"   {f.get('properties')} {f.get('geometry')}")


def kiel(aus):
    t = hole("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/1045322209798569984").decode("utf-8", "replace")
    (ZIEL / "kiel_angebot.json").write_text(t, encoding="utf-8")
    d = json.loads(t)
    for k in ("title", "rights", "standardLicense", "customLicenseAsResource", "conditionForUse",
              "contractOffer", "accessRights", "mdpBrokering", "temporalCoverage", "accrualPeriodicity",
              "created", "modified", "contentData"):
        aus.append(f"{k}: {json.dumps(d.get(k), ensure_ascii=False)[:800]}")


KMK = {
    "2007_08": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/Ferien07_08.pdf",
    "2008_09": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/Ferien08_09.pdf",
    "2009_10": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/Ferien09_10.pdf",
    "2010_11": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/Ferien2010_11.pdf",
    "2011_12": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2011_12.pdf",
    "2012_13": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2012_13.pdf",
    "2013_14": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2013_14.pdf",
    "2014_15": "https://www.kmk.org/fileadmin/Dateien/pdf/Bildung/AllgBildung/FER2014_15.pdf",
    "2015_16": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2015_16.pdf",
    "2016_17": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2016_17_-_NEU.pdf",
    "2017_18": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER17_18.pdf",
    "2018_19": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER18_19.pdf",
    "2019_20": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER19_20.pdf",
    "2020_21": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2020_21-neu.pdf",
    "2021_22": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2021_22-neu.pdf",
    "2022_23": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2022_23-neu.pdf",
    "2023_24": "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER2023_24-neu.pdf",
}


def kmk(aus):
    for jahr, url in KMK.items():
        try:
            pdf = ZIEL / "kmk" / f"FER{jahr}.pdf"
            pdf.write_bytes(hole(url))
            subprocess.run(["pdftotext", "-layout", str(pdf), str(ZIEL / "kmk" / f"FER{jahr}.txt")], check=True)
            pdf.unlink()
            aus.append(f"ok {jahr} {url}")
        except Exception as e:  # noqa: BLE001
            aus.append(f"fehler {jahr} {url} {e!r}")


if __name__ == "__main__":
    for name, f in [("mobidata", mobidata), ("muenster", muenster), ("kiel", kiel), ("kmk", kmk)]:
        teil(name, f)
