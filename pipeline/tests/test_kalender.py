from __future__ import annotations

from datetime import date

from zaehlkarte.config import Pfade
from zaehlkarte.kalender import (
    FEIERTAGE_LAENDER,
    LAENDER,
    Ferienkalender,
    feiertage,
    ferienkalender,
    tagtyp,
)


def test_feiertage_laender_wie_umgesetzt():
    """FEIERTAGE_LAENDER nennt genau die Länder, für die `feiertage()` mehr als die bundesweiten
    kennt – jedes Land hat mindestens einen eigenen Feiertag."""
    bund = feiertage("XX", 2026)
    mit_eigenen = {land for land in LAENDER if len(feiertage(land, 2026)) > len(bund)}
    assert mit_eigenen == FEIERTAGE_LAENDER


def test_feiertage_der_uebrigen_laender():
    """HE, RP, SL, ST, TH – mit den Jahren, ab denen ein Feiertag gilt."""
    fronleichnam = date(2026, 6, 4)
    assert all(fronleichnam in feiertage(land, 2026) for land in ("HE", "RP", "SL"))
    assert date(2026, 11, 1) in feiertage("RP", 2026) and date(2026, 11, 1) in feiertage("SL", 2026)
    assert date(2026, 11, 1) not in feiertage("HE", 2026)
    assert feiertage("SL", 2026)[date(2026, 8, 15)] == "Mariä Himmelfahrt"
    assert date(1993, 1, 6) in feiertage("ST", 1993)
    assert date(1992, 1, 6) not in feiertage("ST", 1992)
    assert date(2026, 10, 31) in feiertage("ST", 2026)
    assert feiertage("TH", 2019)[date(2019, 9, 20)] == "Weltkindertag"
    assert date(2018, 9, 20) not in feiertage("TH", 2018)
    assert date(2026, 10, 31) in feiertage("TH", 2026)


def test_neue_laender_ferien_und_schultage():
    """Hessen 2026/27 laut KMK-Kalender: Herbstferien 05.–17.10., ab 19.10. Schule, Fronleichnam
    Feiertag; Schuljahre vor 1999/2000 unbekannt."""
    k = ferienkalender("HE", Pfade().config)
    assert tagtyp(date(2026, 10, 5), "HE", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2026, 10, 19), "HE", k) == ("schule", None)
    assert tagtyp(date(2027, 5, 27), "HE", k) == ("feiertag", "Fronleichnam")
    assert tagtyp(date(1998, 9, 1), "HE", k) == (None, None)
    sh = ferienkalender("SH", Pfade().config)
    # Zelle „02.10. / 16. - 30.10.“
    assert tagtyp(date(2006, 10, 2), "SH", sh) == ("ferien", "Herbstferien")
    assert tagtyp(date(2006, 10, 16), "SH", sh) == ("ferien", "Herbstferien")
    assert tagtyp(date(2006, 10, 10), "SH", sh) == ("schule", None)


def test_mecklenburg_vorpommern_einzeltage_der_herbstferien():
    """2024/25 und 2025/26 je zwei Einzeltage, die der Textleser den Nachbarzeilen gab."""
    k = ferienkalender("MV", Pfade().config)
    for tag in (date(2024, 10, 4), date(2024, 11, 1), date(2025, 10, 2), date(2025, 11, 3)):
        assert tagtyp(tag, "MV", k) == ("ferien", "Herbstferien"), tag


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


def test_sachsen_feiertage_und_ferien():
    assert date(2026, 11, 18) in feiertage("SN", 2026)  # Buß- und Bettag (Mittwoch vor dem 23.11.)
    assert date(2025, 11, 19) in feiertage("SN", 2025)
    assert date(2026, 10, 31) in feiertage("SN", 2026)  # Reformationstag
    assert date(2026, 11, 18) not in feiertage("BY", 2026)  # in Bayern nur unterrichtsfrei
    k = Ferienkalender.lade(Pfade().config / "schulferien_sachsen.csv")
    assert tagtyp(date(2026, 11, 18), "SN", k) == ("feiertag", "Buß- und Bettag")
    assert tagtyp(date(2026, 10, 20), "SN", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2026, 11, 12), "SN", k) == ("schule", None)
    # zweizeilige Zelle über der Zeile „Sachsen“, das Saarland daneben mit „--“ (keine Ferien)
    assert tagtyp(date(2027, 5, 7), "SN", k) == ("ferien", "Pfingstferien")
    assert tagtyp(date(2018, 5, 11), "SN", k) == ("ferien", "Pfingstferien")


def test_mecklenburg_vorpommern_feiertage_und_ferien():
    assert date(2026, 3, 8) in feiertage("MV", 2026)  # Frauentag seit 2023
    assert date(2022, 3, 8) not in feiertage("MV", 2022)
    assert date(2026, 10, 31) in feiertage("MV", 2026)
    k = Ferienkalender.lade(Pfade().config / "schulferien_mecklenburg-vorpommern.csv")
    assert tagtyp(date(2026, 10, 20), "MV", k) == ("ferien", "Herbstferien")
    assert tagtyp(date(2026, 11, 12), "MV", k) == ("schule", None)
    assert tagtyp(date(2021, 2, 19), "MV", k) == ("ferien", "Winterferien")  # zweizeilige Zelle


def test_abdeckung_meldet_kalender_die_bald_enden():
    """`zaehlkarte kalender`: Alle 16 Länder reichen bis 2027/28; ein Stichtag im Schuljahr
    2028/29 meldet jedes Land."""
    from zaehlkarte.kalender import abdeckung

    zeilen, fehlt = abdeckung(Pfade().config, date(2027, 2, 14))
    assert fehlt == [] and len(zeilen) == len(LAENDER)
    assert "Kalender HE: 1999/2000 – 2027/2028" in zeilen
    zeilen, fehlt = abdeckung(Pfade().config, date(2028, 9, 1))
    assert fehlt == list(LAENDER)
    assert zeilen[0].endswith(
        "endet vor 2028/2029: KMK-Kalender nachtragen (werkzeuge/kmk_ferien.py)")
