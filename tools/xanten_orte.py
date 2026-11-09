"""Werkzeug: Lage der Xantener Zählstellen 2020 aus OpenStreetMap (Overpass).

Knotenpunkte: gemeinsamer Knoten zweier Straßen des Namens („Siegfriedstraße/ Trajanring/ …“).
Querschnitte: Geometrie der Straße (die Stelle auf der Straße kommt aus der Zählstellenkarte
im Bericht, Abb. 3.-1)."""

import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/xanten_orte.json")
UA = {"User-Agent": "zaehlkarte-geokodierung/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
SERVER = ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter")
KNOTEN = {
    "K1": "Siegfriedstraße/ Trajanring/ Am Nordturm/ Varusring",
    "K2": "Salmstraße/ Varusring/ Am Rheintor/ Varusring",
    "K3": "Varusring/ Lüttinger Straße/ Varusring/ Lüttinger Straße",
    "K4": "Varusring/ Bislicher Insel/ Rheinberger Straße/ Augustusring",
    "K5": "Siegfriedstraße/ Bahnhofstraße/ Poststraße/ Bahnhofstraße",
    "K6": "Im Niederbruch/ Sonsbecker Straße/ Heinrich-Lensing-Straße/ Sonsbecker Straße",
    "K7": "Poststraße/ Augustusring/ Veener Weg/ Augustusring",
    "K8": "Heinrich-Lensing-Straße/ Augustusring/ Augustusring",
    "K9": "Poststraße/ Holzweg/ Poststraße/ Holzweg",
    "K10": "Lüttinger Straße/ Viktorstraße/ Holzweg/ Viktorstraße",
    "K11": "Trajanring/ Augustusring/ Philosophenweg/ Gelderner Straße",
    "K12": "Trajanring/ Sonsbecker Straße/ Trajanring",
}
QUERSCHNITTE = ["Maulbeerkamp", "Westwall", "Orkstraße", "Rheinstraße", "Ostwall"]


def overpass(abfrage):
    fehler = None
    for server in SERVER:
        try:
            time.sleep(2)
            daten = urllib.parse.urlencode({"data": abfrage}).encode()
            with urllib.request.urlopen(urllib.request.Request(server, data=daten, headers=UA),
                                        timeout=120) as a:
                return json.loads(a.read())
        except Exception as e:  # noqa: BLE001
            fehler = repr(e)
    return {"fehler": fehler, "elements": []}


GEBIET = 'area["name"="Xanten"]["boundary"="administrative"]->.x;'
out = {"knoten": {}, "strassen": {}}
for k, name in KNOTEN.items():
    strassen = list(dict.fromkeys(s.strip() for s in name.split("/") if s.strip()))
    treffer = []
    for i, a in enumerate(strassen):
        for b in strassen[i + 1:]:
            r = overpass(f'[out:json][timeout:60];{GEBIET}way(area.x)["highway"]["name"="{a}"]->.a;'
                         f'way(area.x)["highway"]["name"="{b}"]->.b;node(w.a)(w.b);out;')
            treffer.append({"a": a, "b": b, "knoten": [(n["lon"], n["lat"]) for n in r.get("elements", [])],
                            "fehler": r.get("fehler")})
    out["knoten"][k] = {"name": name, "paare": treffer}
for s in QUERSCHNITTE:
    r = overpass(f'[out:json][timeout:60];{GEBIET}way(area.x)["highway"]["name"="{s}"];out geom;')
    out["strassen"][s] = [{"id": w["id"], "highway": w["tags"].get("highway"),
                           "geometrie": [(p["lon"], p["lat"]) for p in w.get("geometry", [])]}
                          for w in r.get("elements", [])]
ZIEL.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print({k: [len(p["knoten"]) for p in v["paare"]] for k, v in out["knoten"].items()})
print({s: len(v) for s, v in out["strassen"].items()})
