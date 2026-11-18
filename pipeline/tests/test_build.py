from __future__ import annotations

from datetime import date

from zaehlkarte.build import bilde_stellen, uebertrage_lage
from zaehlkarte.modell import Zaehlung
from zaehlkarte.site import fenster_text, kennwerte


def z(kennung, stelle, lon, lat, name="A-Str. / B-Str.", jahr=2020, lage="geokodiert"):
    return Zaehlung(
        "berlin",
        kennung,
        stelle,
        name,
        "K",
        lon,
        lat,
        lage if lon else None,
        date(jahr, 5, 5),
        [(420, 1140)],
        15,
        h0=7,
        stunden={"kfz": [10] * 12},
    )


def test_lage_uebertragen_nur_eindeutig():
    a = z("a", "K1", 13.40, 52.50)
    b = z("b", "K1", 13.4001, 52.5001)
    c = z("c", "K1", None, None)
    weit = [
        z("d", "K2", 13.40, 52.50, name="Nord"),
        z("e", "K2", 13.50, 52.60, name="Süd"),
        z("f", "K2", None, None, name="Süd"),
        z("g", "K2", None, None, name="West"),
    ]
    n = uebertrage_lage([a, b, c, *weit])
    assert n == 2
    assert c.lage == "uebertragen" and abs(c.lon - 13.40005) < 1e-6
    assert weit[2].lon == 13.50  # gleicher Name -> eindeutig
    assert weit[3].lon is None  # zwei Orte, kein Name passt -> keine Lage


def test_stellen_teilen_sich_bei_weit_entfernten_orten():
    zs = [
        z("a", "K1", 13.40, 52.50, jahr=2001),
        z("b", "K1", 13.50, 52.60, jahr=1999),
        z("c", "K1", 13.4002, 52.5001, jahr=2010),
        z("d", None, 13.3, 52.4),
    ]
    stellen = {s.id: s for s in bilde_stellen(zs)}
    assert set(stellen) == {"berlin:K1", "berlin:K1-2", "berlin:_d"}
    assert [x.kennung for x in stellen["berlin:K1"].zaehlungen] == ["b"]  # erste Zählung zuerst
    assert [x.kennung for x in stellen["berlin:K1-2"].zaehlungen] == ["a", "c"]


def test_kennwerte_und_fenster():
    assert fenster_text([(420, 1140)]) == "7–19"
    assert fenster_text([(360, 600), (930, 1140)]) == "6–10, 15:30–19"
    k = kennwerte(z("a", "K1", 13.4, 52.5))
    assert k["w"] == [120, None, None, None, None] and k["w24"] is None
    assert k["sp"] == [10, None, None, None, None] and k["g"] == 1
    assert set(k) == {"datum", "tag", "fenster", "g", "w", "w16", "w24", "sp"}


def test_bericht_nennt_zaehlungen_ohne_ferienkalender(monkeypatch, tmp_path):
    """Ein Werktag, dessen Schuljahr der Kalender des Landes nicht hat, bleibt „unbekannt“ – der
    Bericht nennt die Zählungen je Schuljahr, damit der Kalender nachgetragen wird."""
    import types

    from zaehlkarte import adapters, build
    from zaehlkarte.config import Pfade

    zaehlungen = [z("K1", "K1", 13.4, 52.5, jahr=jahr) for jahr in (1995, 1995, 2020)]

    class Bericht:
        def zeilen(self):
            return []

    modul = types.SimpleNamespace(Bericht=Bericht, lese=lambda q, pfade, bericht: list(zaehlungen))
    monkeypatch.setitem(adapters.ADAPTER, "test", modul)
    monkeypatch.setattr(build, "quellen", lambda pfade: {
        "berlin": {"code": "berlin", "adapter": "test", "land": "NW"}})
    gebaut = build.baue(Pfade(pipeline=tmp_path / "p", repo=tmp_path))
    # NW-Kalender fehlt im leeren config/: auch 2020 ist unbekannt
    assert gebaut.berichte["berlin"][-1] == ("ohne Ferienkalender (NW, Tag unbekannt): "
                                             "3 Zählungen in den Schuljahren 1994/1995, 2019/2020")
    gebaut = build.baue(Pfade())
    assert gebaut.berichte["berlin"][-1] == (
        "ohne Ferienkalender (NW, Tag unbekannt): 2 Zählungen in den Schuljahren 1994/1995")


def test_stroeme_je_quelle_und_jahr(monkeypatch, tmp_path):
    """stroeme/{quelle}-{jahr}.json: nur Zählungen mit Strömen, je Quelle und Jahr eine Datei."""
    import json

    from zaehlkarte import site
    from zaehlkarte.build import Gebaut, Stelle
    from zaehlkarte.config import Pfade

    a = z("K1_20190505", "K1", 13.4, 52.5, jahr=2019)
    a.arme = [{"nr": 1, "name": "Nordstraße (N)", "winkel": 0.0},
              {"nr": 2, "name": "Südstraße (S)", "winkel": 180.0}]
    a.stroeme = [{"von": 1, "nach": 2, "stunden": {"kfz": [6] * 12}},
                 {"von": 2, "nach": 1, "stunden": {"kfz": [4] * 12}}]
    a.lieferung = "neu"
    b = z("K1_20200505", "K1", 13.4, 52.5)  # ohne Ströme
    stelle = Stelle("berlin:K1", "berlin", "A-Str. / B-Str.", "K", 13.4, 52.5, "geokodiert", [a, b])
    pfade = Pfade(pipeline=tmp_path / "p", repo=tmp_path)
    monkeypatch.setattr(site, "quellen", lambda pfade: {
        "berlin": {"code": "berlin", "name": "Berlin", "land": "BE", "lizenz": "dl-de/by-2-0"}})
    monkeypatch.setattr(site.datenlage_, "schreibe", lambda *a: [tmp_path / "datenlage.json"])
    alt = pfade.karte / "stroeme" / "berlin-1999.json"
    alt.parent.mkdir(parents=True)
    alt.write_text("{}")
    site.schreibe(Gebaut([stelle], [], {}), pfade, date(2026, 11, 18))
    manifest = json.loads((pfade.karte / "manifest.json").read_text())
    assert manifest["dateien"]["stroeme"] == "stroeme/{quelle}-{jahr}.json"
    assert manifest["stroeme"] == {"berlin": [2019]}
    assert sorted(p.name for p in (pfade.karte / "stroeme").iterdir()) == ["berlin-2019.json"]
    inhalt = json.loads((pfade.karte / "stroeme" / "berlin-2019.json").read_text())
    assert inhalt["version"] == site.STROEME_VERSION and inhalt["quelle"] == "berlin"
    assert inhalt["zaehlungen"] == {"K1_20190505": {
        "stelle": "berlin:K1", "datum": "2019-05-05", "tag": None, "fenster": "7–19",
        "intervall": 15, "lieferung": "neu", "h0": 7, "arme": a.arme, "stroeme": a.stroeme}}
