from __future__ import annotations

from datetime import date

from zaehlkarte.adapters import neubulach_pdf as n
from zaehlkarte.config import Pfade

KOPF = [("Einheit", 0), ("Krad", 55), ("PKW", 95), ("LKW", 135), ("I", 150), ("LKW", 175),
        ("II", 190), ("SUMME", 215)]
MITTE = {"Krad": 61, "PKW": 101, "LKW I": 143, "LKW II": 184}  # Mitte der Spaltenköpfe


def _w(text: str, x0: float, top: float) -> n.Wort:
    return n.Wort(text, x0, x0 + 5 * len(text), top)


def _zahl(text: str, spalte: str, x: float, top: float) -> n.Wort:
    breite = 5 * len(text)
    return n.Wort(text, x + MITTE[spalte] - breite / 2, x + MITTE[spalte] + breite / 2, top)


def _zeile(blocks: list[tuple[str, str, dict[str, list[int]]]], oben: float) -> list[n.Wort]:
    """Eine Zeile der Tabelle mit Blöcken (Nummer, Name, {„4h“/„24h“: [Krad, PKW, LKW I,
    LKW II]}) nebeneinander, je 260 breit wie im PDF."""
    ws = [_w("KP", 0, oben + 14), _w("9", 10, oben + 14)]
    for i, (nr, name, zeilen) in enumerate(blocks):
        x = 112 + 260 * i
        ws += [_w(nr, x + 90, oben)] + [_w(t, x + 110 + 35 * k, oben)
                                         for k, t in enumerate(name.split())]
        ws += [_w(t, x + 10 + dx, oben + 8) for t, dx in KOPF]
        ws += [_w("4h-Werte", x, oben + 16)]
        ws += [_w("24h", x, oben + 23), _w("(DTVw)", x + 12, oben + 23)]
        for art, top in (("4h", oben + 16), ("24h", oben + 23)):
            for spalte, wert in zip(MITTE, zeilen.get(art, [None] * 4), strict=True):
                if wert is None:
                    continue
                ws.append(_zahl(f"{wert:,}".replace(",", "."), spalte, x + 10, top))
        ws += [_w("DTV", x, oben + 31), _w("9.999", x + 95, oben + 31)]  # hochgerechnet
    return ws


SEITE = (
    # Knoten 1: 24 Stunden gezählt, keine 4h-Werte
    _zeile([("1.1", "Waldweg", {"24h": [18, 660, 42, 19]}),
            ("1.2", "Julius-Heuß-Str. Süd", {"24h": [120, 9324, 311, 125]}),
            ("1.3", "Mathildenstr.", {"24h": [14, 638, 82, 0]}),
            ("1.4", "Julius-Heuß-Str. Nord", {"24h": [124, 9136, 269, 136]})], 100)
    # Knoten 3: drei Arme, 15–19 Uhr gezählt, 24h hochgerechnet
    + _zeile([("3.1", "Wildbader Str.", {"4h": [17, 825, 16, 22], "24h": [51, 2460, 72, 103]}),
              ("3.2", "K 4371", {"4h": [6, 187, 12, 8], "24h": [18, 557, 54, 37]}),
              ("3.3", "Wildbader Str. Ost", {"4h": [23, 988, 28, 30], "24h": [69, 2945, 126, 140]})],
             200)
    # Querschnitt 2 (Block 7) und ein Knoten, dem ein Arm fehlt (ungerade Summe)
    + _zeile([("7.1", "Altbulacher Str.", {"4h": [17, 666, 37, 3]}),
              ("5.1", "Hauptstr.", {"4h": [1, 2, 0, 0]})], 300)
)

