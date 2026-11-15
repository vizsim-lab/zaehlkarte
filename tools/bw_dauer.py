"""BW, Stundenwerte der Landes-Dauerzählstellen (MobiData BW, Verkehrsministerium, dl-de/by-2-0):
Monate, Format, Zeitbezug an den Umstelltagen, Kennungen K_…, Lage. Nur was robots.txt den
Werkzeugen erlaubt (tools/robots.py; mobidata-bw.de: Crawl-delay 10 s).

Aufruf: python3 tools/bw_dauer.py ergebnis/bw/dauer
"""

import collections
import csv
import io
import json
import pathlib
import re
import sys
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/bw/dauer")
ZIEL.mkdir(parents=True, exist_ok=True)
BASIS = "https://mobidata-bw.de"
DATENSAETZE = ["stundenwerte_dauerzaehlstellen", "karte_strassenverkehrszaehlung"]
ZIP = BASIS + "/vm/Stundenwerte_Dauerzaehlstellen_BW/Stundenwerte_{m}.zip"
LOG = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(s, flush=True)
    LOG.append(s)


def holen(url, grenze=60_000_000):
    inhalt, end, typ = R.oeffne(url, zeit=180, grenze=grenze)
    return inhalt, end, typ


def ressourcen(name):
    """Ressourcen eines Datensatzes aus dem DCAT-Dokument (sonst Links der HTML-Seite)."""
    aus = []
    try:
        inhalt, _, _ = holen(f"{BASIS}/dataset/{name}.jsonld", 20_000_000)
        (ZIEL / f"{name}.jsonld").write_bytes(inhalt)
        d = json.loads(inhalt)
        for k in d.get("@graph", []):
            if "Distribution" in str(k.get("@type")):
                url = (k.get("dcat:downloadURL") or k.get("dcat:accessURL") or {})
                url = url.get("@id") if isinstance(url, dict) else url
                titel = k.get("dct:title")
                titel = titel.get("@value") if isinstance(titel, dict) else titel
                aus.append({"titel": titel, "url": url, "format": k.get("dct:format"),
                            "geaendert": (k.get("dct:modified") or {}).get("@value")
                            if isinstance(k.get("dct:modified"), dict) else k.get("dct:modified")})
        log(name, "DCAT:", len(aus), "Ressourcen")
    except Exception as e:  # noqa: BLE001
        log(name, "DCAT nicht lesbar:", repr(e)[:200])
        inhalt, _, _ = holen(f"{BASIS}/dataset/{name}", 5_000_000)
        (ZIEL / f"{name}.html").write_bytes(inhalt)
        links = sorted(set(re.findall(r'href="([^"]+)"', inhalt.decode("utf-8", "replace"))))
        aus = [{"url": u} for u in links if "/resource/" in u or u.endswith((".zip", ".csv",
                                                                             ".json", ".geojson"))]
        log(name, "HTML:", len(aus), "Links")
    return aus


def lies_zip(m):
    url = ZIP.format(m=m)
    try:
        inhalt, _, _ = holen(url)
    except Exception as e:  # noqa: BLE001
        log(m, "nicht da:", repr(e)[:120])
        return None
    z = zipfile.ZipFile(io.BytesIO(inhalt))
    namen = z.namelist()
    log(m, f"{len(inhalt) / 1e6:.1f} MB, {len(namen)} Dateien, z. B.", namen[:3])
    return z


def auswerten(z, m, proben):
    """Je Datei: Kopfzeilen, Spalten, Stunden je Tag, Kennungen, Fahrstreifen."""
    aus = {"monat": m, "dateien": len(z.namelist()), "kopf": None, "spalten": None,
           "stunden_je_tag": collections.Counter(), "kennungen": collections.Counter(),
           "werte_leer": 0, "zeilen": 0, "beispiel_tage": {}, "stellen": []}
    for i, n in enumerate(sorted(z.namelist())):
        roh = z.read(n)
        for enc in ("utf-8-sig", "cp1252"):
            try:
                text = roh.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        zeilen = text.splitlines()
        if i < 2 and len(proben) < 3:
            proben.append((n, zeilen[:40]))
        # Kopf: Zeilen bis zur Spaltenzeile (die mit „Datum“ oder „Stunde“)
        kopf_ende = next((j for j, z_ in enumerate(zeilen)
                          if re.search(r"(?i)datum|stunde|zeit", z_) and ";" in z_), None)
        if kopf_ende is None:
            continue
        kopf = zeilen[:kopf_ende]
        if aus["kopf"] is None:
            aus["kopf"], aus["spalten"] = kopf, zeilen[kopf_ende]
        aus["stellen"].append({"datei": n, "kopf": kopf})
        spalten = zeilen[kopf_ende].split(";")
        tage = collections.Counter()
        for zeile in csv.reader(zeilen[kopf_ende + 1:], delimiter=";"):
            if not zeile or not zeile[0].strip():
                continue
            aus["zeilen"] += 1
            tage[zeile[0].strip()] += 1
            for s, w in zip(spalten, zeile):
                if s.startswith("K_"):
                    aus["kennungen"][w.strip()] += 1
                elif w.strip() in ("", "-") and s not in ("Datum", "Stunde"):
                    aus["werte_leer"] += 1
        for t, n_ in tage.items():
            aus["stunden_je_tag"][n_] += 1
            if n_ != 24 and len(aus["beispiel_tage"]) < 12:
                aus["beispiel_tage"][f"{n}:{t}"] = n_
    aus["stunden_je_tag"] = dict(aus["stunden_je_tag"])
    aus["kennungen"] = dict(aus["kennungen"].most_common(30))
    return aus


def main():
    alle = {}
    for name in DATENSAETZE:
        alle[name] = ressourcen(name)
    (ZIEL / "ressourcen.json").write_text(json.dumps(alle, ensure_ascii=False, indent=1))
    monate = sorted({mm.group(1) for r in alle[DATENSAETZE[0]]
                     if (mm := re.search(r"Stundenwerte_(\d{6})\.zip", str(r.get("url"))))})
    log("Monate laut Datensatz:", len(monate), monate[:3], "…", monate[-3:])
    # Zeitumstellung: Ende März und Ende Oktober; dazu der jüngste und der älteste Monat
    wahl = [m for m in ("202503", "202510") if m in monate or not monate]
    wahl += [m for m in (monate[:1] + monate[-1:]) if m not in wahl]
    proben, ergebnisse = [], []
    for m in wahl:
        z = lies_zip(m)
        if z is not None:
            ergebnisse.append(auswerten(z, m, proben))
    (ZIEL / "auswertung.json").write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1))
    (ZIEL / "proben.json").write_text(json.dumps(proben, ensure_ascii=False, indent=1))
    # Lage: Ressourcen der Zählstellenkarte (kleine Dateien holen, große nur nennen)
    for r in alle[DATENSAETZE[1]]:
        url = str(r.get("url") or "")
        if not url.startswith("http") or not R.erlaubt(url):
            continue
        try:
            inhalt, end, typ = holen(url, 15_000_000)
            datei = re.sub(r"[^A-Za-z0-9._-]", "_", url.rsplit("/", 1)[-1])[:80] or "ressource"
            (ZIEL / f"karte_{datei}").write_bytes(inhalt[:15_000_000])
            log("Karte:", url, typ, len(inhalt), "Bytes")
        except Exception as e:  # noqa: BLE001
            log("Karte nicht lesbar:", url, repr(e)[:150])
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
