"""Opendatasoft-Stundenwerte (dauer/ods_stunden.py) mit synthetischen Exporten im Aufbau der
Quellen: Würzburg (Passantenzählung, mehrere Standorte; das Kennzeichen „unverified“ – ungeprüfte
Rohwerte – ändert nichts) und Neuss (RS5, ein Standort ohne Feld). Zeiten im Export in UTC."""

from datetime import date, datetime, timedelta

import pytest

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import ods_stunden
from zaehlkarte.dauer.modell import tagessummen

WUERZBURG = {
    "code": "wuerzburg_fuss", "land": "BY", "basis": "https://example.org", "datensatz": "p",
    "gruppe": "fuss", "zeit": "timestamp", "werte": ["pedestrians_count"],
    "stelle": "location_id",
    "stellen": {"135": {"kennung": "135", "name": "Schönbornstraße", "lon": 9.93, "lat": 49.79},
                "470": {"kennung": "470", "name": "Spiegelstraße", "lon": 9.934, "lat": 49.795}},
}
NEUSS = {
    "code": "neuss_rad", "land": "NW", "basis": "https://example.org", "datensatz": "rs5",
    "gruppe": "rad", "zeit": "date", "werte": ["counts"],
    "stellen": {"": {"kennung": "rs5", "name": "Radschnellweg RS5",
                     "abschnitt": "Hammer Landstraße", "lon": 6.7, "lat": 51.2}},
}


def _stunden(tag: date, versatz: int) -> list[datetime]:
    """Die Stunden eines Ortstags in UTC (versatz = Stunden vor UTC, ohne Zeitumstellung)."""
    beginn = datetime(tag.year, tag.month, tag.day) - timedelta(hours=versatz)
    return [beginn + timedelta(hours=h) for h in range(24)]


def _iso(t: datetime) -> str:
    return t.isoformat() + "+00:00"


def _schreibe(tmp_path, code: str, kopf: str, zeilen: list[str]) -> Pfade:
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = pfade.roh / code
    ordner.mkdir(parents=True)
    (ordner / ods_stunden.DATEI).write_bytes(
        ("﻿" + "\n".join([kopf, *zeilen]) + "\n").encode("utf-8"))
    return pfade


def test_wuerzburg_standorte(tmp_path):
    kopf = "timestamp;pedestrians_count;unverified;location_id;location_name"
    z = []
    voll = date(2025, 6, 3)  # Sommerzeit: Ortstag beginnt 22 Uhr UTC am Vortag
    z += [f"{_iso(t)};{100 + i};0;135;Schönbornstraße"
          for i, t in enumerate(_stunden(voll, 2))]
    z += [f"{_iso(t)};50;{1 if i < 20 else 0};470;Spiegelstraße"  # unverifiziert: Rohwert
          for i, t in enumerate(_stunden(voll, 2))]
    z += [f"{_iso(t)};7;0;999;Unbekannt" for t in _stunden(voll, 2)[:3]]
    doppelt = date(2025, 6, 4)
    z += [f"{_iso(t)};20;0;135;Schönbornstraße" for t in _stunden(doppelt, 2)]
    z.append(f"{_iso(_stunden(doppelt, 2)[5])};21;0;135;Schönbornstraße")
    z.append("2025-06-05T10:30:00+00:00;9;0;135;Schönbornstraße")  # nicht auf voller Stunde
    z.append(f"{_iso(_stunden(date(2025, 6, 5), 2)[0])};;0;135;Schönbornstraße")  # ohne Wert
    pfade = _schreibe(tmp_path, "wuerzburg_fuss", kopf, z)

    bericht = ods_stunden.Bericht()
    reihe = ods_stunden.lese(WUERZBURG, pfade, bericht)
    assert [s.id for s in reihe.stellen] == ["wuerzburg_fuss:135", "wuerzburg_fuss:470"]
    assert reihe.stellen[0].name == "Schönbornstraße" and reihe.stellen[0].land == "BY"
    assert tuple(reihe.werte) == ("fuss",)
    summen, _ = tagessummen(reihe, "fuss")
    i = reihe.index
    assert summen[0, i(voll)] == sum(100 + h for h in range(24))
    assert summen[1, i(voll)] == 24 * 50  # ungeprüfte Rohwerte zählen
    assert summen[0, i(doppelt)] < 0  # doppelte Stunde: nicht gezählt
    assert bericht.ohne_stelle == {"999": 3}
    assert bericht.doppelt == 1 and bericht.unlesbar == 1 and bericht.leer == 1
    assert bericht.zeitraum["135"][0] == "2025-06-02T22:00"
    assert any("135: 2025-06-02T22:00" in z for z in bericht.zeilen())


