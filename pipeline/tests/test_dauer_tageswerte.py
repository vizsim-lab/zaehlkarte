"""Tageswerte der Quelle im Modell der Dauerzählstellen (modell.py, site.py): Quellen nur mit
Tageswerten und Tageswerte vor der ersten gezählten Stunde – nie als Ersatz fehlender Stunden."""

from __future__ import annotations

import json
import shutil
from datetime import date

import numpy as np
import pytest

from zaehlkarte.config import PIPELINE, Pfade
from zaehlkarte.dauer import site
from zaehlkarte.dauer.modell import (
    Dauerstelle,
    Messreihe,
    aus_tageswerten,
    kuerze,
    setze_lokal,
    setze_tage,
    tagessummen,
)
from zaehlkarte.kalender import FERIEN

Q = {"code": "test_tw", "name": "Test (Rad)", "land": "BY", "lizenz": "CC BY 4.0",
     "lizenz_url": "https://creativecommons.org/licenses/by/4.0/", "titel": "Test"}


def _stelle(k: str) -> Dauerstelle:
    return Dauerstelle("test_tw", k, f"Stelle {k}", None, None, 10.9, 48.37, "BY")


def _tage(*isos: str) -> np.ndarray:
    return np.array(isos, dtype="datetime64[D]")


def _reihe() -> Messreihe:
    return Messreihe.leer("test_tw", date(2025, 6, 2), date(2025, 6, 8),
                          [_stelle("a"), _stelle("b")], ("rad",), tagesgruppen=("rad",))


def test_nur_tageswerte():
    r = _reihe()
    gesetzt, widerspruch = setze_tage(
        r, "rad", np.array([0, 0, 0, 1, 1]), _tage("2025-06-02", "2025-06-03", "2025-06-04",
                                                   "2025-06-02", "2025-06-02"),
        np.array([1200, 0, -1, 500, 501]))
    assert (gesetzt, widerspruch) == (2, 1)  # -1: nicht gezählt; b am 2.6. widersprüchlich
    summen, n = tagessummen(r, "rad")
    assert summen[0, :3].tolist() == [1200, 0, -1]  # 0 wie geliefert, -1 nicht gezählt
    assert summen[1, 0] == -1
    assert n[0, 0] == 0  # keine gezählte Stunde
    assert aus_tageswerten(r, "rad")[0].tolist() == [True, True, False, False, False, False,
                                                     False]


def test_tageswerte_nur_vor_der_ersten_stunde():
    r = _reihe()
    setze_tage(r, "rad", np.zeros(5, dtype=int),
               _tage("2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06"),
               np.array([100, 110, 120, 130, 140]))
    # Stunden ab dem 4.6.: der 4.6. vollständig, am 5.6. fehlt 8 Uhr
    for tag, ohne in (("2025-06-04", None), ("2025-06-05", 8)):
        h = np.array([x for x in range(24) if x != ohne])
        setze_lokal(r, "rad", np.zeros(len(h), dtype=int), _tage(*[tag] * len(h)), h,
                    np.full(len(h), 10))
    summen, n = tagessummen(r, "rad")
    assert summen[0, :5].tolist() == [100, 110, 240, -1, -1]  # ab der ersten Stunde nur Stunden
    assert n[0, 3] == 23
    assert aus_tageswerten(r, "rad")[0, :5].tolist() == [True, True, False, False, False]


def test_kuerze_behaelt_tageswerte():
    r = Messreihe.leer("test_tw", date(2025, 6, 1), date(2025, 6, 30), [_stelle("a")], ("rad",),
                       tagesgruppen=("rad",))
    setze_tage(r, "rad", np.array([0, 0]), _tage("2025-06-10", "2025-06-12"), np.array([5, 6]))
    kuerze(r)
    assert (r.von, r.tage) == (date(2025, 6, 10), 3)
    assert r.tageswerte["rad"].shape == (1, 3)


