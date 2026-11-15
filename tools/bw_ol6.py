"""BW, Kurzzeitzählungen ohne Lizenz – Lage, sechster Versuch: kleine Abfragen für das, was nach
ol4 offen ist (Adlerkreuzung, Bonlanden), reihum über die erlaubten Overpass-Server und
mit kurzer Wartezeit je Versuch, damit ein überlasteter Server nicht den ganzen Lauf aufhält.
Abfragen, die schon ein Ergebnis haben (ergebnis/bw/ol6/teile/*.json), werden übersprungen.
OpenFreeMap-Kacheln und Photon sperrt robots.txt für Robots (ol3, ol5).

Aufruf: python3 tools/bw_ol6.py ergebnis/bw/ol6
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
TUE = "48.43,8.90,48.59,9.17"
# ol4 hat die Straßen geliefert; offen sind nur Namen von Orten und Kreuzungen
ABFRAGEN = {
    # „Adlerkreuzung“ in Lustnau: Haltestellen, Gasthaus, Kreuzung mit „Adler“ im Namen
    "adler": ('[out:json][timeout:60];(node["name"~"Adler"](48.515,9.06,48.545,9.10);'
              'way["name"~"Adler"](48.515,9.06,48.545,9.10););out body geom;'),
    # „westl. Bonlanden“ in Bühl
    "bonlanden": (f'[out:json][timeout:60];(node["name"~"Bonlanden"]({TUE});'
                  f'way["name"~"Bonlanden"]({TUE}););out body geom;'),
    # alle Straßen um die Kreuzung Wilhelmstraße/Stuttgarter Straße (Nordarm)
    "lustnau": ('[out:json][timeout:60];(way["highway"](48.5260,9.0740,48.5330,9.0820););'
                'out body geom;'),
    # Neckar und Bahn an den Brücken der Kusterdinger Straße
    "neckar_lustnau": ('[out:json][timeout:60];(way["waterway"~"^(river|canal)$"]'
                       '(48.518,9.085,48.530,9.100);way["railway"="rail"](48.518,9.085,48.530,9.100););'
                       'out body geom;'),
    # Hauptstraßen in Unterjesingen (der Name der Ortsdurchfahrt fehlt in ol4)
    "unterjesingen": ('[out:json][timeout:60];(way["highway"~"^(primary|secondary|tertiary|trunk)'
                      '(_link)?$"](48.518,8.955,48.535,9.000););out body geom;'),
}
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def versuch(name, abfrage, url):
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
                d = versuch(name, ABFRAGEN[name], url)
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
