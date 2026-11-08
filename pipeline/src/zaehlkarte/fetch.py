"""Rohdaten holen: Archive mit Prüfsumme (Berlin), MobiData BW samt Excel aus den ZIPs.

Alles landet in pipeline/data/raw/ (gitignored). Berlin-Archive und Geokodierung sind auf einen
Commit gepinnt (sha256 in sources.yaml); eine abweichende Prüfsumme bricht ab. MobiData BW
liefert laufend neue Zählungen: Übersicht und ZIP werden jedes Mal neu geholt, aus dem ZIP nur
die Excel-Dateien behalten (die PDFs sind dieselben Zahlen als Bericht). Münster: ZIP und
Positionsdatei mit Prüfsumme; aus dem ZIP die XLS und PDF. Moers: je Datensatz die Metadaten
(CKAN-API) und alle Messdateien, jedes Mal neu. Konstanz: je Standort eine CSV mit Prüfsumme.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

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


def entpacke_excel(zip_pfad: Path, ziel: Path, endungen: tuple[str, ...] = (".xlsx",)) -> int:
    """Nur Dateien mit diesen Endungen (Groß-/Kleinschreibung egal) nach `ziel`."""
    if ziel.exists():
        shutil.rmtree(ziel)
    n = 0
    with zipfile.ZipFile(zip_pfad) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.lower().endswith(endungen):
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
        elif q["adapter"] == "moers_radar":
            n = 0
            for paket in q["pakete"]:
                ordner = pfade.roh / "moers" / paket
                ordner.mkdir(parents=True, exist_ok=True)
                antwort = requests.get(q["api"].format(paket=paket), headers=UA, timeout=120)
                antwort.raise_for_status()
                p = antwort.json()["result"]
                (ordner / "paket.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
                for r in p.get("resources", []):
                    datei = unquote((r.get("url") or "").rsplit("/", 1)[-1])
                    if datei:
                        lade(r["url"], ordner / datei)
                        n += 1
            log.append(f"{code}: {len(q['pakete'])} Datensätze, {n} Messungen")
        elif q["adapter"] == "muenster":
            ordner = pfade.roh / "muenster"
            pos = q["positionen"]
            log.append(lade_geprueft(pos["url"], ordner / pos["datei"], pos.get("sha256")))
            with tempfile.TemporaryDirectory() as tmp:
                zip_pfad = Path(tmp) / "zaehlungen.zip"
                lade_geprueft(q["url_zip"], zip_pfad, q.get("sha256_zip"))
                n = entpacke_excel(zip_pfad, ordner / "zip", (".xls", ".pdf"))
            log.append(f"{code}: Positionen + {n} XLS- und PDF-Dateien")
        elif q["adapter"] == "konstanz_mobil":
            ordner = pfade.roh / "konstanz"
            for st in q["standorte"]:
                log.append(lade_geprueft(st["url"], ordner / st["datei"], st.get("sha256")))
    return log
