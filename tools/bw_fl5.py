"""Erkundung (15.11.2026), Teil 5: Dauerzählstellen in Bayern (BAYSIS) – Freigabe der
Projektleitung am 15.11.2026 („die will ich!“), die Werte über die Schnittstelle zu holen, über die
die öffentliche Seite „Dauerzählstellen“ sie lädt (`POST /services/apiDAUZ/api/DAUZ`, JSON mit
`zaehlstellennummer` und `abfrageArt`, laut baysis.js). Die Mobilithek (798871611185745920) nennt
diese Seite als Zugang, Nutzungsbedingungen GeoNutzV.

Hier nur das Format: je eine Zählstelle an einer Staats- und einer Kreisstraße, Stammdaten,
Verfügbarkeit, Stunden- und Tageswerte (ohne und mit Zeitraum); dazu die Lage aus dem ArcGIS-Dienst
und das Impressum. Höflich: zwei Sekunden zwischen den Anfragen.

Aufruf: python3 tools/bw_fl5.py ergebnis/bw/fl5
"""

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
API = "https://www.baysis.bayern.de/services/apiDAUZ/api/DAUZ"
GIS = ("https://gisportal-stmb.bayern.de/server/rest/services/WMS/BAYSIS_Verkehrsdaten/MapServer/0/"
       "query?where=1%3D1&outFields=Zaehlstellennummer,Strassenbezeichnung,Strassenklasse,Status"
       "&returnGeometry=true&outSR=4326&f=geojson")
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def frage(name, nutzlast):
    daten = json.dumps(nutzlast, ensure_ascii=False).encode("utf-8")
    try:
        inhalt, _, art = R.oeffne(API, daten=daten, kopf={"Content-Type": "application/json",
                                                          "Accept": "application/json"},
                                  zeit=180, grenze=80_000_000)
        log(name, "ok", len(inhalt), art)
        (ZIEL / f"{name}.json").write_bytes(inhalt)
        try:
            kurz = json.dumps(json.loads(inhalt), ensure_ascii=False)[:2500]
        except ValueError:
            kurz = inhalt[:800].decode("utf-8", "replace")
        aus = f"## {name} {json.dumps(nutzlast, ensure_ascii=False)} ({len(inhalt)} Byte)\n{kurz}\n"
    except Exception as e:  # noqa: BLE001
        log(name, "Fehler", repr(e)[:200])
        aus = f"## {name} {json.dumps(nutzlast, ensure_ascii=False)}\nFehler {e!r}"[:600] + "\n"
    time.sleep(2)
    return aus


def main():
    aus = []
    st, k = "9639", "9648"  # St 2406, K M 15 (Ebene „dauerzaehlstellen“ des ArcGIS-Diensts)
    for z in (st, k):
        for art in ("stammdaten", "verfügbarkeit"):
            aus.append(frage(f"{z}_{art}", {"zaehlstellennummer": z, "abfrageArt": art}))
    aus.append(frage(f"{st}_stundenwerte", {"zaehlstellennummer": st, "abfrageArt": "stundenwerte"}))
    aus.append(frage(f"{st}_tagwerte", {"zaehlstellennummer": st, "abfrageArt": "tagwerte"}))
    for name, von, bis in (("iso", "2025-10-20", "2025-10-27"), ("de", "20.10.2025", "27.10.2025")):
        aus.append(frage(f"{st}_stunden_{name}", {"zaehlstellennummer": st, "abfrageArt": "stundenwerte",
                                                  "vonDatum": von, "bisDatum": bis}))
    aus.append(frage(f"{st}_tage_jahr", {"zaehlstellennummer": st, "abfrageArt": "tagwerte",
                                         "vonDatum": "2024-01-01", "bisDatum": "2024-12-31"}))
    for url, name in ((GIS, "lage.geojson"),
                      ("https://www.baysis.bayern.de/internet/impressum/index.html", "impressum.html")):
        try:
            inhalt, _, _ = R.oeffne(url, zeit=90, grenze=20_000_000)
            (ZIEL / name).write_bytes(inhalt)
            log("ok", url, len(inhalt))
        except Exception as e:  # noqa: BLE001
            log("Fehler", url, repr(e)[:200])
        time.sleep(2)
    (ZIEL / "antworten.txt").write_text("\n".join(aus), encoding="utf-8")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    with open(ZIEL / "log.txt", "a") as f:
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
