"""Werkzeug: KMK-Ferienkalender 1999/2000–2020/21 laden und als Text ablegen (pdftotext -layout),
dazu Prüfsummen der Münster-Dateien (ZIP, CSV) für sources.yaml."""

import hashlib
import json
import pathlib
import subprocess
import sys
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/ferien")
K = "https://www.kmk.org/fileadmin/Dateien/pdf/"
KMK = {
    "1999_00": "Ferienkalender/Ferien99_00.pdf",
    "2000_01": "Ferienkalender/Ferien00_01.pdf",
    "2001_02": "Ferienkalender/Ferien01_02.pdf",
    "2002_03": "Ferienkalender/Ferien02_03.pdf",
    "2003_04": "Ferienkalender/Ferien03_04.pdf",
    "2004_05": "Ferienkalender/Ferien04_05.pdf",
    "2005_06": "Ferienkalender/Ferien05_06.pdf",
    "2006_07": "Ferienkalender/Ferien06_07.pdf",
    "2007_08": "Ferienkalender/Ferien07_08.pdf",
    "2008_09": "Ferienkalender/Ferien08_09.pdf",
    "2009_10": "Ferienkalender/Ferien09_10.pdf",
    "2010_11": "Ferienkalender/Ferien2010_11.pdf",
    "2011_12": "Ferienkalender/FER2011_12.pdf",
    "2012_13": "Ferienkalender/FER2012_13.pdf",
    "2013_14": "Ferienkalender/FER2013_14.pdf",
    "2014_15": "Bildung/AllgBildung/FER2014_15.pdf",
    "2015_16": "Ferienkalender/FER2015_16.pdf",
    "2016_17": "Ferienkalender/FER2016_17_-_NEU.pdf",
    "2017_18": "Ferienkalender/FER17_18.pdf",
    "2018_19": "Ferienkalender/FER18_19.pdf",
    "2019_20": "Ferienkalender/FER19_20.pdf",
    "2020_21": "Ferienkalender/FER2020_21-neu.pdf",
}
MUENSTER = {
    "Verkehrszählung.zip": "https://opendata.stadt-muenster.de/sites/default/files/Verkehrsz%C3%A4hlung.zip",
    "Zählstellen.csv": "https://opendata.stadt-muenster.de/sites/default/files/Z%C3%A4hlstellen.csv",
}


def hole(url: str) -> bytes:
    anfrage = urllib.request.Request(url, headers={"User-Agent": "zaehlkarte-werkzeug/0.1"})
    with urllib.request.urlopen(anfrage, timeout=120) as antwort:
        return antwort.read()


ZIEL.mkdir(parents=True, exist_ok=True)
protokoll = {}
for sj, pfad in KMK.items():
    url = K + pfad
    try:
        inhalt = hole(url)
        (ZIEL / f"kmk_{sj}.pdf").write_bytes(inhalt)
        subprocess.run(["pdftotext", "-layout", str(ZIEL / f"kmk_{sj}.pdf"),
                        str(ZIEL / f"kmk_{sj}.txt")], check=False)
        protokoll[sj] = {"url": url, "bytes": len(inhalt)}
    except Exception as e:  # noqa: BLE001
        protokoll[sj] = {"url": url, "fehler": repr(e)[:200]}
for name, url in MUENSTER.items():
    try:
        inhalt = hole(url)
        protokoll[name] = {"url": url, "bytes": len(inhalt),
                           "sha256": hashlib.sha256(inhalt).hexdigest()}
    except Exception as e:  # noqa: BLE001
        protokoll[name] = {"url": url, "fehler": repr(e)[:200]}
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, indent=1, ensure_ascii=False))
print(json.dumps(protokoll, indent=1, ensure_ascii=False))
