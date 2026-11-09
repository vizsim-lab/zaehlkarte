from __future__ import annotations

from datetime import date

from zaehlkarte.build import bilde_stellen, uebertrage_lage
from zaehlkarte.modell import Zaehlung
from zaehlkarte.site import STAND, STAND_EN, fenster_text, kennwerte


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
    assert set(k) == {"datum", "tag", "fenster", "g", "w", "w24", "sp"}


def test_stand_in_beiden_sprachen():
    assert STAND_EN.keys() == STAND.keys()  # der Sprachumschalter der Karte braucht jeden Stand
