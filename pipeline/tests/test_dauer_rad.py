"""Rad-Zählstellen (Familie Dauerzählstellen): Ortszeit-Stunden mit Zeitumstellung (setze_lokal),
MobiData BW, Münster, Aachen, Berlin und München – je mit synthetischen Dateien im Format der
Quelle: nur gezählte Werte (rekonstruiert, markiert, `NA` = nicht gezählt), Kanäle je Stelle,
Rückstellung der Uhr (zusammengefasst oder eine Stunde fehlt) und die Lage."""

from __future__ import annotations

import csv
import gzip
import io
import json
import tarfile
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

import zaehlkarte.fetch
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import aachen_rad, berlin_rad, mobidata_eco, muenchen_rad, muenster_rad
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, setze_lokal, tagessummen

RUECK = date(2026, 10, 25)  # Rückstellung der Uhr
SOMMER = date(2026, 3, 29)  # Beginn der Sommerzeit


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.config.mkdir(parents=True, exist_ok=True)
    return p


def stelle(k: str = "1") -> Dauerstelle:
    return Dauerstelle(quelle="q", kennung=k, name="X", abschnitt=None, richtung=None, lon=7.0,
                       lat=51.0, land="NW")


def felder(eintraege: list[tuple[int, date, int, int]]):
    s = np.array([e[0] for e in eintraege], dtype=np.int64)
    t = np.array([e[1] for e in eintraege], dtype="datetime64[D]")
    h = np.array([e[2] for e in eintraege], dtype=np.int64)
    w = np.array([e[3] for e in eintraege], dtype=np.int64)
    return s, t, h, w


def tag_voll(tag: date, wert: int, anzahl: int = 1, ohne: set[int] = frozenset()) -> list:
    out = []
    for h in range(24):
        if h in ohne:
            continue
        out += [(0, tag, h, wert)] * anzahl
    return out


# ------------------------------------------------------------------------------------ Modell
def test_setze_lokal_stunden_und_zeitumstellung():
    r = Messreihe.leer("q", date(2026, 3, 28), date(2026, 10, 26), [stelle()], ("rad",))
    e = tag_voll(date(2026, 3, 28), 10)
    e += tag_voll(SOMMER, 10)  # 2 Uhr gibt es nicht: der Eintrag dort wird verworfen
    e += tag_voll(RUECK, 10)  # eine Zeile um 2 Uhr mit beiden Stunden
    e += tag_voll(date(2026, 10, 26), 10, ohne={7})  # 7 Uhr fehlt
    s, t, h, w = felder(e)
    gesetzt, verworfen = setze_lokal(r, "rad", s, t, h, w, anzahl=1, rueck="zusammen")
    assert verworfen == 1
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2026, 3, 28))] == 240
    assert summe[0, i(SOMMER)] == 230 and n[0, i(SOMMER)] == 23
    assert r.werte["rad"][0, i(SOMMER), 2] == LEER
    assert summe[0, i(RUECK)] == 240 and r.doppelt[0, i(RUECK)]
    assert summe[0, i(date(2026, 10, 26))] == LEER and n[0, i(date(2026, 10, 26))] == 23
    assert gesetzt == 24 + 23 + 24 + 23


