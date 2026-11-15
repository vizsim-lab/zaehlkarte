"""Moers, Fußgänger Steinstraße (dauer/moers_fuss.py) mit synthetischen Monatsdateien in den vier
Spaltenfolgen der Quelle (deutsch mit Windows-1252, Export von hystreet.com mit UTF-8 und BOM,
verschobene Zeilen, `collection_type`), Zeit in Ortszeit mit Abstand zu UTC."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import zaehlkarte.abruf
import zaehlkarte.ckan
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import moers_fuss
from zaehlkarte.dauer.modell import LEER, tagessummen

BERLIN = ZoneInfo("Europe/Berlin")
Q = {"code": "moers_fuss", "land": "NW", "ckan": "https://odp.example", "paket": "steinstrasse",
     "dateien": r"stundlich.*\.csv$", "ab": date(2022, 5, 5),
     "lage": {"kennung": "steinstrasse", "name": "Steinstraße", "lon": 6.6297, "lat": 51.4514,
              "hinweise": ["Lage laut OpenStreetMap"]}}
DE = ("Lage;Zeitpunkt der Messung;Wochentag;Fußgänger insgesamt;Temperatur in ºc;Wetterlage;"
      "Fußgänger insgesamt Richtung Neumarkt;Fußgänger insgesamt Richtung Neuer Wall;Erwachsene;"
      "Kinder;Erwachsene Richtung Neumarkt;Erwachsene Richtung Neuer Wall;Kinder Richtung "
      "Neumarkt;Kinder Richtung Neuer Wall")
EN = ("location;time of measurement;weekday;pedestrians count;temperature in ºc;weather "
      "condition;incidents;towards Neumarkt pedestrians count;towards Neuer Wall pedestrians "
      "count;adult pedestrians count;child pedestrians count;adult towards Neumarkt pedestrians "
      "count;adult towards Neuer Wall pedestrians count;child towards Neumarkt pedestrians count;"
      "child towards Neuer Wall pedestrians count;zone 1 pedestrians count;zone 1 towards Neumarkt "
      "pedestrians count;zone 1 towards Neuer Wall pedestrians count;zone 2 pedestrians count;zone "
      "2 towards Neumarkt pedestrians count;zone 2 towards Neuer Wall pedestrians count")


def stunden(von: date, bis: date):
    """Alle Stunden von `von` 0 Uhr bis `bis` 23 Uhr Ortszeit -> („2022-10-30 02:00:00 +0200“,
    Wochentag)."""
    t = datetime(von.year, von.month, von.day, tzinfo=BERLIN).astimezone(UTC)
    ende = datetime(bis.year, bis.month, bis.day, tzinfo=BERLIN).astimezone(UTC) + timedelta(
        days=1, hours=1)
    while t < ende:
        lokal = t.astimezone(BERLIN)
        if lokal.date() <= bis:
            yield lokal.strftime("%Y-%m-%d %H:%M:%S %z"), lokal.strftime("%A"), lokal
        t += timedelta(hours=1)


def wert(lokal: datetime) -> int:
    return 10 + lokal.hour


def de_datei(von, bis, *, incidents=False, null_bis=None) -> str:
    """Deutscher Kopf; `incidents`: Zeilen mit leerer Spalte hinter der Wetterlage (Juli 2022)."""
    z = [DE]
    for t, wt, lokal in stunden(von, bis):
        w = 0 if null_bis and lokal.date() <= null_bis else wert(lokal)
        leer = ";" if incidents else ""
        z.append(f"Steinstraße, Moers;{t};{wt};{w};15;rain;{leer}7;8;9;1;4;5;0;1")
    return "\n".join(z) + "\n"


def en_datei(von, bis, *, art=None, verschoben=False) -> str:
    """Export von hystreet.com; `art`: {Zeit: collection_type} (Spalte nur dann);
    `verschoben`: Kopf mit Tabulator und leerer letzter Spalte, „Steinstraße\\t Moers“ (Februar
    2023)."""
    kopf = EN + (";collection_type" if art is not None else "") + (";" if verschoben else "")
    z = [kopf]
    for t, wt, lokal in stunden(von, bis):
        lage = "Steinstraße; Moers" if verschoben else "Steinstraße, Moers"
        zeile = f"{lage};{t};{wt};{wert(lokal)};3;cloudy;;7;8;9;1;4;5;0;1;2;3;4;5;6;7"
        if art is not None:
            zeile += ";" + art.get(t, "measured")
        z.append(zeile)
    text = "\n".join(z) + "\n"
    return text.replace(";", "\t") if verschoben else text


def tagessumme(tag: date) -> int:
    return sum(wert(lokal) for _, _, lokal in stunden(tag, tag))


def schreibe(pfade: Pfade, dateien: dict[str, tuple[str, bytes]]) -> None:
    ordner = pfade.roh / "moers_fuss"
    (ordner / "monate").mkdir(parents=True, exist_ok=True)
    for datei, (_, inhalt) in dateien.items():
        (ordner / "monate" / datei).write_bytes(inhalt)
    (ordner / "abruf.json").write_text(json.dumps({"dateien": {
        d: {"url": f"https://odp.example/{d}", "name": n, "stand": "2026-11-11"}
        for d, (n, _) in dateien.items()}}), encoding="utf-8")


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.roh.mkdir(parents=True, exist_ok=True)
    return p


def test_lese(pfade):
    juli = de_datei(date(2022, 7, 1), date(2022, 7, 2), incidents=True).splitlines()
    doppelt = next(z for z in juli if "2022-07-02 05:00:00" in z)
    juli.append(doppelt.replace(f";{10 + 5};", ";77;", 1))  # derselbe Zeitpunkt, anderer Wert
    juli.append("Steinstraße, Moers;kein Datum;Friday;5;15;rain;;1;1;1;0;1;0;0;0")
    maerz = en_datei(date(2024, 3, 30), date(2024, 3, 31),
                     art={"2024-03-30 05:00:00 +0100": "modelled"})
    schreibe(pfade, {
        "besucherzahlen-moers-mai-2022-stundlich.csv": (
            "Besucherzahlen Moers ab 5. Mai 2022 nach Stunden",
            de_datei(date(2022, 5, 3), date(2022, 5, 6), null_bis=date(2022, 5, 4))
            .replace(";", "\t").encode("cp1252")),
        "besucherzahlen-moers-juli-2022-stundlich.csv": (
            "Besuchszahlen Moers im Juli 2022 nach Stunden",
            ("\n".join(juli) + "\n").encode("cp1252")),
        "besucherzahlen-moers-oktober-2022-stundlich.csv": (
            "Besuchszahlen Moers im Oktober 2022 nach Stunden",
            de_datei(date(2022, 10, 30), date(2022, 10, 30)).encode("cp1252")),
        "besucherzahlen-moers-februar-2023-stundlich.csv": (
            "Besuchszahlen Moers im Februar 2023 nach Stunden",
            en_datei(date(2023, 2, 1), date(2023, 2, 1), verschoben=True).encode("cp1252")),
        "besucherzahlen-moers-marz-2024-stundlich.csv": (
            "Besucherzahlen Moers im März 2024 nach Stunden",
            ("﻿" + maerz).encode("utf-8")),
        # falscher Inhalt: der August 2023 unter dem Titel August 2024
        "besucherzahlen-moers-august-2024-stundlich.csv": (
            "Besucherzahlen Moers im August 2024 nach Stunden",
            ("﻿" + en_datei(date(2023, 8, 1), date(2023, 8, 1), art={})).encode("utf-8")),
        "besucherzahlen-moers-september-2024-stundlich.csv": (
            "Besucherzahlen Moers im September 2024 nach Stunden",
            b"Datum;Anzahl\n2024-09-01;5\n"),
    })
    b = moers_fuss.Bericht()
    r = moers_fuss.lese(Q, pfade, b)
    assert [s.id for s in r.stellen] == ["moers_fuss:steinstrasse"]
    assert r.stellen[0].name == "Steinstraße" and r.stellen[0].hinweise
    assert tuple(r.werte) == ("fuss",)
    assert r.von == date(2022, 5, 5)  # die Nullen vor dem Beginn zählen nicht
    summe, _ = tagessummen(r, "fuss")
    i = r.index
    assert summe[0, i(date(2022, 5, 5))] == tagessumme(date(2022, 5, 5))
    assert summe[0, i(date(2022, 7, 1))] == tagessumme(date(2022, 7, 1))  # Spalte mehr: Wert stimmt
    assert summe[0, i(date(2022, 7, 2))] == LEER  # 5 Uhr doppelt mit verschiedenen Werten
    assert summe[0, i(date(2022, 10, 30))] == tagessumme(date(2022, 10, 30))  # 25 Stunden
    assert r.doppelt[0, i(date(2022, 10, 30))]
    assert summe[0, i(date(2023, 2, 1))] == tagessumme(date(2023, 2, 1))  # verschobene Zeilen
    assert summe[0, i(date(2024, 3, 31))] == tagessumme(date(2024, 3, 31))  # 23 Stunden
    assert summe[0, i(date(2024, 3, 30))] == LEER  # eine Stunde geschätzt (modelled)
    assert r.werte["fuss"][0, i(date(2024, 3, 30)), 5] == LEER
    assert summe[0, i(date(2023, 8, 1))] == LEER  # nur in der Datei „August 2024“
    assert b.vor_beginn == 48 and b.geschaetzt == 1 and b.unlesbar == 1
    assert b.widerspruch == 1
    assert b.ausserhalb == {"besucherzahlen-moers-august-2024-stundlich.csv": 24}
    assert b.ohne_kopf == ["besucherzahlen-moers-september-2024-stundlich.csv"]
    assert b.bis == "2024-03-31"
    assert any("geschätzt" in z for z in b.zeilen())


def test_monat():
    assert moers_fuss.monat("Besucherzahlen Moers ab 5. Mai 2022 nach Stunden") == (2022, 5)
    assert moers_fuss.monat("Besuchszahlen Moers im März 2023 nach Stunden") == (2023, 3)
    assert moers_fuss.monat(None, "besucherzahlen-moers-marz-2024-stundlich.csv") == (2024, 3)
    assert moers_fuss.monat("", "besucherzahlen-moers-maerz-2023-stundlich.csv") == (2023, 3)
    assert moers_fuss.monat("Steinstraße", "daten.csv") is None


def test_lies_datei_kopf_und_text():
    assert moers_fuss.lies_datei("Datum;Anzahl\n2024-09-01;5\n") is None
    assert moers_fuss.text_von("Fußgänger".encode("cp1252")) == "Fußgänger"
    assert moers_fuss.text_von("﻿Fußgänger".encode()) == "Fußgänger"
    z = moers_fuss.lies_datei(en_datei(date(2025, 6, 2), date(2025, 6, 2), art={}))
    assert len(z) == 24 and z[0][1] == 10 and z[0][2] == "measured"
    assert z[0][0].utcoffset() == timedelta(hours=2)


def test_hole(pfade, monkeypatch):
    stand = {"juni": "2026-11-11T14:18:50"}

    def paket(basis, name, wege):
        assert (basis, name, wege) == ("https://odp.example", "steinstrasse", ("dcat",))
        return {"title": "Besuchszahlen Steinstraße – nach Stunden", "resources": [
            {"name": "Besucherzahlen Moers im Juni 2024 nach Stunden",
             "url": "https://odp.example/r/1/download/besucherzahlen-moers-juni-2024-stundlich.csv",
             "last_modified": stand["juni"]},
            {"name": "Besucherzahlen Moers im Juli 2024 nach Stunden",
             "url": "https://odp.example/r/2/download/besucherzahlen-moers-juli-2024-stundlich.csv",
             "last_modified": "2026-11-11T14:20:00"},
            {"name": "Besucherzahlen Moers im Juni 2024 nach Tagen",
             "url": "https://odp.example/r/3/download/besucherzahlen-moers-juni-2024-taglich.csv",
             "last_modified": "2026-11-11T14:21:00"},
        ]}

    geladen = []

    def lade(url, ziel, **k):
        geladen.append(url.rsplit("/", 1)[-1])
        ziel.write_text(en_datei(date(2024, 6, 3), date(2024, 6, 3)), encoding="utf-8")
        return ziel

    monkeypatch.setattr(zaehlkarte.ckan, "paket", paket)
    monkeypatch.setattr(zaehlkarte.abruf, "lade", lade)
    log = moers_fuss.hole(Q, pfade)
    assert sorted(geladen) == ["besucherzahlen-moers-juli-2024-stundlich.csv",
                               "besucherzahlen-moers-juni-2024-stundlich.csv"]
    assert "2 Monatsdateien, 2 neu" in log[0]
    moers_fuss.hole(Q, pfade)  # unverändert: nichts neu
    assert len(geladen) == 2
    stand["juni"] = "2026-12-01T08:00:00"  # die Stadt ersetzt den Juni
    moers_fuss.hole(Q, pfade)
    assert geladen[2:] == ["besucherzahlen-moers-juni-2024-stundlich.csv"]
    abruf = json.loads((pfade.roh / "moers_fuss" / "abruf.json").read_text(encoding="utf-8"))
    assert len(abruf["dateien"]) == 2 and abruf["paket"] == "steinstrasse"
