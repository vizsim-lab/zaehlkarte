"""werkzeuge/kmk_ferien.py: Ferien aus der Tabelle des KMK-PDFs (pdfplumber, hier nachgebaut)
und die Einträge einer Zelle – mehrere je Zelle, Tag ohne Monat, kein Bereich über eine leere
Nachbarzelle hinweg."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import date
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).resolve().parents[1] / "werkzeuge" / "kmk_ferien.py"


@pytest.fixture(scope="module")
def kmk():
    spec = importlib.util.spec_from_file_location("kmk_ferien", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _pdf(monkeypatch, tabelle: list[list[str | None]]) -> None:
    """pdfplumber.open(...) liefert eine Seite mit dieser Tabelle."""

    class Seite:
        def extract_tables(self):
            return [tabelle]

    class Pdf:
        pages = [Seite()]

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setitem(sys.modules, "pdfplumber", types.SimpleNamespace(open=lambda p: Pdf()))


@pytest.mark.parametrize(("zelle", "erwartet"), [
    ("04.10. - 19.10.\n01.11.", [(4, 10, 19, 10), (1, 11, 1, 11)]),
    ("30.04. und 02.05.", [(30, 4, 30, 4), (2, 5, 2, 5)]),
    ("02.10. / 16. - 30.10.", [(2, 10, 2, 10), (16, 10, 30, 10)]),
    ("05. – 17.10.", [(5, 10, 17, 10)]),
    ("07.04 - 19.04.", [(7, 4, 19, 4)]),
    ("26.04. - 30.04.2", [(26, 4, 30, 4)]),
    ("10.05.3)/21. - 25.05.", [(10, 5, 10, 5), (21, 5, 25, 5)]),
    # Text einer ganzen Zeile: ein Strich mit viel Abstand ist eine leere Nachbarzelle
    ("10.03. - 22.03. / 22.04.          -          30.06. - 09.08.",
     [(10, 3, 22, 3), (22, 4, 22, 4), (30, 6, 9, 8)]),
    ("--", []),
])
def test_eintraege_einer_zelle(kmk, zelle, erwartet):
    assert [kmk._paar(m) for m in kmk.EINTRAG.finditer(zelle)] == erwartet


def test_tabelle_mit_zwei_sommerspalten_und_fussnote(kmk, monkeypatch):
    """2001/02: Sommer 2001 vorn und Sommer 2002 hinten, die Jahre aus dem Kopf; vor dem Namen
    eine Fußnote („2\\nSchleswig-Holstein“), Klammern mit beweglichen Ferientagen."""
    _pdf(monkeypatch, [
        ["Land 2)", "Sommer\n2001", "Herbst\n2001", "Weihnachten\n2001/2002", "Winter\n2002",
         "Ostern/Frühjahr\n2002", "Himmelfahrt/Pfingsten\n2002", "Sommer\n2002"],
        ["Hamburg (-)", "19.07. - 29.08.", "15.10. - 27.10.", "24.12. - 05.01.", "01.02. 3)",
         "04.03. - 16.03.", "10.05.3)/21. - 25.05.", "04.07. - 14.08."],
        ["2\nSchleswig-Holstein (1)", "19.07. - 29.08.", "--", "24.12. - 05.01.", "-", "-", "-",
         "04.07. - 14.08."],
    ])
    hh = kmk.lies_pdf(Path("FER2001_02.pdf"), "Hamburg", "2001/2002")
    assert hh == [
        (date(2001, 7, 19), date(2001, 8, 29), "Sommerferien"),
        (date(2001, 10, 15), date(2001, 10, 27), "Herbstferien"),
        (date(2001, 12, 24), date(2002, 1, 5), "Weihnachtsferien"),
        (date(2002, 2, 1), date(2002, 2, 1), "Winterferien"),
        (date(2002, 3, 4), date(2002, 3, 16), "Osterferien"),
        (date(2002, 5, 10), date(2002, 5, 10), "Pfingstferien"),
        (date(2002, 5, 21), date(2002, 5, 25), "Pfingstferien"),
        (date(2002, 7, 4), date(2002, 8, 14), "Sommerferien"),
    ]
    sh = kmk.lies_pdf(Path("FER2001_02.pdf"), "Schleswig-Holstein", "2001/2002")
    assert [n for *_, n in sh] == ["Sommerferien", "Weihnachtsferien", "Sommerferien"]


def test_bayern_fruehjahrsferien_und_unbekanntes_land(kmk, monkeypatch):
    _pdf(monkeypatch, [
        ["Land*", "Herbst\n2024", "Weihnachten\n2024/2025", "Winter\n2025", "Ostern/Frühjahr\n2025",
         "Himmelfahrt/Pfingsten\n2025", "Sommer\n2025"],
        ["Bayern", "28.10. - 31.10.", "23.12. - 03.01.", "--", "03.03. - 07.03.\n14.04. - 25.04.",
         "10.06. - 20.06.", "01.08.\n04.08. - 15.09."],
    ])
    by = kmk.lies_pdf(Path("FER2024_25.pdf"), "Bayern", "2024/2025")
    assert [(v, n) for v, _, n in by if n in ("Frühjahrsferien", "Osterferien")] == [
        (date(2025, 3, 3), "Frühjahrsferien"), (date(2025, 4, 14), "Osterferien")]
    with pytest.raises(ValueError, match="Hessen nicht in der Tabelle"):
        kmk.lies_pdf(Path("FER2024_25.pdf"), "Hessen", "2024/2025")
