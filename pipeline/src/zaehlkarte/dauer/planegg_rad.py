"""Planegg (Landkreis München): Fahrradzählstelle der Gemeinde an der Amtmannstraße/Münchner
Straße – Tageswerte je Richtung seit Mai 2021, eine Excel-Datei je Jahr auf planegg.de, ohne
Lizenzangabe (CLAUDE.md, „Quellen ohne Lizenz“). Nur Tageswerte: in der Karte als Tageswerte der
Quelle (modell.py), wie bei den Radzählstationen Augsburgs.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/bw`, tools/bw_fl1.py):
- Die Seite der Zählstelle (`seite` in der Quelldatei) verlinkt je Jahr eine Datei
  „JJJJ_Fahrrad Amtmannstraße.xlsx“ unter `/_Resources/Persistent/<Prüfsumme>/…` – der Pfad
  ändert sich mit jeder neuen Fassung. `hole` liest die Links deshalb jedes Mal von der Seite und
  legt die Dateien als `JJJJ.xlsx` ab; `lese` nimmt nur die Jahre, die die Seite zuletzt nannte.
- Je Monat ein Blatt („Mai 2021“, auch „März  2025“, „Aprill 2025“), darin „Monat … JJJJ“, dann
  der Kopf „Datum | Richtung Krailling | Richtung Planegg | gesamt“ (auch „Krailing“, mit
  Leerzeichen am Ende) und je Tag eine Zeile mit dem Datum und den Rädern je Richtung. „gesamt“
  ist eine Formel (Summe beider Richtungen); am Ende eine Zeile „Summe“ – 2025 in mehreren Blättern
  nicht fortgeschrieben (März bis August stehen dieselben Zahlen), hier nicht verwendet.
- In der Karte: je Tag die Summe beider Richtungen (wie „gesamt“), nur wenn beide eine Zahl haben
  (auch 0). Keine Stunden: Ob ein Tag vollständig gezählt ist, lässt sich nicht prüfen.
- Monat des Blatts: Die Blätter „Februar 2025“ und „Februar 2026“ tragen die Daten 1.–28. Januar,
  aber 28 Zeilen mit eigenen Werten – offenbar die Vorlage des Januars. Die Werte passen zum
  Februar: Sie fallen an den Wochenenden des Februars (1./2., 8./9. … 2025; 1., 7./8. … 2026),
  nicht an denen des Januars. `monat_laut_blatt` in der Quelldatei nennt solche Blätter (Vermerk
  dort); in ihnen gilt der Tag der Zeile im Monat des Blatts. Passt das Datum einer Zeile sonst
  nicht zum Blatt, übernimmt die Zählkarte die Zeile nicht (Bericht) – der Bau bricht nicht ab.
- Quelldatei: `seite`, `datei_muster` (regulärer Ausdruck auf den entschlüsselten Pfad, das Jahr
  als Gruppe 1), `monat_laut_blatt` und die Zählstelle `stelle` (Kennung, Straße, Abschnitt, Lage
  aus OpenStreetMap – die Quelle nennt keine Koordinaten).
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_tage

ABRUF = "abruf.json"
MONATE = {m: i for i, m in enumerate(
    ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
     "oktober", "november", "dezember"), start=1)}
BLATT = re.compile(r"([A-Za-zÄÖÜäöü]+)\s+(\d{4})")


@dataclass
class Bericht:
    jahre: list[str] = field(default_factory=list)
    blaetter: int = 0
    tageszeilen: int = 0
    tage: int = 0
    widerspruch: int = 0
    ohne_wert: int = 0  # Zeilen, in denen eine Richtung keine Zahl hat (nicht gezählt)
    monat_korrigiert: Counter = field(default_factory=Counter)  # Blatt -> Zeilen
    falscher_monat: Counter = field(default_factory=Counter)  # Blatt -> Zeilen (nicht übernommen)
    ohne_kopf: list[str] = field(default_factory=list)
    nullen: int = 0
    zeitraum: str | None = None

    def zeilen(self) -> list[str]:
        z = [f"Jahre {', '.join(self.jahre)}: {self.blaetter} Blätter, {self.tageszeilen} "
             f"Tageszeilen, {self.tage} Tageswerte in der Karte (widersprüchlich: "
             f"{self.widerspruch}, ohne Zahl in einer Richtung: {self.ohne_wert}, mit 0: "
             f"{self.nullen}); {self.zeitraum}"]
        if self.monat_korrigiert:
            z.append("Monat laut Blatt (monat_laut_blatt): " + ", ".join(
                f"{k} ({n})" for k, n in sorted(self.monat_korrigiert.items())))
        if self.falscher_monat:
            z.append("Datum passt nicht zum Blatt, nicht übernommen: " + ", ".join(
                f"{k} ({n})" for k, n in sorted(self.falscher_monat.items())))
        if self.ohne_kopf:
            z.append("Blätter ohne Kopf „Datum“: " + ", ".join(self.ohne_kopf))
        return z


def dateien_der_seite(text: str, basis: str, muster: str) -> dict[str, str]:
    """Links der Seite auf die Jahresdateien -> {Jahr: URL}; `muster` mit dem Jahr als Gruppe 1,
    geprüft am entschlüsselten Pfad (`2021_Fahrrad%20Amtmannstra%C3%9Fe.xlsx`)."""
    rx = re.compile(muster)
    out: dict[str, str] = {}
    for href in re.findall(r"""href\s*=\s*["']([^"'#]+)""", text, re.IGNORECASE):
        url = urllib.parse.urljoin(basis, html.unescape(href).strip())
        m = rx.search(urllib.parse.unquote(urllib.parse.urlsplit(url).path))
        if m:
            out.setdefault(m.group(1), url)
    return dict(sorted(out.items()))


def hole(q: dict, pfade: Pfade) -> list[str]:
    from zaehlkarte import abruf

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    seite = abruf.hole(q["seite"]).text
    dateien = dateien_der_seite(seite, q["seite"], q["datei_muster"])
    if not dateien:
        raise ValueError(f"{q['code']}: keine Jahresdatei auf {q['seite']} (Muster "
                         f"{q['datei_muster']!r}) – Seite geändert?")
    for jahr, url in dateien.items():
        abruf.lade(url, ordner / f"{jahr}.xlsx")
    (ordner / ABRUF).write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "seite": q["seite"], "dateien": dateien}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    return [f"{q['code']}: {len(dateien)} Jahresdateien ({', '.join(dateien)})"]