def test_setze_lokal_viertelstunden_einfach_und_ungueltig():
    r = Messreihe.leer("q", RUECK, date(2026, 10, 27), [stelle()], ("rad",))
    e = tag_voll(RUECK, 1, anzahl=4)  # 2 Uhr nur einmal: eine der beiden Stunden fehlt
    e += tag_voll(date(2026, 10, 26), 1, anzahl=4)
    e = [x for x in e if not (x[1] == date(2026, 10, 26) and x[2] == 5)]
    e += [(0, date(2026, 10, 26), 5, 1)] * 3
    e += [(0, date(2026, 10, 27), h, 2) for h in range(24) for _ in range(4)]
    e[-1] = (0, date(2026, 10, 27), 23, LEER)  # eine Viertelstunde nicht gezählt
    s, t, h, w = felder(e)
    setze_lokal(r, "rad", s, t, h, w, anzahl=4, rueck="einfach")
    summe, n = tagessummen(r, "rad")
    assert summe[0, 0] == LEER and n[0, 0] == 23 and not r.doppelt[0, 0]
    assert summe[0, 1] == LEER and n[0, 1] == 23  # 5 Uhr: nur drei Viertelstunden
    assert summe[0, 2] == LEER
    assert r.werte["rad"][0, 2, 23] == LEER and r.werte["rad"][0, 2, 22] == 8
    # beide Stunden getrennt (doppelt so viele Einträge) ergeben die Summe – auch bei „zusammen“
    r2 = Messreihe.leer("q", RUECK, RUECK, [stelle()], ("rad",))
    s, t, h, w = felder(tag_voll(RUECK, 1, anzahl=4) + [(0, RUECK, 2, 1)] * 4)
    setze_lokal(r2, "rad", s, t, h, w, anzahl=4, rueck="einfach")
    assert tagessummen(r2, "rad")[0][0, 0] == 100 and r2.doppelt[0, 0]


# ---------------------------------------------------------------------------------- MobiData
MD_KOPF = ["operator_name", "domain_name", "domain_id", "counter_site", "counter_site_id",
           "counter_serial", "longitude", "latitude", "timezone", "iso_timestamp", "channels_in",
           "channels_out", "channels_unknown", "channels_all", "site_temperature",
           "site_rain_accumulation", "site_snow_accumulation"]
MD_STELLEN = {"100004595": ("Stadt Freiburg", "Wiwilibrücke", "7.8407526", "47.995213"),
              "100013034": ("Stadt Heidelberg", "Mannheimer Straße", "8.65914", "49.4118"),
              "100003358": ("Stadt Tübingen", "Fuß- & Radtunnel Südportal", "9.04806", "48.518"),
              "100020000": ("Stadt Konstanz", "Fahrradbrücke", "9.17", "47.67")}
MD_Q = {"code": "mobidata_rad", "land": "BW", "ab": "2026-09", "nachladen_monate": 2,
        "frisch_tage": 3, "monate": "https://md.example/stunden_{monat}.csv.gz",
        "ohne": {"100003358": "Fuß und Rad zusammen"}}


def md_monat(zeilen: list[tuple[str, str, str]]) -> bytes:
    f = io.StringIO()
    w = csv.writer(f, lineterminator="\n")
    w.writerow(MD_KOPF)
    for sid, ts, wert in zeilen:
        dom, name, lon, lat = MD_STELLEN[sid]
        w.writerow(["Eco Counter GmbH", dom, "1", name, sid, "", lon, lat,
                    "(UTC+01:00) Europe/Paris DST", ts, "na", "na", wert, wert, "10", "0", "na"])
    return gzip.compress(f.getvalue().encode("utf-8"))


def md_stunden(sid: str, tag: date, wert: str, versatz: str, ohne: set[int] = frozenset()):
    return [(sid, f"{tag.isoformat()}T{h:02d}:00:00{versatz}", wert)
            for h in range(24) if h not in ohne]


