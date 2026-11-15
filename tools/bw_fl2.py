"""Erkundung (15.11.2026), Teil 2: Wo liefert BAYSIS die Stundenwerte der Dauerzählstellen? Und
wie lang reicht das ältere Eco-Counter-Format von MobiData BW (Personen-Kanäle)?

Teile (Aufruf: python3 tools/bw_fl2.py <ziel> <teil> [<teil> …]):
- baysis: Seite „Dauerzählstellen“ samt Skripten (wo steckt die Auswahl?), die Seite der
  SVZ-Zählstellenauswahl zum Vergleich, der ArcGIS-Dienst BAYSIS_Verkehrsdaten (Ebenen, die
  Ebene der Dauerzählstellen als JSON).
- mobidata: das ältere Format `eco_counter_fahrradzaehler.csv` – Zeitraum je Kanalart.
Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py).
"""

from __future__ import annotations

import collections
import csv
import gzip
import io
import json
import pathlib
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
LOG: list[str] = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def hole(url, *, zeit=90, grenze=40_000_000):
    for versuch in range(3):
        try:
            inhalt, ende, art = R.oeffne(url, zeit=zeit, grenze=grenze)
            log("ok", url, len(inhalt), art)
            return inhalt, ende, art
        except R.Gesperrt:
            log("gesperrt", url)
            raise
        except Exception as e:  # noqa: BLE001
            log("Fehler", versuch + 1, url, repr(e)[:160])
            if versuch == 2 or "HTTP Error 4" in repr(e):
                raise
            time.sleep(5 + 10 * versuch)


def speichere(name: str, inhalt: bytes):
    p = ZIEL / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(inhalt)


BAYSIS = "https://www.baysis.bayern.de"
GIS = "https://gisportal-stmb.bayern.de/server/rest/services"


def baysis():
    aus = []
    seiten = {"dauz.html": f"{BAYSIS}/internet/verdat/dauz/index.html",
              "svz_zaehlstelle.html": f"{BAYSIS}/internet/verdat/svz/zaehlstelle/index.html",
              "svz.html": f"{BAYSIS}/internet/verdat/svz/index.html",
              "vdm.html": f"{BAYSIS}/internet/verdat/vdm/index.html"}
    skripte = set()
    for name, url in seiten.items():
        try:
            inhalt, ende, _ = hole(url)
        except Exception as e:  # noqa: BLE001
            aus.append(f"{url}: {e!r}"[:200])
            continue
        speichere(f"baysis/{name}", inhalt)
        t = inhalt.decode("utf-8", "replace")
        # Hauptinhalt: alles mit „Auswahl“, Formulare, data-Attribute, onclick
        for m in re.finditer(r"<[^>]*(?:Auswahl|data-|onclick|<form|<select|<input|<button)[^>]*>", t):
            aus.append(f"{name}: {m.group(0)[:400]}")
        i = t.find("Auswahl nach")
        if i >= 0:
            aus.append(f"{name} um „Auswahl nach“: {t[max(0, i - 3000):i + 3000]}")
        for s in re.findall(r"""<script[^>]+src=["']([^"']+)""", t):
            skripte.add(urllib.parse.urljoin(ende, s))
    for url in sorted(skripte):
        try:
            inhalt, _, _ = hole(url, grenze=10_000_000)
        except Exception:  # noqa: BLE001
            continue
        name = re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.urlsplit(url).path)[-80:]
        speichere(f"baysis/js/{name}", inhalt)
        t = inhalt.decode("utf-8", "replace")
        for m in re.finditer(r"(?i)dauz|zaehlst|zählst|\.csv|\.json|ajax|fetch\(|XMLHttpRequest|/api/|/web/|\.aspx|\.php", t):
            aus.append(f"{name} @{m.start()}: {t[max(0, m.start() - 200):m.start() + 300]!r}")
    # ArcGIS-Dienste
    for pfad in ["?f=json", "/WMS?f=json", "/WFS?f=json", "/WMS/BAYSIS_Verkehrsdaten/MapServer?f=json",
                 "/WMS/BAYSIS_Verkehrsdaten/MapServer/layers?f=json"]:
        url = GIS + pfad
        try:
            inhalt, _, _ = hole(url)
            speichere("gis/" + re.sub(r"[^A-Za-z0-9._-]+", "_", pfad) + ".json", inhalt)
        except Exception as e:  # noqa: BLE001
            aus.append(f"{url}: {e!r}"[:200])
    try:
        lagen = json.loads((ZIEL / "gis/_WMS_BAYSIS_Verkehrsdaten_MapServer_layers_f_json.json").read_text())
        for lage in lagen.get("layers", []):
            aus.append(f"Ebene {lage.get('id')}: {lage.get('name')} | {lage.get('type')} | Felder "
                       + ", ".join(f"{f.get('name')}" for f in lage.get("fields") or []))
            if "dauer" in (lage.get("name") or "").lower():
                url = (f"{GIS}/WMS/BAYSIS_Verkehrsdaten/MapServer/{lage['id']}/query?where=1%3D1"
                       "&outFields=*&returnGeometry=true&outSR=4326&f=json")
                try:
                    inhalt, _, _ = hole(url)
                    speichere(f"gis/dauerzaehlstellen_{lage['id']}.json", inhalt)
                except Exception as e:  # noqa: BLE001
                    aus.append(f"{url}: {e!r}"[:200])
    except Exception as e:  # noqa: BLE001
        aus.append(f"Ebenen: {e!r}"[:200])
    (ZIEL / "baysis.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


def mobidata():
    url = "https://mobidata-bw.de/daten/eco-counter/eco_counter_fahrradzaehler.csv"
    inhalt, _, _ = hole(url, zeit=300, grenze=400_000_000)
    speichere("mobidata/eco_counter_fahrradzaehler.csv.gz", gzip.compress(inhalt, 6))
    text = inhalt.decode("utf-8-sig", "replace")
    r = csv.DictReader(io.StringIO(text))
    aus = [f"Spalten: {r.fieldnames}"]
    je = collections.defaultdict(lambda: ["9999", "0000", 0])
    for z in r:
        k = z.get("channel_name", "")
        art = ("personen" if re.search(r"(?i)person|fußg|fussg|pedestr", k) else
               "pkw" if re.search(r"(?i)pkw|auto|car", k) else "rad")
        t = z.get("iso_timestamp", "")
        g = je[(z.get("counter_site_id"), z.get("counter_site"), art)]
        g[0], g[1], g[2] = min(g[0], t), max(g[1], t), g[2] + 1
    for k, (a, b, n) in sorted(je.items(), key=lambda x: (x[0][2] != "personen", x[0])):
        if k[2] != "rad" or n < 0:
            aus.append(f"{k}: {a} bis {b}, {n} Zeilen")
    aus.append(f"alle Stellen: {len({k[0] for k in je})}; Zeitraum gesamt "
               f"{min(v[0] for v in je.values())} bis {max(v[1] for v in je.values())}")
    (ZIEL / "mobidata.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


TEILE = {"baysis": baysis, "mobidata": mobidata}

if __name__ == "__main__":
    ZIEL.mkdir(parents=True, exist_ok=True)
    for t in sys.argv[2:]:
        try:
            TEILE[t]()
        except Exception as e:  # noqa: BLE001
            log("Teil", t, "abgebrochen:", repr(e)[:300])
    (ZIEL / f"robots_{'_'.join(sys.argv[2:])}.json").write_text(
        json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    with open(ZIEL / "log.txt", "a") as f:
        f.write("\n".join(LOG) + "\n")
