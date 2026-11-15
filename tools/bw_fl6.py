"""Erkundung (15.11.2026), Teil 6: Dauerzählstellen in Bayern (BAYSIS) an Staats- und
Kreisstraßen – Stammdaten, Verfügbarkeit und Lage aller 80 Zählstellen, dazu, wie weit die
Stundenwerte zurückreichen und wie lange ein Jahr dauert (Freigabe der Projektleitung am
15.11.2026).

- Liste: ArcGIS-Ebene „dauerzaehlstellen“ (Strassenklasse St oder K).
- Stammdaten und Verfügbarkeit: `POST /services/apiDAUZ/api/DAUZ` wie die Seite „Dauerzählstellen“.
- Lage: Straße, Abschnitt und Station über den öffentlichen Dienst SibPublic (Stationssuche), den
  die BAYSIS-Anwendung dafür nutzt; die ArcGIS-Ebene liefert keine Geometrie.
- Zeitraum: Stundenwerte einer Zählstelle für eine Woche 2019 und 2022 und für ein ganzes Jahr
  (2025), mit Dauer und Größe.
Höflich: zwei Sekunden zwischen den Anfragen.

Aufruf: python3 tools/bw_fl6.py ergebnis/bw/fl6
"""

import json
import pathlib
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
(ZIEL / "stamm").mkdir(parents=True, exist_ok=True)
API = "https://www.baysis.bayern.de/services/apiDAUZ/api/DAUZ"
GIS = ("https://gisportal-stmb.bayern.de/server/rest/services/WMS/BAYSIS_Verkehrsdaten/MapServer/0/"
       "query?where=1%3D1&outFields=*&returnGeometry=false&f=json")
SIB = "https://gisportal-stmb.bayern.de/server/rest/services/SibPublic/MapServer/exts/SibPublic/Stationssuche"
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def post(nutzlast, zeit=300):
    daten = json.dumps(nutzlast, ensure_ascii=False).encode("utf-8")
    t0 = time.time()
    inhalt, _, _ = R.oeffne(API, daten=daten, kopf={"Content-Type": "application/json",
                                                    "Accept": "application/json"},
                            zeit=zeit, grenze=200_000_000)
    time.sleep(2)
    return inhalt, time.time() - t0


def main():
    liste = json.loads(R.oeffne(GIS, zeit=90)[0])
    stellen = [f["attributes"] for f in liste["features"]
               if f["attributes"].get("Strassenklasse") in ("St", "K")]
    (ZIEL / "liste.json").write_text(json.dumps(stellen, ensure_ascii=False, indent=1))
    log(len(stellen), "Zählstellen an Staats- und Kreisstraßen")
    ergebnis = {}
    for a in stellen:
        nr = str(a["Zaehlstellennummer"])
        e = ergebnis[nr] = {"liste": a}
        for art in ("stammdaten", "verfügbarkeit"):
            try:
                inhalt, dauer = post({"zaehlstellennummer": nr, "abfrageArt": art})
                d = json.loads(inhalt)
                (ZIEL / "stamm" / f"{nr}_{art}.json").write_bytes(inhalt)
                if art == "stammdaten":
                    e["stamm"] = {k: v.get("wert") for k, v in (d[0] if d else {}).items()
                                  if isinstance(v, dict)}
                else:
                    monate = [r["datum"]["wert"] for r in d]
                    e["monate"] = [monate[-1], monate[0], len(monate)] if monate else []
            except Exception as ex:  # noqa: BLE001
                e[art] = repr(ex)[:200]
                log(nr, art, "Fehler", repr(ex)[:150])
        s = e.get("stamm") or {}
        strasse = (s.get("strasse") or a.get("Strassenbezeichnung") or "").replace(" ", "")
        station = (s.get("station") or "").replace(",", ".")
        abschnitt = s.get("abschnitt") or a.get("AoANummer") or ""
        q = urllib.parse.urlencode({"station": station, "strassenBezeichnung": strasse,
                                    "abschnitt": abschnitt, "f": "pjson"})
        try:
            inhalt, _, _ = R.oeffne(f"{SIB}?{q}", zeit=60)
            e["lage"] = json.loads(inhalt)
        except Exception as ex:  # noqa: BLE001
            e["lage"] = repr(ex)[:200]
        time.sleep(1)
        log(nr, s.get("strasse"), s.get("zaehlstellenbezeichnug"), e.get("monate"),
            json.dumps(e.get("lage"), ensure_ascii=False)[:160])
    (ZIEL / "stellen.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1))
    # Zeitraum und Aufwand an einer Zählstelle
    zeit = []
    for name, von, bis in (("2019_woche", "2019-06-03", "2019-06-09"),
                           ("2022_woche", "2022-12-26", "2023-01-08"),
                           ("2025_jahr", "2025-01-01", "2025-12-31")):
        try:
            inhalt, dauer = post({"zaehlstellennummer": "9639", "abfrageArt": "stundenwerte",
                                  "vonDatum": von, "bisDatum": bis}, zeit=900)
            d = json.loads(inhalt)
            tage = sorted({r["datum"]["wert"][6:] + r["datum"]["wert"][3:5] + r["datum"]["wert"][:2]
                           for r in d})
            zeit.append(f"{name}: {len(d)} Zeilen, {len(inhalt)} Byte, {dauer:.1f} s, "
                        f"Tage {tage[:1]} … {tage[-1:]}")
            if name != "2025_jahr":
                (ZIEL / f"9639_{name}.json").write_bytes(inhalt)
        except Exception as ex:  # noqa: BLE001
            zeit.append(f"{name}: {ex!r}"[:300])
        log(zeit[-1])
    (ZIEL / "zeitraum.txt").write_text("\n".join(zeit) + "\n", encoding="utf-8")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    with open(ZIEL / "log.txt", "a") as f:
        f.write("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
