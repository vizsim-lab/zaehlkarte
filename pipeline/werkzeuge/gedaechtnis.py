"""Gedächtnis der Dauerzählstellen im Release `dauerzaehlstellen` holen und ablegen.

Manche Quellen halten ihre Stundenwerte nur einige Monate vor (Hamburg). Was ein Adapter selbst
aufhebt, liegt in `pipeline/data/raw/<code>/gedaechtnis/`; der Workflow „Dauerzählstellen bauen“
holt es vor dem Abruf aus dem Release und legt danach ab, was sich geändert hat. Ein Asset heißt
`<code>__<datei>` (etwa `hamburg_kfz__stunden_2026-11.csv.gz`).

Ablegen ohne Verlustfenster: erst als `<name>.neu` hochladen, dann das alte Asset löschen und das
neue umbenennen. Bricht ein Lauf dazwischen ab, liegt `<name>.neu` im Release – `holen` nimmt
dann diese Fassung. Und nie mit weniger: Eine Datei, die weniger Werte enthält als beim Holen
(Stunden mit Wert bzw. Stellen), wird nicht abgelegt – das Gedächtnis wächst nur.

Zweite Kopie (`kopieren`, nach dem Ablegen): jede Fassung einer Datei, die es dort noch nicht
gibt, als `<Zeitpunkt>__<Prüfsumme>__<code>__<datei>` in ein eigenes Release je Jahr
(`gedaechtnis-kopie-JJJJ`; ein Release fasst höchstens 1000 Assets) – nie überschrieben, nie
gelöscht. Sie schützt vor gelöschten oder kaputten Assets im Release `dauerzaehlstellen`.
Wiederherstellen: je `<code>__<datei>` die jüngste Fassung (Name beginnt mit dem Zeitpunkt) aus
dem jüngsten Kopie-Release laden, unter `<code>__<datei>` nach
`pipeline/data/raw/<code>/gedaechtnis/<datei>` legen und `ablegen` laufen lassen.

    uv run python werkzeuge/gedaechtnis.py holen    [--release dauerzaehlstellen]
    uv run python werkzeuge/gedaechtnis.py ablegen  [--release dauerzaehlstellen]
    uv run python werkzeuge/gedaechtnis.py kopieren
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROH = Path(__file__).resolve().parents[1] / "data" / "raw"
VORHER = ROH / "gedaechtnis_vorher.json"
KOPIE = "gedaechtnis-kopie-{jahr}"
KOPIE_NOTIZ = (
    "Zweite Kopie des Gedächtnisses aus dem Release dauerzaehlstellen: jede Fassung einer Datei "
    "als <Zeitpunkt>__<Prüfsumme>__<code>__<datei>, nie überschrieben, nie gelöscht. "
    "Wiederherstellen: je <code>__<datei> die jüngste Fassung (pipeline/werkzeuge/gedaechtnis.py)."
    " Stundenwerte wie geliefert – Hamburg: dl-de/by-2-0, Freie und Hansestadt Hamburg, Behörde "
    "für Verkehr und Mobilitätswende; Leipzig: dl-de/by-2-0, Stadt Leipzig; strassen.json: "
    "© OpenStreetMap-Mitwirkende, ODbL. Abgelegt vom Workflow „Dauerzählstellen bauen“.")


def gh(*args: str, ausgabe: bool = False) -> str:
    r = subprocess.run(["gh", *args], check=True, text=True, capture_output=ausgabe)
    return r.stdout if ausgabe else ""


def repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY") or gh(
        "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner", ausgabe=True).strip()


def assets(release: str) -> dict[str, int]:
    """Alle Assets des Releases (seitenweise – mit den Monaten werden es mit der Zeit viele)."""
    rid = json.loads(gh("api", f"repos/{repo()}/releases/tags/{release}", ausgabe=True))["id"]
    seiten = gh("api", "--paginate", "--slurp",
                f"repos/{repo()}/releases/{rid}/assets?per_page=100", ausgabe=True)
    return {a["name"]: a["id"] for seite in json.loads(seiten) for a in seite}


def sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def umfang(pfad: Path) -> int:
    """Wie viel eine Datei des Gedächtnisses enthält: Stunden mit Wert (CSV) bzw. Einträge."""
    if pfad.name.endswith(".csv.gz"):
        with gzip.open(pfad, "rt", encoding="utf-8", newline="") as f:
            r = csv.reader(f, delimiter=";")
            next(r, None)
            return sum(sum(1 for x in z[3:] if x != "") for z in r)
    if pfad.suffix == ".json":
        d = json.loads(pfad.read_text(encoding="utf-8"))
        return len(d.get("stellen", d)) if isinstance(d, dict) else len(d)
    return pfad.stat().st_size


def dateien() -> dict[str, Path]:
    """Asset-Name -> lokale Datei für alles in raw/<code>/gedaechtnis/."""
    out = {}
    for pfad in sorted(ROH.glob("*/gedaechtnis/*")):
        if pfad.is_file():
            out[f"{pfad.parent.parent.name}__{pfad.name}"] = pfad
    return out


def holen(release: str) -> None:
    namen = [n for n in assets(release) if "__" in n]
    with tempfile.TemporaryDirectory() as tmp:
        for name in namen:
            gh("release", "download", release, "--pattern", name, "--dir", tmp, "--clobber")
        # .neu zuletzt: eine abgebrochene Ablage hat die neuere, vollständige Fassung hinterlassen
        for name in sorted(namen, key=lambda n: n.endswith(".neu")):
            ziel_name = name.removesuffix(".neu")
            code, datei = ziel_name.split("__", 1)
            ziel = ROH / code / "gedaechtnis" / datei
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(tmp) / name, ziel)
    stand = {n: {"sha256": sha(p), "umfang": umfang(p)} for n, p in dateien().items()}
    VORHER.parent.mkdir(parents=True, exist_ok=True)
    VORHER.write_text(json.dumps(stand, indent=1, sort_keys=True))
    print(f"Gedächtnis: {len(stand)} Dateien aus dem Release geholt")


def ablegen(release: str) -> None:
    if not VORHER.exists():
        raise SystemExit("Gedächtnis: erst `holen` – sonst ersetzte eine leere Fassung die alte")
    vorher = json.loads(VORHER.read_text())
    geaendert = {n: p for n, p in dateien().items() if vorher.get(n, {}).get("sha256") != sha(p)}
    weniger = [n for n, p in geaendert.items() if n in vorher and umfang(p) < vorher[n]["umfang"]]
    if weniger:
        raise SystemExit("Gedächtnis: weniger Werte als vorher, nicht abgelegt: "
                         + ", ".join(weniger))
    if not geaendert:
        print("Gedächtnis: nichts geändert")
        return
    with tempfile.TemporaryDirectory() as tmp:
        for name, pfad in geaendert.items():
            neu = Path(tmp) / f"{name}.neu"
            shutil.copyfile(pfad, neu)
            alt = assets(release)
            if f"{name}.neu" in alt:
                gh("api", "-X", "DELETE", f"repos/{repo()}/releases/assets/{alt[f'{name}.neu']}")
            gh("release", "upload", release, str(neu))
            alt = assets(release)
            if name in alt:
                gh("api", "-X", "DELETE", f"repos/{repo()}/releases/assets/{alt[name]}")
            gh("api", "-X", "PATCH", f"repos/{repo()}/releases/assets/{alt[f'{name}.neu']}",
               "-f", f"name={name}")
            print(f"Gedächtnis abgelegt: {name} ({pfad.stat().st_size / 1e6:.1f} MB)")


def release_anlegen(release: str, titel: str, notiz: str) -> None:
    try:
        gh("release", "view", release, ausgabe=True)
    except subprocess.CalledProcessError:
        gh("release", "create", release, "--latest=false", "--title", titel, "--notes", notiz)


def kopieren(jetzt: datetime | None = None) -> None:
    """Jede Fassung, die es in der Kopie dieses Jahres noch nicht gibt, dorthin – nie ersetzen."""
    jetzt = jetzt or datetime.now(UTC)
    lokal = dateien()
    if not lokal:
        print("Gedächtnis: nichts zu kopieren")
        return
    release = KOPIE.format(jahr=jetzt.year)
    release_anlegen(release, f"Daten: Gedächtnis, zweite Kopie {jetzt.year}", KOPIE_NOTIZ)
    da = {n.split("__", 1)[1] for n in assets(release) if n.count("__") >= 3}
    zeit = jetzt.strftime("%Y-%m-%dT%H%M%SZ")
    neu = 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, pfad in lokal.items():
            kennung = f"{sha(pfad)[:12]}__{name}"
            if kennung in da:
                continue
            ziel = Path(tmp) / f"{zeit}__{kennung}"
            shutil.copyfile(pfad, ziel)
            gh("release", "upload", release, str(ziel))
            neu += 1
    print(f"Gedächtnis: {neu} von {len(lokal)} Dateien neu in der Kopie {release}")


def main() -> int:
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("was", choices=["holen", "ablegen", "kopieren"])
    a.add_argument("--release", default="dauerzaehlstellen")
    args = a.parse_args()
    if args.was == "kopieren":
        kopieren()
    else:
        (holen if args.was == "holen" else ablegen)(args.release)
    return 0


if __name__ == "__main__":
    sys.exit(main())
