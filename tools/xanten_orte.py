"""Werkzeug: Straßen der Xantener Zählstellen 2020 aus OpenStreetMap (eine Overpass-Abfrage:
Wege mit Knoten-IDs und die Knoten; Kreuzungen und Lage rechnet man lokal)."""

import json
import pathlib
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/xanten_osm.json")
UA = {"User-Agent": "zaehlkarte-geokodierung/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
STRASSEN = [
    "Siegfriedstraße", "Trajanring", "Am Nordturm", "Varusring", "Salmstraße", "Am Rheintor",
    "Lüttinger Straße", "Bislicher Insel", "Rheinberger Straße", "Augustusring", "Bahnhofstraße",
    "Poststraße", "Im Niederbruch", "Sonsbecker Straße", "Heinrich-Lensing-Straße", "Veener Weg",
    "Holzweg", "Viktorstraße", "Philosophenweg", "Gelderner Straße", "Maulbeerkamp", "Westwall",
    "Orkstraße", "Rheinstraße", "Ostwall",
]
ABFRAGE = (
    '[out:json][timeout:180];area["name"="Xanten"]["boundary"="administrative"]->.x;'
    f'way(area.x)["highway"]["name"~"^({"|".join(STRASSEN)})$"];out body;>;out skel qt;'
)
for server in ("https://overpass-api.de/api/interpreter",
               "https://overpass.private.coffee/api/interpreter",
               "https://overpass.kumi.systems/api/interpreter"):
    try:
        daten = urllib.parse.urlencode({"data": ABFRAGE}).encode()
        with urllib.request.urlopen(urllib.request.Request(server, data=daten, headers=UA),
                                    timeout=240) as a:
            antwort = json.loads(a.read())
        ZIEL.write_text(json.dumps(antwort, ensure_ascii=False))
        print(server, len(antwort.get("elements", [])), "Elemente")
        break
    except Exception as e:  # noqa: BLE001
        print(server, repr(e)[:200])