QUELLE = {
    "code": "neubulach", "land": "BW", "datum": date(2023, 10, 12),
    "dateien": [{"datei": "k.pdf", "url": "https://example.org/k.pdf", "titel": "Kurzbericht"}],
    "stellen": {
        "K1": {"name": "Julius-Heuß-Straße/Waldweg/Mathildenstraße", "typ": "K", "block": 1,
               "zeile": "24h", "lon": 8.69, "lat": 48.66, "genauigkeit": "kreuzung"},
        "K3": {"name": "Wildbader Straße/K 4369", "typ": "K", "block": 3, "zeile": "4h",
               "fenster": [15, 19]},
        "K5": {"name": "Hauptstraße", "typ": "K", "block": 5, "zeile": "4h", "fenster": [15, 19]},
        "Q2": {"name": "Oberhaugstetter Straße", "typ": "Q", "block": 7, "zeile": "4h",
               "fenster": [15, 19], "hinweise": ["Lage nach dem Plan"]},
    },
}


def test_arme_aus_der_lage_der_woerter():
    b = n.Bericht()
    arme = n.arme([SEITE], b)
    assert [(a.nummer, a.name) for a in arme] == [
        ("1.1", "Waldweg"), ("1.2", "Julius-Heuß-Str. Süd"), ("1.3", "Mathildenstr."),
        ("1.4", "Julius-Heuß-Str. Nord"), ("3.1", "Wildbader Str."), ("3.2", "K 4371"),
        ("3.3", "Wildbader Str. Ost"), ("7.1", "Altbulacher Str."), ("5.1", "Hauptstr.")]
    assert arme[0].zeilen == {"24h": {"Krad": 18, "PKW": 660, "LKW I": 42, "LKW II": 19}}
    assert arme[4].zeilen["4h"] == {"Krad": 17, "PKW": 825, "LKW I": 16, "LKW II": 22}
    assert b.probleme == []


def test_zaehlungen():
    b = n.Bericht()
    zs = {z.stelle_roh: z for z in n.zaehlungen(n.arme([SEITE]), QUELLE, b)}
    assert sorted(zs) == ["K1", "K3", "Q2"]
    k1 = zs["K1"]  # 24 Stunden: Tagessumme, Knoten = halbe Summe der Arme
    assert k1.summen == {"kfz": 10509, "sv": 492} and k1.fenstersummen == {}
    assert k1.fenster == [(0, 1440)] and k1.richtungen == 4 and k1.lage == "geokodiert"
    assert k1.kennung == "K1_20231012" and k1.datum == date(2023, 10, 12)
    k3 = zs["K3"]  # 15–19 Uhr: Summe über das Zählfenster, keine Tagessumme
    assert k3.summen == {} and k3.fenstersummen == {"kfz": 1081, "sv": 58}
    assert k3.fenster == [(900, 1140)] and k3.lon is None and k3.richtungen == 3
    q2 = zs["Q2"]  # Querschnitt: der Block selbst
    assert q2.fenstersummen == {"kfz": 723, "sv": 40} and q2.typ == "Q" and q2.richtungen == 2
    assert q2.hinweise[0] == "Lage nach dem Plan"
    assert any("15 bis 19 Uhr" in h for h in q2.hinweise)
    assert any("Summe der Zufahrten" in h for h in k1.hinweise)
    assert "rad" not in k1.gruppen()  # nicht veröffentlicht, nicht 0
    assert any(p.startswith("K5: Summe der Arme ungerade") for p in b.probleme)


def test_fehlende_zeile_gibt_keinen_wert():
    arme = n.arme([SEITE])
    werte, problem = n.summen([a for a in arme if a.knoten == 1], "4h", knoten=True)
    assert werte is None and "unvollständig" in problem


def test_lese(tmp_path, monkeypatch):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    (pfade.roh / "neubulach").mkdir(parents=True)
    assert list(n.lese(QUELLE, pfade)) == []  # ohne Rohdatei nichts
    (pfade.roh / "neubulach" / "k.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(n, "lese_pdf", lambda pfad: [SEITE])
    zs = list(n.lese({**QUELLE, "datum": "2023-10-12"}, pfade))
    assert len(zs) == 3 and all(z.quelle == "neubulach" and z.land == "BW" for z in zs)
    assert zs[0].rohdatei == "https://example.org/k.pdf"
