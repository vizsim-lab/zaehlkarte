"""Gemeinde je Dauerzählstelle (zaehlkarte.gemeinden): Shapefile lesen, Punkt in Fläche, Rand,
Prüfsumme beim Holen, `ags` und `gemeinden` in dauer/index.json – mit einem synthetischen
Shapefile (wie VG250_GEM aufgebaut: Formtyp 5, Felder AGS, GEN, GF)."""

from __future__ import annotations

import hashlib
import io
import json
import struct
import zipfile
from datetime import date

import numpy as np
import pytest

from zaehlkarte import gemeinden as gm
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import site
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe

GEO84 = b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]]]'
UTM = b'PROJCS["ETRS_1989_UTM_Zone_32N",GEOGCS["GCS_ETRS_1989"]]'


def quadrat(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    """Ring im Uhrzeigersinn (Außenring im Shapefile), geschlossen."""
    return [(x0, y0), (x0, y1), (x1, y1), (x1, y0), (x0, y0)]


def shapefile(formen: list[tuple[dict, list[list[tuple[float, float]]]]]) -> tuple[bytes, bytes]:
    """(.shp, .dbf) mit Polygonen; je Form die Felder (AGS, GEN, GF) und die Ringe."""
    saetze = []
    for nr, (_, ringe) in enumerate(formen, start=1):
        punkte = [p for r in ringe for p in r]
        xs, ys = [p[0] for p in punkte], [p[1] for p in punkte]
        teile, start = [], 0
        for r in ringe:
            teile.append(start)
            start += len(r)
        inhalt = struct.pack("<i4d2i", 5, min(xs), min(ys), max(xs), max(ys), len(ringe),
                             len(punkte))
        inhalt += struct.pack(f"<{len(teile)}i", *teile)
        inhalt += b"".join(struct.pack("<2d", *p) for p in punkte)
        saetze.append(struct.pack(">2i", nr, len(inhalt) // 2) + inhalt)
    koerper = b"".join(saetze)
    kopf = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, (100 + len(koerper)) // 2)
    kopf += struct.pack("<2i4d4d", 1000, 5, 0, 0, 0, 0, 0, 0, 0, 0)
    shp = kopf + koerper

    felder = [("AGS", 8), ("GEN", 30), ("GF", 1)]
    satzlaenge = 1 + sum(b for _, b in felder)
    dbf = struct.pack("<B3BIHH20x", 3, 26, 11, 15, len(formen), 32 + 32 * len(felder) + 1,
                      satzlaenge)
    for name, breite in felder:
        dbf += struct.pack("<11sc4xB15x", name.encode(), b"C", breite)
    dbf += b"\r"
    for werte, _ in formen:
        dbf += b" " + b"".join(str(werte[n]).encode("utf-8").ljust(b)[:b] for n, b in felder)
    return shp, dbf + b"\x1a"


def zip_datei(pfad, formen, prj: bytes = GEO84) -> None:
    shp, dbf = shapefile(formen)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        ordner = "vg250_01-01.geo84.shape.ebenen/vg250_ebenen_0101/"
        z.writestr(ordner + "VG250_GEM.shp", shp)
        z.writestr(ordner + "VG250_GEM.dbf", dbf)
        z.writestr(ordner + "VG250_GEM.prj", prj)
        z.writestr(ordner + "VG250_GEM.cpg", b"UTF-8")
        z.writestr(ordner + "VG250_KRS.shp", b"")  # andere Ebenen bleiben ungelesen
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(puffer.getvalue())


# Stadt A (10–11° Länge, 50–51° Breite) mit einem Loch, in dem Gemeinde B liegt; daneben C als
# Landfläche und darüber eine Wasserfläche W (GF 2) derselben Ausdehnung mit anderem Schlüssel.
FORMEN = [
    ({"AGS": "09162000", "GEN": "Großstadt", "GF": 4},
     [quadrat(10.0, 50.0, 11.0, 51.0), quadrat(10.4, 50.4, 10.6, 50.6)[::-1]]),
    ({"AGS": "09184118", "GEN": "Insel", "GF": 4}, [quadrat(10.4, 50.4, 10.6, 50.6)]),
    ({"AGS": "09999999", "GEN": "Wasser", "GF": 2}, [quadrat(11.0, 50.0, 12.0, 51.0)]),
    ({"AGS": "09184120", "GEN": "Daneben", "GF": 4}, [quadrat(11.0, 50.0, 12.0, 51.0)]),
]


@pytest.fixture
def grenzen(tmp_path):
    pfad = tmp_path / "vg250.zip"
    zip_datei(pfad, FORMEN)
    return gm.lese_zip(pfad, {"stand": "2026-01-01"})


def test_lese_zip(grenzen):
    assert grenzen.ags == ["09162000", "09184118", "09999999", "09184120"]
    assert grenzen.namen[0] == "Großstadt"  # UTF-8 laut .cpg
    assert grenzen.land.tolist() == [True, True, False, True]
    assert len(grenzen.ringe[0]) == 2  # Außenring und Loch
    assert grenzen.box[3].tolist() == [11.0, 50.0, 12.0, 51.0]


def test_punkt_in_flaeche_loch_und_landflaeche(grenzen):
    assert grenzen.finde(10.2, 50.2) == ("09162000", "innen")
    assert grenzen.finde(10.5, 50.5) == ("09184118", "innen")  # im Loch der Großstadt
    assert grenzen.finde(11.5, 50.5) == ("09184120", "innen")  # Land vor Wasser


def test_rand_und_ohne(grenzen):
    # rund 140 m westlich der Großstadt (bei 50,5° Breite ist ein Grad Länge rund 71 km)
    assert grenzen.finde(10.0 - 0.002, 50.5) == ("09162000", "rand")
    assert grenzen.finde(10.0 - 0.01, 50.5) == (None, "ohne")  # rund 710 m: zu weit
    ags, arten = grenzen.zuordne([(10.2, 50.2), (9.0, 50.0)])
    assert ags == ["09162000", None] and arten == ["innen", "ohne"]


def test_projizierte_koordinaten_abgelehnt(tmp_path):
    pfad = tmp_path / "utm.zip"
    zip_datei(pfad, FORMEN, prj=UTM)
    with pytest.raises(ValueError, match="projizierten"):
        gm.lese_zip(pfad)


def _konfiguration(pfade: Pfade, summe: str) -> dict:
    cfg = {"url": "https://daten.example/vg/vg250_01-01.geo84.shape.ebenen.zip", "sha256": summe,
           "stand": "2026-01-01", "titel": "VG250", "herausgeber": "BKG", "lizenz": "dl-de/by-2-0",
           "lizenz_url": "https://www.govdata.de/dl-de/by-2-0", "portal": "https://gdz.example",
           "quellenvermerk": "© BKG (2026) dl-de/by-2-0"}
    pfade.config.mkdir(parents=True, exist_ok=True)
    (pfade.config / "gemeinden.yaml").write_text(json.dumps(cfg), encoding="utf-8")
    return cfg


def test_hole_prueft_die_pruefsumme(tmp_path, monkeypatch):
    from zaehlkarte import abruf

    quelle = tmp_path / "quelle.zip"
    zip_datei(quelle, FORMEN)
    summe = hashlib.sha256(quelle.read_bytes()).hexdigest()
    geladen = []

    def lade(url, ziel, **_):
        geladen.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(quelle.read_bytes())
        return ziel

    monkeypatch.setattr(abruf, "lade", lade)
    pfade = Pfade(pipeline=tmp_path / "a", repo=tmp_path / "a")
    _konfiguration(pfade, summe)
    assert gm.hole(pfade)[0].startswith("Gemeinden: vg250_01-01.geo84.shape.ebenen.zip geholt")
    assert gm.hole(pfade)[0].endswith("liegt vor (Prüfsumme stimmt)") and len(geladen) == 1
    g, fehlt = gm.lese(pfade)
    assert fehlt == [] and g.meta["quellenvermerk"] == "© BKG (2026) dl-de/by-2-0"
    assert g.meta["code"] == "gemeinden" and g.meta["herkunft_url"] == "https://gdz.example"

    andere = Pfade(pipeline=tmp_path / "b", repo=tmp_path / "b")
    _konfiguration(andere, "0" * 64)
    with pytest.raises(ValueError, match="Prüfsumme"):
        gm.hole(andere)
    assert not gm.datei(andere, {"url": "x/vg250_01-01.geo84.shape.ebenen.zip"}).exists()
    assert gm.lese(andere)[0] is None


def _reihe() -> tuple[dict, Messreihe]:
    q = {"code": "test_rad", "name": "Test (Rad)", "land": "BY", "titel": "Test",
         "lizenz": "dl-de/by-2-0", "lizenz_url": "https://www.govdata.de/dl-de/by-2-0"}
    stellen = [Dauerstelle("test_rad", k, f"Stelle {k}", None, None, lon, lat, "BY")
               for k, lon, lat in (("a", 10.2, 50.2), ("b", 10.5, 50.5), ("c", 9.0, 50.0))]
    r = Messreihe.leer("test_rad", date(2026, 11, 2), date(2026, 11, 3), stellen, ("rad",))
    r.werte["rad"][:, :, :] = 10
    return q, r


def test_site_schreibt_ags_und_quelle(tmp_path, grenzen):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    site.schreibe([_reihe()], pfade, date(2026, 11, 12), gemeinden=grenzen)
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    assert index["version"] == 5
    felder = index["stellen"]["felder"]
    assert felder[-2:] == ["ags", "chunk"]
    stellen = {w[0]: dict(zip(felder, w, strict=True)) for w in index["stellen"]["werte"]}
    assert {k: s["ags"] for k, s in stellen.items()} == {
        "test_rad:a": "09162000", "test_rad:b": "09184118", "test_rad:c": None}
    assert index["gemeinden"] == {"stand": "2026-01-01"}


def test_site_ohne_grenzen(tmp_path):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    _, bericht = site.schreibe([_reihe()], pfade, date(2026, 11, 12))
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    assert [w[-2] for w in index["stellen"]["werte"]] == [None, None, None]
    assert index["gemeinden"] is None
    assert any(z.startswith("Gemeinden: keine Grenzen") for z in bericht)


def test_ringe_mit_wenigen_punkten_fallen_weg():
    shp, _ = shapefile([({"AGS": "1", "GEN": "x", "GF": 4},
                         [quadrat(0, 0, 1, 1), [(0, 0), (1, 1), (0, 0)]])])
    (_, ringe), = gm._shp(shp)
    assert len(ringe) == 1 and np.array_equal(ringe[0][0], [0.0, 0.0])
