"""Neubulach: Verkehrszählungen zur Fortschreibung des Lärmaktionsplans (Video, 12.10.2023) aus dem
Kurzbericht der Stadt (IGV, Januar 2024) – ohne Lizenz (CLAUDE.md, „Quellen ohne Lizenz“).

Aufbau des PDFs (Stand November 2026; Werkzeug-Branch `werkzeug/bw`, tools/bw_ol.py):
- Gezählt hat GEOVISTA am Donnerstag, 12.10.2023 mit Videokameras: Knotenpunkt 1 über
  24 Stunden, die Knotenpunkte 2 bis 6 und die Querschnitte 2 und 3 von 15 bis 19 Uhr
  (Tabelle 1 des Berichts; „7 x 4h, 1 x 24h-Zählung … 0:00 – 23:59 Uhr“ über der Tabelle).
- Die Tabelle „Übersicht der DTV-Werte“ (Seiten 5 und 6) hat je Arm eines Knotens bzw. je
  Querschnitt einen Block („1.1 Waldweg“, „7.1 Altbulacher Str.“; die erste Ziffer ist der
  Knoten, 7 und 8 sind die Querschnitte 2 und 3) mit den Spalten Krad, PKW, LKW I, LKW II und
  den Zeilen „4h-Werte“ (gezählt, 15–19 Uhr), „24h (DTVw)“, „DTV“, „6 bis 22 Uhr“, „22 bis 6
  Uhr“, M und P. Werte je Arm = Querschnitt des Arms (beide Richtungen).
- In der Karte nur, was gezählt ist: Knoten 1 die Zeile „24h (DTVw)“ – laut Bericht nicht
  hochgerechnet (die 24-Stunden-Zählung „bildet den DTVw ab“, Jahreszeitenfaktor 1,0) –, die
  übrigen Knoten und die Querschnitte die Zeile „4h-Werte“ als Summe über 15–19 Uhr. Die
  hochgerechneten Zeilen (24h der 4-Stunden-Zählungen, DTV, Tag/Nacht, M, P) bleiben draußen.
- Kfz = Krad + PKW (mit Lieferwagen bis 3,5 t) + LKW I (Lkw ohne Anhänger, Busse) + LKW II
  (Lkw mit Anhänger, Sattelzüge); Schwerverkehr = LKW I + LKW II. Rad ist laut Bericht
  erfasst, steht aber in keiner Tabelle.
- Knotenpunkt = Summe der Zufahrten: jedes Fahrzeug kreuzt den Querschnitt eines Arms beim
  Hinein- und beim Hinausfahren, also halbe Summe der Arme (der Strombelastungsplan nennt
  ebenso „Σ EIN = Σ AUS“). Ist die Summe der Arme ungerade, fehlt ein Arm – dann kein Wert.
- Zählstellen, Lage und Zeile aus der Quelldatei (`stellen`).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

SPALTEN = ("Krad", "PKW", "LKW I", "LKW II")
SCHWER = ("LKW I", "LKW II")
ZEILEN = {"4h": "4h-Werte", "24h": "24h (DTVw)"}
_BLOCK = re.compile(r"^(\d)\.(\d)$")
_ZAHL = re.compile(r"^\d{1,3}(?:\.\d{3})*$")


@dataclass(frozen=True)
class Wort:
    text: str
    x0: float
    x1: float
    top: float

    @property
    def mitte(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Arm:
    knoten: int  # erste Ziffer der Blocknummer
    nummer: str  # „2.3“
    name: str
    zeilen: dict[str, dict[str, int]] = field(default_factory=dict)  # "4h"/"24h" -> Spalte -> Wert


@dataclass
class Bericht:
    arme: int = 0
    zaehlungen: int = 0
    probleme: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        return [f"{self.arme} Arme bzw. Querschnitte gelesen, {self.zaehlungen} Zählungen",
                *[f"Problem: {p}" for p in self.probleme]]


def _zeilen(woerter: list[Wort], toleranz: float = 1.5) -> list[list[Wort]]:
    out: list[list[Wort]] = []
    for w in sorted(woerter, key=lambda w: (w.top, w.x0)):
        if out and abs(out[-1][0].top - w.top) <= toleranz:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(z, key=lambda w: w.x0) for z in out]


def _kopf(zeile: list[Wort]) -> list[tuple[str, float]]:
    """Spaltenköpfe einer Zeile „Einheit Krad PKW LKW I LKW II SUMME“ -> [(Spalte, Mitte)]."""
    out = []
    i = 0
    while i < len(zeile):
        w = zeile[i]
        if w.text == "LKW" and i + 1 < len(zeile) and zeile[i + 1].text in ("I", "II"):
            out.append((f"LKW {zeile[i + 1].text}", (w.x0 + zeile[i + 1].x1) / 2))
            i += 2
            continue
        if w.text in ("Krad", "PKW", "SUMME"):
            out.append((w.text, w.mitte))
        i += 1
    return out


def arme(seiten: list[list[Wort]], bericht: Bericht | None = None) -> list[Arm]:
    """Wörter der Seiten -> Arme mit den Zeilen „4h-Werte“ und „24h (DTVw)“."""
    bericht = bericht if bericht is not None else Bericht()
    out: list[Arm] = []
    for woerter in seiten:
        zeilen = _zeilen(woerter)
        for i, zeile in enumerate(zeilen):
            einheit = [w for w in zeile if w.text == "Einheit"]
            if not einheit:
                continue
            # Blocknummern: die nächste Zeile darüber mit „1.1“ usw.
            ids = next(([w for w in z if _BLOCK.match(w.text)] for z in reversed(zeilen[:i])
                        if any(_BLOCK.match(w.text) for w in z)), [])
            # ein Block beginnt mit der Zeilenbeschriftung („4h-Werte“) gut 10 pt links von
            # „Einheit“; die Zahlen des Blocks davor enden weiter links
            grenzen = [w.x0 - 20 for w in einheit] + [float("inf")]
            koepfe = _kopf(zeile)
            for von, bis in zip(grenzen, grenzen[1:], strict=False):
                nr = next((w for w in ids if von <= w.x0 < bis), None)
                if nr is None:
                    bericht.probleme.append(f"Block ohne Nummer (Seite, x {von:.0f})")
                    continue
                name = " ".join(w.text for w in next(z for z in reversed(zeilen[:i]) if nr in z)
                                if w.x0 > nr.x0 and von <= w.x0 < bis)
                arm = Arm(int(_BLOCK.match(nr.text)[1]), nr.text, name)
                spalten = [(s, m) for s, m in koepfe if von <= m < bis]
                # „4h-Werte“ und „24h (DTVw)“ folgen direkt unter dem Kopf
                for z in (z for z in zeilen[i + 1:] if z[0].top - zeile[0].top < 20):
                    im_block = [w for w in z if von <= w.x0 < bis]
                    text = " ".join(w.text for w in im_block if not _ZAHL.match(w.text))
                    art = next((a for a, t in ZEILEN.items() if text.startswith(t)), None)
                    if art is None:
                        continue
                    werte = {}
                    for w in im_block:
                        if not _ZAHL.match(w.text):
                            continue
                        s, m = min(spalten, key=lambda sm, w=w: abs(sm[1] - w.mitte))
                        if abs(m - w.mitte) > 15 or s not in SPALTEN or s in werte:
                            bericht.probleme.append(f"{nr.text} {art}: Zahl {w.text} ohne Spalte")
                            continue
                        werte[s] = int(w.text.replace(".", ""))
                    if werte:
                        arm.zeilen[art] = werte
                out.append(arm)
                bericht.arme += 1
    return out


def summen(arme_: list[Arm], zeile: str, knoten: bool) -> tuple[dict[str, int] | None, str | None]:
    """Kfz und Schwerverkehr eines Knotens (halbe Summe der Arme) bzw. Querschnitts.
    -> (Werte, Problem)"""
    if not arme_:
        return None, "kein Arm"
    kfz = sv = 0
    for a in arme_:
        w = a.zeilen.get(zeile)
        if not w or set(w) != set(SPALTEN):
            return None, f"{a.nummer}: Zeile {ZEILEN[zeile]} unvollständig ({w})"
        kfz += sum(w.values())
        sv += sum(w[s] for s in SCHWER)
    if knoten:
        if kfz % 2 or sv % 2:
            return None, f"Summe der Arme ungerade (Kfz {kfz}, Schwerverkehr {sv}) – fehlt ein Arm?"
        kfz, sv = kfz // 2, sv // 2
    return {"kfz": kfz, "sv": sv}, None


def _hinweise(knoten: bool, zeile: str) -> list[str]:
    out = []
    if knoten:
        out.append("Wert des Knotenpunkts = Summe der Zufahrten (halbe Summe der Querschnitte "
                   "aller Arme in der Tabelle des Berichts).")
    if zeile == "24h":
        out.append("Gezählt über 24 Stunden; der Bericht nennt den Wert DTVw (ohne Hochrechnung, "
                   "Jahreszeitenfaktor 1,0).")
    else:
        out.append("Gezählt von 15 bis 19 Uhr; die Hochrechnung des Berichts auf 24 Stunden und "
                   "den DTV steht nicht in der Karte.")
    return out


def zaehlungen(arme_: list[Arm], quelle: dict, bericht: Bericht) -> Iterator[Zaehlung]:
    datei = quelle["dateien"][0]
    tag = quelle["datum"] if isinstance(quelle["datum"], date) else date.fromisoformat(
        str(quelle["datum"]))
    je_knoten: dict[int, list[Arm]] = defaultdict(list)
    for a in arme_:
        je_knoten[a.knoten].append(a)
    for kennung, st in quelle["stellen"].items():
        knoten = st["typ"] == "K"
        werte, problem = summen(je_knoten.get(st["block"], []), st["zeile"], knoten)
        if werte is None:
            bericht.probleme.append(f"{kennung}: {problem}")
            continue
        von, bis = st.get("fenster", [0, 24])
        fenster = [(von * 60, bis * 60)]
        arm_namen = [a.name for a in je_knoten[st["block"]]]
        bericht.zaehlungen += 1
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=f"{kennung}_{tag:%Y%m%d}",
            stelle_roh=kennung,
            name=st["name"],
            typ=st["typ"],
            lon=st.get("lon"),
            lat=st.get("lat"),
            lage="geokodiert" if st.get("lon") is not None else None,
            datum=tag,
            fenster=fenster,
            intervall=None,
            summen=werte if (von, bis) == (0, 24) else {},
            fenstersummen={} if (von, bis) == (0, 24) else werte,
            land=quelle["land"],
            richtungen=len(arm_namen) if knoten else 2,
            kategorien="Krad, Pkw (mit Lieferwagen bis 3,5 t), Lkw I (Lkw ohne Anhänger, Busse), "
                       "Lkw II (Lkw mit Anhänger, Sattelzüge) – Schwerverkehr = Lkw I und Lkw II; "
                       "Rad gezählt, aber nicht veröffentlicht",
            rohdatei=datei["url"],
            bemerkung=(f"Videozählung zur Fortschreibung des Lärmaktionsplans ({datei['titel']}, "
                       + ("Knotenpunkt " if knoten else "Querschnitt ") + kennung[1:] + ")"),
            hinweise=[*st.get("hinweise", []), *_hinweise(knoten, st["zeile"])],
            zusatz={"arme": arm_namen, "genauigkeit": st.get("genauigkeit")},
        )


def lese_pdf(pfad: Path) -> list[list[Wort]]:
    import pdfplumber

    with pdfplumber.open(pfad) as pdf:
        return [[Wort(w["text"], w["x0"], w["x1"], w["top"])
                 for w in s.extract_words(x_tolerance=1.5)] for s in pdf.pages]


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    pfad = pfade.roh / quelle["code"] / quelle["dateien"][0]["datei"]
    if not pfad.exists():
        return
    yield from zaehlungen(arme(lese_pdf(pfad), bericht), quelle, bericht)