def test_mobidata_hole_und_lese(pfade, monkeypatch):
    sep = (md_stunden("100004595", date(2026, 9, 30), "10", "+02:00")
           + md_stunden("100013034", date(2026, 9, 30), "5", "+02:00"))
    okt = []
    # Rückstellung: Freiburg eine Zeile um 2 Uhr (beide Stunden), Heidelberg beide getrennt
    for sid in ("100004595", "100013034"):
        for h in range(24):
            v = "+02:00" if h < 2 or (h == 2 and sid == "100013034") else "+01:00"
            okt.append((sid, f"2026-10-25T{h:02d}:00:00{v}", "10" if sid == "100004595" else "5"))
    okt.append(("100013034", "2026-10-25T02:00:00+01:00", "5"))
    okt += md_stunden("100004595", date(2026, 10, 26), "10", "+01:00", ohne={9})  # 9 Uhr fehlt
    okt += md_stunden("100004595", date(2026, 10, 27), "10", "+01:00")
    okt[-1] = ("100004595", "2026-10-27T23:00:00+01:00", "na")
    okt += md_stunden("100004595", date(2026, 10, 28), "10", "+01:00")
    okt.append(okt[-1])  # gleiche Zeile doppelt: einmal gezählt
    okt += md_stunden("100013034", date(2026, 10, 28), "5", "+01:00")
    okt[-1] = ("100013034", "2026-10-28T23:00:00+01:00", "6")
    okt.append(("100013034", "2026-10-28T23:00:00+01:00", "7"))  # widersprüchlich
    okt += md_stunden("100003358", date(2026, 10, 28), "99", "+01:00")  # ohne: nicht in der Karte
    okt += md_stunden("100004595", date(2026, 10, 31), "10", "+01:00")  # jünger als frisch_tage
    dateien = {"202609": md_monat(sep), "202610": md_monat(okt)}
    geholt = []

    def lade(url: str, ziel: Path) -> Path:
        import requests

        geholt.append(url)
        m = url.split("_")[-1][:6]
        if m not in dateien:
            antwort = requests.Response()
            antwort.status_code = 404
            raise requests.HTTPError(response=antwort)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(dateien[m])
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    monkeypatch.setattr(mobidata_eco, "_monate", lambda ab, bis: ["202609", "202610", "202611"])
    log = mobidata_eco.hole(MD_Q, pfade)
    assert "2 Monatsdateien geladen" in log[0] and "noch nicht da: 202611" in log[0]
    # zweiter Lauf: nur die jüngsten zwei Monate neu
    geholt.clear()
    mobidata_eco.hole(MD_Q, pfade)
    assert [u.split("_")[-1] for u in geholt] == ["202610.csv.gz", "202611.csv.gz"]
    abruf = pfade.roh / "mobidata_rad" / "abruf.json"
    abruf.write_text(json.dumps({"abgerufen": "2026-11-02T08:00:00Z"}))  # Grenze 30.10.

    b = mobidata_eco.Bericht()
    r = mobidata_eco.lese(MD_Q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["100004595", "100013034"]
    assert (r.stellen[0].name, r.stellen[0].abschnitt) == ("Wiwilibrücke", "Stadt Freiburg")
    assert b.ohne and "Fuß und Rad zusammen" in b.ohne[0]
    assert b.doppelt_gleich == 1 and b.doppelt_anders == 2 and b.na == 1
    assert b.frisch == 24
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2026, 9, 30))] == 240 and summe[1, i(date(2026, 9, 30))] == 120
    assert summe[0, i(RUECK)] == 240 and r.doppelt[0, i(RUECK)]  # zusammengefasst
    assert summe[1, i(RUECK)] == 125 and r.doppelt[1, i(RUECK)]  # getrennt
    assert summe[0, i(date(2026, 10, 26))] == LEER  # 9 Uhr fehlt
    assert summe[0, i(date(2026, 10, 27))] == LEER  # na
    assert summe[0, i(date(2026, 10, 28))] == 240
    assert summe[1, i(date(2026, 10, 28))] == LEER  # 23 Uhr widersprüchlich
    assert r.tag(r.tage - 1) == date(2026, 10, 28)


