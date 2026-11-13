"""Rad-Zählstellen, dritte Runde (Bonn, Düsseldorf): Adapter mit synthetischen Dateien."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import zaehlkarte.fetch
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bonn_rad
from zaehlkarte.dauer.modell import LEER, tagessummen


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.roh.mkdir(parents=True, exist_ok=True)
    return p


# -------------------------------------------------------------------------------- Bonn
BN_Q = {
    "code": "bonn_rad", "land": "NW", "katalog": "https://bn.example/data.json", "ab_jahr": 2020,
    "ohne_jahre": [2022], "rueck": "einfach",
    "stellen": {
        "5.01": {"name": "Kennedybrücke", "abschnitt": "Nordseite", "lat": 50.737, "lon": 7.106},
        "5.02": {"name": "Kennedybrücke", "abschnitt": "Südseite", "lat": 50.736, "lon": 7.107},
    },
}
SOMMER, RUECK = date(2025, 3, 30), date(2025, 10, 26)


def bonn_datei(tage: list[date], wort: bool = False, leer: set | None = None,
               fuell: bool = False) -> str:
    """Jahresdatei wie die der Stadt: zwei Kopfzeilen, Time-Kopf mit Summenspalten, Summe am Ende.
    Spalte 5.01 = Stunde + 1, 5.02 = 2, Summe der Brücke daneben, 5.99 ohne Lage."""
    monate = ["Jan.", "Feb.", "März", "Apr.", "Mai", "Juni", "Juli", "Aug.", "Sept.", "Okt.",
              "Nov.", "Dez."]
    z = ["Zeitraum;1. Januar 2025 -> 31. Dezember 2025;;;;", ";;;;;",
         "Time;5.01 BN - Kennedybrücke (Nordseite);5.02 BN - Kennedybrücke (Südseite) Barometer;"
         "5.99 BN - Neue Stelle;Kennedybrücke; Summe"]
    for tag in tage:
        for h in range(24):
            if tag == SOMMER and h == 2 and not fuell:
                continue
            if tag == RUECK and h == 2:
                pass  # 2 Uhr nur einmal
            t = (f"{tag.day}. {monate[tag.month - 1]} {tag.year} {h:02d}:00" if wort
                 else f"{tag:%d.%m.%Y} {h:02d}:00")
            a = "" if leer and (tag, h) in leer else str(h + 1)
            z.append(f"{t};{a};2;5;{(h + 1 + 2) if a else ''};{h + 8}")
    z.append("Summe;1;2;3;4;5")
    return "\n".join(z) + "\n"


def test_bonn_zeit_beide_formate():
    assert bonn_rad.zeit("01.01.2025 00:00") == datetime(2025, 1, 1, 0, 0)
    assert bonn_rad.zeit("1. Jan. 2024 13:00") == datetime(2024, 1, 1, 13, 0)
    assert bonn_rad.zeit("31. März 2024 01:00") == datetime(2024, 3, 31, 1, 0)
    assert bonn_rad.zeit("3. Sept. 2021 10:00") == datetime(2021, 9, 3, 10, 0)
    assert bonn_rad.zeit("5. Mai 2021 07:00") == datetime(2021, 5, 5, 7, 0)
    assert bonn_rad.zeit("Summe") is None and bonn_rad.zeit("1. Foo 2024 00:00") is None


def test_bonn_hole_katalog_und_lese(pfade, monkeypatch):
    katalog = {"dataset": [
        {"title": "Fahrradmessstellen Ergebnisse Radzählungen 2025",
         "license": "http://www.opendefinition.org/licenses/cc-zero",
         "distribution": [{"title": "Fahrradmesstellen Ergebnisse Radzählungen Stundenauswertung",
                           "downloadURL": "https://bn.example/2025.csv"}]},
        {"title": "Fahrradmessstellen Ergebnisse Radzählungen 2024",
         "license": "http://www.opendefinition.org/licenses/cc-zero",
         "distribution": [
             {"title": "… 15 Minutenauswertung 2024", "downloadURL": "https://bn.example/2024q.csv"},
             {"title": "… Stundenauswertung", "downloadURL": "https://bn.example/2024.csv"}]},
        {"title": "Fahrradmessstellen Ergebnisse Radzählungen 2023",
         "license": "http://dcat-ap.de/def/licenses/other-closed",
         "distribution": [{"title": "Stundenauswertung", "downloadURL": "https://bn.example/2023.csv"}]},
        {"title": "Fahrradmessstellen Ergebnisse Radzählungen 2022",
         "license": "http://www.opendefinition.org/licenses/cc-zero",
         "distribution": [{"title": "2022", "downloadURL": "https://bn.example/2022.csv"}]},
        {"title": "Fahrradmessstellen Ergebnisse Radzählungen 2019",
         "license": "http://www.opendefinition.org/licenses/cc-zero",
         "distribution": [{"title": "2019", "downloadURL": "https://bn.example/2019.csv"}]},
        {"title": "Fahrradmessstellen Ergebnisse Radzählungen Vortag",
         "license": "http://www.opendefinition.org/licenses/cc-zero",
         "distribution": [{"title": "Vortag", "downloadURL": "https://stadtplan.example/csv"}]},
    ]}

    class Antwort:
        def raise_for_status(self):
            pass

        def json(self):
            return katalog

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **k: Antwort())
    inhalt = {
        "https://bn.example/2025.csv": bonn_datei([date(2025, 3, 29), SOMMER, RUECK],
                                                  leer={(date(2025, 3, 29), 9)}),
        "https://bn.example/2024.csv": bonn_datei([date(2024, 6, 3)], wort=True),
    }
    geladen = []

    def lade(url: str, ziel: Path) -> Path:
        geladen.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(inhalt[url].encode("cp1252"))
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    log = bonn_rad.hole(BN_Q, pfade)
    assert sorted(geladen) == ["https://bn.example/2024.csv", "https://bn.example/2025.csv"]
    assert "2023" in log[0] and "2022" not in log[0] and "2019" not in log[0]
    b = bonn_rad.Bericht()
    r = bonn_rad.lese(BN_Q, pfade, b)
    assert [(s.name, s.abschnitt) for s in r.stellen] == [("Kennedybrücke", "Nordseite"),
                                                         ("Kennedybrücke", "Südseite")]
    summe, n = tagessummen(r, "rad")
    i = r.index
    voll = sum(h + 1 for h in range(24))
    assert summe[0, i(date(2024, 6, 3))] == voll and summe[1, i(date(2024, 6, 3))] == 48
    assert summe[0, i(date(2025, 3, 29))] == LEER  # eine leere Zelle: nicht vollständig
    assert summe[1, i(date(2025, 3, 29))] == 48
    assert summe[0, i(SOMMER)] == voll - 3 and summe[1, i(SOMMER)] == 46  # 23 Stunden
    assert summe[0, i(RUECK)] == LEER  # Rückstellung: 2 Uhr nur einmal
    assert b.ohne_lage == {"5.99 Neue Stelle"} and b.leer == 1 and not any(b.unlesbar.values())
    assert b.dateien == ["2024", "2025"]


def test_bonn_fuellstunde_am_tag_der_sommerzeit(pfade):
    o = pfade.roh / "bonn_rad"
    o.mkdir(parents=True)
    (o / "jahr_2025.csv").write_text(bonn_datei([SOMMER], fuell=True), encoding="utf-8")
    b = bonn_rad.Bericht()
    r = bonn_rad.lese(BN_Q, pfade, b)
    summe, _ = tagessummen(r, "rad")
    assert summe[0, r.index(SOMMER)] == sum(h + 1 for h in range(24)) - 3  # 2 Uhr verworfen
    assert b.sommerzeit == 2


def test_bonn_viertelstunden_datei_abgelehnt(pfade):
    o = pfade.roh / "bonn_rad"
    o.mkdir(parents=True)
    t0 = datetime(2025, 6, 2)
    zeilen = [f"{(t0 + timedelta(minutes=15 * k)):%d.%m.%Y %H:%M};1;1" for k in range(8)]
    (o / "jahr_2025.csv").write_text(
        "Zeitraum;x\n\nTime;5.01 BN - A;5.02 BN - B\n" + "\n".join(zeilen) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="keine Stundenauswertung"):
        bonn_rad.lese(BN_Q, pfade, bonn_rad.Bericht())
