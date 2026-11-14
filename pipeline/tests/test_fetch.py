"""Abruf der Kurzzeitzählungen: Eine Quelle, die scheitert, hält die anderen nicht auf; der
Bericht nennt sie, und `zaehlkarte fetch` endet mit Exit-Code 1 (ohne ihre Rohdaten fehlte sie
im Bau). `zaehlkarte dauer fetch` scheitert weiter nur, wenn alle Quellen scheitern."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from zaehlkarte import cli, fetch
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bau

QUELLEN = {code: {"code": code, "adapter": "test"} for code in ("a", "b", "c")}


@pytest.fixture
def pfade(tmp_path) -> Pfade:
    return Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)


def test_eine_quelle_scheitert_die_anderen_laufen_weiter(monkeypatch, pfade):
    geholt = []

    def hole_quelle(code, q, pfade):
        geholt.append(code)
        if code == "b":
            raise ConnectionError("Portal antwortet nicht")
        return [f"{code}: geladen"]

    monkeypatch.setattr(fetch, "quellen", lambda pfade: QUELLEN)
    monkeypatch.setattr(fetch, "hole_quelle", hole_quelle)
    log, fehler = fetch.hole(pfade)
    assert geholt == ["a", "b", "c"]
    assert fehler == ["b"]
    assert log[0] == "a: geladen" and log[-1] == "c: geladen"
    assert "FEHLER b: ConnectionError('Portal antwortet nicht')" in log
    assert fetch.hole(pfade, nur=["a"]) == (["a: geladen"], [])


def test_unbekannter_adapter_ist_ein_fehler_der_quelle(monkeypatch, pfade):
    q = {"code": "x", "adapter": "gibt_es_nicht"}
    with pytest.raises(ValueError, match="kein Abruf für den Adapter"):
        fetch.hole_quelle("x", q, pfade)
    monkeypatch.setattr(fetch, "quellen", lambda pfade: {"x": q})
    log, fehler = fetch.hole(pfade)
    assert fehler == ["x"] and log[0].startswith("FEHLER x: ValueError")


@pytest.mark.parametrize(("fehler", "code"), [([], 0), (["b"], 1)])
def test_cli_fetch_exit_code(monkeypatch, fehler, code):
    monkeypatch.setattr(fetch, "hole", lambda nur=None: (["a: geladen"], fehler))
    r = CliRunner().invoke(cli.app, ["fetch"])
    assert r.exit_code == code
    assert "a: geladen" in r.output
    assert ("Abruf gescheitert: b" in r.output) == bool(fehler)


@pytest.mark.parametrize(("fehler", "code"), [([], 0), (["a"], 0), (["a", "b"], 1)])
def test_cli_dauer_fetch_scheitert_nur_wenn_alle_scheitern(monkeypatch, fehler, code):
    monkeypatch.setattr(bau, "hole", lambda nur=None: (["geholt"], fehler))
    monkeypatch.setattr("zaehlkarte.config.dauerquellen", lambda pfade=None: {"a": {}, "b": {}})
    r = CliRunner().invoke(cli.app, ["dauer", "fetch"])
    assert r.exit_code == code
    assert ("Abruf gescheitert" in r.output) == bool(fehler)
