"""BW, Kurzzeitzählungen ohne Lizenz – Lage, dritter Versuch: erst Photon (Suche der Karte, ohne
Schlüssel) für die ungefähre Lage jeder Straße, dann Overpass in kleinen Ausschnitten (Straße und
Querstraße samt Geometrie), dazu Ortstafeln in Neubulach. Nur was robots.txt erlaubt.

Aufruf: python3 tools/bw_ol3.py ergebnis/bw/ol3
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
PHOTON = "https://photon.komoot.io/api/?{}"
SERVER = ["https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass.private.coffee/api/interpreter"]
# (Kennung, Ort für die Suche, Straße, Querstraßen bzw. Bezugspunkte)
ZIELE = [
    ("kusterdinger", "Tübingen", "Kusterdinger Straße", []),
    ("adler", "Tübingen", "Stuttgarter Straße", ["Wilhelmstraße", "Nürtinger Straße", "Dorfstraße"]),
    ("nordring", "Tübingen", "Nordring", ["Wilhelmstraße"]),
    ("lustnauer_tor", "Tübingen", "Am Stadtgraben", ["Wilhelmstraße", "Mühlstraße", "Doblerstraße", "Lustnauer Tor"]),
    ("muehlstrasse", "Tübingen", "Mühlstraße", ["Eberhardsbrücke", "Neckarbrücke"]),
    ("gartenstrasse", "Tübingen", "Gartenstraße", ["Kielmeyerstraße"]),
    ("westbahnhof", "Tübingen", "Westbahnhofstraße", ["Belthlestraße"]),
    ("schleifmuehle", "Tübingen", "Schleifmühleweg", ["Rappstraße"]),
    ("hagellocher", "Tübingen", "Hagellocher Weg", ["Rosentalstraße", "Am Weilersbach"]),
    ("hegel", "Tübingen", "Hegelstraße", ["Derendinger Straße"]),
    ("schnarrenberg", "Tübingen", "Schnarrenbergstraße", ["Herrenberger Straße"]),
    ("tunnel", "Tübingen", "Schloßbergtunnel", []),
    ("buehl", "Tübingen-Bühl", "Eugen-Bolz-Straße", ["Knollstraße"]),
    ("hirschau", "Tübingen-Hirschau", "Kingersheimer Straße", ["Industriestraße"]),
    ("weilheim", "Tübingen-Weilheim", "Weinbergstraße", ["Alte Landstraße"]),
    ("unterjesingen", "Tübingen-Unterjesingen", "Hauptstraße", ["Rottenburger Straße"]),
    ("k3", "Neubulach-Martinsmoos", "Wildbader Straße", []),
]
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def photon(q):
    url = PHOTON.format(urllib.parse.urlencode({"q": q, "limit": 5, "lang": "de"}))
    try:
        inhalt, _, _ = R.oeffne(url, zeit=60)
        return json.loads(inhalt)
    except Exception as e:  # noqa: BLE001
        log("Photon Fehler", q, repr(e)[:150])
        return None


def overpass(abfrage):
    for url in SERVER:
        try:
            inhalt, _, _ = R.oeffne(url, daten=urllib.parse.urlencode({"data": abfrage}).encode(),
                                   zeit=120, grenze=30_000_000)
            return json.loads(inhalt), url
        except Exception as e:  # noqa: BLE001
            log("  Overpass Fehler", url, repr(e)[:120])
            time.sleep(3)
    return None, None


def main():
    ergebnis = {}
    for kennung, ort, strasse, quer in ZIELE:
        p = photon(f"{strasse}, {ort}")
        ergebnis[kennung] = {"photon": p}
        if not p or not p.get("features"):
            log(kennung, "Photon: nichts")
            continue
        f = p["features"][0]
        lon, lat = f["geometry"]["coordinates"]
        ext = f["properties"].get("extent")  # [minlon, maxlat, maxlon, minlat]
        if ext:
            s, w, n, e = ext[3] - 0.004, ext[0] - 0.006, ext[1] + 0.004, ext[2] + 0.006
        else:
            s, w, n, e = lat - 0.008, lon - 0.012, lat + 0.008, lon + 0.012
        namen = "|".join([strasse] + quer)
        abfrage = (f'[out:json][timeout:60];(way["highway"]["name"~"^({namen})$"]({s},{w},{n},{e});'
                   f'way["highway"]["bridge"="yes"]({s},{w},{n},{e});'
                   f'way["highway"]["tunnel"="yes"]({s},{w},{n},{e});'
                   f'node["traffic_sign"~"city_limit"]({s},{w},{n},{e}););out tags geom;')
        d, url = overpass(abfrage)
        ergebnis[kennung]["bbox"] = [s, w, n, e]
        ergebnis[kennung]["osm"] = d
        log(kennung, f"Photon {f['properties'].get('name')} {f['properties'].get('city') or f['properties'].get('county')}",
            f"({lon:.5f}, {lat:.5f})", "Overpass:", url, len((d or {}).get("elements", [])))
        time.sleep(2)
    # Neubulach: Martinsmoos und Ortstafeln im ganzen Gebiet
    d, url = overpass('[out:json][timeout:90];(way["highway"](48.605,8.645,48.635,8.69);'
                      'node["traffic_sign"~"city_limit"](48.60,8.62,48.69,8.74););out tags geom;')
    ergebnis["neubulach_sued"] = {"osm": d}
    log("neubulach_sued", url, len((d or {}).get("elements", [])))
    (ZIEL / "lage.json").write_text(json.dumps(ergebnis, ensure_ascii=False))
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
