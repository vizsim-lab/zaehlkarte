"""Augsburg: Radzählstationen der Stadt (Radverkehrsbeauftragter) – Tageswerte je Station seit
September 2016, eine CSV auf augsburg.de (Mobilithek-Angebot -4859503742463304999, CC BY 4.0).
Die erste Quelle nur mit Tageswerten: in der Karte als Tageswerte der Quelle (modell.py).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/erkundung`, tools/holen.py Runde 17):
- Zeile 1 „Zeitraum,16. September 2016 - 11. August 2026“, eine Leerzeile, dann der Kopf
  „Zeit,Dieselbrücke,…,Wagenhalsstraße“ und je Tag eine Zeile „2026-08-10 00:00:00,2076,…“ mit
  einem Wert je Station (leer: die Station zählte noch nicht oder fiel aus).
- Der Kopf ist nicht gequotet: „Südlich A8-Unterführung, Ostseite“ zerfällt an seinem Komma. Die
  Quelldatei nennt die Stationen deshalb in der Reihenfolge der Spalten (`stationen`); der Kopf
  muss genau ihre Namen tragen, sonst bricht der Bau ab (die Spalten könnten sich verschoben
  haben).
- Der letzte Tag des Zeitraums ist der Tag, an dem die Datei entstand – nur zum Teil gezählt
  (11.08.2026: 3 bis 556 statt rund 1.000 bis 4.000). Die Zählkarte übernimmt ihn nicht.
- Keine Stunden: Ob ein Tag vollständig gezählt ist, lässt sich nicht prüfen; der Tageswert gilt
  wie geliefert (auch 0), ein leerer Wert als nicht gezählt.
- Lage: Die Quelle nennt nur die Beschreibung der Station; Punkte in der Quelldatei (OSM), dort
  auch Straße und Abschnitt für die Karte (`strasse`, `abschnitt`; `name` wie im Kopf).
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_tage

DATEI = "zaehler.csv"
MONATE = {m: i for i, m in enumerate(
    ("januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
     "oktober", "november", "dezember"), start=1)}
DATUM = re.compile(r"(\d{1,2})\.\s*([A-Za-zÄÖÜäöü]+)\s+(\d{4})")


@dataclass
class Bericht:
    gelesen: int = 0
    unlesbar: int = 0  # Zeilen ohne lesbares Datum oder mit falscher Zahl von Spalten
    unlesbare_werte: int = 0
    tage: int = 0
    widerspruch: int = 0
    nullen: Counter = field(default_factory=Counter)
    zeitraum: str | None = None
    weggelassen: str | None = None
    bis: str | None = None

    def zeilen(self) -> list[str]:
        z = [f"{self.gelesen} Zeilen ({self.unlesbar} unlesbar, {self.unlesbare_werte} unlesbare "
             f"Werte), {self.tage} Tageswerte in der Karte (widersprüchlich: {self.widerspruch}); "
             f"Zeitraum laut Datei: {self.zeitraum}; "
             f"nicht übernommen (Tag der Erstellung): {self.weggelassen}; jüngster Tag {self.bis}"]
        if self.nullen:
            z.append("Tage mit 0: " + ", ".join(f"{k} {n}" for k, n in self.nullen.most_common()))
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    from zaehlkarte import abruf

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    abruf.lade(q["datei"], ordner / DATEI)
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "datei": q["datei"]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Datei geholt"]


def deutsches_datum(text: str) -> date | None:
    """„11. August 2026“ -> date(2026, 8, 11)."""
    m = DATUM.search(text)
    if not m or m[2].lower() not in MONATE:
        return None
    return date(int(m[3]), MONATE[m[2].lower()], int(m[1]))


def zeitraum(zeile: str) -> tuple[date | None, date | None]:
    """„Zeitraum,16. September 2016 - 11. August 2026“ -> (Anfang, Ende)."""
    teile = zeile.split(",", 1)[-1].split(" - ")
    if len(teile) != 2:
        return None, None
    return deutsches_datum(teile[0]), deutsches_datum(teile[1])


def wert(text: str) -> int | None:
    """„2076“ -> 2076; leer -> None (nicht gezählt); unlesbar -> ValueError."""
    text = text.strip()
    if not text:
        return None
    v = float(text)
    if v < 0 or v != int(v):
        raise ValueError(text)
    return int(v)


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    pfad = pfade.roh / q["code"] / DATEI
    if not pfad.exists():
        raise ValueError(f"{q['code']}: keine Datei {pfad} – erst `zaehlkarte dauer fetch`")
    roh = pfad.read_bytes()
    try:
        text = roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = roh.decode("cp1252")
    zeilen = text.splitlines()
    anfang, ende = zeitraum(zeilen[0]) if zeilen and zeilen[0].startswith("Zeitraum") else (None,
                                                                                            None)
    bericht.zeitraum = f"{anfang} – {ende}" if ende else None
    kopf = next((i for i, z in enumerate(zeilen) if z.startswith("Zeit,")), None)
    namen = [s["name"] for s in q["stationen"]]
    if kopf is None or zeilen[kopf].split(",", 1)[1].strip() != ",".join(namen):
        raise ValueError(f"{q['code']}: Kopf der Datei passt nicht zu `stationen` in der "
                         f"Quelldatei: {zeilen[kopf] if kopf is not None else zeilen[:3]}")
    stellen = [Dauerstelle(  # `name` wie im Kopf; in der Karte `strasse` und `abschnitt`
        quelle=q["code"], kennung=s["kennung"], name=s.get("strasse") or s["name"],
        abschnitt=s.get("abschnitt"),
        richtung=None, lon=float(s["lon"]), lat=float(s["lat"]), land=q["land"],
        hinweise=list(s.get("hinweise") or [])) for s in q["stationen"]]
    eintraege: list[tuple[int, date, int]] = []
    for r in csv.reader(io.StringIO("\n".join(zeilen[kopf + 1:]))):
        if not r or not any(x.strip() for x in r):
            continue
        bericht.gelesen += 1
        try:
            tag = datetime.strptime(r[0].strip()[:10], "%Y-%m-%d").date()
        except ValueError:
            bericht.unlesbar += 1
            continue
        if len(r) - 1 != len(stellen):
            bericht.unlesbar += 1
            continue
        for i, x in enumerate(r[1:]):
            try:
                w = wert(x)
            except ValueError:  # ein unlesbarer Wert: an dem Tag an der Station nicht gezählt
                bericht.unlesbare_werte += 1
                continue
            if w is not None:
                eintraege.append((i, tag, w))
    if not eintraege:
        raise ValueError(f"{q['code']}: keine Werte in {pfad}")
    # der Tag der Erstellung (Ende des Zeitraums, sonst der letzte Tag der Datei): nur zum Teil
    letzter = ende or max(t for _, t, _ in eintraege)
    bericht.weggelassen = letzter.isoformat()
    eintraege = [e for e in eintraege if e[1] < letzter]
    von = min(t for _, t, _ in eintraege)
    bis = max(t for _, t, _ in eintraege)
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",), tagesgruppen=("rad",))
    st = np.array([e[0] for e in eintraege], dtype=np.int64)
    tg = np.array([e[1] for e in eintraege], dtype="datetime64[D]")
    ww = np.array([e[2] for e in eintraege], dtype=np.int64)
    bericht.tage, bericht.widerspruch = setze_tage(reihe, "rad", st, tg, ww)
    bericht.nullen = Counter(stellen[i].name for i, _, w in eintraege if w == 0)
    kuerze(reihe)
    bericht.bis = reihe.tag(reihe.tage - 1).isoformat()
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Tageswerte je Station laut Datei der Stadt (keine Stunden)")]
    return reihe
