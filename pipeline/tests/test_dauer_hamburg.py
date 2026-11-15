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


def test_strassennamen_abzug_nicht_zu_holen(api, pfade, monkeypatch):
    import zaehlkarte.fetch
    from zaehlkarte import abruf

    def lade(url, ziel):
        raise abruf.Gesperrt(url)

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    a = thing("0248931", 10.0050, 53.60005, "Ost nach West", "Ost")
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {},
               "obs": stunden(utc(2026, 11, 1, 23), 48)}]
    q = {**Q, "osm": "https://download.example/hamburg-latest.osm"}
    log = hh.hole(q, pfade)
    assert any("Stunden geholt" in z for z in log)  # die Zählwerte kommen trotzdem
    assert any("nicht geholt (OSM-Abzug: Gesperrt)" in z for z in log)
    assert not (pfade.roh / "hamburg_kfz" / "gedaechtnis" / "strassen.json").exists()


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


def test_strassennamen_und_knotenpunkt(api, pfade, tmp_path, monkeypatch):
    # zwei Arme eines Knotenpunkts an zwei Straßen: Name = eigene Straße, Abschnitt = die andere
    osm = tmp_path / "hh.osm"
    osm.write_text("""<?xml version='1.0' encoding='UTF-8'?>
<osm version="0.6">
 <node id="1" lat="53.6000" lon="9.9900"/><node id="2" lat="53.6000" lon="10.0100"/>
 <node id="3" lat="53.5900" lon="10.0000"/><node id="4" lat="53.6100" lon="10.0000"/>
 <way id="10"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary"/>
  <tag k="name" v="Bramfelder Straße"/></way>
 <way id="11"><nd ref="3"/><nd ref="4"/><tag k="highway" v="secondary"/>
  <tag k="name" v="Steilshooper Straße"/></way>
</osm>
""")
    import zaehlkarte.fetch

    geladen = []

    def lade(url, ziel):
        geladen.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(osm.read_bytes())
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    a = thing("0248931", 10.0050, 53.60005, "Ost nach West", "Ost")  # an der Bramfelder Straße
    b = thing("0248942", 10.00005, 53.6050, "Nord nach Süd", "Nord")  # an der Steilshooper Straße
    # Gegenrichtung desselben Arms, näher an der Querstraße (20 m) als an ihrer eigenen (30 m)
    c = thing("0248932", 10.0003, 53.60027, "West nach Ost", "Ost")
    obs = stunden(utc(2026, 11, 1, 23), 48)
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {}, "obs": obs},
              {"id": 2, "layer": "Kfz_1-Stunde", "thing": b, "props": {}, "obs": obs},
              {"id": 3, "layer": "Kfz_1-Stunde", "thing": c, "props": {}, "obs": obs}]
    q = {**Q, "osm": "https://download.example/hamburg-latest.osm"}  # XML statt PBF
    log = hh.hole(q, pfade)
    assert any("Straßennamen für 3 neue Stellen (3 gefunden, OSM-Abzug vom " in z for z in log)
    hh.hole(q, pfade)  # zweiter Lauf: Namen aus dem Gedächtnis, kein neuer Abzug
    # eine neue Stelle später: Name aus dem schon geladenen Abzug, nicht noch einmal laden
    d = thing("0248941", 10.00005, 53.6060, "Süd nach Nord", "Nord")
    api.ds.append({"id": 4, "layer": "Kfz_1-Stunde", "thing": d, "props": {}, "obs": obs})
    log = hh.hole(q, pfade)
    assert any("Straßennamen für 1 neue Stellen (1 gefunden" in z for z in log)
    assert geladen == [q["osm"]]
    namen = json.loads((pfade.roh / "hamburg_kfz" / "gedaechtnis" / "strassen.json").read_text())
    assert "OpenStreetMap" in namen["lizenz"] and namen["osm"] == q["osm"]
    assert namen["abzug"] == namen["stand"]  # heute geladen
    r = hh.lese(q, pfade, hh.Bericht())
    s = {x.kennung: x for x in r.stellen}
    assert s["0248931"].name == "Bramfelder Straße"
    assert s["0248931"].abschnitt == "Knotenpunkt mit Steilshooper Straße, Arm Ost"
    assert s["0248942"].name == "Steilshooper Straße"
    assert s["0248942"].abschnitt == "Knotenpunkt mit Bramfelder Straße, Arm Nord"
    assert namen["stellen"]["0248932"]["name"] == "Steilshooper Straße"  # eigener Treffer …
    assert s["0248932"].name == "Bramfelder Straße"  # … aber der Arm heißt wie sein bester


