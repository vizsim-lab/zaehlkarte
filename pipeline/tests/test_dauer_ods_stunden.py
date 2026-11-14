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
