from __future__ import annotations

from datetime import date

from zaehlkarte.adapters import nuernberg_pdf as n


def w(text, x0, top, h=11.0, breite=None):
    """Ein Wort wie aus `woerter` (aufrechte Lage)."""
    return {
        "text": text,
        "x0": x0,
        "x1": x0 + (breite or 6 * len(text)),
        "top": top,
        "bottom": top + h,
        "h": h,
    }


def test_zelle_wert_fussnote_und_zweite_zeile():
    z = n.lies_zelle(
        [
            w("16.829", 260, 198),
            w("1", 296, 196.5, h=7),
            w("321", 259, 210.4, h=8),
            w("(1,9%)", 276, 210.4, h=8),
        ]
    )
    assert z == {"text": "16.829", "fn": ["1"], "zweite": "321 (1,9%)", "fg": False}
    # Fußnote „1)“ in normaler Größe, Zeichen für den Fußgängerbereich
    assert n.lies_zelle([w("30.679", 236, 100), w("1)", 270, 100, breite=6)])["fn"] == ["1"]
    z = n.lies_zelle([w("u", 240, 100, breite=6), w("350", 250, 100)])
    assert (z["text"], z["fg"]) == ("350", True)


def test_fussnoten_mehrere_je_zeile_und_seitenzahl():
    ws = [
        w("1)", 54, 520, breite=8),
        w("Umbau", 64, 520),
        w("Erlenstegenstraße", 100, 520),
        w("2)", 300, 520, breite=8),
        w("Baumaßnahme", 310, 520),
        w("Ostendstraße", 390, 520),
        w("3", 54, 532, h=5),
        w("Firmenlauf", 60, 533, h=8),
        w("Dienstagabend", 110, 533, h=8),
        w("31", 780, 560),
    ]
    assert n.fussnoten(ws) == {
        "1": "Umbau Erlenstegenstraße",
        "2": "Baumaßnahme Ostendstraße",
        "3": "Firmenlauf Dienstagabend",
    }


def _kante(top, x0=30, x1=800):
    return {"orientation": "h", "x0": x0, "x1": x1, "top": top, "bottom": top + 0.5}


def _tabelle(nummer_oben: float) -> list[dict]:
    kopf = [
        w("Tabelle", 40, 40),
        w("7:", 90, 40),
        w("ENTWICKLUNG", 110, 40),
        w("Zählstellen", 300, 40),
        w("2025", 370, 40),
        w("Zählstelle", 40, 76),
        w("Juli", 300, 76),
        w("2023", 325, 76),
        w("Juli", 400, 76),
        w("2024", 425, 76),
        w("Juli", 500, 76),
        w("2025", 525, 76),
    ]
    return kopf + [
        w("13", 40, nummer_oben),
        w("Erlenstegenstraße", 80, 102),
        w("104", 190, 102),
        w("(B", 80, 114),
        w("14", 95, 114),
        w("Stadtgrenze)", 112, 114),
        w("13.479", 310, 103),
        w("2", 347, 101.5, h=7),
        w("16.618", 410, 103),
        w("16.046", 510, 103),
        w("3", 547, 101.5, h=7),
        w("224", 40, 140),
        w("1", 64, 140),
        w("Ziegelsteinstraße", 80, 140),
        w("--", 318, 140),
        w("--", 418, 140),
        w("15.318", 510, 140),
        w("3", 40, 180, h=5),
        w("Sperrung", 46, 181, h=8),
        w("Thumenberger", 90, 181, h=8),
        w("Weg", 160, 181, h=8),
    ]


def test_tabelle_mit_und_ohne_linien():
    # neuere Berichte: Linien zwischen den Zeilen, Nummer mittig; ältere: keine Linien, Nummer oben
    mit = n.lies_woerter(_tabelle(108), [_kante(95), _kante(130), _kante(160)])
    ohne = n.lies_woerter(_tabelle(102), [_kante(95), _kante(160)])
    for r in (mit, ohne):
        assert r["jahre"] == [2023, 2024, 2025]
        assert [(z["nummer"], z["name"]) for z in r["zeilen"]] == [
            ("13", ["Erlenstegenstraße 104", "(B 14 Stadtgrenze)"]),
            ("224/1", ["Ziegelsteinstraße"]),
        ]
        assert r["zeilen"][0]["werte"][2025]["fn"] == ["3"]
        assert r["zeilen"][0]["werte"][2023] == {
            "text": "13.479",
            "fn": ["2"],
            "zweite": "",
            "fg": False,
        }
        assert r["zeilen"][1]["werte"][2024]["text"] == "--"
        assert r["fussnoten"] == {"3": "Sperrung Thumenberger Weg"}


