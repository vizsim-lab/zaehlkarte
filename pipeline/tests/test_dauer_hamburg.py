"""Hamburg (SensorThings, Wärmebildkameras): Abruf gegen eine nachgebaute API, Gedächtnis,
Umrechnung UTC -> Ortszeit samt Zeitumstellung, Straßennamen aus einem kleinen OSM-Abzug."""

from __future__ import annotations

import json
import urllib.parse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import hamburg_sta as hh
from zaehlkarte.dauer import site
from zaehlkarte.dauer.modell import tagessummen

Q = {
    "code": "hamburg_kfz", "name": "Hamburg (Kfz)", "land": "HH", "adapter": "hamburg_sta",
    "api": "https://iot.example/v1.1", "dienst": "HH_STA_Kfz",
    "layer": {"kfz": "Kfz_1-Stunde", "sv": "SV_1-Stunde"},
    "nachladen_tage": 2, "frisch_tage": 1, "lizenz": "dl-de/by-2-0",
}


def zeit(t: datetime) -> str:
    return f"{t:%Y-%m-%dT%H}:00:00Z/{t:%Y-%m-%dT%H}:59:59Z"


def stunden(von: datetime, n: int, wert=lambda t: 10) -> list[tuple[str, object]]:
    return [(zeit(von + timedelta(hours=i)), wert(von + timedelta(hours=i))) for i in range(n)]


def thing(kennung: str, lon: float, lat: float, richtung: str, arm: str) -> dict:
    return {
        "@iot.id": int(kennung), "name": f"Verkehrszählstelle {kennung}",
        "properties": {"assetID": kennung, "richtung": richtung},
        "Locations": [{
            "description": f"Mittelpunkt des Streckenverlaufes bezüglich Zählstelle {kennung[:4]} "
                           f"auf dem Richtungsarm {arm} von {richtung}",
            "location": {"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": [lon, lat]}}}],
    }


class FakeSTA:
    """Antwortet wie FROST auf die drei Abfragen des Adapters (Datastreams mit Thing,
    Datastreams mit verschachtelten Observations, ein Datastream mit Observations)."""

    def __init__(self):
        self.ds: list[dict] = []  # {id, layer, thing, props, obs: [(Zeit, Wert)]}
        self.abrufe: list[str] = []

    def __call__(self, sitzung, url):
        self.abrufe.append(url)
        teile = urllib.parse.urlsplit(url)
        p = dict(urllib.parse.parse_qsl(teile.query))
        expand = p.get("$expand", "")
        seit = None
        if "phenomenonTime ge " in expand:
            seit = expand.split("phenomenonTime ge ")[1].split(";")[0].rstrip(")")

        def obs(d):
            return [{"phenomenonTime": z, "result": w} for z, w in d["obs"]
                    if seit is None or z[:20] >= seit]

        if "Datastreams(" in teile.path:
            i = int(teile.path.split("Datastreams(")[1].rstrip(")"))
            d = next(x for x in self.ds if x["id"] == i)
            return {"@iot.id": i, "Observations": obs(d)}
        layer = p["$filter"].split("layerName eq '")[1].rstrip("'")
        treffer = [d for d in self.ds if d["layer"] == layer]
        if expand.startswith("Thing"):
            return {"value": [{"@iot.id": d["id"], "name": f"ds {d['id']}",
                               "properties": d["props"],
                               "Thing": d["thing"]} for d in treffer]}
        return {"value": [{"@iot.id": d["id"], "Observations": obs(d)} for d in treffer]}


@pytest.fixture
def api(monkeypatch):
    fake = FakeSTA()
    monkeypatch.setattr(hh, "_json", fake)
    return fake


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.config.mkdir(parents=True, exist_ok=True)
    return p


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


