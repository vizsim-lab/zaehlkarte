"""BW, Kurzzeitzählungen ohne Lizenz – Lage: gezielte Overpass-Abfragen (kleine Ausschnitte):
Tübingen (Straßen der Zählstellen samt Teilorten, Tunnel, Brücken) und Neubulach (Martinsmoos,
Ortstafeln). Nur was robots.txt erlaubt.

Aufruf: python3 tools/bw_ol2.py ergebnis/bw/ol
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
          "https://overpass.private.coffee/api/interpreter"]
TUE_NAMEN = ("Kusterdinger Straße|Stuttgarter Straße|Nürtinger Straße|Dorfstraße|Wilhelmstraße|"
             "Nordring|Am Stadtgraben|Mühlstraße|Doblerstraße|Lustnauer Tor|Gartenstraße|"
             "Kielmeyerstraße|Eberhardsbrücke|Neckarbrücke|Westbahnhofstraße|Belthlestraße|"
             "Schleifmühleweg|Rappstraße|Hagellocher Weg|Rosentalstraße|Am Weilersbach|Hegelstraße|"
             "Derendinger Straße|Schnarrenbergstraße|Herrenberger Straße|Eugen-Bolz-Straße|"
             "Knollstraße|Kingersheimer Straße|Industriestraße|Weinbergstraße|Alte Landstraße|"
             "Hauptstraße|Rottenburger Straße|Schloßbergtunnel|Schlossbergtunnel|Bühler Straße")
ABFRAGEN = {
    "tuebingen_strassen": f"""[out:json][timeout:150];
way["highway"]["name"~"^({TUE_NAMEN})$"](48.45,8.92,48.56,9.12);
out tags geom;""",
    "tuebingen_l370_tunnel": """[out:json][timeout:150];
(way["highway"]["ref"~"^(L 370|B 296|B 28|B 27)$"](48.47,8.95,48.53,9.08);
 way["highway"]["tunnel"="yes"](48.49,9.03,48.53,9.07););
out tags geom;""",
    "neubulach_sued": """[out:json][timeout:150];
(way["highway"](48.60,8.64,48.635,8.70);
 node["traffic_sign"~"city_limit"](48.60,8.62,48.69,8.74););
out tags geom;""",
}


def main():
    log = []
    for name, abfrage in ABFRAGEN.items():
        for url in SERVER:
            try:
                inhalt, _, _ = R.oeffne(url, daten=urllib.parse.urlencode({"data": abfrage}).encode(),
                                       zeit=200, grenze=80_000_000)
                d = json.loads(inhalt)
                (ZIEL / f"osm_{name}.json").write_text(json.dumps(d, ensure_ascii=False))
                log.append(f"{name} {url} {len(d.get('elements', []))}")
                break
            except Exception as e:  # noqa: BLE001
                log.append(f"{name} {url} Fehler {repr(e)[:150]}")
            time.sleep(5)
        print(log[-1], flush=True)
    (ZIEL / "log2.txt").write_text("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
