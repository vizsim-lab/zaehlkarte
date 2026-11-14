"""Augsburg, Radzählstationen (dauer/augsburg_rad.py) mit einer synthetischen Datei im Aufbau der
Quelle: Zeile „Zeitraum,…“, Leerzeile, ungequoteter Kopf (ein Name mit Komma), je Tag eine Zeile."""

from datetime import date

import pytest

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import augsburg_rad
from zaehlkarte.dauer.modell import aus_tageswerten, tagessummen

STATIONEN = [
    {"name": "Dieselbrücke", "kennung": "dieselbruecke", "lon": 10.87, "lat": 48.38},
    {"name": "Südlich A8-Unterführung, Ostseite", "kennung": "a8-ost", "lon": 10.92,
     "lat": 48.41, "strasse": "Lechdamm", "abschnitt": "südlich der A8",
     "hinweise": ["Lage ungefähr"]},
    {"name": "Wagenhalsstraße", "kennung": "wagenhalsstrasse", "lon": 10.88, "lat": 48.36},
]
Q = {"code": "augsburg_rad", "land": "BY", "stationen": STATIONEN}
KOPF = "Zeit,Dieselbrücke,Südlich A8-Unterführung, Ostseite,Wagenhalsstraße"


def _schreibe(tmp_path, zeilen: list[str], kopf: str = KOPF) -> Pfade:
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / "augsburg_rad"
    ordner.mkdir(parents=True)
    text = "\n".join(["Zeitraum,2. Juni 2025 - 6. Juni 2025", "", kopf, *zeilen]) + "\n"
    (ordner / augsburg_rad.DATEI).write_text(text, encoding="utf-8")
    return pfade


def test_lese(tmp_path):
    pfade = _schreibe(tmp_path, [
        "2025-06-02 00:00:00,1200,,800",
        "2025-06-03 00:00:00,1300,0,810",
        "2025-06-04 00:00:00,x,5,820",  # ein unlesbarer Wert
        "kein Datum,1,2,3",
        "2025-06-05 00:00:00,1500,7,",
        "2025-06-06 00:00:00,12,1,3",  # Tag der Erstellung: nur zum Teil gezählt
    ])
    bericht = augsburg_rad.Bericht()
    reihe = augsburg_rad.lese(Q, pfade, bericht)
    assert [s.id for s in reihe.stellen] == ["augsburg_rad:dieselbruecke", "augsburg_rad:a8-ost",
                                            "augsburg_rad:wagenhalsstrasse"]
    assert (reihe.stellen[1].name, reihe.stellen[1].abschnitt) == ("Lechdamm", "südlich der A8")
    assert reihe.stellen[0].name == "Dieselbrücke"
    assert reihe.stellen[1].hinweise == ["Lage ungefähr"]
    assert (reihe.von, reihe.tag(reihe.tage - 1)) == (date(2025, 6, 2), date(2025, 6, 5))
    summen, n = tagessummen(reihe, "rad")
    assert summen[0].tolist() == [1200, 1300, -1, 1500]  # 4.6. unlesbar: nicht gezählt
    assert summen[1].tolist() == [-1, 0, 5, 7]  # leer: nicht gezählt, 0 wie geliefert
    assert summen[2].tolist() == [800, 810, 820, -1]
    assert n.max() == 0 and aus_tageswerten(reihe, "rad").sum() == 9
    assert bericht.unlesbar == 1 and bericht.unlesbare_werte == 1 and bericht.tage == 9
    assert bericht.weggelassen == "2025-06-06" and bericht.bis == "2025-06-05"
    assert bericht.nullen == {"Lechdamm": 1}
    assert bericht.zeitraum == "2025-06-02 – 2025-06-06"


def test_kopf_muss_passen(tmp_path):
    pfade = _schreibe(tmp_path, ["2025-06-02 00:00:00,1,2,3"],
                      kopf="Zeit,Dieselbrücke,Wagenhalsstraße,Südlich A8-Unterführung, Ostseite")
    with pytest.raises(ValueError, match="Kopf der Datei"):
        augsburg_rad.lese(Q, pfade, augsburg_rad.Bericht())


def test_zeitraum_und_wert():
    assert augsburg_rad.zeitraum("Zeitraum,16. September 2016 - 11. August 2026") == (
        date(2016, 9, 16), date(2026, 8, 11))
    assert augsburg_rad.zeitraum("Zeitraum,1. März 2020 - 2. Mai 2020") == (
        date(2020, 3, 1), date(2020, 5, 2))
    assert augsburg_rad.zeitraum("Zeitraum,irgendwann") == (None, None)
    assert augsburg_rad.wert(" 2076 ") == 2076 and augsburg_rad.wert("") is None
    assert augsburg_rad.wert("12.0") == 12
    with pytest.raises(ValueError):
        augsburg_rad.wert("-3")
