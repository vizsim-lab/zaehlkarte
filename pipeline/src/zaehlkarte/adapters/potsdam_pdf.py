"""Potsdam: manuelle Knotenpunktzählungen der Stadt (Zählpläne als PDF, 2010–2023).

Quelle: Open-Data-Portal der Landeshauptstadt Potsdam, Datensatz „Verkehrszählungen“: je
Knoten die Lage und ein ZIP mit den Zählplänen (ein PDF je Zählung). Die Stadt zählt von Hand
an einem mittleren Werktag (April bis Oktober) von 7 bis 10 und 15 bis 18 Uhr (potsdam.de).
Jeder Plan („FAHRZEUG-VERTEILUNG“, aus der Excel-Vorlage „StromPlan“) nennt je Zufahrt und
Verkehrsart (RAD, NFZ, SV, KFZ, FZ) drei Werte: Frühspitzenstunde (FSp),
Nachmittagsspitzenstunde (NSp) und die Summe der sechs Stunden (6h), dazu den Beginn der
Spitzenstunden („Sph-Beginn: 7.30 Uhr und 15.30 Uhr“) und Bemerkungen. Stundenwerte stehen
nicht drin.

- Werte: je Verkehrsart die Spalte SUMME (alle Zufahrten). Die Spalten kommen aus der Lage der
  Wörter (Kopf „SUMME“, Zufahrten NORD/OST/…), nicht aus dem Text: neben der Tabelle stehen die
  Zahlen des Stromplans, und in manchen Plänen fehlt eine Zufahrtsspalte im Text. Prüfung: Summe
  der Zufahrten = SUMME, wo alle Zufahrten lesbar sind.
- Spitzenstunden -> `spitzen` (gleitend im Halbstundenraster, bestimmt nach Kfz), Summe der
  gezählten Stunden -> `fenstersummen`. Kennzahl in der Karte: nur die stärkste Stunde Kfz –
  Rad und Schwerverkehr stehen in den Kfz-Spitzenstunden, nicht in ihren eigenen.
- Nicht gezählt: eine Verkehrsart mit lauter Nullen (Pläne „nurRad“: Kfz 0).
- Schwerverkehr = SV des Plans (Bus, Lkw, Lastzug); NFZ (SV mit Lieferwagen) und FZ (alle
  Fahrzeuge mit Rad) fehlen in der Karte. Hochrechnungen auf den Tag (Q DTVw) auch.
- Zählfenster aus dem Plan („von 7.00 - 10.00 Uhr u. 15.00 - 18.00 Uhr“, „5h-Zählung - von
  8.00 bis 13.00 Uhr“); fehlt die Angabe bei einer 6h-Zählung: 7–10 und 15–18 Uhr (Stadt).
- Datum: das nach „DATUM“ (oben auf dem Plan steht das Druckdatum).
- Lage: Koordinaten des Knotens aus dem Portal.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

MODI = {"RAD": "rad", "NFZ": "nfz", "SV": "sv", "KFZ": "kfz", "FZ": "fz"}
IN_KARTE = ("kfz", "sv", "rad")
NAMEN = {"kfz": "Kfz", "sv": "SV", "rad": "Rad"}
_ZEILE = re.compile(r"^(FSp|NSp|Sp|\d{1,2}h)$")
# Zufahrten heißen NORD, OST, … oder kurz NG, SG (Nord, Süd + Gerade); Großbuchstaben
_RICHTUNG = re.compile(r"^[A-ZÄÖÜ][A-ZÄÖÜ-]{0,11}$")
_ZAHL = re.compile(r"^(\d{1,3}(?:\.\d{3})+|\d+)$")
_DEZIMAL = re.compile(r"^\d+,\d+$")  # errechnete Werte („2230,75“) – keine Zählwerte
_UHR = r"(\d{1,2})[.:](\d{2})"
_DATUM = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_JAHR_DATEI = re.compile(r"(?<!\d)(20\d{2})(?!\d)")
STANDARD_FENSTER = [(420, 600), (900, 1080)]  # 7–10 und 15–18 Uhr laut potsdam.de


@dataclass
class Wort:
    text: str
    x0: float
    x1: float
    top: float

    @property
    def mitte(self) -> float:
        return (self.x0 + self.x1) / 2


@dataclass
class Bericht:
    dateien: int = 0
    gelesen: int = 0
    unlesbar: list[str] = field(default_factory=list)
    zufahrten_abweichend: list[str] = field(default_factory=list)
    errechnet: list[str] = field(default_factory=list)
    fenster_angenommen: int = 0
    datum_jahr_abweichend: list[str] = field(default_factory=list)
    nicht_gezaehlt: Counter = field(default_factory=Counter)
    ohne_lage: int = 0
    doppelt: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        return [
            f"{self.gelesen} von {self.dateien} Zählplänen gelesen",
            f"Zählfenster nicht im Plan (7–10, 15–18 Uhr angenommen): {self.fenster_angenommen}",
            "nicht gezählt (lauter Nullen): "
            + (", ".join(f"{g} {n}" for g, n in sorted(self.nicht_gezaehlt.items())) or "–"),
            f"ohne Lage im Portal: {self.ohne_lage}",
            *[f"Summe der Zufahrten ≠ SUMME: {d}" for d in self.zufahrten_abweichend[:15]],
            *[f"errechnete Werte (Nachkommastellen), nicht übernommen: {d}"
              for d in self.errechnet],
            *[f"Datum nicht im Jahr des Dateinamens: {d}" for d in self.datum_jahr_abweichend],
            *[f"doppelt (gleicher Inhalt): {d}" for d in self.doppelt],
            *[f"nicht lesbar: {d}" for d in self.unlesbar],
        ]


def _zahl(text: str) -> int | None:
    return int(text.replace(".", "")) if _ZAHL.match(text) else None


def worte(seite) -> list[Wort]:
    """Aufrechte Wörter der Seite (gedrehte Straßennamen im Stromplan fallen weg)."""
    s = seite.dedupe_chars()
    return [Wort(w["text"], w["x0"], w["x1"], w["top"])
            for w in s.extract_words(extra_attrs=["upright"]) if w["upright"]]


def tabelle(ws: list[Wort]) -> tuple[dict[str, dict[str, dict]], list[str]] | None:
    """Tabelle FAHRZEUG-VERTEILUNG -> ({Modus: {Zeile: {...}}}, Namen der Zufahrten).

    Zeile = FSp, NSp, Sp oder „6h“/„5h“ mit "summe" (Spalte SUMME; None, wo der Plan einen
    errechneten Wert mit Nachkommastellen zeigt), "errechnet" und "zufahrten" (Werte je Zufahrt
    oder None, wenn nicht so viele Zahlen wie Zufahrten in der Zeile stehen)."""
    kopf = sorted((w for w in ws if w.text == "SUMME"), key=lambda w: w.top)
    if not kopf:
        return None
    summe = kopf[0]
    ende = min((w.top for w in ws
                if w.text.startswith(("Bemerkung", "NFZ=", "Q")) and w.top > summe.top),
               default=float("inf"))
    # Zeilenköpfe: FSp/NSp/… mit einer Zahl unter SUMME in derselben Zeile
    zeilen = []
    for w in ws:
        if not _ZEILE.match(w.text) or not summe.top < w.top < ende or w.x1 > summe.x0:
            continue
        rest = [v for v in ws if abs(v.top - w.top) < 4 and v.x0 > w.x1
                and (_zahl(v.text) is not None or _DEZIMAL.match(v.text))]
        unter = [v for v in rest if abs(v.mitte - summe.mitte) < 25]
        if unter:
            zeilen.append((w, rest, min(unter, key=lambda v: abs(v.mitte - summe.mitte))))
    if not zeilen:
        return None
    links = Counter(round(w.x0) for w, _, _ in zeilen).most_common(1)[0][0]
    zeilen = [z for z in zeilen if abs(z[0].x0 - links) < 8]
    erste = min(w.top for w, _, _ in zeilen)
    richtungen = sorted(
        (w for w in ws if _RICHTUNG.match(w.text) and w.top < erste and w.x0 > links + 10
         and w.x1 < summe.x0 and summe.top - 30 < w.top),
        key=lambda w: w.x0,
    )
    modi = sorted((w for w in ws if w.text in MODI and w.x1 < links and summe.top < w.top < ende),
                  key=lambda w: w.top)
    out: dict[str, dict[str, dict]] = {}
    for w, rest, wert in sorted(zeilen, key=lambda z: z[0].top):
        modus = next((MODI[m.text] for m in reversed(modi) if m.top <= w.top + 4), None)
        if modus is None:
            continue
        zwischen = sorted((v for v in rest if v is not wert and v.x1 <= summe.x0 + 2),
                          key=lambda v: v.x0)
        zufahrten = ([_zahl(v.text) for v in zwischen]
                     if richtungen and len(zwischen) == len(richtungen) else None)
        out.setdefault(modus, {})[w.text] = {
            "summe": _zahl(wert.text),
            "errechnet": bool(_DEZIMAL.match(wert.text)),
            "zufahrten": zufahrten,
        }
    return out, [r.text for r in richtungen]


def _min(h: str, m: str) -> int:
    return int(h) * 60 + int(m)


def angaben(text: str) -> dict:
    """Spitzenstunden, Zählfenster, Datum, Bemerkungen und Knoten aus dem Text des Plans."""
    out: dict = {}
    m = re.search(rf"Sph-Beginn:\s*{_UHR}\s*Uhr(?:\s*und\s*{_UHR}\s*Uhr)?", text)
    if m:
        out["beginn"] = [_min(m[1], m[2])] + ([_min(m[3], m[4])] if m[3] else [])
    mitten = []
    for muster in (r"(?<![A-Za-z])\[?F?Sp\]?\s*:\s*[\d.]+\s*KFZ/h\s*" + _UHR,
                   r"\(?NSp\)?\s*:\s*[\d.]+\s*KFZ/h\s*" + _UHR):
        mm = re.search(muster, text)
        mitten.append(_min(mm[1], mm[2]) if mm else None)
    out["mitten"] = mitten
    m = re.search(rf"von\s*{_UHR}\s*-\s*{_UHR}\s*Uhr\s*u\.\s*{_UHR}\s*-\s*{_UHR}\s*Uhr", text)
    if m:
        g = m.groups()
        out["fenster"] = [(_min(g[0], g[1]), _min(g[2], g[3])),
                          (_min(g[4], g[5]), _min(g[6], g[7]))]
    else:
        m = re.search(rf"(\d+)\s*h\s*-\s*Zählung\s*-\s*von\s*{_UHR}\s*bis\s*{_UHR}\s*Uhr", text)
        if m:
            out["fenster"] = [(_min(m[2], m[3]), _min(m[4], m[5]))]
    m = re.search(r"DATUM\s*:(.*)", text, re.S)
    d = _DATUM.search(m[1]) if m else None
    if d:
        try:
            out["datum"] = date(int(d[3]), int(d[2]), int(d[1]))
        except ValueError:
            pass
    m = re.search(r"Bemerkungen\s*:(.*?)(?:Sph-Beginn|SUMME Zufahrten)", text, re.S)
    if m:
        zeilen = [" ".join(z.split()) for z in m[1].splitlines()]
        # Zahlen des Stromplans, die in die Zeilen geraten (einzeln stehende Zahlen), fallen weg
        zeilen = [re.sub(r"^(?:[\d.]+\s+)+(?=\D)", "", z) for z in zeilen]
        out["bemerkung"] = " ".join(z for z in zeilen if z and not _ZAHL.match(z)).strip(" -")
    return out


def spitzen_aus(tab: dict, ang: dict, nach: str) -> list[dict]:
    """Spitzenstunden mit Fenster [von, bis) und den Werten je Verkehrsart der Karte."""
    namen = [z for z in ("FSp", "NSp", "Sp") if any(z in zeilen for zeilen in tab.values())]
    beginn = list(ang.get("beginn") or [])
    mitten = ang.get("mitten") or []
    out = []
    for i, name in enumerate(namen):
        von = beginn[i] if i < len(beginn) else None
        if von is None and i < len(mitten) and mitten[i] is not None:
            von = mitten[i] - 30
        werte = {g: tab[g][name]["wert"] for g in IN_KARTE
                 if g in tab and name in tab[g] and tab[g][name]["wert"] is not None}
        if von is None or not werte:
            continue
        titel = {"FSp": "Frühspitze", "NSp": "Nachmittagsspitze", "Sp": "Spitzenstunde"}[name]
        out.append({"von": von, "bis": von + 60, "name": titel, "nach": nach, "werte": werte})
    return out


def lese_plan(seite_text: str, ws: list[Wort]) -> dict | None:
    """Ein Zählplan (Seite 1) -> Werte und Angaben, None wenn es keiner ist."""
    if "FAHRZEUG-VERTEILUNG" not in seite_text:
        return None
    t = tabelle(ws)
    if not t:
        return None
    tab, richtungen = t
    ang = angaben(seite_text)
    # SUMME und Summe der Zufahrten laufen in einigen Plänen auseinander (Formelfehler: SV in der
    # Frühspitze 0 bei 62 in den Zufahrten) -> der größere Wert, wie bei Münster, mit Hinweis
    abweichend = []
    for g, zeilen in tab.items():
        for zeile, z in zeilen.items():
            z["wert"] = z["summe"]
            if z["zufahrten"] and None not in z["zufahrten"] and z["summe"] is not None:
                zufahrten = sum(z["zufahrten"])
                if zufahrten != z["summe"]:
                    z["wert"] = max(zufahrten, z["summe"])
                    if g in IN_KARTE:
                        abweichend.append(f"{NAMEN[g]} {zeile}: SUMME {z['summe']}, "
                                          f"Zufahrten {zufahrten}")
    gezaehlt = {g: zeilen for g, zeilen in tab.items() if any(z["wert"] for z in zeilen.values())}
    nach = "kfz" if "kfz" in gezaehlt else "rad"
    summen_zeile = next((z for z in ("6h", "5h", "4h", "9h", "8h")
                         if any(z in v for v in tab.values())), None)
    if summen_zeile is None:
        summen_zeile = next((z for v in tab.values() for z in v if re.match(r"\d+h$", z)), None)
    fenstersummen = {g: gezaehlt[g][summen_zeile]["wert"] for g in IN_KARTE
                     if g in gezaehlt and summen_zeile in gezaehlt[g]
                     and gezaehlt[g][summen_zeile]["wert"] is not None}
    errechnet = [f"{g.upper()} {zeile}" for g, zeilen in tab.items() for zeile, z in zeilen.items()
                 if z["errechnet"]]
    return {
        "tabelle": tab,
        "errechnet": errechnet,
        "richtungen": richtungen,
        "gezaehlt": sorted(gezaehlt),
        "nicht_gezaehlt": sorted(g for g in IN_KARTE if g in tab and g not in gezaehlt),
        "spitzen": spitzen_aus({g: v for g, v in tab.items() if g in gezaehlt}, ang, nach),
        "summen_zeile": summen_zeile,
        "fenstersummen": fenstersummen,
        "abweichend": abweichend,
        **ang,
    }


def lese_pdf(pfad: Path) -> dict | None:
    import pdfplumber

    with pdfplumber.open(pfad) as pdf:
        seite = pdf.pages[0]
        text = seite.dedupe_chars().extract_text() or ""
        return lese_plan(text, worte(seite))


def _knoten(pfade: Pfade) -> dict[str, dict]:
    pfad = pfade.roh / "potsdam" / "export.json"
    if not pfad.exists():
        return {}
    return {str(k["kpnr"]): k for k in json.loads(pfad.read_text(encoding="utf-8"))}


def _fenster_stunden(fenster: list[tuple[int, int]]) -> int:
    return sum(b - a for a, b in fenster) // 60


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    knoten = _knoten(pfade)
    gesehen: dict[tuple, str] = {}
    kennungen: set[str] = set()
    for pfad in sorted((pfade.roh / "potsdam" / "pdf").glob("*/*.pdf")):
        bericht.dateien += 1
        kpnr = pfad.parent.name
        try:
            p = lese_pdf(pfad)
        except Exception as e:  # noqa: BLE001 – kaputtes PDF: im Bericht, nicht abbrechen
            bericht.unlesbar.append(f"{pfad.name}: {e!r}"[:160])
            continue
        if p and p["errechnet"]:
            # Werte mit Nachkommastellen sind errechnet, nicht gezählt – dann ist unklar, welche
            # der ganzen Zahlen im Plan gezählt sind: den Plan nicht übernehmen
            bericht.errechnet.append(f"{kpnr}/{pfad.name}: {', '.join(p['errechnet'])}")
            continue
        if not p or not p.get("datum") or not (p["spitzen"] or p["fenstersummen"]):
            bericht.unlesbar.append(f"{kpnr}/{pfad.name}: kein lesbarer Zählplan (Scan, Kordon)")
            continue
        schluessel = (kpnr, p["datum"], json.dumps(p["tabelle"], sort_keys=True))
        if schluessel in gesehen:
            bericht.doppelt.append(f"{kpnr}/{pfad.name} = {gesehen[schluessel]}")
            continue
        gesehen[schluessel] = pfad.name
        bericht.gelesen += 1
        for g in p["nicht_gezaehlt"]:
            bericht.nicht_gezaehlt[g] += 1
        hinweise = []
        jahr = _JAHR_DATEI.findall(pfad.stem)
        if jahr and int(jahr[-1]) != p["datum"].year:
            bericht.datum_jahr_abweichend.append(f"{kpnr}/{pfad.name}: {p['datum']:%d.%m.%Y}")
            hinweise.append(f"Datum laut Zählplan {p['datum']:%d.%m.%Y}, im Dateinamen {jahr[-1]}.")
        fenster = p.get("fenster")
        if not fenster and p["summen_zeile"] == "6h":
            fenster = STANDARD_FENSTER
            bericht.fenster_angenommen += 1
            hinweise.append("Zählzeit nicht im Zählplan genannt – laut Stadt zählt sie von 7 "
                            "bis 10 und 15 bis 18 Uhr.")
        stunden_fenster = _fenster_stunden(fenster or [])
        fenstersummen = p["fenstersummen"]
        if fenster and p["summen_zeile"] and stunden_fenster != int(p["summen_zeile"][:-1]):
            # Summe über andere Stunden als das Fenster: nicht als Fenstersumme zeigen
            hinweise.append(f"Zählplan: {p['summen_zeile']}-Summe, Zählzeit "
                            f"{stunden_fenster} Stunden.")
            fenstersummen = {}
        if p["abweichend"]:
            bericht.zufahrten_abweichend.append(f"{kpnr}/{pfad.name}: {'; '.join(p['abweichend'])}")
            hinweise.append("Im Zählplan stimmen Spalte SUMME und Summe der Zufahrten nicht "
                            "überein (" + "; ".join(p["abweichend"])
                            + "); die Karte nimmt den größeren Wert.")
        hinweise.append("Der Zählplan nennt nur die Spitzenstunden (nach Kfz) und die Summe der "
                        "gezählten Stunden – keine Stundenwerte.")
        k = knoten.get(kpnr, {})
        punkt = k.get("geo_point_2d") or {}
        if not punkt:
            bericht.ohne_lage += 1
        typ = "Q" if re.search(r"_Q[a-z]*(?:_|$)", pfad.stem) else "K"
        if typ == "Q":  # Querschnitt am Knoten; an einem Tag teils mehrere (Güterfelder Eck)
            hinweise.insert(0, f"Querschnittszählung am Knoten (Zählplan „{pfad.name}“).")
        kennung = f"{kpnr}_{p['datum']:%Y%m%d}"
        n = 2
        while kennung in kennungen:  # zwei Pläne vom selben Tag (z. B. Teilzählung)
            kennung = f"{kpnr}_{p['datum']:%Y%m%d}_{n}"
            n += 1
        kennungen.add(kennung)
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=kennung,
            stelle_roh=kpnr,
            name=k.get("name") or pfad.stem.replace("_", " "),
            typ=typ,
            lon=punkt.get("lon"),
            lat=punkt.get("lat"),
            lage="quelle" if punkt else None,
            datum=p["datum"],
            fenster=fenster or [],
            intervall=None,
            land=quelle["land"],
            richtungen=len(p["richtungen"]) or None,
            kategorien="Kfz, Schwerverkehr (Bus, Lkw, Lastzug), Rad – ohne Nutzfahrzeuge mit "
                       "Lieferwagen (Nfz)",
            rohdatei=k.get("zahlplan"),
            bemerkung=p.get("bemerkung") or None,
            hinweise=hinweise,
            spitzen=p["spitzen"],
            fenstersummen=fenstersummen,
            zusatz={"datei": f"{kpnr}/{pfad.name}", "zufahrten": p["richtungen"]},
        )
