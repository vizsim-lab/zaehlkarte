from __future__ import annotations

import csv
from datetime import date
from types import SimpleNamespace

import pytest

from zaehlkarte.adapters import kevelaer_pdf as kev
from zaehlkarte.config import Pfade

DREI_ARME = [
    2,
    3,
    4,
    6,
    7,
    8,
]  # Ströme eines Knotens mit drei Armen (Zeile unter „Intervall Fz-Arten“)


def _strom(werte: list[int]) -> list[int | None]:
    out: list[int | None] = [None] * 12
    for nr, w in zip(DREI_ARME, werte, strict=True):
        out[nr - 1] = w
    return out


def test_zwoelf_ordnet_stroeme_zu_und_prueft_die_zahl():
    assert kev._zwoelf("22 7 4 7 5 1.032", DREI_ARME, "x") == _strom([22, 7, 4, 7, 5, 1032])
    with pytest.raises(ValueError):
        kev._zwoelf("1 2 3", DREI_ARME, "Seite 21")


def test_nachmittagsseite_drei_arme_und_lkw_mit_anhaenger():
    k = kev.Knoten(5)
    kev.lies_knotenseite(
        k,
        21,
        [
            "Verkehrszählungsergebnisse Kevelaer",
            "Wellener Landstraße Südstraße Wellener Landstraße",
            "Intervall Fz-Arten GA RA LE RE LA GE",
            "2 3 4 6 7 8",
            "17:00 - 17:15 PKW 22 7 4 7 5 32",
            "KRAD 0 0 0 0 0 1",
            "LIEFERWAGEN 2 1 2 3 3 5",
            "LKW 5 3 3 3 0 7",
            "17:15 - 17:30 PKW 18 8 5 5 4 43",
            "KRAD 0 0 0 0 0 0",
            "LIEFERWAGEN 1 1 1 1 1 1",
            "LKW m.A. 0 2 0 1 2 0",
        ],
    )
    viertel = k.viertel["nachmittags"]
    assert sorted(viertel) == [17 * 60, 17 * 60 + 15]
    assert viertel[17 * 60]["PKW"] == _strom([22, 7, 4, 7, 5, 32])
    # „LKW m.A.“ ist die Lkw-Zeile dieser Viertelstunde und wird eigens vermerkt
    assert viertel[17 * 60 + 15]["LKW"] == _strom([0, 2, 0, 1, 2, 0])
    assert k.mit_anhaenger == {"nachmittags": _strom([0, 2, 0, 1, 2, 0])}
    assert k.viertel["morgens"] == {}


def test_kopf_mit_datum_name_und_falsche_nummer():
    k = kev.Knoten(1)
    kev.lies_knotenseite(
        k,
        4,
        [
            "Verkehrszählungsergebnisse Kevelaer",
            "Knotenpunkt 1 Datum der Zählung: Do. 17.09.2019",
            "Wettener Straße/ Gewerbering/ Hoogeweg",
            "September 2019",
        ],
    )
    assert k.datum == date(2019, 9, 17)
    assert k.name == "Wettener Straße/Gewerbering/Hoogeweg"
    with pytest.raises(ValueError):
        kev.lies_knotenseite(kev.Knoten(2), 4, ["Knotenpunkt 1 Datum der Zählung: Do. 17.09.2019"])


