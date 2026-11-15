"""Bayern, Dauerzählstellen (BAYSIS, dauer/baysis_dauz.py): Liste und Lage aus der ArcGIS-Operation
`find` (Aliasnamen, Punkt in WGS84), Stundenzeilen im Format der Schnittstelle (je Feld
`{"wert": …}`, Stunde 01–24 als Ende der Stunde, Prüfkennzeichen je Wert), Zeitumstellung,
Auswahl der Straßenklassen, Monatsblöcke, das höfliche Abrufen (Pause, Ablehnungen, Zeitbudget) und
der Plan der Läufe (Probe, neue Zählstellen, Nachladen nach einer Veröffentlichung, Lücken,
Sicherheitsnetz)."""

from __future__ import annotations

import gzip
import json
from datetime import UTC, date, datetime

import pytest
import requests

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import baysis_dauz as bd
from zaehlkarte.dauer.modell import tagessummen

Q = {"code": "bayern_dauz", "land": "BY", "strassenklassen": ["St", "K"], "ab": "2025-10",
     "api": "https://baysis.example/services/apiDAUZ/api/DAUZ",
     "liste": "https://gis.example/MapServer/find?searchText={klasse}&layers=0&f=json"}

STELLEN = [  # Nummer, Straße, Klasse, Status, Punkt
    ("9639", "St 2406", "St", "aktiv (in Betrieb)", (11.09968808647594, 49.37051641134266)),
    ("9648", "K M 15", "K", "aktiv (in Betrieb)", (11.4201, 48.1102)),
    ("9700", "St 2544", "St", "inaktiv (außer Betrieb)", (11.431, 48.105)),
    ("9701", "St 2063", "St", "aktiv (in Betrieb)", None),
    ("9999", "St 1", "St", "geplant", (11.0, 48.0)),
    ("9175", "B 12", "B", "aktiv (in Betrieb)", (12.0, 48.5)),
]


def _liste(klasse: str, nummern=None) -> dict:
    """Antwort der Operation `find` (Attribute unter Aliasnamen, „Station“ mit Zeilenumbruch)."""
    return {"results": [
        {"layerId": 0, "layerName": "dauerzaehlstellen", "foundFieldName": "Straßenklasse",
         "value": k, "attributes": {"OBJECTID": "7", "Straßenbezeichnung": s,
                                    "Abschnittsnummer": "180", "Station\n": "0,419",
                                    "Zählstellennummer": nr, "Straßenklasse": k, "Status": st},
         "geometryType": "esriGeometryPoint",
         **({"geometry": {"x": p[0], "y": p[1], "spatialReference": {"wkid": 4326}}} if p else {})}
        for nr, s, k, st, p in STELLEN if k == klasse and (nummern is None or nr in nummern)]}


def _w(x):
    return {"spaltenname": "x", "bezeichnung": "x", "wert": x}


def _zeile(tag: date, stunde: int, k1, k2, l1, l2, kenn=("-", "-", "-", "-")):
    return {"datum": _w(tag.strftime("%d.%m.%Y")), "wochentag": _w("Mo"),
            "stunde": _w(f"{stunde:02d}"), "kfzKennR1": _w(kenn[0]), "kfzKennR2": _w(kenn[1]),
            "lkwKennR1": _w(kenn[2]), "lkwKennR2": _w(kenn[3]),
            "kfZ_GQ": _w(str(k1 + k2)), "lkW_GQ": _w(str(l1 + l2)),
            "kfZ_R1": _w(str(k1)), "kfZ_R2": _w(str(k2)), "lkW_R1": _w(str(l1)),
            "lkW_R2": _w(str(l2))}


def _tag(tag: date, **aenderung):
    """24 Zeilen eines Tages (10/20 Kfz, 1/2 Lkw je Stunde); `aenderung`: Stunde -> Kennzeichen."""
    return [_zeile(tag, h, 10, 20, 1, 2, aenderung.get(f"h{h}", ("-", "-", "-", "-")))
            for h in range(1, 25)]


def _stamm(nr, strasse, name, hin, gegen, klassen="8+1"):
    return [{"zaehlstelle": _w(nr), "zaehlstellenbezeichnug": _w(name), "strasse": _w(strasse),
             "abschnitt": _w("180"), "station": _w("0,419"), "inRichtung": _w(hin),
             "gegenRichtung": _w(gegen), "lkW_Unterscheidung": _w(klassen)}]