def test_mobidata_widerspruch_bei_rueckstellung_und_bloecke(pfade, monkeypatch):
    """Zwei verschiedene Werte für dieselbe Zeile um 2 Uhr am Rückstelltag sind nicht gezählt
    (nicht als „beide Stunden getrennt“ summiert); das Ergebnis hängt nicht von der Blockgröße
    ab."""
    zeilen = []
    for sid, wert in (("100004595", "10"), ("100013034", "5"), ("100020000", "3")):
        for h in range(24):
            v = "+02:00" if h < 2 else "+01:00"
            zeilen.append((sid, f"{RUECK.isoformat()}T{h:02d}:00:00{v}", wert))
        zeilen += md_stunden(sid, date(2026, 10, 26), wert, "+01:00")
    zeilen.append(("100020000", f"{RUECK.isoformat()}T02:00:00+01:00", "4"))  # widersprüchlich
    ordner = pfade.roh / "mobidata_rad"
    ordner.mkdir(parents=True)
    (ordner / "stunden_202610.csv.gz").write_bytes(md_monat(zeilen))
    (ordner / "abruf.json").write_text(json.dumps({"abgerufen": "2026-11-02T08:00:00Z"}))
    ergebnisse = []
    for block in (64, 1, 2):
        monkeypatch.setattr(mobidata_eco, "BLOCK", block)
        b = mobidata_eco.Bericht()
        r = mobidata_eco.lese(MD_Q, pfade, b)
        assert b.doppelt_anders == 2 and b.stunden == 3 * 48 - 1
        ergebnisse.append(r)
    r = ergebnisse[0]
    summe, _ = tagessummen(r, "rad")
    i = r.index(RUECK)
    assert summe[0, i] == 240 and summe[1, i] == 120 and r.doppelt[0, i]
    assert summe[2, i] == LEER and not r.doppelt[2, i]
    assert r.werte["rad"][2, i, 2] == LEER and summe[2, i + 1] == 72
    for andere in ergebnisse[1:]:
        assert np.array_equal(andere.werte["rad"], r.werte["rad"])
        assert np.array_equal(andere.doppelt, r.doppelt)


# ----------------------------------------------------------------------------------- Münster
def ms_monat(sid: str, kanaele: list[str], zeilen: list[tuple[str, list[str], str]]) -> str:
    kopf = ["Datetime", f"{sid} (Gartenstraße)", *[f"{k} (Gartenstraße Kanal)" for k in kanaele],
            f"{sid}-status", *[f"{k}-status" for k in kanaele]]
    f = io.StringIO()
    w = csv.writer(f, lineterminator="\n")
    w.writerow(kopf)
    for ts, werte, status in zeilen:
        gesamt = str(sum(int(x) for x in werte if x))
        w.writerow([ts, gesamt, *werte, status, *["0"] * len(kanaele)])
    return f.getvalue()


def ms_tag(tag: date, werte: list[str], status: str = "0", ohne: set[int] = frozenset()):
    return [(f"{tag.isoformat()} {h:02d}:{m:02d}", werte, status)
            for h in range(24) if h not in ohne for m in (0, 15, 30, 45)]


def ms_archiv(dateien: dict[str, str]) -> bytes:
    f = io.BytesIO()
    with tarfile.open(fileobj=f, mode="w:gz") as tf:
        for name, text in {**dateien, "README.md": "x", "site_min.json": json.dumps(
                [{"name": "Gartenstraße", "directory": "100034978"}])}.items():
            daten = text.encode("utf-8")
            info = tarfile.TarInfo(f"radverkehr-zaehlstellen-main/{name}")
            info.size = len(daten)
            tf.addfile(info, io.BytesIO(daten))
    return f.getvalue()


MS_Q = {"code": "muenster_rad", "land": "NW", "archiv": "https://archiv.example/main.tar.gz",
        "standorte": "https://ms.example/standorte.geojson"}
MS_LAGE = {"type": "FeatureCollection", "features": [
    {"properties": {"id": 100034978, "name": "Gartenstraße"},
     "geometry": {"type": "Point", "coordinates": [7.635686, 51.971541]}}]}