def test_tagesgruppe_braucht_reihe():
    with pytest.raises(ValueError, match="ohne Reihe"):
        Messreihe.leer("x", date(2025, 1, 1), date(2025, 1, 2), [], ("kfz",), ("rad",))


def test_site_schreibt_tageswerte(tmp_path):
    pfade = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    (pfade.config / FERIEN).mkdir(parents=True)
    shutil.copy(PIPELINE / "config" / FERIEN / "BY.csv", pfade.config / FERIEN)
    r = _reihe()
    # a: nur Tageswerte (2.–6.6.); b: Tageswerte 2.–3.6., Stunden ab 4.6.
    setze_tage(r, "rad", np.array([0, 0, 0, 0, 0, 1, 1]),
               _tage("2025-06-02", "2025-06-03", "2025-06-04", "2025-06-05", "2025-06-06",
                     "2025-06-02", "2025-06-03"),
               np.array([1000, 1100, 1200, 1300, 1400, 50, 60]))
    for tag in ("2025-06-04", "2025-06-05"):
        setze_lokal(r, "rad", np.ones(24, dtype=int), _tage(*[tag] * 24), np.arange(24),
                    np.full(24, 3))
    _, bericht = site.schreibe([(Q, r)], pfade, erzeugt=date(2026, 11, 14))
    ziel = pfade.karte / "dauer"
    index = json.loads((ziel / "index.json").read_text())
    assert index["version"] == site.VERSION >= 4
    ids = [w[0] for w in index["stellen"]["werte"]]
    assert ids == ["test_tw:a", "test_tw:b"]
    assert index["tageswerte_bis"] == {"rad": ["2025-06-06", "2025-06-03"]}
    q = index["quellen"][0]
    assert q["tageswerte"] == {"rad": ["2025-06-02", "2025-06-06"]}
    assert q["zeitraeume"]["rad"] == ["2025-06-02", "2025-06-06"]
    # jüngster Schultag: a am 6.6. (Tageswert), b am 5.6. (Summe der Stunden)
    assert index["juengster"]["rad"] == [["2025-06-06", 1400], ["2025-06-05", 72]]
    jahr = json.loads((ziel / "tage" / "2025.json").read_text())
    t0 = (date(2025, 6, 2) - date(2025, 1, 1)).days
    assert jahr["werte"]["rad"][0][t0:t0 + 5] == [1000, 1100, 1200, 1300, 1400]
    assert jahr["werte"]["rad"][1][t0:t0 + 5] == [50, 60, 72, 72, None]
    chunk = json.loads((ziel / "0.json").read_text())["stellen"]
    assert chunk["test_tw:a"]["tageswerte_bis"] == {"rad": "2025-06-06"}
    assert chunk["test_tw:a"]["n"]["rad"][:2] == [0, 0]
    assert chunk["test_tw:b"]["tageswerte_bis"] == {"rad": "2025-06-03"}
    assert any("Tageswerte der Quelle (rad): 7" in z for z in site.statistik([(Q, r)]))
    assert any("2 Stellen" in z for z in bericht)


def test_site_ohne_tageswerte_ohne_feld(tmp_path):
    pfade = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    (pfade.config / FERIEN).mkdir(parents=True)
    shutil.copy(PIPELINE / "config" / FERIEN / "BY.csv", pfade.config / FERIEN)
    r = Messreihe.leer("test_tw", date(2025, 6, 2), date(2025, 6, 2), [_stelle("a")], ("rad",))
    setze_lokal(r, "rad", np.zeros(24, dtype=int), _tage(*["2025-06-02"] * 24), np.arange(24),
                np.full(24, 1))
    site.schreibe([(Q, r)], pfade, erzeugt=date(2026, 11, 14))
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    assert index["tageswerte_bis"] == {} and index["quellen"][0]["tageswerte"] == {}
    chunk = json.loads((pfade.karte / "dauer" / "0.json").read_text())["stellen"]
    assert chunk["test_tw:a"]["tageswerte_bis"] == {}
