from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import xlwt

from zaehlkarte.adapters import muenster_xls as m
from zaehlkarte.config import Pfade
from zaehlkarte.koordinaten import affin, affin_anpassen, utm_zu_wgs84

KAT = ("Kfz", "Pkw", "Bus", "Lkw", "Lz", "Krad", "Rad")


def werte(*zahlen: int) -> dict[str, int]:
    return dict(zip(KAT, zahlen, strict=True))


def arm_oben(z: dict, o: int, s: dict, q: dict) -> None:
    """Q S nebeneinander, Kategorien links, Werte darunter."""
    z[(14, 9 + o)], z[(14, 10 + o)] = "Q", "S"
    for i, k in enumerate(KAT):
        z[(15 + i, 8 + o)], z[(15 + i, 9 + o)], z[(15 + i, 10 + o)] = k, q[k], s[k]


def arm_rechts(z: dict, o: int, s: dict, q: dict) -> None:
    """Q über S, Kategorien darüber, Werte nach links (Kfz zuerst)."""
    z[(23, 28 + o)], z[(24, 28 + o)] = "Q", "S"
    for i, k in enumerate(KAT):
        z[(22, 27 - i + o)], z[(23, 27 - i + o)], z[(24, 27 - i + o)] = k, q[k], s[k]


def arm_links(z: dict, o: int, s: dict, q: dict, marke: bool = True) -> None:
    """S über Q, Kategorien weiter oben, Werte nach rechts. `marke=False`: S/Q gelöscht."""
    if marke:
        z[(32, o)], z[(33, o)] = "S", "Q"
    for i, k in enumerate(KAT):
        z[(28, 1 + i + o)], z[(32, 1 + i + o)], z[(33, 1 + i + o)] = k, s[k], q[k]


def blatt(pfad: Path, tag: date, rechts_leer: bool = False) -> None:
    z: dict = {
        (1, 22): "Lage der Zählstelle: ",
        (1, 28): "Teststraße/ Beispielweg",
        (2, 22): "Koordinaten",
        (2, 25): "X",
        (2, 26): 3405000.0,
        (2, 29): "Y",
        (2, 30): 5757000.0,
        (3, 22): "Zähltag: ",
        (3, 25): "Do",
        (3, 26): float((tag - date(1899, 12, 30)).days),
        (4, 22): "Knoten-Nr.",
        (4, 26): 10000026.0,
        (5, 3): "Spitzenstunde: 07.00 - 08.00 Uhr",
        (5, 32): "Spitzenstunde: 16.00 - 17.00 Uhr",
        (46, 26): "A = ",
        (46, 27): "Teststraße (Nord)",
    }
    # 7–8 Uhr: Kfz-Zelle des rechten Arms falsch (200 statt 195)
    arm_oben(z, 0, werte(100, 90, 2, 5, 1, 2, 7), werte(210, 190, 4, 10, 2, 4, 12))
    arm_rechts(z, 0, werte(200, 180, 4, 8, 2, 1, 0), werte(380, 350, 8, 16, 4, 2, 1))
    arm_links(z, 0, werte(50, 48, 0, 1, 0, 1, 3), werte(100, 96, 0, 2, 0, 2, 5))
    # 16–17 Uhr: am linken Arm fehlen die Beschriftungen S/Q
    n = (lambda *_: werte(0, 0, 0, 0, 0, 0, 0)) if rechts_leer else werte
    arm_oben(z, 29, n(120, 110, 3, 4, 1, 2, 9), n(250, 230, 6, 8, 2, 4, 15))
    arm_rechts(z, 29, n(150, 140, 2, 5, 1, 2, 1), n(300, 280, 4, 10, 2, 4, 2))
    arm_links(z, 29, n(60, 57, 1, 1, 0, 1, 2), n(110, 104, 2, 2, 0, 2, 4), marke=False)
    wb = xlwt.Workbook()
    ws = wb.add_sheet("KNOTEN5")
    for (r, c), v in z.items():
        ws.write(r, c, v)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(pfad))


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = p.roh / "muenster"
    ordner.mkdir(parents=True)
    (ordner / "Zählstellen.csv").write_text(
        "﻿KNOTEN,RECHTSWERT,HOCHWERT,ZAEHLSTELLE\n10000026,412472,5752443,Teststraße\n",
        encoding="utf-8",
    )
    z = ordner / "zip" / "Verkehrszählung"
    blatt(z / "10000026_2304_2009_01.xls", date(2009, 4, 23))
    # Dateiname mit einem Datum, das es nicht gibt; nachmittags lauter Nullen
    blatt(z / "10000026_3104_2010_01.XLS", date(2010, 4, 22), rechts_leer=True)
    return p


