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
- `tage` (optional): ein zweiter Datensatz mit Tageswerten je Standort und Ortstag (`datensatz`,
  `zeit` mit dem Datum, `werte`; `stelle` wie oben). Sie kommen als Tageswerte der Quelle in die
  Reihe (`Messreihe.tageswerte`) – nur an Tagen vor der ersten gezählten Stunde einer Stelle
  (Würzburg: Passanten-Tagesdaten seit 2020, Stunden erst seit 2024).
`hole` legt die Metadaten (Felder, Beschreibung) neben den Export (`metadaten.json`); fehlen
`zeit` oder `werte`, nennt `lese` die Spalten des Exports.
"""

from __future__ import annotations

import csv
import io
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import ods
from zaehlkarte.dauer.modell import (
    Dauerstelle,
    Messreihe,
    aus_tageswerten,
    kuerze,
    setze_tage,
    setze_utc,
    verfahren_mit_tageswerten,
)

DATEI = "export.csv"
TAGE = "tage.csv"


@dataclass
class Bericht:
    gelesen: int = 0
    unlesbar: int = 0
    leer: int = 0
    doppelt: int = 0
    ohne_stelle: Counter = field(default_factory=Counter)
    zeitraum: dict = field(default_factory=dict)  # Kennung -> [erste, letzte Stunde] (UTC)
    stunden: int = 0
    stellen: int = 0
    bis: str | None = None
    # Tageswerte der Quelle (`tage` in der Quelldatei)
    tage_gelesen: int = 0
    tage_unlesbar: int = 0
    tage_widerspruch: int = 0
    tage_zeitraum: dict = field(default_factory=dict)  # Kennung -> [erster, letzter Tag]
    tageswerte: int = 0  # in der Karte (vor der ersten gezählten Stunde der Stelle)

    def zeilen(self) -> list[str]:
        z = [f"{self.gelesen} Zeilen ({self.unlesbar} unlesbar, {self.leer} ohne alle Werte, "
             f"{self.doppelt} Stunden doppelt), {self.stellen} Zählstellen, {self.stunden} "
             f"Stunden in der Karte; jüngster Wert {self.bis}"]
        z += [f"{k}: {a} bis {b} (UTC)" for k, (a, b) in sorted(self.zeitraum.items())]
        if self.tage_gelesen:
            z.append(f"Tageswerte der Quelle: {self.tage_gelesen} Zeilen ({self.tage_unlesbar} "
                     f"unlesbar, {self.tage_widerspruch} Tage widersprüchlich), in der Karte "
                     f"{self.tageswerte}")
            z += [f"{k}: Tageswerte {a} bis {b}"
                  for k, (a, b) in sorted(self.tage_zeitraum.items())]
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
    log = [ods.hole_export(q["basis"], q["datensatz"], ",".join(felder) if felder else None,
                           ordner, DATEI)]
    if t := q.get("tage"):
        stelle = t.get("stelle", q.get("stelle"))
        felder = [t["zeit"], *t["werte"]] + ([stelle] if stelle else [])
        log.append(ods.hole_export(q["basis"], t["datensatz"], ",".join(felder), ordner, TAGE))
    return log


def tag(text: str) -> date | None:
    """„2020-01-01“ (auch mit Uhrzeit 0 Uhr) -> Datum."""
    text = text.strip()
    try:
        d = date.fromisoformat(text[:10])
    except ValueError:
        return None
    return d if len(text) == 10 or text[10:].lstrip("T ").startswith("00:00") else None


def _stelle(q: dict, ort: str, stellen: list[Dauerstelle], index: dict[str, int]) -> int:
    """Index der Stelle zum Standort `ort` (legt sie aus der Quelldatei an)."""
    if ort not in index:
        info = q["stellen"][ort]
        index[ort] = len(stellen)
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=str(info["kennung"]), name=info["name"],
            abschnitt=info.get("abschnitt"), richtung=info.get("richtung"),
            lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
            hinweise=list(info.get("hinweise") or [])))
    return index[ort]


def _tageswerte(q: dict, pfade: Pfade, stellen: list[Dauerstelle], index: dict[str, int],
                bericht: Bericht) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Tageswerte der Quelle (`tage` in der Quelldatei) -> (Stelle, Tag, Wert) oder None; eine
    Stelle nur mit Tageswerten wird angelegt."""
    t = q.get("tage")
    if not t:
        return None
    pfad = pfade.roh / q["code"] / TAGE
    if not pfad.exists():
        raise ValueError(f"{q['code']}: kein Export {pfad} – erst `zaehlkarte dauer fetch`")
    stelle = t.get("stelle", q.get("stelle"))
    s_, t_, w_ = [], [], []
    for r in csv.DictReader(io.StringIO(pfad.read_bytes().decode("utf-8-sig")), delimiter=";"):
        bericht.tage_gelesen += 1
        d = tag(r.get(t["zeit"]) or "")
        ort = (r.get(stelle) or "").strip() if stelle else ""
        werte = [(r.get(f) or "").strip() for f in t["werte"]]
        if d is None or ort not in q["stellen"] or not all(werte):
            bericht.tage_unlesbar += 1
            continue
        try:
            w = sum(int(round(float(x))) for x in werte)
        except ValueError:
            bericht.tage_unlesbar += 1
            continue
        s_.append(_stelle(q, ort, stellen, index))
        t_.append(d)
        w_.append(w)
        kennung = str(q["stellen"][ort]["kennung"])
        a, b = bericht.tage_zeitraum.get(kennung, (d, d))
        bericht.tage_zeitraum[kennung] = (min(a, d), max(b, d))
    bericht.tage_zeitraum = {k: [a.isoformat(), b.isoformat()]
                             for k, (a, b) in bericht.tage_zeitraum.items()}
    if not s_:
        return None
    return (np.array(s_, dtype=np.int64), np.array(t_, dtype="datetime64[D]"),
            np.array(w_, dtype=np.int64))


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
        _stelle(q, ort, stellen, index)
        werte = [(r.get(f) or "").strip() for f in q["werte"]]
        if not any(werte):
            bericht.leer += 1
            continue
        try:
            w = sum(int(round(float(x))) for x in werte) if all(werte) else -1
        except ValueError:
            w = -1
        kennung = stellen[index[ort]].kennung
        a, b = bericht.zeitraum.get(kennung, (t, t))
        bericht.zeitraum[kennung] = (min(a, t), max(b, t))
        schluessel = (index[ort], t)
        if schluessel in eintraege:
            doppelt.add(schluessel)
        eintraege[schluessel] = w
    for s in doppelt:  # dieselbe Stunde zweimal: nicht gezählt
        eintraege[s] = -1
    bericht.doppelt = len(doppelt)
    bericht.zeitraum = {k: [a.isoformat(timespec="minutes"), b.isoformat(timespec="minutes")]
                        for k, (a, b) in bericht.zeitraum.items()}
    if not eintraege:
        raise ValueError(f"{q['code']}: keine Werte in {pfad}")
    zeiten = np.array([t for _, t in eintraege], dtype="datetime64[h]")
    von = (zeiten.min().astype(datetime) - timedelta(days=1)).date()
    bis = (zeiten.max().astype(datetime) + timedelta(days=1)).date()
    tage = _tageswerte(q, pfade, stellen, index, bericht)
    bericht.stellen = len(stellen)
    if tage is not None:
        von, bis = min(von, tage[1].min().astype(date)), max(bis, tage[1].max().astype(date))
    gruppe = q["gruppe"]
    reihe = Messreihe.leer(q["code"], von, bis, stellen, (gruppe,),
                           tagesgruppen=(gruppe,) if tage is not None else ())
    st = np.array([s for s, _ in eintraege], dtype=np.int64)
    ww = np.array(list(eintraege.values()), dtype=np.int64)
    bericht.stunden = setze_utc(reihe, gruppe, st, zeiten, ww)
    if tage is not None:
        _, bericht.tage_widerspruch = setze_tage(reihe, gruppe, *tage)
    kuerze(reihe)
    if tage is not None:
        bericht.tageswerte = int(aus_tageswerten(reihe, gruppe).sum())
    bericht.bis = reihe.tag(reihe.tage - 1).isoformat()
    stunden_text = f"Stundenwerte aus dem Opendatasoft-Export ({', '.join(q['werte'])})"
    reihe.verfahren = verfahren_mit_tageswerten(
        reihe,
        f"Vor der ersten gezählten Stunde einer Zählstelle die Tageswerte der Quelle (Datensatz "
        f"„{q['tage']['datensatz']}“, je Ortstag wie geliefert – ob jede Stunde gezählt ist, "
        f"lässt sich nicht prüfen); danach {stunden_text}" if tage is not None else "",
        stunden_text)
    return reihe
