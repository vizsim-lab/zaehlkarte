"""Pfade und Konfiguration der Pipeline.

- `pipeline/config/` – die Konfiguration, die einzige Quellenliste (Aufbau: config/README.md):
  eine Datei je Quelle (`quellen/kurzzeit/`, `quellen/dauer/`), die Datenlage je Land
  (`kommunen/`), Rechtslage, Anfragevorlage, Ausnahmen von robots.txt, Ferien je Land
- `pipeline/data/` – Rohdaten und Zwischenstände (gitignored, `zaehlkarte fetch` holt sie)
- `public/data/` – die Kartendaten (im Git; Vite kopiert `public/` unverändert nach `dist/`)
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

PIPELINE = Path(__file__).resolve().parents[2]
REPO = PIPELINE.parent
CODE = re.compile(r"[a-z][a-z0-9_]*")  # Code einer Quelle = ihr Dateiname, unveränderlich


@dataclass(frozen=True)
class Pfade:
    pipeline: Path = PIPELINE
    repo: Path = REPO

    @property
    def config(self) -> Path:
        return self.pipeline / "config"

    @property
    def roh(self) -> Path:
        return self.pipeline / "data" / "raw"

    @property
    def interim(self) -> Path:
        return self.pipeline / "data" / "interim"

    @property
    def karte(self) -> Path:
        return self.repo / "public" / "data"


@cache
def _yaml(pfad: Path):
    with pfad.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _quellen(ordner: Path) -> dict[str, dict]:
    """Eine Datei je Quelle, der Dateiname ist der Code. Reihenfolge nach `nr` – die der Quellen
    in den Kartendaten; `nr` selbst gibt der Lader nicht weiter."""
    eintraege = []
    for pfad in sorted(ordner.glob("*.yaml")):
        if not CODE.fullmatch(pfad.stem):
            raise ValueError(f"{pfad}: Code {pfad.stem!r} – nur Kleinbuchstaben, Ziffern und _")
        q = dict(_yaml(pfad))
        nr = q.pop("nr", None)
        if type(nr) is not int or nr < 1:
            raise ValueError(f"{pfad}: `nr` fehlt oder ist keine positive ganze Zahl")
        eintraege.append((nr, pfad.stem, q))
    if doppelt := sorted(nr for nr, n in Counter(e[0] for e in eintraege).items() if n > 1):
        raise ValueError(f"{ordner}: `nr` doppelt vergeben: {doppelt}")
    return {code: q for _, code, q in sorted(eintraege, key=lambda e: e[0])}


def _kommunen(ordner: Path) -> list[dict]:
    """Datenlage: je Land eine Datei (`<LAND>.yaml`, eine Liste), die Länder nach Kürzel."""
    alle = []
    for pfad in sorted(ordner.glob("*.yaml")):
        eintraege = _yaml(pfad) or []
        if not isinstance(eintraege, list):
            raise ValueError(f"{pfad}: eine Liste von Kommunen erwartet")
        alle.extend(eintraege)
    return alle


@cache
def _konfiguration(config: Path) -> dict:
    def datei(name: str, leer):
        pfad = config / name
        return _yaml(pfad) if pfad.is_file() else leer

    return {
        "quellen": _quellen(config / "quellen" / "kurzzeit"),
        "dauer": _quellen(config / "quellen" / "dauer"),
        "datenlage": _kommunen(config / "kommunen"),
        "recht": datei("recht.yaml", {}),
        "anfrage_vorlage": datei("anfrage_vorlage.yaml", None),
        "robots": datei("robots.yaml", []),
    }


def konfiguration(pfade: Pfade | None = None) -> dict:
    """Die ganze Konfiguration aus `pipeline/config/`: `quellen` (Kurzzeit) und `dauer` (Code ->
    Eintrag, nach `nr`), `datenlage` (die Kommunen aller Länder), `recht` (Land -> Rechtslage),
    `anfrage_vorlage`, `robots` (Ausnahmen von robots.txt)."""
    return _konfiguration((pfade or Pfade()).config)


def quellen(pfade: Pfade | None = None, nur_live: bool = True) -> dict[str, dict]:
    """Kurzzeit-Quellen (Code -> Eintrag, `config/quellen/kurzzeit/`), standardmäßig nur
    `status: live`."""
    alle = konfiguration(pfade)["quellen"]
    return {k: {**v, "code": k} for k, v in alle.items() if not nur_live or v["status"] == "live"}


def dauerquellen(pfade: Pfade | None = None, nur_live: bool = True) -> dict[str, dict]:
    """Quellen der Familie Dauerzählstellen (`config/quellen/dauer/`)."""
    alle = konfiguration(pfade)["dauer"]
    return {k: {**v, "code": k} for k, v in alle.items() if not nur_live or v["status"] == "live"}