def test_muenster_hole_und_lese(pfade, monkeypatch):
    zeilen = ms_tag(date(2026, 10, 1), ["1", "2"])
    zeilen += ms_tag(date(2026, 10, 2), ["1", "2"], status="validated")
    zeilen += ms_tag(date(2026, 10, 3), ["1", "2"], status="4")  # rekonstruiert: nicht gezählt
    zeilen += ms_tag(date(2026, 10, 4), ["1", "2"])
    zeilen[-1] = (zeilen[-1][0], ["1", "2"], "modified")  # geändert: nicht gezählt
    zeilen += ms_tag(RUECK, ["2", "2"])  # 2 Uhr einmal, mit beiden Stunden
    zeilen += ms_tag(date(2026, 10, 26), ["1", ""])  # leerer Kanal zählt 0
    text = ms_monat("100034978", ["101034978", "102034978"], zeilen)
    # Gesamtspalte weicht einmal von der Summe der Kanäle ab
    text = text.replace("2026-10-26 08:00,1,1,,", "2026-10-26 08:00,5,1,,")
    archiv = ms_archiv({"100034978/2026-10.csv": text, "100034978/2026-03.csv": ms_monat(
        "100034978", ["101034978"], ms_tag(SOMMER, ["3"], ohne={2}))})

    class Antwort:
        content = archiv

        def raise_for_status(self):
            pass

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **k: Antwort())

    def lade(url: str, ziel: Path) -> Path:
        assert url == MS_Q["standorte"]
        ziel.write_text(json.dumps(MS_LAGE))
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    log = muenster_rad.hole(MS_Q, pfade)
    assert "3 Dateien" in log[0]
    assert not (pfade.roh / "muenster_rad" / "repo" / "README.md").exists()

    b = muenster_rad.Bericht()
    r = muenster_rad.lese(MS_Q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["100034978"] and r.stellen[0].name == "Gartenstraße"
    assert (r.stellen[0].lon, r.stellen[0].lat) == (7.635686, 51.971541)
    assert b.status["4"] == 96 and b.status["validated"] == 96 and b.summe_abweichend == 1
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(SOMMER)] == 23 * 4 * 3
    assert summe[0, i(date(2026, 10, 1))] == 96 * 3 and summe[0, i(date(2026, 10, 2))] == 96 * 3
    assert summe[0, i(date(2026, 10, 3))] == LEER and n[0, i(date(2026, 10, 3))] == 0
    assert summe[0, i(date(2026, 10, 4))] == LEER and n[0, i(date(2026, 10, 4))] == 23
    assert summe[0, i(RUECK)] == 96 * 4 and r.doppelt[0, i(RUECK)]
    assert summe[0, i(date(2026, 10, 26))] == LEER and n[0, i(date(2026, 10, 26))] == 23


# ------------------------------------------------------------------------------------ Aachen
AC_PDF_TEXT = """ID     Name                                        Standort            Daten seit
418432 Alexianergraben                             50.772281, 6.081894 2024-08-01
447917 Annuntiatenbach                             50.776281, 6.80208 2024-10-01
448500 Hohenstaufenallee (Richt. Lütticher Str.)   50.764499, 6.076681 2023-04-01
"""
AC_KOPF = ["Zeitstempel_von (UTC)", "Zeitstempel_bis (UTC)",
           "418432 | Alexianergraben | Radfahrer Richtung Norden",
           "418432 | Alexianergraben | Radfahrer Richtung Süden",
           "448500 | Hohenstaufenallee (Richt. Lütticher Str.) | Radfahrer Richtung Lütticher Str",
           "448500 | Hohenstaufenallee (Richt. Lütticher Str.) | "
           "Radfahrer Richtung Mozartstraße (Falschfahrer)",
           "447917 | Annuntiatenbach | Radfahrer Richtung Augustinerbach",
           "999999 | Ohne Lage | Rad"]
AC_Q = {"code": "aachen_rad", "land": "NW", "api": "https://ac.example/api/3/action/package_show",
        "paket": "radzaehlstellen",
        "lage": {"447917": {"lat": 50.776281, "lon": 6.080208, "grund": "Tippfehler"}}}


