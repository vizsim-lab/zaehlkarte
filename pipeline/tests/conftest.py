from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from zaehlkarte import abruf, ckan

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
