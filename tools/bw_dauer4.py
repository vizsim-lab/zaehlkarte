"""BW, vierter Probelauf: alle Jahre und Monate der Landes-Dauerzählstellen (2016–heute) einmal
durchgehen – je Datei Name und Kopfzeilen (für die Zuordnung zur Zählstellenkarte), Kennungen
und Statuskennung je Monat, die Stunden an den Umstelltagen, vollständige Tage je Richtung,
doppelte Stellen in einem Monat, Kodierung. Nur was robots.txt erlaubt (Crawl-delay 10 s).

Aufruf: python3 tools/bw_dauer4.py ergebnis/bw/dauer4
"""

import collections
import datetime as dt
import gzip
import io
import json
import pathlib
import re
import statistics
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/bw/dauer4")
ZIEL.mkdir(parents=True, exist_ok=True)
BASIS = "https://mobidata-bw.de"
VM = BASIS + "/vm/Stundenwerte_Dauerzaehlstellen_BW"
GUT = set("-u")
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def text(b: bytes) -> tuple[str, str]:
    try:
        return b.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return b.decode("cp1252", "replace"), "cp1252"


def letzter_sonntag(j, m):
    d = dt.date(j, m, 31)
    return d - dt.timedelta(days=(d.weekday() - 6) % 7)


KOEPFE, KENNUNGEN, STATUS, VOLL, DOPPELT, KODIERUNG = [], {}, {}, {}, {}, collections.Counter()
UMSTELL = collections.defaultdict(collections.Counter)  # Tag -> (Stunde, Kennung KFZ) -> n
SUMMEN = collections.defaultdict(list)  # (Tag, Stunde) -> Summe KFZ je Datei
WERTE = collections.Counter()  # Auffälliges in Wertfeldern


def datei(monat_hint: str, name: str, roh: bytes):
    t, kod = text(roh)
    KODIERUNG[kod] += 1
    zeilen = t.splitlines()
    k1, k2, k3, sp = (zeilen[i].split(";") for i in range(4))
    stelle = k1[0].strip().zfill(4) + k1[1].strip().zfill(4)
    KOEPFE.append([monat_hint, name.split("/")[-1], [x.strip() for x in k1[:6]],
                   [x.strip() for x in k2[:6]], [x.strip() for x in k3 if x.strip()]])
    n1, n2 = int(k2[0]), int(k2[1])
    spalten = [s for s in sp if s]
    idx = {s: i for i, s in enumerate(spalten)}
    gr = [k3[2 + j].strip() for j in range(int(k3[0]))]
    ken = KENNUNGEN.setdefault(monat_hint, collections.Counter())
    sta = STATUS.setdefault(monat_hint, collections.Counter())
    voll = VOLL.setdefault(monat_hint, collections.Counter())
    je_tag = collections.defaultdict(lambda: {1: 0, 2: 0})
    tage = set()
    for z_ in zeilen[4:]:
        f = z_.split(";")
        if len(f) < 3 or not f[0].strip():
            continue
        d, st = f[0][:6], f[0][6:]
        tage.add(d)
        sta[st] += 1
        for g in gr:
            for s in range(1, n1 + n2 + 1):
                ken[f"{g}|{f[idx[f'K_{g}FS{s}']]}"] += 1
                w = f[idx[f"{g}FS{s}"]]
                if not w.strip().isdigit():
                    WERTE[f"{g}:{w!r}"] += 1
        for r, spuren in ((1, range(1, n1 + 1)), (2, range(n1 + 1, n1 + n2 + 1))):
            if st == "" and all(f[idx[f"K_KFZFS{s}"]] in GUT for s in spuren):
                je_tag[d][r] += 1
        tag = dt.date(2000 + int(d[:2]), int(d[2:4]), int(d[4:6]))
        j = tag.year
        if tag in (letzter_sonntag(j, 3), letzter_sonntag(j, 10)):
            for s in range(1, n1 + n2 + 1):
                UMSTELL[tag.isoformat()][f"{f[1]}{st}|{f[idx[f'K_KFZFS{s}']]}"] += 1
        if tag.weekday() == 6 and tag.month in (3, 10) and tag.day >= 15 and f[1] in ("02:00", "03:00", "04:00"):
            try:
                SUMMEN[(tag.isoformat(), f[1])].append(sum(int(f[idx[f"KFZFS{s}"]]) for s in range(1, n1 + n2 + 1)))
            except ValueError:
                pass
    for d in tage:
        tag = dt.date(2000 + int(d[:2]), int(d[2:4]), int(d[4:6]))
        soll = 23 if tag == letzter_sonntag(tag.year, 3) else 24
        for r in (1, 2):
            voll["richtungstage"] += 1
            voll["vollstaendig" if je_tag[d][r] >= soll else "nicht"] += 1
    return stelle


def zip_durchgehen(monat_hint: str, z: zipfile.ZipFile):
    stellen = collections.defaultdict(list)
    for n in z.namelist():
        if n.endswith("/"):
            continue
        if n.lower().endswith(".zip"):
            m = re.search(r"(\d{6})", n)
            zip_durchgehen(m.group(1) if m else n, zipfile.ZipFile(io.BytesIO(z.read(n))))
            continue
        m = re.search(r"_(\d{2})(\d{2})\.csv$", n)
        hint = f"20{m.group(1)}{m.group(2)}" if m else monat_hint
        try:
            stellen[(hint, datei(hint, n, z.read(n)))].append(n.split("/")[-1])
        except Exception as e:  # noqa: BLE001
            log("Fehler", n, repr(e)[:150])
    for (hint, s), namen in stellen.items():
        if len(namen) > 1:
            DOPPELT.setdefault(hint, {})[s] = namen


def main():
    jahre = [f"{VM}/Stundenwerte_{j}.zip" for j in range(2016, 2025)]
    dcat, _, _ = R.oeffne(f"{BASIS}/dataset/stundenwerte_dauerzaehlstellen.jsonld", zeit=120)
    monate = sorted(set(re.findall(r"Stundenwerte_(\d{6})\.zip", dcat.decode("utf-8", "replace"))))
    log("Monate laut DCAT:", monate)
    for url in jahre + [f"{VM}/Stundenwerte_{m}.zip" for m in monate]:
        try:
            inhalt, _, _ = R.oeffne(url, zeit=900, grenze=90_000_000)
        except Exception as e:  # noqa: BLE001
            log(url, "Fehler:", repr(e)[:200])
            continue
        log(url.split("/")[-1], len(inhalt))
        zip_durchgehen(url.split("_")[-1][:-4], zipfile.ZipFile(io.BytesIO(inhalt)))
        del inhalt
    sonntage = collections.defaultdict(dict)
    for (tag, h), v in SUMMEN.items():
        sonntage[tag][h] = round(statistics.median(v), 1)
    with gzip.open(ZIEL / "koepfe.json.gz", "wt", encoding="utf-8") as f:
        json.dump(KOEPFE, f, ensure_ascii=False)
    (ZIEL / "auswertung.json").write_text(json.dumps({
        "kodierung": KODIERUNG, "kennungen": KENNUNGEN, "status": STATUS, "vollstaendig": VOLL,
        "doppelt": DOPPELT, "werte": WERTE, "umstelltage": UMSTELL,
        "sonntage_02_03_04": dict(sorted(sonntage.items()))}, ensure_ascii=False, indent=1))
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")


if __name__ == "__main__":
    main()
