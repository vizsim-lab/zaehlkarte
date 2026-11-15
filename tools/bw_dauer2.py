"""BW, zweiter Probelauf der Landes-Dauerzählstellen: ganze Monats-ZIPs (Umstellmonate und der
jüngste) zum Auswerten in der Sandbox, die BASt-Beschreibung des Bestandsbandformats (Kennungen,
Zeitbezug), Größe der Archive 2016–2024. Nur was robots.txt den Werkzeugen erlaubt.

Aufruf: python3 tools/bw_dauer2.py ergebnis/bw/dauer2
"""

import json
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/bw/dauer2")
(ZIEL / "zip").mkdir(parents=True, exist_ok=True)
VM = "https://mobidata-bw.de/vm/Stundenwerte_Dauerzaehlstellen_BW"
MONATE = ["202503", "202510", "202603", "202607", "202608"]
BAST = ["https://www.bast.de/DE/Publikationen/Daten/Verkehrstechnik/Downloads/DZ-Beschreibung.pdf"
        "?__blob=publicationFile",
        "https://www.bast.de/DE/Publikationen/Daten/Verkehrstechnik/DZ.html",
        "https://www.bast.de/DE/Publikationen/Daten/Verkehrstechnik/DZ-Richtung.html"]
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def kopf(url):
    """HEAD – nur, wenn robots.txt den Abruf erlaubt."""
    if not R.erlaubt(url):
        return {"gesperrt": True}
    R.warte(url)
    anfrage = urllib.request.Request(url, method="HEAD", headers={"User-Agent": R.UA})
    try:
        with R.OPENER.open(anfrage, timeout=60) as a:
            return {"status": a.status, "laenge": a.headers.get("Content-Length"),
                    "geaendert": a.headers.get("Last-Modified"), "typ": a.headers.get("Content-Type")}
    except Exception as e:  # noqa: BLE001
        return {"fehler": repr(e)[:200]}


def main():
    for m in MONATE:
        url = f"{VM}/Stundenwerte_{m}.zip"
        try:
            inhalt, _, _ = R.oeffne(url, zeit=300, grenze=40_000_000)
            (ZIEL / "zip" / f"Stundenwerte_{m}.zip").write_bytes(inhalt)
            log(m, len(inhalt), "Bytes")
        except Exception as e:  # noqa: BLE001
            log(m, "Fehler:", repr(e)[:200])
    archive = {name: kopf(f"{VM}/{name}") for name in
               ["Stundenwerte_Archiv.zip"] + [f"Stundenwerte_{j}.zip" for j in range(2016, 2025)]}
    log("Archive:", json.dumps(archive, ensure_ascii=False))
    for url in BAST:
        name = url.split("/")[-1].split("?")[0]
        if not R.erlaubt(url):
            log("BASt gesperrt:", url)
            continue
        try:
            inhalt, end, typ = R.oeffne(url, zeit=120, grenze=20_000_000)
            (ZIEL / name).write_bytes(inhalt)
            log("BASt:", name, len(inhalt), typ, end)
        except Exception as e:  # noqa: BLE001
            log("BASt Fehler:", url, repr(e)[:200])
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
