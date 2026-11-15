"""Planegg, Fahrradzählstelle Amtmannstraße (dauer/planegg_rad.py) mit synthetischen
Jahresdateien im Aufbau der Quelle: je Monat ein Blatt, Kopf „Datum | Richtung Krailling |
Richtung Planegg | gesamt“, „gesamt“ als Formel, am Ende „Summe“ – dazu ein Februar-Blatt mit den
Daten des Januars (Vorlage nicht angepasst) und Schreibweisen der Quelle („Aprill“, „Krailing“)."""

import json
from datetime import date, datetime

import openpyxl

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import planegg_rad
from zaehlkarte.dauer.modell import aus_tageswerten, tagessummen

Q = {"code": "planegg_rad", "land": "BY", "monat_laut_blatt": ["Februar 2025"],
     "stelle": {"kennung": "amtmannstrasse", "strasse": "Amtmannstraße",
                "abschnitt": "an der Münchner Straße", "lon": 11.43, "lat": 48.10}}


def _blatt(mappe, name, monat_text, zeilen, kopf=("Datum", "Richtung Krailling",
                                                     "Richtung Planegg ", "gesamt")):
    ws = mappe.create_sheet(name)
    ws.append(["Anzahl Fahrradfahrer Amtmannstraße (Hin- und Rückrichtung)"])
    ws.append([])
    ws.append([monat_text])
    ws.append([])
    ws.append(list(kopf))
    for i, (tag, a, b) in enumerate(zeilen, start=6):
        ws.append([tag, a, b, f"=B{i}+C{i}"])
    ws.append(["Summe", 3249, 5566, "=B9+C9"])  # nicht fortgeschrieben wie 2025 – egal


def _pfade(tmp_path, jahre: dict[str, openpyxl.Workbook]) -> Pfade:
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / "planegg_rad"
    ordner.mkdir(parents=True)
    for jahr, mappe in jahre.items():
        mappe.save(ordner / f"{jahr}.xlsx")
    (ordner / planegg_rad.ABRUF).write_text(json.dumps(
        {"dateien": {j: f"https://example.org/{j}_Fahrrad.xlsx" for j in jahre}}))
    return pfade


def _mappe():
    m = openpyxl.Workbook()
    m.remove(m.active)
    return m


def test_lese(tmp_path):
    m24, m25 = _mappe(), _mappe()
    _blatt(m24, "Dezember 2024", "Monat Dezember 2024",
           [(datetime(2024, 12, 30), 40, 50), (datetime(2024, 12, 31), 0, 0)])
    _blatt(m25, "Januar 2025", "Monat Januar 2025",
           [(datetime(2025, 1, 1), 41, 129), (datetime(2025, 1, 2), 47, None)])
    # Vorlage des Januars nicht angepasst: Daten 1./2. Januar im Blatt „Februar 2025“
    _blatt(m25, "Februar 2025", "Monat Februar 2025",
           [(datetime(2025, 1, 1), 66, 199), (datetime(2025, 1, 2), 50, 154)])
    _blatt(m25, "Aprill 2025", "Monat Aprill 2025", [(datetime(2025, 4, 1), 10, 20)],
           kopf=("Datum", "Richtung Krailing", "Richtung Planegg", "gesamt"))
    # falsches Datum in einem Blatt, das die Quelldatei nicht nennt: nicht übernommen
    _blatt(m25, "Mai 2025", "Monat Mai 2025",
           [(datetime(2025, 5, 1), 5, 6), (datetime(2025, 6, 2), 7, 8)])
    pfade = _pfade(tmp_path, {"2024": m24, "2025": m25})
    bericht = planegg_rad.Bericht()
    reihe = planegg_rad.lese(Q, pfade, bericht)
    assert [s.id for s in reihe.stellen] == ["planegg_rad:amtmannstrasse"]
    st = reihe.stellen[0]
    assert (st.name, st.abschnitt, st.land) == ("Amtmannstraße", "an der Münchner Straße", "BY")
    summen, n = tagessummen(reihe, "rad")
    werte = {reihe.tag(i): int(v) for i, v in enumerate(summen[0]) if v >= 0}
    assert werte == {date(2024, 12, 30): 90, date(2024, 12, 31): 0, date(2025, 1, 1): 170,
                     date(2025, 2, 1): 265, date(2025, 2, 2): 204, date(2025, 4, 1): 30,
                     date(2025, 5, 1): 11}
    assert n.max() == 0 and aus_tageswerten(reihe, "rad").sum() == len(werte)
    assert (reihe.von, reihe.tag(reihe.tage - 1)) == (date(2024, 12, 30), date(2025, 5, 1))
    assert bericht.ohne_wert == 1 and bericht.nullen == 1 and bericht.tage == len(werte)
    assert dict(bericht.monat_korrigiert) == {"Februar 2025": 2}
    assert dict(bericht.falscher_monat) == {"Mai 2025": 1}
    assert bericht.jahre == ["2024", "2025"] and bericht.blaetter == 5
    assert any("Mai 2025 (1)" in z for z in bericht.zeilen())


def test_nur_jahre_der_seite(tmp_path):
    """`lese` nimmt nur die Jahre, die die Seite zuletzt verlinkte (abruf.json)."""
    m24, m25 = _mappe(), _mappe()
    _blatt(m24, "Mai 2024", "Monat Mai 2024", [(datetime(2024, 5, 1), 1, 2)])
    _blatt(m25, "Mai 2025", "Monat Mai 2025", [(datetime(2025, 5, 1), 3, 4)])
    pfade = _pfade(tmp_path, {"2024": m24, "2025": m25})
    (pfade.roh / "planegg_rad" / planegg_rad.ABRUF).write_text(json.dumps(
        {"dateien": {"2025": "https://example.org/2025_Fahrrad.xlsx"}}))
    reihe = planegg_rad.lese(Q, pfade, planegg_rad.Bericht())
    assert (reihe.von, reihe.tage) == (date(2025, 5, 1), 1)


def test_dateien_der_seite():
    seite = """<a href="/_Resources/Persistent/6/c/3/5/6c35/2021_Fahrrad%20Amtmannstra%C3%9Fe.xlsx">
    Zähldaten 2021</a> <a href='/_Resources/Persistent/d/4/2026_Fahrrad%20Amtmannstra%C3%9Fe.xlsx'>
    2026</a> <a href="/umwelt/energie/links.pdf">x</a>
    <a href="/_Resources/Persistent/1/2021_Fahrrad%20alt.xlsx">doppelt</a>"""
    d = planegg_rad.dateien_der_seite(seite, "https://www.planegg.de/umwelt/x",
                                      r"/(\d{4})_Fahrrad[^/]*\.xlsx$")
    assert d == {
        "2021": "https://www.planegg.de/_Resources/Persistent/6/c/3/5/6c35/2021_Fahrrad%20Amtmannstra%C3%9Fe.xlsx",
        "2026": "https://www.planegg.de/_Resources/Persistent/d/4/2026_Fahrrad%20Amtmannstra%C3%9Fe.xlsx"}


def test_monat_des_blatts():
    assert planegg_rad.monat_des_blatts("März  2025", []) == (2025, 3)
    assert planegg_rad.monat_des_blatts("Aprill 2026", []) == (2026, 4)
    assert planegg_rad.monat_des_blatts("Tabelle1", [("Monat: Juni  2021",)]) == (2021, 6)
    assert planegg_rad.monat_des_blatts("Tabelle1", [("Anzahl",)]) is None
