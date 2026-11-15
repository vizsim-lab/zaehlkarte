"""BW: in OpenStreetMap eingetragene Radzählstellen gegen die Rad-Zählstellen der Karte
(MobiData-Bündel und Ettlingen, aus dem Release `dauerzaehlstellen`) abgleichen.

OSM über Overpass (Server, deren robots.txt die Werkzeuge erlauben; tools/robots.py), gesucht:
`monitoring:bicycle=yes` und `man_made=monitoring_station` mit Fahrrad im Namen oder Zweck.
Aufruf: python3 tools/bw_rad_osm.py <dauer/index.json> ergebnis/bw/rad_osm
"""

import json
import math
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

INDEX = pathlib.Path(sys.argv[1])
ZIEL = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "ergebnis/bw/rad_osm")
ZIEL.mkdir(parents=True, exist_ok=True)
SERVER = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass.private.coffee/api/interpreter"]
ABFRAGE = """[out:json][timeout:170];
area["ISO3166-2"="DE-BW"]["admin_level"="4"]->.bw;
(
  nwr["monitoring:bicycle"="yes"](area.bw);
  nwr["man_made"="monitoring_station"]["monitoring:traffic"="yes"]["bicycle"](area.bw);
  nwr["man_made"="monitoring_station"]["name"~"[Rr]ad|[Ff]ahrrad|[Bb]icycle"](area.bw);
  nwr["display"]["monitoring:bicycle"](area.bw);
);
out center tags;"""


def abstand_m(a, b):
    (lon1, lat1), (lon2, lat2) = a, b
    x = math.radians(lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6_371_000 * math.hypot(x, y)


def overpass():
    for url in SERVER:
        try:
            daten = urllib.parse.urlencode({"data": ABFRAGE}).encode()
            inhalt, _, _ = R.oeffne(url, daten=daten, zeit=200, grenze=30_000_000)
            return json.loads(inhalt), url
        except Exception as e:  # noqa: BLE001
            print(url, "Fehler:", repr(e)[:200], flush=True)
    return None, None


def main():
    d = json.loads(INDEX.read_text(encoding="utf-8"))
    felder = d["stellen"]["felder"]
    i = {f: felder.index(f) for f in ("id", "quelle", "name", "lon", "lat")}
    karte = [{"id": s[i["id"]], "quelle": s[i["quelle"]], "name": s[i["name"]],
              "lage": (s[i["lon"]], s[i["lat"]])} for s in d["stellen"]["werte"]
             if s[i["quelle"]] in ("mobidata_rad", "ettlingen")]
    print("Stellen der Karte (BW):", len(karte), flush=True)
    antwort, server = overpass()
    if antwort is None:
        (ZIEL / "ergebnis.json").write_text(json.dumps({"fehler": "Overpass"}, indent=1))
        return
    osm = []
    for el in antwort.get("elements", []):
        lage = (el.get("lon") or (el.get("center") or {}).get("lon"),
                el.get("lat") or (el.get("center") or {}).get("lat"))
        if None in lage:
            continue
        naechste = min(karte, key=lambda k: abstand_m(lage, k["lage"])) if karte else None
        osm.append({"osm": f"{el['type']}/{el['id']}", "lage": lage, "tags": el.get("tags", {}),
                    "naechste": naechste and {"id": naechste["id"], "name": naechste["name"],
                                              "m": round(abstand_m(lage, naechste["lage"]))}})
    fern = sorted((o for o in osm if not o["naechste"] or o["naechste"]["m"] > 150),
                  key=lambda o: -(o["naechste"] or {"m": 1e9})["m"])
    (ZIEL / "ergebnis.json").write_text(json.dumps(
        {"server": server, "osm": len(osm), "karte": len(karte), "ohne_stelle_150m": fern,
         "alle": osm}, ensure_ascii=False, indent=1))
    zeilen = [f"Server {server}: {len(osm)} Zählstellen in OSM, {len(karte)} in der Karte; "
              f"{len(fern)} ohne Stelle der Karte im Umkreis von 150 m"]
    for o in fern:
        t = o["tags"]
        zeilen.append(" | ".join(str(x) for x in (
            o["osm"], f"{o['lage'][1]:.5f},{o['lage'][0]:.5f}", t.get("name"), t.get("operator"),
            t.get("ref"), t.get("website") or t.get("url"), t.get("monitoring:bicycle"),
            t.get("monitoring:pedestrian"), (o["naechste"] or {}).get("m"))))
    (ZIEL / "liste.txt").write_text("\n".join(zeilen) + "\n")
    print("\n".join(zeilen[:60]), flush=True)


if __name__ == "__main__":
    main()
