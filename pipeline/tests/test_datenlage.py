"""Datenlage je Kommune (`zaehlkarte.datenlage`): je Familie ein Block mit Stand, Quellen, Text
und Belegen aus config/kommunen/<LAND>.yaml; datenlage.json (Version 2) und docs/DATENLAGE.md aus
der Konfiguration und der vorhandenen index.json, ohne neuen Bau."""

from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from zaehlkarte import datenlage as dl
from zaehlkarte.config import Pfade

KONFIG = {
    "quellen": {"teststadt": {"name": "Teststadt", "land": "BE", "status": "live"}},
    "anfrage_vorlage": {"betreff": "Verkehrszählungen", "text": "Stadt {kommune}, bitte.{zusatz}"},
    "recht": {"HH": "Hamburgisches Transparenzgesetz"},
    "datenlage": [
        {"ags": "11000000", "name": "Teststadt", "lage": [13.4, 52.5],
         "kurzzeit": {"stand": "in_karte", "quellen": ["teststadt"], "was": "Zählungen"},
         "dauer": {"stand": "in_karte", "quellen": ["test_rad"],
                   "was": "Detektoren,\n  Stundenwerte",
                   "links": [["Archiv", "https://example.org/archiv"]]}},
        {"ags": "02000000", "name": "Hafenstadt", "lage": [10.0, 53.55],
         "kontakt": {"fds_suche": "Hafenstadt"},
         "kurzzeit": {"stand": "kandidat", "was": "Knotenpunktzählungen",
                      "anfrage": {"zusatz": "Auch 2014."},
                      "links": [["Antwort", "https://example.org/antwort"]]},
         "dauer": {"stand": "kandidat", "was": "Dauerzählstellen; offen nur Mittelwerte",
                   "links": [["Karte", "https://example.org/karte"]]}},
        {"ags": "02000001", "name": "Dorf", "lage": [9.9, 53.4],
         "kurzzeit": {"stand": "abgelehnt", "was": "Anfrage abgelehnt",
                      "anfrage": {"an": "Gemeinde Dorf"}}},
        # nur Dauerzählstellen bekannt: kein Block der Kurzzeitzählungen
        {"ags": "02000002", "name": "Radstadt", "lage": [10.1, 53.6],
         "dauer": {"stand": "ohne_lizenz", "was": "Rad-Dauerzählstellen; Werte ohne Lizenz",
                   "links": [["Portal", "https://example.org/portal"]]}},
    ],
}


@pytest.fixture
def pfade(tmp_path: Path, schreibe_konfiguration) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    schreibe_konfiguration(p.config, KONFIG)
    p.karte.mkdir(parents=True)
    # zwei Stellen der Teststadt mit drei Zählungen (Abbild einer gebauten index.json)
    (p.karte / "index.json").write_text(json.dumps({
        "quellen": ["teststadt"],
        "stellen": {"felder": ["id", "quelle", "name", "typ", "lon", "lat", "lage", "chunk"],
                    "werte": [["teststadt:1", 0, "A", "K", 13.0, 52.0, "gps", 0],
                              ["teststadt:2", 0, "B", "K", 13.4, 52.6, "gps", 0]]},
        "zaehlungen": {"felder": ["stelle", "datum"],
                       "werte": [[0, "2024-05-01"], [1, "2024-05-02"], [1, "2025-05-02"]]},
    }), encoding="utf-8")
    return p


def test_bloecke_je_familie(pfade):
    fc = dl.datenlage(pfade, Counter({"teststadt": 3}))
    assert fc["version"] == dl.VERSION and fc["stand"]["dauer"]["kandidat"] == (
        "vorhanden, Werte nicht offen")
    test, hafen, dorf, radstadt = (f["properties"] for f in fc["features"])
    assert [f["geometry"]["coordinates"] for f in fc["features"]][0] == [13.4, 52.5]
    assert (test["ags"], test["name"], test["land"]) == ("11000000", "Teststadt", "BE")
    assert test["kurzzeit"]["zaehlungen"] == 3 and test["kurzzeit"]["quellen"] == ["teststadt"]
    assert test["dauer"]["was"] == "Detektoren, Stundenwerte"
    assert test["dauer"]["quellen"] == ["test_rad"]
    assert (test["stand_k"], test["stand_d"]) == ("in_karte", "in_karte")
    # nur Dauerzählstellen: kein Block, kein flacher Stand der Kurzzeitzählungen
    assert radstadt["kurzzeit"] is None and "stand_k" not in radstadt
    assert radstadt["stand_d"] == "ohne_lizenz"
    assert dorf["dauer"] is None and "stand_d" not in dorf
    assert hafen["recht"] == "Hamburgisches Transparenzgesetz"
    assert hafen["kontakt"]["fds"].endswith("?q=Hafenstadt") and hafen["kontakt"]["fds_suche"]
    assert hafen["dauer"] == {"stand": "kandidat", "quellen": [],
                              "was": "Dauerzählstellen; offen nur Mittelwerte", "situation": None,
                              "links": [{"titel": "Karte", "url": "https://example.org/karte"}]}
    assert hafen["kurzzeit"]["anfrage"]["text"] == "Stadt Hafenstadt, bitte.\nAuch 2014."
    assert hafen["kurzzeit"]["zaehlungen"] is None
    assert dorf["kurzzeit"]["anfrage"]["text"] == "Stadt Dorf, bitte."
    assert radstadt["kontakt"] is None


