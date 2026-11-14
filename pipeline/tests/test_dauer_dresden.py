"""Dresden (dauer/dresden_rad.py) mit synthetischen Dateien im Aufbau der Quelle: CSV-Ausgabe der
OGC-API (Ortszeit, 0 Uhr nur als Datum, krumme Minuten an Umstelltagen), Stammdaten aus der Ebene
der aktuellen Werte und aus einer Zeile der Ebene aller Werte (GeoJSON)."""

import json
import urllib.parse
from datetime import date

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import dresden_rad
from zaehlkarte.dauer.modell import tagessummen

Q = {"code": "dresden_rad", "land": "SN", "rueck": "einfach", "ab_jahr": 2017,
     "api": "https://dd.example/ogcapi/collections/", "werte": "L1780", "aktuell": "L1781"}

STAMM = {
    "1077": {"ids": 1077, "fremd_id": "F01020", "bezeichnung": "Lennéstraße",
             "lage": "in Höhe Hauptallee", "status": "Aktiv",
             "r1": "Richtung Nord - Straßburger Platz", "r2": "Richtung Süd - Lennéplatz",
             "lon": 13.7509, "lat": 51.0420},
    "1083": {"ids": 1083, "fremd_id": "F02093", "bezeichnung": "Carolabrücke",
             "lage": "Höhe Synagoge", "status": "Inaktiv", "r1": "Richtung Altstadt", "r2": "",
             "lon": 13.7462, "lat": 51.0545},
}


def _zeile(ids: int, tag: str, stunde: int | None, w1, w2, minute: int = 0) -> str:
    zeit = tag if stunde == 0 and minute == 0 else f"{tag} {stunde:02d}:{minute:02d}:00"
    return f"{ids};{'' if w1 is None else w1};{'' if w2 is None else w2};{zeit}"


def test_zeit_und_wert():
    assert dresden_rad.zeit("2025-10-26") == (date(2025, 10, 26), 0, True)
    assert dresden_rad.zeit("2025-10-26 02:00:00") == (date(2025, 10, 26), 2, True)
    assert dresden_rad.zeit("2025-10-26 02:13:00") == (date(2025, 10, 26), 2, False)
    assert dresden_rad.zeit("26.10.2025 02:00:00") is None
    assert dresden_rad.wert("12") == 12 and dresden_rad.wert("3.0") == 3
    assert dresden_rad.wert("") is None