def test_gedaechtnis_roundtrip_und_gleiche_bytes(tmp_path):
    g = {}
    ok, weg = hh.uebernimm(g, "kfz", "0248931", [
        ("2026-11-01T00:00:00Z/2026-11-01T00:59:59Z", 5),
        ("2026-11-01T01:00:00Z/2026-11-01T01:59:59Z", 7),
        ("2026-11-01T02:15:00Z/2026-11-01T02:29:59Z", 3),  # keine volle Stunde
        ("2026-11-01T03:00:00Z/2026-11-01T03:59:59Z", 2.5),  # keine Anzahl
        ("2026-12-01T00:00:00Z/2026-12-01T00:59:59Z", 0),
    ])
    assert (ok, weg) == (3, 2)
    assert hh.schreibe_gedaechtnis(tmp_path, g) == [
        "stunden_2026-11.csv.gz", "stunden_2026-12.csv.gz"]
    assert hh.schreibe_gedaechtnis(tmp_path, g) == []  # gleicher Inhalt -> keine Änderung
    zurueck = hh.lies_gedaechtnis(tmp_path)
    assert zurueck[("0248931", "kfz", "2026-11-01")][:3] == [5, 7, None]
    assert zurueck[("0248931", "kfz", "2026-12-01")][0] == 0  # 0 bleibt 0, leer bleibt leer
    assert hh.letzte_stunde(zurueck) == utc(2026, 12, 1, 0)


def test_hole_und_lese_mit_zeitumstellung(api, pfade):
    # Stelle A: Kfz und SV, 24.10.–27.10.2026 (Rückstellung am 25.10.), am 26.10. fehlt eine Stunde
    a = thing("0248931", 10.0, 53.6, "Nordost nach Südwest", "Nordost")
    b = thing("0248942", 10.001, 53.6, "Südwest nach Nordost", "Südwest")
    beginn = utc(2026, 10, 23, 22)  # 24.10. 0 Uhr Sommerzeit
    kfz_a = [x for x in stunden(beginn, 4 * 24 + 1, lambda t: 100)
             if x[0][:13] != "2026-10-26T05"]
    api.ds = [
        {"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {"zaehlfelder": ["0699-Z.3"]},
         "obs": kfz_a},
        {"id": 2, "layer": "SV_1-Stunde", "thing": a, "props": {},
         "obs": stunden(beginn, 4 * 24 + 1, lambda t: 3)},
        {"id": 3, "layer": "Kfz_1-Stunde", "thing": b, "props": {},
         "obs": stunden(beginn, 4 * 24 + 1, lambda t: 50)},
    ]
    log = hh.hole(Q, pfade)
    assert "Gedächtnis geändert: stunden_2026-10.csv.gz" in log[0]
    meta = json.loads((pfade.roh / "hamburg_kfz" / "stellen.json").read_text())
    meta["abgerufen"] = "2026-10-29T00:00:00Z"  # alles älter als frisch_tage (1 Tag)
    (pfade.roh / "hamburg_kfz" / "stellen.json").write_text(json.dumps(meta))
    bericht = hh.Bericht()
    r = hh.lese(Q, pfade, bericht)
    assert [s.kennung for s in r.stellen] == ["0248931", "0248942"]
    s0 = r.stellen[0]
    assert s0.name == "Zählstelle 0248931"  # ohne OSM-Abzug: nach Kennung
    assert s0.abschnitt == "Knotenpunkt 0248, Arm Nordost"
    assert s0.richtung == "von Nordost nach Südwest" and s0.fahrstreifen == ["Zählfeld 0699-Z.3"]
    assert set(r.werte) == {"kfz", "sv"}
    i25 = r.index(date(2026, 10, 25))
    # Rückstellung: 2 Uhr kommt zweimal -> Summe beider Stunden, Tag hat 25 Stunden
    assert r.werte["kfz"][0, i25, 2] == 200 and r.doppelt[0, i25]
    summe, n = tagessummen(r, "kfz")
    assert summe[0, i25] == 25 * 100 and n[0, i25] == 24
    assert summe[0, r.index(date(2026, 10, 24))] == 24 * 100
    assert summe[0, r.index(date(2026, 10, 26))] == -1  # 6 Uhr Ortszeit fehlt
    assert tagessummen(r, "sv")[0][0, i25] == 25 * 3
    assert tagessummen(r, "sv")[0][1, i25] == -1  # Stelle B zählt keinen Schwerverkehr
    assert bericht.stunden["kfz"] > 0 and bericht.stellen == 2

    # zweiter Lauf: nur ab letzter Stunde minus nachladen_tage, korrigierter Wert ersetzt den alten
    api.abrufe.clear()
    api.ds[2]["obs"] = [(z, 60 if z.startswith("2026-10-27T") else w) for z, w in api.ds[2]["obs"]]
    hh.hole(Q, pfade)
    assert any("phenomenonTime ge 2026-10-25T22:00:00Z" in urllib.parse.unquote(u)
               for u in api.abrufe)
    g = hh.lies_gedaechtnis(pfade.roh / "hamburg_kfz" / "gedaechtnis")
    assert g[("0248942", "kfz", "2026-10-27")][0] == 60
    assert g[("0248942", "kfz", "2026-10-24")][0] == 50  # Altes bleibt


