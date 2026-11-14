"""Der Lader der Konfiguration (`config.konfiguration`): eine Datei je Quelle, Reihenfolge nach
`nr`, die Kommunen je Land – und Fehler, die den Bau anhalten, statt still durchzugehen."""

from __future__ import annotations

from pathlib import Path

import pytest

from zaehlkarte.config import Pfade, dauerquellen, konfiguration, quellen


def _pfade(tmp_path: Path) -> Pfade:
    return Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)


def _datei(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")


def test_quellen_nach_nr_ohne_nr(tmp_path):
    """Die Reihenfolge der Quellen ist die von `nr`, nicht die der Dateinamen – so bleiben die
    Kartendaten gleich, wenn eine Quelle dazukommt; `nr` selbst gibt der Lader nicht weiter."""
    p = _pfade(tmp_path)
    _datei(p.config / "quellen" / "kurzzeit" / "berlin.yaml", "nr: 1\nstatus: live\nland: BE\n")
    _datei(p.config / "quellen" / "kurzzeit" / "aachen.yaml", "nr: 3\nstatus: research\n")
    _datei(p.config / "quellen" / "kurzzeit" / "moers.yaml", "nr: 2\nstatus: live\nland: NW\n")
    _datei(p.config / "quellen" / "dauer" / "rad.yaml", "nr: 1\nstatus: live\n")
    cfg = konfiguration(p)
    assert list(cfg["quellen"]) == ["berlin", "moers", "aachen"]
    assert cfg["quellen"]["berlin"] == {"status": "live", "land": "BE"}
    assert list(quellen(p)) == ["berlin", "moers"]  # nur live, mit Code
    assert quellen(p)["moers"]["code"] == "moers"
    assert list(dauerquellen(p)) == ["rad"]
    assert (cfg["datenlage"], cfg["recht"], cfg["robots"]) == ([], {}, [])


@pytest.mark.parametrize("dateien, meldung", [
    ({"a.yaml": "status: live\n"}, "`nr` fehlt"),
    ({"a.yaml": "nr: 0\n"}, "keine positive ganze Zahl"),
    ({"a.yaml": "nr: true\n"}, "keine positive ganze Zahl"),
    ({"a.yaml": "nr: 1\n", "b.yaml": "nr: 1\n"}, r"`nr` doppelt vergeben: \[1\]"),
    ({"Gross.yaml": "nr: 1\n"}, "Code 'Gross'"),
])
def test_fehler_in_quelldateien(tmp_path, dateien, meldung):
    p = _pfade(tmp_path)
    for name, text in dateien.items():
        _datei(p.config / "quellen" / "dauer" / name, text)
    with pytest.raises(ValueError, match=meldung):
        konfiguration(p)


def test_kommunen_je_land_nach_kuerzel(tmp_path):
    p = _pfade(tmp_path)
    _datei(p.config / "kommunen" / "NW.yaml", "- kommune: Moers\n- kommune: Aachen\n")
    _datei(p.config / "kommunen" / "BE.yaml", "- kommune: Berlin\n")
    _datei(p.config / "kommunen" / "HB.yaml", "")  # leer: keine Kommune
    namen = [e["kommune"] for e in konfiguration(p)["datenlage"]]
    assert namen == ["Berlin", "Moers", "Aachen"]


def test_kommunen_als_liste(tmp_path):
    p = _pfade(tmp_path)
    _datei(p.config / "kommunen" / "NW.yaml", "kommune: Moers\n")
    with pytest.raises(ValueError, match="eine Liste von Kommunen"):
        konfiguration(p)


def test_echte_konfiguration_vollstaendig():
    """Die echte Konfiguration liefert alle Teile."""
    cfg = konfiguration()
    assert cfg["quellen"] and cfg["dauer"] and cfg["datenlage"] and cfg["robots"]
    assert cfg["anfrage_vorlage"]["text"] and len(cfg["recht"]) == 16