def test_neuss_ein_standort_und_sommerzeit(tmp_path):
    # 30.03.2025: Ortstag mit 23 Stunden (0 Uhr MEZ = 23 Uhr UTC am Vortag, ab 3 Uhr MESZ)
    stunden = [datetime(2025, 3, 29, 23)] + [datetime(2025, 3, 30, h) for h in range(22)]
    z = [f"{_iso(t)};10" for t in stunden]
    z += [f"{_iso(t)};{h}" for h, t in enumerate(_stunden(date(2025, 7, 1), 2))]
    pfade = _schreibe(tmp_path, "neuss_rad", "date;counts", z)

    bericht = ods_stunden.Bericht()
    reihe = ods_stunden.lese(NEUSS, pfade, bericht)
    assert [s.id for s in reihe.stellen] == ["neuss_rad:rs5"]
    assert reihe.stellen[0].abschnitt == "Hammer Landstraße"
    summen, _ = tagessummen(reihe, "rad")
    assert summen[0, reihe.index(date(2025, 3, 30))] == 230  # 23 Stunden
    assert summen[0, reihe.index(date(2025, 7, 1))] == sum(range(24))
    assert bericht.stellen == 1 and bericht.stunden == 47


def test_ohne_felder_nennt_spalten(tmp_path):
    pfade = _schreibe(tmp_path, "neuss_rad", "date;counts", ["2026-07-13T10:00:00+00:00;5"])
    with pytest.raises(ValueError, match=r"\['date', 'counts'\]"):
        ods_stunden.lese(NEUSS | {"zeit": None, "werte": []}, pfade, ods_stunden.Bericht())


