"""Kevelaer: Verkehrszählung 2019 für die Verkehrsuntersuchung im Kernort (PDF ohne Lizenz).

Quelle: „Ergebnisse der Verkehrszählungen im Rahmen des Projekts Untersuchung der
Verkehrsverhältnisse und Neukonzeption im Kernort der Wallfahrtsstadt Kevelaer“ (büro
stadtVerkehr, Hilden, November 2019; 74 Seiten auf kevelaer.de, ohne Lizenzangabe). Gezählt per
Video:

- 16 Knotenpunkte („Datum der Zählung: Do. 17.09.2019“ – der 17.09.2019 war ein Dienstag; es
  gilt das Datum), 6–10 und 15–19 Uhr, je Viertelstunde, Strom (zwölf Spalten LA … RE, je Arm
  drei) und Fahrzeugart (Pkw, Krad, Lieferwagen, Lkw);
- 13 Querschnitte am Donnerstag, 19.09.2019, 24 Stunden, je Stunde und Fahrzeugart, beide
  Richtungen zusammen.

Je Knotenpunkt vier Seiten: Kopf mit Morgentabelle, Nachmittagstabelle, Summen (Summe je Strom
über vier Stunden, „Hochrechnung DTV“, „davon mo“/„davon“ je Fahrzeugart), Grafik. Bei 13
Knotenpunkten ist die Morgentabelle, bei 12 die Summenseite nur ein Bild: Deren Werte stehen in
der Abschrift `pipeline/abschriften/kevelaer.csv` (Werkzeug `werkzeuge/abschrift_kevelaer.py`).
Geprüft wird je Knotenpunkt und Zählfenster, mit Text und Abschrift gemischt: Die Viertelstunden
je Fahrzeugart und Strom müssen die Zeile „davon mo“ bzw. „davon“ treffen, die Fahrzeugarten die
„Summe Kfz/4h“, „Summe Pkw/4h“ (Pkw und Krad) und „Summe Lkw/4h“ (Lieferwagen und Lkw) – sonst
bleibt das Fenster draußen. Querschnitte: je Stunde die Summe der Arten gleich der Spalte „Anzahl
Fahrzeuge“, die Summenzeile gleich der Summe der Stunden.

- Kfz = alle vier Arten; Schwerverkehr = die Art „Lkw“ (der Bericht kennt keine eigenen Arten
  für Busse und Lastzüge; Lieferwagen zählen nicht dazu – im Bericht stecken sie im „Lkw-Anteil
  mit Lieferverkehr“).
- Die Hochrechnungen auf den Tag (DTV) und die Pkw-Einheiten bleiben draußen.
- Lage aus der Quelldatei (`orte`): Knotenpunkte aus OpenStreetMap, Querschnitte nach dem
  Zählstellenplan im Zwischenbericht zum Verkehrskonzept (Abb. 2.3.1.2-2), auf die Straße gelegt.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

ARTEN = ("PKW", "KRAD", "LIEFERWAGEN", "LKW")
FENSTER = {"morgens": (6, 10), "nachmittags": (15, 19)}
ABSCHRIFT = Path(__file__).resolve().parents[3] / "abschriften" / "kevelaer.csv"

_INTERVALL = re.compile(
    r"^(\d{2}):(\d{2}) - (\d{2}):(\d{2}) (PKW|KRAD|LIEFERWAGEN|LKW)( m\.A\.)?((?: [\d.]+)+)$"
)
# „LKW m.A.“: einmal je Nachmittagstabelle ist die Zeile Lkw so beschriftet (17:15–17:30). Die
# „Summe Kfz/4h“ zählt sie mit, „davon … LKW“ und „Summe Lkw/4h“ nicht (Summe über die
# Beschriftung):
# Sie ist die Lkw-Zeile dieser Viertelstunde, die Prüfung rechnet sie den beiden Summen zu.
_ART = re.compile(r"^(PKW|KRAD|LIEFERWAGEN|LKW)( m\.A\.)?((?: [\d.]+)+)$")
_SUMME = re.compile(r"^Summe (Kfz|Pkw|Lkw)/4h \((6-10|15-19)\)((?: [\d.]+)+)$")
_DAVON = re.compile(r"^davon( mo)? (PKW|KRAD|LIEFERWAGEN|LKW)((?: [\d.]+)+)$")
_STROEME = re.compile(r"^\d{1,2}(?: \d{1,2})+$")
_KOPF = re.compile(r"^Knotenpunkt (\d+)(?: Datum der Zählung: \w+\.? (\d{2})\.(\d{2})\.(\d{4}))?$")
_Q_KOPF = re.compile(r"^Q(\d+) - (.+)$")
_Q_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_Q_ZEILE = re.compile(r"^(\d{1,2}) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) [\d,]+%$")
_Q_SUMME = re.compile(r"^([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)$")


def _zahlen(s: str) -> list[int]:
    return [int(x.replace(".", "")) for x in s.split()]


def _zwoelf(s: str, stroeme: list[int], wo: str) -> list[int | None]:
    """Werte einer Zeile auf die zwölf Ströme; Ströme, die es nicht gibt (drei Arme): None."""
    werte = _zahlen(s)
    if len(werte) != len(stroeme):
        raise ValueError(f"{wo}: {len(werte)} Werte für die Ströme {stroeme}")
    out: list[int | None] = [None] * 12
    for nr, w in zip(stroeme, werte, strict=True):
        out[nr - 1] = w
    return out


@dataclass
class Knoten:
    nummer: int
    datum: date | None = None
    arme: list[str] = field(default_factory=list)
    # Fenster -> Viertelstunde (Minute ihres Beginns) -> Art -> zwölf Ströme (None: gibt es nicht)
    viertel: dict[str, dict[int, dict[str, list[int | None]]]] = field(
        default_factory=lambda: {"morgens": {}, "nachmittags": {}}
    )
    summen: dict[tuple[str, str], list[int | None]] = field(
        default_factory=dict
    )  # (Kfz|Pkw|Lkw, Fenster)
    davon: dict[tuple[str, str], list[int | None]] = field(default_factory=dict)  # (Art, Fenster)
    seiten: set[int] = field(default_factory=set)
    aus_abschrift: set[str] = field(default_factory=set)
    kopfname: str = ""
    mit_anhaenger: dict[str, list[int | None]] = field(
        default_factory=dict
    )  # Zeile „LKW m.A.“ je Fenster

    @property
    def name(self) -> str:
        return re.sub(r"\s*/\s*", "/", self.kopfname)


@dataclass
class Querschnitt:
    nummer: int
    name: str
    datum: date | None = None
    stunden: dict[int, dict[str, int]] = field(default_factory=dict)  # Stunde -> Art -> Anzahl
    anzahl: dict[int, int] = field(default_factory=dict)  # Spalte „Anzahl Fahrzeuge“
    summe: int | None = None
    seite: int = 0


@dataclass
class Bericht:
    knoten: int = 0
    querschnitte: int = 0
    fenster_gut: int = 0
    fenster_falsch: list[str] = field(default_factory=list)
    aus_abschrift: int = 0
    q_falsch: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        return [
            f"{self.knoten} Knotenpunkte, {self.fenster_gut} Zählfenster stimmen mit den "
            f"Summen des Berichts ({self.aus_abschrift} davon ganz oder teils aus der "
            "Abschrift der Bildseiten)",
            *[f"Fenster weggelassen: {s}" for s in self.fenster_falsch],
            f"{self.querschnitte} Querschnitte",
            *[f"Querschnitt mit falscher Summe: {s}" for s in self.q_falsch],
            *[f"ohne Lage: {k}" for k in self.ohne_lage],
        ]


def _fenster_von(minute: int) -> str:
    return "morgens" if minute < 12 * 60 else "nachmittags"


def _arme(woerter: list[dict]) -> list[str]:
    """Namen der Arme: die Zeile über „Intervall Fz-Arten“, an großen Lücken getrennt."""
    intervall = next((w for w in woerter if w["text"] == "Intervall"), None)
    if intervall is None:
        return []
    kopf = sorted(
        (w for w in woerter if intervall["top"] - 12 < w["top"] < intervall["top"] - 3),
        key=lambda w: w["x0"],
    )
    arme: list[list[str]] = []
    rechts = None
    for w in kopf:
        if rechts is None or w["x0"] - rechts > 8:
            arme.append([])
        arme[-1].append(w["text"])
        rechts = w["x1"]
    return [" ".join(a) for a in arme]


def lese_textseiten(pfad: Path) -> tuple[dict[int, Knoten], list[Querschnitt]]:
    import pdfplumber

    knoten: dict[int, Knoten] = {}
    quer: list[Querschnitt] = []
    with pdfplumber.open(pfad) as pdf:
        for i, seite in enumerate(pdf.pages[:67], start=1):
            if i < 4:
                continue
            nr = i // 4  # je Knotenpunkt vier Seiten ab Seite 4
            k = knoten.setdefault(nr, Knoten(nr))
            text = seite.extract_text() or ""
            if not text.strip():
                continue  # Bildseite
            k.seiten.add(i)
            if i % 4 in (0, 1) and not k.arme:
                k.arme = _arme(seite.extract_words())
            lies_knotenseite(k, i, text.splitlines())
        for i, seite in enumerate(pdf.pages[67:], start=68):
            # je Querschnitt der Seite ein Datum, senkrecht gesetzt
            quer += lies_querschnittseite(
                i, (seite.extract_text() or "").splitlines(), _gedrehte_daten(seite)
            )
    return knoten, quer


def lies_knotenseite(k: Knoten, i: int, zeilen: list[str]) -> None:
    """Textzeilen einer Seite des Knotenpunkts: Kopf, Viertelstunden, Summen, „davon“."""
    minute = None
    davon = None  # (Fenster) nach „davon( mo) PKW“ folgen KRAD, LIEFERWAGEN, LKW ohne „davon“
    stroeme: list[int] = []
    vorige = ""
    wo = f"Seite {i}"
    for zeile in (z.strip() for z in zeilen):
        if vorige.startswith("Intervall Fz-Arten") and _STROEME.match(zeile):
            stroeme = _zahlen(zeile)
        if _KOPF.match(vorige) and not k.kopfname:
            k.kopfname = zeile
        vorige = zeile
        m = _KOPF.match(zeile)
        if m and int(m[1]) != k.nummer:
            raise ValueError(f"{wo}: Knotenpunkt {m[1]} statt {k.nummer}")
        if m and m[2]:
            k.datum = date(int(m[4]), int(m[3]), int(m[2]))
        if davon and (m := _ART.match(zeile)):
            k.davon[(m[1], davon)] = _zwoelf(m[3], stroeme, wo)
            continue
        davon = None
        if m := _INTERVALL.match(zeile):
            minute = int(m[1]) * 60 + int(m[2])
            werte = _zwoelf(m[7], stroeme, wo)
            k.viertel[_fenster_von(minute)].setdefault(minute, {})[m[5]] = werte
            if m[6]:
                k.mit_anhaenger[_fenster_von(minute)] = werte
        elif (m := _ART.match(zeile)) and minute is not None:
            werte = _zwoelf(m[3], stroeme, wo)
            k.viertel[_fenster_von(minute)][minute][m[1]] = werte
            if m[2]:
                k.mit_anhaenger[_fenster_von(minute)] = werte
        elif m := _SUMME.match(zeile):
            k.summen[(m[1], "morgens" if m[2] == "6-10" else "nachmittags")] = _zwoelf(
                m[3], stroeme, wo
            )
        elif m := _DAVON.match(zeile):
            davon = "morgens" if m[1] else "nachmittags"
            k.davon[(m[2], davon)] = _zwoelf(m[3], stroeme, wo)


def lies_querschnittseite(i: int, zeilen: list[str], daten: list[date]) -> list[Querschnitt]:
    """Textzeilen einer Seite mit (meist zwei) Querschnitten; `daten` in der Folge der Köpfe."""
    out: list[Querschnitt] = []
    daten = list(daten)
    q = None
    for zeile in (z.strip() for z in zeilen):
        if m := _Q_KOPF.match(zeile):
            q = Querschnitt(int(m[1]), m[2].strip(), seite=i)
            q.datum = daten.pop(0) if daten else None
            out.append(q)
        elif q is None:
            continue
        elif m := _Q_ZEILE.match(zeile):
            h = int(m[1])
            q.anzahl[h] = int(m[2].replace(".", ""))
            q.stunden[h] = dict(zip(ARTEN, _zahlen(" ".join(m.group(4, 5, 6, 7))), strict=True))
        elif (m := _Q_SUMME.match(zeile)) and len(q.stunden) == 24 and q.summe is None:
            q.summe = int(m[1].replace(".", ""))
    return out


def _gedrehte_daten(seite) -> list[date]:
    """Daten der Querschnitte: senkrechter Text links („Donnerstag 19.09.2019“), von oben nach unten
    in der Reihenfolge der Querschnitte auf der Seite."""
    zeichen = sorted((c for c in seite.chars if not c["upright"]), key=lambda c: c["top"])
    bloecke: list[list[dict]] = []
    for c in zeichen:
        if bloecke and c["top"] - bloecke[-1][-1]["top"] < 20:
            bloecke[-1].append(c)
        else:
            bloecke.append([c])
    out = []
    for b in bloecke:
        text = "".join(c["text"] for c in sorted(b, key=lambda c: -c["top"]))  # von unten nach oben
        if m := _Q_DATUM.search(text):
            out.append(date(int(m[3]), int(m[2]), int(m[1])))
    return out


def lese_abschrift(pfad: Path, knoten: dict[int, Knoten]) -> None:
    """Werte der Bildseiten (Abschrift) zu den Knotenpunkten; Textseiten gehen vor."""
    with open(pfad, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            k = knoten.setdefault(int(r["knotenpunkt"]), Knoten(int(r["knotenpunkt"])))
            if int(r["seite"]) in k.seiten:
                continue
            werte = [int(r[f"s{i}"]) if r[f"s{i}"] != "" else None for i in range(1, 13)]
            a = r["abschnitt"]
            if a == "kopf":
                if k.datum is None and r["zeit"]:
                    k.datum = date.fromisoformat(r["zeit"])
                if not k.kopfname:
                    k.kopfname = r["text"]
            elif a == "viertelstunde":
                h, mi = map(int, r["zeit"].split(":"))
                minute = h * 60 + mi
                k.viertel[_fenster_von(minute)].setdefault(minute, {})[r["art"]] = werte
                k.aus_abschrift.add(_fenster_von(minute))
            elif a == "summe":
                fenster = "morgens" if r["zeit"] == "6-10" else "nachmittags"
                k.summen[(r["art"], fenster)] = werte
                k.aus_abschrift.add(fenster)
            elif a in ("davon_mo", "davon"):
                fenster = "morgens" if a == "davon_mo" else "nachmittags"
                k.davon[(r["art"], fenster)] = werte
                k.aus_abschrift.add(fenster)


def fenster_pruefen(k: Knoten, fenster: str) -> str | None:
    """None, wenn das Fenster vollständig ist und alle Summen trifft; sonst der Grund."""
    h0, h1 = FENSTER[fenster]
    viertel = k.viertel[fenster]
    soll = list(range(h0 * 60, h1 * 60, 15))
    if sorted(viertel) != soll or any(set(viertel[m]) != set(ARTEN) for m in soll):
        return "Viertelstunden unvollständig"
    da = [any(viertel[m][a][s] is not None for m in soll for a in ARTEN) for s in range(12)]
    if any(viertel[m][a][s] is None for m in soll for a in ARTEN for s in range(12) if da[s]):
        return "Strom nicht in jeder Viertelstunde gezählt"

    def summe(werte):
        return [sum(werte(s)) if da[s] else None for s in range(12)]

    je_art = {a: summe(lambda s, a=a: (viertel[m][a][s] for m in soll)) for a in ARTEN}
    # die Zeile „LKW m.A.“ fehlt in den Summen des Berichts je Art (s. o.)
    ohne = k.mit_anhaenger.get(fenster, [None] * 12)

    def plus(werte, art_oder_name):
        if werte is None or art_oder_name not in ("LKW", "Lkw"):
            return werte
        return [w + (ohne[s] or 0) if w is not None else None for s, w in enumerate(werte)]

    for a in ARTEN:
        if plus(k.davon.get((a, fenster)), a) != je_art[a]:
            return f"Summe {a} trifft „davon“ nicht"
    for name, arten in (("Kfz", ARTEN), ("Pkw", ("PKW", "KRAD")), ("Lkw", ("LIEFERWAGEN", "LKW"))):
        if plus(k.summen.get((name, fenster)), name) != summe(
            lambda s, arten=arten: (je_art[a][s] for a in arten)
        ):
            return f"„Summe {name}/4h“ passt nicht"
    return None


def lese(
    quelle: dict, pfade: Pfade, bericht: Bericht | None = None, abschrift: Path = ABSCHRIFT
) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    orte = quelle.get("orte", {})
    for datei in quelle["dateien"]:
        pfad = pfade.roh / quelle["code"] / datei["datei"]
        if not pfad.exists():
            continue
        knoten, quer = lese_textseiten(pfad)
        lese_abschrift(abschrift, knoten)
        for nr in sorted(knoten):
            k = knoten[nr]
            bericht.knoten += 1
            gut = []
            for fenster in FENSTER:
                grund = fenster_pruefen(k, fenster)
                if grund:
                    bericht.fenster_falsch.append(f"K{nr} {fenster}: {grund}")
                    continue
                gut.append(fenster)
                bericht.fenster_gut += 1
                bericht.aus_abschrift += fenster in k.aus_abschrift
            if not gut or k.datum is None:
                continue
            stunden: dict[int, tuple[int, int]] = {}
            for fenster in gut:
                for m, arten in k.viertel[fenster].items():
                    kfz, sv = stunden.get(m // 60, (0, 0))
                    stunden[m // 60] = (
                        kfz + sum(x or 0 for v in arten.values() for x in v),
                        sv + sum(x or 0 for x in arten["LKW"]),
                    )
            yield _zaehlung(
                quelle,
                datei,
                f"K{nr}",
                "K",
                k.name,
                k.datum,
                stunden,
                gut,
                orte,
                bericht,
                arme=[a for a in k.arme if a],
                hinweise=_hinweise_knoten(k, gut),
            )
        for q in quer:
            bericht.querschnitte += 1
            summe = sum(q.anzahl.values())
            falsch = [h for h in q.stunden if sum(q.stunden[h].values()) != q.anzahl[h]]
            if len(q.stunden) != 24 or falsch or q.summe != summe or q.datum is None:
                bericht.q_falsch.append(
                    f"Q{q.nummer} {q.name}: Stunden {falsch}, Summe {q.summe} statt {summe}"
                )
                continue
            stunden = {h: (q.anzahl[h], q.stunden[h]["LKW"]) for h in range(24)}
            yield _zaehlung(
                quelle,
                datei,
                f"Q{q.nummer}",
                "Q",
                f"{q.name} (Querschnitt {q.nummer})",
                q.datum,
                stunden,
                ["ganztags"],
                orte,
                bericht,
                arme=[],
                hinweise=[],
            )


def _hinweise_knoten(k: Knoten, gut: list[str]) -> list[str]:
    out = []
    if k.datum == date(2019, 9, 17):
        out.append(
            "Der Bericht nennt „Do. 17.09.2019“; der 17.09.2019 war ein Dienstag – das Datum gilt."
        )
    if len(gut) == 1:
        out.append(
            f"Nur {'6–10' if gut[0] == 'morgens' else '15–19'} Uhr: das andere Zählfenster "
            "trifft die Summen des Berichts nicht."
        )
    return out


def _zaehlung(
    quelle, datei, kennung, typ, name, datum, stunden, fenster, orte, bericht, arme, hinweise
):
    ort = orte.get(kennung) or {}
    if not ort:
        bericht.ohne_lage.append(kennung)
    h0, h1 = min(stunden), max(stunden)
    if fenster == ["ganztags"]:
        zf = [(0, 24 * 60)]
    else:
        zf = [(FENSTER[f][0] * 60, FENSTER[f][1] * 60) for f in fenster]
    return Zaehlung(
        quelle=quelle["code"],
        kennung=f"{kennung}_{datum:%Y%m%d}",
        stelle_roh=kennung,
        name=name,
        typ=typ,
        lon=ort.get("lon"),
        lat=ort.get("lat"),
        lage="geokodiert" if ort else None,
        datum=datum,
        fenster=zf,
        intervall=15 if typ == "K" else 60,
        h0=h0,
        stunden={
            "kfz": [stunden[h][0] if h in stunden else None for h in range(h0, h1 + 1)],
            "sv": [stunden[h][1] if h in stunden else None for h in range(h0, h1 + 1)],
        },
        land=quelle["land"],
        richtungen=len(arme) if typ == "K" else 2,
        kategorien="Pkw, Krad, Lieferwagen, Lkw – Schwerverkehr = Lkw (Busse und Lastzüge sind "
        "keine eigene Art); Rad und Fuß nicht gezählt"
        + ("" if typ == "K" else "; beide Richtungen zusammen"),
        rohdatei=datei.get("url"),
        bemerkung=f"Verkehrszählung für die Verkehrsuntersuchung im Kernort per Video "
        f"({'Knotenpunkt' if typ == 'K' else 'Querschnitt'} {kennung[1:]})",
        hinweise=hinweise + list(ort.get("hinweise", [])),
        zusatz={"datei": datei["datei"], "arme": arme, "genauigkeit": ort.get("genauigkeit")},
    )
