"""Augsburg: Passantenzählung in der Annastraße (Stadt Augsburg, Wirtschaftsförderung) – Personen
je Stunde seit 16.12.2020, eine CSV auf augsburg.de (Mobilithek-Angebot -1747083335311792689,
CC BY 4.0). Die erste Quelle der Gruppe Fuß.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/erkundung`, tools/holen.py Runde 11):
- `Standort;Jahr;Datum;Stunde;Passanten` – „Annastraße;2020;Mi., 16.12.2020;13 Uhr;521“, UTF-8
  mit BOM, Ortszeit. Der Pfad der Datei trägt ein Datum („…/opendata/240429/…“), die Datei wird
  aber fortgeschrieben (zuletzt 11.08.2026).
- Keine Stunde hat den Wert 0; es fehlen Stunden, fast nur nachts (2 bis 4 Uhr, dort sonst Werte
  von 1 bis 3) – vermutlich Stunden ohne Passanten. Die Zählkarte füllt nichts auf: eine fehlende
  Stunde gilt als nicht gezählt, der Tag als nicht vollständig.
- Sommerzeit: 2 Uhr fehlt. Rückstellung: 2 Uhr steht einmal; ob mit beiden Stunden, ist nicht
  eindeutig (2023 und 2024 rund das Doppelte, 2021, 2022 und 2025 nicht) – `rueck: einfach`, der
  Tag gilt als nicht vollständig. Eine doppelte Stunde (09.10.2025, 13 Uhr) gilt als nicht gezählt.
- Lage: die Datei nennt nur „Annastraße“ – Punkt in der Quelldatei (`lage`).
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_lokal


@dataclass
class Bericht:
    gelesen: int = 0
    unlesbar: int = 0
    stunden: int = 0
    sommerzeit: int = 0
    standorte: list[str] = field(default_factory=list)
    bis: str | None = None

    def zeilen(self) -> list[str]:
        return [f"{self.gelesen} Zeilen ({self.unlesbar} unlesbar), Standorte "
                f"{', '.join(self.standorte)}, {self.stunden} Stunden in der Karte (2 Uhr am Tag "
                f"der Sommerzeit verworfen: {self.sommerzeit}); jüngster Wert {self.bis}"]


def hole(q: dict, pfade: Pfade) -> list[str]:
    from zaehlkarte import abruf

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    abruf.lade(q["datei"], ordner / "passanten.csv")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "datei": q["datei"]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Datei geholt"]


def zeile(r: dict) -> tuple[date, int, int] | None:
    """„Mi., 16.12.2020“, „13 Uhr“, „521“ -> (Tag, 13, 521)."""
    try:
        tag = datetime.strptime(r["Datum"].split(",")[-1].strip(), "%d.%m.%Y").date()
        stunde = int(r["Stunde"].split()[0])
        wert = int(r["Passanten"].strip())
    except (KeyError, ValueError, AttributeError, IndexError):
        return None
    if not 0 <= stunde <= 23 or wert < 0:
        return None
    return tag, stunde, wert


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    pfad = pfade.roh / q["code"] / "passanten.csv"
    if not pfad.exists():
        raise ValueError(f"{q['code']}: keine Datei {pfad} – erst `zaehlkarte dauer fetch`")
    text = pfad.read_bytes().decode("utf-8-sig")
    je_ort: dict[str, list[tuple[date, int, int]]] = {}
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        bericht.gelesen += 1
        z = zeile(r)
        if z is None:
            bericht.unlesbar += 1
            continue
        je_ort.setdefault((r.get("Standort") or "").strip(), []).append(z)
    lagen = q["lage"]
    stellen, eintraege = [], []
    for ort in sorted(je_ort):
        if ort not in lagen:
            raise ValueError(f"{q['code']}: Standort {ort!r} ohne Lage in der Quelldatei")
        i = len(stellen)
        lage = lagen[ort]
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=lage.get("kennung") or ort, name=ort,
            abschnitt=lage.get("abschnitt"), richtung=None, lon=float(lage["lon"]),
            lat=float(lage["lat"]), land=q["land"], hinweise=list(lage.get("hinweise") or [])))
        eintraege += [(i, t, h, w) for t, h, w in je_ort[ort]]
    if not stellen:
        raise ValueError(f"{q['code']}: keine Werte in {pfad}")
    bericht.standorte = [s.name for s in stellen]
    von = min(e[1] for e in eintraege)
    bis = max(e[1] for e in eintraege)
    bericht.bis = bis.isoformat()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("fuss",))
    st = np.array([e[0] for e in eintraege], dtype=np.int64)
    tg = np.array([e[1] for e in eintraege], dtype="datetime64[D]")
    hh = np.array([e[2] for e in eintraege], dtype=np.int64)
    ww = np.array([e[3] for e in eintraege], dtype=np.int64)
    bericht.stunden, bericht.sommerzeit = setze_lokal(reihe, "fuss", st, tg, hh, ww, anzahl=1,
                                                      rueck=q.get("rueck", "einfach"))
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Passanten je Stunde laut Datei der Stadt, zu Tagessummen zusammengefasst")]
    return reihe