def test_stellen_der_liste():
    listen = [_liste("St"), _liste("K"), _liste("B")]
    st = bd._stellen_der_liste(Q, listen)
    # ohne Bundesstraße (B 12) und ohne „geplant“ (9999); die Lage aus der Geometrie
    assert [s["nr"] for s in st] == ["9639", "9648", "9700", "9701"]
    assert (st[0]["strasse"], st[0]["lon"], st[0]["lat"]) == ("St 2406", 11.09968808647594,
                                                              49.37051641134266)
    assert st[3]["lon"] is None
    assert [s["nr"] for s in bd._stellen_der_liste({"strassenklassen": ["K"]}, listen)] == ["9648"]


def test_bloecke_und_monate():
    assert bd.monate("2025-11", date(2026, 2, 3)) == ["2025-11", "2025-12", "2026-01", "2026-02"]
    ms = bd.monate("2023-01", date(2024, 2, 1))
    assert bd.bloecke(ms) == [("2024-01", "2024-02"), ("2023-01", "2023-12")]
    assert bd.bloecke(["2025-01", "2025-03", "2025-04"]) == [("2025-03", "2025-04"),
                                                             ("2025-01", "2025-01")]
    assert bd.bloecke([]) == []


def test_start_der_frage():
    q = {"block_monate": 3}
    ziel = bd.monate("2026-01", date(2026, 11, 15))
    assert bd.start_der_frage(q, ziel, None) == "2026-09"  # ohne Zeilen: die jüngsten drei
    assert bd.start_der_frage(q, ziel, date(2026, 9, 30)) == "2026-10"  # Monat zu Ende
    assert bd.start_der_frage(q, ziel, date(2026, 10, 12)) == "2026-10"  # Monat nicht zu Ende
    assert bd.start_der_frage(q, ziel, date(2025, 5, 31)) == "2026-09"  # höchstens drei Monate
    assert bd.start_der_frage(q, ziel, date(2026, 11, 30)) == "2026-12"  # nichts zu fragen


def test_zeilen_je_monat():
    z = _tag(date(2025, 10, 31))[:2] + _tag(date(2025, 11, 1))[:1]
    je = bd.zeilen_je_monat(z)
    assert {k: len(v) for k, v in je.items()} == {"2025-10": 2, "2025-11": 1}


def test_abrufer_wiederholt_und_bricht_ab(monkeypatch):
    schlaf: list[float] = []
    antworten = iter([requests.ConnectionError("abgelehnt"), "ok", requests.ConnectionError("x"),
                      requests.ConnectionError("x"), requests.ConnectionError("x")])

    class Antwort:
        def json(self):
            return {"ok": True}

    def hole(url, **kw):
        a = next(antworten)
        if isinstance(a, Exception):
            raise a
        return Antwort()

    import zaehlkarte.abruf
    monkeypatch.setattr(zaehlkarte.abruf, "hole", hole)
    a = bd.Abrufer({**Q, "pause": 7, "abbruch": 3, "budget_minuten": 60}, schlafe=schlaf.append)
    assert a.json(Q["api"], {"zaehlstellennummer": "9639"}) == {"ok": True}
    assert schlaf == [60, 7]  # erst eine Minute nach der Ablehnung, dann die Pause
    with pytest.raises(bd.Abbruch, match="3 Ablehnungen"):
        a.json(Q["api"], {"zaehlstellennummer": "9639"})
    assert (a.anfragen, a.ablehnungen) == (1, 4)
    uhr = iter([0.0, 10_000.0])
    b = bd.Abrufer({**Q, "budget_minuten": 1}, schlafe=schlaf.append, uhr=lambda: next(uhr))
    with pytest.raises(bd.Abbruch, match="Zeitbudget"):
        b.json(Q["api"], {})


def _pfade(tmp_path, werte: dict[str, dict[str, list]], stamm: dict) -> Pfade:
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    o = pfade.roh / "bayern_dauz"
    (o / "stamm").mkdir(parents=True)
    for k in ("St", "K"):
        (o / f"liste_{k}.json").write_text(json.dumps(_liste(k)))
    for nr, d in stamm.items():
        (o / "stamm" / f"{nr}.json").write_text(json.dumps(d))
    for nr, monate in werte.items():
        (o / "werte" / nr).mkdir(parents=True)
        for m, zeilen in monate.items():
            with gzip.open(o / "werte" / nr / f"{m}.json.gz", "wt") as f:
                json.dump(zeilen, f)
    return pfade


