"""VMZ Niedersachsen (dauer/vmz_rad.py) mit synthetischen Dateien im Aufbau der Quelle: Seite der
Zählstellenübersicht mit eingebettetem Startzustand, Stundenwerte der Zählerabfrage (wie von `hole`
abgelegt), Störungen."""

import json
from datetime import date

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import vmz_rad
from zaehlkarte.dauer.modell import tagessummen

Q = {"code": "vmz_rad", "land": "NI", "rueck": "einfach"}


def _seite(features: list[dict]) -> str:
    """Wie die Seite: Zustand als JSON in einer JavaScript-Zeichenkette (\\/ und \\u00e4)."""
    zustand = {"reHydratedState": {"featureSources": {"niedersachsen-radzaehler": {
        "url": "/geojson/niedersachsen-radzaehler.geojson",
        "data": {"type": "FeatureCollection", "features": features}}}}}
    text = json.dumps(zustand).replace("/", "\\/").replace("\\", "\\\\").replace("'", "\\'")
    return f"<script>var options = JSON.parse('{text}');\n</script>"


def _f(kennung: str, name: str, gruppe: str, lon: float, lat: float) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"externalId": kennung, "name": name, "group": gruppe,
                           "source": "LHH"}}


def test_zaehlstellen_aus_der_seite():
    html = _seite([_f("100030021", "Lister Meile, LHH", "70_Stadt Hannover", 9.746, 52.384),
                   _f("100030021", "Lister Meile, LHH", "70_Stadt Hannover", 9.746, 52.384),
                   _f("300047417", "B 210, Hinte, LK Aurich", "20_Nordwest", 7.21, 53.40),
                   _f("NeoCount1870", "Oldendorp, Gemeinde Jemgum", "zzz_Gemeinde Jemgum",
                      7.29, 53.32)])
    stellen = vmz_rad.zaehlstellen(html)
    assert [s["kennung"] for s in stellen] == ["100030021", "300047417", "NeoCount1870"]
    assert stellen[0]["lat"] == 52.384 and stellen[0]["gruppe"] == "70_Stadt Hannover"
    assert vmz_rad.name_und_abschnitt("B 210, Hinte, LK Aurich", "20_Nordwest") == (
        "B 210", "Hinte, LK Aurich")
    assert vmz_rad.name_und_abschnitt("Lister Meile, LHH", "70_Stadt Hannover") == (
        "Lister Meile", "Hannover")
    assert vmz_rad.name_und_abschnitt("Oldendorp, Gemeinde Jemgum", "zzz_Gemeinde Jemgum") == (
        "Oldendorp", "Jemgum")
    assert vmz_rad.name_und_abschnitt("B 217, Ronnenberg, Region Hannover",
                                      "60_Region Hannover") == ("B 217", "Ronnenberg")
    assert vmz_rad.name_und_abschnitt("Stadt Rotenburg (Wümme)", "zzz_Stadt Rotenburg (Wümme)") == (
        "Rotenburg (Wümme)", None)
    assert vmz_rad.name_und_abschnitt("K 117 OD Großburgwedel", "60_Region Hannover") == (
        "K 117 OD Großburgwedel", "Region Hannover")


def _werte(zeilen: list[tuple[str, str]]) -> str:
    """Abgelegt wie von `hole`: [[Zeit, Wert], …] (Wert als Text wie in der Antwort)."""
    return json.dumps([[t, w] for t, w in zeilen])


