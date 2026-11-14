from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
import yaml

from zaehlkarte import abruf, ckan, datenlage

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def robots_offen(monkeypatch):
    """Ohne Netz: jede robots.txt leer (alles erlaubt, kein Crawl-delay), Zustand von `abruf` und
    `ckan` je Test frisch. test_abruf.py setzt eigene robots.txt."""
    monkeypatch.setattr(abruf, "_robots_text", lambda basis: (200, ""))
    monkeypatch.setattr(abruf, "_REGELN", {})
    monkeypatch.setattr(abruf, "_ZULETZT", {})
    monkeypatch.setattr(abruf, "_AUSNAHMEN", [])
    monkeypatch.setattr(abruf, "GENUTZT", Counter())
    monkeypatch.setattr(abruf, "GEWARTET", Counter())
    monkeypatch.setattr(ckan, "_OHNE", set())


def _schreibe_konfiguration(config: Path, cfg: dict) -> None:
    """Eine Konfiguration in der Gestalt von `config.konfiguration()` als Ordner schreiben: je
    Quelle eine Datei (`nr` nach der Reihenfolge im dict), die Kommunen je Land (aus `ags`)."""

    def schreibe(pfad: Path, inhalt) -> None:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_text(yaml.safe_dump(inhalt, allow_unicode=True, sort_keys=False),
                        encoding="utf-8")

    for schluessel, familie in (("quellen", "kurzzeit"), ("dauer", "dauer")):
        for nr, (code, q) in enumerate((cfg.get(schluessel) or {}).items(), start=1):
            schreibe(config / "quellen" / familie / f"{code}.yaml", {"nr": nr, **q})
    je_land: dict[str, list[dict]] = {}
    for e in cfg.get("datenlage") or []:  # das Land aus dem Gemeindeschlüssel
        je_land.setdefault(datenlage.LAND[e["ags"][:2]], []).append(e)
    for land, eintraege in je_land.items():
        schreibe(config / "kommunen" / f"{land}.yaml", eintraege)
    for name in ("recht", "anfrage_vorlage", "robots"):
        if name in cfg:
            schreibe(config / f"{name}.yaml", cfg[name])


@pytest.fixture
def schreibe_konfiguration():
    """Für Tests mit eigener Konfiguration: `schreibe_konfiguration(pfade.config, cfg)`."""
    return _schreibe_konfiguration