def test_frisch_tage_und_neue_stelle(api, pfade):
    a = thing("0300911", 10.0, 53.5, "Nord nach Süd", "Nord")
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {},
               "obs": stunden(utc(2026, 11, 1, 23), 72)}]
    hh.hole(Q, pfade)
    # neue Stelle beim zweiten Lauf: ganze Reihe, nicht nur ab `seit`
    c = thing("0300922", 10.0, 53.501, "Süd nach Nord", "Süd")
    api.ds.append({"id": 5, "layer": "Kfz_1-Stunde", "thing": c, "props": {},
                   "obs": stunden(utc(2026, 10, 1, 22), 24)})
    hh.hole(Q, pfade)
    g = hh.lies_gedaechtnis(pfade.roh / "hamburg_kfz" / "gedaechtnis")
    assert ("0300922", "kfz", "2026-10-02") in g
    meta = json.loads((pfade.roh / "hamburg_kfz" / "stellen.json").read_text())
    meta["abgerufen"] = "2026-11-04T10:00:00Z"  # frisch_tage 1 -> ab 3.11. 10 Uhr UTC nicht
    (pfade.roh / "hamburg_kfz" / "stellen.json").write_text(json.dumps(meta))
    bericht = hh.Bericht()
    r = hh.lese(Q, pfade, bericht)
    assert bericht.frisch > 0
    assert r.tag(r.tage - 1) <= date(2026, 11, 3)
    i = [s.kennung for s in r.stellen].index("0300911")
    assert tagessummen(r, "kfz")[0][i, r.index(date(2026, 11, 2))] == 240


def test_naechste_strasse(tmp_path):
    osm = tmp_path / "klein.osm"
    osm.write_text("""<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6">
 <node id="1" lat="53.6000" lon="10.0000"/><node id="2" lat="53.6000" lon="10.0100"/>
 <node id="3" lat="53.6003" lon="10.0000"/><node id="4" lat="53.6003" lon="10.0100"/>
 <node id="5" lat="53.6100" lon="10.0000"/><node id="6" lat="53.6100" lon="10.0100"/>
 <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="secondary"/>
  <tag k="name" v="Bramfelder Straße"/></way>
 <way id="11"><nd ref="3"/><nd ref="4"/><tag k="highway" v="cycleway"/>
  <tag k="name" v="Radweg Nord"/></way>
 <way id="12"><nd ref="5"/><nd ref="6"/><tag k="highway" v="footway"/>
  <tag k="name" v="Parkweg"/></way>
</osm>
""")
    from zaehlkarte.dauer.strassen import naechste_strassen

    t = naechste_strassen(osm, {
        "a": (10.005, 53.60025),  # näher am Radweg, aber die Fahrstraße liegt im Umkreis
        "b": (10.005, 53.61002),  # nur ein Fußweg in der Nähe
        "c": (10.005, 53.6050),   # nichts im Umkreis
    })
    assert t["a"]["name"] == "Bramfelder Straße" and t["a"]["abstand_m"] < 30
    assert t["b"]["name"] == "Parkweg"
    assert "c" not in t