# ---------------------------------------------------------------- Tageswerte (Layer „1-Tag“)

Q_TAG = {**Q, "tageslayer": {"kfz": "Kfz_1-Tag", "sv": "SV_1-Tag"}}


def ortstage(von: date, n: int, wert=lambda t: 1000) -> list[tuple[str, object]]:
    """Tages-Observations wie Hamburg sie liefert: Ortstag in UTC (Mitternacht bis Mitternacht
    Ortszeit, 23 bzw. 25 Stunden an den Tagen der Zeitumstellung)."""
    from zoneinfo import ZoneInfo

    berlin = ZoneInfo("Europe/Berlin")
    out = []
    for i in range(n):
        t = von + timedelta(days=i)
        n_ = t + timedelta(days=1)
        a = datetime(t.year, t.month, t.day, tzinfo=berlin).astimezone(UTC)
        b = (datetime(n_.year, n_.month, n_.day, tzinfo=berlin).astimezone(UTC)
             - timedelta(seconds=1))
        out.append((f"{a:%Y-%m-%dT%H:%M:%SZ}/{b:%Y-%m-%dT%H:%M:%SZ}", wert(t)))
    return out


def test_ortstag():
    assert hh.ortstag("2021-05-25T22:00:00Z/2021-05-26T21:59:59Z") == date(2021, 5, 26)
    assert hh.ortstag("2026-11-10T23:00:00Z/2026-11-11T22:59:59Z") == date(2026, 11, 11)
    assert hh.ortstag("2026-11-10T23:00:00Z/2026-11-11T22:59:59.999Z") == date(2026, 11, 11)
    # Zeitumstellung: 23 bzw. 25 Stunden
    assert hh.ortstag("2026-03-28T23:00:00Z/2026-03-29T21:59:59Z") == date(2026, 3, 29)
    assert hh.ortstag("2026-10-24T22:00:00Z/2026-10-25T22:59:59Z") == date(2026, 10, 25)
    # kein Ortstag: UTC-Tag, halber Tag, 24 Stunden über die Umstellung, unlesbar
    assert hh.ortstag("2026-10-24T00:00:00Z/2026-10-24T23:59:59Z") is None
    assert hh.ortstag("2026-11-10T23:00:00Z/2026-11-11T10:59:59Z") is None
    assert hh.ortstag("2026-10-24T22:00:00Z/2026-10-25T21:59:59Z") is None
    assert hh.ortstag("2026-11-10T23:00:00/2026-11-11T22:59:59") is None  # ohne Zone
    assert hh.ortstag("") is None and hh.ortstag("2026-11-11") is None


def test_tagesgedaechtnis_roundtrip(tmp_path):
    g = {}
    ok, weg, widerspruch = hh.uebernimm_tage(g, "kfz", "0248931", [
        *ortstage(date(2025, 12, 30), 3, lambda t: t.day),
        ("2026-01-05T00:00:00Z/2026-01-05T23:59:59Z", 7),  # UTC-Tag, kein Ortstag
        (ortstage(date(2026, 1, 6), 1)[0][0], None),  # kein Wert
        (ortstage(date(2026, 1, 7), 1)[0][0], -3),
        (ortstage(date(2026, 1, 8), 1)[0][0], 0),  # 0 bleibt 0
        (ortstage(date(2026, 1, 8), 1)[0][0], 0),  # derselbe Tag noch einmal, gleicher Wert
        # Zeitumstellung 2026 mit 24 statt 23 Stunden (so liefert Hamburg 2026): kein Ortstag
        ("2026-03-28T23:00:00Z/2026-03-29T22:59:59Z", 900),
    ])
    assert (ok, weg, widerspruch) == (4, 4, 0)
    # verschiedene Werte für denselben Tag: nicht übernommen, ein aufgehobener Wert bleibt
    assert hh.uebernimm_tage(g, "kfz", "0248931", [
        (ortstage(date(2025, 12, 30), 1)[0][0], 5), (ortstage(date(2025, 12, 30), 1)[0][0], 6),
        (ortstage(date(2026, 1, 9), 1)[0][0], 5), (ortstage(date(2026, 1, 9), 1)[0][0], 6),
    ]) == (0, 0, 2)
    assert g[("0248931", "kfz", "2025-12")][29] == 30
    assert g[("0248931", "kfz", "2026-01")][8] is None
    ordner = tmp_path / "gedaechtnis"
    assert hh.schreibe_tage(ordner, g) == ["tage_2025.csv.gz", "tage_2026.csv.gz"]
    assert hh.schreibe_tage(ordner, g) == []  # gleicher Inhalt -> keine Änderung
    zurueck = hh.lies_tage(ordner)
    assert zurueck[("0248931", "kfz", "2025-12")][29:31] == [30, 31]
    assert zurueck[("0248931", "kfz", "2026-01")][:8] == [1, None, None, None, None, None, None, 0]
    assert hh.letzter_tag(zurueck) == date(2026, 1, 8)
    assert hh.lies_gedaechtnis(ordner) == {}  # Stunden- und Tagesdateien getrennt


