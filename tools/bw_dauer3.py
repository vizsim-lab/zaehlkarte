"""BW, dritter Probelauf: die Jahresarchive 2016–2024 der Landes-Dauerzählstellen (ZIP je Jahr,
rund 50 MB) – Aufbau, Kopfzeilen, Spalten, Kennungen, Statuskennung, Umstelltage, vollständige
Tage je Richtung; ganze CSV einiger Stellen zum Nachlesen. Nur was robots.txt erlaubt.

Aufruf: python3 tools/bw_dauer3.py ergebnis/bw/dauer3 2016 2020 2024
"""

import collections
import io
import json
import pathlib
import re
import statistics
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/bw/dauer3")
JAHRE = sys.argv[2:] or ["2016", "2024"]
ZIEL.mkdir(parents=True, exist_ok=True)
VM = "https://mobidata-bw.de/vm/Stundenwerte_Dauerzaehlstellen_BW"
GUT = set("-u")
PROBE = {"62228202", "64168161", "73148035", "62221202", "64161001"}  # Rosenmühle, A 6, A 5
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def text(b: bytes) -> str:
    for enc in ("utf-8", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("latin-1")


def auswerten(jahr: str, z: zipfile.ZipFile) -> dict:
    namen = z.namelist()
    aus = {"jahr": jahr, "eintraege": len(namen), "namen": namen[:40], "endungen":
           dict(collections.Counter(pathlib.PurePosixPath(n).suffix for n in namen)),
           "ordner": dict(collections.Counter(n.split("/")[0] for n in namen).most_common(30))}
    aufbau, kennungen, status, kodierung = (collections.Counter() for _ in range(4))
    tage = collections.Counter()
    umstell = collections.defaultdict(list)
    koepfe, fehler = [], []
    for n in namen:
        if n.endswith("/"):
            continue
        roh = z.read(n)
        if n.lower().endswith(".zip"):
            aus.setdefault("innere_zip", []).append(n)
            continue
        t = text(roh)
        kodierung["utf-8" if t == roh.decode("utf-8", "replace") else "andere"] += 1
        zeilen = t.splitlines()
        if len(zeilen) < 5 or ";" not in zeilen[0]:
            fehler.append((n, zeilen[:3]))
            continue
        k1, k2, k3, sp = (zeilen[i].split(";") for i in range(4))
        stelle = k1[0].strip().zfill(4) + k1[1].strip().zfill(4)
        if len(koepfe) < 400:
            koepfe.append({"datei": n, "kopf": zeilen[:4]})
        if stelle in PROBE or any(p in n for p in PROBE):
            (ZIEL / f"probe_{jahr}_{pathlib.PurePosixPath(n).name}").write_text(t)
        try:
            n1, n2 = int(k2[0]), int(k2[1])
            spalten = [s for s in sp if s]
            idx = {s: i for i, s in enumerate(spalten)}
            gr = [k3[2 + j].strip() for j in range(int(k3[0]))]
        except Exception as e:  # noqa: BLE001
            fehler.append((n, repr(e)[:100]))
            continue
        aufbau[(f"{n1}+{n2}", ";".join(gr), len(spalten))] += 1
        je_tag = collections.defaultdict(lambda: {1: 0, 2: 0})
        for z_ in zeilen[4:]:
            f = z_.split(";")
            if len(f) < 3 or not f[0].strip():
                continue
            d, st = f[0][:6], f[0][6:]
            status[st] += 1
            for g in gr:
                for s in range(1, n1 + n2 + 1):
                    k = f[idx.get(f"K_{g}FS{s}", -1)] if f"K_{g}FS{s}" in idx else "<fehlt>"
                    kennungen[(g, k)] += 1
            for r, spuren in ((1, range(1, n1 + 1)), (2, range(n1 + 1, n1 + n2 + 1))):
                if st == "" and all(f[idx[f"K_KFZFS{s}"]] in GUT for s in spuren):
                    je_tag[d][r] += 1
            if f[1] in ("02:00", "03:00", "04:00"):
                try:
                    umstell[(d, f[1])].append(sum(int(f[idx[f"KFZFS{s}"]]) for s in range(1, n1 + n2 + 1)))
                except ValueError:
                    pass
        for d, rr in je_tag.items():
            for r in (1, 2):
                tage["mit_stunde"] += 1
                tage[str(rr[r]) if rr[r] >= 23 else "weniger"] += 1
    aus.update({"aufbau": {"|".join(map(str, k)): v for k, v in aufbau.most_common()},
                "kennungen": {"|".join(k): v for k, v in sorted(kennungen.items())},
                "status": dict(status), "kodierung": dict(kodierung), "tage_je_richtung": dict(tage),
                "fehler": fehler[:20], "koepfe": koepfe})
    sonntage = sorted({d for d, _ in umstell})
    aus["sonntage_02_03_04"] = {d: [round(statistics.median(umstell[(d, h)]), 1)
                                    for h in ("02:00", "03:00", "04:00") if umstell.get((d, h))]
                               for d in sonntage if d[2:4] in ("03", "10") and d[4:] >= "20"}
    return aus


def main():
    for jahr in JAHRE:
        url = f"{VM}/Stundenwerte_{jahr}.zip"
        try:
            inhalt, _, _ = R.oeffne(url, zeit=600, grenze=90_000_000)
        except Exception as e:  # noqa: BLE001
            log(jahr, "Fehler:", repr(e)[:200])
            continue
        log(jahr, len(inhalt), "Bytes")
        z = zipfile.ZipFile(io.BytesIO(inhalt))
        innen = [n for n in z.namelist() if n.lower().endswith(".zip")]
        if innen:  # ZIP aus Monats-ZIPs: jedes Monats-ZIP auswerten
            log(jahr, "innere ZIPs:", innen[:14])
            for n in innen[:12]:
                aus = auswerten(f"{jahr}_{pathlib.PurePosixPath(n).stem}",
                                zipfile.ZipFile(io.BytesIO(z.read(n))))
                (ZIEL / f"auswertung_{jahr}_{pathlib.PurePosixPath(n).stem}.json").write_text(
                    json.dumps(aus, ensure_ascii=False, indent=1))
        else:
            aus = auswerten(jahr, z)
            (ZIEL / f"auswertung_{jahr}.json").write_text(json.dumps(aus, ensure_ascii=False, indent=1))
            log(jahr, "Aufbau:", json.dumps(aus["aufbau"], ensure_ascii=False)[:600])
            log(jahr, "Status:", aus["status"], "Tage:", aus["tage_je_richtung"])
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
