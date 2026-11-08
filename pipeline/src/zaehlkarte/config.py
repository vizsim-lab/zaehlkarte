"""Pfade und Konfiguration der Pipeline.

- `pipeline/config/*.yaml` – Quellen (`sources.yaml`, die einzige Quellenliste), Kriterien
- `pipeline/data/` – Rohdaten und Zwischenstände (gitignored, `zaehlkarte fetch` holt sie)
- `public/data/` – die Kartendaten (im Git; Vite kopiert `public/` unverändert nach `dist/`)
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

PIPELINE = Path(__file__).resolve().parents[2]
REPO = PIPELINE.parent


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
def _lade(pfad: Path) -> dict:
    with pfad.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def lade_yaml(name: str, pfade: Pfade | None = None) -> dict:
    return _lade((pfade or Pfade()).config / name)


def quellen(pfade: Pfade | None = None, nur_live: bool = True) -> dict[str, dict]:
    """Quellen aus sources.yaml (Code -> Eintrag), standardmäßig nur `status: live`."""
    alle = lade_yaml("sources.yaml", pfade)["quellen"]
    return {k: {**v, "code": k} for k, v in alle.items() if not nur_live or v["status"] == "live"}
