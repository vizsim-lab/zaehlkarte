"""Schulferien eines Landes aus den KMK-Ferienkalendern lesen (PDF -> Text mit `pdftotext -layout`).

    pdftotext -layout FER2012_13.pdf FER2012_13.txt
    uv run python werkzeuge/kmk_ferien.py Bayern FER*.txt > schulferien.csv
    uv run python werkzeuge/kmk_ferien.py --pruefe config/schulferien_nordrhein-westfalen.csv \
        Nordrhein-Westfalen FER*.txt

Die Tabelle hat je Land eine Zeile und sechs Spalten (Herbst, Weihnachten, Winter,
Ostern/Frühjahr, Himmelfahrt/Pfingsten, Sommer); mehrzeilige Zellen setzt pdftotext über und unter
die Zeile des Landes. Jede Zeile zwischen zwei Ländern gehört zum näheren, jedes Datum zur Spalte,
deren Überschrift ihm am nächsten steht. Die Jahre ergeben sich aus dem Schuljahr: Herbst im
ersten, Weihnachten im ersten bzw. (Januar) zweiten, alle übrigen im zweiten Jahr.

Ausgabe wie `config/schulferien_*.csv` (von, bis, ferien, schuljahr, gebiet, quelle); die Quelle
ist die URL je Schuljahr (`--urls` mit Zeilen „2012_13 https://…“). Das Ergebnis vor dem Einchecken
gegen die PDFs prüfen – kursiv gesetzte unterrichtsfreie Tage unterscheidet der Text nicht.
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
DATUM = r"(\d{1,2})\s?\.\s?(\d{1,2})\.?(?:\s?\d{4})?"
EINTRAG = re.compile(DATUM + r"(?:\s*[-–]\s*" + DATUM + r")?")
STRICH = re.compile(r"(?<!\S)(?:--?|–)(?!\S)")  # Zelle ohne Ferien


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
    z = re.sub(r"\(\s*[-\d]*\s*\)", lambda m: " " * len(m.group(0)), zeile)  # „(3)“ bewegliche Tage
    out = []
    for m in EINTRAG.finditer(z):
        mitte = (m.start() + m.end()) / 2
        out.append((min(range(len(mitten)), key=lambda k: abs(mitten[k] - mitte)), m))
    return out


def _belegt(zeile: str, mitten: list[float]) -> set[int]:
    """Spalten, in denen die Zeile etwas einträgt: ein Datum oder einen Strich („-“, „--“ heißt
    keine Ferien – die Zelle ist belegt, eine mehrzeilige Zelle daneben gehört nicht dazu)."""
    z = re.sub(r"\(\s*[-\d]*\s*\)", lambda m: " " * len(m.group(0)), zeile)
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
            t1, m1 = int(m.group(1)), int(m.group(2))
            t2, m2 = (int(m.group(3)), int(m.group(4))) if m.group(3) else (t1, m1)

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("land")
    ap.add_argument("dateien", nargs="+", type=Path)
    ap.add_argument("--urls", type=Path, help="Zeilen „2012_13 https://…“")
    ap.add_argument("--pruefe", type=Path, help="vorhandene CSV zum Vergleich")
    a = ap.parse_args()
    urls = {}
    if a.urls:
        for z in a.urls.read_text(encoding="utf-8").splitlines():
            if z.strip():
                k, u = z.split()
                urls[k] = u
    alle = []
    for p in sorted(a.dateien):
        m = re.search(r"(\d{4})_(\d{2})", p.name)
        sj = f"{m.group(1)}/{int(m.group(1)) + 1}"
        for von, bis, name in lies(p.read_text(encoding="utf-8"), a.land, sj):
            alle.append((von, bis, name, sj, urls.get(f"{m.group(1)}_{m.group(2)}", "")))
    if a.pruefe:
        zeilen = csv.DictReader(z for z in a.pruefe.open(encoding="utf-8") if not z.startswith("#"))
        soll = {(r["von"], r["bis"], r["schuljahr"]) for r in zeilen
                if r.get("gebiet", "alle") in ("alle", "")}
        ist = {(v.isoformat(), b.isoformat(), sj) for v, b, _, sj, _ in alle}
        jahre = {sj for *_, sj, _ in alle} & {s for *_, s in soll}
        soll = {x for x in soll if x[2] in jahre}
        ist = {x for x in ist if x[2] in jahre}
        print(f"Schuljahre verglichen: {len(jahre)}; nur im Text: {sorted(ist - soll)}; "
              f"nur in der CSV: {sorted(soll - ist)}")
        return
    w = csv.writer(sys.stdout, lineterminator="\n")
    w.writerow(["von", "bis", "ferien", "schuljahr", "gebiet", "quelle"])
    for von, bis, name, sj, url in alle:
        w.writerow([von.isoformat(), bis.isoformat(), name, sj, "alle", url])


if __name__ == "__main__":
    main()
