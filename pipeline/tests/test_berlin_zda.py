from __future__ import annotations

import zipfile
from pathlib import Path

from zaehlkarte.adapters import berlin_zda, kategorien
from zaehlkarte.config import Pfade


def zda_text(
    knoten: str, datum: str, zeit: str, art: str, richtungen: list[list[str]],
    marken: list[str] | None = None, **kopf
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
        zeilen.append(f"; {marken[i - 1]}" if marken else f"; {i} -> {i + 1}")
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
    assert kategorien.spalten(["Fußg"]) == {"fuss": [0]}  # ohne Altersgruppen
    assert kategorien.spalten(["Erw", "Azubi"]) == {"fuss": [0, 1]}
    assert kategorien.spalten(["ÜKfz", "Lkw"]) == {"kfz": [0, 1], "sv": [1]}


def test_parse_gps_erkennt_vertauschte_reihenfolge():
    assert berlin_zda.parse_gps("13.42288, 52.54172") == (13.42288, 52.54172)
    assert berlin_zda.parse_gps("48.1, 11.5") == (None, None)  # nicht in Berlin


def test_geokodier_liste_und_ergaenzung(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    text = zda_text(
        "K 0000004",
        "04.09.2019",
        "0700,0800",
        KFZ_RAD,
        [["1 0 0 0 1"] * 4],
        arm1="Musterstraße (N)",
        arm2="Beispielweg (O)",
    )
    archiv(pfade.roh / "neu.zip", {"K0000004_20190904.zda": text})
    archiv(pfade.roh / "alt.zip", {})
    (pfade.roh / "geo.csv").write_text(
        "datei,geo_lon,geo_lat,geo_methode,geo_gebiet,geo_strassen\n"
    )
    q = quelle()
    zeilen = berlin_zda.geokodier_liste(q, pfade)
    assert len(zeilen) == 1
    assert zeilen[0]["datei"] == "K0000004_20190904.zda"
    assert zeilen[0]["plz"] == "10115" and zeilen[0]["ortsteil"] == "Mitte"
    assert "Musterstraße" in zeilen[0]["arme"]
    # mit Ergänzung verortet, und nicht mehr in der Liste
    (tmp_path / "geokodierung").mkdir()
    (tmp_path / "geokodierung" / "erg.csv").write_text(
        "datei,geo_lon,geo_lat,geo_methode,geo_gebiet,geo_strassen\n"
        "K0000004_20190904.zda,13.39,52.53,kreuzung,plz,A|B\n"
    )
    q["geokodierung_ergaenzung"] = {"datei": "geokodierung/erg.csv"}
    (z,) = berlin_zda.lese(q, pfade)
    assert (z.lon, z.lat, z.lage) == (13.39, 52.53, "geokodiert")


def test_arme_und_stroeme(tmp_path):
    """Je Richtung ein Strom von Arm nach Arm; die Winkel der Arme im Uhrzeigersinn ab Nord."""
    nord_ost = ["10 1 0 0 2"] * 8  # Kfz 11 je Viertelstunde (Pkw, Lkw), Rad 2
    ost_nord = ["5 0 0 0 -1"] * 8  # Rad nicht gezählt
    nord_sued = ["3 0 0 0 0"] * 4 + ["-1 0 0 0 0"] + ["3 0 0 0 0"] * 3  # 8 Uhr: Kfz fehlt
    text = zda_text(
        "K 0000005", "05.09.2019", "0700,0900", KFZ_RAD, [nord_ost, ost_nord, nord_sued],
        marken=["1 -> 2", "2 -> 1", "1 -> 3"],
        arm1="Nordstraße (N),0,1000", arm2="Oststraße (O),2700,0100",
        arm3="Südstraße (S),1800,0010", arm4=",0,0000",
    )
    (z,), _ = lies(tmp_path, {"K0000005_20190905.zda": text})
    assert z.arme == [
        {"nr": 1, "name": "Nordstraße (N)", "winkel": 0.0},
        {"nr": 2, "name": "Oststraße (O)", "winkel": 90.0},  # 270° gegen den Uhrzeigersinn
        {"nr": 3, "name": "Südstraße (S)", "winkel": 180.0},
    ]
    assert [(s["von"], s["nach"]) for s in z.stroeme] == [(1, 2), (2, 1), (1, 3)]
    assert z.stroeme[0]["stunden"] == {"kfz": [44, 44], "sv": [4, 4], "rad": [8, 8]}
    assert z.stroeme[1]["stunden"] == {"kfz": [20, 20], "sv": [0, 0]}  # ohne Rad
    assert z.stroeme[2]["stunden"]["kfz"] == [12, None]
    # zusammen die Summe der Zählung, die fehlende Stunde bleibt offen
    assert z.stunden["kfz"] == [76, None]
    assert z.stunden["rad"] == [8, 8]


def test_arme_ohne_winkel_und_ohne_namen(tmp_path):
    text = zda_text(
        "Q 0000006", "06.09.2019", "0700,0800", KFZ_RAD, [["1 0 0 0 1"] * 4] * 2,
        marken=["1 -> 2", "2 -> 1"], arm1="Musterstraße (W)", arm2=",1350,0001",
    )
    (z,), _ = lies(tmp_path, {"Q0000006_20190906.zda": text})
    # ohne Zahlen kein Winkel; ohne Namen nur, weil ein Strom ihn nennt (135° gegen = 225°)
    assert z.arme == [{"nr": 1, "name": "Musterstraße (W)", "winkel": None},
                      {"nr": 2, "name": "", "winkel": 225.0}]
    assert berlin_zda.arme({"arm1": "Tempelhofer Ufer (W),650,1011"}) == [
        {"nr": 1, "name": "Tempelhofer Ufer (W)", "winkel": 295.0}]
