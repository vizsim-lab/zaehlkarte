"""BW: Stunden an Monatsgrenzen (2024-06/07, 2024-11/12, 2025-01) – erste und letzte Zeilen je
Datei mit Kennzeichen, Zahl der Dateien je erster/letzter Zeile. Nur was robots.txt erlaubt.

Aufruf: python3 tools/bw_rand.py ergebnis/bw/rand
"""

import collections
import io
import json
import pathlib
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
VM = "https://mobidata-bw.de/vm/Stundenwerte_Dauerzaehlstellen_BW"
aus = {}


def monat(name, z):
    erste, letzte, flags = collections.Counter(), collections.Counter(), collections.Counter()
    beispiele = []
    for n in sorted(z.namelist()):
        if not n.endswith(".csv"):
            continue
        roh = z.read(n)
        try:
            t = roh.decode("utf-8")
        except UnicodeDecodeError:
            t = roh.decode("cp1252")
        zeilen = [l for l in t.splitlines()[4:] if l.strip()]
        sp = t.splitlines()[3].split(";")
        ks = [i for i, s in enumerate(sp) if s.startswith("K_KFZFS")]
        f0, f1 = zeilen[0].split(";"), zeilen[-1].split(";")
        erste[f"{f0[0]} {f0[1]} {sorted({f0[i] for i in ks})}"] += 1
        letzte[f"{f1[0]} {f1[1]} {sorted({f1[i] for i in ks})}"] += 1
        if len(beispiele) < 3:
            beispiele.append({"datei": n, "anfang": zeilen[:2], "ende": zeilen[-2:]})
        for l in zeilen[:3] + zeilen[-3:]:
            f = l.split(";")
            flags[f"{f[1]} {sorted({f[i] for i in ks})}"] += 1
    aus[name] = {"erste": erste.most_common(8), "letzte": letzte.most_common(8),
                 "kennungen_rand": flags.most_common(12), "beispiele": beispiele}
    print(name, aus[name]["erste"][:3], aus[name]["letzte"][:3], flags.most_common(6), flags and "", flush=True)


def main():
    inhalt, _, _ = R.oeffne(f"{VM}/Stundenwerte_2024.zip", zeit=900, grenze=90_000_000)
    z = zipfile.ZipFile(io.BytesIO(inhalt))
    for n in z.namelist():
        if any(m in n for m in ("202406", "202407", "202411", "202412")):
            monat(n, zipfile.ZipFile(io.BytesIO(z.read(n))))
    inhalt, _, _ = R.oeffne(f"{VM}/Stundenwerte_202501.zip", zeit=300, grenze=40_000_000)
    monat("202501", zipfile.ZipFile(io.BytesIO(inhalt)))
    (ZIEL / "rand.json").write_text(json.dumps(aus, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
