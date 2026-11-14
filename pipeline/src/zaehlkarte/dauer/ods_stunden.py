"""Opendatasoft-Datensätze mit Stundenwerten, deren Felder die Quelldatei nennt (Stadt Neuss: RS5;
Würzburg: Passantenzählung) – ein Export je Datensatz über `ods.hole_export`, Zeiten in UTC.

Die Quelldatei legt fest:
- `basis`, `datensatz` (Opendatasoft), `gruppe` (rad, fuss, …);
- `zeit`: Feld mit dem Beginn der Stunde (Datum mit Uhrzeit; der Export liefert es in UTC);
- `werte`: Felder, die zusammen den Wert der Stunde ergeben (etwa beide Richtungen) – fehlt
  eines, ist die Stunde nicht gezählt;
- `stelle`: Feld mit dem Standort (mehrere Zählstellen in einem Datensatz) oder keins;
- `stellen`: je Standort (Wert des Felds `stelle`, sonst `""`) Kennung, Name, Abschnitt, Lage und
  Hinweise. Standorte ohne Eintrag kommen nicht in die Karte (Bericht).
`hole` legt die Metadaten (Felder, Beschreibung) neben den Export (`metadaten.json`); fehlen
`zeit` oder `werte`, nennt `lese` die Spalten des Exports.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import ods
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc

DATEI = "export.csv"


@dataclass
class Bericht:
    gelesen: int = 0
    unlesbar: int = 0
    leer: int = 0
    doppelt: int = 0
    ohne_stelle: Counter = field(default_factory=Counter)
    stunden: int = 0
    stellen: int = 0
    bis: str | None = None

    def zeilen(self) -> list[str]:
        z = [f"{self.gelesen} Zeilen ({self.unlesbar} unlesbar, {self.leer} ohne alle Werte, "
             f"{self.doppelt} Stunden doppelt), {self.stellen} Zählstellen, {self.stunden} "
             f"Stunden in der Karte; jüngster Wert {self.bis}"]
        if self.ohne_stelle:
            z.append("Standorte ohne Eintrag in der Quelldatei (nicht in der Karte): "
                     + ", ".join(f"{k} ({n})" for k, n in self.ohne_stelle.most_common()))
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    meta = ods.metadaten(q["basis"], q["datensatz"])
    (ordner / "metadaten.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n",
                                           encoding="utf-8")
    felder = [q["zeit"], *q["werte"]] + ([q["stelle"]] if q.get("stelle") else []) \
        if q.get("zeit") and q.get("werte") else None
    return [ods.hole_export(q["basis"], q["datensatz"], ",".join(felder) if felder else None,
                            ordner, DATEI)]


def stunde(text: str) -> datetime | None:
    """„2026-07-13T10:00:00+00:00“ -> naive UTC-Zeit, nur auf voller Stunde."""
    try:
        t = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is not None:
        t = (t - t.utcoffset()).replace(tzinfo=None)
    return t if t.minute == 0 and t.second == 0 else None


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    pfad = pfade.roh / q["code"] / DATEI
    if not pfad.exists():
        raise ValueError(f"{q['code']}: kein Export {pfad} – erst `zaehlkarte dauer fetch`")
    text = pfad.read_bytes().decode("utf-8-sig")
    leser = csv.DictReader(io.StringIO(text), delimiter=";")
    if not q.get("zeit") or not q.get("werte") or q["zeit"] not in (leser.fieldnames or []):
        raise ValueError(f"{q['code']}: `zeit` und `werte` in der Quelldatei festlegen – Spalten "
                         f"des Exports: {leser.fieldnames}; erste Zeilen: "
                         f"{text.splitlines()[1:4]}")
    stellen_cfg: dict = q["stellen"]
    index: dict[str, int] = {}
    stellen: list[Dauerstelle] = []
    eintraege: dict[tuple[int, datetime], int] = {}
    doppelt: set[tuple[int, datetime]] = set()
    for r in leser:
        bericht.gelesen += 1
        t = stunde(r.get(q["zeit"]) or "")
        if t is None:
            bericht.unlesbar += 1
            continue
        ort = (r.get(q["stelle"]) or "").strip() if q.get("stelle") else ""
        if ort not in stellen_cfg:
            bericht.ohne_stelle[ort or "(ohne Standort)"] += 1
            continue
        if ort not in index:
            info = stellen_cfg[ort]
            index[ort] = len(stellen)
            stellen.append(Dauerstelle(
                quelle=q["code"], kennung=str(info["kennung"]), name=info["name"],
                abschnitt=info.get("abschnitt"), richtung=info.get("richtung"),
                lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
                hinweise=list(info.get("hinweise") or [])))
        werte = [(r.get(f) or "").strip() for f in q["werte"]]
        if not any(werte):
            bericht.leer += 1
            continue
        try:
            w = sum(int(round(float(x))) for x in werte) if all(werte) else -1
        except ValueError:
            w = -1
        schluessel = (index[ort], t)
        if schluessel in eintraege:
            doppelt.add(schluessel)
        eintraege[schluessel] = w
    for s in doppelt:  # dieselbe Stunde zweimal: nicht gezählt
        eintraege[s] = -1
    bericht.doppelt = len(doppelt)
    if not eintraege:
        raise ValueError(f"{q['code']}: keine Werte in {pfad}")
    bericht.stellen = len(stellen)
    zeiten = np.array([t for _, t in eintraege], dtype="datetime64[h]")
    von = (zeiten.min().astype(datetime) - timedelta(days=1)).date()
    bis = (zeiten.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, (q["gruppe"],))
    st = np.array([s for s, _ in eintraege], dtype=np.int64)
    ww = np.array(list(eintraege.values()), dtype=np.int64)
    bericht.stunden = setze_utc(reihe, q["gruppe"], st, zeiten, ww)
    kuerze(reihe)
    bericht.bis = reihe.tag(reihe.tage - 1).isoformat()
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        f"Stundenwerte aus dem Opendatasoft-Export ({', '.join(q['werte'])})")]
    return reihe
