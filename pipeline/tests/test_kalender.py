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
    assert tagtyp(date(2022, 11, 15), "BW", k) == ("schule", None)
    assert tagtyp(date(2011, 11, 15), "BW", k) == (None, None)  # Schuljahr fehlt
    assert tagtyp(date(2013, 9, 6), "BW", k) == ("ferien", "Sommerferien")  # aus kmk_ferien.py


def test_bayern_feiertage_und_ferien():
    assert date(2025, 8, 15) in feiertage("BY", 2025)  # Mariä Himmelfahrt (München)
    assert date(2025, 1, 6) in feiertage("BY", 2025) and date(2025, 11, 1) in feiertage("BY", 2025)
    assert date(2025, 8, 15) not in feiertage("BW", 2025)
    k = Ferienkalender.lade(Pfade().config / "schulferien_bayern.csv")
    assert tagtyp(date(2025, 11, 19), "BY", k) == ("ferien", "Buß- und Bettag (unterrichtsfrei)")
    assert tagtyp(date(2026, 2, 17), "BY", k) == ("ferien", "Frühjahrsferien")
    assert tagtyp(date(2026, 4, 1), "BY", k) == ("ferien", "Osterferien")
    assert tagtyp(date(2008, 6, 3), "BY", k) == ("schule", None)
    assert tagtyp(date(2026, 11, 12), "BY", k) == ("schule", None)


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
    assert tagtyp(date(2026, 11, 12), "NW", k) == ("schule", None)  # 2026/27 aus kmk_ferien.py
    assert tagtyp(date(2026, 10, 20), "NW", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2009, 10, 15), "NW", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2000, 1, 6), "NW", k) == ("ferien", "Weihnachtsferien")
    assert tagtyp(date(2003, 9, 11), "NW", k) == ("ferien", "Sommerferien")  # bis 13.09.
    assert tagtyp(date(2003, 9, 16), "NW", k) == ("schule", None)
    assert tagtyp(date(2010, 5, 25), "NW", k) == ("ferien", "Pfingstferien")  # ein Tag


def test_brandenburg_feiertage_und_ferien():
    assert date(2013, 10, 31) in feiertage("BB", 2013)  # Reformationstag
    assert date(2013, 11, 1) not in feiertage("BB", 2013)
    k = Ferienkalender.lade(Pfade().config / "schulferien_brandenburg.csv")
    assert tagtyp(date(2019, 4, 11), "BB", k) == ("schule", None)
    assert tagtyp(date(2013, 10, 10), "BB", k) == ("ferien", "Herbstferien")  # zweizeilige Zelle
    assert tagtyp(date(2013, 11, 1), "BB", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2023, 7, 6), "BB", k) == ("schule", None)  # Sommerferien ab 13.07.
    assert tagtyp(date(2023, 7, 13), "BB", k) == ("ferien", "Sommerferien")


def test_nrw_ab_2020():
    k = Ferienkalender.lade(Pfade().config / "schulferien_nordrhein-westfalen.csv")
    assert tagtyp(date(2020, 8, 25), "NW", k) == ("schule", None)  # Xanten, nach den Sommerferien
    assert tagtyp(date(2022, 7, 12), "NW", k) == ("ferien", "Sommerferien")