def test_name_aus():
    assert (
        n.name_aus(["Weg)13.027 Nopitschstraße", "(HP Sandreuth)"])
        == "Nopitschstraße (HP Sandreuth)"
    )
    assert (
        n.name_aus(["(nördl. Brehmstr.) Weinmarkt", "(westl. Winklerstr.)"])
        == "Weinmarkt (westl. Winklerstr.)"
    )
    assert (
        n.name_aus(["M aximilianstraße", "(nördl. Fürther Straße)"])
        == "Maximilianstraße (nördl. Fürther Straße)"
    )
    assert (
        n.name_aus(["Regensburger StraStraß0e Straße", "(westl. Valznerweiherstraße)"])
        == "Regensburger Straße (westl. Valznerweiherstraße)"
    )
    assert (
        n.name_aus(["Rothenburger Straße) Straße", "(östl. Fuggerstraße)"])
        == "Rothenburger Straße (östl. Fuggerstraße)"
    )
    assert (
        n.name_aus(["Gaulnhofer Straße", "(östl. Lindenplatz"])
        == "Gaulnhofer Straße (östl. Lindenplatz)"
    )


def _zeile(nummer, name, werte, seite=30):
    return {
        "nummer": nummer,
        "name": name,
        "seite": seite,
        "werte": {
            j: {"text": t, "fn": fn, "zweite": "", "fg": False} for j, (t, fn) in werte.items()
        },
    }


def _quelle():
    return {
        "code": "nuernberg",
        "land": "BY",
        "dateien": [
            {"jahr": 2013, "url": "https://x/2013.pdf", "zaehltage": ["2013-07-23", "2013-07-24"]},
            {"jahr": 2014, "url": "https://x/2014.pdf", "zaehltage": ["2014-07-22", "2014-07-23"]},
        ],
        "orte": {
            "55a/4": {"lon": 11.0, "lat": 49.4, "genauigkeit": "kreuzung"},
            "290/2": [
                {"wenn": "Donau", "lon": 11.01, "lat": 49.41},
                {"wenn": "Hafenstraße", "lon": 11.02, "lat": 49.42},
            ],
        },
    }


def test_zaehlungen_auswahl_und_hinweise():
    berichte = {
        2013: {
            "zeilen": [
                _zeile("13", ["Erlenstegenstraße 104"], {2013: ("18.000", ["2"])}),
                _zeile("290/2", ["Hafenstraße"], {2013: ("28.062", [])}),
                _zeile("75", ["Brettergartenstraße"], {2013: ("1.154", ["9"])}),
            ],
            "fussnoten": {30: {"2": "Umbau Erlenstegenstraße", "9": "Vorjahreswert"}},
            "kordon": {"13": {2013: "18.100"}},
            "bruecken": {},
        },
        2014: {
            "zeilen": [
                _zeile(
                    "13", ["Erlenstegenstraße 104"], {2013: ("18.000", []), 2014: ("17.500", [])}
                ),
                _zeile(
                    "55a/4",
                    ["Vorjurastraße", "(südl. Weltenburger Str.)"],
                    {2013: ("16.069", []), 2014: ("--", [])},
                ),
                _zeile("290/2", ["Donaustr."], {2013: ("8.757", []), 2014: ("9.000", [])}),
            ],
            "fussnoten": {},
            "kordon": {},
            "bruecken": {},
        },
    }
    b = n.Bericht()
    zs = {z.kennung: z for z in n.zaehlungen(berichte, _quelle(), b)}
    assert set(zs) == {"13_2013", "13_2014", "290-2_2013", "290-2_2014", "55a-4_2013"}
    z = zs["13_2013"]
    assert (z.datum, z.fenster, z.fenstersummen) == (
        date(2013, 7, 23),
        [(360, 1320)],
        {"kfz": 18000},
    )
    assert z.hinweise == [
        "Bericht 2013: Umbau Erlenstegenstraße",
        "Die Tabelle „Außenkordon“ desselben Berichts nennt 18.100.",
    ]
    # fehlt im Bericht des Jahres: aus dem nächsten Bericht, mit Hinweis
    z = zs["55a-4_2013"]
    assert z.fenstersummen == {"kfz": 16069} and z.rohdatei == "https://x/2014.pdf"
    assert (
        "Wert aus dem Bericht 2014; der Bericht 2013 führt die Zählstelle nicht auf." in z.hinweise
    )
    assert (z.lon, z.lat, z.lage) == (11.0, 49.4, "geokodiert")
    # Abweichung späterer Berichte als Hinweis, Lage je Name
    z = zs["290-2_2013"]
    assert z.fenstersummen == {"kfz": 28062} and (z.lon, z.lat) == (11.02, 49.42)
    assert "Spätere Berichte nennen 8.757 (2014)." in z.hinweise
    assert (zs["290-2_2014"].lon, zs["290-2_2014"].lat) == (11.01, 49.41)
    assert b.vorjahreswert == ["75 2013"] and b.aus_spaeterem == ["55a/4 2013 aus 2014"]
    assert "13 Erlenstegenstraße 104" in b.ohne_lage
