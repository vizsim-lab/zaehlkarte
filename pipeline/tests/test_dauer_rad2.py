"""Rad-Zählstellen, zweite Runde (November 2026): Würzburg und Rhein-Kreis Neuss (Opendatasoft,
Eco-Counter mit Status), Dortmund (15 Minuten, Ortszeit mit Versatz), Essen (Quartalsdateien,
Lizenz je Ressource), Leipzig (31 Tage im WFS, Gedächtnis) – je mit synthetischen Dateien im Format
der Quelle: nur gezählte Werte, Doppelte, Kanäle je Stelle, Zeitumstellung, Lage."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

import zaehlkarte.fetch
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import dortmund_rad, essen_rad, gedaechtnis, leipzig_rad, ods, ods_eco
from zaehlkarte.dauer.modell import LEER, tagessummen, utc_stunden

RUECK = date(2026, 10, 25)  # Rückstellung der Uhr
SOMMER = date(2026, 3, 29)  # Beginn der Sommerzeit


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.config.mkdir(parents=True, exist_ok=True)
    return p


def utc(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


def stunden_utc(von: datetime, n: int):
    return [von + timedelta(hours=i) for i in range(n)]


# ------------------------------------------------------------------------------------ Modell
def test_utc_stunden_doppelte_und_unvollstaendige():
    t = np.array(["2026-10-25T00:00", "2026-10-25T00:15", "2026-10-25T00:30", "2026-10-25T00:45",
                  "2026-10-25T01:00", "2026-10-25T01:15", "2026-10-25T01:15", "2026-10-25T01:30",
                  "2026-10-25T01:45",
                  "2026-10-25T02:00", "2026-10-25T02:15", "2026-10-25T02:15", "2026-10-25T02:30",
                  "2026-10-25T02:45",
                  "2026-10-25T03:00", "2026-10-25T03:15", "2026-10-25T03:30"],
                 dtype="datetime64[m]")
    w = np.array([1, 2, 3, 4, 1, 1, 1, 1, 1, 5, 5, 6, 5, 5, 1, 1, 1])
    s, h, summe, verschieden = utc_stunden(np.zeros(len(t), dtype=np.int64), t, w, 4)
    assert h.tolist() == [np.datetime64("2026-10-25T00", "h"), np.datetime64("2026-10-25T01", "h")]
    assert summe.tolist() == [10, 4]  # 1 Uhr: dieselbe Viertelstunde zweimal gleich -> einmal
    assert verschieden == 1  # 2 Uhr: 02:15 mit 5 und 6 -> Stunde nicht gezählt; 3 Uhr unvollständig
    s, h, summe, _ = utc_stunden(np.array([0] * 4 + [1] * 4), np.concatenate([t[:4], t[:4]]),
                                 np.array([1, 1, 1, 1, 2, 2, -1, 2]), 4)
    assert s.tolist() == [0] and summe.tolist() == [4]  # Stelle 1: ein Wert nicht gezählt


# ------------------------------------------------------------------- Opendatasoft: Würzburg
def wue_csv(zeilen: list[tuple[str, datetime, str, str]]) -> str:
    out = ["id;date;counts;status"]
    for k, t, w, st in zeilen:
        out.append(f"{k};{t.strftime('%Y-%m-%dT%H:%M:%S+00:00')};{w};{st}")
    return "\n".join(out) + "\n"


WUE_Q = {"code": "wuerzburg_rad", "land": "BY", "basis": "https://wue.example",
         "datensatz": "fahrrad-zaehlung-daten", "standorte": "bicycle_counter_sites"}


def test_wuerzburg_status_doppelte_und_rueckstellung(pfade):
    o = pfade.roh / "wuerzburg_rad"
    o.mkdir(parents=True)
    raw, gel = '["raw"]', '["deleted"]'
    z = []
    # 24.10. Ortszeit = 23.10. 22 Uhr bis 24.10. 21 Uhr UTC; Stelle 1 vollständig, 2 je Stunde
    for t in stunden_utc(utc(2026, 10, 23, 22), 24):
        z.append(("300014875", t, "2", raw))
        z.append(("300020348", t, "1", raw))
    z.append(("300020348", utc(2026, 10, 24, 5), "1", raw))  # dieselbe Stunde gleich: einmal
    # 25.10. (Rückstellung, 25 Stunden ab 24.10. 22 Uhr UTC) – 0 Uhr UTC fehlt wie in der Quelle
    for t in stunden_utc(utc(2026, 10, 24, 22), 25):
        if t != utc(2026, 10, 25, 0):
            z.append(("300014875", t, "3", raw))
    # 26.10.: Stelle 2 mit einer gelöschten Stunde, Stelle 1 mit zwei verschiedenen Werten
    for t in stunden_utc(utc(2026, 10, 25, 23), 24):
        z.append(("300020348", t, "" if t.hour == 9 else "1", gel if t.hour == 9 else raw))
        z.append(("300014875", t, "4", raw))
    z.append(("300014875", utc(2026, 10, 26, 6), "5", raw))
    z.append(("999", utc(2026, 10, 26, 6), "5", raw))  # ohne Lage
    (o / ods_eco.DATEI).write_text(wue_csv(z))
    (o / "standorte.json").write_text(json.dumps({
        "300014875": {"name": "Röntgenring", "lon": 9.933, "lat": 49.8004},
        "300020348": {"name": "Greinberg Richtung Innenstadt", "lon": 9.961, "lat": 49.8005}}))
    b = ods_eco.Bericht()
    r = ods_eco.lese(WUE_Q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["300014875", "300020348"]
    assert (r.stellen[1].name, r.stellen[1].richtung) == ("Greinberg", "Richtung Innenstadt")
    assert b.ohne_lage == ["999"] and b.status["deleted"] == 1 and b.ohne_wert == 1
    assert b.doppelt_verschieden == 1
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2026, 10, 24))] == 48 and summe[1, i(date(2026, 10, 24))] == 24
    assert summe[0, i(RUECK)] == LEER and n[0, i(RUECK)] == 23  # 2 Uhr: nur eine der Stunden
    assert summe[0, i(date(2026, 10, 26))] == LEER  # 6 Uhr UTC mit 4 und 5
    assert summe[1, i(date(2026, 10, 26))] == LEER  # gelöscht = nicht gezählt


# --------------------------------------------------------- Opendatasoft: Rhein-Kreis Neuss
NE_Q = {"code": "rhein_kreis_neuss_rad", "land": "NW", "basis": "https://rkn.example",
        "datensatz": "eco-counter-data", "kanaele": True,
        "stellen": {"100019715": {"name": "Rhein-Radweg", "abschnitt": "Meerbusch-Büderich"}}}


def test_neuss_kanaele_und_status(pfade):
    o = pfade.roh / "rhein_kreis_neuss_rad"
    o.mkdir(parents=True)
    zeilen = ["id;date;counts;status;channel_id"]
    for t in stunden_utc(utc(2026, 6, 30, 22), 48):  # 1. und 2.7. Ortszeit
        for kanal, w in (("101019715", 2), ("102019715", 3)):
            if t == utc(2026, 7, 2, 8) and kanal == "102019715":
                zeilen.append(f"100019715;{t.isoformat()};{w};modified;{kanal}")  # geändert
                continue
            zeilen.append(f"100019715;{t.isoformat()};{w};raw;{kanal}")
    # Sommerzeit-Artefakt der Quelle: leere Zeile zur selben Stunde wie eine gezählte
    zeilen.append(f"100019715;{utc(2026, 7, 1, 4).isoformat()};;;101019715")
    zeilen.append(f"100019715;{utc(2026, 7, 1, 5).isoformat()};7;raw;")  # ohne Kanal: verworfen
    (o / ods_eco.DATEI).write_text("\n".join(zeilen) + "\n")
    (o / "standorte.json").write_text(json.dumps(
        {"100019715": {"name": "Meerbusch", "lon": 6.705018, "lat": 51.261012}}))
    b = ods_eco.Bericht()
    r = ods_eco.lese(NE_Q, pfade, b)
    s = r.stellen[0]
    assert (s.name, s.abschnitt, b.kanaele) == ("Rhein-Radweg", "Meerbusch-Büderich", 2)
    summe, _ = tagessummen(r, "rad")
    assert summe[0, r.index(date(2026, 7, 1))] == 24 * 5  # leere Zeile stört nicht
    assert summe[0, r.index(date(2026, 7, 2))] == LEER  # ein Kanal geändert -> Stunde nicht gezählt
    assert b.status["modified"] == 1 and b.ohne_wert == 1


def test_ods_export_nur_bei_aenderung(pfade, monkeypatch):
    meta = {"metas": {"default": {"modified": "2026-07-05", "data_processed": "2026-07-05T22:15",
                                  "records_count": 3}}}
    monkeypatch.setattr(ods, "metadaten", lambda basis, ds: meta)
    geladen = []

    def lade(url: str, ziel: Path) -> Path:
        geladen.append(url)
        ziel.write_text("id;date\n")
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    o = pfade.roh / "x"
    ods.hole_export("https://b.example", "ds", "id,date", o, "daten.csv")
    assert "unverändert" in ods.hole_export("https://b.example", "ds", "id,date", o, "daten.csv")
    assert len(geladen) == 1 and "timezone=UTC" in geladen[0] and "select=id%2Cdate" in geladen[0]
    meta["metas"]["default"]["data_processed"] = "2026-11-12"
    ods.hole_export("https://b.example", "ds", "id,date", o, "daten.csv")
    assert len(geladen) == 2


# ------------------------------------------------------------------------------- Dortmund
DO_Q = {"code": "dortmund_rad", "land": "NW", "basis": "https://do.example", "datensatz": "fb61",
        "stellen": {"schnettkerbruecke": {"name": "Schnettkerbrücke", "lat": 51.4977,
                                          "lon": 7.435}}}


def test_dortmund_viertelstunden_mit_versatz(pfade):
    o = pfade.roh / "dortmund_rad"
    o.mkdir(parents=True)
    z = ["zeitpunkt_utc;radfahrer;aus_fahrtrichtung_tu;in_fahrtrichtung_tu"]

    def tag(d: date, versatz_vor: str, versatz_nach: str, wechsel: int | None, leer2=False):
        for h in range(24):
            for m in (0, 15, 30, 45):
                v = versatz_vor if wechsel is None or h < wechsel else versatz_nach
                if leer2 and h == 2:  # Sommerzeit: 2 Uhr gibt es nicht, die Quelle führt sie leer
                    z.append(f"{d}T02:{m:02d}:00+01:00;;;")
                    continue
                z.append(f"{d}T{h:02d}:{m:02d}:00{v};3;1;2")

    tag(date(2026, 3, 28), "+01:00", "+01:00", None)
    tag(SOMMER, "+01:00", "+02:00", 3, leer2=True)
    # Rückstellung: 2 Uhr nur einmal (mit +01:00) wie in der Quelle – 0 Uhr UTC fehlt
    tag(RUECK, "+02:00", "+01:00", 2)
    z.append("2026-03-28T05:00:00+01:00;4;1;2")  # Summe ≠ Richtungen; doppelt mit anderem Wert
    (o / dortmund_rad.DATEI).write_text("\n".join(z) + "\n")
    b = dortmund_rad.Bericht()
    r = dortmund_rad.lese(DO_Q, pfade, b)
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2026, 3, 28))] == LEER  # 5 Uhr: Viertelstunde doppelt, verschieden
    assert summe[0, i(SOMMER)] == 23 * 4 * 3  # leere Zeilen um 2 Uhr stören nicht
    assert summe[0, i(RUECK)] == LEER and n[0, i(RUECK)] == 23
    assert b.nicht["Summe ≠ Richtungen"] == 1 and b.doppelt_verschieden == 1


# ---------------------------------------------------------------------------------- Essen
ES_Q = {"code": "essen_rad", "land": "NW", "api": "https://nrw.example/package_show",
        "paket": "radverkehrszahlungen-e", "lizenz_ressource": "dl-by-de", "rueck": "einfach",
        "spalten": [["grugatrasse", "Richtung Rüttenscheid (West)"],
                    ["grugatrasse", "Richtung Ruhr (Ost)"],
                    ["huyssenallee", "Richtung Rüttenscheid (Süd)"],
                    ["huyssenallee", "Richtung Stadtkern (Nord)"]],
        "stellen": {"grugatrasse": {"name": "Grugatrasse", "lat": 51.426592, "lon": 7.038219},
                    "huyssenallee": {"name": "Huyssenallee", "lat": 51.446642, "lon": 7.009876}}}


def essen_datei(tage: list[date], trenner: str = ";", kopf2: str = "Grugatrasse Ruhr_Ost",
                leer: set[tuple[date, int, int]] = frozenset()) -> str:
    z = [trenner.join(["Datum und Uhrzeit", "Grugatrasse Ruettenscheid_West", kopf2,
                       "Huyssenallee Ruettenscheid_Sued", "Huyssenallee Stadtkern_Nord"])]
    for d in tage:
        for h in range(24):
            if d == SOMMER and h == 2:
                continue  # wie in der Quelle: 2 Uhr fehlt
            werte = ["" if (d, h, k) in leer else str(k + 1) for k in range(4)]
            z.append(trenner.join([f"{d:%d.%m.%Y} {h:02d}:00", *werte]))
    return "\n".join(z) + "\n"


def test_essen_hole_lizenz_und_lese(pfade, monkeypatch):
    ressourcen = [
        {"name": "Radverkehrszählungen 2026 Q1", "url": "https://es.example/q1.csv",
         "license": "http://dcat-ap.de/def/licenses/dl-by-de/2.0"},
        {"name": " Radverkehrszählungen 2025 Q4 ", "url": "https://es.example/q4.csv",
         "license": "http://dcat-ap.de/def/licenses/dl-by-de/2.0"},
        {"name": "Radverkehrszählungen 2020 Q4", "url": "https://es.example/zu.csv",
         "license": "http://dcat-ap.de/def/licenses/other-closed"},
        {"name": " Kumulierte Radverkehrszählungen 2025", "url": "https://es.example/k.csv",
         "license": "http://dcat-ap.de/def/licenses/dl-by-de/2.0"},
    ]

    class Antwort:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"resources": ressourcen}}

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **k: Antwort())
    inhalt = {
        "https://es.example/q1.csv": essen_datei([date(2026, 3, 28), SOMMER],
                                                 kopf2="Huyssenallee Stadtkern_Nord",
                                                 leer={(date(2026, 3, 28), 9, 1)}),
        "https://es.example/q4.csv": essen_datei([date(2025, 10, 25), date(2025, 10, 26)],
                                                 trenner="\t"),
    }
    geladen = []

    def lade(url: str, ziel: Path) -> Path:
        geladen.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(inhalt[url])
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    log = essen_rad.hole(ES_Q, pfade)
    assert sorted(geladen) == ["https://es.example/q1.csv", "https://es.example/q4.csv"]
    assert "2020 Q4" in log[0]
    essen_rad.hole(ES_Q, pfade)  # unverändert: nichts neu
    assert len(geladen) == 2
    b = essen_rad.Bericht()
    r = essen_rad.lese(ES_Q, pfade, b)
    assert [s.name for s in r.stellen] == ["Grugatrasse", "Huyssenallee"]
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[1, i(date(2025, 10, 25))] == 24 * 7 and summe[0, i(date(2025, 10, 25))] == 24 * 3
    assert summe[0, i(date(2025, 10, 26))] == LEER  # Rückstellung: 2 Uhr nur einmal
    assert summe[0, i(date(2026, 3, 28))] == LEER and b.leer["grugatrasse"] == 1
    assert summe[1, i(date(2026, 3, 28))] == 24 * 7
    assert summe[1, i(SOMMER)] == 23 * 7
    assert len(b.kopf_abweichend) == 1 and "Q1" in b.kopf_abweichend[0]


# -------------------------------------------------------------------------------- Leipzig
def lz_csv(zeilen: list[tuple]) -> str:
    out = ["FID,objectid,stationname,stationid,phenomenontime,count,fme_tstamp,geom"]
    for oid, k, zeit, w, *lieferung in zeilen:
        stempel = lieferung[0] if lieferung else "2026-11-13T06:30:08.657"
        out.append(f"x.{oid},{oid},Manetstraße,de.sn.stlp.statisch.rad.{k},{zeit},{w},"
                   f"{stempel},POINT (316626.38 5690467.49)")
    return "\n".join(out) + "\n"


def test_leipzig_rueckstellung_nach_objectid():
    z, oid = [], 1000
    for h in range(24):
        oid += 1
        z.append((oid, "100040870", f"2026-10-25T{h:02d}:00:00", h))
        if h == 2:  # zweite Stunde 2 Uhr, danach eingetragen
            oid += 1
            z.append((oid, "100040870", "2026-10-25T02:00:00", 99))
    z.append((5, "300021611", "2026-10-25T02:00:00", 7))  # 2 Uhr nur einmal: welche?
    z.append((6, "300021611", "2026-10-24T08:00:00", 3))
    z.append((7, "300021611", "2026-10-24T08:00:00", 4))  # doppelt, verschieden
    z.append((8, "300021611", "2026-10-24T09:00:00", 5))
    z.append((9, "300021611", "2026-10-24T09:00:00", 5))  # doppelt, gleich
    # eine Stunde in zwei Lieferungen: die jüngste gilt
    z.append((10, "300021611", "2026-10-24T10:00:00", 33, "2026-11-08T04:10:13.993"))
    z.append((20, "300021611", "2026-10-24T10:00:00", 30, "2026-11-09T06:30:25.940"))
    werte, weg = leipzig_rad.lies_stunden(lz_csv(z))
    je = {(k, t): w for k, t, w in werte}
    assert je[("100040870", utc(2026, 10, 25, 0))] == 2  # erste 2 Uhr = 0 Uhr UTC (Sommerzeit)
    assert je[("100040870", utc(2026, 10, 25, 1))] == 99  # zweite 2 Uhr = 1 Uhr UTC
    assert je[("100040870", utc(2026, 10, 25, 2))] == 3  # 3 Uhr Ortszeit (MEZ)
    assert je[("300021611", utc(2026, 10, 24, 7))] == 5
    assert je[("300021611", utc(2026, 10, 24, 8))] == 30
    assert ("300021611", utc(2026, 10, 24, 6)) not in je
    assert weg["2 Uhr der Rückstellung nicht zweimal"] == 1
    assert weg["doppelt mit verschiedenen Werten"] == 2


def test_leipzig_hole_gedaechtnis_und_lese(pfade, monkeypatch):
    q = {"code": "leipzig_rad", "land": "SN", "wfs": "https://lz.example/wfs",
         "ebenen": {"standorte": "OpenData:standort", "stunden": "OpenData:stunde"}}
    standorte = ("FID,objectid,stationname,stationid,installationdate,fme_tstamp,geom\n"
                 "s.1,1,Manetstraße,de.sn.stlp.statisch.rad.100040870,2017-10-25,x,"
                 "POINT (316626.3845562657 5690467.490876849)\n")
    lauf = {"n": 0}

    def stunden() -> str:
        # erster Abruf: 24. und 25.10., zweiter: nur 25. und 26.10. (das Fenster wandert)
        tage = [date(2026, 10, 24), RUECK] if lauf["n"] == 0 else [RUECK, date(2026, 10, 26)]
        z, oid = [], 0
        for d in tage:
            for h in range(24):
                for _ in range(2 if (d == RUECK and h == 2) else 1):
                    oid += 1
                    z.append((oid, "100040870", f"{d}T{h:02d}:00:00", 10))
        return lz_csv(z)

    class Antwort:
        def __init__(self, text):
            self.text, self.encoding = text, None

        def raise_for_status(self):
            pass

    import requests

    def get(url, params=None, **k):
        if params["typeName"].endswith("standort"):
            return Antwort(standorte)
        return Antwort(stunden())

    monkeypatch.setattr(requests, "get", get)
    leipzig_rad.hole(q, pfade)
    lauf["n"] = 1
    log = leipzig_rad.hole(q, pfade)
    assert "geändert" in log[0]
    g = gedaechtnis.lies(pfade.roh / "leipzig_rad" / "gedaechtnis")
    assert sum(v is not None for w in g.values() for v in w) == 3 * 24 + 1
    b = leipzig_rad.Bericht()
    r = leipzig_rad.lese(q, pfade, b)
    s = r.stellen[0]
    assert s.name == "Manetstraße" and abs(s.lat - 51.3335) < 0.01 and abs(s.lon - 12.3593) < 0.01
    summe, _ = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2026, 10, 24))] == 240 and summe[0, i(RUECK)] == 250
    assert r.doppelt[0, i(RUECK)] and summe[0, i(date(2026, 10, 26))] == 240
    assert b.monate == ["2026-10"]


# ---------------------------------------------------------------- Werkzeug: KMK-Ferien
def test_kmk_zweizeilige_zelle_neben_strich():
    """Eine Zeile zwischen zwei Ländern, gleich weit von beiden: Sie gehört zu dem Land, dessen
    eigene Zeile in der Spalte leer ist – „--“ (keine Ferien) zählt als belegt."""
    werkzeug = Path(__file__).resolve().parents[1] / "werkzeuge" / "kmk_ferien.py"
    spec = importlib.util.spec_from_file_location("kmk_ferien", werkzeug)
    kmk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(kmk)
    kopf = ("Land             Herbst          Weihnachten      Winter        Ostern/Frühjahr      "
            "Himmelfahrt/Pfingsten      Sommer")
    zeilen = [
        kopf,
        "Saarland         05.10. - 16.10. 21.12. - 31.12.  08.02. - 12.02. 30.03. - 09.04."
        "          --               28.06. - 06.08.",
        "                                                                                         "
        "07.05.",
        "Sachsen          12.10. - 24.10. 23.12. - 02.01.  08.02. - 19.02. 26.03. - 02.04."
        "                           10.07. - 20.08.",
        "                                                                                         "
        "15.05. - 18.05.",
        "Sachsen-Anhalt   19.10. - 30.10. 21.12. - 02.01.  01.02. - 06.02. 22.03. - 27.03."
        "          15.05. - 22.05.  10.07. - 20.08.",
    ]
    sn = kmk.lies("\n".join(zeilen), "Sachsen", "2026/2027")
    pfingsten = [(v, b) for v, b, n in sn if n == "Pfingstferien"]
    assert pfingsten == [(date(2027, 5, 7), date(2027, 5, 7)),
                         (date(2027, 5, 15), date(2027, 5, 18))]
    assert not [x for x in kmk.lies("\n".join(zeilen), "Saarland", "2026/2027")
                if x[2] == "Pfingstferien"]


# -------------------------------------------------------------------------------- Rostock
def test_rostock_viertelstunden_mit_versatz_und_ohne(pfade):
    from zaehlkarte.dauer import rostock_rad

    o = pfade.roh / "rostock_rad"
    o.mkdir(parents=True)
    z = ["standort_id,zeitpunkt,summe"]

    def viertel(k: str, d: date, versatz: dict[int, str], wert: int = 1, fehlt: set = frozenset()):
        for h in range(24):
            for m in (0, 15, 30, 45):
                if (h, m) in fehlt:
                    continue
                v = versatz.get(h, versatz[-1])
                z.append(f'"{k}",{d:%Y/%m/%d} {h:02d}:{m:02d}:00{v},{wert}')

    viertel("100005392", date(2026, 10, 24), {-1: "+02"})
    # Rückstellung: beide Stunden 2–3 Uhr, die erste mit +02, die zweite mit +01
    viertel("100005392", RUECK, {-1: "+01", 0: "+02", 1: "+02", 2: "+02"})
    for m in (0, 15, 30, 45):
        z.append(f'"100005392",2026/10/25 02:{m:02d}:00+01,1')
    viertel("100005392", date(2026, 10, 26), {-1: "+01"}, fehlt={(9, 30)})
    viertel("300041920", date(2026, 10, 24), {-1: "+02"}, wert=5)  # steht unter `ohne`
    viertel("999", date(2026, 10, 24), {-1: "+02"})  # ohne Lage
    (o / "daten.csv").write_text("\n".join(z) + "\n")
    (o / "standorte.json").write_text(json.dumps({"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "properties": {"id": "100005392", "bezeichnung": "Hamburger Straße/Liningweg"},
         "geometry": {"type": "Point", "coordinates": [12.07412, 54.10296]}},
        {"type": "Feature", "properties": {"id": "300041920", "bezeichnung": "Saarplatz Lindenpark",
                                           "beschreibung": "Steuergerät"},
         "geometry": {"type": "Point", "coordinates": [12.1, 54.09]}}]}))
    q = {"code": "rostock_rad", "land": "MV", "ohne": {"300041920": "Steuergerät"}}
    b = rostock_rad.Bericht()
    r = rostock_rad.lese(q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["100005392"]
    assert b.ohne == ["300041920"] and b.ohne_lage == ["999"]
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2026, 10, 24))] == 96
    assert summe[0, i(RUECK)] == 100 and r.doppelt[0, i(RUECK)]  # 25 Stunden
    assert summe[0, i(date(2026, 10, 26))] == LEER and n[0, i(date(2026, 10, 26))] == 23


# --------------------------------------------------------------------------------- Bochum
def test_bochum_rad_ohne_fuss_und_richtungen(pfade):
    from zaehlkarte.dauer import bochum_rad

    o = pfade.roh / "bochum_rad"
    o.mkdir(parents=True)
    z = ["timestamp,timestamp_utc,name,passanten_in,passanten_out,radfahrende_in,radfahrende_out"]
    t0 = utc(2026, 10, 23, 22)  # 24.10. 0 Uhr Ortszeit
    for i in range(2 * 96):
        t = t0 + timedelta(minutes=15 * i)
        lokal = t.astimezone(leipzig_rad.ORT).isoformat()
        rad = ("1.0", "2.0")
        if t == utc(2026, 10, 25, 7, 15):
            rad = ("1.0", "")  # eine Richtung fehlt
        z.append(f"{lokal},{t:%Y-%m-%dT%H:%M:%SZ},Erzbahntrasse,9.0,9.0,{rad[0]},{rad[1]}")
    (o / "erzbahntrasse.csv").write_text("\n".join(z) + "\n")
    q = {"code": "bochum_rad", "land": "NW",
         "stellen": {"erzbahntrasse": {"name": "Erzbahntrasse", "lat": 51.487049, "lon": 7.184623},
                     "springorumtrasse_sued": {"name": "Springorumtrasse Süd", "lat": 51.44,
                                               "lon": 7.18}},
         "ohne": {"springorumtrasse_sued": "fehlende Kanäle vermutet"}}
    b = bochum_rad.Bericht()
    r = bochum_rad.lese(q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["erzbahntrasse"]
    assert b.ohne == ["springorumtrasse_sued"]
    summe, _ = tagessummen(r, "rad")
    assert summe[0, r.index(date(2026, 10, 24))] == 96 * 3  # nur Rad, nicht Fuß
    assert summe[0, r.index(RUECK)] == LEER and b.unvollstaendig["erzbahntrasse"] == 1
    url = bochum_rad.datei_url({"api": "https://gitlab.example/api/v4", "projekt": "Stadt/rad"},
                               "erzbahntrasse")
    assert url == ("https://gitlab.example/api/v4/projects/Stadt%2Frad/repository/files/"
                   "data%2Ferzbahntrasse%2Fbochum_ecocounter_erzbahntrasse.csv/raw?ref=main")
