from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from zaehlkarte.adapters import olpe_radar as o
from zaehlkarte.config import Pfade

DL = "http://dcat-ap.de/def/licenses/dl-by-de/2.0"
QUELLE = {
    "code": "olpe", "land": "NW",
    "lieferungen": [{"code": "dl-de-by", "lizenz_id": DL}],
    "orte": {"tabelle.json": {"name": "Zum Honigsack 35", "lon": 7.85, "lat": 51.0}},
}


def _geraet(fahrzeuge: list[tuple[str, int]], punkte: list[tuple[str, float, float]],
            von: str = "2025-06-20T10:00:00Z") -> dict:
    return {"header": {"count_vehicles": len(fahrzeuge)},
            "request": {"devicenr": 8326, "from": von, "to": "2025-06-21T10:00:00Z"},
            "data": [{"devicenr": 8326,
                      "measurement_data": [{"lat": lat, "lon": lon, "end_date": ende,
                                            "start_date": "2025-06-20 07:44:00Z"}
                                           for ende, lon, lat in punkte],
                      "vehicle_data": [{"date": t, "direction": 1, "lane": 0, "code": c,
                                        "length": 40, "v1": 30} for t, c in fahrzeuge]}]}


def test_utc_wird_ortszeit():
    assert o._utc("2025-06-20 10:00:05") == datetime(2025, 6, 20, 12, 0, 5)  # Sommerzeit
    assert o._utc("2025-11-12T09:53:43.736Z") == datetime(2025, 11, 12, 10, 53, 43, 736000)


def test_geraet_lage_nur_aus_der_zeit_der_fahrzeuge():
    d = _geraet([("2025-06-20 10:00:05", 7), ("2025-06-20 12:30:00", 7)],
                [("2025-06-20 21:59:59Z", 7.85, 51.03),  # Tag der Messung
                 ("2025-06-21 21:59:59Z", 7.85, 51.03),
                 ("2025-06-25 21:59:59Z", 7.94, 51.07)])  # Gerät schon an der nächsten Stelle
    m = o.lese_geraet(d)
    assert m.lage == (7.85, 51.03)
    assert m.beginn == datetime(2025, 6, 20, 12, 0)  # Exportfenster ab 10 Uhr UTC
    assert m.geraet == 8326


def test_stunden_klassen_und_volle_stunden():
    d = _geraet([("2025-06-20 10:00:05", 7), ("2025-06-20 10:20:00", 3),
                 ("2025-06-20 10:40:00", 230), ("2025-06-20 11:10:00", 250),
                 ("2025-06-20 12:05:00", 7)], [])
    r = o.stunden(o.lese_geraet(d))
    # 12–13 Uhr Ortszeit: Pkw + Lkw (Kfz 2, davon SV 1) + Rad 1; 13–14 Uhr: Klasse 250 = Kfz;
    # die angefangene Stunde ab 14 Uhr zählt nicht
    assert r == {datetime(2025, 6, 20, 12): (2, 1, 1), datetime(2025, 6, 20, 13): (1, 0, 0)}


def test_luecke_nur_wo_verkehr_zu_erwarten_waere():
    reihe = {}
    start = datetime(2025, 6, 23)  # Montag
    for tag in range(3):
        for h in range(24):
            t = start + timedelta(days=tag, hours=h)
            reihe[t] = (20 if 6 <= h <= 20 else 0, 0, 0)  # nachts leer: echte Nullen
    for h in (9, 10, 11):  # Mittwoch 9–12 Uhr ohne Fahrzeug: Ausfall
        reihe[datetime(2025, 6, 25, h)] = (0, 0, 0)
    assert o.luecken(reihe) == [(datetime(2025, 6, 25, 9), datetime(2025, 6, 25, 11))]


def test_spannen():
    assert o.spannen([9, 10, 11, 15]) == ["9–12 Uhr", "15–16 Uhr"]
    assert o.spannen([23]) == ["23–24 Uhr"] and o.spannen([]) == []


def test_ausfall_als_spanne_ganzer_tag_ohne_zaehlung():
    # Mo, Mi, Do je 10 Fahrzeuge in der Stunde; Di gar keins, Mi 9–12 Uhr keins
    zeilen = [{"Datum": f"{tag}.06.2025 {h:02d}:{mi:02d}:00", "Richtung": 1, "Klasse": 7}
              for tag in (23, 25, 26) for h in range(24) for mi in range(0, 60, 6)
              if not (tag == 25 and 9 <= h < 12)]
    zeilen.append({"Datum": "27.06.2025 00:05:00", "Richtung": 1, "Klasse": 7})
    b = o.Bericht()
    zs = list(o._zaehlungen(QUELLE, {"title": "Verkehrsmessung Teststraße"}, {"name": "Messung"},
                            "test.json", o.lese_tabelle(zeilen), {}, "dl-de-by", b))
    assert [z.datum.day for z in zs] == [23, 25, 26]  # Dienstag ganz im Ausfall: keine Zählung
    mittwoch = zs[1]
    assert mittwoch.stunden["kfz"][8:13] == [10, None, None, None, 10]
    assert any(h.startswith("Ohne Daten (9–12 Uhr)") for h in mittwoch.hinweise)
    assert b.luecken == ["test.json: 24.06. 00 bis 24 Uhr", "test.json: 25.06. 09 bis 12 Uhr"]


