"""Bochum: Zählstellen Rad- und Fußverkehr der Stadt (Eco-Counter) – 15-Minuten-Werte je Richtung,
Rad und Fuß getrennt, täglich über die Eco-Counter-API abgerufen und im GitLab der Stadt
(openCode.de) abgelegt; eine Gesamtdatei je Zählstelle.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12–14.py):
- `data/<stelle>/bochum_ecocounter_<stelle>.csv`: `timestamp` (Ortszeit mit Versatz),
  `timestamp_utc`, `name`, `radfahrende_in`, `radfahrende_out`, an manchen Stellen dazu
  `passanten_in`, `passanten_out` (in der Karte nicht verwendet – Fuß ist eine eigene Zählung).
- Eine Viertelstunde ist gezählt, wenn beide Rad-Richtungen einen Wert haben; eine Stunde, wenn
  alle vier Viertelstunden gezählt sind (in UTC – die Zeitumstellung ist damit eindeutig). An
  einzelnen Tagen stehen nur volle Stunden da (die übrigen Viertelstunden leer) – nicht gezählt.
- Laut README verarbeitet die Stadt die Kanäle der API selbst („pick best block“ je Richtung,
  Summe bei der alten Springorumtrasse); an der Springorumtrasse Süd vermutet sie für Rad fehlende
  Kanäle – die Stelle steht unter `ohne`.
- Lage und Namen: Tabelle im README des Repositories (`stellen` in sources.yaml).
"""

from __future__ import annotations

import json
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc, utc_stunden

RAD = ("radfahrende_in", "radfahrende_out")


@dataclass
class Bericht:
    viertelstunden: int = 0
    unvollstaendig: Counter = field(default_factory=Counter)  # je Stelle: ohne beide Richtungen
    doppelt_verschieden: int = 0
    stellen: int = 0
    ohne: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{self.viertelstunden} Viertelstunden; ohne beide Rad-Richtungen (nicht gezählt): "
             + (", ".join(f"{k} {n}" for k, n in self.unvollstaendig.most_common()) or "keine")
             + f"; doppelt mit verschiedenen Werten: {self.doppelt_verschieden}; "
             f"{self.stellen} Zählstellen; Stunden in der Karte: rad {self.stunden}"]
        if self.ohne:
            z.append(f"nicht in der Karte (sources.yaml `ohne`): {', '.join(self.ohne)}")
        return z


def datei_url(q: dict, stelle: str) -> str:
    pfad = urllib.parse.quote(f"data/{stelle}/bochum_ecocounter_{stelle}.csv", safe="")
    projekt = urllib.parse.quote(q["projekt"], safe="")
    return f"{q['api']}/projects/{projekt}/repository/files/{pfad}/raw?ref={q.get('zweig', 'main')}"


def hole(q: dict, pfade: Pfade) -> list[str]:
    from zaehlkarte.fetch import lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    ohne = set(q.get("ohne") or {})
    geholt, fehler = [], []
    for stelle in q["stellen"]:
        if stelle in ohne:
            continue
        try:
            lade(datei_url(q, stelle), ordner / f"{stelle}.csv")
            geholt.append(stelle)
        except Exception as e:  # noqa: BLE001 – eine Stelle darf die anderen nicht aufhalten
            fehler.append(f"{stelle} ({e!r})")
    if not geholt:
        raise ValueError(f"{q['code']}: keine Datei geholt – {', '.join(fehler)}")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "stellen": geholt, "fehler": fehler,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(geholt)} Zählstellen geholt"
            + (f"; Fehler: {', '.join(fehler)}" if fehler else "")]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import pandas as pd

    ordner = pfade.roh / q["code"]
    ohne = set(q.get("ohne") or {})
    stellen, s_l, t_l, w_l = [], [], [], []
    for k, info in q["stellen"].items():
        if k in ohne:
            bericht.ohne.append(k)
            continue
        pfad = ordner / f"{k}.csv"
        if not pfad.exists():
            continue
        df = pd.read_csv(pfad, dtype=str, keep_default_na=False)
        bericht.viertelstunden += len(df)
        t = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce", format="ISO8601")
        rad = [pd.to_numeric(df[c], errors="coerce") for c in RAD]
        beide = rad[0].notna() & rad[1].notna() & t.notna()
        bericht.unvollstaendig[k] = int((~beide & t.notna()).sum())
        da = (t.notna() & (rad[0].notna() | rad[1].notna())).to_numpy()  # leere Zeilen: fehlen
        w = np.where(beide, rad[0].fillna(0) + rad[1].fillna(0), -1)[da]
        i = len(stellen)
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=info["name"], abschnitt=info.get("abschnitt"),
            richtung=None, lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
            hinweise=list(info.get("hinweise") or [])))
        s_l.append(np.full(int(da.sum()), i, dtype=np.int64))
        t_l.append(t[da].dt.tz_localize(None).to_numpy().astype("datetime64[m]"))
        w_l.append(w.astype(np.int64))
    if not stellen:
        raise ValueError(f"{q['code']}: keine Dateien in {ordner} – erst `zaehlkarte dauer fetch`")
    bericht.unvollstaendig = Counter({k: n for k, n in bericht.unvollstaendig.items() if n})
    bericht.stellen = len(stellen)
    s_, h_, w_, bericht.doppelt_verschieden = utc_stunden(
        np.concatenate(s_l), np.concatenate(t_l), np.concatenate(w_l), 4)
    von = (h_.min().astype(datetime) - timedelta(days=1)).date()
    bis = (h_.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    bericht.stunden = setze_utc(reihe, "rad", s_, h_, w_)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "15-Minuten-Werte (beide Rad-Richtungen) zu Stunden zusammengefasst")]
    return reihe
