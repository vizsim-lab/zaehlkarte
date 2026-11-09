from __future__ import annotations

from datetime import date

from zaehlkarte.adapters import xanten_pdf as x
from zaehlkarte.config import Pfade

ARTEN = ("PKW", "KRAD", "LIEFER", "LKW", "LASTZUG", "BUS")


def _viertelstunde(h: int, m: int, werte: dict[str, list[int]], knoten: bool = True,
                   summe: int | None = None) -> list[str]:
    """Zeilen einer Viertelstunde wie im PDF (die Zeile „Summe“ steht am Bus)."""
    dezimal = f"{h},{m * 100 // 60:02d}"
    zeilen = []
    for i, art in enumerate(ARTEN):
        vorn = f"{h}:{m:02d} {h + (m + 15) // 60}:{(m + 15) % 60:02d} " if i == 0 else ""
        mitte = "1 99 " if knoten else ""
        z = f"{vorn}{dezimal} {mitte}{art} " + " ".join(str(v) for v in werte.get(art, [0, 0, 0]))
        if art == "BUS":
            s = summe if summe is not None else sum(sum(v) for v in werte.values())
            z = f"Summe {s} {z}"
        zeilen.append(z)
    return zeilen


def test_bloecke_viertelstunden_und_summe():
    seite1 = ["Mobilitätskonzept Stadt Xanten Verkehrszählung",
              "Knotenpunkt 8 Datum der Zählung: Di. 25.08.2020",
              "Heinrich-Lensing-Straße/ Augustusring/ Augustusring",
              "5 Stundenzählung"]
    for m in (0, 15, 30, 45):
        seite1 += _viertelstunde(7, m, {"PKW": [10, 0, 5], "LKW": [1, 0, 0], "BUS": [0, 1, 0]})
    seite2 = []  # Fortsetzung ohne Kopf; eine Viertelstunde mit falscher Summe
    for m in (0, 15, 30):
        seite2 += _viertelstunde(8, m, {"PKW": [2, 2, 2]}, summe=99 if m == 15 else None)
    seite2 += ["Querschnitt 2 Datum der Zählung: Di. 25.08.2020", "Westwall"]
    for m in (0, 15, 30, 45):
        seite2 += _viertelstunde(0, m, {"PKW": [0, 1], "LASTZUG": [1, 0]}, knoten=False)
    bloecke = x.lese_text(["\n".join(seite1), "\n".join(seite2)])
    assert [(b.kennung, b.name, b.datum) for b in bloecke] == [
        ("K8", "Heinrich-Lensing-Straße/Augustusring/Augustusring", date(2020, 8, 25)),
        ("Q2", "Westwall", date(2020, 8, 25)),
    ]
    b = x.Bericht()
    k8 = x.stunden(bloecke[0], b)
    assert k8 == {7: (4 * 17, 4 * 2)}  # 8–9 Uhr: nur drei Viertelstunden -> nicht gezählt
    assert b.unvollstaendig == 1 and len(b.summe_falsch) == 1
    assert x.stunden(bloecke[1], b) == {0: (8, 4)}


def test_lese(tmp_path, monkeypatch):
    pfade = Pfade(pipeline=tmp_path, repo=tmp_path)
    (pfade.roh / "xanten").mkdir(parents=True)
    (pfade.roh / "xanten" / "k.pdf").write_bytes(b"%PDF")
    text = ["Knotenpunkt 1 Datum der Zählung: Di. 25.08.2020",
            "Siegfriedstraße/ Trajanring/ Am Nordturm/ Varusring"]
    for h in (7, 8, 15):
        for m in (0, 15, 30, 45):
            text += _viertelstunde(h, m, {"PKW": [1, 2, 3], "BUS": [1, 0, 0]})
    monkeypatch.setattr(x, "lese_pdf", lambda pfad: x.lese_text(["\n".join(text)]))
    q = {"code": "xanten", "land": "NW",
         "dateien": [{"datei": "k.pdf", "url": "https://opendata.ruhr/k.pdf", "titel": "Knoten"}],
         "orte": {"K1": {"lon": 6.45, "lat": 51.66, "genauigkeit": "kreuzung"}}}
    (z,) = list(x.lese(q, pfade))
    assert z.kennung == "K1_20200825" and z.typ == "K" and z.richtungen == 4
    assert z.fenster == [(420, 540), (900, 960)]  # 7–9 und 15–16 Uhr
    assert z.h0 == 7 and z.stunden["kfz"] == [28, 28] + [None] * 6 + [28]
    assert z.stunden["sv"][0] == 4 and z.lage == "geokodiert" and z.intervall == 15
    assert "rad" not in z.stunden  # nicht gezählt, nicht 0
