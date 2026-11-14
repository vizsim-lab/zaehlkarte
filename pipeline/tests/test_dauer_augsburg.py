"""Augsburg, Passanten Annastraße (dauer/augsburg_fuss.py) mit einer synthetischen Datei im Aufbau
der Quelle: `Standort;Jahr;Datum;Stunde;Passanten`, UTF-8 mit BOM, Ortszeit."""

from datetime import date

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import augsburg_fuss
from zaehlkarte.dauer.modell import tagessummen

WOCHENTAG = ["Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."]
Q = {"code": "augsburg_fuss", "land": "BY", "rueck": "einfach",
     "lage": {"Annastraße": {"kennung": "annastrasse", "lon": 10.8956, "lat": 48.36838,
                             "hinweise": ["Lage laut OpenStreetMap"]}}}


def _zeile(tag: date, stunde: int, wert: int) -> str:
    return (f"Annastraße;{tag.year};{WOCHENTAG[tag.weekday()]}, {tag:%d.%m.%Y};{stunde} Uhr;"
            f"{wert}")


def test_lese(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = tmp_path / "data" / "raw" / "augsburg_fuss"
    ordner.mkdir(parents=True)
    z = ["Standort;Jahr;Datum;Stunde;Passanten"]
    z += [_zeile(date(2025, 6, 3), h, 100 + h) for h in range(24)]  # voll
    z += [_zeile(date(2025, 6, 4), h, 50) for h in range(24) if h != 3]  # 3 Uhr fehlt
    z += [_zeile(date(2025, 3, 30), h, 10) for h in range(24) if h != 2]  # Sommerzeit: 23 h
    z += [_zeile(date(2025, 10, 26), h, 10) for h in range(24)]  # Rückstellung: 2 Uhr einmal
    z += [_zeile(date(2025, 10, 9), h, 20) for h in range(24)]
    z.append(_zeile(date(2025, 10, 9), 13, 20))  # doppelte Stunde: nicht gezählt
    z.append("Annastraße;2025;kein Datum;13 Uhr;5")
    (ordner / "passanten.csv").write_bytes(("﻿" + "\n".join(z) + "\n").encode("utf-8"))

    bericht = augsburg_fuss.Bericht()
    reihe = augsburg_fuss.lese(Q, pfade, bericht)
    assert [s.id for s in reihe.stellen] == ["augsburg_fuss:annastrasse"]
    assert reihe.stellen[0].name == "Annastraße" and reihe.stellen[0].hinweise
    assert tuple(reihe.werte) == ("fuss",)
    summen, _ = tagessummen(reihe, "fuss")
    i = reihe.index
    assert summen[0, i(date(2025, 6, 3))] == sum(100 + h for h in range(24))
    assert summen[0, i(date(2025, 6, 4))] < 0  # fehlende Stunde: nicht aufgefüllt
    assert summen[0, i(date(2025, 3, 30))] == 230  # 23 Stunden
    assert summen[0, i(date(2025, 10, 26))] < 0  # Rückstellung: 2 Uhr nur einmal
    assert summen[0, i(date(2025, 10, 9))] < 0  # doppelte Stunde
    assert bericht.unlesbar == 1 and bericht.standorte == ["Annastraße"]


def test_zeile():
    assert augsburg_fuss.zeile({"Datum": "Mi., 16.12.2020", "Stunde": "13 Uhr",
                                "Passanten": "521"}) == (date(2020, 12, 16), 13, 521)
    assert augsburg_fuss.zeile({"Datum": "Mi., 16.12.2020", "Stunde": "24 Uhr",
                                "Passanten": "1"}) is None
    assert augsburg_fuss.zeile({"Datum": "16.12.2020", "Stunde": "0 Uhr",
                                "Passanten": "x"}) is None