def test_summenseite_davon_mit_folgezeilen_und_tausenderpunkt():
    k = kev.Knoten(3)
    zwoelf = " ".join(["1"] * 12)
    kev.lies_knotenseite(
        k,
        14,
        [
            "Knotenpunkt 3",
            "Kölner Str. B9/Wellener Landstraße L491/Mühlenhoeksweg",
            "Intervall Fz-Arten LA GA RA LE GE RE LA GA RA LE GE RE",
            "1 2 3 4 5 6 7 8 9 10 11 12",
            "Hochrechnung DTV",
            "Summe Kfz/4h (6-10) 330 402 385 188 74 38 67 417 125 117 144 1.258",
            "Summe Lkw/4h (15-19) 74 90 62 56 23 9 11 100 29 19 31 48",
            "DTV 24 Stunden 1 2 3 4 5 6 7 8 9 10 11 12",
            "PKW 2.000 2 2 2 2 2 2 2 2 2 2 2",  # Hochrechnung: keine Viertelstunde, kein „davon“
            "davon mo PKW 274 293 310 101 39 22 44 321 91 87 118 1.065",
            f"KRAD {zwoelf}",
            f"LIEFERWAGEN {zwoelf}",
            f"LKW {zwoelf}",
            "davon PKW 423 395 310 470 181 90 60 465 131 108 88 370",
            f"KRAD {zwoelf}",
            f"LIEFERWAGEN {zwoelf}",
            "LKW 2 2 2 2 2 2 2 2 2 2 2 2",
            "Graphische Darstellung der DTV-Werte (Mttelwert aus mo und na):",
        ],
    )
    assert k.datum is None and k.kopfname.startswith("Kölner Str. B9")
    assert k.summen[("Kfz", "morgens")][11] == 1258
    assert k.summen[("Lkw", "nachmittags")][0] == 74
    assert k.davon[("PKW", "morgens")][11] == 1065
    assert k.davon[("LKW", "morgens")] == [1] * 12
    assert k.davon[("PKW", "nachmittags")][0] == 423
    assert k.davon[("LKW", "nachmittags")] == [2] * 12
    assert len(k.davon) == 8
    assert k.viertel == {"morgens": {}, "nachmittags": {}}


def _fenster(k: kev.Knoten, fenster: str, anhaenger: int | None = None) -> None:
    """Ein vollständiges Zählfenster samt Summen, wie der Bericht sie bildet: „davon … LKW“ und
    „Summe Lkw/4h“ ohne die Zeile „LKW m.A.“ (Viertelstunde `anhaenger`), „Summe Kfz/4h“ mit ihr."""
    h0, h1 = kev.FENSTER[fenster]
    minuten = list(range(h0 * 60, h1 * 60, 15))
    for i, m in enumerate(minuten):
        k.viertel[fenster][m] = {
            a: _strom([(i + s + j) % 5 + (20 if a == "PKW" else 0) for s in range(6)])
            for j, a in enumerate(kev.ARTEN)
        }

    def summe(arten, ohne_anhaenger=False):
        return [
            None
            if w is None
            else sum(
                k.viertel[fenster][m][a][s]
                for m in minuten
                for a in arten
                if not (ohne_anhaenger and a == "LKW" and m == anhaenger)
            )
            for s, w in enumerate(_strom([0] * 6))
        ]

    for a in kev.ARTEN:
        k.davon[(a, fenster)] = summe([a], ohne_anhaenger=True)
    k.summen[("Kfz", fenster)] = summe(kev.ARTEN)
    k.summen[("Pkw", fenster)] = summe(["PKW", "KRAD"])
    k.summen[("Lkw", fenster)] = summe(["LIEFERWAGEN", "LKW"], ohne_anhaenger=True)
    if anhaenger is not None:
        k.mit_anhaenger[fenster] = k.viertel[fenster][anhaenger]["LKW"]


def test_fenster_pruefen():
    k = kev.Knoten(5)
    _fenster(k, "morgens")
    _fenster(k, "nachmittags", anhaenger=17 * 60 + 15)
    assert kev.fenster_pruefen(k, "morgens") is None
    assert kev.fenster_pruefen(k, "nachmittags") is None
    # ohne den Vermerk „LKW m.A.“ träfen die Lkw-Summen des Berichts nicht
    ohne = k.mit_anhaenger.pop("nachmittags")
    assert kev.fenster_pruefen(k, "nachmittags") == "Summe LKW trifft „davon“ nicht"
    k.mit_anhaenger["nachmittags"] = ohne
    k.viertel["morgens"][6 * 60]["KRAD"][1] += 1
    assert kev.fenster_pruefen(k, "morgens") == "Summe KRAD trifft „davon“ nicht"
    k.davon[("KRAD", "morgens")][1] += 1
    assert kev.fenster_pruefen(k, "morgens") == "„Summe Kfz/4h“ passt nicht"
    k.viertel["morgens"][7 * 60]["PKW"][1] = None
    assert kev.fenster_pruefen(k, "morgens") == "Strom nicht in jeder Viertelstunde gezählt"
    del k.viertel["nachmittags"][16 * 60]
    assert kev.fenster_pruefen(k, "nachmittags") == "Viertelstunden unvollständig"


