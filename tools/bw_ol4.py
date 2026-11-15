"""BW, Kurzzeitzählungen ohne Lizenz – Lage, vierter Versuch: Overpass mit wenigen, gezielten
Abfragen (Straßen nach exaktem Namen im Gebiet der Stadt Tübingen, alle Straßen um Martinsmoos,
Ortstafeln, Orte, Friedhöfe, Parkplätze) und langem Atem: jede Abfrage bis zu achtmal über alle
erlaubten Server, mit wachsender Pause. Photon sperrt robots.txt für alle Robots (ol3).

Aufruf: python3 tools/bw_ol4.py ergebnis/bw/ol4
"""

import json
import pathlib
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
SERVER = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass.private.coffee/api/interpreter",
          "https://overpass.kumi.systems/api/interpreter"]
TUE = "48.43,8.90,48.59,9.17"  # Gebiet der Stadt Tübingen samt Teilorten (großzügig)
NAMEN = [
    # Kernstadt
    "Kusterdinger Straße", "Stuttgarter Straße", "Wilhelmstraße", "Nürtinger Straße", "Dorfstraße",
    "Alberstraße", "Nordring", "Am Stadtgraben", "Mühlstraße", "Doblerstraße", "Lustnauer Tor",
    "Gartenstraße", "Kielmeyerstraße", "Eberhardsbrücke", "Westbahnhofstraße", "Belthlestraße",
    "Schleifmühleweg", "Rappstraße", "Hagellocher Weg", "Rosentalstraße", "Am Weilersbach",
    "Hegelstraße", "Derendinger Straße", "Schnarrenbergstraße", "Herrenberger Straße",
    "Schloßbergtunnel", "Schlossbergtunnel",
    # Teilorte
    "Eugen-Bolz-Straße", "Knollstraße", "Kingersheimer Straße", "Industriestraße",
    "Weinbergstraße", "Alte Landstraße", "Hauptstraße", "Rottenburger Straße",
]
ABFRAGEN = {
    "tuebingen": "[out:json][timeout:170];(" + "".join(
        f'way["highway"]["name"="{n}"]({TUE});' for n in NAMEN) + (
        f'way["highway"]["ref"~"^(L 370|B 296|B 28|L 371)$"]({TUE});'
        'way["tunnel"]["highway"](48.505,9.03,48.53,9.07);'
        f'node["place"]({TUE});'
        f'node["traffic_sign"~"city_limit"]({TUE});'
        'way["landuse"="cemetery"](48.48,9.00,48.53,9.09);'
        'way["amenity"="grave_yard"](48.48,9.00,48.53,9.09);'
        'way["amenity"="parking"](48.50,8.92,48.54,9.00);'
        ");out body geom;"),
    "martinsmoos": ('[out:json][timeout:170];(way["highway"](48.630,8.610,48.668,8.672);'
                    'node["traffic_sign"~"city_limit"](48.60,8.60,48.70,8.75);'
                    'node["place"](48.60,8.60,48.70,8.75););out body geom;'),
}
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def overpass(name, abfrage, runden=8):
    daten = urllib.parse.urlencode({"data": abfrage}).encode()
    for runde in range(runden):
        for url in SERVER:
            try:
                inhalt, _, _ = R.oeffne(url, daten=daten, zeit=200, grenze=60_000_000)
                d = json.loads(inhalt)
                if d.get("remark") and not d.get("elements"):
                    raise ValueError(d["remark"][:150])
                log(name, "Runde", runde + 1, url, len(d.get("elements", [])), "Elemente")
                return d, url
            except R.Gesperrt:
                log(name, "gesperrt", url)
            except Exception as e:  # noqa: BLE001
                log(name, "Runde", runde + 1, url, "Fehler", repr(e)[:150])
            time.sleep(5)
        time.sleep(min(30 * (runde + 1), 150))
    return None, None


def main():
    ergebnis = {}
    for name, abfrage in ABFRAGEN.items():
        d, url = overpass(name, abfrage)
        ergebnis[name] = {"server": url, "osm": d}
        (ZIEL / f"{name}.json").write_text(json.dumps(d, ensure_ascii=False) if d else "null")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")
    print(json.dumps({k: (v["server"], len((v["osm"] or {}).get("elements", [])))
                      for k, v in ergebnis.items()}))


if __name__ == "__main__":
    main()
