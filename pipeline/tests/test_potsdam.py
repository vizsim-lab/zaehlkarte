from __future__ import annotations

import json
from datetime import date

from zaehlkarte import kennzahlen as kz
from zaehlkarte.adapters import potsdam_pdf as pp
from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung
from zaehlkarte.site import _lizenzen

TEXT = """Landeshauptstadt Potsdam 15.01.2020
FAHRZEUG-VERTEILUNG
Bemerkungen :
- Teilzählung - Zuf. OG wurde errechnet
1.234 - Wetter früh 3°C sonnig
Sph-Beginn: 7.30 Uhr und 16.00 Uhr
SUMME Zufahrten: [FSp] : 600 KFZ/h 8:00
(NSp): 630 KFZ/h 16:30
6h : 3600 KFZ
DATUM : WEST 286 KFZ/h 16:30
6h Werte 11.04.2019
von 7.00 - 10.00 Uhr u. 15.00 - 18.00 Uhr 230 Nedlitzer Str./Amundsenstr."""


def _w(text: str, x0: float, top: float) -> pp.Wort:
    return pp.Wort(text, x0, x0 + 6 * len(text), top)


def _tabelle(sv_fsp_summe: str = "6",
             kfz: tuple = ((100, 200, 300), (110, 210, 310), (600, 1200, 1800))) -> list:
    """Wörter einer Tabelle FAHRZEUG-VERTEILUNG wie im Plan: Kopf, je Verkehrsart drei Zeilen,
    links daneben Zahlen des Stromplans (gehören nicht zur Tabelle)."""
    ws = [_w("SUMME", 740, 60), _w("%", 790, 60), _w("NORD", 585, 63), _w("OST", 628, 63),
          _w("SÜD", 668, 63), _w("NORD", 195, 63)]
    zeilen = [
        ("RAD", [("FSp", (10, 20, 30), "60"), ("NSp", (5, 5, 5), "15"),
                 ("6h", (40, 50, 60), "150")]),
        ("SV", [("FSp", (1, 2, 3), sv_fsp_summe), ("NSp", (0, 0, 0), "0"),
                ("6h", (5, 5, 5), "15")]),
        ("KFZ", [(n, w, str(sum(w))) for n, w in zip(("FSp", "NSp", "6h"), kfz, strict=True)]),
    ]
    top = 85
    for modus, reihen in zeilen:
        ws.append(_w(modus, 503, top - 1))
        for name, zufahrten, summe in reihen:
            ws += [_w(name, 552, top), _w("1.073", 240, top)]  # Stromplan daneben
            ws += [_w(str(v), x, top) for v, x in zip(zufahrten, (595, 635, 675), strict=True)]
            ws += [_w(summe, 752, top), _w("5,0", 784, top + 1)]
            top += 14
    ws.append(_w("Bemerkungen", 503, top + 20))
    return ws


def test_tabelle_aus_der_lage_der_woerter():
    tab, richtungen = pp.tabelle(_tabelle())
    assert richtungen == ["NORD", "OST", "SÜD"]  # „NORD“ des Stromplans links nicht
    assert tab["kfz"]["FSp"] == {"summe": 600, "errechnet": False, "zufahrten": [100, 200, 300]}
    assert tab["rad"]["6h"]["summe"] == 150 and tab["sv"]["NSp"]["summe"] == 0
    assert set(tab) == {"rad", "sv", "kfz"}


def test_plan_spitzen_fenster_datum():
    p = pp.lese_plan(TEXT, _tabelle())
    assert p["datum"] == date(2019, 4, 11)  # nicht das Druckdatum oben
    assert p["fenster"] == [(420, 600), (900, 1080)]
    assert p["spitzen"] == [
        {"von": 450, "bis": 510, "name": "Frühspitze", "nach": "kfz",
         "werte": {"kfz": 600, "sv": 6, "rad": 60}},
        {"von": 960, "bis": 1020, "name": "Nachmittagsspitze", "nach": "kfz",
         "werte": {"kfz": 630, "sv": 0, "rad": 15}},
    ]
    assert p["fenstersummen"] == {"kfz": 3600, "sv": 15, "rad": 150}
    assert p["bemerkung"] == "Teilzählung - Zuf. OG wurde errechnet - Wetter früh 3°C sonnig"
    assert p["abweichend"] == [] and p["errechnet"] == []


