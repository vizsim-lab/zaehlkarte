"""Münster: ein Zählblatt als XLS lesen (Knotenstromplan, 2000–2012). Gemeinsames in `muenster`.

Ein Blatt ist ein Knotenstromplan mit zwei Hälften, links und rechts je eine Stunde
(„Spitzenstunde: 07.00 - 08.00 Uhr“, meist 7–8 und 16–17 Uhr). Je Knotenarm zwei Tabellen
nach Fahrzeugart (Kfz, Pkw, Bus, Lkw, Lz, Krad, Rad): „S“ = Zufahrt (Summe der Ströme aus dem
Arm), „Q“ = Querschnitt (Zu- und Abfahrt). Die Knotensumme einer Stunde ist die Summe der
Zufahrten. Die Tabellen liest der Leser über die Beschriftungen „S“/„Q“ und die
Kategorie-Namen daneben, nicht über feste Zellen – die Vorlagen (2, 3 oder 4 Arme,
verschoben) unterscheiden sich.

- Kfz = Pkw + Bus + Lkw + Lz + Krad, nachgerechnet. In einigen Blättern sind Formeln falsch:
  mal fehlt ein Strom in der Kfz-Zelle (Kfz 26 bei 315 Pkw), mal in den Fahrzeugarten – je
  Arm gilt dann der größere Wert (beide Summen stehen im Hinweis).
- Schwerverkehr = Bus + Lkw + Lz.
- Eine Stunde, in der alle Kfz-Werte 0 sind, gilt als nicht gezählt (leere Vorlage) – im
  Hauptverkehrsnetz gibt es keine Spitzenstunde ohne ein einziges Kfz.
- Fehlen einem Arm die Beschriftungen S/Q oder die Kategorie-Namen, hilft die gespiegelte
  Blatthälfte bzw. die feste Reihenfolge der Kategorien (nur, wenn die Kfz-Zelle passt).
- Es zählt das erste Blatt; ein Blatt „Radverkehr“ (nur Rad, eigene Armaufteilung) wird
  eigens gelesen, weitere Blätter mit anderen Stunden oder Werten nur genannt.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

# Reihenfolge in allen Vorlagen (vom S weg); neuere PDFs (2017) haben nur Kfz, Pkw und SV
REIHENFOLGE = ("Kfz", "Pkw", "Bus", "Lkw", "Lz", "Krad", "Rad")
KATEGORIEN = (*REIHENFOLGE, "SV")
FAHRZEUGE = ("Pkw", "Bus", "Lkw", "Lz", "Krad")  # Kfz = ihre Summe
SCHWER = ("Bus", "Lkw", "Lz")
_STUNDE = re.compile(r"(\d{1,2})[.:](\d{2})\s*[-–]\s*(\d{1,2})[.:](\d{2})")
_WOCHENTAG = {"mo": 0, "di": 1, "mi": 2, "do": 3, "fr": 4, "sa": 5, "so": 6}


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
    for i in range(1, len(REIHENFOLGE) + 1):
        rr, cc = r + dr * i, c + dc * i
        v = _zahl(g(rr, cc))
        if v is None:
            break
        kat = None if ohne else _beschriftung(g, rr, cc, senkrecht=dr != 0)
        if kat is None and i == 1:
            ohne = True
        if ohne:
            kat = REIHENFOLGE[i - 1]
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


def _fahrzeugsumme(s: dict[str, int]) -> int | None:
    """Summe der Fahrzeugarten eines Arms (Pkw + Bus + Lkw + Lz + Krad, sonst Pkw + SV)."""
    if all(k in s for k in FAHRZEUGE):
        return sum(s[k] for k in FAHRZEUGE)
    if "Pkw" in s and "SV" in s:
        return s["Pkw"] + s["SV"]
    return None


def summen(liste: list[dict]) -> dict[str, int | None]:
    """Knotensummen einer Hälfte aus den Zufahrten (S) aller Arme; None = nicht gezählt.

    Kfz je Arm: Kfz-Zelle und Summe der Fahrzeugarten, wo beide da sind und abweichen der
    größere Wert – die Formelfehler der Zählblätter lassen Ströme aus (mal fehlt ein Strom in
    der Kfz-Zelle, mal in den Fahrzeugarten); `kfz_quelle` und `kfz_arten` halten beide Summen
    für den Hinweis. Schwerverkehr = Bus + Lkw + Lz (oder die Spalte SV) – ein Arm ganz ohne
    Kfz zählt dabei als 0."""
    kfz: int | None = 0
    sv: int | None = 0
    kfz_quelle: int | None = 0
    kfz_arten: int | None = 0
    rad: int | None = 0
    for arm in liste:
        s = arm["s"]
        arten = _fahrzeugsumme(s)
        zelle = s.get("Kfz")
        kfz_arm = max(v for v in (arten, zelle) if v is not None) if (arten, zelle) != (
            None, None) else None
        kfz = _plus(kfz, kfz_arm)
        if all(k in s for k in SCHWER):
            sv = _plus(sv, sum(s[k] for k in SCHWER))
        elif "SV" in s:
            sv = _plus(sv, s["SV"])
        elif kfz_arm != 0:
            sv = None
        kfz_quelle = _plus(kfz_quelle, zelle)
        kfz_arten = _plus(kfz_arten, arten)
        rad = _plus(rad, s.get("Rad"))
    return {"kfz": kfz, "sv": sv, "kfz_quelle": kfz_quelle, "kfz_arten": kfz_arten, "rad": rad}


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
