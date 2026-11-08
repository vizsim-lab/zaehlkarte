"""Werkzeug: Lage der mobilen Zählstellen Konstanz (Nominatim, Overpass) und die
Datensatzseite samt Beschreibung."""

import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/konstanz_orte.json")
UA = {"User-Agent": "zaehlkarte-geokodierung/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url, daten=None):
    time.sleep(1.2)
    with urllib.request.urlopen(urllib.request.Request(url, data=daten, headers=UA), timeout=90) as a:
        return json.loads(a.read())


def nominatim(**q):
    q.update({"format": "jsonv2", "limit": 3, "countrycodes": "de", "addressdetails": 1})
    return hole("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(q))


def overpass(abfrage):
    return hole("https://overpass-api.de/api/interpreter", urllib.parse.urlencode({"data": abfrage}).encode())


out = {}
out["Schottenstraße"] = nominatim(street="Schottenstraße", city="Konstanz")
out["Alte Rheinbrücke"] = nominatim(q="Alte Rheinbrücke, Konstanz")
out["Jakobstraße 62"] = nominatim(street="62 Jakobstraße", city="Konstanz")
out["Theodor-Heuss-Straße"] = nominatim(street="Theodor-Heuss-Straße", city="Konstanz")
out["Z-Brücke"] = nominatim(q="Z-Brücke, Konstanz")
out["Fahrradbrücke"] = nominatim(q="Fahrradbrücke, Konstanz")
kreuz = """[out:json][timeout:60];
area["name"="Konstanz"]["boundary"="administrative"]->.k;
way(area.k)["highway"]["name"="Gartenstraße"]->.a;
way(area.k)["highway"]["name"="Schottenstraße"]->.b;
node(w.a)(w.b);
out;"""
out["Gartenstraße/Schottenstraße"] = overpass(kreuz)
# Geometrie der beiden Straßen ohne Hausnummer und der Brücken (für die Mitte)
out["linien"] = overpass("""[out:json][timeout:60];
area["name"="Konstanz"]["boundary"="administrative"]->.k;
(way(area.k)["highway"]["name"~"^(Schottenstraße|Theodor-Heuss-Straße)$"];
 way(area.k)["name"~"Rheinbrücke|Z-Brücke|Fahrradbrücke"];);
out geom;""")
ZIEL.write_text(json.dumps(out, ensure_ascii=False, indent=1))
print({k: (len(v) if isinstance(v, list) else len(v.get("elements", []))) for k, v in out.items()})