def monat_des_blatts(name: str, zeilen: list[tuple]) -> tuple[int, int] | None:
    """(Jahr, Monat) aus dem Namen des Blatts („März  2025“, „Aprill 2025“) oder, wenn der nicht
    passt, aus der Zeile „Monat … JJJJ“ darin."""
    for text in (name, *(str(z[0]) for z in zeilen[:8] if z and isinstance(z[0], str))):
        for m in BLATT.finditer(text.replace("Monat:", " ").replace("Monat", " ")):
            wort = m.group(1).lower().replace("aprill", "april")
            if wort in MONATE:
                return int(m.group(2)), MONATE[wort]
    return None


def _spalten(kopf: tuple) -> tuple[int, int] | None:
    """Spalten „Richtung Krailling“ und „Richtung Planegg“ im Kopf (Schreibweisen der Quelle)."""
    k = p = None
    for i, c in enumerate(kopf):
        t = str(c or "").strip().lower()
        if t.startswith("richtung krail"):
            k = i
        elif t.startswith("richtung planegg"):
            p = i
    return (k, p) if k is not None and p is not None else None


def _zahl(x) -> int | None:
    if isinstance(x, bool) or x is None:
        return None
    if isinstance(x, int):
        return x if x >= 0 else None
    if isinstance(x, float) and x.is_integer() and x >= 0:
        return int(x)
    return None


def lies_blatt(name: str, zeilen: list[tuple], korrigieren: bool, bericht: Bericht
               ) -> list[tuple[date, int]]:
    """Zeilen eines Monatsblatts -> [(Tag, Summe beider Richtungen)]."""
    bericht.blaetter += 1
    monat = monat_des_blatts(name, zeilen)
    kopf = next((i for i, z in enumerate(zeilen)
                 if z and isinstance(z[0], str) and z[0].strip().lower() == "datum"), None)
    spalten = _spalten(zeilen[kopf]) if kopf is not None else None
    if monat is None or spalten is None:
        bericht.ohne_kopf.append(name)
        return []
    out = []
    for z in zeilen[kopf + 1:]:
        if not z or not isinstance(z[0], datetime):
            continue  # Leerzeilen, „Summe“
        bericht.tageszeilen += 1
        tag = z[0].date()
        if (tag.year, tag.month) != monat:
            if not korrigieren:
                bericht.falscher_monat[name] += 1
                continue
            try:
                tag = date(monat[0], monat[1], tag.day)
            except ValueError:
                bericht.falscher_monat[name] += 1
                continue
            bericht.monat_korrigiert[name] += 1
        a, b = (_zahl(z[i]) if i < len(z) else None for i in spalten)
        if a is None or b is None:
            bericht.ohne_wert += 1
            continue
        out.append((tag, a + b))
    return out


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import openpyxl

    ordner = pfade.roh / q["code"]
    if not (ordner / ABRUF).exists():
        raise ValueError(f"{q['code']}: keine Dateien in {ordner} – erst `zaehlkarte dauer fetch`")
    jahre = sorted(json.loads((ordner / ABRUF).read_text(encoding="utf-8"))["dateien"])
    korrektur = set(q.get("monat_laut_blatt") or [])
    eintraege: list[tuple[date, int]] = []
    for jahr in jahre:
        bericht.jahre.append(jahr)
        mappe = openpyxl.load_workbook(ordner / f"{jahr}.xlsx", read_only=True, data_only=False)
        for name in mappe.sheetnames:
            zeilen = list(mappe[name].iter_rows(values_only=True))
            # „Februar 2025“ und „Februar  2025“ gelten gleich
            eintraege += lies_blatt(name, zeilen, " ".join(name.split()) in korrektur, bericht)
        mappe.close()
    if not eintraege:
        raise ValueError(f"{q['code']}: keine Tageswerte in {ordner}")
    s = q["stelle"]
    stelle = Dauerstelle(quelle=q["code"], kennung=s["kennung"], name=s["strasse"],
                         abschnitt=s.get("abschnitt"), richtung=s.get("richtung"),
                         lon=float(s["lon"]), lat=float(s["lat"]), land=q["land"],
                         hinweise=list(s.get("hinweise") or []))
    von = min(t for t, _ in eintraege)
    bis = max(t for t, _ in eintraege)
    reihe = Messreihe.leer(q["code"], von, bis, [stelle], ("rad",), tagesgruppen=("rad",))
    bericht.tage, bericht.widerspruch = setze_tage(
        reihe, "rad", np.zeros(len(eintraege), dtype=np.int64),
        np.array([t for t, _ in eintraege], dtype="datetime64[D]"),
        np.array([w for _, w in eintraege], dtype=np.int64))
    bericht.nullen = sum(1 for _, w in eintraege if w == 0)
    kuerze(reihe)
    bericht.zeitraum = f"{reihe.von.isoformat()} bis {reihe.tag(reihe.tage - 1).isoformat()}"
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Tageswerte je Richtung laut Excel-Dateien der Gemeinde, beide Richtungen "
                        "summiert (keine Stunden)")]
    return reihe
