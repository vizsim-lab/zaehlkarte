from __future__ import annotations

from datetime import date

from zaehlkarte.config import Pfade
from zaehlkarte.kalender import Ferienkalender, feiertage, tagtyp


def test_feiertage_je_land():
    assert date(2024, 3, 8) in feiertage("BE", 2024)  # Frauentag nur Berlin
    assert date(2024, 3, 8) not in feiertage("BW", 2024)
    assert date(2024, 5, 30) in feiertage("BW", 2024)  # Fronleichnam
    assert date(2024, 1, 6) in feiertage("BW", 2024)
    assert date(2025, 5, 8) in feiertage("BE", 2025)  # 80. Jahrestag der Befreiung


def test_bw_ferien_und_schultage():
    k = Ferienkalender.lade(Pfade().config / "schulferien_baden-wuerttemberg.csv")
    assert tagtyp(date(2023, 11, 16), "BW", k) == ("schule", None)
    assert tagtyp(date(2024, 7, 25), "BW", k) == ("ferien", "Sommerferien")
    assert tagtyp(date(2025, 10, 31), "BW", k)[0] == "ferien"  # unterrichtsfreier Tag
    assert tagtyp(date(2024, 2, 24), "BW", k) == ("wochenende", "Samstag")
    assert tagtyp(date(2022, 11, 15), "BW", k) == (None, None)  # Schuljahr fehlt


def test_berlin_west_ost_vor_1991():
    k = Ferienkalender.lade(Pfade().config / "schulferien_berlin.csv")
    assert k.status(date(1989, 7, 25), "west") == ("ferien", "Sommerferien")
    assert k.status(date(1989, 7, 10), "west") == ("schule", None)
    # Gebiet unbekannt: nur sicher, wenn beide Kalender dasselbe sagen
    assert k.status(date(1989, 7, 25), None)[0] in ("ferien", None)
    assert k.status(date(2019, 9, 2), None) == ("schule", None)  # seit 1991 ein Kalender


def test_nrw_feiertage_und_ferien():
    assert date(2009, 6, 11) in feiertage("NW", 2009)  # Fronleichnam
    assert date(2009, 11, 1) in feiertage("NW", 2009)  # Allerheiligen
    assert date(2009, 1, 6) not in feiertage("NW", 2009)
    k = Ferienkalender.lade(Pfade().config / "schulferien_nordrhein-westfalen.csv")
    assert tagtyp(date(2009, 4, 23), "NW", k) == ("schule", None)
    assert tagtyp(date(2009, 10, 15), "NW", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2000, 1, 6), "NW", k) == ("ferien", "Weihnachtsferien")
    assert tagtyp(date(2003, 9, 11), "NW", k) == ("ferien", "Sommerferien")  # bis 13.09.
    assert tagtyp(date(2003, 9, 16), "NW", k) == ("schule", None)
    assert tagtyp(date(2010, 5, 25), "NW", k) == ("ferien", "Pfingstferien")  # ein Tag