def test_hole_waehlt_felder(tmp_path, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(ods_stunden.ods, "metadaten", lambda basis, ds: {"metas": {}})
    monkeypatch.setattr(ods_stunden.ods, "hole_export",
                        lambda basis, ds, select, ordner, name: aufrufe.append(select) or "ok")
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ods_stunden.hole(WUERZBURG, pfade)
    ods_stunden.hole(NEUSS | {"zeit": None, "werte": []}, pfade)
    assert aufrufe == ["timestamp,pedestrians_count,location_id", None]
    assert (pfade.roh / "wuerzburg_fuss" / "metadaten.json").exists()


def test_stunde():
    assert ods_stunden.stunde("2026-07-13T10:00:00+00:00") == datetime(2026, 7, 13, 10)
    assert ods_stunden.stunde("2026-07-13T12:00:00+02:00") == datetime(2026, 7, 13, 10)
    assert ods_stunden.stunde("2026-07-13T10:15:00+00:00") is None
    assert ods_stunden.stunde("kein Datum") is None


def test_tageswerte_vor_den_stunden(tmp_path):
    """Würzburg: Tagesdaten seit 2020, Stunden erst seit 2024 – die Tageswerte gelten nur vor der
    ersten gezählten Stunde einer Stelle; ein Tag mit fehlender Stunde bleibt nicht gezählt."""
    from zaehlkarte.dauer.modell import aus_tageswerten

    q = WUERZBURG | {"tage": {"datensatz": "pt", "zeit": "timestamp",
                              "werte": ["pedestrians_count"]}}
    kopf = "timestamp;pedestrians_count;unverified;location_id;location_name"
    erster = date(2024, 1, 2)  # erste Stunde (Winterzeit: 23 Uhr UTC am Vortag)
    z = [f"{_iso(t)};100;1;135;Schönbornstraße" for t in _stunden(erster, 1)]
    z += [f"{_iso(t)};100;1;135;Schönbornstraße" for t in _stunden(date(2024, 1, 3), 1)[1:]]
    pfade = _schreibe(tmp_path, "wuerzburg_fuss", kopf, z)
    tage = ["timestamp;pedestrians_count;location_id",
            "2023-12-30;25000;135", "2023-12-31;0;135",  # 0 bleibt 0
            "2024-01-01;24000;135", "2024-01-02;9999;135",  # ab der ersten Stunde: Stunden
            "2024-01-03;7777;135",  # fehlende Stunde wird nie gefüllt
            "2023-12-31;12000;470",  # Stelle nur mit Tageswerten
            "2023-12-29;5;135", "2023-12-29;6;135",  # derselbe Tag, verschieden: nicht gezählt
            "2023-12-28;;135", "kein Tag;1;135", "2023-12-28;1;999"]
    (pfade.roh / "wuerzburg_fuss" / ods_stunden.TAGE).write_text("\n".join(tage) + "\n",
                                                                  encoding="utf-8")
    bericht = ods_stunden.Bericht()
    reihe = ods_stunden.lese(q, pfade, bericht)
    assert reihe.von == date(2023, 12, 30)  # 29.12. widersprüchlich: leer, abgeschnitten
    assert set(reihe.tageswerte) == {"fuss"}
    assert [s.kennung for s in reihe.stellen] == ["135", "470"]
    summen, n = tagessummen(reihe, "fuss")
    tw = aus_tageswerten(reihe, "fuss")
    i = reihe.index
    assert summen[0, i(date(2023, 12, 30))] == 25000 and tw[0, i(date(2023, 12, 30))]
    assert summen[0, i(date(2023, 12, 31))] == 0
    assert summen[0, i(date(2024, 1, 1))] == 24000 and n[0, i(date(2024, 1, 1))] == 0
    assert summen[0, i(erster)] == 2400 and not tw[0, i(erster)]
    assert summen[0, i(date(2024, 1, 3))] == -1
    assert summen[1, i(date(2023, 12, 31))] == 12000 and tw[1].sum() == 1
    assert bericht.tage_gelesen == 11 and bericht.tage_unlesbar == 3
    assert bericht.tage_widerspruch == 1 and bericht.tageswerte == 3 + 1
    assert bericht.tage_zeitraum["135"] == ["2023-12-29", "2024-01-03"]
    assert any("Tageswerte der Quelle: 11 Zeilen" in z for z in bericht.zeilen())
    (v1, b1, t1), (v2, _, t2) = reihe.verfahren
    assert (v1, b1, v2) == (date(2023, 12, 30), date(2024, 1, 1), erster)
    assert "„pt“" in t1 and t2.startswith("Stundenwerte")


def test_hole_mit_tagesdaten(tmp_path, monkeypatch):
    aufrufe = []
    monkeypatch.setattr(ods_stunden.ods, "metadaten", lambda basis, ds: {"metas": {}})
    monkeypatch.setattr(ods_stunden.ods, "hole_export",
                        lambda basis, ds, select, ordner, name: aufrufe.append((ds, select, name))
                        or "ok")
    q = WUERZBURG | {"tage": {"datensatz": "pt", "zeit": "timestamp",
                              "werte": ["pedestrians_count"]}}
    assert ods_stunden.hole(q, Pfade(pipeline=tmp_path, repo=tmp_path)) == ["ok", "ok"]
    assert aufrufe == [("p", "timestamp,pedestrians_count,location_id", "export.csv"),
                       ("pt", "timestamp,pedestrians_count,location_id", "tage.csv")]


def test_tag():
    assert ods_stunden.tag("2020-01-01") == date(2020, 1, 1)
    assert ods_stunden.tag("2020-01-01T00:00:00+00:00") == date(2020, 1, 1)
    assert ods_stunden.tag("2020-01-01T12:00:00") is None
    assert ods_stunden.tag("Januar") is None
