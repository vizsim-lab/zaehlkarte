"""Werkzeug: Olpe – alle „Verkehrsmessung(en)“-Pakete des Open-Data-Portals samt Dateien (gzip),
dazu je Datei eine Kurzstatistik (Fahrzeuge, Zeitraum, Klassen-Codes, Richtungen, Stundenprofil,
Lage), um Zeitzone und Klassen zu klären."""

import gzip
import hashlib
import json
import pathlib
import re
import statistics
import sys
import urllib.parse
import urllib.request
from collections import Counter

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/olpe")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
API = "https://opendata.olpe.de/api/3/action/"
protokoll = {}


def hole(url, roh=False, timeout=300):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as a:
        daten = a.read()
    return daten if roh else json.loads(daten)


def statistik(daten: bytes) -> dict:
    d = json.loads(daten.decode("utf-8-sig"))
    st = {"format": "geraet" if isinstance(d, dict) else "flach"}
    fahrzeuge, lagen, codes, namen, richt, spur, stunden = [], [], Counter(), Counter(), Counter(), Counter(), Counter()
    if isinstance(d, dict):
        st["header"] = d.get("header")
        st["request"] = d.get("request")
        for e in d.get("data", []):
            for m in e.get("measurement_data", []):
                lagen.append((m.get("lon"), m.get("lat"), m.get("start_date"), m.get("end_date")))
            for v in e.get("vehicle_data", []):
                fahrzeuge.append(v.get("date"))
                codes[v.get("code")] += 1
                richt[v.get("direction")] += 1
                spur[v.get("lane")] += 1
    else:
        for v in d:
            fahrzeuge.append(v.get("Datum"))
            codes[v.get("Klasse")] += 1
            namen[(v.get("Klasse"), v.get("Fahrzeugklassen-Bezeichnung"))] += 1
            richt[v.get("Richtung")] += 1
            spur[v.get("Fahrspur")] += 1
    for t in fahrzeuge:
        m = re.search(r"(\d{2}):\d{2}:\d{2}", t or "")
        if m:
            stunden[int(m.group(1))] += 1
    st.update({
        "fahrzeuge": len(fahrzeuge), "erstes": min(fahrzeuge) if fahrzeuge else None,
        "letztes": max(fahrzeuge) if fahrzeuge else None,
        "codes": codes.most_common(), "namen": [[list(k), n] for k, n in namen.most_common()],
        "richtungen": richt.most_common(), "spuren": spur.most_common(),
        "stunden": [stunden.get(h, 0) for h in range(24)],
        "lagen": len(lagen),
        "lage_median": [statistics.median(x[0] for x in lagen if x[0]),
                        statistics.median(x[1] for x in lagen if x[1])] if lagen else None,
        "lage_erste": lagen[:3],
    })
    return st


pakete = {}
for q in ("Verkehrsmessung", "Verkehrsmessungen"):
    try:
        for p in hole(API + "package_search?" + urllib.parse.urlencode({"q": q, "rows": 200}))["result"]["results"]:
            if re.search(r"verkehrsmess", p["name"] + " " + (p.get("title") or ""), re.I):
                pakete[p["name"]] = p
    except Exception as e:  # noqa: BLE001
        protokoll[f"suche:{q}"] = repr(e)[:200]
protokoll["pakete"] = sorted(pakete)
stat = {}
for name, p in sorted(pakete.items()):
    ordner = ZIEL / name
    ordner.mkdir(exist_ok=True)
    (ordner / "paket.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in p.get("resources", []):
        url = r.get("url") or ""
        if not re.search(r"\.(json|csv|txt)$", url, re.I):
            continue
        datei = urllib.parse.unquote(url.rsplit("/", 1)[-1])
        try:
            daten = hole(url, roh=True)
            (ordner / (datei + ".gz")).write_bytes(gzip.compress(daten))
            eintrag = {"url": url, "bytes": len(daten), "sha256": hashlib.sha256(daten).hexdigest(),
                       "ressource": r.get("name")}
            if datei.lower().endswith(".json"):
                try:
                    eintrag.update(statistik(daten))
                except Exception as e:  # noqa: BLE001
                    eintrag["statistik_fehler"] = repr(e)[:200]
            stat[f"{name}/{datei}"] = eintrag
        except Exception as e:  # noqa: BLE001
            stat[f"{name}/{datei}"] = {"url": url, "fehler": repr(e)[:200]}
(ZIEL / "statistik.json").write_text(json.dumps(stat, ensure_ascii=False, indent=1), encoding="utf-8")
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(protokoll, ensure_ascii=False, indent=1))
