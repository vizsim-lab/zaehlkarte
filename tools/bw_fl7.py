"""Erkundung (15.11.2026), Teil 7: BAYSIS-Dauerzählstellen an Staats- und Kreisstraßen – langsam.
Teil 6 lief nach rund 15 Anfragen in einer Minute in „Connection refused“ (bei BAYSIS und beim
GIS-Portal); hier zehn Sekunden zwischen den Anfragen und nach einer Ablehnung eine Minute Pause
(höchstens drei Versuche). Zwischenstände landen sofort in Dateien.

- Lage: die SVZ-Zählstellen 2021 aus dem WFS „BAYSIS_Verkehrsdaten“ (CC BY 4.0, mit Geometrie) –
  passt die Zählstellennummer einer SVZ-Stelle (Blatt + vier Ziffern) zur Nummer der
  Dauerzählstelle und die Straße? Dazu ein Versuch mit der ArcGIS-Operation `find`.
- Stammdaten aller 80 Zählstellen (Name, Straße, Abschnitt, Station, Richtungen, Fahrzeugarten).
- Zeitraum: Stunden einer Zählstelle für Juni 2022 und Juni 2019.

Aufruf: python3 tools/bw_fl7.py ergebnis/bw/fl7
"""

import json
import pathlib
import sys
import time
import urllib.error

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
(ZIEL / "stamm").mkdir(parents=True, exist_ok=True)
API = "https://www.baysis.bayern.de/services/apiDAUZ/api/DAUZ"
WFS = ("https://gisportal-stmb.bayern.de/server/services/WFS/BAYSIS_Verkehrsdaten/MapServer/"
       "WFSServer?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES="
       "BAYSIS_Verkehrsdaten:svz2021_zaehlstellen&OUTPUTFORMAT=GEOJSON")
FIND = ("https://gisportal-stmb.bayern.de/server/rest/services/WMS/BAYSIS_Verkehrsdaten/MapServer/"
        "find?searchText=9639&contains=false&searchFields=Zaehlstellennummer&layers=0"
        "&returnGeometry=true&sr=4326&f=json")
PAUSE = 10
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(f"{time.strftime('%H:%M:%S')} {s}")
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")


def hole(url, *, daten=None, kopf=None, zeit=300, grenze=200_000_000):
    for versuch in range(3):
        try:
            t0 = time.time()
            inhalt, _, _ = R.oeffne(url, daten=daten, kopf=kopf, zeit=zeit, grenze=grenze)
            time.sleep(PAUSE)
            return inhalt, time.time() - t0
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            log("abgelehnt", versuch + 1, url[:90], repr(e)[:120])
            time.sleep(60 * (versuch + 1))
    raise RuntimeError(f"dreimal abgelehnt: {url[:90]}")


def post(nutzlast, zeit=300):
    return hole(API, daten=json.dumps(nutzlast, ensure_ascii=False).encode("utf-8"),
                kopf={"Content-Type": "application/json", "Accept": "application/json"}, zeit=zeit)


def main():
    for name, url in (("svz2021_zaehlstellen.geojson", WFS), ("find_9639.json", FIND)):
        try:
            inhalt, dauer = hole(url, zeit=300)
            (ZIEL / name).write_bytes(inhalt)
            log("ok", name, len(inhalt), f"{dauer:.1f} s")
        except Exception as e:  # noqa: BLE001
            log("Fehler", name, repr(e)[:200])
    liste = json.loads(pathlib.Path("ergebnis/bw/fl6/liste.json").read_text())
    for a in liste:
        nr = str(a["Zaehlstellennummer"])
        ziel = ZIEL / "stamm" / f"{nr}.json"
        if ziel.exists():
            continue
        try:
            inhalt, dauer = post({"zaehlstellennummer": nr, "abfrageArt": "stammdaten"})
            ziel.write_bytes(inhalt)
            d = json.loads(inhalt)
            s = {k: v.get("wert") for k, v in (d[0] if d else {}).items() if isinstance(v, dict)}
            log(nr, f"{dauer:.1f} s", s.get("strasse"), s.get("zaehlstellenbezeichnug"),
                s.get("lkW_Unterscheidung"), s.get("status"))
        except Exception as e:  # noqa: BLE001
            log(nr, "Fehler", repr(e)[:200])
    for name, von, bis in (("2022_06", "2022-06-01", "2022-06-30"),
                           ("2019_06", "2019-06-01", "2019-06-30")):
        try:
            inhalt, dauer = post({"zaehlstellennummer": "9639", "abfrageArt": "stundenwerte",
                                  "vonDatum": von, "bisDatum": bis}, zeit=600)
            d = json.loads(inhalt)
            log(name, len(d), "Zeilen", len(inhalt), "Byte", f"{dauer:.1f} s",
                d[-1]["datum"]["wert"] if d else None, d[0]["datum"]["wert"] if d else None)
        except Exception as e:  # noqa: BLE001
            log(name, "Fehler", repr(e)[:200])
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
