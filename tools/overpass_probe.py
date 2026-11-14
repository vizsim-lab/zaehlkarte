"""Overpass-Server für die Straßennamen der Pipeline prüfen: robots.txt (Werkzeug-Kennungen samt
Claude und Pipeline), Antwortzeit für eine kleine Umkreis-Abfrage per GET und POST.
Aufruf: python3 tools/overpass_probe.py ergebnis/overpass_probe
"""

import json
import pathlib
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/overpass_probe")
ZIEL.mkdir(parents=True, exist_ok=True)
SERVER = ["https://overpass.kumi.systems/api/interpreter",
          "https://overpass.private.coffee/api/interpreter",
          "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
ABFRAGE = ('[out:json][timeout:25];(way(around:50,53.600400,10.005000)["highway"]["name"];'
           'way(around:50,53.551100,9.993700)["highway"]["name"];);out geom;')
PIPELINE = ("zaehlkarte-pipeline", "*")


def main():
    aus = []
    for url in SERVER:
        r = R.regeln(url)
        e = {"server": url, "werkzeug": R.erlaubt(url),
             "pipeline": all(r.erlaubt(k, url) for k in PIPELINE)}
        for weg in ("GET", "POST"):
            ziel = url + "?" + urllib.parse.urlencode({"data": ABFRAGE}) if weg == "GET" else url
            if not R.erlaubt(ziel):
                e[weg] = "gesperrt"
                continue
            t0 = time.time()
            try:
                daten = urllib.parse.urlencode({"data": ABFRAGE}).encode() if weg == "POST" else None
                inhalt, end, typ = R.oeffne(ziel, daten=daten, zeit=90, grenze=5_000_000)
                j = json.loads(inhalt)
                namen = sorted({el.get("tags", {}).get("name") for el in j.get("elements", [])})
                e[weg] = {"s": round(time.time() - t0, 1), "typ": typ, "wege": len(j["elements"]),
                          "namen": namen[:8], "bemerkung": j.get("remark")}
            except Exception as ex:  # noqa: BLE001
                e[weg] = {"s": round(time.time() - t0, 1), "fehler": repr(ex)[:300]}
        aus.append(e)
        print(json.dumps(e, ensure_ascii=False), flush=True)
    (ZIEL / "overpass.json").write_text(json.dumps(aus, ensure_ascii=False, indent=1))
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