def ac_jahr(beginn: datetime, stunden: int, leer: set[tuple[int, int]] = frozenset(),
            ohne: set[int] = frozenset()) -> str:
    f = io.StringIO()
    w = csv.writer(f, lineterminator="\n")
    w.writerow(AC_KOPF)
    for i in range(stunden):
        if i in ohne:
            continue
        t = beginn + timedelta(hours=i)
        werte = ["" if (i, k) in leer else str(k + 1) for k in range(6)]
        w.writerow([t.strftime("%Y-%m-%d %H:00:00+00"), t.strftime("%Y-%m-%d %H:59:59+00"), *werte])
    return f.getvalue()


def test_aachen_standorte_aus_text():
    s = aachen_rad.standorte_aus_text(AC_PDF_TEXT)
    assert s["418432"] == ("Alexianergraben", 50.772281, 6.081894)
    assert s["448500"][0] == "Hohenstaufenallee (Richt. Lütticher Str.)"
    assert s["447917"][2] == 6.80208  # wie im PDF; korrigiert wird in lese()


def test_aachen_hole_und_lese(pfade, monkeypatch):
    # 24.10.2026 22 Uhr UTC = 25.10. 0 Uhr Ortszeit; die Rückstellung hat 25 Stunden
    csv25 = ac_jahr(datetime(2026, 10, 24, 22), 25 + 24, leer={(30, 0)}, ohne={40})
    ressourcen = [
        {"name": "Radzaehlstellen_2026.csv", "url": "https://ac.example/alt_2026.csv",
         "last_modified": "2026-11-12T03:00:00"},
        {"name": "Radzaehlstellen_2026.csv", "url": "https://ac.example/neu_2026.csv",
         "last_modified": "2026-11-13T03:00:00"},
        {"name": "Standorte Radzählstellen", "format": "PDF", "url": "https://ac.example/standorte.pdf"},
    ]

    class Antwort:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": {"resources": ressourcen}}

    import requests

    monkeypatch.setattr(requests, "get", lambda url, **k: Antwort())
    geholt = []

    def lade(url: str, ziel: Path) -> Path:
        geholt.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(csv25 if url.endswith(".csv") else "PDF")
        return ziel

    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    log = aachen_rad.hole(AC_Q, pfade)
    assert geholt == ["https://ac.example/neu_2026.csv", "https://ac.example/standorte.pdf"]
    assert "1 Jahresdateien (2026)" in log[0]
    monkeypatch.setattr(aachen_rad, "lies_standorte",
                        lambda p: aachen_rad.standorte_aus_text(AC_PDF_TEXT))

    b = aachen_rad.Bericht()
    r = aachen_rad.lese(AC_Q, pfade, b)
    assert [s.kennung for s in r.stellen] == ["418432", "447917", "448500"]
    assert b.ohne_lage == ["999999 (Ohne Lage)"] and b.lage_korrigiert
    ann = r.stellen[1]
    assert (ann.lon, ann.lat) == (6.080208, 50.776281)
    hohen = r.stellen[2]
    assert hohen.hinweise and "gegen die Fahrtrichtung" in hohen.hinweise[0]
    summe, n = tagessummen(r, "rad")
    i = r.index
    # 25.10.: 25 UTC-Stunden; Alexianergraben 1 + 2 je Stunde, Stunde 2 doppelt
    assert summe[0, i(RUECK)] == 25 * 3 and r.doppelt[0, i(RUECK)]
    assert summe[2, i(RUECK)] == 25 * (3 + 4)  # mit Falschfahrern
    # 26.10.: Stunde 30 (UTC) mit leerem Kanal bei Alexianergraben, Stunde 40 fehlt ganz
    assert summe[0, i(date(2026, 10, 26))] == LEER and summe[1, i(date(2026, 10, 26))] == LEER
    assert b.leer["418432"] == 1


