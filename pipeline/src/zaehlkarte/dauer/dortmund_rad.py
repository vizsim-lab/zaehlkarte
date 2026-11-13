"""Dortmund: Dauerzählstelle Radverkehr Schnettkerbrücke der Stadt – 15-Minuten-Werte je Richtung
seit dem 23.01.2018 im Opendatasoft-Portal der Stadt, täglich aktualisiert.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12/13.py):
- Export mit `zeitpunkt_utc` – trotz des Namens die Ortszeit mit Versatz („2026-08-07T19:00:00
  +02:00“; `zeitpunkt` ist dieselbe Ortszeit, aber als UTC ausgewiesen) –, `radfahrer` und den
  Richtungen `aus_fahrtrichtung_tu`, `in_fahrtrichtung_tu`.
- Gezählt ist eine Viertelstunde mit Zahl in `radfahrer`, gleich der Summe der Richtungen; eine
  Stunde, wenn alle vier Viertelstunden gezählt sind (über den Versatz in UTC – die Zeitumstellung
  ist damit eindeutig).
- Die Lage steht nicht im Datensatz: `stellen` in sources.yaml.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import ods
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc, utc_stunden

FELDER = "zeitpunkt_utc,radfahrer,aus_fahrtrichtung_tu,in_fahrtrichtung_tu"
DATEI = "daten.csv"


@dataclass
class Bericht:
    viertelstunden: int = 0
    nicht: Counter = field(default_factory=Counter)  # Grund -> Viertelstunden (nicht gezählt)
    doppelt_verschieden: int = 0
    stunden: int = 0

    def zeilen(self) -> list[str]:
        return [f"{self.viertelstunden} Viertelstunden; nicht gezählt: "
                + (", ".join(f"{k} {n}" for k, n in self.nicht.most_common()) or "keine")
                + f"; doppelt mit verschiedenen Werten: {self.doppelt_verschieden}; "
                f"Stunden in der Karte: rad {self.stunden}"]


def hole(q: dict, pfade: Pfade) -> list[str]:
    return [f"{q['code']}: " + ods.hole_export(q["basis"], q["datensatz"], FELDER,
                                               pfade.roh / q["code"], DATEI)]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import pandas as pd

    pfad = pfade.roh / q["code"] / DATEI
    if not pfad.exists():
        raise ValueError(f"{q['code']}: kein Export in {pfad.parent} – erst "
                         "`zaehlkarte dauer fetch`")
    df = pd.read_csv(pfad, sep=";", dtype=str, keep_default_na=False)
    bericht.viertelstunden = len(df)
    t = pd.to_datetime(df["zeitpunkt_utc"], utc=True, errors="coerce", format="ISO8601")
    zahl = {k: pd.to_numeric(df[k], errors="coerce")
            for k in ("radfahrer", "aus_fahrtrichtung_tu", "in_fahrtrichtung_tu")}
    gezaehlt = zahl["radfahrer"].notna() & (zahl["radfahrer"] >= 0)
    richtungen = zahl["aus_fahrtrichtung_tu"] + zahl["in_fahrtrichtung_tu"]
    abweichend = gezaehlt & richtungen.notna() & (richtungen != zahl["radfahrer"])
    bericht.nicht["Zeit unlesbar"] = int(t.isna().sum())
    bericht.nicht["ohne Wert"] = int((~gezaehlt & t.notna()).sum())
    bericht.nicht["Summe ≠ Richtungen"] = int((abweichend & t.notna()).sum())
    bericht.nicht["nicht auf der Viertelstunde"] = int((t.notna() & (t.dt.minute % 15 != 0)).sum())
    bericht.nicht = Counter({k: n for k, n in bericht.nicht.items() if n})
    # Zeilen ohne Wert (etwa die Stunde der Sommerzeit, die es nicht gibt) zählen nicht mit
    da = t.notna() & (t.dt.minute % 15 == 0) & zahl["radfahrer"].notna()
    w = np.where(gezaehlt & ~abweichend, zahl["radfahrer"].fillna(-1), -1)[da.to_numpy()]
    utc = t[da].dt.tz_localize(None).to_numpy().astype("datetime64[m]")
    k, info = next(iter(q["stellen"].items()))
    stellen = [Dauerstelle(
        quelle=q["code"], kennung=str(k), name=info["name"], abschnitt=info.get("abschnitt"),
        richtung=None, lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
        hinweise=[])]
    s_, h_, w_, bericht.doppelt_verschieden = utc_stunden(
        np.zeros(len(utc), dtype=np.int64), utc, w.astype(np.int64), 4)
    if not len(h_):
        raise ValueError(f"{q['code']}: keine vollständig gezählte Stunde")
    von = (h_.min().astype(datetime) - timedelta(days=1)).date()
    bis = (h_.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    bericht.stunden = setze_utc(reihe, "rad", s_, h_, w_)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "15-Minuten-Werte (beide Richtungen) zu Stunden zusammengefasst")]
    return reihe