def test_plan_formelfehler_und_nur_rad():
    p = pp.lese_plan(TEXT, _tabelle(sv_fsp_summe="0"))
    assert p["spitzen"][0]["werte"]["sv"] == 6  # Zufahrten 1+2+3, SUMME 0: der größere Wert
    assert p["abweichend"] == ["SV FSp: SUMME 0, Zufahrten 6"]
    p = pp.lese_plan(TEXT, _tabelle(kfz=((0, 0, 0),) * 3))  # Plan „nurRad“
    assert "kfz" in p["nicht_gezaehlt"]
    assert [s["nach"] for s in p["spitzen"]] == ["rad", "rad"]
    assert "kfz" not in p["spitzen"][0]["werte"]


def test_errechnete_werte_erkannt():
    ws = _tabelle()
    ws = [pp.Wort("3600,75", w.x0 - 18, w.x1, w.top) if w.text == "3600" else w for w in ws]
    p = pp.lese_plan(TEXT, ws)
    assert p["errechnet"] == ["KFZ 6h"]


def test_spitzenstunde_nur_fuer_die_bestimmende_gruppe():
    z = Zaehlung(quelle="potsdam", kennung="k", stelle_roh="s", name="n", typ="K", lon=None,
                 lat=None, lage=None, datum=None, fenster=[(420, 600), (900, 1080)], intervall=None,
                 spitzen=pp.lese_plan(TEXT, _tabelle())["spitzen"],
                 fenstersummen={"kfz": 3600, "rad": 150})
    assert kz.spitzenstunde(z, "kfz") == (16, 630)
    assert kz.spitzenstunde(z, "rad") is None  # Rad in der Kfz-Spitzenstunde: nicht die stärkste
    assert kz.summe(z, "kfz", 7, 19) is None and kz.tag24(z, "kfz") is None
    assert z.gruppen() == ["kfz", "sv", "rad"]


def test_lese_und_quellenangabe(tmp_path, monkeypatch):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / "potsdam"
    (ordner / "pdf" / "2300").mkdir(parents=True)
    (ordner / "pdf" / "2300" / "Nedlitzer_Str_Amundsenstr_2019.pdf").write_bytes(b"%PDF")
    (ordner / "export.json").write_text(json.dumps([{
        "name": "Nedlitzer Straße/Amundsenstraße", "kpnr": "2300",
        "geo_point_2d": {"lon": 13.05, "lat": 52.42},
        "zahlplan": "https://de.ftp.opendatasoft.com/potsdam/Verkehrszaehlungen/2300.zip",
    }]), encoding="utf-8")
    monkeypatch.setattr(pp, "lese_pdf", lambda pfad: pp.lese_plan(TEXT, _tabelle()))
    q = {"code": "potsdam", "land": "BB", "name": "Potsdam", "abruf": "potsdam/abruf.txt",
         "titel": "Verkehrszählungen © LHP/NB-16-OGD/{abruf} (verändert)", "lizenz": "NB-16-OGD"}
    b = pp.Bericht()
    (z,) = list(pp.lese(q, pfade, b))
    assert z.kennung == "2300_20190411" and z.stelle_roh == "2300" and z.typ == "K"
    assert (z.lon, z.lat, z.lage) == (13.05, 52.42, "quelle")
    assert z.name == "Nedlitzer Straße/Amundsenstraße" and z.richtungen == 3
    assert z.stunden == {} and z.fenstersummen == {"kfz": 3600, "sv": 15, "rad": 150}
    assert z.rohdatei.endswith("/2300.zip")
    assert any("Spitzenstunden" in h for h in z.hinweise)
    assert b.gelesen == 1
    assert _lizenzen(q, pfade)[0]["titel"] == "Verkehrszählungen © LHP/NB-16-OGD (verändert)"
    (ordner / "abruf.txt").write_text("2026-11-08")
    titel = _lizenzen(q, pfade)[0]["titel"]
    assert titel == "Verkehrszählungen © LHP/NB-16-OGD/08.11.2026 (verändert)"
