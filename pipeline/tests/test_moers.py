from __future__ import annotations

import json
from datetime import date

from zaehlkarte.adapters import moers_radar as m
from zaehlkarte.config import Pfade


def test_stunden_je_tag_nur_volle_stunden():
    text = "﻿" + "\n".join([
        "02.11.15 09:26:16;00;033;01;1",  # Beginn: 9–10 Uhr angefangen, zählt nicht
        "02.11.15 10:05:00;00;034;01;0",
        "02.11.15 10:59:59;00;050;09;1",  # 9 m: Schwerverkehr
        "02.11.15 23:30:00;00;030;02;0",
        "03.11.15 00:10:00;00;030;02;0",
        "03.11.15 02:00:00;00;030;12;0",
        "03.11.15 07:56:25;00;039;02;0",  # Ende: 7–8 Uhr angefangen, zählt nicht
        "kaputte Zeile",
    ])
    fz = m.lese_fahrzeuge(text)
    assert len(fz) == 7
    tage = m.stunden_je_tag(fz)
    assert sorted(tage) == [date(2015, 11, 2), date(2015, 11, 3)]
    assert min(tage[date(2015, 11, 2)]) == 10 and max(tage[date(2015, 11, 2)]) == 23
    assert tage[date(2015, 11, 2)][10] == (2, 1)
    assert tage[date(2015, 11, 2)][12] == (0, 0)  # Gerät lief, kein Fahrzeug: echte 0
    assert sorted(tage[date(2015, 11, 3)]) == list(range(7))
    assert tage[date(2015, 11, 3)][2] == (1, 1)


def test_jahr_korrektur_uhr_des_geraets():
    fz = m.lese_fahrzeuge("25.01.07 10:06:26;00;017;01;1\n27.01.07 07:31:17;00;039;02;0")
    assert m.jahr_korrektur(fz, 2017, "kirschenallee117t30250117.txt") == 10
    assert m.jahr_korrektur(fz, 2017, "kirschenallee117t30260117.txt") == 0  # anderer Tag
    assert m.jahr_korrektur(fz, 2007, "kirschenallee117t30250117.txt") == 0


def test_lese_mit_lage(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / "moers" / "verkehrszahlungen-2015"
    ordner.mkdir(parents=True)
    datei = "friemersheimer-strasse-12t3002112015.txt"
    (ordner / datei).write_text(
        "02.11.15 09:26:16;00;033;01;1\n02.11.15 10:30:00;00;033;01;1\n"
        "03.11.15 11:00:00;00;040;02;0\n",
        encoding="utf-8",
    )
    (ordner / "paket.json").write_text(json.dumps({
        "title": "Verkehrszählungen 2015 (Stadt Moers)",
        "resources": [{"name": "Verkehrszählung Friemersheimer Straße 12",
                       "url": f"https://portal/download/{datei}"}],
    }), encoding="utf-8")
    geo = tmp_path / "geokodierung"
    geo.mkdir()
    (geo / "moers.csv").write_text(
        "paket,datei,name,abfrage,lon,lat,genauigkeit,treffer\n"
        f"verkehrszahlungen-2015,{datei},x,x,6.63,51.44,hausnummer,x\n", encoding="utf-8")
    q = {"code": "moers", "land": "NW", "geokodierung": {"datei": "geokodierung/moers.csv"}}
    bericht = m.Bericht()
    zs = list(m.lese(q, pfade, bericht))
    assert [z.datum for z in zs] == [date(2015, 11, 2), date(2015, 11, 3)]
    z = zs[0]
    assert z.name == "Friemersheimer Straße 12" and z.typ == "Q" and z.lage == "geokodiert"
    assert (z.lon, z.lat) == (6.63, 51.44)
    assert z.h0 == 10 and z.stunden["kfz"][0] == 1 and z.stunden["sv"][0] == 0
    assert z.fenster == [(600, 1440)]  # 10–24 Uhr
    assert zs[1].fenster == [(0, 660)]  # 0–11 Uhr
    assert bericht.dateien == 1 and bericht.genauigkeit == {"hausnummer": 1}
