"""Rohdaten holen: Archive mit Prüfsumme (Berlin), MobiData BW samt Excel aus den ZIPs.

Alles landet in pipeline/data/raw/ (gitignored). Berlin-Archive und Geokodierung sind auf einen
Commit gepinnt (sha256 in sources.yaml); eine abweichende Prüfsumme bricht ab. MobiData BW
liefert laufend neue Zählungen: Übersicht und ZIP werden jedes Mal neu geholt, aus dem ZIP nur
die Excel-Dateien behalten (die PDFs sind dieselben Zahlen als Bericht).
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from pathlib import Path

import requests

from zaehlkarte.config import Pfade, quellen

UA = {"User-Agent": "zaehlkarte-pipeline (+https://github.com/vizsim-lab/zaehlkarte)"}


def sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def lade(url: str, ziel: Path) -> Path:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_suffix(ziel.suffix + ".teil")
    with requests.get(url, headers=UA, stream=True, timeout=600) as r:
        r.raise_for_status()
        with tmp.open("wb") as f:
            for block in r.iter_content(1 << 20):
                f.write(block)
    tmp.replace(ziel)
    return ziel


def lade_geprueft(url: str, ziel: Path, soll: str | None) -> str:
    if ziel.exists() and (soll is None or sha256(ziel) == soll):
        return f"{ziel.name}: vorhanden"
    lade(url, ziel)
    if soll and (ist := sha256(ziel)) != soll:
        raise ValueError(f"{ziel.name}: Prüfsumme {ist} statt {soll}")
    return f"{ziel.name}: geladen"


def entpacke_excel(zip_pfad: Path, ziel: Path) -> int:
    if ziel.exists():
        shutil.rmtree(ziel)
    n = 0
    with zipfile.ZipFile(zip_pfad) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".xlsx"):
                continue
            pfad = (ziel / info.filename).resolve()
            if not pfad.is_relative_to(ziel.resolve()):
                continue  # kein Pfad aus dem ZIP heraus
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_bytes(zf.read(info))
            n += 1
    return n


def hole(pfade: Pfade | None = None, nur: list[str] | None = None) -> list[str]:
    pfade = pfade or Pfade()
    log = []
    for code, q in quellen(pfade).items():
        if nur and code not in nur:
            continue
        if q["adapter"] == "berlin_zda":
            for lf in q["lieferungen"]:
                log.append(lade_geprueft(lf["url"], pfade.roh / lf["datei"], lf.get("sha256")))
            g = q["geokodierung"]
            log.append(lade_geprueft(g["url"], pfade.roh / g["datei"], g.get("sha256")))
        elif q["adapter"] == "mobidata_bw":
            ordner = pfade.roh / "mobidata" / q["paket"]
            lade(q["url_uebersicht"], ordner / q["uebersicht"])
            with tempfile.TemporaryDirectory() as tmp:
                zip_pfad = lade(q["url_zip"], Path(tmp) / "zaehlungen.zip")
                n = entpacke_excel(zip_pfad, ordner / "zip")
            log.append(f"{code}: Übersicht + {n} Excel-Dateien")
    return log
