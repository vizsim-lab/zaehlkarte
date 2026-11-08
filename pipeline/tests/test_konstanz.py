from __future__ import annotations

from datetime import date, datetime

from zaehlkarte.adapters import konstanz_mobil as k
from zaehlkarte.config import Pfade

QUELLE = "Stadt Konstanz, Amt für Stadtplanung und Umwelt"


def _protokoll(zeilen: list[str]) -> str:
    """5-Minuten-Protokoll wie Gartenstraße/Schottenstraße (Datum; Uhrzeit mit Sekunden)."""
    kopf = "Datum; Uhrzeit;Fussgaenger-Ri-Fahrradbruecke;Fussgaenger-Ri-Schweiz; Total ;Quelle"
    return "﻿" + "\n".join([kopf, *zeilen]) + "\n"


def test_spalten_nach_verkehrsart():
    assert k.gruppe_der_spalte("Fahrradfahrer inkl. Lastenraeder (stadteinwaerts)") == "rad"
    assert k.gruppe_der_spalte("Auto stadtauswaerts") == "kfz"
    assert k.gruppe_der_spalte("Stadteinwaerts_PKW") == "kfz"
    assert k.gruppe_der_spalte("Fussgaenger-Ri-Fahrradbruecke") == "fuss"  # nicht Rad
    assert k.gruppe_der_spalte("Stadtauswaerts_Fußgaenger") == "fuss"
    for name in (" Total ", "Stadteinwaerts", "Insgesamt stadteinwaerts", " Andere stadteinwaerts",
                 "Datum-Uhrzeit", "Quelle"):
        assert k.gruppe_der_spalte(name) is None


def test_intervall_beginn_rundet_und_kennt_das_ende():
    t = datetime(2020, 11, 10, 7, 0, 4)
    assert k.intervall_beginn(t, 5, "ende") == datetime(2020, 11, 10, 6, 55)
    assert k.intervall_beginn(t, 5, "beginn") == datetime(2020, 11, 10, 7, 0)
    # kurz nach Mitternacht geschrieben: Intervall des Vortags
    assert k.intervall_beginn(datetime(2020, 11, 11, 0, 0, 3), 5, "ende") == datetime(
        2020, 11, 10, 23, 55)


def test_protokoll_mit_ende_doppelten_und_leeren_zeilen():
    zeilen = [f"10.11.2020;10:00:01;0;0;0;{QUELLE}"]  # erste Zeile nach dem Einschalten: leer
    zeilen += [f"10.11.2020;10:{m:02d}:04;2;1;3;{QUELLE}" for m in range(5, 60, 5)]
    zeilen += [f"10.11.2020;10:30:04;2;1;3;{QUELLE}"]  # doppelt, gleiche Werte
    zeilen += [f"10.11.2020;11:00:05;5;0;5;{QUELLE}"]  # Ende des Intervalls 10:55–11:00
    # Stunde 11: alle Intervalle da, aber ein Widerspruch -> nicht gezählt
    zeilen += [f"10.11.2020;11:{m:02d}:04;1;1;2;{QUELLE}" for m in range(5, 60, 5)]
    zeilen += [f"10.11.2020;12:00:03;1;1;2;{QUELLE}", f"10.11.2020;11:30:04;9;9;18;{QUELLE}"]
    zeilen += ["10.11.2020;12:05:00;;;;"]  # ohne Werte
    b = k.Bericht()
    tage, zuordnung = k.lese_standort(_protokoll(zeilen), None, 5, "ende", b)
    assert zuordnung == {"Fussgaenger-Ri-Fahrradbruecke": "fuss", "Fussgaenger-Ri-Schweiz": "fuss"}
    stunden = tage[date(2020, 11, 10)]
    assert sorted(stunden) == [10]  # 9 Uhr nur die leere Startzeile, 11 Uhr widersprüchlich
    assert stunden[10] == {"fuss": 11 * 3 + 5}
    assert (b.doppelt, b.widerspruch, b.leer) == (2, 1, 1)


def test_viertelstunden_ohne_verkehrsart_im_namen():
    text = "﻿Datum-Uhrzeit;Stadteinwaerts;Stadtauswaerts;Summe;Quelle\n" + "\n".join(
        f"21.08.2020 08:{m:02d};{10 + m};5;{15 + m};{QUELLE}" for m in (0, 15, 30, 45)
    ) + f"\n21.08.2020 09:00;1;1;2;{QUELLE}\n"
    tage, zuordnung = k.lese_standort(text, "rad", 15)
    assert zuordnung == {"Stadteinwaerts": "rad", "Stadtauswaerts": "rad"}
    assert tage == {date(2020, 8, 21): {8: {"rad": 10 + 25 + 40 + 55 + 4 * 5}}}


def test_lese(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / "konstanz"
    ordner.mkdir(parents=True)
    zeilen = [f"{t:%d.%m.%Y};{t:%H:%M}:04;1;0;1;{QUELLE}"
              for t in (datetime(2020, 10, d, h, m) for d in (2, 3) for h in range(24)
                        for m in range(0, 60, 5))]
    (ordner / "Ort_2.csv").write_text(_protokoll(zeilen), encoding="utf-8")
    q = {"code": "konstanz", "land": "BW", "standorte": [{
        "datei": "Ort_2.csv", "url": "https://portal/Ort_2.csv", "name": "Ort", "intervall": 5,
        "zeitstempel": "ende", "lon": 9.17, "lat": 47.66, "kategorien": "Fußgänger",
        "richtungen": "Richtung A und B", "hinweise": ["Lage: Brücke."],
        "hinweise_zeitraum": [{"von": date(2020, 10, 3), "text": "Ab dem 3. weniger."}],
    }]}
    b = k.Bericht()
    zs = list(k.lese(q, pfade, b))
    assert [z.datum for z in zs] == [date(2020, 10, 2), date(2020, 10, 3)]
    z2, z3 = zs
    assert z2.kennung == "Ort_20201002" and z2.stelle_roh == "Ort"  # ohne Upload-Zähler „_2“
    assert z2.typ == "Q" and z2.lage == "geokodiert" and (z2.lon, z2.lat) == (9.17, 47.66)
    # erste Zeile 00:00:04 gehört zum Vortag; 23:55 des 3. fehlt (Ende 00:00 des 4.)
    assert z2.fenster == [(0, 1440)] and z2.stunden["fuss"] == [12] * 24
    assert z3.fenster == [(0, 1380)]
    assert z2.rohdatei == "https://portal/Ort_2.csv" and z2.kategorien == "Fußgänger"
    assert "Richtung A und B" in z2.bemerkung
    assert z2.hinweise[0] == "Lage: Brücke." and "Ende des 5-Minuten-Intervalls" in z2.hinweise[1]
    assert "Ab dem 3. weniger." not in z2.hinweise and "Ab dem 3. weniger." in z3.hinweise
    assert set(z2.stunden) == {"fuss"}  # Rad und Kfz: nicht gezählt, nicht 0
    assert b.dateien == 1