def test_strassennamen_overpass_nicht_erreichbar(api, pfade, monkeypatch):
    from zaehlkarte import abruf

    def hole(url, **k):
        raise abruf.requests.ReadTimeout(url)

    monkeypatch.setattr(abruf, "hole", hole)
    a = thing("0248931", 10.0050, 53.60005, "Ost nach West", "Ost")
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {},
               "obs": stunden(utc(2026, 11, 1, 23), 48)}]
    q = {**Q, "overpass": ["https://langsam.example/api/interpreter"]}
    log = hh.hole(q, pfade)
    assert any("Stunden geholt" in z for z in log)  # die Zählwerte kommen trotzdem
    assert any("nicht geholt (Overpass: ReadTimeout)" in z for z in log)
    assert not (pfade.roh / "hamburg_kfz" / "gedaechtnis" / "strassen.json").exists()


def test_naechste_strasse_aus_overpass():
    from zaehlkarte.dauer.strassen import naechste, overpass_abfrage, segmente_aus_overpass

    punkte = {"a": (10.005, 53.60025), "b": (10.005, 53.61002), "c": (10.005, 53.6050)}
    antwort = overpass_antwort(
        ("Bramfelder Straße", "secondary", [(10.0, 53.6), (10.01, 53.6)]),
        ("Radweg Nord", "cycleway", [(10.0, 53.6003), (10.01, 53.6003)]),
        ("Parkweg", "footway", [(10.0, 53.61), (10.01, 53.61)]),
        ("Gleis", "rail", [(10.0, 53.605), (10.01, 53.605)]))  # kein highway der Listen
    antwort["elements"].append({"type": "node", "id": 1, "lat": 53.605, "lon": 10.005})
    t = naechste(punkte, segmente_aus_overpass(antwort, (9.9, 53.5, 10.1, 53.7)))
    assert t["a"]["name"] == "Bramfelder Straße" and t["a"]["abstand_m"] < 30
    assert t["b"]["name"] == "Parkweg"
    assert "c" not in t
    abfrage = overpass_abfrage({"a": (10.005, 53.60025)})
    assert abfrage == ('[out:json][timeout:60];(way(around:50,53.600250,10.005000)'
                       '["highway"]["name"];);out geom;')


def test_site_mit_hamburg(api, pfade):
    a = thing("0248931", 10.0, 53.6, "Nordost nach Südwest", "Nordost")
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {},
               "obs": stunden(utc(2026, 11, 1, 23), 3 * 24, lambda t: 10)},
              {"id": 2, "layer": "SV_1-Stunde", "thing": a, "props": {},
               "obs": stunden(utc(2026, 11, 1, 23), 3 * 24, lambda t: 1)}]
    hh.hole(Q, pfade)
    meta = json.loads((pfade.roh / "hamburg_kfz" / "stellen.json").read_text())
    meta["abgerufen"] = "2026-11-10T00:00:00Z"
    (pfade.roh / "hamburg_kfz" / "stellen.json").write_text(json.dumps(meta))
    r = hh.lese(Q, pfade, hh.Bericht())
    dateien, bericht = site.schreibe([(Q, r)], pfade, date(2026, 11, 12))
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    assert index["gruppen"] == ["kfz", "sv"]
    assert index["gruppen_namen"]["sv"] == "Schwerverkehr (Detektor)"
    assert index["quellen"][0]["gruppen"] == ["kfz", "sv"]
    assert index["quellen"][0]["zeitraeume"] == {"kfz": ["2026-11-02", "2026-11-04"],
                                                 "sv": ["2026-11-02", "2026-11-04"]}
    werte = dict(zip(index["stellen"]["felder"], index["stellen"]["werte"][0], strict=True))
    assert werte["g"] == 3 and werte["von"] == "2026-11-02" and werte["bis"] == "2026-11-04"
    chunk = json.loads((pfade.karte / "dauer" / "0.json").read_text())
    d = chunk["stellen"]["hamburg_kfz:0248931"]
    assert d["tage"]["sv"] == [24, 24, 24] and d["n"]["kfz"] == [24, 24, 24]
    assert "kalender" in index and index["kalender"]["HH"][0] in "swhfu"
    assert {g: len(v) for g, v in index["juengster"].items()} == {"kfz": 1, "sv": 1}