def test_umstellung_auf_sommerzeit():
    assert not o.gibt_es(datetime(2026, 3, 29, 2))
    assert o.gibt_es(datetime(2026, 3, 29, 3))


def test_hole_ersetzt_den_alten_abruf(tmp_path, monkeypatch):
    from zaehlkarte import fetch

    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    q = {**QUELLE, "adapter": "olpe_radar", "api_suche": "https://example.org/suche",
         "paket_muster": "^verkehrsmess"}
    pakete = [
        {"name": "verkehrsmessung-standort-zum-honigsack-35", "license_id": DL,
         "title": "Verkehrsmessung Standort „Zum Honigsack 35“",
         "resources": [{"url": "https://example.org/Zum%20Honigsack%2035.json"},
                       {"url": "https://example.org/Zum%20Honigsack%2035.csv"}]},
        {"name": "parkplaetze", "resources": [{"url": "https://example.org/p.json"}]},
    ]

    class Antwort:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"results": pakete}}

    geladen = []

    def lade(url, ziel):
        geladen.append(url)
        ziel.write_text("[]", encoding="utf-8")
        return ziel

    monkeypatch.setattr(fetch, "quellen", lambda pfade: {"olpe": q})
    monkeypatch.setattr(fetch.requests, "get", lambda url, **kw: Antwort())
    monkeypatch.setattr(fetch, "lade", lade)
    alt = pfade.roh / "olpe" / "verkehrsmessungen-alt"
    alt.mkdir(parents=True)
    assert fetch.hole(pfade, ["olpe"]) == ["olpe: 1 Datensätze, 1 Messungen"]
    ordner = pfade.roh / "olpe" / "verkehrsmessung-standort-zum-honigsack-35"
    assert (ordner / "Zum Honigsack 35.json").exists()  # Name wie in `orte`
    paket = json.loads((ordner / "paket.json").read_text(encoding="utf-8"))
    assert paket["license_id"] == DL and paket["title"].endswith("35“")
    assert not alt.exists() and geladen == ["https://example.org/Zum%20Honigsack%2035.json"]


def test_lese(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    for name, lizenz, datei, inhalt in (
        ("verkehrsmessungen-rochusstrabe", DL, "geraet.json",
         _geraet([(f"2025-06-20 {h:02d}:30:00", 7) for h in range(10, 16)],
                 [("2025-06-20 21:59:59Z", 7.85, 51.03)])),
        ("verkehrsmessung-standort-zum-honigsack-35", DL, "tabelle.json",
         [{"Datum": f"25.03.2026 {h:02d}:10:00", "Richtung": 1, "Klasse": 9,
           "Fahrzeugklassen-Bezeichnung": "Sattel-Kfz"} for h in range(8, 12)]),
        ("verkehrsmessungen-fremd", "http://dcat-ap.de/def/licenses/other-closed", "fremd.json",
         _geraet([("2025-06-20 10:00:05", 7)], [])),
    ):
        ordner = pfade.roh / "olpe" / name
        ordner.mkdir(parents=True)
        (ordner / datei).write_text(json.dumps(inhalt), encoding="utf-8")
        titel = "Verkehrsmessungen Rochusstraße" if "rochus" in name else "Verkehrsmessung"
        (ordner / "paket.json").write_text(json.dumps({
            "name": name, "title": titel, "license_id": lizenz,
            "resources": [{"name": "Messung", "url": f"https://example.org/{datei}"}]}),
            encoding="utf-8")
    b = o.Bericht()
    zs = sorted(o.lese(QUELLE, pfade, b), key=lambda z: z.kennung)
    assert len(b.lizenz_fremd) == 1 and b.dateien == 2
    rochus, honig = zs[0], zs[1]
    assert (honig.name, honig.lage, honig.lon) == ("Zum Honigsack 35", "geokodiert", 7.85)
    assert honig.datum == date(2026, 3, 25)
    assert honig.h0 == 9 and honig.stunden["kfz"] == [1, 1] and honig.stunden["sv"] == [1, 1]
    assert (rochus.name, rochus.lage, rochus.typ) == ("Rochusstraße", "gps", "Q")
    assert rochus.lieferung == "dl-de-by"
    assert rochus.h0 == 12 and rochus.stunden["kfz"] == [1, 1, 1, 1, 1]
    assert rochus.stunden["rad"] == [0, 0, 0, 0, 0] and rochus.fenster == [(12 * 60, 17 * 60)]