# ------------------------------------------------------------------------------------ Berlin
def berlin_datei(pfad: Path) -> None:
    import openpyxl
    from openpyxl.styles import PatternFill

    wb = openpyxl.Workbook()
    wb.active.title = "Hinweise"
    so = wb.create_sheet("Standortdaten")
    so.append(["Zählstelle", "Beschreibung - Fahrtrichtung", "Breitengrad", "Längengrad",
               "Installationsdatum"])
    so.append(["02-MI-JAN-N", "Jannowitzbrücke Nord", 52.51393215939899, 13.41783460946187,
               datetime(2015, 4, 1)])
    orange = PatternFill("solid", fgColor="FFFFC000")
    rekon = PatternFill("solid", fgColor=openpyxl.styles.colors.Color(theme=5, tint=0.4))
    for jahr, tage in (("2025", [date(2025, 10, 25), date(2025, 10, 26), date(2025, 10, 27)]),
                       ("2026", [date(2025, 10, 27), date(2026, 3, 29)])):
        ws = wb.create_sheet(f"Jahresdatei {jahr}")
        ws.append(["Zählstelle        Inbetriebnahme", "02-MI-JAN-N\n01.04.2015",
                   "99-XX-OHNE\n01.01.2020"])
        for tag in tage:
            for h in range(24):
                if tag == date(2026, 3, 29) and h == 2:
                    ws.append([datetime(tag.year, tag.month, tag.day, h), None, None])
                    continue
                ws.append([datetime(tag.year, tag.month, tag.day, h), 10, 1])
        if jahr == "2025":
            ws.cell(row=2 + 5, column=2).fill = orange  # 25.10.2025 5 Uhr unplausibel
            ws.cell(row=2 + 48 + 7, column=2).fill = rekon  # 27.10.2025 7 Uhr rekonstruiert
    wb.save(pfad)


def test_berlin_rad(pfade):
    ordner = pfade.roh / "berlin_rad"
    ordner.mkdir(parents=True)
    berlin_datei(ordner / berlin_rad.DATEI)
    b = berlin_rad.Bericht()
    r = berlin_rad.lese({"code": "berlin_rad", "land": "BE"}, pfade, b)
    assert [s.kennung for s in r.stellen] == ["02-MI-JAN-N"] and b.ohne_lage == ["99-XX-OHNE"]
    assert r.stellen[0].name == "Jannowitzbrücke Nord" and r.stellen[0].lat == 52.513932
    assert b.markiert == {"0/unplausibel": 1, "rekonstruiert": 1}
    # 27.10.2025 steht in beiden Blättern: gleiche Werte zählen einmal; die Markierung im Blatt
    # 2025 macht den Wert dort ungültig, im Blatt 2026 nicht -> widersprüchlich, nicht gezählt
    assert b.doppelt_anders == 1 and b.doppelt_gleich == 23 + 24
    assert b.leer == 2  # 29.03.2026 2 Uhr: leere Zellen
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2025, 10, 25))] == LEER and n[0, i(date(2025, 10, 25))] == 23
    assert summe[0, i(date(2025, 10, 26))] == 240 and r.doppelt[0, i(date(2025, 10, 26))]
    assert summe[0, i(date(2025, 10, 27))] == LEER
    assert summe[0, i(date(2026, 3, 29))] == 230


# ----------------------------------------------------------------------------------- München
def mu_datei(zeilen: list[list[str]], kommentar: bool = True, format_: str = "-") -> str:
    kopf = ["datum", "uhrzeit_start", "uhrzeit_ende", "zaehlstelle", "richtung_1", "richtung_2",
            "gesamt", *(["kommentar"] if kommentar else [])]
    f = io.StringIO()
    w = csv.writer(f, lineterminator="\r\n")
    w.writerow(kopf)
    for z in zeilen:
        w.writerow(z)
    return "﻿" + f.getvalue()


