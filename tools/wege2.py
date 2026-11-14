"""Muster der erlaubten Wege für die Umstellung der Pipeline holen (robots.txt nach RFC 9309,
tools/robots.py): DCAT-Dokumente (JSON-LD) und HTML-Seiten der CKAN-Portale von Moers, Olpe und
Aachen, dazu robots.txt von Geofabrik. Nur Metadaten, keine Messdateien.

Ablage: <ziel>/roh/<nr>_<name> (höchstens 3 MB je Abruf) und <ziel>/wege2.json.
Aufruf: python3 tools/wege2.py ergebnis/wege2
"""

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/wege2")
NR0 = int(sys.argv[2]) if len(sys.argv) > 2 else 0
(ZIEL / "roh").mkdir(parents=True, exist_ok=True)

OLPE = "https://opendata.olpe.de"
ODP = "https://www.offenesdatenportal.de"
AC = "https://offenedaten.aachen.de"
AC_DS = AC + "/dataset/c81cc173-5302-45d9-9b9d-87bea105f77e/resource/"
ABRUFE = [
    ("olpe_honigsack.html", OLPE + "/dataset/verkehrsmessung-standort-zum-honigsack-35"),
    ("olpe_gunsestrabe.html", OLPE + "/dataset/verkehrsmessungen-gunsestrabe"),
    ("olpe_hatzenbergstrabe.html", OLPE + "/dataset/verkehrsmessungen-hatzenbergstrabe"),
    ("olpe_in_der_wuste.html", OLPE + "/dataset/verkehrsmessungen-in-der-wuste"),
    ("olpe_rochusstrabe.html", OLPE + "/dataset/verkehrsmessungen-rochusstrabe"),
]
NUR_ROBOTS = []
PIPELINE = ("zaehlkarte-pipeline", "*")


def main():
    aus = []
    for i, (name, url) in enumerate(ABRUFE):
        r = R.regeln(url)
        e = {"name": name, "url": url, "pipeline": all(r.erlaubt(k, url) for k in PIPELINE),
             "werkzeug": R.erlaubt(url)}
        if e["werkzeug"]:
            try:
                inhalt, end, typ = R.oeffne(url, zeit=90, grenze=3_000_000)
                (ZIEL / "roh" / f"{NR0 + i:02d}_{name}").write_bytes(inhalt)
                e |= {"end": end, "typ": typ, "bytes": len(inhalt)}
                text = inhalt.decode("utf-8", "replace")
                e["dataset_links"] = sorted(set(re.findall(r'href="(/dataset/[^"/?#]+)"', text)))[:60]
            except Exception as ex:  # noqa: BLE001
                e["fehler"] = repr(ex)[:200]
        aus.append(e)
        print(name, e.get("bytes"), e.get("fehler", ""), flush=True)
    for url in NUR_ROBOTS:
        r = R.regeln(url)
        aus.append({"url": url, "pipeline": all(r.erlaubt(k, url) for k in PIPELINE),
                    "werkzeug": R.erlaubt(url), "robots": R.TEXTE.get(R._basis(url))})
    (ZIEL / f"wege2_{NR0}.json").write_text(json.dumps(aus, ensure_ascii=False, indent=1))
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