def test_lese(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = tmp_path / "data" / "raw" / "dresden_rad"
    (ordner / "werte").mkdir(parents=True)
    (ordner / "stellen.json").write_text(json.dumps({"stellen": STAMM}))
    z = ['"ids";"w1";"w2";"messzeit"']
    for h in range(24):  # 3.6.: beide voll
        z += [_zeile(1077, "2025-06-03", h, 1, 2), _zeile(1083, "2025-06-03", h, 5, None)]
    for h in range(24):  # 4.6.: Lennéstraße ohne Südwert um 7 Uhr
        z.append(_zeile(1077, "2025-06-04", h, 1, None if h == 7 else 1))
    for h in (h for h in range(24) if h != 2):  # Sommerzeit 30.3.: 23 Stunden
        z += [_zeile(1077, "2025-03-30", h, 1, 0), _zeile(1083, "2025-03-30", h, 1, None)]
    z.append(_zeile(1077, "2025-03-30", 3, 1, 0, minute=11))  # krumme Minute: 3 Uhr nicht gezählt
    for h in range(24):  # Rückstellung 26.10.: 2 Uhr nur einmal
        z.append(_zeile(1077, "2025-10-26", h, 1, 1))
    z.append(_zeile(9999, "2025-06-03", 5, 1, 1))  # ohne Stammdaten
    (ordner / "werte" / "2025.csv").write_text("\n".join(z) + "\n", encoding="utf-8")

    bericht = dresden_rad.Bericht()
    reihe = dresden_rad.lese(Q, pfade, bericht)
    assert [s.kennung for s in reihe.stellen] == ["F01020", "F02093"]
    assert (reihe.stellen[0].name, reihe.stellen[0].abschnitt) == ("Lennéstraße",
                                                                   "in Höhe Hauptallee")
    assert reihe.stellen[0].id == "dresden_rad:F01020"
    assert any("nur eine Richtung" in h for h in reihe.stellen[1].hinweise)
    assert any("Inaktiv" in h for h in reihe.stellen[1].hinweise)
    summen, _ = tagessummen(reihe, "rad")
    i = reihe.index
    assert summen[0, i(date(2025, 6, 3))] == 72 and summen[1, i(date(2025, 6, 3))] == 120
    assert summen[0, i(date(2025, 6, 4))] < 0  # eine Richtung fehlt: nicht vollständig
    assert summen[0, i(date(2025, 3, 30))] < 0  # krumme Minute: nicht vollständig
    assert summen[1, i(date(2025, 3, 30))] == 23  # Sommerzeit: 23 Stunden
    assert summen[0, i(date(2025, 10, 26))] < 0  # Rückstellung: 2 Uhr nur einmal
    assert bericht.krumm == 1 and bericht.leer == 1 and bericht.ohne_stamm == ["9999"]


class _Antwort:
    def __init__(self, text: str = "", daten=None):
        self.text, self._daten, self.encoding = text, daten, None
        self.status_code, self.headers, self.is_redirect = 200, {}, False

    def raise_for_status(self):
        pass

    def json(self):
        return self._daten


def test_hole(tmp_path, monkeypatch):
    """Je Jahr ein Abruf aller Zählstellen (Filter auf die Ortszeit, %20 statt +), ältere Jahre als
    das Vorjahr nur, wenn sie fehlen; Stammdaten von Zählstellen, die L1781 nicht kennt, aus einer
    Zeile der Ebene L1780."""
    import requests

    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    ordner = tmp_path / "data" / "raw" / "dresden_rad" / "werte"
    ordner.mkdir(parents=True)
    heute = dresden_rad.datetime.now(dresden_rad.UTC).date()
    (ordner / "2018.csv").write_text('"ids";"w1";"w2";"messzeit"\n1077;1;1;2018-06-01\n')
    abrufe: list[str] = []

    def get(url, params=None, **k):
        abrufe.append(url)
        if "/L1781/" in url:
            return _Antwort(daten={"type": "FeatureCollection", "features": [
                {"type": "Feature", "id": 1077, "geometry": {"coordinates": [13.75, 51.04]},
                 "properties": {k: v for k, v in STAMM["1077"].items()
                                if k not in ("ids", "lon", "lat")} | {"status": "A"}}]})
        filter_ = urllib.parse.unquote(url.split("filter=")[1].split("&")[0])
        if "limit=1" in url:
            p = {k: v for k, v in STAMM["1083"].items() if k not in ("lon", "lat")}
            return _Antwort(daten={"features": [
                {"geometry": {"coordinates": [13.7462, 51.0545]}, "properties": p}]})
        jahr = int(filter_.split('messzeit>="')[1][:4])
        ids = 1083 if jahr == 2019 else 1077
        return _Antwort(f'"ids";"w1";"w2";"messzeit"\n{ids};1;0;{jahr}-06-01 08:00:00\n')

    monkeypatch.setattr(requests, "get", get)
    zeilen = dresden_rad.hole(Q, pfade)
    jahre = [u for u in abrufe if "/L1780/" in u and "limit=1" not in u]
    assert len(jahre) == heute.year - 2017  # 2018 lag schon da
    assert all("%20" in u and "+" not in u for u in jahre)
    assert any("messzeit%3E%3D%222019-01-01T00%3A00%3A00%22" in u for u in jahre)
    stamm = json.loads((ordner.parent / "stellen.json").read_text())["stellen"]
    assert set(stamm) == {"1077", "1083"} and stamm["1083"]["lon"] == 13.7462
    assert stamm["1077"]["fremd_id"] == "F01020" and "Zählstellen" in zeilen[0]
