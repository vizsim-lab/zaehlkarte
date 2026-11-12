"""Entwicklungswerkzeug: Aufbau der Dauerzählstellen-Daten von Berlin (VIZ) und Hamburg
(SensorThings) erkunden – Liste, Readme, Stammdaten und Auszüge, keine vollständigen Abzüge.

Läuft im Workflow „Erkundung Dauerzählstellen“ (beide Server sind aus manchen
Entwicklungsumgebungen nicht erreichbar) und schreibt nach ergebnis/dauer/.

    uv run --no-project --with openpyxl python tools/dauer_erkunden.py ergebnis/dauer
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import tarfile
import time
import traceback
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}
BLOB = "https://mdhopendata.blob.core.windows.net/verkehrsdetektion"
STA_KFZ = "https://iot.hamburg.de/v1.1"
STA_RAD = "https://iot.hamburg.de/v1.0"
MAX_PROBE = 1_500_000_000  # größere Dateien nur auflisten


def hole(url: str, timeout: int = 300) -> bytes:
    for versuch in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            if versuch == 2:
                raise
            time.sleep(5)
    raise RuntimeError("unerreichbar")


def hole_json(url: str) -> dict:
    return json.loads(hole(url, 120))


# ---------------------------------------------------------------- Berlin


def blob_liste() -> list[dict]:
    eintraege, marker = [], ""
    while True:
        url = f"{BLOB}?restype=container&comp=list&include=metadata&maxresults=5000"
        if marker:
            url += "&marker=" + urllib.parse.quote(marker)
        wurzel = ET.fromstring(hole(url, 120))
        for b in wurzel.iter("Blob"):
            p = b.find("Properties")
            eintraege.append({
                "name": b.findtext("Name"),
                "groesse": int(p.findtext("Content-Length") or 0),
                "geaendert": p.findtext("Last-Modified"),
                "md5": p.findtext("Content-MD5"),
                "typ": p.findtext("Content-Type"),
                "meta": {m.tag: m.text for m in list(b.find("Metadata") if b.find("Metadata") is not None else [])},
            })
        marker = wurzel.findtext("NextMarker") or ""
        if not marker:
            return eintraege


def muster(name: str) -> str:
    return re.sub(r"\d", "#", name)


def csv_zusammenfassung(text_zeilen, kopf_n: int = 15) -> dict:
    """Erste Zeilen, Zeilenzahl, Trennzeichen, je Spalte bis 5 Beispielwerte, Anzahl Werte in Spalte 1."""
    kopf, n, erste_spalte, trenner = [], 0, set(), None
    tage = set()
    for zeile in text_zeilen:
        if n < kopf_n:
            kopf.append(zeile.rstrip("\n"))
        if trenner is None and zeile.strip():
            trenner = max([";", ",", "\t"], key=zeile.count)
        if n > 0 and trenner:
            teile = zeile.rstrip("\n").split(trenner)
            if teile and len(erste_spalte) < 200_000:
                erste_spalte.add(teile[0])
            if len(teile) > 1 and len(tage) < 1000:
                tage.add(teile[1])
        n += 1
    return {"kopf": kopf, "zeilen": n, "trenner": trenner, "werte_spalte1": len(erste_spalte),
            "beispiel_spalte1": sorted(erste_spalte)[:20], "werte_spalte2": len(tage),
            "beispiel_spalte2": sorted(tage)[:5] + sorted(tage)[-3:]}


def zeilen_aus(daten: bytes):
    return io.TextIOWrapper(io.BytesIO(daten), encoding="utf-8", errors="replace", newline="")


def untersuche_datei(name: str, daten: bytes) -> dict:
    out: dict = {"name": name, "bytes": len(daten)}
    klein = name.lower()
    if klein.endswith((".tgz", ".tar.gz", ".tar")):
        with tarfile.open(fileobj=io.BytesIO(daten), mode="r:*") as tf:
            glieder = [m for m in tf.getmembers() if m.isfile()]
            out["glieder"] = len(glieder)
            out["glieder_namen"] = [m.name for m in glieder]
            out["proben"] = []
            for m in glieder[:3] + glieder[-1:]:
                inhalt = tf.extractfile(m).read()
                if m.name.lower().endswith(".gz"):
                    inhalt = gzip.decompress(inhalt)
                out["proben"].append({"name": m.name, **csv_zusammenfassung(zeilen_aus(inhalt))})
    elif klein.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(daten)) as zf:
            out["glieder_namen"] = [i.filename for i in zf.infolist()]
            out["proben"] = []
            for info in zf.infolist()[:6]:
                if info.is_dir():
                    continue
                inhalt = zf.read(info)
                if info.filename.lower().endswith(".gz"):
                    inhalt = gzip.decompress(inhalt)
                out["proben"].append({"name": info.filename, "bytes": info.file_size,
                                      **csv_zusammenfassung(zeilen_aus(inhalt))})
    elif klein.endswith(".gz"):
        out.update(csv_zusammenfassung(zeilen_aus(gzip.decompress(daten))))
    elif klein.endswith((".csv", ".txt")):
        out.update(csv_zusammenfassung(zeilen_aus(daten)))
    return out


def stammdaten_csv(daten: bytes, ziel: Path) -> dict:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(daten), read_only=True, data_only=True)
    out = {}
    for ws in wb.worksheets:
        zeilen = [["" if v is None else v for v in r] for r in ws.iter_rows(values_only=True)]
        with (ziel / f"stammdaten_{ws.title}.csv").open("w", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter=";").writerows(zeilen)
        out[ws.title] = {"zeilen": len(zeilen), "kopf": [str(v) for v in (zeilen[0] if zeilen else [])]}
    return out


def berlin(ziel: Path) -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    liste = blob_liste()
    with (ziel / "liste.tsv").open("w", encoding="utf-8") as f:
        f.write("name\tgroesse\tgeaendert\tmd5\ttyp\tmeta\n")
        for e in liste:
            f.write(f"{e['name']}\t{e['groesse']}\t{e['geaendert']}\t{e['md5']}\t{e['typ']}\t"
                    f"{json.dumps(e['meta'], ensure_ascii=False)}\n")
    je_muster = defaultdict(list)
    for e in liste:
        je_muster[muster(e["name"])].append(e)
    uebersicht = {
        "dateien": len(liste),
        "bytes": sum(e["groesse"] for e in liste),
        "je_jahr": dict(sorted(Counter(e["name"].split("/")[0] for e in liste).items())),
        "bytes_je_jahr": {j: sum(e["groesse"] for e in liste if e["name"].startswith(j + "/"))
                          for j in sorted({e["name"].split("/")[0] for e in liste if "/" in e["name"]})},
        "muster": {m: {"n": len(es), "erste": es[0]["name"], "letzte": es[-1]["name"],
                       "groesste": max(x["groesse"] for x in es)} for m, es in sorted(je_muster.items())},
    }
    (ziel / "uebersicht.json").write_text(json.dumps(uebersicht, ensure_ascii=False, indent=1))

    # Readme und Stammdaten ganz (klein)
    for e in liste:
        n = e["name"]
        if "/" not in n and n.lower().endswith(".txt"):
            (ziel / Path(n).name).write_bytes(hole(f"{BLOB}/{urllib.parse.quote(n)}"))
        if n.lower().endswith(".xlsx"):
            daten = hole(f"{BLOB}/{urllib.parse.quote(n)}")
            info = stammdaten_csv(daten, ziel)
            (ziel / f"{Path(n).stem}.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))

    # Proben: je Muster die erste und letzte Datei, dazu je Jahr eine Juni-Datei je Muster
    proben = []
    for m, es in sorted(je_muster.items()):
        if not any(es[0]["name"].lower().endswith(x) for x in (".zip", ".gz", ".tgz", ".csv", ".tar")):
            continue
        kandidaten = {es[0]["name"]: es[0], es[-1]["name"]: es[-1]}
        for e in es:
            if re.search(r"(^|[^0-9])(20\d\d)[-_]?06([^0-9]|$)", e["name"]):
                kandidaten.setdefault(e["name"], e)
        proben.extend(kandidaten.values())
    befunde = []
    for e in proben:
        if e["groesse"] > MAX_PROBE:
            befunde.append({"name": e["name"], "bytes": e["groesse"], "uebersprungen": True})
            continue
        try:
            daten = hole(f"{BLOB}/{urllib.parse.quote(e['name'])}", 900)
            befunde.append(untersuche_datei(e["name"], daten))
        except Exception as err:  # noqa: BLE001
            befunde.append({"name": e["name"], "fehler": repr(err)})
        print("Berlin:", e["name"], flush=True)
    (ziel / "proben.json").write_text(json.dumps(befunde, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- Hamburg


def sta(basis: str, pfad: str, **params) -> dict:
    q = urllib.parse.urlencode(params, safe="$(),;'/=", quote_via=urllib.parse.quote)
    return hole_json(f"{basis}/{pfad}?{q}")


def hamburg_dienst(basis: str, dienst: str, ziel: Path) -> None:
    filt = f"properties/serviceName eq '{dienst}'"
    out: dict = {"dienst": dienst, "basis": basis}
    things = sta(basis, "Things", **{"$filter": filt, "$count": "true", "$top": "3",
                                       "$expand": "Locations,Datastreams"})
    out["things_anzahl"] = things.get("@iot.count")
    out["things_beispiel"] = things.get("value", [])
    # alle Datastreams des Dienstes: Layer und Zeitraum
    layer: Counter = Counter()
    zeitraeume: dict[str, list] = defaultdict(list)
    url = (f"{basis}/Datastreams?" + urllib.parse.urlencode(
        {"$filter": filt, "$select": "id,name,properties,phenomenonTime", "$top": "1000",
         "$count": "true"}, safe="$(),;'/=", quote_via=urllib.parse.quote))
    seiten = 0
    while url and seiten < 100:
        antwort = hole_json(url)
        for ds in antwort.get("value", []):
            ln = (ds.get("properties") or {}).get("layerName", "?")
            layer[ln] += 1
            if ds.get("phenomenonTime"):
                zeitraeume[ln].append(ds["phenomenonTime"])
        url = antwort.get("@iot.nextLink")
        seiten += 1
    out["datastreams_je_layer"] = dict(layer)
    out["zeitraum_je_layer"] = {
        ln: {"n": len(z), "fruehester_beginn": min(x.split("/")[0] for x in z),
             "spaetester_beginn": max(x.split("/")[0] for x in z),
             "spaetestes_ende": max(x.split("/")[-1] for x in z)} for ln, z in zeitraeume.items()}
    # Beobachtungen der ersten Thing: je Layer die ersten und letzten drei
    beob = {}
    for t in out["things_beispiel"][:1]:
        for ds in t.get("Datastreams", []):
            ln = (ds.get("properties") or {}).get("layerName", ds.get("name"))
            for richtung in ("asc", "desc"):
                try:
                    o = sta(basis, f"Datastreams({ds['@iot.id']})/Observations",
                            **{"$top": "3", "$orderby": f"phenomenonTime {richtung}",
                               "$select": "phenomenonTime,result,resultTime,parameters"})
                    beob[f"{ln} {richtung}"] = o.get("value", [])
                except Exception as err:  # noqa: BLE001
                    beob[f"{ln} {richtung}"] = repr(err)
    out["beobachtungen_erste_thing"] = beob
    (ziel / f"{dienst}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


def hamburg(ziel: Path) -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    for basis, dienst in ((STA_KFZ, "HH_STA_AutomatisierteVerkehrsmengenerfassung"),
                          (STA_RAD, "HH_STA_HamburgerRadzaehlnetz")):
        try:
            hamburg_dienst(basis, dienst, ziel)
        except Exception:  # noqa: BLE001
            (ziel / f"{dienst}.fehler.txt").write_text(traceback.format_exc())
        print("Hamburg:", dienst, flush=True)


if __name__ == "__main__":
    wurzel = Path(sys.argv[1])
    for teil, fn in (("hamburg", hamburg), ("berlin", berlin)):
        try:
            fn(wurzel / teil)
        except Exception:  # noqa: BLE001
            (wurzel / teil).mkdir(parents=True, exist_ok=True)
            (wurzel / teil / "fehler.txt").write_text(traceback.format_exc())