def mu_tag(tag: date, r1: int, r2: int, fmt: str, kommentar: bool = True,
           na: set[int] = frozenset(), stelle_: str = "Arnulf") -> list[list[str]]:
    d = tag.strftime({"-": "%Y-%m-%d", ".": "%Y.%m.%d", "": "%Y%m%d"}[fmt])
    out = []
    for h in range(24):
        for m in (0, 15, 30, 45):
            if h in na:
                z = [d, f"{h:02d}:{m:02d}:00", "", stelle_, "NA", "NA", "NA", "Baustelle"]
            else:
                z = [d, f"{h:02d}:{m:02d}", "", f"{stelle_}   ", f"   {r1}", str(r2),
                     str(r1 + r2), "NA"]
            out.append(z if kommentar else z[:7])
    return out


def test_muenchen_dateien_waehlen():
    res = [{"name": "15 Minuten Werte 2025", "url": "https://m.example/rad_2025_15min.csv"},
           {"name": "Tageswerte Wetter 2025", "url": "https://m.example/rad_2025_tage.csv"},
           {"name": "15 Minuten-Werte - Dezember 2025 - Daten der Raddauerzählstellen", "url": "https://m.example/rad_2025_12_15min.csv"},
           {"name": "15 Minuten-Werte - März 2026 - Daten der Raddauerzählstellen", "url": "https://m.example/rad_2026_03_15min.csv"},
           {"name": "Tageswerte und Wetter - März 2026 - Daten der Raddauerzählstellen München",
            "url": "https://m.example/rad_2026_03_tage.csv"},
           {"name": "WFS (CSV)", "url": "https://m.example/ows?x=csv"}]
    assert muenchen_rad.dateien_waehlen(res) == {
        "jahr_2025.csv": "https://m.example/rad_2025_15min.csv",
        "monat_2026_03.csv": "https://m.example/rad_2026_03_15min.csv"}


def test_muenchen_lese(pfade):
    ordner = pfade.roh / "muenchen_rad"
    ordner.mkdir(parents=True)
    jahr = (mu_tag(date(2025, 10, 24), 2, 1, "-") + mu_tag(date(2025, 10, 26), 2, 1, "-")
            + mu_tag(date(2025, 10, 27), 2, 1, "-", na={9}))
    jahr[5][6] = "4"  # gesamt ≠ richtung_1 + richtung_2: nicht gezählt
    (ordner / "jahr_2025.csv").write_text(mu_datei(jahr), encoding="utf-8")
    (ordner / "monat_2026_03.csv").write_text(mu_datei(
        mu_tag(SOMMER, 1, 0, ".", kommentar=False)
        + mu_tag(date(2026, 3, 30), 1, 0, "", kommentar=False),
        kommentar=False), encoding="utf-8")
    (ordner / "standorte.geojson").write_text(json.dumps({"features": [
        {"properties": {"zaehlstelle": "Arnulf", "zaehlstelle_lang": "Arnulfstr. 9 - 11 Südseite",
                        "latitude": 48.14205, "longitude": 11.55534}}]}), encoding="utf-8")
    b = muenchen_rad.Bericht()
    r = muenchen_rad.lese({"code": "muenchen_rad", "land": "BY"}, pfade, b)
    assert [s.name for s in r.stellen] == ["Arnulfstr. 9 - 11 Südseite"]
    assert b.summe_abweichend == 1 and b.na == 4 and b.kommentare == {"Baustelle": 4}
    assert b.sommerzeit == 4
    summe, n = tagessummen(r, "rad")
    i = r.index
    assert summe[0, i(date(2025, 10, 24))] == LEER  # eine Viertelstunde mit falscher Summe
    assert summe[0, i(date(2025, 10, 26))] == LEER and n[0, i(date(2025, 10, 26))] == 23
    assert not r.doppelt[0, i(date(2025, 10, 26))]
    assert summe[0, i(date(2025, 10, 27))] == LEER  # NA (Baustelle)
    assert summe[0, i(SOMMER)] == 23 * 4 and summe[0, i(date(2026, 3, 30))] == 96
