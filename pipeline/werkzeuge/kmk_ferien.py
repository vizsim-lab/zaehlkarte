"""Schulferien eines Landes aus den KMK-Ferienkalendern lesen – aus dem PDF (bevorzugt) oder aus
dessen Text (`pdftotext -layout`).

    uv run python werkzeuge/kmk_ferien.py --urls urls.txt Hessen FER*.pdf > schulferien_hessen.csv
    uv run python werkzeuge/kmk_ferien.py --pruefe config/schulferien_bayern.csv Bayern FER*.pdf

PDF: pdfplumber liest die Tabelle an ihren Linien – je Land eine Zeile, je Spalte eine Zelle,
mehrzeilige Zellen bleiben beisammen. Name und Jahr einer Spalte stehen in ihrem Kopf („Herbst
2024“, „Weihnachten 2024/2025“; Daten ab August im ersten, sonst im zweiten Jahr). Bis 2001/02
stehen die Sommerferien vorn und gehören zum ersten Jahr des Schuljahres, 2001/02 hat zwei
Sommerspalten – beides folgt aus dem Kopf.

Text (nur, wo das PDF fehlt): Die Tabelle hat je Land eine Zeile und sechs Spalten (Herbst,
Weihnachten, Winter, Ostern/Frühjahr, Himmelfahrt/Pfingsten, Sommer); mehrzeilige Zellen setzt
pdftotext über und unter die Zeile des Landes. Jede Zeile zwischen zwei Ländern gehört zum näheren,
jedes Datum zur Spalte, deren Überschrift ihm am nächsten steht. Die Jahre ergeben sich aus dem
Schuljahr: Herbst im ersten, Weihnachten im ersten bzw. (Januar) zweiten, alle übrigen im zweiten
Jahr. Zwischen zwei Ländern ist die Zuordnung unsicher: 2024/25 gab sie zwei Tage
Mecklenburg-Vorpommerns an die Nachbarn.

Eine Zelle kann mehrere Einträge haben: „04.10. - 19.10. / 01.11.“, „30.04. und 02.05.“,
„16. - 30.10.“ (Tag ohne Monat). Kursiv gesetzte schul- und unterrichtsfreie Tage stehen wie Ferien
unter dem Namen ihrer Spalte. Gleiche Einträge eines Schuljahres zählen einmal.

Ausgabe wie `config/schulferien_*.csv` (von, bis, ferien, schuljahr, gebiet, quelle); die Quelle
ist die URL je Schuljahr (`--urls` mit Zeilen „2012_13 https://…“).
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

SPALTEN = [("Herbst", "Herbstferien"), ("Weihnachten", "Weihnachtsferien"),
           ("Winter", "Winterferien"), ("Ostern", "Osterferien"), ("Pfingsten", "Pfingstferien"),
           ("Sommer", "Sommerferien")]
LAENDER = ["Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
           "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz",
           "Saarland", "Sachsen-Anhalt", "Sachsen", "Schleswig-Holstein", "Thüringen"]
NAMEN = [("Sommer", "Sommerferien"), ("Herbst", "Herbstferien"), ("Weihnacht", "Weihnachtsferien"),
         ("Winter", "Winterferien"), ("Ostern", "Osterferien"), ("Frühjahr", "Osterferien"),
         ("Pfingst", "Pfingstferien"), ("Himmelf", "Pfingstferien")]
DATUM = r"(\d{1,2})\s?\.\s?(\d{1,2})\.?(?:\s?\d{4})?"
TAG = r"(\d{1,2})\."  # Tag ohne Monat vor einem Bis-Datum: „16. - 30.10.“
# eng um den Strich: ein Strich mit viel Abstand ist eine leere Nachbarzelle („22.04.   -   30.06.“)
BIS = r"\s{0,3}[-–]\s{0,3}"
EINTRAG = re.compile(rf"(?:{DATUM}|{TAG}(?={BIS}\d))(?:{BIS}{DATUM})?")
STRICH = re.compile(r"(?<!\S)(?:--?|–)(?!\S)")  # Zelle ohne Ferien
KLAMMER = re.compile(r"\(\s*[-\d]*\s*\)")  # „(3)“: Zahl der beweglichen Ferientage


def _paar(m: re.Match) -> tuple[int, int, int, int] | None:
    """(Tag, Monat) des ersten und letzten Tages; „16. - 30.10.“ nimmt den Monat des Bis-Datums."""
    if m.group(1):
        t1, m1 = int(m.group(1)), int(m.group(2))
    elif m.group(4):
        t1, m1 = int(m.group(3)), int(m.group(5))
    else:
        return None
    t2, m2 = (int(m.group(4)), int(m.group(5))) if m.group(4) else (t1, m1)
    return t1, m1, t2, m2


def _land(zeile: str) -> str | None:
    t = zeile.strip()
    for land in LAENDER:  # „Sachsen-Anhalt“ vor „Sachsen“
        if t.startswith(land) and not t.startswith(land + "-"):
            return land
    return None


def _kopf(zeilen: list[str]) -> tuple[int, list[float]]:
    """Zeile mit den Spaltenüberschriften -> (Index, Mitte je Spalte)."""
    for i, z in enumerate(zeilen):
        if "Herbst" in z and "Sommer" in z and "Weihnacht" in z:
            mitten = []
            for wort, _ in SPALTEN:
                k = z.find(wort if wort != "Ostern" else "Ostern")
                if wort == "Pfingsten":
                    k = z.find("Himmelfahrt") if "Himmelfahrt" in z else z.find("Pfingsten")
                    ende = z.find("Pfingsten", k) + len("Pfingsten")
                    mitten.append((k + ende) / 2)
                    continue
                if wort == "Ostern":
                    wort_ende = "Ostern/Frühjahr" if "Ostern/Frühjahr" in z else "Ostern"
                    ende = k + len(wort_ende)
                    mitten.append((k + ende) / 2)
                    continue
                mitten.append(k + len(wort) / 2)
            return i, mitten
    raise ValueError("keine Kopfzeile mit Herbst … Sommer")


def _treffer(zeile: str, mitten: list[float]) -> list[tuple[int, re.Match]]:
    """Daten einer Zeile mit ihrer Spalte (nächste Überschrift)."""
    z = KLAMMER.sub(lambda m: " " * len(m.group(0)), zeile)
    out = []
    for m in EINTRAG.finditer(z):
        mitte = (m.start() + m.end()) / 2
        out.append((min(range(len(mitten)), key=lambda k: abs(mitten[k] - mitte)), m))
    return out


def _belegt(zeile: str, mitten: list[float]) -> set[int]:
    """Spalten, in denen die Zeile etwas einträgt: ein Datum oder einen Strich („-“, „--“ heißt
    keine Ferien – die Zelle ist belegt, eine mehrzeilige Zelle daneben gehört nicht dazu)."""
    z = KLAMMER.sub(lambda m: " " * len(m.group(0)), zeile)
    spalten = {k for k, _ in _treffer(zeile, mitten)}
    rest = EINTRAG.sub(lambda m: " " * len(m.group(0)), z)
    for m in STRICH.finditer(rest):
        mitte = (m.start() + m.end()) / 2
        spalten.add(min(range(len(mitten)), key=lambda k: abs(mitten[k] - mitte)))
    return spalten


def lies(text: str, land: str, schuljahr: str) -> list[tuple[date, date, str]]:
    """-> [(von, bis, Name)] des Landes in diesem Schuljahr („2012/2013“)."""
    y1 = int(schuljahr[:4])
    zeilen = text.splitlines()
    kopf, mitten = _kopf(zeilen)
    # Zeilen der Länder; die Tabelle endet vor den Fußnoten („*in Klammern …“, „Stand: …“)
    reihen: list[tuple[int, str]] = []
    ende = len(zeilen)
    for i in range(kopf + 1, len(zeilen)):
        t = zeilen[i].strip()
        if reihen and t.startswith(("*", "¹", "Stand", "Angegeben")):
            ende = i
            break
        name = _land(zeilen[i])
        if name and name not in {n for _, n in reihen}:
            reihen.append((i, name))
    namen = [n for _, n in reihen]
    if land not in namen:
        raise ValueError(f"{land} nicht in der Tabelle {schuljahr}")
    pos = namen.index(land)
    eigene = reihen[pos][0]
    oben = reihen[pos - 1][0] if pos else None
    unten = reihen[pos + 1][0] if pos + 1 < len(reihen) else None
    belegt_eigen = _belegt(zeilen[eigene], mitten)

    def belegt(i: int | None) -> set[int]:
        return _belegt(zeilen[i], mitten) if i is not None else set()

    zellen: dict[int, list[tuple[int, re.Match]]] = {k: [] for k in range(len(SPALTEN))}
    von_i = oben + 1 if oben is not None else kopf + 1
    bis_i = unten if unten is not None else ende
    for i in range(von_i, bis_i):
        for k, m in _treffer(zeilen[i], mitten):
            if i != eigene:
                nachbar = oben if i < eigene else unten
                if nachbar is not None:
                    d_eigen, d_nachbar = abs(i - eigene), abs(i - nachbar)
                    if d_eigen > d_nachbar:
                        continue
                    # gleich weit: zur Reihe, deren eigene Zeile in dieser Spalte leer ist (dort
                    # steht die mehrzeilige Zelle); sind beide leer, zur oberen
                    if d_eigen == d_nachbar and (k in belegt_eigen
                                                 or (k not in belegt(nachbar) and i < eigene)):
                        continue
            zellen[k].append((i, m))
    out = []
    for k, (_, name) in enumerate(SPALTEN):
        for _, m in sorted(zellen[k], key=lambda x: (x[0], x[1].start())):
            if (paar := _paar(m)) is None:
                continue
            t1, m1, t2, m2 = paar

            def jahr(monat: int, spalte: int = k) -> int:
                if spalte == 0:
                    return y1 if monat >= 8 else y1 + 1
                if spalte == 1:
                    return y1 if monat >= 8 else y1 + 1
                return y1 + 1

            von, bis = date(jahr(m1), m1, t1), date(jahr(m2), m2, t2)
            if bis < von:
                raise ValueError(f"{land} {schuljahr} {name}: {von} > {bis}")
            nam = name
            # Bayern: zwei Einträge unter Ostern/Frühjahr = Frühjahrs- (Fasching) und Osterferien
            if k == 3 and land == "Bayern" and len(zellen[k]) > 1 and m is sorted(
                    zellen[k], key=lambda x: (x[0], x[1].start()))[0][1]:
                nam = "Frühjahrsferien"
            out.append((von, bis, nam))
    return out


def _spalten(kopf: list[str | None]) -> list[tuple[str, str | None] | None]:
    """Je Spalte des Tabellenkopfs (Ferienname, Jahresangabe „2024“ bzw. „2024/2025“); None für
    die Spalte der Länder."""
    out: list[tuple[str, str | None] | None] = []
    for zelle in kopf:
        text = " ".join((zelle or "").split())
        name = next((n for wort, n in NAMEN if wort in text), None)
        jahr = re.search(r"\d{4}(?:\s*/\s*\d{4})?", text)
        out.append((name, jahr.group(0).replace(" ", "") if jahr else None) if name else None)
    return out


def _jahr(angabe: str | None, monat: int, y1: int, name: str) -> int:
    if angabe and "/" in angabe:
        erstes, zweites = angabe.split("/")
        return int(erstes) if monat >= 8 else int(zweites)
    if angabe:
        return int(angabe)
    return y1 if monat >= 8 and name in ("Herbstferien", "Weihnachtsferien") else y1 + 1


def _landzelle(text: str) -> str:
    """„2\nSchleswig-Holstein (1)“, „Mecklenburg-\nVorpommern“ -> Name am Anfang, eine Zeile."""
    text = re.sub(r"-\s*\n\s*", "-", text).replace("\n", " ")
    return re.sub(r"^[^A-Za-zÄÖÜäöü]+", "", text)


def lies_pdf(pfad: Path, land: str, schuljahr: str) -> list[tuple[date, date, str]]:
    """-> [(von, bis, Name)] des Landes aus der Tabelle des PDFs (pdfplumber)."""
    import pdfplumber

    with pdfplumber.open(pfad) as pdf:
        tabellen = [t for s in pdf.pages for t in s.extract_tables()]
    if not tabellen:
        raise ValueError(f"{pfad.name}: keine Tabelle")
    tabelle = max(tabellen, key=len)
    spalten = _spalten(tabelle[0])
    if sum(s is not None for s in spalten) < 6:
        raise ValueError(f"{pfad.name}: Tabellenkopf nicht erkannt: {tabelle[0]}")
    zeile = next((z for z in tabelle[1:] if z and z[0] and _land(_landzelle(z[0])) == land), None)
    if zeile is None:
        raise ValueError(f"{land} nicht in der Tabelle {schuljahr}")
    y1 = int(schuljahr[:4])
    out = []
    for spalte, zelle in zip(spalten, zeile, strict=True):
        if spalte is None or not zelle:
            continue
        name, angabe = spalte
        paare = [p for m in EINTRAG.finditer(KLAMMER.sub(" ", zelle)) if (p := _paar(m))]
        for i, (t1, m1, t2, m2) in enumerate(paare):
            von = date(_jahr(angabe, m1, y1, name), m1, t1)
            bis = date(_jahr(angabe, m2, y1, name), m2, t2)
            if bis < von:
                raise ValueError(f"{land} {schuljahr} {name}: {von} > {bis}")
            # Bayern: zwei Einträge unter Ostern/Frühjahr = Frühjahrs- (Fasching) und Osterferien
            nam = "Frühjahrsferien" if (land == "Bayern" and name == "Osterferien"
                                        and len(paare) > 1 and i == 0) else name
            out.append((von, bis, nam))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("land")
    ap.add_argument("dateien", nargs="+", type=Path, help="FER2012_13.pdf (oder .txt) …")
    ap.add_argument("--urls", type=Path, help="Zeilen „2012_13 https://…“")
    ap.add_argument("--pruefe", type=Path, help="vorhandene CSV zum Vergleich")
    a = ap.parse_args()
    urls = {}
    if a.urls:
        for z in a.urls.read_text(encoding="utf-8").splitlines():
            if z.strip():
                k, u = z.split()
                urls[k] = u
    alle: list[tuple[date, date, str, str, str]] = []
    for p in sorted(a.dateien):
        m = re.search(r"(\d{4})_(\d{2})", p.name)
        sj = f"{m.group(1)}/{int(m.group(1)) + 1}"
        eintraege = (lies_pdf(p, a.land, sj) if p.suffix.lower() == ".pdf"
                     else lies(p.read_text(encoding="utf-8"), a.land, sj))
        for von, bis, name in dict.fromkeys(eintraege):  # gleiche Einträge einmal
            alle.append((von, bis, name, sj, urls.get(f"{m.group(1)}_{m.group(2)}", "")))
    if a.pruefe:
        zeilen = csv.DictReader(z for z in a.pruefe.open(encoding="utf-8") if not z.startswith("#"))
        soll = {(r["von"], r["bis"], r["schuljahr"]) for r in zeilen
                if r.get("gebiet", "alle") in ("alle", "berlin", "")}
        ist = {(v.isoformat(), b.isoformat(), sj) for v, b, _, sj, _ in alle}
        jahre = {sj for *_, sj, _ in alle} & {s for *_, s in soll}
        soll = {x for x in soll if x[2] in jahre}
        ist = {x for x in ist if x[2] in jahre}
        print(f"Schuljahre verglichen: {len(jahre)}; nur im Kalender: {sorted(ist - soll)}; "
              f"nur in der CSV: {sorted(soll - ist)}")
        return
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["von", "bis", "ferien", "schuljahr", "gebiet", "quelle"])
    for von, bis, name, sj, url in alle:
        w.writerow([von.isoformat(), bis.isoformat(), name, sj, "alle", url])


if __name__ == "__main__":
    main()