def test_lese(tmp_path):
    rueck = date(2025, 10, 26)  # Rückstellung der Uhr: 2–3 Uhr nur einmal, mit „z“
    werte = {"9639": {
        "2025-10": _tag(date(2025, 10, 24)) + _tag(date(2025, 10, 25), h9=("k", "-", "-", "a"))
        + _tag(rueck, h3=("z", "z", "z", "z")),
        "2025-11": []}}  # ein Monat ohne Zeilen
    stamm = {"9639": _stamm("9639", "St 2406", "Nürnberg-Worzeldorf", "Worzeldorf", "Kornburg"),
             "9648": _stamm("9648", "K M 15", "Planegg-Martinsried", "Großhadern", "Gräfelfing",
                            klassen="5+1"),
             "9701": _stamm("9701", "St 2063", "Irgendwo", "A", "B")}
    bericht = bd.Bericht()
    reihe = bd.lese(Q, _pfade(tmp_path, werte, stamm), bericht)
    assert [s.id for s in reihe.stellen] == ["bayern_dauz:9639-1", "bayern_dauz:9639-2",
                                            "bayern_dauz:9648-1", "bayern_dauz:9648-2"]
    s1 = reihe.stellen[0]
    assert (s1.name, s1.richtung) == ("St 2406 Nürnberg-Worzeldorf", "Richtung Worzeldorf")
    assert (s1.lon, s1.lat) == (11.099688, 49.370516)
    assert reihe.stellen[3].richtung == "Richtung Gräfelfing"
    assert set(reihe.werte) == {"kfz", "sv"}  # 9648 (lkw, nicht 8+1) ohne Werte: weg
    assert (reihe.von, reihe.tag(reihe.tage - 1)) == (date(2025, 10, 24), rueck)
    kfz, _ = tagessummen(reihe, "kfz")
    sv, _ = tagessummen(reihe, "sv")
    # 24.10. vollständig; 25.10.: Kfz R1 um 8–9 Uhr Schätzwert -> nicht vollständig, R2 voll;
    # SV R2 um 8–9 Uhr Ausfall; 26.10.: 2–3 Uhr mit „z“ -> nicht vollständig
    assert kfz[0].tolist() == [240, -1, -1] and kfz[1].tolist() == [480, 480, -1]
    assert sv[0].tolist() == [24, 24, -1] and sv[1].tolist() == [48, -1, -1]
    assert bericht.ohne_werte == ["K M 15 9648"]
    assert bericht.ohne_stamm == ["9700 (St 2544)"]
    assert bericht.ohne_lage == ["St 2063 Irgendwo (9701)"]
    assert bericht.kennzeichen["z"] == 4 and bericht.kennzeichen["k"] == 1
    assert bericht.lkw_klassen == {"8+1": 1, "5+1": 1}
    assert any("2 Zählstellen, 4 Richtungen" in z for z in bericht.zeilen())


def test_lese_sommerzeit(tmp_path):
    """Frühjahr: die Zeile 03 (2–3 Uhr) gibt es nicht – verworfen, der Tag hat 23 Stunden."""
    tag = date(2025, 3, 30)
    werte = {"9639": {"2025-03": _tag(tag, h3=("z", "z", "z", "z"))}}
    stamm = {"9639": _stamm("9639", "St 2406", "Worzeldorf", "A", "B")}
    bericht = bd.Bericht()
    reihe = bd.lese({**Q, "ab": "2025-03"}, _pfade(tmp_path, werte, stamm), bericht)
    kfz, n = tagessummen(reihe, "kfz")
    assert kfz[0].tolist() == [230] and n[0].tolist() == [23]
    assert bericht.sommerzeit == 4


class Server:
    """BAYSIS zum Testen: die Listen, Stammdaten und Stundenzeilen (am 1. und 15. jedes Monats
    und am jüngsten Tag) bis `stand[nr]`; merkt sich die Fragen."""

    def __init__(self, stand: dict, abbruch_nach: int | None = None):
        self.stand, self.abbruch_nach = stand, abbruch_nach
        self.fragen: list[tuple] = []
        self.anfragen = self.ablehnungen = 0

    def json(self, url, nutzlast=None, timeout=300):
        if self.abbruch_nach is not None and self.anfragen >= self.abbruch_nach:
            raise bd.Abbruch("Zeitbudget aufgebraucht")
        self.anfragen += 1
        if nutzlast is None:
            k = url.split("searchText=")[1].split("&")[0]
            self.fragen.append(("liste", k))
            return _liste(k, set(self.stand))
        nr = nutzlast["zaehlstellennummer"]
        if nutzlast["abfrageArt"] == "stammdaten":
            self.fragen.append(("stamm", nr))
            return _stamm(nr, "St 1", f"Ort {nr}", "A", "B")
        von = date.fromisoformat(nutzlast["vonDatum"])
        bis = date.fromisoformat(nutzlast["bisDatum"])
        self.fragen.append((nr, nutzlast["vonDatum"][:7], nutzlast["bisDatum"][:7]))
        ende = self.stand[nr]
        if ende is None:
            return []
        tage = sorted({date(int(m[:4]), int(m[5:]), t) for m in bd.monate(von.isoformat(), bis)
                       for t in (1, 15)} | {ende})
        return [z for t in tage if von <= t <= min(bis, ende) for z in _tag(t)]


