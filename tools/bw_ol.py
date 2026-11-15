"""BW, Kurzzeitzählungen ohne Lizenz: Tübingen (Vorlage 242/2022 samt Anlagen) und die Straßen
von Tübingen und Neubulach aus OpenStreetMap (Overpass) für die Lage der Zählstellen. Nur was
robots.txt erlaubt (tools/robots.py).

Aufruf: python3 tools/bw_ol.py ergebnis/bw/ol
"""

import json
import pathlib
import subprocess
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
LOG = []
TUE = "https://www.tuebingen.de/gemeinderat/getfile.asp?id={}&type=do"
PDFS = {"81381": "tuebingen_vorlage.pdf", "81457": "tuebingen_anlage1.pdf",
        "81458": "tuebingen_anlage2.pdf", "81490": "tuebingen_anlage3.pdf"}
NEUBULACH = "https://www.neubulach.de/ceasy/resource/?download=1&id=3956"
SERVER = ["https://overpass.private.coffee/api/interpreter",
          "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
          "https://overpass-api.de/api/interpreter"]
# Straßen (Ausschnitt): Tübingen Kernstadt und Teilorte, Neubulach mit Ortsteilen
ABFRAGEN = {
    "tuebingen": """[out:json][timeout:120];
(way["highway"]["name"](48.47,8.94,48.56,9.13);
 way["highway"]["ref"~"^(B|L|K) "](48.47,8.94,48.56,9.13);
 way["tunnel"](48.50,9.03,48.53,9.07);
 way["bridge"]["highway"](48.50,9.03,48.53,9.08););
out tags geom;""",
    "neubulach": """[out:json][timeout:120];
(way["highway"](48.63,8.66,48.69,8.73););
out tags geom;""",
}
FUSSANGABEN = ["Adler", "Lustnauer Tor", "Nordring", "Neckarbrücke"]


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def hole(url, datei, grenze=40_000_000):
    try:
        inhalt, end, typ = R.oeffne(url, zeit=180, grenze=grenze)
    except Exception as e:  # noqa: BLE001
        log("Fehler", url, repr(e)[:200])
        return None
    (ZIEL / datei).write_bytes(inhalt)
    log(datei, len(inhalt), typ, end)
    if datei.endswith(".pdf"):
        subprocess.run(["pdftotext", "-layout", str(ZIEL / datei), str(ZIEL / (datei + ".txt"))],
                       check=False)
    return inhalt


def overpass(name, abfrage):
    for url in SERVER:
        try:
            inhalt, _, _ = R.oeffne(url, daten=urllib.parse.urlencode({"data": abfrage}).encode(),
                                   zeit=200, grenze=80_000_000)
            d = json.loads(inhalt)
            (ZIEL / f"osm_{name}.json").write_text(json.dumps(d, ensure_ascii=False))
            log("Overpass", name, url, len(d.get("elements", [])), "Wege")
            return
        except Exception as e:  # noqa: BLE001
            log("Overpass Fehler", name, url, repr(e)[:200])


def main():
    for nr, datei in PDFS.items():
        hole(TUE.format(nr), datei)
    hole(NEUBULACH, "neubulach_kurzbericht.pdf")
    for name, abfrage in ABFRAGEN.items():
        overpass(name, abfrage)
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
