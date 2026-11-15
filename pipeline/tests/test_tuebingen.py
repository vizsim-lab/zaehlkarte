from __future__ import annotations

from datetime import date

from zaehlkarte.adapters import tuebingen_pdf as t
from zaehlkarte.config import Pfade

SPALTEN = (190.0, 296.0, 415.0)


def _woerter(text: str, x: float, oben: float, groesse: float = 10.0,
             fett: bool = False) -> list[t.Wort]:
    """Wörter einer Angabe nebeneinander wie im PDF (Breite etwa 0,55 der Schriftgröße je
    Zeichen, dazu ein Zwischenraum)."""
    out = []
    for w in text.split():
        out.append(t.Wort(w, x, oben, groesse, fett))
        x += len(w) * groesse * 0.55 + 3
    return out


def _kasten(oben: float, titel: str, zusatz: str, koepfe: list[str], werte: list[str | None],
            einheit: str, vermerke: list[str | None] | None = None) -> list[t.Wort]:
    """Wörter eines Kastens wie im PDF: Kopf mit fettem Titel und den Zähltagen, Zusatz, je
    Spalte ein Wert mit Einheit (gestaffelt wie im PDF) und darunter klein der Vermerk."""
    ws = _woerter(titel, 30, oben, fett=True)
    for x, k in zip(SPALTEN, koepfe, strict=False):
        ws += _woerter(k, x, oben)
    if zusatz:
        ws += _woerter(zusatz, 30, oben + 12)
    for i, (x, w) in enumerate(zip(SPALTEN, werte, strict=False)):
        if w is not None:
            ws += _woerter(f"{w} {einheit}", x, oben + 24 + 8 * i)
    for x, v in zip(SPALTEN, vermerke or [], strict=False):
        if v:
            ws += _woerter(v, x, oben + 60, groesse=7.0)
    return ws


def _seite() -> list[t.Wort]:
    ws = _woerter("Ost", 30, 20, 11.0, True)  # Überschrift ohne Zähltage: kein Kasten
    ws += _kasten(100, "Kusterdinger Straße", "Neckarbrücke",
                  ["22.10.2015", "17.10.2019", "30.06.2022"], ["6.780", "6.275", "6.361"], "Kfz/24h")
    ws += _kasten(200, "Kusterdinger Straße", "Neckarbrücke",
                  ["22.10.2015", "17.10.2019", "30.06.2022"], ["259", "704", "1.669"], "Rad/24h")
    ws += _kasten(300, "Stuttgarter Straße", "südl. Adlerkreuzung nach Nord",
                  ["11.06.2015", "17.10.2019", "12.07.2022"], ["14.712", "15.883", "14.316"],
                  "Kfz/24h", ["Hochrechnung 16h → 24h"])
    ws += _kasten(400, "Stuttgarter Straße", "südl. Adlerkreuzung nach Süd",
                  ["11.06.2015", "17.10.2019", "12.07.2022"], ["7.148", "7.311", "14.412"],
                  "Kfz/24h", ["Hochrechnung 16h → 24h", None, "Baustelle Alberstr. W → S"])
    ws += _kasten(500, "Mühlstraße", "nur Bus", ["23.10.2018", "22.10.2019", "28.06.2022"],
                  ["1.710", None, "1.856"], "Bus/24h")
    ws += _kasten(600, "Eberhardsbrücke", "Nordseite", ["2019 KW 47, 48", "22.10.2019", "n/a"],
                  ["5.841", "5.755", None], "Kfz/24h", ["Dauerzählstelle Ø Di-Do", "Zählung"])
    return ws


def _teilorte() -> list[t.Wort]:
    return _kasten(100, "Bühl", "Eugen-Bolz-Straße", ["25.10.2012", "05.07.2022"],
                   ["15.330", "6.074"], "Kfz/24h", ["östl. Knollstr.", "westl. Bonlanden"])


QUELLE = {
    "code": "tuebingen", "land": "BW",
    "dateien": [{"datei": "a1.pdf", "url": "https://example.org/a1.pdf", "titel": "Anlage 1"},
                {"datei": "a3.pdf", "url": "https://example.org/a3.pdf", "titel": "Anlage 3"}],
    "stellen": [
        {"id": "kusterdinger", "name": "Kusterdinger Straße (Neckarbrücke)",
         "kaesten": ["Kusterdinger Straße | Neckarbrücke"], "lon": 9.08, "lat": 48.52,
         "genauigkeit": "bauwerk"},
        {"id": "stuttgarter", "name": "Stuttgarter Straße südlich der Adlerkreuzung",
         "je_richtung": {"Richtung Norden": "Stuttgarter Straße | südl. Adlerkreuzung nach Nord",
                         "Richtung Süden": "Stuttgarter Straße | südl. Adlerkreuzung nach Süd"}},
        {"id": "eberhardsbruecke", "name": "Eberhardsbrücke",
         "kaesten": ["Eberhardsbrücke | Nordseite"]},
        {"id": "buehl_knoll", "name": "Bühl, östlich der Knollstraße",
         "kaesten": ["Bühl | Eugen-Bolz-Straße"], "vermerk": "östl. Knollstr."},
        {"id": "buehl_bonlanden", "name": "Bühl, westlich Bonlanden",
         "kaesten": ["Bühl | Eugen-Bolz-Straße"], "vermerk": "westl. Bonlanden",
         "hinweise": ["Lage ungefähr"]},
    ],
}