def test_lese(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = tmp_path / "data" / "raw" / "vmz_rad"
    (ordner / "werte").mkdir(parents=True)
    (ordner / "stellen.json").write_text(json.dumps({"stellen": [
        {"kennung": "100030021", "name": "Lister Meile, LHH", "gruppe": "70_Stadt Hannover",
         "quelle": "LHH", "lon": 9.746, "lat": 52.384},
        {"kennung": "300026962", "name": "Bültenweg, Stadt Braunschweig",
         "gruppe": "zzz_Stadt Braunschweig", "quelle": "NLSTBV", "lon": 10.53, "lat": 52.27},
    ]}))
    # 3.6.2025 voll (24 Stunden), 4.6. ohne 7 Uhr (leer), 5.6. laut Störung fehlend
    voll = [(f"2025-06-0{t} {h:02d}:00:00", "10") for t in (3, 5) for h in range(24)]
    luecke = [(f"2025-06-04 {h:02d}:00:00", None if h == 7 else "10") for h in range(24)]
    (ordner / "werte" / "100030021_2025.json").write_text(_werte(sorted(voll + luecke)))
    # Sommerzeit 30.3.2025: 2 Uhr fehlt -> 23 Stunden, voll; Rückstellung 26.10.: 2 Uhr einmal
    sommer = [(f"2025-03-30 {h:02d}:00:00", "1") for h in range(24) if h != 2]
    rueck = [(f"2025-10-26 {h:02d}:00:00", "1") for h in range(24)]
    (ordner / "werte" / "300026962_2025.json").write_text(_werte(sommer + rueck))
    stoerung = {"type": "missing_data", "station_id": "100030021",
                "start_datetime": "2025-06-05 00:00:00", "end_datetime": "2025-06-05 23:59:59"}
    (ordner / "stoerungen_2025.json").write_text(json.dumps([stoerung]))
    (ordner / "stoerungen_2026.json").write_text(json.dumps([stoerung]))  # Überlappung: einmal

    bericht = vmz_rad.Bericht()
    reihe = vmz_rad.lese(Q, pfade, bericht)
    assert [s.name for s in reihe.stellen] == ["Lister Meile", "Bültenweg"]
    assert [s.abschnitt for s in reihe.stellen] == ["Hannover", "Braunschweig"]
    assert reihe.stellen[0].id == "vmz_rad:100030021"
    summen, _ = tagessummen(reihe, "rad")
    i = reihe.index
    assert summen[0, i(date(2025, 6, 3))] == 240
    assert summen[0, i(date(2025, 6, 4))] < 0  # 7 Uhr fehlt: nicht vollständig gezählt
    assert summen[0, i(date(2025, 6, 5))] < 0  # Störung der Quelle: nicht gezählt
    assert summen[1, i(date(2025, 3, 30))] == 23  # Sommerzeit: 23 Stunden
    assert summen[1, i(date(2025, 10, 26))] < 0  # Rückstellung: 2 Uhr nur einmal
    assert bericht.stoerungen == 1 and bericht.leer == 1 and bericht.stellen == 2
    assert np.all(reihe.werte["rad"][0, i(date(2025, 6, 5))] < 0)


def test_hole_jahresgrenzen_und_bloecke(tmp_path, monkeypatch):
    """Je Jahr ein Abruf bis zum 1.1. des Folgejahrs (vom Endtag kommt nur 0 Uhr), abgelegt nur die
    Stunden des Jahrs; höchstens BLOCK Zählstellen je Abruf; ältere Jahre nur, wenn sie fehlen."""
    import requests

    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    stellen = [_f(str(100 + n), f"Stelle {n}, LHH", "70_Stadt Hannover", 9.7, 52.4)
               for n in range(vmz_rad.BLOCK + 1)]
    abrufe: list[tuple[str, dict]] = []

    class Antwort:
        def __init__(self, url, params):
            self.url, self.params, self.encoding = url, params or {}, None
            self.text = _seite(stellen) if url.endswith("/radzaehler/") else "[]"

        def raise_for_status(self):
            pass

        def json(self):
            von, bis = self.url.split("/values/")[1].split("/")[:2]
            return {k: {"values": [{"datetime": f"{von} 05:00:00", "value": "7"},
                                   {"datetime": f"{bis} 00:00:00", "value": "1"}]}
                    for k in self.params["stationIds"].split(",")}

    def get(url, params=None, **k):
        abrufe.append((url, params or {}))
        return Antwort(url, params)

    monkeypatch.setattr(requests, "get", get)
    q = {**Q, "liste": "https://vmz.example/niedersachsen/radzaehler/",
         "api": "https://vmz.example/wheel-counter/", "ab_jahr": 2017}
    heute = vmz_rad.datetime.now(vmz_rad.UTC).date()
    ordner = tmp_path / "data" / "raw" / "vmz_rad" / "werte"
    ordner.mkdir(parents=True)
    alt = heute.year - 2  # schon da: wird nicht neu geholt
    for s in stellen:
        (ordner / f"{s['properties']['externalId']}_{alt}.json").write_text("[]")
    (ordner.parent / f"stoerungen_{alt}.json").write_text("[]")

    vmz_rad.hole(q, pfade)
    werte = [u for u, _ in abrufe if "/values/" in u]
    assert "https://vmz.example/wheel-counter/values/2017-01-01/2018-01-01/hourly" in werte
    assert not any(f"/values/{alt}-" in u for u in werte)
    assert not any(f"/problems/{alt}-" in u for u, _ in abrufe)
    assert all(len(p["stationIds"].split(",")) <= vmz_rad.BLOCK for u, p in abrufe
               if "/values/" in u)
    assert len([u for u in werte if "/values/2017-" in u]) == 2  # 11 Zählstellen: zwei Blöcke
    abgelegt = json.loads((ordner / "100_2017.json").read_text())
    assert abgelegt == [["2017-01-01 05:00:00", "7"]]  # 0 Uhr am 1.1.2018 nicht in 2017
    assert (ordner / f"110_{heute.year}.json").exists()
