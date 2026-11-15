"""Nürnberg: jährliche Verkehrszählung (Querschnittszählung), Berichte als PDF, ohne Lizenz.

Quelle: Stadt Nürnberg, Verkehrsplanungsamt – je Jahr ein Bericht „Verkehrszählung …“ (Neues aus
dem Baumeisterhaus) auf nuernberg.de, 2007–2025 (2011, 2020 und 2021 ohne Zählung). Gezählt wird
seit 1967 am Dienstag und Mittwoch der vorletzten Schulwoche vor den Sommerferien von 6 bis 22 Uhr,
in vier Intervallen à vier Stunden an zwei Tagen: Dienstag 10–14 und 18–22 Uhr, Mittwoch 6–10 und
14–18 Uhr (Berichte 2007 und 2025). Die Zählungen im Modell tragen das Datum des Dienstags.

Gelesen wird die Tabelle im Anhang „Entwicklung des Verkehrs (Kfz/16 h) – Zählstellen JJJJ“: je
Zählstelle (Nummer, Name, Lage in Klammern) Kfz von 6 bis 22 Uhr für bis zu zwölf Jahre, ab dem
Bericht 2023 darunter Lkw + Lastzüge mit Anteil. Die Tabellen stehen teils gedreht auf
Hochformatseiten; Zeichen und Linien werden dafür in die aufrechte Lage gedreht.

- Wert eines Jahres aus dem Bericht dieses Jahres. Fehlt die Zählstelle dort oder ist die Zelle
  leer, aus dem nächsten Bericht, der ihn nennt (Hinweis an der Zählung). Weicht ein späterer
  Bericht ab, steht auch das als Hinweis da – geändert wird nichts.
- „--“ und leere Zellen: nicht gezählt. Fußnote „Vorjahreswert“: kein Wert dieses Jahres.
- Fußnoten (Baustellen, Sperrungen, Veranstaltungen) als Hinweise; „◆“ vor dem Wert kennzeichnet
  den Fußgängerbereich.
- Nur Kfz: Lkw + Lastzüge (ohne Busse) sind nicht der Schwerverkehr der Karte (Lkw, Lastzüge,
  Busse) und bleiben in `zusatz`. Rad und Fuß nennen diese Tabellen nicht.
- Zeilen „(Abbieger)“ sind ein einzelner Abbiegestrom, kein Querschnitt: weggelassen.
- Lage aus der Quelldatei (`orte`, OpenStreetMap, werkzeuge/geokodiere_nuernberg.py).
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

FENSTER = [(6 * 60, 22 * 60)]
JAHR = re.compile(r"(?:Juli)?(19[6-9]\d|20[0-4]\d)")
NUMMER = re.compile(r"^(\d{1,3}[a-zA-Z]{0,2}([/.]?\d{1,2}[a-z]?)?|FG\s?\d+)$")
WERT = re.compile(r"^(\d{1,3}(\.\d{3})*|\d{4,6})$")
FG_ZEICHEN = re.compile(r"^(\(cid:\d+\)|u|\uf075|◆|♦)\s*(?=\d)")


@dataclass
class Bericht:
    berichte: int = 0
    seiten: int = 0
    tabellenzeilen: int = 0
    zaehlungen: int = 0
    aus_spaeterem: list[str] = field(default_factory=list)
    vorjahreswert: list[str] = field(default_factory=list)
    abbieger: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)
    fehlende_berichte: list[int] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        return [
            f"{self.berichte} Berichte, {self.seiten} Tabellenseiten, {self.tabellenzeilen} Zeilen",
            f"Werte aus späteren Berichten: {len(self.aus_spaeterem)}",
            *[f"  {s}" for s in self.aus_spaeterem[:12]],
            f"Vorjahreswerte (weggelassen): {', '.join(self.vorjahreswert) or '–'}",
            f"Abbiegeströme (weggelassen): {', '.join(self.abbieger) or '–'}",
            *[f"Bericht fehlt (nicht geholt): {j}" for j in self.fehlende_berichte],
            *[f"ohne Lage: {k}" for k in self.ohne_lage[:30]],
        ]


# --- PDF lesen -----------------------------------------------------------------------------------


def _drehe(c: dict, breite: float, hoehe: float) -> dict:
    """Zeichen oder Kante in die aufrechte Lage (Text von links nach rechts)."""
    m = tuple(
        0 if abs(x) < 1e-6 else (1 if x > 0 else -1) for x in c.get("matrix", (1, 0, 0, 1))[:4]
    )
    x0, x1, top, bottom = c["x0"], c["x1"], c["top"], c["bottom"]
    if m[:2] == (0, 1):  # gegen den Uhrzeigersinn gesetzt: liest von unten nach oben
        return {**c, "x0": hoehe - bottom, "x1": hoehe - top, "top": x0, "bottom": x1}
    if m[:2] == (0, -1):
        return {**c, "x0": top, "x1": bottom, "top": breite - x1, "bottom": breite - x0}
    return dict(c)


def zeichen_und_kanten(seite) -> tuple[list[dict], list[dict]]:
    """Zeichen und Kanten einer pdfplumber-Seite, bei gedrehten Tabellen in aufrechter Lage."""
    breite, hoehe = seite.width, seite.height
    quer = sum(1 for c in seite.chars if not c.get("upright", True)) > len(seite.chars) / 2
    if quer:
        zs = [_drehe(c, breite, hoehe) for c in seite.chars if not c.get("upright", True)]
        ks = [
            {
                "x0": hoehe - e["bottom"],
                "x1": hoehe - e["top"],
                "top": e["x0"],
                "bottom": e["x1"],
                "orientation": "h" if e["orientation"] == "v" else "v",
            }
            for e in seite.edges
        ]
    else:
        zs = [dict(c) for c in seite.chars if c.get("upright", True)]
        ks = [dict(e) for e in seite.edges]
    for c in zs:
        c["h"] = c["bottom"] - c["top"]
    return zs, ks


def woerter(zs: list[dict]) -> list[dict]:
    """Zeichen zu Wörtern: gleiche Zeile und Größe; Leerzeichen oder eine Lücke trennen.
    Hochgestellte Fußnoten (kleiner) werden so eigene Wörter."""
    zeilen: list[list[dict]] = []
    for c in sorted((c for c in zs if c["text"] != ""), key=lambda c: (c["top"] + c["bottom"]) / 2):
        mitte = (c["top"] + c["bottom"]) / 2
        for z in zeilen:
            ref = z[0]
            if abs((ref["top"] + ref["bottom"]) / 2 - mitte) < 0.3 * min(ref["h"], c["h"]) and abs(
                ref["h"] - c["h"]
            ) < 0.15 * max(ref["h"], c["h"]):
                z.append(c)
                break
        else:
            zeilen.append([c])
    out = []
    for z in zeilen:
        z.sort(key=lambda c: c["x0"])
        wort: list[dict] = []
        for c in z:
            if not c["text"].strip():
                if wort:
                    out.append(_wort(wort))
                wort = []
                continue
            if wort and c["x0"] - wort[-1]["x1"] >= 0.25 * max(c["h"], wort[-1]["h"]):
                out.append(_wort(wort))
                wort = []
            wort.append(c)
        if wort:
            out.append(_wort(wort))
    return out


def _wort(cs: list[dict]) -> dict:
    return {
        "text": "".join(c["text"] for c in cs),
        "x0": min(c["x0"] for c in cs),
        "x1": max(c["x1"] for c in cs),
        "top": min(c["top"] for c in cs),
        "bottom": max(c["bottom"] for c in cs),
        "h": statistics.median(c["h"] for c in cs),
    }


def trenner(ks: list[dict], x0: float, x1: float) -> list[float]:
    """y der waagrechten Linien, die mindestens 60 % von x0..x1 abdecken (Rahmen aus Rechtecken)."""
    stuecke: dict[float, list[tuple[float, float]]] = defaultdict(list)
    for e in ks:
        if e["orientation"] != "h":
            continue
        a, b = max(e["x0"], x0), min(e["x1"], x1)
        if b > a:
            stuecke[round((e["top"] + e["bottom"]) / 2 * 2) / 2].append((a, b))
    ys = []
    for y in sorted(stuecke):
        abgedeckt, ende = 0.0, x0
        for a, b in sorted(stuecke[y]):
            if b > ende:
                abgedeckt += b - max(a, ende)
                ende = b
        if abgedeckt > 0.6 * (x1 - x0) and not (ys and y - ys[-1] < 2.5):
            ys.append(y)
    return ys


def lies_zelle(ws: list[dict]) -> dict:
    """Erste Zeile = Wert, kleine hochgestellte Ziffern daneben = Fußnoten, weitere Zeilen = zweite
    Angabe (ab 2023: Lkw+Lz mit Anteil)."""
    hmax = max(w["h"] for w in ws)
    gross = [w for w in ws if w["h"] > 0.85 * hmax]
    oben = min(w["top"] for w in gross)
    erste = [w for w in gross if w["top"] < oben + 0.5 * hmax]
    mitte = statistics.median((w["top"] + w["bottom"]) / 2 for w in erste)
    unten1 = max(w["bottom"] for w in erste)
    fn, zweite = [], []
    for w in ws:
        if any(w is e for e in erste):
            continue
        if (
            w["h"] < 0.85 * hmax
            and (w["top"] + w["bottom"]) / 2 < mitte
            and w["bottom"] <= unten1 + 0.5
        ):
            fn.append(w)
        elif (w["top"] + w["bottom"]) / 2 > mitte + 0.4 * hmax:
            zweite.append(w)
        else:
            erste.append(w)
    erste.sort(key=lambda w: w["x0"])
    t = " ".join(w["text"] for w in erste)
    fg = bool(FG_ZEICHEN.match(t))
    t = FG_ZEICHEN.sub("", t)
    fns = [re.sub(r"\D", "", w["text"]) for w in sorted(fn, key=lambda w: w["x0"])]
    if m := re.match(r"^(\d{1,3}(?:\.\d{3})*)\s*(\d+\))$", t):  # „1)“ in normaler Größe
        t, fns = m.group(1), [*fns, m.group(2).rstrip(")")]
    zweite.sort(key=lambda w: (round(w["top"]), w["x0"]))
    return {
        "text": t,
        "fn": [f for f in fns if f],
        "zweite": " ".join(w["text"] for w in zweite),
        "fg": fg,
    }


def fussnoten(ws: list[dict]) -> dict[str, str]:
    """Fußnoten unter der Tabelle: „1) Text“ oder hochgestellte Ziffer + Text, mehrere je Zeile.
    Jedes Textwort gehört zur nächsten Nummer links auf derselben Zeile, Umbrüche zur letzten."""
    if not ws:
        return {}
    htext = statistics.median(w["h"] for w in ws)
    nummern, texte = [], []
    for w in ws:
        t = w["text"]
        if re.fullmatch(r"\d{1,2}\)", t) or (re.fullmatch(r"\d{1,2}", t) and w["h"] < 0.9 * htext):
            nummern.append({**w, "nr": t.rstrip(")")})
        else:
            texte.append(w)
    # Seitenzahl allein auf ihrer Zeile
    texte = [
        w
        for w in texte
        if not (
            re.fullmatch(r"\d{1,3}", w["text"])
            and not any(
                x is not w
                and abs((x["top"] + x["bottom"]) / 2 - (w["top"] + w["bottom"]) / 2) < 0.6 * htext
                for x in ws
            )
        )
    ]
    if not nummern:
        return {}
    zeile = lambda w: (round((w["top"] + w["bottom"]) / 2 / (0.6 * htext)), w["x0"])  # noqa: E731
    out: dict[str, list] = {n["nr"]: [] for n in nummern}
    letzte = None
    for w in sorted(texte, key=zeile):
        mw = (w["top"] + w["bottom"]) / 2
        links = [
            n
            for n in nummern
            if abs((n["top"] + n["bottom"]) / 2 - mw) < 0.9 * htext and n["x1"] <= w["x0"] + 1
        ]
        if links:
            dmin = min(abs((n["top"] + n["bottom"]) / 2 - mw) for n in links)
            n = max(
                (n for n in links if abs((n["top"] + n["bottom"]) / 2 - mw) < dmin + 1.0),
                key=lambda n: n["x1"],
            )
            letzte = n["nr"]
        elif letzte is None:
            continue
        out[letzte].append(w)

    def sauber(t: str) -> str:
        return re.split(r"\s(?:Shö_|V:\\|\(cid:\d+\)|u Fußgängerbereich|\uf075)", " " + t)[
            0
        ].strip()

    return {k: sauber(" ".join(w["text"] for w in sorted(v, key=zeile))) for k, v in out.items()}


def lies_seite(seite) -> dict | None:
    """Eine Tabellenseite: Jahre (Spalten), Zeilen (Nummer, Name, Zellen), Fußnoten."""
    zs, ks = zeichen_und_kanten(seite)
    return lies_woerter(woerter(zs), ks)


def lies_woerter(ws: list[dict], ks: list[dict]) -> dict | None:
    if not ws:
        return None
    titel = next((w for w in ws if w["text"].lower() == "zählstelle"), None) or next(
        (w for w in ws if w["text"].lower().startswith("zählstelle")), None
    )
    jahre = [{**w, "text": m.group(1)} for w in ws if (m := JAHR.fullmatch(w["text"]))]
    if titel is None or len(jahre) < 3:
        return None
    tabzeilen = [w["top"] for w in ws if re.match(r"Tabelle|ENTWICKLUNG|Zählstellen", w["text"])]
    jahre = sorted(
        (
            w
            for w in jahre
            if abs(w["top"] - titel["top"]) < 30
            and not any(abs(w["top"] - t) < 3 for t in tabzeilen)
        ),
        key=lambda w: w["x0"],
    )
    if len(jahre) < 3:
        return None
    mitten = [((w["x0"] + w["x1"]) / 2, int(w["text"])) for w in jahre]
    grenzen = []
    for i, (m, j) in enumerate(mitten):
        links = (mitten[i - 1][0] + m) / 2 if i else m - (mitten[1][0] - mitten[0][0]) / 2
        rechts = (
            (mitten[i + 1][0] + m) / 2 if i + 1 < len(mitten) else m + (m - mitten[i - 1][0]) / 2
        )
        grenzen.append((links, rechts, j))
    erste = grenzen[0][0]
    kopf_unten = max(w["bottom"] for w in jahre)
    breite_x0 = min(w["x0"] for w in ws if w["top"] > kopf_unten) - 3
    ys = [y for y in trenner(ks, max(breite_x0, erste - 250), grenzen[-1][1]) if y > kopf_unten - 1]
    unten = ys[-1] if ys else max(w["bottom"] for w in ws)
    # „27/“ + „8“: Schrägstrich am Ende des ersten Teils
    for w in [w for w in ws if re.fullmatch(r"\d{1,3}[a-zA-Z]{0,2}/", w["text"])]:
        rechts = [
            x
            for x in ws
            if abs(x["top"] - w["top"]) < 0.3 * w["h"]
            and 0 <= x["x0"] - w["x1"] < 0.6 * w["h"]
            and re.fullmatch(r"\d{1,2}[a-z]?", x["text"])
        ]
        if rechts:
            w["text"], w["x1"] = w["text"] + rechts[0]["text"], rechts[0]["x1"]
            ws.remove(rechts[0])
    kand = [
        w
        for w in ws
        if kopf_unten < w["top"] < unten
        and w["x1"] < erste
        and (NUMMER.match(w["text"]) or w["text"] == "FG")
    ]
    if not kand:
        return None
    xmin = min(w["x0"] for w in kand)
    hm = statistics.median(w["h"] for w in kand)
    anker = sorted(
        (w for w in kand if w["x0"] < xmin + 1.4 * hm and w["h"] >= 0.85 * hm),
        key=lambda w: w["top"],
    )
    if unter := [y for y in ys if y > anker[-1]["top"] + 0.5 * anker[-1]["h"]]:
        unten = unter[0]  # Linie unter der letzten Zeile; darunter die Fußnoten
    namen_x = [
        w["x0"]
        for a in anker
        for w in ws
        if abs(w["top"] - a["top"]) < 0.4 * a["h"]
        and w["x0"] > a["x1"]
        and w["text"][:1].isalpha()
        and w["text"][:1].isupper()
    ]
    name_x0 = statistics.median(namen_x) if namen_x else xmin + 3 * hm
    # Nummern, deren Schrägstrich im Text fehlt: „224“ + „1“ -> 224/1, „30c7“ -> 30c/7
    for a in anker:
        rest = sorted(
            (
                w
                for w in ws
                if abs(w["top"] - a["top"]) < 0.4 * a["h"]
                and w["x0"] >= a["x1"] - 0.5
                and w["x1"] < name_x0 - 0.5
                and re.fullmatch(r"[/.]?\d{1,2}[a-z]?", w["text"])
            ),
            key=lambda w: w["x0"],
        )
        a["nummer"] = a["text"]
        a["rest"] = rest[:1]
        if rest and a["text"] != "FG":
            a["nummer"] = a["text"].rstrip("/.") + "/" + rest[0]["text"].lstrip("/.")
        elif a["text"] == "FG":
            fg = [
                w
                for w in ws
                if abs(w["top"] - a["top"]) < 2
                and 0 < w["x0"] - a["x1"] < 8
                and w["text"].isdigit()
            ]
            if fg:
                a["nummer"], a["rest"] = f"FG {fg[0]['text']}", fg[:1]
        a["nummer"] = re.sub(r"^(\d{1,3}[a-zA-Z]{1,2})(\d{1,2})$", r"\1/\2", a["nummer"])
        a["nummer"] = re.sub(r"^(\d{1,3}[a-z]?)\.(\d{1,2}[a-z]?)$", r"\1/\2", a["nummer"])
    tab_x0 = xmin - 3
    baender = list(zip(ys, ys[1:], strict=False))
    treffer = [sum(1 for w in anker if a < (w["top"] + w["bottom"]) / 2 < b) for a, b in baender]
    if baender and sum(1 for t in treffer if t == 1) >= 0.8 * len(anker):
        baender = [ab for ab, t in zip(baender, treffer, strict=True) if t >= 1]  # mit Linien
    else:  # Zeilen ohne Linien: ab jeder Nummer (sie steht auf der ersten Zeile)
        starts = [w["top"] - 0.25 * w["h"] for w in anker]
        baender = list(zip(starts, [*starts[1:], unten], strict=True))
    zeilen = []
    for a, b in baender:
        band = [
            w
            for w in ws
            if a <= (w["top"] + w["bottom"]) / 2 < b and w["x0"] >= tab_x0 - 5 and w["top"] < unten
        ]
        if band and (z := _zeile(band, grenzen, anker)):
            zeilen.append(z)
    # Namen über drei Zeilen: der Rest („Lechstraße)“) steht in gedrehten Tabellen auf der ersten
    # Zeile der nächsten Zählstelle – zurück zur Zeile mit der offenen Klammer
    for vor, z in zip(zeilen, zeilen[1:], strict=False):
        offen = " ".join(vor["name"]).count("(") > " ".join(vor["name"]).count(")")
        if offen and z["name"] and (m := re.match(r"^([^()\s]+\))\s*(.*)$", z["name"][0])):
            vor["name"].append(m.group(1))
            z["name"] = [m.group(2), *z["name"][1:]] if m.group(2) else z["name"][1:]
    return {
        "jahre": [j for _, j in mitten],
        "zeilen": zeilen,
        "fussnoten": fussnoten([w for w in ws if w["top"] > unten + 1]),
    }


def _zeile(band: list[dict], grenzen, anker: list[dict]) -> dict | None:
    links = [w for w in band if w["x1"] <= grenzen[0][0] + 2]
    eigene = sorted((a for a in anker if any(w is a for w in links)), key=lambda w: w["top"])
    if not eigene:
        return None
    nummer = eigene[0]
    weg = {id(nummer), *(id(r) for r in nummer.get("rest", []))}
    zeilen: list[
        list
    ] = []  # [top, [Wörter]] – erst nach Zeilen, in jeder Zeile von links nach rechts
    for w in sorted((w for w in links if id(w) not in weg), key=lambda w: w["top"]):
        if zeilen and abs(zeilen[-1][0] - w["top"]) < 0.3 * w["h"]:
            zeilen[-1][1].append(w)
        else:
            zeilen.append([w["top"], [w]])
    zeilen = [[top, [w["text"] for w in sorted(ws, key=lambda w: w["x0"])]] for top, ws in zeilen]
    werte = {}
    for links_, rechts_, j in grenzen:
        if zelle := [w for w in band if links_ <= (w["x0"] + w["x1"]) / 2 < rechts_]:
            werte[j] = lies_zelle(zelle)
    return {"nummer": nummer["nummer"], "name": [" ".join(t) for _, t in zeilen], "werte": werte}


def seitentext(zs: list[dict]) -> str:
    ws = sorted(woerter(zs), key=lambda w: (round(w["top"] / 4), w["x0"]))
    return " ".join(w["text"] for w in ws)


def lese_pdf(pfad: Path) -> dict:
    """Ein Bericht: Zeilen der Tabelle „Zählstellen JJJJ“ (mit Seite), Fußnoten je Seite und die
    Nummern der Gruppen Außenkordon und Pegnitzbrücken (Tabellen davor im Anhang)."""
    import pdfplumber

    out = {"zeilen": [], "fussnoten": {}, "kordon": {}, "bruecken": {}, "seiten": 0}
    with pdfplumber.open(pfad) as pdf:
        vorher = None
        for i, s in enumerate(pdf.pages):
            zs, ks = zeichen_und_kanten(s)
            t = seitentext(zs)
            if "Zählstelle" not in t:
                vorher = None
                continue
            titel = re.search(r"Tabelle\s*\d+\s*:", t)
            if titel and re.search(r"Au(ß|ss)enkordon", t[titel.start() : titel.start() + 120]):
                art = "kordon"
            elif titel and re.search(r"Pegnitzbr", t[titel.start() : titel.start() + 120]):
                art = "bruecken"
            elif "ENTWICKLUNG DES VERKEHRS" in t:
                art = "zaehlstellen"
            elif vorher and not titel:
                art = vorher
            else:
                vorher = None
                continue
            vorher = art
            r = lies_woerter(woerter(zs), ks)
            if not r or (art != "zaehlstellen" and len(r["jahre"]) < 8):
                continue
            if art == "zaehlstellen":
                out["seiten"] += 1
                out["fussnoten"][i + 1] = r["fussnoten"]
                out["zeilen"] += [{**z, "seite": i + 1} for z in r["zeilen"]]
            else:
                for z in r["zeilen"]:
                    out[art][z["nummer"]] = {j: v["text"] for j, v in z["werte"].items()}
    return out


# --- Zählungen ------------------------------------------------------------------------------------


def name_aus(teile: list[str]) -> str:
    """Name einer Zeile, bereinigt um Reste der Nachbarzeilen und versteckte Werte im PDF."""
    t = re.sub(r"\s+", " ", " ".join(teile)).strip()
    t = re.sub(r"\b([A-ZÄÖÜ]) ([a-zäöüß])", r"\1\2", t)  # „M aximilianstraße“
    t = re.sub(r"\d{1,3}\.\d{3}", " ", t)  # versteckter Wert („Weg)13.027“)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^(\S+?\)\s*)+(?=[A-ZÄÖÜ(])", "", t)  # Rest der Vorzeile („Weg)“)
    t = re.sub(r"^\([^)]*\)\s*(?=[A-ZÄÖÜ])", "", t)  # Zusatz der Vorzeile
    # überlagerter Text („StraStraß0e“), schließende Klammer ohne öffnende
    # („Rothenburger Straße) Straße“)
    woerter_, tiefe = [], 0
    for wort in t.split():
        if re.search(r"(Stra){2}|[a-zäöüß]\d[a-zäöüß]", wort):
            continue
        if wort.endswith(")") and "(" not in wort and tiefe == 0:
            continue
        tiefe += wort.count("(") - wort.count(")")
        woerter_.append(wort)
    t = " ".join(woerter_)
    if t.count("(") > t.count(")"):  # Name im Bericht abgeschnitten
        t += ")"
    return t.strip()


def _zahl(text: str) -> int | None:
    return int(text.replace(".", "")) if WERT.match(text) else None


def _fussnote(b: dict, seite: int, nr: str) -> str | None:
    if t := b["fussnoten"].get(seite, {}).get(nr):
        return t
    for s in sorted(b["fussnoten"], key=lambda s: abs(s - seite)):  # Fußnoten der Nachbarseiten
        if t := b["fussnoten"][s].get(nr):
            return t
    return None


def _punkt(z: int) -> str:
    return f"{z:,}".replace(",", ".")


def zaehlungen(berichte: dict[int, dict], quelle: dict, bericht: Bericht) -> Iterator[Zaehlung]:
    """Je Zählstelle und Jahr eine Zählung (Kfz 6–22 Uhr) aus den gelesenen Berichten."""
    dateien = {d["jahr"]: d for d in quelle["dateien"]}
    orte = quelle.get("orte", {})
    # (nummer, jahr) -> [(bericht, zeile, zelle)]
    alle: dict[tuple[str, int], list] = defaultdict(list)
    for bj, b in sorted(berichte.items()):
        for z in b["zeilen"]:
            for j, zelle in z["werte"].items():
                alle[(z["nummer"], j)].append((bj, z, zelle))
    for (nummer, jahr), quellen in sorted(alle.items(), key=lambda x: (x[0][1], x[0][0])):
        if jahr not in dateien:  # nur Jahre mit eigenem Bericht (Datum)
            continue
        mit_wert = [(bj, z, c) for bj, z, c in quellen if _zahl(c["text"]) is not None]
        eigen = [q for q in mit_wert if q[0] == jahr]
        gewaehlt = eigen[0] if eigen else (min(mit_wert, key=lambda q: q[0]) if mit_wert else None)
        if gewaehlt is None:
            continue
        bj, zeile, zelle = gewaehlt
        b = berichte[bj]
        name = name_aus(zeile["name"])
        if re.search(r"\(Abbieger\)", name):
            bericht.abbieger.append(f"{nummer} {jahr}")
            continue
        fns = [t for f in zelle["fn"] if (t := _fussnote(b, zeile["seite"], f))]
        if any("Vorjahreswert" in t for t in fns):
            bericht.vorjahreswert.append(f"{nummer} {jahr}")
            continue
        wert = _zahl(zelle["text"])
        hinweise = [f"Bericht {bj}: {t}" for t in fns]
        if bj != jahr:
            fehlt = (
                "führt die Zählstelle nicht auf"
                if not any(q[0] == jahr for q in quellen)
                else "lässt das Feld leer"
            )
            hinweise.append(f"Wert aus dem Bericht {bj}; der Bericht {jahr} {fehlt}.")
            bericht.aus_spaeterem.append(f"{nummer} {jahr} aus {bj}")
        andere = sorted(
            {(_zahl(c["text"]), q) for q, _, c in mit_wert if q > bj and _zahl(c["text"]) != wert}
        )
        if andere:
            abw = defaultdict(list)
            for w, q in andere:
                abw[w].append(q)
            hinweise += [
                f"Spätere Berichte nennen {_punkt(w)} ({', '.join(map(str, qs))})."
                for w, qs in abw.items()
            ]
        for art, titel in (("kordon", "Außenkordon"), ("bruecken", "Pegnitzbrücken")):
            g = b[art].get(nummer, {}).get(jahr)
            if g and _zahl(g) is not None and _zahl(g) != wert:
                hinweise.append(
                    f"Die Tabelle „{titel}“ desselben Berichts nennt {_punkt(_zahl(g))}."
                )
        if zelle.get("fg"):
            hinweise.append("Im Bericht als Fußgängerbereich gekennzeichnet.")
        ort = orte.get(nummer) or {}
        if isinstance(ort, list):  # mehrere Lagen je Nummer: nach dem Namen
            ort = next(
                (o for o in ort if o.get("wenn") and o["wenn"].casefold() in name.casefold()),
                next((o for o in ort if not o.get("wenn")), {}),
            )
        if not ort:
            bericht.ohne_lage.append(f"{nummer} {name}")
        zweite = re.match(r"^([\d.]+)\s*\(", zelle.get("zweite") or "")
        tag = date.fromisoformat(str(dateien[jahr]["zaehltage"][0]))
        bericht.zaehlungen += 1
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=f"{nummer.replace('/', '-').replace(' ', '')}_{jahr}",
            stelle_roh=nummer,
            name=name,
            typ="Q",
            lon=ort.get("lon"),
            lat=ort.get("lat"),
            lage="geokodiert" if ort else None,
            datum=tag,
            fenster=list(FENSTER),
            intervall=None,
            fenstersummen={"kfz": wert},
            land=quelle["land"],
            kategorien="Kfz (Kraftrad, Pkw, Lkw, Lastzug, Bus), beide Richtungen zusammen",
            rohdatei=dateien[bj]["url"],
            bemerkung=f"Verkehrszählung Juli {jahr}, Zählstelle {nummer} "
            f"(Bericht {bj}, Seite {zeile['seite']})",
            hinweise=hinweise + list(ort.get("hinweise", [])),
            zusatz={
                "bericht": bj,
                "seite": zeile["seite"],
                "lkw_lz": int(zweite.group(1).replace(".", "")) if zweite else None,
                "fussgaengerbereich": bool(zelle.get("fg")),
                "genauigkeit": ort.get("genauigkeit"),
            },
        )


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "nuernberg"
    berichte = {}
    for d in quelle["dateien"]:
        pfad = ordner / d["datei"]
        if not pfad.exists():
            bericht.fehlende_berichte.append(d["jahr"])
            continue
        b = lese_pdf(pfad)
        bericht.berichte += 1
        bericht.seiten += b["seiten"]
        bericht.tabellenzeilen += len(b["zeilen"])
        berichte[d["jahr"]] = b
    yield from zaehlungen(berichte, quelle, bericht)
