"""Erkundung (15.11.2026), Teil 3: Lage der Fahrradzählstelle Planegg (Amtmannstraße/Münchner
Straße) aus OpenStreetMap – kleine Overpass-Abfragen reihum über die erlaubten Server (wie
bw_ol6.py). Abfragen mit Ergebnis (ergebnis/bw/fl3/teile/*.json) werden übersprungen.

Aufruf: python3 tools/bw_fl3.py ergebnis/bw/fl3
"""

import json
import pathlib
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
(ZIEL / "teile").mkdir(parents=True, exist_ok=True)
SERVER = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass.private.coffee/api/interpreter",
          "https://overpass.kumi.systems/api/interpreter"]
PLANEGG = "48.085,11.395,48.125,11.445"
ABFRAGEN = {
    # die beiden Straßen der Zählstelle samt Geometrie
    "strassen": (f'[out:json][timeout:60];(way["name"~"^(Amtmannstraße|Münchner Straße)$"]({PLANEGG}););'
                 'out body geom;'),
    # Zählgeräte, die in OSM eingetragen sind
    "zaehler": (f'[out:json][timeout:60];(node["man_made"="monitoring_station"]({PLANEGG});'
                f'node["monitoring:bicycle"]({PLANEGG});node["description"~"[Zz]ähl"]({PLANEGG}););'
                'out body;'),
    # Rad- und Fußwege am Knoten (um 48.10/11.42 herum, weit genug für beide Straßen)
    "radwege": (f'[out:json][timeout:60];(way["highway"~"^(cycleway|path|footway)$"]({PLANEGG});'
                f'way["bicycle_road"="yes"]({PLANEGG});way["cycleway"]({PLANEGG}););out body geom;'),
}
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def versuch(abfrage, url):
    daten = urllib.parse.urlencode({"data": abfrage}).encode()
    inhalt, _, _ = R.oeffne(url, daten=daten, zeit=100, grenze=60_000_000)
    d = json.loads(inhalt)
    if d.get("remark") and not d.get("elements"):
        raise ValueError(d["remark"][:150])
    return d


def main(runden=10):
    offen = [n for n in ABFRAGEN if not (ZIEL / "teile" / f"{n}.json").exists()]
    for runde in range(runden):
        if not offen:
            break
        for i, name in enumerate(list(offen)):
            url = SERVER[(runde + i) % len(SERVER)]
            try:
                d = versuch(ABFRAGEN[name], url)
                (ZIEL / "teile" / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False))
                log(name, "Runde", runde + 1, url, len(d.get("elements", [])), "Elemente")
                offen.remove(name)
            except R.Gesperrt:
                log(name, "gesperrt", url)
            except Exception as e:  # noqa: BLE001
                log(name, "Runde", runde + 1, url, "Fehler", repr(e)[:120])
            time.sleep(3)
        if offen:
            time.sleep(20 + 10 * runde)
    log("offen:", offen)
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    with open(ZIEL / "log.txt", "a") as f:
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
