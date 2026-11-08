"""Münster: die PDF-Fassung der Knotenstrompläne lesen (2010–2020).

Die PDFs sind Ausdrucke derselben Excel-Vorlagen wie die XLS (siehe `muenster_xls`), aber ohne
Zellraster: Der Leser arbeitet mit den Lagen der Wörter. Zu jeder Beschriftung „S“ gehört ein
„Q“ daneben (oben/unten/rechts/links wie im XLS-Leser), die Werte stehen in derselben Zeile
oder Spalte, und zu jedem Wert gehört die Kategorie-Beschriftung in derselben Zeile (links
davon) oder Spalte (darüber).

Senkrecht gesetzte Tabellen stehen gedreht im PDF. Gedrehte Zeichen werden je Drehrichtung
für sich zu Wörtern zusammengesetzt (gegen den Uhrzeigersinn: von unten nach oben gelesen),
sonst kämen sie rückwärts heraus („zfK“, „0301“). Als Zeilenlage gilt bei gedrehtem Text
der Textanfang (unten bzw. oben), weil Excel ihn an der Zellkante ausrichtet.

Was „dieselbe Spalte“ ist, entscheiden die Tabellenrahmen (senkrechte und waagerechte
Rahmenlinien = Zellgrenzen der Excel-Vorlage): Beschriftungen stehen linksbündig, Zahlen
rechtsbündig in derselben Zelle. Wo keine Rahmen sind, gilt ein Abstand von 4 pt.

Je Seite eine oder zwei Stunden; mehrseitige PDFs (eine Stunde je Seite) werden
zusammengeführt. Gelesen werden nur Seiten mit Knotenstromplan (Beschriftung
„Spitzenstunde“); Radar-Berichte („Class/Volume Report“) und Scans ohne Text nicht.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from zaehlkarte.adapters.muenster_xls import FAHRZEUGE, KATEGORIEN, _uhr, summen

_ZAHL = re.compile(r"^\d{1,3}(?:\.\d{3})+$|^\d+$")
_STUNDE = re.compile(r"Spitzenstunde:?\s*(\d{1,2})[.:](\d{2})\s*[-–]\s*(\d{1,2})[.:](\d{2})")
_TAG = re.compile(r"Zähltag:?\s*(?:(Mo|Di|Mi|Do|Fr|Sa|So)\.?)?\s*(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
_WOCHENTAG = {"Mo": 0, "Di": 1, "Mi": 2, "Do": 3, "Fr": 4, "Sa": 5, "So": 6}
_KNOTEN = re.compile(r"Knot\w*-?\s*Nr\.?\s*(?:\([^)]*\))?\s*(\d{6,8})")
_KOORD = re.compile(r"X\s*(\d{6,7})(?:[.,]\d+)?\s*Y\s*(\d{7})")
_DATEI_IM_TEXT = re.compile(r"\s*\S*\.xls\b.*$")
_ARM = re.compile(r"^([A-F])\s*=\s*(.+)$")
TOL = 4.0  # pt: gleiche Zeile/Spalte


_ZUSAMMEN = re.compile(r"(Kfz|Pkw|Bus|Lkw|Lz|Krad|Rad)")
BREIT = 40.0  # pt: breitere „Zellen“ sind Bereiche ohne Rahmen


@dataclass
class Wort:
    text: str
    x: float  # Spaltenlage (Mitte)
    y: float  # Zeilenlage (Mitte, bei gedrehtem Text der Textanfang)
    x0: float
    gedreht: bool
    x1: float = 0.0
    top: float = 0.0
    bottom: float = 0.0
    # Zelle zwischen senkrechten bzw. waagerechten Rahmenlinien (unbekannt: unendlich breit)
    spalte: tuple[float, float] = (float("-inf"), float("inf"))
    band: tuple[float, float] = (float("-inf"), float("inf"))

    @property
    def zahl(self) -> int | None:
        return int(self.text.replace(".", "")) if _ZAHL.match(self.text) else None

    def gleiche_spalte(self, other: Wort) -> bool:
        """Dieselbe Rahmenzelle, überlappende Breite (linksbündige Beschriftung über
        rechtsbündiger Zahl) oder höchstens 4 pt Abstand der Mitten."""
        if self.spalte == other.spalte and self.spalte[1] - self.spalte[0] <= BREIT:
            return True
        if min(self.x1, other.x1) - max(self.x0, other.x0) > 0.5:
            return True
        return abs(self.x - other.x) <= TOL

    def gleiche_zeile(self, other: Wort) -> bool:
        if self.band == other.band and self.band[1] - self.band[0] <= BREIT:
            return True
        return abs(self.y - other.y) <= TOL


def _kanten(werte: list[float]) -> list[float]:
    out: list[list[float]] = []
    for v in sorted(werte):
        if out and v - out[-1][-1] <= 1.5:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def _zelle(kanten: list[float], v: float) -> tuple[float, float]:
    import bisect

    i = bisect.bisect_right(kanten, v)
    links = kanten[i - 1] if i > 0 else float("-inf")
    return links, (kanten[i] if i < len(kanten) else float("inf"))


def worte(seite) -> list[Wort]:
    """Wörter einer Seite; gedrehte je Drehrichtung richtig herum zusammengesetzt, zusammen-
    gelaufene Beschriftungen („KradLz“) getrennt, jedes Wort in seiner Rahmenzelle."""
    linien = [*seite.rects, *seite.lines]
    senkrecht = _kanten([o["x0"] for o in linien if o["width"] < 1.5 and o["height"] > 3])
    waagerecht = _kanten([o["top"] for o in linien if o["height"] < 1.5 and o["width"] > 3])
    out = []
    gruppen = (
        (lambda c: c.get("upright", True), "ttb", "mitte"),
        (lambda c: not c.get("upright", True) and c["matrix"][1] > 0, "btt", "unten"),
        (lambda c: not c.get("upright", True) and c["matrix"][1] <= 0, "ttb", "oben"),
    )
    for wahl, richtung, anker in gruppen:
        teil = seite.filter(lambda o, wahl=wahl: o.get("object_type") != "char" or wahl(o))
        for w in teil.extract_words(x_tolerance=1, y_tolerance=2, char_dir_rotated=richtung):
            y = {"mitte": (w["top"] + w["bottom"]) / 2, "unten": w["bottom"], "oben": w["top"]}
            teile = _ZUSAMMEN.findall(w["text"])
            if anker == "mitte" and len(teile) > 1 and "".join(teile) == w["text"]:
                # zusammengelaufene Beschriftungen nach Buchstabenanteil aufteilen
                breite = (w["x1"] - w["x0"]) / len(w["text"])
                links = w["x0"]
                for t in teile:
                    rechts = links + breite * len(t)
                    out.append(Wort(t, (links + rechts) / 2, y[anker], links, False, rechts,
                                    w["top"], w["bottom"]))
                    links = rechts
                continue
            out.append(Wort(w["text"], (w["x0"] + w["x1"]) / 2, y[anker], w["x0"], anker != "mitte",
                            w["x1"], w["top"], w["bottom"]))
    for w in out:
        w.spalte = _zelle(senkrecht, w.x)
        w.band = _zelle(waagerecht, w.y)
    return out


def zeilen_text(ws: list[Wort]) -> list[tuple[float, float, str]]:
    """Aufrechte Wörter zu Textzeilen: [(y, x0 des ersten Worts, Text)]."""
    aufrecht = sorted((w for w in ws if not w.gedreht), key=lambda w: (w.y, w.x0))
    zeilen: list[list[Wort]] = []
    for w in aufrecht:
        if zeilen and abs(w.y - zeilen[-1][0].y) <= 2.5:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    out = []
    for z in zeilen:
        z.sort(key=lambda w: w.x0)
        out.append((z[0].y, z[0].x0, " ".join(w.text for w in z)))
    return out


def _werte_entlang(ws: list[Wort], s: Wort, typ: str) -> list[Wort]:
    """Wörter neben S in Leserichtung der Tabelle, nach Abstand."""
    if typ in ("oben", "unten"):
        nah = [w for w in ws if w is not s and w.gleiche_spalte(s)]
        nah = [w for w in nah if (w.y > s.y + 1 if typ == "oben" else w.y < s.y - 1)]
        return sorted(nah, key=lambda w: abs(w.y - s.y))
    nah = [w for w in ws if w is not s and abs(w.y - s.y) <= TOL]
    nah = [w for w in nah if (w.x < s.x - 1 if typ == "rechts" else w.x > s.x + 1)]
    return sorted(nah, key=lambda w: abs(w.x - s.x))


def _kategorie(etiketten: list[Wort], wert: Wort, senkrecht: bool) -> str | None:
    """Senkrechte Tabelle: Beschriftung links in derselben Zeile; waagerechte: darüber in
    derselben Spalte – die nächste."""
    if senkrecht:
        kandidaten = [e for e in etiketten if e.gleiche_zeile(wert) and e.x < wert.x]
        return min(kandidaten, key=lambda e: wert.x - e.x).text if kandidaten else None
    kandidaten = [e for e in etiketten if e.gleiche_spalte(wert) and e.y < wert.y]
    return min(kandidaten, key=lambda e: wert.y - e.y).text if kandidaten else None


def _tabelle(ws: list[Wort], etiketten: list[Wort], start: Wort, typ: str) -> dict[str, int]:
    werte: dict[str, int] = {}
    for w in _werte_entlang(ws, start, typ)[: len(KATEGORIEN) + 1]:
        if w.zahl is None:
            break
        kat = _kategorie(etiketten, w, senkrecht=typ in ("oben", "unten"))
        if kat is None or kat in werte:
            break
        werte[kat] = w.zahl
    return werte


def arme(ws: list[Wort]) -> list[dict]:
    """Je Knotenarm: Lage der Beschriftung S, Art (oben/unten/rechts/links), S und Q."""
    etiketten = [w for w in ws if w.text in KATEGORIEN]
    qs = [w for w in ws if w.text == "Q"]
    out = []
    for s in (w for w in ws if w.text == "S"):
        nah = [q for q in qs if abs(q.x - s.x) + abs(q.y - s.y) < 30]
        if not nah:
            continue
        q = min(nah, key=lambda q: abs(q.x - s.x) + abs(q.y - s.y))
        if abs(q.y - s.y) <= TOL:
            typ = "oben" if q.x < s.x else "unten"
        elif abs(q.x - s.x) <= TOL:
            typ = "rechts" if q.y < s.y else "links"
        else:
            continue
        werte = _tabelle(ws, etiketten, s, typ)
        if werte:
            out.append({"x": s.x, "y": s.y, "typ": typ, "s": werte,
                        "q": _tabelle(ws, etiketten, q, typ)})
    return out


def stimmig(arm: dict) -> bool:
    """Kfz-Zelle = Summe der Fahrzeugarten (bzw. Pkw + SV in den Vorlagen mit SV)."""
    s = arm["s"]
    if "Kfz" not in s:
        return False
    if all(k in s for k in FAHRZEUGE):
        return s["Kfz"] == sum(s[k] for k in FAHRZEUGE)
    return "Pkw" in s and "SV" in s and s["Kfz"] == s["Pkw"] + s["SV"]


def _spitzenstunden(ws: list[Wort]) -> list[tuple[float, int | None, str]]:
    """[(x0, Stunde oder None, Text)] je Angabe „Spitzenstunde: …“, links nach rechts. Der Text
    reicht bis zur nächsten Angabe oder zum Zähltag in derselben Zeile."""
    aufrecht = [w for w in ws if not w.gedreht]
    out = []
    for w in aufrecht:
        if not w.text.startswith("Spitzenstunde"):
            continue
        zeile = sorted((v for v in aufrecht if abs(v.y - w.y) <= 2.5 and v.x0 > w.x0),
                       key=lambda v: v.x0)
        teile = [w.text]
        for v in zeile:
            if v.text.startswith(("Spitzenstunde", "Zähltag")):
                break
            teile.append(v.text)
        text = " ".join(teile)
        m = _STUNDE.search(text)
        stunde = None
        if m:
            h1, m1, h2, m2 = (int(v) for v in m.groups())
            stunde = h1 if m1 == 0 and m2 == 0 and h2 == h1 + 1 else None
        out.append((w.x0, stunde, text))
    return sorted(out)


def lese_seite(seite) -> dict:
    """Eine Seite -> {stunden, fehlt, leer, arme, kopf, nur_rad, ist_plan, …}."""
    ws = worte(seite)
    texte = zeilen_text(ws)
    voll = " ".join(t for _, _, t in texte)
    nur_rad = "NUR RADVERKEHR" in voll.upper()
    gruppe = "rad" if nur_rad else "kfz"
    kopf: dict = {"armnamen": {}}
    angaben = _spitzenstunden(ws)
    for _, _, t in texte:
        if t.startswith("Lage der Zählstelle"):
            kopf["name"] = t.split(":", 1)[1].strip() if ":" in t else ""
        elif t.startswith("Querschnitt") and "name" in kopf:
            kopf["name"] += f" ({t})"
        if m := _ARM.match(t):
            # in derselben Zeile steht teils der Name der Excel-Datei
            kopf["armnamen"][m.group(1)] = _DATEI_IM_TEXT.sub("", m.group(2)).strip()
    if m := _TAG.search(voll):
        jahr = int(m.group(4))
        jahr = jahr + 2000 if jahr < 100 else jahr
        try:
            kopf["datum"] = date(jahr, int(m.group(3)), int(m.group(2)))
        except ValueError:
            pass
        if m.group(1):
            kopf["wochentag"] = _WOCHENTAG[m.group(1)]
    if m := _KNOTEN.search(voll):
        kopf["knoten"] = m.group(1)
    if m := _KOORD.search(voll):
        x, y = float(m.group(1)), float(m.group(2))
        # 7 Stellen: Gauß-Krüger (Zone 3), 6 Stellen: UTM 32 ohne Zonenangabe (neuere Blätter)
        kopf["gk_x" if x > 1e6 else "utm_x"], kopf["gk_y" if x > 1e6 else "utm_y"] = x, y

    # je Angabe die Arme ihrer Blatthälfte (die rechte beginnt so weit vor ihrer Angabe wie
    # die linke vor ihrer)
    alle = arme(ws)
    if len(angaben) >= 2:
        links_x = min(w.x0 for w in ws)
        grenze = angaben[1][0] - (angaben[0][0] - links_x) - 5
        haelften = [[a for a in alle if a["x"] < grenze], [a for a in alle if a["x"] >= grenze]]
    else:
        haelften = [alle]
    stunden: dict[int, dict] = {}
    fehlt = []
    leer = 0
    for (_, stunde, text), liste in zip(angaben[:2], haelften, strict=False):
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
            fehlt.append(f"{_uhr(stunde)} (zweimal auf der Seite)")
        else:
            stunden[stunde] = werte
    mit_sv = sum("SV" in a["s"] for a in alle) > len(alle) / 2
    return {
        "kategorien": "Pkw, SV (Schwerverkehr)" if mit_sv else None,
        "stunden": stunden,
        "fehlt": fehlt,
        "leer": leer,
        "arme": max((len(h) for h in haelften), default=0),
        "stimmig": sum(stimmig(a) for a in alle),
        "anzahl_arme": len(alle),
        "kopf": kopf,
        "nur_rad": nur_rad,
        "ist_plan": bool(angaben),
    }


def lese_datei(pfad: Path) -> dict:
    """Ein PDF -> dieselbe Form wie `muenster_xls.lese_datei` (kopf, kfz, rad, weitere)."""
    import pdfplumber

    with pdfplumber.open(pfad) as pdf:
        seiten = [lese_seite(s) for s in pdf.pages]
    plaene = [s for s in seiten if s["ist_plan"] and not s["nur_rad"]]
    if not plaene:
        grund = ("kein Knotenstromplan (Radar-Bericht oder Scan ohne Text)"
                 if not any(s["ist_plan"] for s in seiten) else "nur Rad")
        return {"kopf": {}, "blatt": "", "kfz": {"stunden": {}, "fehlt": [grund], "leer": 0,
                "arme": 0}, "rad": None, "weitere": [], "stimmig": (0, 0)}
    erste = plaene[0]
    tag = erste["kopf"].get("datum")
    stunden: dict[int, dict] = {}
    fehlt: list[str] = []
    weitere = []
    leer = 0
    for i, s in enumerate(plaene, 1):
        anderer_tag = s["kopf"].get("datum") not in (None, tag)
        if anderer_tag:
            weitere.append(f"Seite {i} ({s['kopf']['datum']:%d.%m.%Y})")
            continue
        leer += s["leer"]
        fehlt += s["fehlt"]
        for h, w in s["stunden"].items():
            if h not in stunden:
                stunden[h] = w
            elif stunden[h]["kfz"] != w["kfz"]:
                weitere.append(f"Seite {i} ({_uhr(h)} mit anderen Werten)")
    rad_seiten = [s for s in seiten if s["nur_rad"] and s["stunden"]]
    rad = None
    if rad_seiten:
        rad = {"stunden": rad_seiten[0]["stunden"], "kopf": rad_seiten[0]["kopf"]}
    return {
        "kopf": erste["kopf"],
        "kategorien": erste["kategorien"],
        "blatt": f"PDF, {len(seiten)} Seite(n)",
        "kfz": {"stunden": stunden, "fehlt": list(dict.fromkeys(fehlt)), "leer": leer,
                "arme": max(s["arme"] for s in plaene)},
        "rad": rad,
        "weitere": weitere,
        "stimmig": (sum(s["stimmig"] for s in plaene), sum(s["anzahl_arme"] for s in plaene)),
    }
