from __future__ import annotations

import zipfile
from pathlib import Path

from zaehlkarte.adapters import berlin_zda, kategorien
from zaehlkarte.config import Pfade


def zda_text(
    knoten: str, datum: str, zeit: str, art: str, richtungen: list[list[str]], **kopf
) -> str:
    zeilen = [
        f"knoten={knoten}",
        "bez=Teststraße / Beispielweg (Mitte, 10115)",
        f"datum={datum}",
        f"zeit={zeit}",
        "intv=15",
        f"art={art}",
    ]
    zeilen += [f"{k}={v}" for k, v in kopf.items()]
    zeilen.append("data=")
    for i, werte in enumerate(richtungen, start=1):
        zeilen.append(f"; {i} -> {i + 1}")
        zeilen += werte
    return "\r\n".join(zeilen) + "\r\n"


def archiv(pfad: Path, dateien: dict[str, str]) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pfad, "w") as zf:
        for name, text in dateien.items():
            zf.writestr(name, text.encode("cp1252"))


def quelle() -> dict:
    return {
        "code": "berlin",
        "land": "BE",
        "geokodierung": {"datei": "geo.csv"},
        "rohdatei_liste": "liste.txt",
        "lieferungen": [
            {"code": "neu", "datei": "neu.zip", "rohdatei_url": "https://beispiel.de/{datei}"},
            {"code": "alt", "datei": "alt.zip"},
        ],
    }


def lies(tmp_path: Path, neu: dict, alt: dict | None = None) -> tuple[list, berlin_zda.Bericht]:
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    archiv(pfade.roh / "neu.zip", neu)
    archiv(pfade.roh / "alt.zip", alt or {})
    pfade.config.mkdir(parents=True, exist_ok=True)
    (pfade.roh / "geo.csv").write_text(
        "datei,geo_lon,geo_lat,geo_methode,geo_gebiet,geo_strassen\n"
        "K0000002_20190902.zda,13.3,52.4,kreuzung,berlin,A|B\n",
        encoding="utf-8",
    )
    bericht = berlin_zda.Bericht()
    return list(berlin_zda.lese(quelle(), pfade, bericht)), bericht


KFZ_RAD = "Pkw+Lfw,Lkw,Bus,Krad,Radf"


def test_stundenwerte_gruppen_und_gps(tmp_path):
    r1 = ["100 5 2 1 10"] * 8  # 7:00–9:00, 15 Minuten
    r2 = ["50 1 0 0 -1"] * 8  # Rad in dieser Richtung nicht gezählt
    text = zda_text(
        "K 0010921", "02.09.2019", "0700,0900", KFZ_RAD, [r1, r2], gps="52.54172, 13.42288"
    )
    (z,), _ = lies(tmp_path, {"K0010921_20190902.zda": text})
    assert z.stelle_roh == "K10921" and z.typ == "K"
    assert (z.lon, z.lat, z.lage) == (13.42288, 52.54172, "gps")
    assert z.h0 == 7
    assert z.stunden["kfz"] == [4 * (108 + 51)] * 2
    assert z.stunden["sv"] == [4 * (7 + 1)] * 2
    assert z.stunden["rad"] == [40, 40]  # nur Richtung 1
    assert any("Rad: 1 von 2 Richtungen nicht gezählt" in h for h in z.hinweise)
    assert z.rohdatei == "https://beispiel.de/K0010921_20190902.zda"
    assert z.name == "Teststraße / Beispielweg"


def test_angebrochene_stunde_ist_none_und_geokodierung(tmp_path):
    werte = ["10 0 0 0 1"] * 6  # 7:30–9:00 -> 7 Uhr nur halb gezählt
    text = zda_text("K2", "02.09.2019", "0730,0900", KFZ_RAD, [werte])
    (z,), _ = lies(tmp_path, {"K0000002_20190902.zda": text})
    assert (z.h0, z.stunden["kfz"]) == (8, [40])  # 7 Uhr fällt weg statt zu klein zu sein
    assert (z.lon, z.lat, z.lage) == (13.3, 52.4, "geokodiert")


def test_doppelte_zaehlungen(tmp_path):
    a = zda_text("K3", "03.09.2019", "0700,0800", KFZ_RAD, [["1 0 0 0 1"] * 4])
    b = zda_text("K3", "03.09.2019", "0000,2400", KFZ_RAD, [["1 0 0 0 1"] * 96])
    alt = zda_text("K3", "03.09.2019", "0700,0800", KFZ_RAD, [["9 0 0 0 9"] * 4])
    zs, bericht = lies(
        tmp_path,
        {"K0000003_20190903.zda": a, "K0000003_20190903_24h.zda": b},
        {"K-000003_20190903.ZDA": alt},
    )
    assert [z.kennung for z in zs] == ["K0000003_20190903_24h"]
    assert bericht.doppelt["12-Stunden-Fassung einer 24-Stunden-Zählung"] == 1
    assert bericht.doppelt["auch in der neueren Lieferung"] == 1


def test_kategorien():
    assert kategorien.spalten(["Pkw+Lfw", "Lkw", "Bus", "Krad", "Radf"]) == {
        "kfz": [0, 1, 2, 3],
        "sv": [1, 2],
        "rad": [4],
    }
    assert kategorien.spalten(["Kfz", "Lkw"]) == {"kfz": [0], "sv": [1]}
    assert kategorien.spalten(["Bus", "Taxi", "Radf"]) == {"rad": [2]}  # Busspur: kein Kfz
    assert kategorien.spalten(["Erw", "Jugend"]) == {"fuss": [0, 1], "kind": [1]}
    assert kategorien.spalten(["Fußg"]) == {"fuss": [0]}  # ohne Alter: kein Kriterium
    assert kategorien.spalten(["Erw", "Azubi"]) == {"fuss": [0, 1]}
    assert kategorien.spalten(["ÜKfz", "Lkw"]) == {"kfz": [0, 1], "sv": [1]}


def test_parse_gps_erkennt_vertauschte_reihenfolge():
    assert berlin_zda.parse_gps("13.42288, 52.54172") == (13.42288, 52.54172)
    assert berlin_zda.parse_gps("48.1, 11.5") == (None, None)  # nicht in Berlin