QUELLE = {"code": "muenster", "land": "NW", "positionen": {"datei": "Zählstellen.csv"},
          "portal": "https://portal/"}


def test_knotensummen_aus_den_zufahrten(pfade):
    bericht = m.Bericht()
    zs = list(m.lese(QUELLE, pfade, bericht))
    assert [z.kennung for z in zs] == ["10000026_2304_2009_01", "10000026_3104_2010_01"]
    z = zs[0]
    assert z.datum == date(2009, 4, 23) and z.typ == "K" and z.richtungen == 3
    assert z.name == "Teststraße / Beispielweg"
    assert z.fenster == [(420, 480), (960, 1020)] and z.h0 == 7 and z.intervall == 60
    # Kfz = Summe der Fahrzeugarten (100 + 195 + 50); 16–17 Uhr samt ergänztem linken Arm
    assert z.stunden["kfz"] == [345] + [None] * 8 + [330]
    assert z.stunden["sv"] == [23] + [None] * 8 + [18]
    assert "rad" not in z.stunden  # Rad-Spalte der Kfz-Zählung geht nicht in die Karte
    text = " ".join(z.hinweise)
    assert "Quelle 350, Summe 345" in text
    assert "nicht in der Karte: 7–8 Uhr: 10; 16–17 Uhr: 12." in text
    assert z.lage == "quelle"
    assert z.lon == pytest.approx(7.72738118, abs=1e-7)
    assert z.lat == pytest.approx(51.91584059, abs=1e-7)
    assert z.zusatz["arme"] == {"A": "Teststraße (Nord)"}
    assert bericht.kfz_korrigiert == 2 and bericht.lage_csv == 2


def test_ungueltiges_datum_und_leere_stunde(pfade):
    bericht = m.Bericht()
    z = list(m.lese(QUELLE, pfade, bericht))[1]
    assert z.datum == date(2010, 4, 22)  # aus dem Zählblatt, der Dateiname nennt den 31.04.
    assert z.fenster == [(420, 480)] and z.stunden["kfz"] == [345]
    text = " ".join(z.hinweise)
    assert "ungültiges Datum" in text
    assert "16–17 Uhr (lauter Nullen – als nicht gezählt gewertet)" in text
    assert bericht.stunden_leer == 1


def test_zaehltag():
    mi, so, do = date(2011, 6, 15), date(2011, 6, 19), date(2011, 6, 16)
    assert m.zaehltag(mi, None, mi, 2) == (mi, None)
    # zweites Datum im Namen, vom Blatt bestätigt (Sonntagszählung)
    tag, hinweis = m.zaehltag(mi, so, so, 6)
    assert tag == so and "nimmt den 19.06.2011" in hinweis
    # Wochenende im Namen, Werktag im Blatt -> Blatt
    sa = date(2006, 5, 27)
    tag, hinweis = m.zaehltag(sa, None, date(2006, 4, 27), 3)
    assert tag == date(2006, 4, 27) and "ein Samstag" in hinweis
    # zwei Werktage -> Dateiname, mit Hinweis
    tag, hinweis = m.zaehltag(mi, None, do, 3)
    assert tag == mi and "16.06.2011" in hinweis
    # Wochenende in Name und Blatt, Blatt sagt Donnerstag -> unsicher
    tag, hinweis = m.zaehltag(so, None, so, 3)
    assert tag == so and "unsicher" in hinweis
    assert m.aus_dateiname("7530025_0805_2002_01_7530025_1010_2002") == (
        "7530025", date(2002, 5, 8), date(2002, 10, 10))
    assert m.aus_dateiname("1012_2015_01_Brandhoveweg-Querschnitt") == (None, None, None)


def test_koordinaten():
    lon, lat = utm_zu_wgs84(412472, 5752443)
    assert (lon, lat) == (pytest.approx(7.72738118, abs=1e-7), pytest.approx(51.91584059, abs=1e-7))
    # affine Anpassung: genau bekannte Abbildung, ein Tippfehler fällt heraus
    soll = [0.9996, -0.01, -2_990_000.0, 0.01, 0.9996, -2_000.0]
    quellpunkte = [(3400000.0 + 1000 * i, 5750000.0 + 700 * (i % 5)) for i in range(12)]
    paare = [(p, affin(soll, *p)) for p in quellpunkte]
    paare.append(((3405000.0, 5755000.0), (0.0, 0.0)))
    parameter, rms, n = affin_anpassen(paare)
    assert n == 12 and rms < 0.01
    punkt = (3401500.0, 5751000.0)
    assert affin(parameter, *punkt) == pytest.approx(affin(soll, *punkt))