def _q_zeilen(nr: int, name: str, lkw: int = 1) -> tuple[list[str], int]:
    zeilen, gesamt = [f"Q{nr} - {name}"], 0
    for h in range(24):
        pkw, krad, liefer = 900 + h if h == 17 else 10 + h, 1, 2
        n = pkw + krad + liefer + lkw
        gesamt += n
        zeilen.append(f"{h} {n} {n + lkw} {pkw} {krad} {liefer} {lkw} 3,0%")
    zeilen += [
        f"{gesamt:,} {gesamt:,} 1 2 3 4 5".replace(",", "."),
        "4h morgens 956 967 872 6 51 27 78",
    ]
    return zeilen, gesamt


def test_querschnittseite_zwei_querschnitte_mit_datum():
    q1, g1 = _q_zeilen(1, "Geldener Straße")
    q2, g2 = _q_zeilen(11, "Hoogeweg", lkw=0)
    kopf = (
        "Querschnittszählungn Uhrzeit Anzahl Fahr-zeuge Pkw-Ein-heiten "
        "PKW KRAD LIEFER LKW LKW-Anteil"
    )
    qs = kev.lies_querschnittseite(
        73, [kopf, *q1, kopf, *q2], [date(2019, 9, 19), date(2019, 9, 17)]
    )
    assert [(q.nummer, q.name, q.datum, q.seite) for q in qs] == [
        (1, "Geldener Straße", date(2019, 9, 19), 73),
        (11, "Hoogeweg", date(2019, 9, 17), 73),
    ]
    assert len(qs[0].stunden) == 24 and qs[0].summe == g1 and g1 > 1000
    assert qs[0].stunden[17] == {"PKW": 917, "KRAD": 1, "LIEFERWAGEN": 2, "LKW": 1}
    assert qs[0].anzahl[17] == 921
    assert qs[1].summe == g2 and qs[1].stunden[0]["LKW"] == 0


def test_gedrehte_daten_von_unten_nach_oben():
    def block(text, unten):
        return [{"text": c, "upright": False, "top": unten - 5 * j} for j, c in enumerate(text)]

    seite = SimpleNamespace(
        chars=[
            *block("Donnerstag 19.09.2019", 300),
            {"text": "Q", "upright": True, "top": 100},
            *block("Dienstag 17.09.2019", 750),
        ]
    )
    assert kev._gedrehte_daten(seite) == [date(2019, 9, 19), date(2019, 9, 17)]


FELDER = [
    "knotenpunkt",
    "seite",
    "abschnitt",
    "zeit",
    "art",
    *[f"s{i}" for i in range(1, 13)],
    "text",
]


def _abschrift(pfad, zeilen):
    with open(pfad, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FELDER, lineterminator="\n")
        w.writeheader()
        for z in zeilen:
            w.writerow(z)


def _werte(werte):
    return {f"s{i + 1}": "" if v is None else v for i, v in enumerate(werte)}


def test_abschrift_der_bildseiten(tmp_path):
    pfad = tmp_path / "kevelaer.csv"
    _abschrift(
        pfad,
        [
            {
                "knotenpunkt": 5,
                "seite": 20,
                "abschnitt": "kopf",
                "zeit": "2019-09-17",
                "text": "Wellener Landstraße L491/Südstraße",
            },
            {
                "knotenpunkt": 5,
                "seite": 20,
                "abschnitt": "viertelstunde",
                "zeit": "06:15",
                "art": "LKW",
                **_werte(_strom([1, 2, 3, 4, 5, 6])),
            },
            {
                "knotenpunkt": 5,
                "seite": 22,
                "abschnitt": "summe",
                "zeit": "15-19",
                "art": "Lkw",
                **_werte(_strom([7] * 6)),
            },
            {
                "knotenpunkt": 5,
                "seite": 22,
                "abschnitt": "davon_mo",
                "art": "KRAD",
                **_werte(_strom([8] * 6)),
            },
            # Textseite: die Werte des Texts gehen vor
            {
                "knotenpunkt": 5,
                "seite": 21,
                "abschnitt": "viertelstunde",
                "zeit": "15:00",
                "art": "PKW",
                **_werte(_strom([9] * 6)),
            },
        ],
    )
    k = kev.Knoten(5, seiten={21})
    knoten = {5: k}
    kev.lese_abschrift(pfad, knoten)
    assert k.datum == date(2019, 9, 17) and k.name == "Wellener Landstraße L491/Südstraße"
    assert k.viertel["morgens"][6 * 60 + 15]["LKW"] == _strom([1, 2, 3, 4, 5, 6])
    assert k.summen[("Lkw", "nachmittags")] == _strom([7] * 6)
    assert k.davon[("KRAD", "morgens")] == _strom([8] * 6)
    assert k.viertel["nachmittags"] == {}
    assert k.aus_abschrift == {"morgens", "nachmittags"}


