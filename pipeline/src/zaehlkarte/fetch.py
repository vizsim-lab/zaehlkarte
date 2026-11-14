"""Rohdaten holen: Archive mit Prüfsumme (Berlin), MobiData BW samt Excel aus den ZIPs.

Alles landet in pipeline/data/raw/ (gitignored). Jeder Abruf geht über `zaehlkarte.abruf` – nur,
was robots.txt erlaubt, mit dem verlangten Abstand (Crawl-delay). Berlin-Archive und Geokodierung
sind auf einen Commit gepinnt (sha256 in sources.yaml); eine abweichende Prüfsumme bricht ab.
MobiData BW liefert laufend neue Zählungen: Übersicht und ZIP werden jedes Mal neu geholt, aus dem
ZIP nur die Excel-Dateien behalten (die PDFs sind dieselben Zahlen als Bericht). Münster: ZIP und
Positionsdatei mit Prüfsumme; aus dem ZIP die XLS und PDF. Moers: je Datensatz die Metadaten (DCAT-
Dokument des Portals, `zaehlkarte.ckan`) und alle Messdateien – neu nur, was fehlt oder sich laut
Metadaten geändert hat. Konstanz: je Standort eine CSV mit Prüfsumme. Potsdam: Knotenliste
(Opendatasoft-API) und je Knoten das ZIP der Zählpläne, jedes Mal neu; das Datum des Abrufs steht
in `potsdam/abruf.txt` – es gehört zur Quellenangabe (NB-16-OGD). Olpe: alle Datensätze
„Verkehrsmessung(en) …“ (HTML-Suche und -Seite des Portals, die Lizenz steht nur dort) samt
JSON-Dateien, jedes Mal neu.

Scheitert eine Quelle, laufen die anderen weiter (wie bei den Dauerzählstellen); `hole` nennt sie
mit dem Fehler, ihre Rohdaten bleiben, wie sie waren. `zaehlkarte fetch` endet dann mit
Exit-Code 1: Der Workflow „Kartendaten neu bauen“ hat keine Rohdaten früherer Läufe – ein Bau
ohne die Quelle ließe ihre Zählungen aus der Karte fallen.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import traceback
import zipfile
from collections.abc import Callable
from datetime import date
from pathlib import Path
from urllib.parse import unquote

from zaehlkarte import abruf, ckan
from zaehlkarte.config import Pfade, quellen

UA = abruf.UA


def sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def lade(url: str, ziel: Path) -> Path:
    """Datei holen (robots.txt und Crawl-delay: `zaehlkarte.abruf`)."""
    return abruf.lade(url, ziel)


def _schreibe_json(pfad: Path, daten: object) -> None:
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")


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


def entpacke_flach(zip_pfad: Path, ziel: Path, endungen: tuple[str, ...]) -> int:
    """Dateien mit diesen Endungen ohne Unterordner des ZIPs nach `ziel` (Potsdam: „2802/x.pdf“)."""
    n = 0
    with zipfile.ZipFile(zip_pfad) as zf:
        for info in zf.infolist():
            name = Path(info.filename).name
            if info.is_dir() or not name.lower().endswith(endungen) or name.startswith("."):
                continue
            ziel.mkdir(parents=True, exist_ok=True)
            (ziel / name).write_bytes(zf.read(info))
            n += 1
    return n


def _berlin_zda(code: str, q: dict, pfade: Pfade) -> list[str]:
    log = [lade_geprueft(lf["url"], pfade.roh / lf["datei"], lf.get("sha256"))
           for lf in q["lieferungen"]]
    g = q["geokodierung"]
    return [*log, lade_geprueft(g["url"], pfade.roh / g["datei"], g.get("sha256"))]


def _mobidata_bw(code: str, q: dict, pfade: Pfade) -> list[str]:
    ordner = pfade.roh / "mobidata" / q["paket"]
    lade(q["url_uebersicht"], ordner / q["uebersicht"])
    with tempfile.TemporaryDirectory() as tmp:
        zip_pfad = lade(q["url_zip"], Path(tmp) / "zaehlungen.zip")
        n = entpacke_excel(zip_pfad, ordner / "zip")
    return [f"{code}: Übersicht + {n} Excel-Dateien"]


def _moers_radar(code: str, q: dict, pfade: Pfade) -> list[str]:
    n = neu = 0
    for paket in q["pakete"]:
        ordner = pfade.roh / "moers" / paket
        ordner.mkdir(parents=True, exist_ok=True)
        vorher = {}
        if (ordner / "paket.json").exists():
            alt = json.loads((ordner / "paket.json").read_text(encoding="utf-8"))
            vorher = {r.get("url"): r.get("last_modified") for r in alt["resources"]}
        p = ckan.paket(q["ckan"], paket, wege=("dcat",))
        for r in p["resources"]:
            datei = unquote((r.get("url") or "").rsplit("/", 1)[-1])
            if not datei:
                continue
            n += 1
            if (ordner / datei).exists() and vorher.get(r["url"]) == r["last_modified"]:
                continue  # unverändert seit dem letzten Abruf
            lade(r["url"], ordner / datei)
            neu += 1
        _schreibe_json(ordner / "paket.json", p)
    return [f"{code}: {len(q['pakete'])} Datensätze, {n} Messungen ({neu} geladen)"]


def _muenster(code: str, q: dict, pfade: Pfade) -> list[str]:
    ordner = pfade.roh / "muenster"
    pos = q["positionen"]
    log = [lade_geprueft(pos["url"], ordner / pos["datei"], pos.get("sha256"))]
    with tempfile.TemporaryDirectory() as tmp:
        zip_pfad = Path(tmp) / "zaehlungen.zip"
        lade_geprueft(q["url_zip"], zip_pfad, q.get("sha256_zip"))
        n = entpacke_excel(zip_pfad, ordner / "zip", (".xls", ".pdf"))
    return [*log, f"{code}: Positionen + {n} XLS- und PDF-Dateien"]


def _potsdam_pdf(code: str, q: dict, pfade: Pfade) -> list[str]:
    ordner = pfade.roh / "potsdam"
    knoten = abruf.hole(q["api"]).json()
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "export.json").write_text(json.dumps(knoten, ensure_ascii=False, indent=1))
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        neu = Path(tmp) / "pdf"
        for k in knoten:
            if k.get("zahlplan"):
                zip_pfad = lade(k["zahlplan"], Path(tmp) / "plan.zip")
                n += entpacke_flach(zip_pfad, neu / str(k["kpnr"]), (".pdf",))
        if (ordner / "pdf").exists():
            shutil.rmtree(ordner / "pdf")
        shutil.copytree(neu, ordner / "pdf")
    (ordner / "abruf.txt").write_text(date.today().isoformat())
    return [f"{code}: {len(knoten)} Knoten, {n} Zählpläne"]


def _xanten_pdf(code: str, q: dict, pfade: Pfade) -> list[str]:
    return [lade_geprueft(d["url"], pfade.roh / "xanten" / d["datei"], d.get("sha256"))
            for d in q["dateien"]]


def _olpe_radar(code: str, q: dict, pfade: Pfade) -> list[str]:
    # die Suche des Portals findet je nach Wortform andere Datensätze – alle Begriffe,
    # dazu die bekannten (`pakete`), falls die Suche einen einmal nicht findet
    namen = ckan.suche(q["ckan"], q["suche"]) + q.get("pakete", [])
    namen = sorted({x for x in namen if re.search(q["paket_muster"], x)})
    if not namen:
        raise ValueError(f"{code}: keine Datensätze gefunden ({q['ckan']})")
    pakete = [ckan.paket(q["ckan"], name, wege=("html",)) for name in namen]
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        neu = Path(tmp) / "olpe"
        for p in pakete:
            ordner = neu / p["name"]
            ordner.mkdir(parents=True)
            _schreibe_json(ordner / "paket.json", p)
            for r in p.get("resources", []):
                datei = unquote((r.get("url") or "").rsplit("/", 1)[-1])
                if datei.lower().endswith(".json"):
                    lade(r["url"], ordner / datei)
                    n += 1
        if (pfade.roh / "olpe").exists():
            shutil.rmtree(pfade.roh / "olpe")
        shutil.copytree(neu, pfade.roh / "olpe")
    return [f"{code}: {len(pakete)} Datensätze, {n} Messungen"]


def _konstanz_mobil(code: str, q: dict, pfade: Pfade) -> list[str]:
    return [lade_geprueft(st["url"], pfade.roh / "konstanz" / st["datei"], st.get("sha256"))
            for st in q["standorte"]]


# Adapter (`adapter:` in sources.yaml) -> Abruf; tests/test_konfiguration.py prüft, dass jede
# live-Quelle einen hat
ABRUF: dict[str, Callable[[str, dict, Pfade], list[str]]] = {
    "berlin_zda": _berlin_zda,
    "mobidata_bw": _mobidata_bw,
    "moers_radar": _moers_radar,
    "muenster": _muenster,
    "potsdam_pdf": _potsdam_pdf,
    "xanten_pdf": _xanten_pdf,
    "olpe_radar": _olpe_radar,
    "konstanz_mobil": _konstanz_mobil,
}


def hole_quelle(code: str, q: dict, pfade: Pfade) -> list[str]:
    if q["adapter"] not in ABRUF:
        raise ValueError(f"{code}: kein Abruf für den Adapter {q['adapter']!r}")
    return ABRUF[q["adapter"]](code, q, pfade)


def hole(pfade: Pfade | None = None, nur: list[str] | None = None) -> tuple[list[str], list[str]]:
    """-> (Log, Quellen mit Fehler). Scheitert eine Quelle, laufen die anderen weiter."""
    pfade = pfade or Pfade()
    log: list[str] = []
    fehler: list[str] = []
    abruf.ausnahmen_setzen(quellen(pfade))
    for code, q in quellen(pfade).items():
        if nur and code not in nur:
            continue
        try:
            log += hole_quelle(code, q, pfade)
        except Exception as e:  # noqa: BLE001 – eine Quelle darf die anderen nicht aufhalten
            fehler.append(code)
            log.append(f"FEHLER {code}: {e!r}")
            log += [f"  {z}" for z in traceback.format_exc().splitlines()[-6:]]
    return log, fehler
