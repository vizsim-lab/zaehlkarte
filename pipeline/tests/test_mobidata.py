from __future__ import annotations

from datetime import datetime
from pathlib import Path

import openpyxl

from zaehlkarte.adapters import mobidata_bw
from zaehlkarte.config import Pfade


def uebersicht(pfad: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        [
            "ID",
            "NAME",
            "BREITENGRAD",
            "LAENGENGRAD",
            "KFZ_1",
            "RAD_1",
            "FUSSGAENGER_1",
            "SV_1",
            "DATUM_1",
            "KFZ_2",
            "RAD_2",
            "FUSSGAENGER_2",
            "SV_2",
            "DATUM_2",
        ]
    )
    ws.append(
        [
            1000,
            "B32_Ulmerstraße_88212_Ravensburg",
            "47.79",
            "9.62",
            384,
            96,
            192,
            24,
            datetime(2024, 7, 11),
            900,
            50,
            10,
            100,
            datetime(2023, 11, 16),
        ]
    )
    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pfad)


def zaehlung(pfad: Path) -> None:
    wb = openpyxl.Workbook()
    z = wb.active
    z.title = "Zusammenfassung"
    for zeile in (
        ["Messstelle", "Ulmerstraße"],
        ["Koordinaten", "47.7901, 9.6201"],
        ["Dauer", "11.07.2024 00:00:00 CEST - 12.07.2024 00:01:01 CEST"],
        ["Zeitintervall", "0:15:00"],
    ):
        z.append(zeile)
    r = wb.create_sheet("Rohdaten")
    r.append(
        ["Zeit", "Quelle", "Quellrichtung", "Ziel", "Zielrichtung", "U-Turn", "Klasse", "Volumen"]
    )
    for h in range(24):
        for m in (0, 15, 30, 45):
            t = f"11.07.2024 {h:02d}:{m:02d}:00 CEST"
            lkw = 1 if m == 0 else 0
            for klasse, v in (("PKW", 4), ("LKW ", lkw), ("Fahrrad", 1), ("Fußgänger", 2)):
                r.append([t, "A", "Norden", "B", "Süden", "Geradeaus", klasse, v])
    r.append(["12.07.2024 00:00:00 CEST", "A", "Norden", "B", "Süden", "Geradeaus", "PKW", 99])
    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pfad)


def test_excel_und_uebersicht(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / "mobidata" / "zaehldaten-test"
    uebersicht(ordner / "uebersicht.xlsx")
    zaehlung(ordner / "zip" / "Zähldaten" / "1000" / "11.07.2024" / "Ulmerstraße.xlsx")
    q = {
        "code": "test",
        "name": "Ravensburg",
        "land": "BW",
        "paket": "zaehldaten-test",
        "uebersicht": "uebersicht.xlsx",
        "portal": "https://portal/",
    }
    bericht = mobidata_bw.Bericht()
    zs = list(mobidata_bw.lese(q, pfade, bericht))
    assert [z.kennung for z in zs] == ["1000_20240711", "1000_20231116"]
    excel, nur = zs
    assert excel.stunden["kfz"] == [17] * 24  # 4 × 4 PKW + 1 LKW je Stunde
    assert excel.stunden["sv"] == [1] * 24
    assert excel.stunden["rad"] == [4] * 24 and excel.stunden["fuss"] == [8] * 24
    assert (excel.lon, excel.lat, excel.lage) == (9.6201, 47.7901, "quelle")
    assert excel.name == "B 32 / Ulmerstraße"
    # Übersicht: KFZ_n ist nur PKW -> Kfz = KFZ + SV; 24-h-Werte passen zur Excel
    assert nur.summen == {"kfz": 1000, "rad": 50, "fuss": 10, "sv": 100}
    assert nur.stunden == {}
    assert bericht.abweichung == []
