"""Münster: manuelle Kfz-Knotenpunktzählungen der Stadt (Open Data, XLS 2000–2012).

Quelle: ZIP „Verkehrszählung“ (je Zählung eine XLS oder PDF; Dateiname = Knotennummer und
Zähltag, `<Knoten>_<TTMM>_<JJJJ>_<lfd. Nr.>…`) und `Zählstellen.csv` (Knotennummer, UTM 32N,
Lagebezeichnung). Gezählt von Hand (meist Studierende und Rentner) während der
Hauptverkehrszeiten im Hauptverkehrsstraßennetz.

Ein Blatt ist ein Knotenstromplan mit zwei Hälften, links und rechts je eine Stunde
(„Spitzenstunde: 07.00 - 08.00 Uhr“, meist 7–8 und 16–17 Uhr). Je Knotenarm zwei Tabellen
nach Fahrzeugart (Kfz, Pkw, Bus, Lkw, Lz, Krad, Rad): „S“ = Zufahrt (Summe der Ströme aus dem
Arm), „Q“ = Querschnitt (Zu- und Abfahrt). Die Knotensumme einer Stunde ist die Summe der
Zufahrten. Die Tabellen liest der Adapter über die Beschriftungen „S“/„Q“ und die
Kategorie-Namen daneben, nicht über feste Zellen – die Vorlagen (2, 3 oder 4 Arme,
verschoben) unterscheiden sich.

- Kfz = Pkw + Bus + Lkw + Lz + Krad, nachgerechnet: Die Kfz-Zelle ist in einigen Blättern
  falsch verformelt (dann ein Hinweis mit beiden Werten).
- Schwerverkehr = Bus + Lkw + Lz.
- Eine Stunde, in der alle Kfz-Werte 0 sind, gilt als nicht gezählt (leere Vorlage) – im
  Hauptverkehrsnetz gibt es keine Spitzenstunde ohne ein einziges Kfz.
- Rad: Die Spalte „Rad“ der Kfz-Blätter ist nicht die ganze Radmenge – wo die Stadt den
  Radverkehr eigens gezählt hat (Blatt „Radverkehr“), liegt sie deutlich darunter oder steht
  auf 0. Sie geht deshalb nicht als Radverkehr in die Karte, sondern steht im Hinweis. Ein
  Blatt „Radverkehr“ (nur Rad, eigene Armaufteilung) gilt als Radzählung, wenn es zum
  selben Zähltag gehört (eins ist die Kopie aus einer anderen Datei).
- Es zählt das erste Blatt. Weitere Blätter mit anderen Stunden oder Werten nennt ein Hinweis.
- Zähltag aus dem Dateinamen. Ausnahmen, je mit Hinweis: Das Datum im Namen gibt es nicht
  (31.04.) oder es ist ein Wochenende, während das Zählblatt einen Werktag nennt – dann gilt
  das Blatt; oder der Name nennt zwei Daten und das Blatt bestätigt das zweite (so stehen
  einige Sonntagszählungen von 2011 unter dem Datum des Mittwochs davor).
- Lage aus der CSV; fehlt der Knoten dort, aus den Gauß-Krüger-Koordinaten im Blatt, über eine
  an den übrigen Knoten angepasste affine Abbildung auf UTM.
- Die PDFs (2010–2020) liest der Adapter noch nicht.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.koordinaten import affin, affin_anpassen, utm_zu_wgs84
from zaehlkarte.modell import Zaehlung

KATEGORIEN = ("Kfz", "Pkw", "Bus", "Lkw", "Lz", "Krad", "Rad")
FAHRZEUGE = ("Pkw", "Bus", "Lkw", "Lz", "Krad")  # Kfz = ihre Summe
SCHWER = ("Bus", "Lkw", "Lz")
_DATEI = re.compile(r"^(\d{6,8})[_-](\d{2})(\d{2})[_.-](\d{4})")
_ZWEITES_DATUM = re.compile(r"_(\d{6,8})_(\d{2})(\d{2})_(\d{4})$")
_STUNDE = re.compile(r"(\d{1,2})[.:](\d{2})\s*[-–]\s*(\d{1,2})[.:](\d{2})")
_WOCHENTAG = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}
_TAGNAME = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
# Gauß-Krüger-Werte im Blatt, die zu Münster passen können (Tippfehler fallen heraus)
_GK_RECHTS = (3390000, 3430000)
_GK_HOCH = (5735000, 5780000)


@dataclass
class Bericht:
    dateien: int = 0
    ohne_knoten: list[str] = field(default_factory=list)
    unlesbar: list[str] = field(default_factory=list)
    doppelt: list[str] = field(default_factory=list)
    kfz_korrigiert: int = 0
    datum: list[str] = field(default_factory=list)
    stunden_leer: int = 0
    rad_blatt: int = 0
    rad_blatt_fremd: list[str] = field(default_factory=list)
    lage_csv: int = 0
    lage_blatt: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    anpassung: str = ""

    def zeilen(self) -> list[str]:
        out = [
            f"{self.dateien} XLS-Dateien gelesen",
            f"Lage: {self.lage_csv} aus der CSV, {self.lage_blatt} aus dem Blatt, "
            f"{len(self.ohne_lage)} ohne",
            f"Kfz nachgerechnet (Quelle weicht ab): {self.kfz_korrigiert}",
            f"Stunden mit lauter Nullen (nicht gezählt): {self.stunden_leer}",
            f"Zähltag mit Hinweis: {len(self.datum)}",
            f"mit Blatt „Radverkehr“: {self.rad_blatt} (fremd: {len(self.rad_blatt_fremd)})",
        ]
        if self.anpassung:
            out.append(f"Gauß-Krüger -> UTM: {self.anpassung}")
        out += [f"ohne Knotennummer/Datum: {d}" for d in self.ohne_knoten[:5]]
        out += [f"nicht lesbar: {d}" for d in self.unlesbar[:10]]
        out += [f"doppelt: {d}" for d in self.doppelt[:5]]
        return out


# --------------------------------------------------------------------------- Blatt lesen


class Gitter:
    """Zellwerte eines Blatts mit Zugriff außerhalb der Ränder (-> None)."""

    def __init__(self, zeilen: list[list[object]]):
        self.zeilen = zeilen

    @classmethod
    def aus_xlrd(cls, blatt) -> Gitter:
        return cls([blatt.row_values(r) for r in range(blatt.nrows)])

    def __call__(self, r: int, c: int) -> object:
        if 0 <= r < len(self.zeilen) and 0 <= c < len(self.zeilen[r]):
            v = self.zeilen[r][c]
            return None if v == "" else v
        return None

    def zellen(self) -> Iterator[tuple[int, int, object]]:
        for r, zeile in enumerate(self.zeilen):
            for c, v in enumerate(zeile):
                if v not in ("", None):
                    yield r, c, v


def _zahl(v: object) -> int | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int | float):
        return int(round(v))
    s = str(v).strip()
    return int(s) if s.isdigit() else None


def _text(v: object) -> str:
    return v.strip() if isinstance(v, str) else ""


def _uhr(h: int) -> str:
    return f"{h}–{h + 1} Uhr"


def _beschriftung(g: Gitter, r: int, c: int, senkrecht: bool) -> str | None:
    """Kategorie zu einer Wertzelle: bei senkrechten Tabellen links in derselben Zeile, bei
    waagerechten darüber in derselben Spalte – die erste Textzelle."""
    schritte = range(c - 1, -1, -1) if senkrecht else range(r - 1, -1, -1)
    for k in schritte:
        v = g(r, k) if senkrecht else g(k, c)
        if v is None or _zahl(v) is not None:
            continue
        t = _text(v)
        return t if t in KATEGORIEN else None
    return None


def _stimmig(werte: dict[str, int]) -> bool:
    """Kfz-Zelle passt zur Summe der Fahrzeugarten (für Tabellen ohne Beschriftung)."""
    if "Kfz" not in werte or not all(k in werte for k in FAHRZEUGE):
        return False
    summe = sum(werte[k] for k in FAHRZEUGE)
    return abs(werte["Kfz"] - summe) <= max(2, 0.02 * summe)


def _tabelle(g: Gitter, r: int, c: int, dr: int, dc: int) -> dict[str, int]:
    """Werte ab der Zelle neben (r, c) in Richtung (dr, dc), je Kategorie.

    Die Kategorie steht neben jeder Wertzelle. Fehlt die Beschriftung ganz (eine Vorlage hat
    die Spalte überschrieben), gilt die Reihenfolge aller Vorlagen – Kfz, Pkw, Bus, Lkw, Lz,
    Krad, Rad vom S weg –, aber nur, wenn die Kfz-Zelle zur Summe der Fahrzeugarten passt."""
    werte: dict[str, int] = {}
    ohne = False
    for i in range(1, len(KATEGORIEN) + 1):
        rr, cc = r + dr * i, c + dc * i
        v = _zahl(g(rr, cc))
        if v is None:
            break
        kat = None if ohne else _beschriftung(g, rr, cc, senkrecht=dr != 0)
        if kat is None and i == 1:
            ohne = True
        if ohne:
            kat = KATEGORIEN[i - 1]
        if kat is None or kat in werte:
            break
        werte[kat] = v
    if ohne and not _stimmig(werte):
        return {}
    return werte


# Lage der Beschriftung Q zu S -> wo die Werte stehen
RICHTUNGEN = {
    "oben": ((0, -1), (1, 0)),  # Q S nebeneinander, Werte darunter
    "unten": ((0, 1), (-1, 0)),  # S Q nebeneinander, Werte darüber
    "rechts": ((-1, 0), (0, -1)),  # Q über S, Werte links davon
    "links": ((1, 0), (0, 1)),  # S über Q, Werte rechts davon
}


def _arm(g: Gitter, r: int, c: int, typ: str) -> dict | None:
    (qdr, qdc), (dr, dc) = RICHTUNGEN[typ]
    s = _tabelle(g, r, c, dr, dc)
    if not s:
        return None
    return {"r": r, "c": c, "typ": typ, "s": s, "q": _tabelle(g, r + qdr, c + qdc, dr, dc)}


def arme(g: Gitter) -> list[dict]:
    """Je Knotenarm: Zeile/Spalte der Beschriftung S, Lage (oben/unten/rechts/links),
    Zufahrt S und Querschnitt Q."""
    out = []
    for r, c, v in g.zellen():
        if _text(v) != "S":
            continue
        for typ, ((qdr, qdc), _) in RICHTUNGEN.items():
            if _text(g(r + qdr, c + qdc)) == "Q":
                arm = _arm(g, r, c, typ)
                if arm:
                    out.append(arm)
                break
    return out


def _versatz(alle: list[dict]) -> int | None:
    """Spaltenabstand der beiden Hälften: häufigster Abstand gleichartiger Arme einer Zeile."""
    abstaende = Counter(
        b["c"] - a["c"]
        for a in alle
        for b in alle
        if a["typ"] == b["typ"] and a["r"] == b["r"] and 20 <= b["c"] - a["c"] <= 40
    )
    return abstaende.most_common(1)[0][0] if abstaende else None


def haelften(g: Gitter, alle: list[dict], grenze: int) -> tuple[list[dict], list[dict], int]:
    """Arme der linken und rechten Blatthälfte. Beide Hälften zeigen denselben Knoten, also
    dieselben Arme: Fehlt einem Arm das Gegenstück (Beschriftung S/Q gelöscht), wird es an der
    gespiegelten Stelle gelesen. Rückgabe: (links, rechts, Anzahl ergänzter Arme)."""
    versatz = _versatz(alle) or grenze
    links = [a for a in alle if a["c"] < versatz]
    rechts = [a for a in alle if a["c"] >= versatz]
    ergaenzt = 0
    for eigene, andere, schritt in ((links, rechts, versatz), (rechts, links, -versatz)):
        for a in list(eigene):
            ziel = (a["r"], a["c"] + schritt)
            if any((b["r"], b["c"]) == ziel and b["typ"] == a["typ"] for b in andere):
                continue
            if g(*ziel) is not None:  # dort steht etwas anderes als eine leere Zelle
                continue
            zwilling = _arm(g, *ziel, a["typ"])
            if zwilling:
                andere.append(zwilling)
                ergaenzt += 1
    return links, rechts, ergaenzt


def _texte(g: Gitter, bis_zeile: int = 12) -> list[tuple[int, int, str]]:
    return [(r, c, _text(v)) for r, c, v in g.zellen() if r < bis_zeile and _text(v)]


def stunden_der_haelften(g: Gitter) -> list[tuple[int, int | None, str]]:
    """[(Spalte, Stunde oder None, Text)] der „Spitzenstunde“-Angaben, links nach rechts.
    Stunde nur bei einer vollen Uhrstunde (7.00–8.00), sonst None."""
    out = []
    for _, c, t in sorted(_texte(g), key=lambda x: x[1]):
        if "pitzenstunde" not in t:
            continue
        m = _STUNDE.search(t)
        stunde = None
        if m:
            h1, m1, h2, m2 = (int(x) for x in m.groups())
            if m1 == 0 and m2 == 0 and h2 == h1 + 1:
                stunde = h1
        out.append((c, stunde, " ".join(t.split())))
    return out


def _plus(summe: int | None, wert: int | None) -> int | None:
    return None if summe is None or wert is None else summe + wert


def summen(liste: list[dict]) -> dict[str, int | None]:
    """Knotensummen einer Hälfte aus den Zufahrten (S) aller Arme; None = nicht gezählt.

    Kfz = Summe der Fahrzeugarten (sonst die Kfz-Zelle); Schwerverkehr = Bus + Lkw + Lz – ein
    Arm ganz ohne Kfz zählt dabei als 0."""
    kfz: int | None = 0
    sv: int | None = 0
    kfz_quelle: int | None = 0
    rad: int | None = 0
    for arm in liste:
        s = arm["s"]
        if all(k in s for k in FAHRZEUGE):
            kfz_arm = sum(s[k] for k in FAHRZEUGE)
        else:
            kfz_arm = s.get("Kfz")
        kfz = _plus(kfz, kfz_arm)
        if all(k in s for k in SCHWER):
            sv = _plus(sv, sum(s[k] for k in SCHWER))
        elif kfz_arm != 0:
            sv = None
        kfz_quelle = _plus(kfz_quelle, s.get("Kfz"))
        rad = _plus(rad, s.get("Rad"))
    return {"kfz": kfz, "sv": sv, "kfz_quelle": kfz_quelle, "rad": rad}


def lese_blatt(g: Gitter, gruppe: str = "kfz") -> dict:
    """Ein Blatt -> {stunden: {Stunde: Summen}, fehlt: [Texte], leer: n, arme: n}.

    `gruppe` muss je Stunde gezählt sein („kfz“ im Kfz-Blatt, „rad“ im Blatt Radverkehr);
    lauter Nullen gelten als nicht gezählt."""
    angaben = stunden_der_haelften(g)
    if not angaben:
        return {"stunden": {}, "fehlt": ["keine Angabe „Spitzenstunde“"], "leer": 0, "arme": 0,
                "ergaenzt": 0}
    # Ersatz-Grenze, falls kein Arm ein Gegenstück hat: die rechte Angabe steht 3 Spalten
    # hinter dem Anfang ihrer Hälfte
    grenze = angaben[1][0] - 3 if len(angaben) > 1 else 10**6
    links, rechts, ergaenzt = haelften(g, arme(g), grenze)
    stunden: dict[int, dict] = {}
    fehlt = []
    leer = 0
    for (_, stunde, text), liste in zip(angaben[:2], (links, rechts), strict=False):
        if stunde is None:
            fehlt.append(f"eine Blatthälfte ohne volle Uhrstunde („{text}“)")
            continue
        werte = summen(liste) if liste else None
        if werte is None or werte[gruppe] is None:
            fehlt.append(f"{_uhr(stunde)} (Tabellen unvollständig)")
        elif werte[gruppe] == 0:
            leer += 1
            fehlt.append(f"{_uhr(stunde)} (lauter Nullen – als nicht gezählt gewertet)")
        elif stunde in stunden:
            fehlt.append(f"{_uhr(stunde)} (zweimal im Blatt)")
        else:
            stunden[stunde] = werte
    return {"stunden": stunden, "fehlt": fehlt, "leer": leer,
            "arme": max(len(links), len(rechts)), "ergaenzt": ergaenzt}


def kopf(g: Gitter, datemode: int = 0) -> dict:
    """Lage, Zähltag (Excel-Datum und Wochentag), Knotennummer, GK-Koordinaten, Armnamen."""
    import xlrd

    out: dict = {"armnamen": {}}
    for r, c, v in g.zellen():
        t = _text(v)
        if r < 8 and t.startswith("Lage der Zählstelle"):
            rest = t.split(":", 1)[1].strip() if ":" in t else ""
            if not rest:
                rest = next((_text(g(r, k)) for k in range(c + 1, c + 12) if _text(g(r, k))), "")
            out["name"] = rest
        elif r < 8 and t.startswith("Zähltag"):
            for k in range(c + 1, c + 9):
                w = g(r, k)
                if isinstance(w, float) and 30000 < w < 50000:
                    out["datum"] = xlrd.xldate_as_datetime(w, datemode).date()
                    break
            tag = (t.split(":", 1)[1].strip() if ":" in t else "") or _text(g(r, c + 3))
            m = re.match(r"\s*([A-Za-z]{2})", tag)
            if m and m.group(1).lower() in _WOCHENTAG:
                out["wochentag"] = _WOCHENTAG[m.group(1).lower()]
        elif r < 8 and t.startswith("Knot"):
            nr = next((_zahl(g(r, k)) for k in range(c + 1, c + 8) if _zahl(g(r, k))), None)
            out["knoten"] = str(nr) if nr else None
        elif r < 8 and t == "X":
            out["gk_x"] = next((g(r, k) for k in range(c + 1, c + 3) if _zahl(g(r, k))), None)
        elif r < 8 and t == "Y":
            out["gk_y"] = next((g(r, k) for k in range(c + 1, c + 3) if _zahl(g(r, k))), None)
        elif r > 30 and re.fullmatch(r"[A-F]\s*=", t):
            name = _text(g(r, c + 1))
            if name:
                out["armnamen"][t[0]] = name
    return out


def name_schoen(roh: str) -> str:
    """'Freckenhorster Straße/ Telgter Straße' -> 'Freckenhorster Straße / Telgter Straße'."""
    return re.sub(r"\s*/\s*", " / ", " ".join(roh.split())).strip(" /")


# --------------------------------------------------------------------------- Datei lesen


def lese_datei(pfad: Path) -> dict:
    """Eine XLS -> Kopf, Stunden je Blatt („kfz“ = erstes Blatt, „rad“ = Blatt Radverkehr)."""
    import xlrd

    wb = xlrd.open_workbook(str(pfad))
    blaetter = wb.sheets()
    erstes = Gitter.aus_xlrd(blaetter[0])
    out = {
        "kopf": kopf(erstes, wb.datemode),
        "blatt": blaetter[0].name,
        "kfz": lese_blatt(erstes),
        "rad": None,
        "weitere": [],
    }
    for b in blaetter[1:]:
        g = Gitter.aus_xlrd(b)
        if b.name.strip().lower() == "radverkehr" or any(
            "NUR RADVERKEHR" in t.upper() for _, _, t in _texte(g)
        ):
            out["rad"] = {**lese_blatt(g, "rad"), "kopf": kopf(g, wb.datemode)}
            continue
        weiteres = lese_blatt(g)
        gleich = {h: w["kfz"] for h, w in weiteres["stunden"].items()} == {
            h: w["kfz"] for h, w in out["kfz"]["stunden"].items()
        }
        if not gleich:
            out["weitere"].append(b.name.strip())
    return out


def datei_kennung(pfad: Path) -> str:
    """Dateiname ohne Endung und ohne Ordnerpräfix aus dem ZIP („Verkehrszählung__“)."""
    return re.sub(r"^Verkehrszählung__", "", pfad.stem)


def _datum(tag: str, monat: str, jahr: str) -> date | None:
    try:
        return date(int(jahr), int(monat), int(tag))
    except ValueError:
        return None


def aus_dateiname(kennung: str) -> tuple[str | None, date | None, date | None]:
    """(Knoten, Datum, zweites Datum am Ende des Namens oder None)."""
    m = _DATEI.match(kennung)
    if not m:
        return None, None, None
    m2 = _ZWEITES_DATUM.search(kennung[m.end():])
    zweites = _datum(*m2.group(2, 3, 4)) if m2 and m2.group(1) == m.group(1) else None
    return m.group(1), _datum(*m.group(2, 3, 4)), zweites


def zaehltag(
    name: date | None, zweites: date | None, blatt: date | None, wochentag: int | None
) -> tuple[date | None, str | None]:
    """Zähltag und, wo die Angaben abweichen, ein Hinweis (siehe Modulkopf)."""

    def den(d: date | None) -> str:
        return f"den {d:%d.%m.%Y}" if d else "ein ungültiges Datum"

    if name is not None and blatt in (None, name) and zweites in (None, name):
        tag, hinweis = name, None
    elif zweites is not None and zweites == blatt:
        tag = zweites
        hinweis = (f"Der Dateiname nennt {den(name)} und {den(zweites)}, das Zählblatt "
                   f"{den(zweites)}; die Karte nimmt {den(zweites)}.")
    elif blatt is not None and blatt.weekday() < 5 and (name is None or name.weekday() >= 5):
        tag = blatt
        grund = f" (ein {_TAGNAME[name.weekday()]})" if name else ""
        hinweis = (f"Der Dateiname nennt {den(name)}{grund}; die Karte folgt dem Zählblatt "
                   f"({den(blatt)}).")
    elif name is not None:
        tag = name
        hinweis = (f"Das Zählblatt nennt als Zähltag {den(blatt)}; die Karte folgt dem "
                   "Dateinamen." if blatt is not None and blatt != name else None)
    else:
        return None, None
    if tag.weekday() >= 5 and wochentag is not None and wochentag < 5:
        zusatz = (f"Laut Zählblatt war es ein {_TAGNAME[wochentag]} – der Zähltag "
                  f"({_TAGNAME[tag.weekday()]}, {tag:%d.%m.%Y}) ist unsicher.")
        hinweis = f"{hinweis} {zusatz}" if hinweis else zusatz
    return tag, hinweis


def lese_positionen(pfad: Path) -> dict[str, dict]:
    """Zählstellen.csv: KNOTEN, RECHTSWERT, HOCHWERT (UTM 32N), ZAEHLSTELLE."""
    out = {}
    with pfad.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                ost, nord = float(r["RECHTSWERT"]), float(r["HOCHWERT"])
            except (TypeError, ValueError):
                continue
            out[r["KNOTEN"].strip()] = {
                "utm": (ost, nord),
                "name": " ".join((r.get("ZAEHLSTELLE") or "").split()),
            }
    return out


def _gk(k: dict) -> tuple[float, float] | None:
    x, y = k.get("gk_x"), k.get("gk_y")
    if isinstance(x, float) and isinstance(y, float):
        if _GK_RECHTS[0] < x < _GK_RECHTS[1] and _GK_HOCH[0] < y < _GK_HOCH[1]:
            return x, y
    return None


def _fenster(stunden: list[int]) -> list[tuple[int, int]]:
    """[7, 8, 16] -> [(420, 540), (960, 1020)] – aneinandergrenzende Stunden zusammen."""
    out: list[list[int]] = []
    for h in sorted(stunden):
        if out and out[-1][1] == h * 60:
            out[-1][1] = h * 60 + 60
        else:
            out.append([h * 60, h * 60 + 60])
    return [(a, b) for a, b in out]


def _reihe(werte: dict[int, dict], gruppe: str, h0: int, laenge: int) -> list[int | None]:
    return [werte[h0 + i][gruppe] if h0 + i in werte else None for i in range(laenge)]


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "muenster"
    positionen = lese_positionen(ordner / quelle["positionen"]["datei"])
    gelesen = []
    for pfad in sorted(p for p in (ordner / "zip").rglob("*") if p.suffix.lower() == ".xls"):
        kennung = datei_kennung(pfad)
        knoten, im_namen, zweites = aus_dateiname(kennung)
        if knoten is None:
            bericht.ohne_knoten.append(kennung)
            continue
        try:
            d = lese_datei(pfad)
        except Exception as e:  # noqa: BLE001 – kaputte Datei überspringen, im Bericht
            bericht.unlesbar.append(f"{kennung}: {e}")
            continue
        bericht.dateien += 1
        bericht.stunden_leer += d["kfz"]["leer"]
        tag, hinweis_tag = zaehltag(
            im_namen, zweites, d["kopf"].get("datum"), d["kopf"].get("wochentag")
        )
        if tag is None:
            bericht.ohne_knoten.append(kennung)
            continue
        if not d["kfz"]["stunden"]:
            bericht.unlesbar.append(f"{kennung}: {'; '.join(d['kfz']['fehlt'])}")
            continue
        if hinweis_tag:
            bericht.datum.append(kennung)
        gelesen.append((kennung, knoten, tag, hinweis_tag, d))

    # Gauß-Krüger aus dem Blatt -> UTM, angepasst an die Knoten, die in beiden stehen
    paare = [
        (gk, positionen[kn]["utm"])
        for _, kn, _, _, d in gelesen
        if kn in positionen and (gk := _gk(d["kopf"]))
    ]
    parameter = None
    if len(paare) >= 10:
        parameter, rms, n = affin_anpassen(paare)
        bericht.anpassung = f"{n} Paare, mittlerer Restfehler {rms:.0f} m"
        if rms > 30:
            parameter = None

    gesehen: dict[tuple, str] = {}
    for kennung, knoten, tag, hinweis_tag, d in gelesen:
        k = d["kopf"]
        st = d["kfz"]["stunden"]
        schluessel = (knoten, tag, tuple(sorted((h, w["kfz"]) for h, w in st.items())))
        if schluessel in gesehen:
            bericht.doppelt.append(f"{kennung} = {gesehen[schluessel]}")
            continue
        gesehen[schluessel] = kennung

        hinweise = [hinweis_tag] if hinweis_tag else []
        lon = lat = lage = None
        if knoten in positionen:
            lon, lat = utm_zu_wgs84(*positionen[knoten]["utm"])
            lage = "quelle"
            bericht.lage_csv += 1
        elif parameter and (gk := _gk(k)):
            lon, lat = utm_zu_wgs84(*affin(parameter, *gk))
            lage = "quelle"
            hinweise.append("Lage aus den Gauß-Krüger-Koordinaten im Zählblatt (der Knoten fehlt "
                            "in der Positionsdatei der Stadt).")
            bericht.lage_blatt += 1
        else:
            bericht.ohne_lage.append(kennung)

        abweichend = [
            f"{_uhr(h)}: Quelle {w['kfz_quelle']}, Summe {w['kfz']}"
            for h, w in sorted(st.items())
            if w["kfz_quelle"] is not None and w["kfz_quelle"] != w["kfz"]
        ]
        if abweichend:
            bericht.kfz_korrigiert += 1
            hinweise.append("Die Kfz-Summe der Quelle weicht von der Summe der Fahrzeugarten ab; "
                            "die Karte zeigt die Summe der Fahrzeugarten ("
                            + "; ".join(abweichend) + ").")

        rad_st: dict[int, dict] = {}
        rb = d["rad"]
        if rb and rb["stunden"]:
            rad_tag = rb["kopf"].get("datum")
            if rad_tag in (None, tag):
                rad_st = rb["stunden"]
                bericht.rad_blatt += 1
                hinweise.append("Rad aus dem eigenen Blatt „Radverkehr“ der Datei (eigene "
                                "Armaufteilung, nur Radverkehr).")
            else:
                bericht.rad_blatt_fremd.append(kennung)
                hinweise.append(f"Das Blatt „Radverkehr“ in der Datei gehört zu einer anderen "
                                f"Zählung ({rb['kopf'].get('name', '')}, {rad_tag:%d.%m.%Y}) und "
                                "fehlt deshalb.")
        if not rad_st:
            rad_kfz = [f"{_uhr(h)}: {w['rad']}" for h, w in sorted(st.items()) if w["rad"]]
            if rad_kfz:
                hinweise.append("Rad laut Spalte der Kfz-Zählung – keine vollständige "
                                "Radzählung, daher nicht in der Karte: " + "; ".join(rad_kfz) + ".")
        if d["kfz"]["fehlt"]:
            hinweise.append("Nicht übernommen: " + "; ".join(d["kfz"]["fehlt"]) + ".")
        if d["weitere"]:
            hinweise.append("Die Datei hat weitere Blätter mit anderen Zeiten oder Werten ("
                            + ", ".join(f"„{b}“" for b in d["weitere"])
                            + "); die Karte zeigt das erste.")

        alle_stunden = sorted(set(st) | set(rad_st))
        h0 = alle_stunden[0]
        laenge = alle_stunden[-1] - h0 + 1
        stunden = {"kfz": _reihe(st, "kfz", h0, laenge)}
        if all(w["sv"] is not None for w in st.values()):
            stunden["sv"] = _reihe(st, "sv", h0, laenge)
        if rad_st:
            stunden["rad"] = _reihe(rad_st, "rad", h0, laenge)

        n_arme = d["kfz"]["arme"]
        name = name_schoen(k.get("name") or positionen.get(knoten, {}).get("name") or knoten)
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=kennung,
            stelle_roh=knoten,
            name=name,
            typ="Q" if n_arme == 2 else "K",
            lon=lon,
            lat=lat,
            lage=lage,
            datum=tag,
            fenster=_fenster(alle_stunden),
            intervall=60,
            h0=h0,
            stunden=stunden,
            land=quelle["land"],
            richtungen=n_arme or None,
            kategorien="Pkw, Bus, Lkw, Lz (Lastzug), Krad" + (", Rad" if "rad" in stunden else ""),
            rohdatei=quelle.get("portal"),
            bemerkung=f"Datei im ZIP der Stadt: {kennung}.xls",
            hinweise=hinweise,
            zusatz={"datei": f"{kennung}.xls", "blatt": d["blatt"], "arme": k["armnamen"]},
        )
