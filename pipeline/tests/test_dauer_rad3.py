"""Rad-Zählstellen, dritte Runde (Bonn, Düsseldorf): Adapter mit synthetischen Dateien."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import zaehlkarte.fetch
from zaehlkarte.config import Pfade, dauerquellen
from zaehlkarte.dauer import bonn_rad, duesseldorf_rad
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
        "5.16": {"lat": 50.715, "lon": 7.117},  # neu, noch ohne Werte: nicht in der Karte
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
    assert bonn_rad.zeit("1. Febr. 2021 00:00") == datetime(2021, 2, 1, 0, 0)
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


def test_bonn_name_aus_dem_kopf_wenn_sources_keinen_nennt(pfade):
    o = pfade.roh / "bonn_rad"
    o.mkdir(parents=True)
    z = ["Zeitraum;x", "", "Time;5.16 BN - Neuer Weg;5.01 BN - Kennedybrücke (Nordseite)"]
    z += [f"02.06.2025 {h:02d}:00;1;2" for h in range(24)]
    (o / "jahr_2025.csv").write_text("\n".join(z) + "\n", encoding="utf-8")
    r = bonn_rad.lese(BN_Q, pfade, bonn_rad.Bericht())
    assert [(s.kennung, s.name) for s in r.stellen] == [("5.16", "Neuer Weg"),
                                                         ("5.01", "Kennedybrücke")]


# -------------------------------------------------------------------------------- Düsseldorf
DD_Q = {**dauerquellen()["duesseldorf_rad"], "code": "duesseldorf_rad"}
DD_SOMMER, DD_RUECK = date(2020, 3, 29), date(2020, 10, 25)
DD_LIZENZ = "http://dcat-ap.de/def/licenses/dl-by-de/2.0"
DD_ZU = " - Wetterabhängige Jahresübersicht Dauerzählstelle"


def dd_2020(tage: list[date], wert: int, leer: set | None = None) -> str:
    """Format 2020: Zeit;Stunde;Anzahl;Wetter…; am Tag der Sommerzeit 3 Uhr zweimal, einmal leer."""
    z = ["Zeit;Stunde;Anzahl;Wetter;Temperatur"]
    for tag in tage:
        for h in range(24):
            if tag == DD_SOMMER and h == 2:
                z.append(f"{tag:%d.%m.%Y};03:00:00;;weather_condition_null;")
                continue
            a = "" if leer and (tag, h) in leer else str(wert)
            z.append(f"{tag:%d.%m.%Y};{h:02d}:00:00;{a};Sonnig;5")
    return "\n".join(z) + "\n"


def dd_2024(tage: list[date], summe_vorn: bool = False) -> str:
    """Format ab 2023: Zeit;IN;OUT;Symbol Wetter… (Fleher Deich 2024: Summe vorn)."""
    kopf = ("Zeit;" + ("Fleher Deich;" if summe_vorn else "")
            + "Fleher Deich Stadteinwaerts;Fleher Deich Stadtauswaerts;Symbol Wetter;Temperatur")
    z = [kopf]
    for tag in tage:
        for h in range(24):
            if tag == date(2024, 3, 31) and h == 2:
                continue
            vorn = "3;" if summe_vorn else ""
            z.append(f"{tag:%d-%m-%Y} {h:02d}:00:00;{vorn}1;2;Sonnig;5")
    return "\n".join(z) + "\n"


def test_duesseldorf_zeit_und_namen():
    z = duesseldorf_rad.zeit
    assert z("01.01.2020", "00:00:00") == datetime(2020, 1, 1, 0)
    assert z("1012021", "0:00") == datetime(2021, 1, 1, 0)
    assert z("15012021", "13:00") == datetime(2021, 1, 15, 13)
    assert z("01.01.2021 00:00", None) == datetime(2021, 1, 1, 0)
    assert z("26-03-2023 01:00:00", None) == datetime(2023, 3, 26, 1)
    assert z("01.01.2020", "00:15:00") is None and z("-07-07 08:", "00:00:00") is None

    def zu(name: str) -> str | None:
        return duesseldorf_rad.zuordnung(DD_Q, name + DD_ZU + " 2021")

    assert zu("Bilker Allee IN") == zu("Bilker Allee IN OUT") == "bilker_allee"
    assert zu("Fleher Deich O stromauf") == zu("Fleher Deich ost stromaufwärts IN OUT") == (
        "fleher_deich_ost")
    assert zu("Koblenzer Straße einwärts nach TL S") == "koblenzer_nach_tls"
    assert zu("Münchener_Ickeswarder Str") == zu("Münchner Ickerswarder Straße IN OUT") == (
        "muenchener_ickerswarder")
    assert zu("KÖ IN OUT") == "koe_steinstrasse" and zu("Koblenzer Straße") == "koblenzer_strasse"
    assert zu("Neue Stelle") is None


def test_duesseldorf_summenspalte_und_fuellzeile():
    lies = duesseldorf_rad.lies_datei
    spalten, stunden, weg, doppelt, summe = lies(dd_2024([date(2024, 6, 3)], summe_vorn=True))
    assert summe == "Fleher Deich"
    assert spalten == ["Fleher Deich Stadteinwaerts", "Fleher Deich Stadtauswaerts"]
    assert set(stunden.values()) == {3} and len(stunden) == 24 and not weg and not doppelt
    _, stunden, _, doppelt, _ = lies(dd_2020([DD_SOMMER], 2))
    assert stunden[datetime(2020, 3, 29, 3)] == 2 and len(stunden) == 23 and not doppelt
    t = ("Zeit;Stunde;Anzahl;Wetter\n01.06.2020;00:00:00;1;x\n01.06.2020;00:00:00;2;x\n"
         "01.06.2020;01:00:00;;x\n")
    _, stunden, _, doppelt, _ = lies(t)
    assert stunden == {datetime(2020, 6, 1, 0): LEER} and doppelt == 1


def test_duesseldorf_hole_und_lese(pfade, monkeypatch):
    def res(name, url, lizenz=DD_LIZENZ):
        return {"name": name + DD_ZU, "url": "https://dd.example/" + url, "license": lizenz}

    paket = "wetterabhangige-jahresubersicht-der-dauerzahlstellen-radverkehr-{}-d"
    pakete = [
        {"name": paket.format(2020), "resources": [
            res("Bilker Allee IN", "BA%20IN%202020.csv"),
            res("Bilker Allee OUT", "BA%20OUT%202020.csv"),
            res("Koblenzer Straße", "KS%202020.csv", "http://dcat-ap.de/def/licenses/other-closed"),
            res("Fleher Deich Rampe", "FDR%202020.csv"),
            res("Kölner Straße 186 Radweg IN OUT", "KO%202020.csv"),
            res("Neue Stelle", "NEU%202020.csv")]},
        {"name": paket.format(2024), "resources": [res("Fleher Deich IN OUT", "FD_2024.csv")]},
        {"name": paket.format(2019), "resources": [res("Bilker Allee IN", "BA%202019.csv")]},
    ]

    class Antwort:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"results": pakete}}

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **k: Antwort())
    tage = [date(2020, 6, 2), DD_SOMMER, DD_RUECK]
    inhalt = {
        "BA%20IN%202020.csv": dd_2020(tage, 2),
        "BA%20OUT%202020.csv": dd_2020(tage, 3, leer={(date(2020, 6, 2), 7)}),
        "FDR%202020.csv": dd_2020(tage, 9),
        "KO%202020.csv": dd_2020(tage, 1),
        "NEU%202020.csv": dd_2020(tage, 1),
        "FD_2024.csv": dd_2024([date(2024, 3, 31), date(2024, 6, 3)], summe_vorn=True),
    }
    geladen = []

    def lade(url: str, ziel: Path) -> Path:
        geladen.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(inhalt[url.removeprefix("https://dd.example/")].encode("utf-8"))
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    log = duesseldorf_rad.hole(DD_Q, pfade)
    assert len(geladen) == 6 and "2020 Koblenzer Straße" in log[0]
    duesseldorf_rad.hole(DD_Q, pfade)  # unverändert: nichts neu
    assert len(geladen) == 6
    assert (pfade.roh / "duesseldorf_rad" / "2020" / "BA IN 2020.csv").exists()
    b = duesseldorf_rad.Bericht()
    r = duesseldorf_rad.lese(DD_Q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["bilker_allee", "fleher_deich"]
    summe, _ = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2020, 6, 2))] == LEER  # eine Stunde OUT leer: nicht vollständig
    assert summe[0, i(DD_SOMMER)] == 23 * 5  # 23 Stunden, die leere Füllzeile zählt nicht
    assert summe[0, i(DD_RUECK)] == LEER  # Rückstellung: 2 Uhr nur einmal
    assert summe[1, i(date(2024, 6, 3))] == 24 * 3 and summe[1, i(date(2024, 3, 31))] == 23 * 3
    assert b.ohne == ["fleher_deich_rampe"] and b.ohne_lage == ["koelner_strasse_186"]
    assert len(b.nicht_zugeordnet) == 1 and "Neue Stelle" in b.nicht_zugeordnet[0]
    assert b.summenspalte == ["2024 fleher_deich: „Fleher Deich“"]