def overpass_antwort(*wege: tuple[str, str, list[tuple[float, float]]]) -> dict:
    """Antwort von Overpass (`out geom`): je Weg Name, highway und Punkte (lon, lat)."""
    return {"elements": [
        {"type": "way", "id": i, "tags": {"highway": hw, "name": name},
         "geometry": [{"lat": lat, "lon": lon} for lon, lat in punkte]}
        for i, (name, hw, punkte) in enumerate(wege, 10)]}


def test_strassennamen_und_knotenpunkt(api, pfade, monkeypatch):
    # zwei Arme eines Knotenpunkts an zwei Straßen: Name = eigene Straße, Abschnitt = die andere
    from zaehlkarte import abruf

    antwort = overpass_antwort(
        ("Bramfelder Straße", "primary", [(9.99, 53.60), (10.01, 53.60)]),
        ("Steilshooper Straße", "secondary", [(10.00, 53.59), (10.00, 53.61)]))
    abfragen = []

    class Antwort:
        def json(self):
            return antwort

    def hole(url, daten=None, **k):
        abfragen.append(url)
        if "kaputt" in url:
            raise abruf.Gesperrt(url)  # der erste Server: der nächste wird versucht
        assert "around:50," in daten["data"] and "out geom" in daten["data"]
        return Antwort()

    monkeypatch.setattr(abruf, "hole", hole)
    a = thing("0248931", 10.0050, 53.60005, "Ost nach West", "Ost")  # an der Bramfelder Straße
    b = thing("0248942", 10.00005, 53.6050, "Nord nach Süd", "Nord")  # an der Steilshooper Straße
    # Gegenrichtung desselben Arms, näher an der Querstraße (20 m) als an ihrer eigenen (30 m)
    c = thing("0248932", 10.0003, 53.60027, "West nach Ost", "Ost")
    obs = stunden(utc(2026, 11, 1, 23), 48)
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {}, "obs": obs},
              {"id": 2, "layer": "Kfz_1-Stunde", "thing": b, "props": {}, "obs": obs},
              {"id": 3, "layer": "Kfz_1-Stunde", "thing": c, "props": {}, "obs": obs}]
    q = {**Q, "overpass": ["https://kaputt.example/api/interpreter",
                           "https://overpass.example/api/interpreter"]}
    log = hh.hole(q, pfade)
    assert any("Straßennamen für 3 neue Stellen (3 gefunden)" in z for z in log)
    hh.hole(q, pfade)  # zweiter Lauf: Namen aus dem Gedächtnis, keine neue Abfrage
    assert abfragen == q["overpass"]
    namen = json.loads((pfade.roh / "hamburg_kfz" / "gedaechtnis" / "strassen.json").read_text())
    assert "OpenStreetMap" in namen["lizenz"]
    assert namen["osm"] == "https://overpass.example/api/interpreter"
    r = hh.lese(q, pfade, hh.Bericht())
    s = {x.kennung: x for x in r.stellen}
    assert s["0248931"].name == "Bramfelder Straße"
    assert s["0248931"].abschnitt == "Knotenpunkt mit Steilshooper Straße, Arm Ost"
    assert s["0248942"].name == "Steilshooper Straße"
    assert s["0248942"].abschnitt == "Knotenpunkt mit Bramfelder Straße, Arm Nord"
    assert namen["stellen"]["0248932"]["name"] == "Steilshooper Straße"  # eigener Treffer …
    assert s["0248932"].name == "Bramfelder Straße"  # … aber der Arm heißt wie sein bester
