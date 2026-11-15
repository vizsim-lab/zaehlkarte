"""BW, Kurzzeitzählungen ohne Lizenz – Lage, Ausweg ohne Overpass: Vektorkacheln von OpenFreeMap
(Hintergrund der Karte, ohne Schlüssel, Daten aus OpenStreetMap) in Zoomstufe 14 für das Gebiet
der Stadt Tübingen und um Martinsmoos. Die Kacheln werden nur abgelegt; gelesen werden sie in der
Entwicklungsumgebung (Ebenen transportation und transportation_name). Nur was robots.txt erlaubt.

Aufruf: python3 tools/bw_ol5.py ergebnis/bw/ol5
"""

import json
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
(ZIEL / "kacheln").mkdir(parents=True, exist_ok=True)
TILEJSON = "https://tiles.openfreemap.org/planet"
GEBIETE = {  # (Süd, West, Nord, Ost)
    "tuebingen": (48.43, 8.90, 48.59, 9.17),
    "martinsmoos": (48.630, 8.610, 48.668, 8.672),
}
Z = 14
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def kachel(lat, lon, z=Z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    r = math.radians(lat)
    y = int((1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * n)
    return x, y


def main():
    inhalt, _, _ = R.oeffne(TILEJSON, zeit=60)
    tj = json.loads(inhalt)
    vorlage = tj["tiles"][0]
    log("TileJSON", vorlage, tj.get("attribution", "")[:120])
    (ZIEL / "tilejson.json").write_text(json.dumps(tj, ensure_ascii=False, indent=1))
    liste = {}
    for name, (s, w, n, o) in GEBIETE.items():
        x0, y0 = kachel(n, w)
        x1, y1 = kachel(s, o)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                liste[(x, y)] = name
    log(len(liste), "Kacheln")
    ok = 0
    for (x, y), name in sorted(liste.items()):
        url = vorlage.replace("{z}", str(Z)).replace("{x}", str(x)).replace("{y}", str(y))
        try:
            daten, _, typ = R.oeffne(url, zeit=60, kopf={"Accept-Encoding": "identity"})
            (ZIEL / "kacheln" / f"{Z}_{x}_{y}.pbf").write_bytes(daten)
            ok += 1
        except Exception as e:  # noqa: BLE001
            log("Fehler", x, y, repr(e)[:150])
    log(ok, "Kacheln geladen")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
