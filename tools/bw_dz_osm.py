"""BW: Verkehrszählstellen (Kfz) in OpenStreetMap – für Dauerzählstellen des Landes ohne Lage in der
Zählstellenkarte (Nummern und Namen als Argumente). Overpass über tools/robots.py.

Aufruf: python3 tools/bw_dz_osm.py ergebnis/bw/dz_osm 8035:Achern 8385:Stetten …
"""

import json
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
GESUCHT = dict(a.split(":", 1) for a in sys.argv[2:])
SERVER = ["https://overpass.private.coffee/api/interpreter",
          "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
ABFRAGE = """[out:json][timeout:170];
area["ISO3166-2"="DE-BW"]["admin_level"="4"]->.bw;
(
  nwr["man_made"="monitoring_station"]["monitoring:traffic"](area.bw);
  nwr["man_made"="monitoring_station"]["monitoring:vehicle"](area.bw);
  nwr["man_made"="monitoring_station"]["traffic_counter"](area.bw);
  nwr["highway"="traffic_counter"](area.bw);
  nwr["traffic_counter"](area.bw);
);
out center tags;"""


def main():
    antwort = None
    for url in SERVER:
        try:
            inhalt, _, _ = R.oeffne(url, daten=urllib.parse.urlencode({"data": ABFRAGE}).encode(),
                                   zeit=200, grenze=30_000_000)
            antwort = json.loads(inhalt)
            break
        except Exception as e:  # noqa: BLE001
            print(url, "Fehler:", repr(e)[:200], flush=True)
    if antwort is None:
        return
    alle = []
    for el in antwort["elements"]:
        t = el.get("tags", {})
        lage = (el.get("lon") or el.get("center", {}).get("lon"), el.get("lat") or el.get("center", {}).get("lat"))
        alle.append({"osm": f"{el['type']}/{el['id']}", "lage": lage, "tags": t})
    treffer = {}
    for nr, name in GESUCHT.items():
        treffer[nr] = [a for a in alle if nr in json.dumps(a["tags"], ensure_ascii=False)
                       or name.lower() in json.dumps(a["tags"], ensure_ascii=False).lower()]
    (ZIEL / "ergebnis.json").write_text(json.dumps({"anzahl": len(alle), "treffer": treffer,
                                                    "alle": alle}, ensure_ascii=False, indent=1))
    print(len(alle), "Zählstellen in OSM")
    for nr, t in treffer.items():
        print(nr, GESUCHT[nr], [(x["osm"], x["lage"], x["tags"]) for x in t][:5])


if __name__ == "__main__":
    main()
