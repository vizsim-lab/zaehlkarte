"""Werkzeug: Olpe – Adressen der Messstellen geokodieren (Nominatim, eine Anfrage je Sekunde),
um die GPS-Lage der Geräte zu prüfen und „Zum Honigsack 35“ (ohne GPS) zu verorten."""

import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/olpe_orte.json")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
ADRESSEN = ["Zum Honigsack 35, 57462 Olpe", "Zum Honigsack, Olpe", "Rochusstraße, Olpe",
            "Günsestraße 26, Olpe", "Günsestraße, Olpe", "Hatzenbergstraße 17, Olpe", "In der Wüste 26, Olpe",
            "Freizeitbad Olpe", "Weite Schlüppe, Olpe", "Alte Landstraße 1, Olpe", "Feuerwehrhaus Oberveischede",
            "Oberveischede, Olpe", "K 18, Olpe"]
out = {}
for a in ADRESSEN:
    try:
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(
            {"q": a, "format": "jsonv2", "limit": 3, "countrycodes": "de"})
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            out[a] = [{k: x.get(k) for k in ("display_name", "lat", "lon", "type", "class")} for x in json.loads(r.read())]
    except Exception as e:  # noqa: BLE001
        out[a] = repr(e)[:200]
    time.sleep(1.2)
ZIEL.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=1)[:4000])
