"""Ettlingen (re@di, Datastore mit UrbanPulse-Strömen): Abruf des Dumps, nur die Ströme je
Fahrtrichtung, Kfz als Summe der Klassen, fehlende Stunde = nicht gezählt, Zeitumstellung,
frisch_tage, Namen je Sensor und der Vertrag von dauer/ mit der Lizenz CC BY-NC 4.0."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

import zaehlkarte.fetch
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import readi_urbanpulse as ett
from zaehlkarte.dauer import site
from zaehlkarte.dauer.modell import tagessummen

Q = {
    "code": "ettlingen", "name": "Ettlingen (automatische Zählstellen)", "land": "BW",
    "adapter": "readi_urbanpulse", "dump": "https://readi.example/datastore/dump/abc",
    "klassen": {"kfz": ["PKW", "Leichtes Nutzfahrzeug", "LKW", "LKW+Anhänger", "Motorrad"]},
    "frisch_tage": 2, "lizenz": "CC BY-NC 4.0",
    "lizenz_url": "https://creativecommons.org/licenses/by-nc/4.0/deed.de",
    "stellen": {"1263": {"name": "Rastatter Straße"},
                "395387": {"name": "Pforzheimer Straße", "abschnitt": "Höhe Hausnummer 14"}},
}
KOPF = ["_id", "timestamp", "dataset_id", "label", "avg_speed", "link", "classification", "amount",
        "series_name", "y", "latitude", "longitude", "direction", "lane_index", "sensor_id", "sid",
        "source"]
LAGE = {"1263": ("48.94020260263178", "8.403475767971708"),
        "395387": ("48.94299648461639", "8.409507136281253")}
STROM = {  # sid -> (Sensor, Fahrstreifen, Bezeichnung, Richtung)
    "4d9ed427": ("1263", "2", "Rastatter Strasse", "Rastatter Strasse - Richtung Bruchhausen"),
    "9572cf5c": ("1263", "3", "Rastatter Strasse", "Rastatter Strasse - Rcihtung Innenstadt"),
    "815788c8": ("395387", "1", "Pforzheimer-Str-14", "Pforzheimer-Str-14 - Richtung Waldbronn"),
}


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


class Dump:
    def __init__(self):
        self.zeilen: list[dict] = []

    def strom(self, sid: str, t: datetime, klassen: dict[str, int]) -> None:
        sensor, spur, label, richtung = STROM[sid]
        for k, y in klassen.items():
            self.zeilen.append({
                "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S"), "dataset_id": sid, "label": label,
                "avg_speed": "48.5", "link": f"https://www.google.com/maps?q={LAGE[sensor][0]}",
                "classification": "Car", "amount": "", "series_name": k, "y": str(y),
                "latitude": LAGE[sensor][0], "longitude": LAGE[sensor][1], "direction": richtung,
                "lane_index": spur, "sensor_id": sensor, "sid": sid, "source": "UrbanPulse"})

    def anderes(self, **z) -> None:
        self.zeilen.append({k: "" for k in KOPF} | z)

    def text(self) -> str:
        f = io.StringIO()
        w = csv.DictWriter(f, fieldnames=KOPF, lineterminator="\n")
        w.writeheader()
        for i, z in enumerate(self.zeilen, 1):
            w.writerow({k: "" for k in KOPF} | z | {"_id": str(i)})
        return "﻿" + f.getvalue()  # wie der Dump mit BOM


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.config.mkdir(parents=True, exist_ok=True)
    return p


def lade_mit(monkeypatch, dump: Dump) -> list[str]:
    def lade(url: str, ziel: Path) -> Path:
        assert url == Q["dump"]
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(dump.text(), encoding="utf-8")
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    return []


def abgerufen(pfade: Pfade, wann: str) -> None:
    pfad = pfade.roh / "ettlingen" / "abruf.json"
    meta = json.loads(pfad.read_text())
    meta["abgerufen"] = wann
    pfad.write_text(json.dumps(meta))


def test_hole_und_lese(pfade, monkeypatch):
    d = Dump()
    beginn = utc(2026, 10, 23, 22)  # 24.10. 0 Uhr Sommerzeit; 25.10. Rückstellung (25 Stunden)
    for i in range(4 * 24 + 1):
        t = beginn + timedelta(hours=i)
        # Bruchhausen: Klassen nur, wenn Fahrzeuge da (nachts nur Pkw); dazu eine fremde Klasse
        nacht = (t.hour + 2) % 24 < 5
        d.strom("4d9ed427", t, {"PKW": 7} if nacht else {"PKW": 40, "LKW": 3, "Motorrad": 1,
                                                            "Fahrrad": 9})
        if t != utc(2026, 10, 26, 5):  # Innenstadt: am 26.10. fehlt 6 Uhr Ortszeit ganz
            d.strom("9572cf5c", t, {"PKW": 20, "Leichtes Nutzfahrzeug": 2})
        d.strom("815788c8", t, {"PKW": 30, "LKW+Anhänger": 1})
    # nicht übernommen: alte Kennung (laufender Tageszähler), Testimport, Übergangszeile
    d.anderes(timestamp="2026-10-24T08:00:00", dataset_id="48", label="Rastatter Strasse",
              series_name="PKW", y="1234", link="https://goo.gl/maps/x")
    d.anderes(timestamp="2026-10-24T08:59:13", dataset_id="1d30632e", label="Karlsruher Strasse",
              series_name="Karlsruhe Richtung Ettlingen", y="2")
    d.anderes(timestamp="2026-10-24T07:00:00", dataset_id="4d9ed427",
              label="Rastatter Strasse | Rastat", series_name="PKW", y="5")
    lade_mit(monkeypatch, d)
    log = ett.hole(Q, pfade)
    assert log[0].startswith("ettlingen: Datastore geholt")
    abruf = json.loads((pfade.roh / "ettlingen" / "abruf.json").read_text())
    assert abruf["url"] == Q["dump"] and len(abruf["sha256"]) == 64
    assert not (pfade.roh / "ettlingen" / "datastore.csv").exists()  # nur gepackt
    abgerufen(pfade, "2026-10-30T12:00:00Z")  # alles älter als frisch_tage (2 Tage)

    b = ett.Bericht()
    r = ett.lese(Q, pfade, b)
    assert b.zeilen_gesamt == len(d.zeilen) and b.stroeme == 3 and b.stellen == 3
    rad = sum(1 for z in d.zeilen if z["series_name"] == "Fahrrad")
    assert b.andere_klassen == {"Fahrrad": rad}
    assert [s.kennung for s in r.stellen] == ["1263-2", "1263-3", "395387-1"]
    s0, s1, s2 = r.stellen
    assert (s0.name, s0.abschnitt) == ("Rastatter Straße", None)
    assert s0.richtung == "Richtung Bruchhausen"
    assert s1.richtung == "Richtung Innenstadt"  # Tippfehler der Quelle
    assert (s0.lon, s0.lat) == (s1.lon, s1.lat) == (8.403476, 48.940203)  # dieselbe Lage
    assert (s2.name, s2.abschnitt) == ("Pforzheimer Straße", "Höhe Hausnummer 14")
    assert s0.id == "ettlingen:1263-2" and set(r.werte) == {"kfz"}

    summe, n = tagessummen(r, "kfz")
    i24, i25, i26 = (r.index(date(2026, 10, x)) for x in (24, 25, 26))
    # 24.10.: 5 Nachtstunden (0–4 Uhr) nur Pkw 7, sonst 40 + 3 + 1 (Fahrrad zählt nicht)
    assert summe[0, i24] == 5 * 7 + 19 * 44
    # Rückstellung: 2 Uhr kommt zweimal -> 25 Stunden, beide in Stunde 2
    assert r.doppelt[2, i25] and n[2, i25] == 24 and summe[2, i25] == 25 * 31
    assert summe[1, i26] == -1 and n[1, i26] == 23  # 6 Uhr fehlt
    assert summe[1, i24] == 24 * 22
    assert b.stunden["kfz"] > 0 and b.frisch == 0


def test_frisch_tage(pfade, monkeypatch):
    d = Dump()
    for i in range(5 * 24):
        d.strom("815788c8", utc(2026, 11, 1, 23) + timedelta(hours=i), {"PKW": 10})
    lade_mit(monkeypatch, d)
    ett.hole(Q, pfade)
    abgerufen(pfade, "2026-11-06T23:30:00Z")  # Grenze 04.11. 23 Uhr UTC = 05.11. 0 Uhr Ortszeit
    b = ett.Bericht()
    r = ett.lese(Q, pfade, b)
    summe, _ = tagessummen(r, "kfz")
    assert r.tag(r.tage - 1) == date(2026, 11, 4)
    assert summe[0].tolist() == [240, 240, 240]
    assert b.frisch == 2 * 24


def test_site_mit_ettlingen(pfade, monkeypatch):
    d = Dump()
    for i in range(3 * 24):
        t = utc(2026, 11, 1, 23) + timedelta(hours=i)
        d.strom("4d9ed427", t, {"PKW": 10})
        d.strom("9572cf5c", t, {"PKW": 20})
    lade_mit(monkeypatch, d)
    ett.hole(Q, pfade)
    abgerufen(pfade, "2026-11-10T00:00:00Z")
    r = ett.lese(Q, pfade, ett.Bericht())
    site.schreibe([(Q, r)], pfade, date(2026, 11, 12))
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    assert index["gruppen"] == ["kfz"]
    q = index["quellen"][0]
    assert q["lizenzen"][0]["lizenz"] == "CC BY-NC 4.0" and q["gruppen"] == ["kfz"]
    assert q["zeitraeume"] == {"kfz": ["2026-11-02", "2026-11-04"]}
    felder = index["stellen"]["felder"]
    stellen = [dict(zip(felder, w, strict=True)) for w in index["stellen"]["werte"]]
    assert [s["id"] for s in stellen] == ["ettlingen:1263-2", "ettlingen:1263-3"]
    assert {(s["lon"], s["lat"]) for s in stellen} == {(8.403476, 48.940203)}
    assert index["kalender"]["BW"][0] in "swhfu"
    chunk = json.loads((pfade.karte / "dauer" / "0.json").read_text())
    assert chunk["stellen"]["ettlingen:1263-3"]["tage"]["kfz"] == [480, 480, 480]