def test_kaesten_aus_der_lage_der_woerter():
    ks = t.kaesten([_seite()], "a1.pdf")
    assert [k.schluessel for k in ks] == [
        "Kusterdinger Straße | Neckarbrücke", "Kusterdinger Straße | Neckarbrücke",
        "Stuttgarter Straße | südl. Adlerkreuzung nach Nord",
        "Stuttgarter Straße | südl. Adlerkreuzung nach Süd", "Mühlstraße | nur Bus",
        "Eberhardsbrücke | Nordseite"]
    rad = ks[1]
    assert [(s.kopf, s.werte) for s in rad.spalten] == [
        ("22.10.2015", {"Rad/24h": 259}), ("17.10.2019", {"Rad/24h": 704}),
        ("30.06.2022", {"Rad/24h": 1669})]
    sued = ks[3]
    assert [s.vermerk for s in sued.spalten] == ["Hochrechnung 16h → 24h", "",
                                                 "Baustelle Alberstr. W → S"]
    assert ks[5].spalten[0].kopf == "2019 KW 47, 48" and ks[5].spalten[2].werte == {}


def test_zaehlungen_nur_gezaehlte_tage():
    b = t.Bericht()
    ks = t.kaesten([_seite()], "a1.pdf") + t.kaesten([_teilorte()], "a3.pdf")
    zs = {z.kennung: z for z in t.zaehlungen(ks, QUELLE, b)}
    assert sorted(zs) == [
        "buehl_bonlanden_20220705", "buehl_knoll_20121025", "eberhardsbruecke_20191022",
        "kusterdinger_20151022", "kusterdinger_20191017", "kusterdinger_20220630",
        "stuttgarter_20191017", "stuttgarter_20220712"]
    k = zs["kusterdinger_20220630"]
    assert k.summen == {"kfz": 6361, "rad": 1669} and k.fenster == [(0, 1440)]
    assert k.lage == "geokodiert" and k.rohdatei == "https://example.org/a1.pdf"
    assert k.zusatz["genauigkeit"] == "bauwerk"
    # je Richtung ein Kasten: Summe beider Richtungen, die Werte stehen in der Bemerkung
    s = zs["stuttgarter_20220712"]
    assert s.summen == {"kfz": 14316 + 14412} and s.richtungen == 2 and s.lon is None
    assert "Richtung Norden 14.316, Richtung Süden 14.412 Kfz/24 h" in s.bemerkung
    assert "Baustelle Alberstr. W → S (Richtung Süden)" in s.bemerkung
    # Hochrechnung, Mittel über Tage, Spalten ohne Datum und Bus bleiben draußen
    assert "stuttgarter_20150611" not in zs
    assert b.nicht["Hochrechnung 16h → 24h"] == 2
    assert b.nicht["kein Datum (2019 KW 47, 48)"] == 1 and b.nicht["Bus/24h"] == 2
    assert "Vermerk der Tabelle: Zählung" in zs["eberhardsbruecke_20191022"].bemerkung
    # der Vermerk wählt die Zählstelle (Teilorte: zwei Orte in einem Kasten)
    assert zs["buehl_knoll_20121025"].summen == {"kfz": 15330}
    assert zs["buehl_bonlanden_20220705"].hinweise == ["Lage ungefähr"]
    assert "östl. Knollstr." not in (zs["buehl_knoll_20121025"].bemerkung or "")
    assert b.ohne_stelle == [] and b.widerspruch == []


def test_kasten_ohne_zaehlstelle_und_widerspruch():
    b = t.Bericht()
    ks = t.kaesten([_seite()], "a1.pdf")
    quelle = {**QUELLE, "stellen": QUELLE["stellen"][:1]}
    list(t.zaehlungen(ks, quelle, b))
    assert "Stuttgarter Straße | südl. Adlerkreuzung nach Nord" in b.ohne_stelle
    # zwei Kästen derselben Stelle nennen für denselben Tag verschiedene Werte: keiner gilt
    ks[1].spalten[0].werte = {"Kfz/24h": 6000, "Rad/24h": 259}
    b = t.Bericht()
    zs = {z.kennung: z for z in t.zaehlungen(ks, quelle, b)}
    assert zs["kusterdinger_20151022"].summen == {"rad": 259}
    assert any("kusterdinger 2015-10-22 kfz" in w for w in b.widerspruch)


def test_nur_eine_richtung_gibt_keine_summe():
    ks = t.kaesten([_seite()], "a1.pdf")
    ks = [k for k in ks if not k.schluessel.endswith("nach Süd")]
    b = t.Bericht()
    zs = {z.kennung: z for z in t.zaehlungen(ks, QUELLE, b)}
    assert not any(k.startswith("stuttgarter") for k in zs)
    assert any("stuttgarter 2019-10-17 kfz: nur" in w for w in b.widerspruch)


def test_datum():
    assert t.datum("05.07.2022") == date(2022, 7, 5)
    assert t.datum("DTV 2019") is None and t.datum("n/a") is None and t.datum("31.02.2022") is None


def test_lese(tmp_path, monkeypatch):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    (pfade.roh / "tuebingen").mkdir(parents=True)
    (pfade.roh / "tuebingen" / "a1.pdf").write_bytes(b"%PDF")  # a3.pdf fehlt: übersprungen
    monkeypatch.setattr(t, "lese_pdf", lambda pfad: [_seite()])
    zs = list(t.lese(QUELLE, pfade))
    assert len(zs) == 6 and all(z.quelle == "tuebingen" and z.land == "BW" for z in zs)