def test_lese_knotenpunkt_und_querschnitt(tmp_path, monkeypatch):
    pfade = Pfade(pipeline=tmp_path)
    (pfade.roh / "kevelaer").mkdir(parents=True)
    (pfade.roh / "kevelaer" / "bericht.pdf").write_bytes(b"%PDF")
    abschrift = tmp_path / "kevelaer.csv"
    _abschrift(abschrift, [])

    k = kev.Knoten(
        5,
        datum=date(2019, 9, 17),
        arme=["Wellener Landstraße", "Südstraße", "Wellener Landstraße"],
        kopfname="Wellener Landstraße L491/ Südstraße",
    )
    _fenster(k, "morgens")
    _fenster(k, "nachmittags", anhaenger=17 * 60 + 15)
    k.summen[("Kfz", "nachmittags")][1] += 1  # Nachmittag trifft die Summe nicht
    q_gut = kev.lies_querschnittseite(68, _q_zeilen(1, "Geldener Straße")[0], [date(2019, 9, 19)])[
        0
    ]
    q_falsch = kev.lies_querschnittseite(68, _q_zeilen(2, "Sonnenstraße")[0], [date(2019, 9, 19)])[
        0
    ]
    q_falsch.summe += 1
    monkeypatch.setattr(kev, "lese_textseiten", lambda pfad: ({5: k}, [q_gut, q_falsch]))

    quelle = {
        "code": "kevelaer",
        "land": "NW",
        "dateien": [{"datei": "bericht.pdf", "url": "https://example.org/bericht.pdf"}],
        "orte": {
            "K5": {"lon": 6.25756, "lat": 51.573133, "genauigkeit": "kreuzung"},
            "Q1": {
                "lon": 6.258545,
                "lat": 51.574803,
                "genauigkeit": "plan",
                "hinweise": ["Lage nach Plan"],
            },
        },
    }
    bericht = kev.Bericht()
    z = {x.kennung: x for x in kev.lese(quelle, pfade, bericht, abschrift=abschrift)}
    assert sorted(z) == ["K5_20190917", "Q1_20190919"]
    assert bericht.fenster_falsch == ["K5 nachmittags: „Summe Kfz/4h“ passt nicht"]
    assert bericht.q_falsch and bericht.q_falsch[0].startswith("Q2 Sonnenstraße")

    kp = z["K5_20190917"]
    assert (kp.name, kp.typ, kp.intervall, kp.h0, kp.fenster) == (
        "Wellener Landstraße L491/Südstraße",
        "K",
        15,
        6,
        [(360, 600)],
    )
    viertel = k.viertel["morgens"]
    stunde6 = [m for m in viertel if m < 7 * 60]
    assert kp.stunden["kfz"][0] == sum(
        x or 0 for m in stunde6 for v in viertel[m].values() for x in v
    )
    assert kp.stunden["sv"][0] == sum(x or 0 for m in stunde6 for x in viertel[m]["LKW"])
    assert len(kp.stunden["kfz"]) == 4
    assert kp.richtungen == 3 and kp.lage == "geokodiert" and kp.lon == 6.25756
    assert any("Dienstag" in h for h in kp.hinweise) and any(
        h.startswith("Nur 6–10 Uhr") for h in kp.hinweise
    )

    q = z["Q1_20190919"]
    assert (q.name, q.typ, q.intervall, q.h0, q.fenster) == (
        "Geldener Straße (Querschnitt 1)",
        "Q",
        60,
        0,
        [(0, 1440)],
    )
    assert q.stunden["kfz"][17] == q_gut.anzahl[17] and q.stunden["sv"] == [1] * 24
    assert q.hinweise == ["Lage nach Plan"] and q.richtungen == 2
    assert bericht.ohne_lage == []