def test_anfrage_an_gemeinde():
    """Die Vorlage nennt die angefragte Stelle: „Stadt X“, wo nichts anderes steht, sonst `an`
    (Gemeinden, Kreise) – der übrige Text ist für alle gleich."""
    vorlage = {"betreff": "Zählungen", "text": "Zählungen, die die {stelle} hat.{zusatz}"}
    assert dl.anfrage(vorlage, "Mühltal", None)["text"] == "Zählungen, die die Stadt Mühltal hat."
    assert (dl.anfrage(vorlage, "Mühltal", "Seit 2022.", "Gemeinde Mühltal")["text"]
            == "Zählungen, die die Gemeinde Mühltal hat.\nSeit 2022.")


@pytest.mark.parametrize("eintrag, meldung", [
    ({"ags": "02000009", "name": "Leer", "lage": [9.0, 53.0]}, "weder kurzzeit noch dauer"),
    ({"ags": "02000009", "name": "Falsch", "lage": [9.0, 53.0],
      "kurzzeit": {"stand": "irgendwie"}}, "kurzzeit.stand 'irgendwie' unbekannt"),
    ({"ags": "02000009", "name": "Alt", "lage": [9.0, 53.0],
      "dauer": {"stand": "automatisch"}}, "dauer.stand 'automatisch' unbekannt"),
])
def test_stand_pflicht(pfade, eintrag, meldung, schreibe_konfiguration):
    """Ein Eintrag braucht einen Block der Kurzzeitzählungen oder einen der Dauerzählstellen, je
    mit einem Stand aus der einen Liste für beide Familien."""
    cfg = copy.deepcopy(KONFIG)
    cfg["datenlage"].append(eintrag)
    schreibe_konfiguration(pfade.config, cfg)
    with pytest.raises(ValueError, match=meldung):
        dl.datenlage(pfade)


def test_staende_in_beiden_sprachen_und_familien():
    """Der Sprachumschalter der Karte braucht jeden Stand in jeder Familie."""
    alle = (dl.STAND, dl.STAND_EN, dl.STAND_DAUER, dl.STAND_DAUER_EN)
    assert all(x.keys() == dl.STAND.keys() for x in alle)
    assert "automatisch" not in dl.STAND and {"nichts_offen", "ohne_lizenz"} <= dl.STAND.keys()


def test_zaehlkarte_datenlage_aus_index(pfade):
    ziele = dl.schreibe(pfade, date(2026, 11, 13))
    assert ziele == [pfade.karte / "datenlage.json", pfade.repo / "docs" / "DATENLAGE.md"]
    fc = json.loads(ziele[0].read_text(encoding="utf-8"))
    test = fc["features"][0]["properties"]
    assert test["kurzzeit"]["zaehlungen"] == 3  # aus index.json
    md = ziele[1].read_text(encoding="utf-8")
    assert "am 2026-11-13" in md
    assert ("| Hafenstadt | HH | erhoben – Anfrage aussichtsreich | vorhanden, Werte nicht offen |"
            in md)
    assert "| Dorf | HH | Anfrage gescheitert |  |" in md
    # nur Dauerzählstellen: „–“ in der Tabelle, Abschnitt mit deren Stand und Belegen
    assert "| Radstadt | HH | – | vorhanden, aber ohne Lizenz |" in md
    assert "## Radstadt (HH) – Dauerzählstellen vorhanden, aber ohne Lizenz" in md
    assert "**Lage:** Rad-Dauerzählstellen; Werte ohne Lizenz" in md
    assert "[Portal](https://example.org/portal)" in md
    assert "## Teststadt – Dauerzählstellen in der Karte" in md
    assert "**Dauerzählstellen (vorhanden, Werte nicht offen):** Dauerzählstellen; offen nur" in md
    # Belege: die der Kurzzeitzählungen und die der Dauerzählstellen
    assert "[Antwort](https://example.org/antwort) · [Karte](https://example.org/karte)" in md


def test_zaehlungen_je_quelle():
    index = {"quellen": ["a", "b"],
             "stellen": {"felder": ["id", "quelle"], "werte": [["a:1", 0], ["b:1", 1], ["a:2", 0]]},
             "zaehlungen": {"felder": ["stelle"], "werte": [[0], [1], [2], [2]]}}
    assert dl.zaehlungen_je_quelle(index) == Counter({"a": 3, "b": 1})