def test_hole_und_lese_mit_tageswerten(api, pfade):
    """Tageswerte nur vor der ersten gezählten Stunde einer Stelle; ein Tag mit fehlender Stunde
    bleibt „nicht vollständig gezählt“; eine Stelle nur mit Tageswerten kommt in die Karte."""
    from zaehlkarte.dauer.modell import aus_tageswerten

    a = thing("0248931", 10.0, 53.6, "Nordost nach Südwest", "Nordost")
    c = thing("0249912", 10.01, 53.61, "Nord nach Süd", "Nord")  # nur Tageswerte
    beginn = utc(2026, 10, 23, 22)  # 24.10. 0 Uhr Sommerzeit
    kfz_a = [x for x in stunden(beginn, 4 * 24 + 1, lambda t: 100)
             if x[0][:13] != "2026-10-26T05"]  # am 26.10. fehlt eine Stunde
    api.ds = [
        {"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {}, "obs": kfz_a},
        {"id": 2, "layer": "SV_1-Stunde", "thing": a, "props": {},
         "obs": stunden(beginn, 4 * 24 + 1, lambda t: 3)},
        {"id": 11, "layer": "Kfz_1-Tag", "thing": a, "props": {},
         "obs": ortstage(date(2026, 10, 20), 9, lambda t: 1000 + t.day)},  # bis 28.10.
        {"id": 12, "layer": "SV_1-Tag", "thing": a, "props": {},
         "obs": ortstage(date(2026, 10, 22), 2, lambda t: 50)},
        {"id": 13, "layer": "Kfz_1-Tag", "thing": c, "props": {"zaehlfelder": ["1472-Z.7"]},
         "obs": ortstage(date(2026, 10, 1), 25, lambda t: 2000 + t.day)},  # bis 25.10.
    ]
    log = hh.hole(Q_TAG, pfade)
    zeile = next(z for z in log if "Tageswerten" in z)
    assert ("3 Datastreams mit Tageswerten, 36 Tage geholt ab Beginn (0 verworfen, 0 mit "
            "widersprüchlichen Werten)") in zeile
    assert "tage_2026.csv.gz" in zeile
    meta = json.loads((pfade.roh / "hamburg_kfz" / "stellen.json").read_text())
    assert set(meta["tagesdatastreams"]) == {"kfz", "sv"}
    meta["abgerufen"] = "2026-10-29T00:00:00Z"  # frisch_tage 1: Tage bis 27.10. (Ortszeit)
    (pfade.roh / "hamburg_kfz" / "stellen.json").write_text(json.dumps(meta))
    bericht = hh.Bericht()
    r = hh.lese(Q_TAG, pfade, bericht)
    assert [s.kennung for s in r.stellen] == ["0248931", "0249912"]
    assert r.stellen[1].fahrstreifen == ["Zählfeld 1472-Z.7"] and r.stellen[1].lat == 53.61
    assert set(r.tageswerte) == {"kfz", "sv"} and r.von == date(2026, 10, 1)
    summe, n = tagessummen(r, "kfz")
    tw = aus_tageswerten(r, "kfz")
    i = r.index
    # Stelle A: Tageswerte bis zum Tag vor der ersten Stunde, dann allein die Stunden
    assert summe[0, i(date(2026, 10, 21))] == 1021 and tw[0, i(date(2026, 10, 21))]
    assert n[0, i(date(2026, 10, 21))] == 0
    assert summe[0, i(date(2026, 10, 24))] == 2400 and not tw[0, i(date(2026, 10, 24))]
    assert summe[0, i(date(2026, 10, 26))] == -1  # nie mit dem Tageswert 1026 gefüllt
    assert summe[0, i(date(2026, 10, 19))] == -1  # vor dem ersten Tageswert
    # Schwerverkehr: Tageswerte 22. und 23.10., ab 24.10. Stunden
    sv = tagessummen(r, "sv")[0]
    assert sv[0, i(date(2026, 10, 23))] == 50 and sv[0, i(date(2026, 10, 24))] == 72
    # Stelle C nur mit Tageswerten, auch am Tag der Rückstellung (25 Stunden)
    assert summe[1, i(date(2026, 10, 25))] == 2025 and tw[1, i(date(2026, 10, 25))]
    assert summe[1, i(date(2026, 10, 26))] == -1
    # Der Tageswert von A für den 28.10. ist zu frisch (frisch_tage), die Reihe endet am 27.10.
    assert r.tag(r.tage - 1) == date(2026, 10, 27)
    assert bericht.tage == {"kfz": 8 + 25, "sv": 2} and bericht.tage_frisch == 1
    assert bericht.tageswerte == {"kfz": 4 + 25, "sv": 2}
    assert any("Tageswerte der Quelle: kfz: 2 Datastreams, sv: 1 Datastreams" in z
               for z in bericht.zeilen())
    # Verfahren: bis zum letzten Tag mit einem Tageswert in der Karte beide, danach Stunden
    (v1, b1, t1), (v2, b2, t2) = r.verfahren
    assert (v1, b1, v2, b2) == (date(2026, 10, 1), date(2026, 10, 25), date(2026, 10, 26),
                                date(2026, 10, 27))
    assert "Tageswerte der Quelle" in t1 and "Stundenwerte" in t1
    assert t2.startswith("Stundenwerte") and "Tageswert" not in t2

    # zweiter Lauf: Tage ab dem jüngsten Tag im Gedächtnis minus nachladen_tage (2), neue Stelle
    # ganz
    api.abrufe.clear()
    d = thing("0249921", 10.02, 53.62, "Süd nach Nord", "Süd")
    api.ds.append({"id": 14, "layer": "Kfz_1-Tag", "thing": d, "props": {},
                   "obs": ortstage(date(2026, 9, 1), 5)})
    api.ds[2]["obs"] = [(z, 1100 if z.startswith("2026-10-26T23") else w)  # 27.10. korrigiert
                        for z, w in api.ds[2]["obs"]]
    hh.hole(Q_TAG, pfade)
    tage_urls = [urllib.parse.unquote(u) for u in api.abrufe if "1-Tag" in urllib.parse.unquote(u)]
    assert any("phenomenonTime ge 2026-10-25T23:00:00Z" in u for u in tage_urls)  # 26.10. 0 Uhr
    tg = hh.lies_tage(pfade.roh / "hamburg_kfz" / "gedaechtnis")
    assert tg[("0249921", "kfz", "2026-09")][:5] == [1000] * 5
    assert tg[("0248931", "kfz", "2026-10")][26] == 1100
    assert tg[("0248931", "kfz", "2026-10")][19] == 1020  # Altes bleibt


def test_site_mit_tageswerten(api, pfade):
    a = thing("0248931", 10.0, 53.6, "Nordost nach Südwest", "Nordost")
    api.ds = [{"id": 1, "layer": "Kfz_1-Stunde", "thing": a, "props": {},
               "obs": stunden(utc(2026, 11, 1, 23), 2 * 24, lambda t: 10)},
              {"id": 11, "layer": "Kfz_1-Tag", "thing": a, "props": {},
               "obs": ortstage(date(2026, 10, 30), 3, lambda t: 300)}]
    hh.hole(Q_TAG, pfade)
    meta = json.loads((pfade.roh / "hamburg_kfz" / "stellen.json").read_text())
    meta["abgerufen"] = "2026-11-10T00:00:00Z"
    (pfade.roh / "hamburg_kfz" / "stellen.json").write_text(json.dumps(meta))
    r = hh.lese(Q_TAG, pfade, hh.Bericht())
    site.schreibe([(Q_TAG, r)], pfade, date(2026, 11, 12))
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    q = index["quellen"][0]
    assert q["tageswerte"] == {"kfz": ["2026-10-30", "2026-11-01"]}
    assert q["zeitraeume"] == {"kfz": ["2026-10-30", "2026-11-03"]}
    assert index["tageswerte_bis"] == {"kfz": ["2026-11-01"]}
    d = json.loads((pfade.karte / "dauer" / "0.json").read_text())["stellen"]["hamburg_kfz:0248931"]
    # 30.10.–1.11. Tageswerte der Quelle, 2. und 3.11. die Summe der Stunden
    assert d["tage"]["kfz"] == [300, 300, 300, 240, 240] and d["n"]["kfz"] == [0, 0, 0, 24, 24]
    assert d["tageswerte_bis"] == {"kfz": "2026-11-01"}
    assert [v["text"][:8] for v in q["verfahren"]] == ["Vor der ", "Stundenw"]
