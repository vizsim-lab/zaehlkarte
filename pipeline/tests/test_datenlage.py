"""Datenlage je Kommune: der Stand der Dauerzählstellen je Kommune (`dauer:` in sources.yaml)
neben dem der Kurzzeitzählungen, und `zaehlkarte datenlage` – datenlage.json und
docs/DATENLAGE.md aus sources.yaml und der vorhandenen index.json, ohne neuen Bau."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from zaehlkarte import site
from zaehlkarte.config import Pfade

QUELLEN = {
    "quellen": {"teststadt": {"name": "Teststadt", "land": "BE", "status": "live"}},
    "anfrage_vorlage": {"betreff": "Verkehrszählungen", "text": "Stadt {kommune}, bitte.{zusatz}"},
    "recht": {"HH": "Hamburgisches Transparenzgesetz"},
    "datenlage": [
        {"kommune": "Teststadt", "quelle": "teststadt", "stand": "in_karte", "was": "Zählungen",
         "dauer": {"stand": "in_karte", "was": "Detektoren,\n  Stundenwerte",
                   "links": [["Archiv", "https://example.org/archiv"]]}},
        {"kommune": "Hafenstadt", "land": "HH", "lon": 10.0, "lat": 53.55, "stand": "kandidat",
         "was": "Knotenpunktzählungen", "anfrage": True, "anfrage_zusatz": "Auch 2014.",
         "links": [["Antwort", "https://example.org/antwort"]],
         "dauer": {"stand": "kandidat", "was": "Dauerzählstellen; offen nur Mittelwerte",
                   "links": [["Karte", "https://example.org/karte"]]}},
        {"kommune": "Dorf", "land": "HH", "lon": 9.9, "lat": 53.4, "stand": "abgelehnt",
         "was": "Anfrage abgelehnt"},
    ],
}


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.config.mkdir(parents=True)
    (p.config / "sources.yaml").write_text(yaml.safe_dump(QUELLEN, allow_unicode=True),
                                          encoding="utf-8")
    p.karte.mkdir(parents=True)
    # zwei Stellen in der Teststadt mit drei Zählungen (Abbild einer gebauten index.json)
    (p.karte / "index.json").write_text(json.dumps({
        "quellen": ["teststadt"],
        "stellen": {"felder": ["id", "quelle", "name", "typ", "lon", "lat", "lage", "chunk"],
                    "werte": [["teststadt:1", 0, "A", "K", 13.0, 52.0, "gps", 0],
                              ["teststadt:2", 0, "B", "K", 13.4, 52.6, "gps", 0]]},
        "zaehlungen": {"felder": ["stelle", "datum"],
                       "werte": [[0, "2024-05-01"], [1, "2024-05-02"], [1, "2025-05-02"]]},
    }), encoding="utf-8")
    return p


def test_dauer_stand_je_kommune(pfade):
    fc = site.datenlage([], pfade)  # ohne gebaute Stellen: die Kommune der Quelle fehlt
    assert [f["properties"]["kommune"] for f in fc["features"]] == ["Hafenstadt", "Dorf"]
    hafen, dorf = (f["properties"] for f in fc["features"])
    assert hafen["dauer"] == {"stand": "kandidat", "was": "Dauerzählstellen; offen nur Mittelwerte",
                              "situation": None,
                              "links": [{"titel": "Karte", "url": "https://example.org/karte"}]}
    assert hafen["anfrage"]["text"] == "Stadt Hafenstadt, bitte.\nAuch 2014."
    assert dorf["dauer"] is None  # kein Eintrag: bei den Dauerzählstellen nicht in der Ebene


def test_anfrage_an_gemeinde():
    """Die Vorlage nennt die angefragte Stelle: „Stadt X“, wo nichts anderes steht, sonst
    `anfrage_an` des Eintrags (Gemeinden, Kreise) – der übrige Text ist für alle gleich."""
    vorlage = {"betreff": "Zählungen", "text": "Zählungen, die die {stelle} hat.{zusatz}"}
    assert site.anfrage(vorlage, "Mühltal", None)["text"] == "Zählungen, die die Stadt Mühltal hat."
    assert (site.anfrage(vorlage, "Mühltal", "Seit 2022.", "Gemeinde Mühltal")["text"]
            == "Zählungen, die die Gemeinde Mühltal hat.\nSeit 2022.")


def test_dauer_stand_unbekannt(pfade):
    with pytest.raises(ValueError, match="dauer.stand 'geliefert' unbekannt"):
        site._dauer({"kommune": "X", "dauer": {"stand": "geliefert"}})


def test_zaehlkarte_datenlage_aus_index(pfade):
    ziele = site.schreibe_datenlage(pfade, date(2026, 11, 13))
    assert ziele == [pfade.karte / "datenlage.json", pfade.repo / "docs" / "DATENLAGE.md"]
    fc = json.loads(ziele[0].read_text(encoding="utf-8"))
    test = fc["features"][0]
    # Lage (Median der Stellen) und Zahl der Zählungen aus index.json
    assert test["geometry"]["coordinates"] == [13.4, 52.6]
    assert test["properties"]["zaehlungen"] == 3
    assert test["properties"]["dauer"]["was"] == "Detektoren, Stundenwerte"
    md = ziele[1].read_text(encoding="utf-8")
    assert "am 2026-11-13" in md
    assert ("| Hafenstadt | HH | erhoben – Anfrage aussichtsreich | vorhanden, Werte nicht offen |"
            in md)
    assert "| Dorf | HH | Anfrage gescheitert |  |" in md
    assert "## Teststadt – Dauerzählstellen in der Karte" in md
    assert "**Dauerzählstellen (vorhanden, Werte nicht offen):** Dauerzählstellen; offen nur" in md
    # Belege: die der Kurzzeitzählungen und die der Dauerzählstellen
    assert "[Antwort](https://example.org/antwort) · [Karte](https://example.org/karte)" in md