def test_hole_plan(tmp_path):
    q = {**Q, "ab": "2026-05", "block_monate": 3, "rueckstand_tage": 14, "nachladen_tage": 35,
         "stamm_tage": 91}
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    o = pfade.roh / "bayern_dauz"
    stand = {"9639": date(2026, 9, 30), "9648": date(2026, 9, 30), "9700": None}

    def lauf(jetzt: datetime) -> list[tuple]:
        server = Server(stand)
        log = bd.hole(q, pfade, abrufer=server, jetzt=jetzt)
        assert "vollständig" in log[0]
        return server.fragen[2:]  # ohne die beiden Listen

    # 1. Lauf: alle neu – Stammdaten und die jüngsten drei Monate, dann die Lücken davor
    assert lauf(datetime(2026, 11, 15, 6, tzinfo=UTC)) == [
        ("stamm", "9639"), ("9639", "2026-09", "2026-11"),
        ("stamm", "9648"), ("9648", "2026-09", "2026-11"),
        ("stamm", "9700"), ("9700", "2026-09", "2026-11"),
        ("9639", "2026-08", "2026-08"), ("9648", "2026-08", "2026-08"),
        ("9700", "2026-08", "2026-08"), ("9639", "2026-05", "2026-07"),
        ("9648", "2026-05", "2026-07"), ("9700", "2026-05", "2026-07")]
    st = json.loads((o / "stand.json").read_text())
    assert (st["neuester_tag"], st["seit"]) == ("2026-09-30", "2026-11-15T06:00:00Z")
    a = json.loads((o / "abruf.json").read_text())
    assert (a["neu"], a["luecken"], a["offene_abschnitte"], a["anfragen"]) == (3, 6, 0, 14)
    assert sorted(p.name for p in (o / "werte" / "9639").iterdir())[0] == "2026-05.json.gz"
    # 2. Lauf, nichts Neues: nur die Probe
    assert lauf(datetime(2026, 11, 22, 6, tzinfo=UTC)) == [("9639", "2026-10", "2026-11")]
    # 3. Lauf, BAYSIS hat den Oktober: die Probe (am längsten nicht gefragt) findet ihn, dann
    # alle, die zurückliegen – auch die Zählstelle ohne Zeilen, einmal
    stand.update({"9639": date(2026, 10, 31), "9648": date(2026, 10, 31)})
    assert lauf(datetime(2026, 12, 15, 6, tzinfo=UTC)) == [
        ("9648", "2026-10", "2026-12"), ("9700", "2026-10", "2026-12"),
        ("9639", "2026-10", "2026-12")]
    assert json.loads((o / "stand.json").read_text())["neuester_tag"] == "2026-10-31"
    # 4. Lauf, nichts Neues: wieder nur die Probe, die Zählstelle ohne Zeilen nicht
    assert lauf(datetime(2026, 12, 22, 6, tzinfo=UTC)) == [("9639", "2026-11", "2026-12")]
    # 5. Lauf nach fünf Wochen ohne Neues: Probe, dann das Sicherheitsnetz
    assert lauf(datetime(2027, 2, 1, 6, tzinfo=UTC)) == [
        ("9648", "2026-12", "2027-02"), ("9700", "2026-12", "2027-02"),
        ("9639", "2026-12", "2027-02")]


def test_hole_abbruch_und_weiter(tmp_path):
    q = {**Q, "ab": "2026-09", "block_monate": 3}
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    o = pfade.roh / "bayern_dauz"
    stand = {"9639": date(2026, 9, 30), "9648": date(2026, 9, 30)}
    jetzt = datetime(2026, 11, 15, 6, tzinfo=UTC)
    server = Server(stand, abbruch_nach=5)
    log = bd.hole(q, pfade, abrufer=server, jetzt=jetzt)
    assert "abgebrochen" in log[0]
    assert server.fragen[2:] == [("stamm", "9639"), ("9639", "2026-09", "2026-11"),
                                 ("stamm", "9648")]
    assert json.loads((o / "abruf.json").read_text())["status"].startswith("abgebrochen")
    assert set(json.loads((o / "stand.json").read_text())["gefragt"]) == {"9639"}
    server = Server(stand)  # der nächste Lauf: die Probe, dann 9648 ohne neue Stammdaten
    bd.hole(q, pfade, abrufer=server, jetzt=datetime(2026, 11, 22, 6, tzinfo=UTC))
    assert server.fragen[2:] == [("9639", "2026-10", "2026-11"), ("9648", "2026-09", "2026-11")]
