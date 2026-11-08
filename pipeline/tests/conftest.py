from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def kriterium_faelle() -> dict:
    return json.loads((REPO / "tests" / "fixtures" / "kriterium.json").read_text(encoding="utf-8"))
