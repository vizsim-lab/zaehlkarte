"""Rostock: Radmonitore der Hanse- und Universitätsstadt (Eco-Counter) – 15-Minuten-Werte je
Zählstelle seit 2012 als eine CSV im Open-Data-Portal OpenData.HRO, täglich aktualisiert; die
Standorte als GeoJSON.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12–14.py):
- `radmonitore_daten.csv`: `standort_id` (Kennung von Eco-Counter), `zeitpunkt` (Beginn der
  Viertelstunde in Ortszeit mit Versatz, „2013/07/15 22:15:00+02“), `summe` (beide Richtungen).
  Rund 5,4 Millionen Zeilen, ohne Status – ob Werte rekonstruiert sind, sagt die Quelle nicht.
- Eine Stunde ist gezählt, wenn alle vier Viertelstunden einen Wert haben (über den Versatz in UTC –
  die Zeitumstellung ist damit eindeutig). Dieselbe Viertelstunde zweimal: gleicher Wert zählt
  einmal, verschiedene gar nicht.
- `radmonitore_standorte.json`: `id`, `bezeichnung`, `beschreibung`, Lage als Punkt (WGS84).
- Zählstellen, die nicht in die Karte kommen, stehen mit Grund unter `ohne` in sources.yaml.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc, utc_stunden


@dataclass
class Bericht:
    viertelstunden: int = 0
    nicht: Counter = field(default_factory=Counter)
    doppelt_verschieden: int = 0
    stellen: int = 0
    ohne: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{self.viertelstunden} Viertelstunden; verworfen: "
             + (", ".join(f"{k} {n}" for k, n in self.nicht.most_common()) or "keine")
             + f"; doppelt mit verschiedenen Werten: {self.doppelt_verschieden}; "
             f"{self.stellen} Zählstellen; Stunden in der Karte: rad {self.stunden}"]
        if self.ohne:
            z.append(f"nicht in der Karte (sources.yaml `ohne`): {', '.join(self.ohne)}")
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    from zaehlkarte.fetch import lade, sha256

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    daten = lade(q["daten"], ordner / "daten.csv")
    lade(q["standorte"], ordner / "standorte.json")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "daten": q["daten"], "bytes": daten.stat().st_size, "sha256": sha256(daten),
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Daten ({daten.stat().st_size / 1e6:.0f} MB) und Standorte geholt"]


def lies_standorte(text: str) -> dict[str, tuple[str, str | None, float, float]]:
    """GeoJSON -> Kennung: (Bezeichnung, Beschreibung, lon, lat)."""
    out = {}
    for f in json.loads(text).get("features", []):
        p, g = f.get("properties") or {}, f.get("geometry") or {}
        if g.get("type") == "Point" and p.get("id"):
            lon, lat = g["coordinates"][:2]
            out[str(p["id"])] = ((p.get("bezeichnung") or "").strip(), p.get("beschreibung"),
                                 float(lon), float(lat))
    return out


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import pandas as pd

    ordner = pfade.roh / q["code"]
    if not (ordner / "daten.csv").exists():
        raise ValueError(f"{q['code']}: keine Daten in {ordner} – erst `zaehlkarte dauer fetch`")
    lage = lies_standorte((ordner / "standorte.json").read_text(encoding="utf-8"))
    df = pd.read_csv(ordner / "daten.csv", dtype=str, keep_default_na=False)
    bericht.viertelstunden = len(df)
    zeit = df["zeitpunkt"].str.strip().str.replace("/", "-", n=2, regex=False)
    t = pd.to_datetime(zeit + "00", format="%Y-%m-%d %H:%M:%S%z", utc=True, errors="coerce")
    w = pd.to_numeric(df["summe"], errors="coerce")
    bericht.nicht["Zeit unlesbar"] = int(t.isna().sum())
    bericht.nicht["ohne Wert"] = int((w.isna() & t.notna()).sum())
    bericht.nicht["nicht auf der Viertelstunde"] = int((t.notna() & (t.dt.minute % 15 != 0)).sum())
    bericht.nicht = Counter({k: n for k, n in bericht.nicht.items() if n})
    da = (t.notna() & w.notna() & (t.dt.minute % 15 == 0)).to_numpy()
    kennung = df["standort_id"].str.strip().str.strip('"').to_numpy()[da]
    utc = t[da].dt.tz_localize(None).to_numpy().astype("datetime64[m]")
    werte = np.where(w[da] >= 0, w[da], -1).astype(np.int64)
    ohne = {str(k) for k in (q.get("ohne") or {})}
    stellen, idx = [], {}
    for k in sorted(set(kennung), key=lambda x: (len(x), x)):
        if k in ohne:
            bericht.ohne.append(k)
            continue
        if k not in lage:
            bericht.ohne_lage.append(k)
            continue
        name, beschreibung, lon, lat = lage[k]
        idx[k] = len(stellen)
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=name or f"Zählstelle {k}", abschnitt=None,
            richtung=None, lon=round(lon, 6), lat=round(lat, 6), land=q["land"]))
    if not stellen:
        raise ValueError(f"{q['code']}: keine Zählstelle mit Lage")
    bericht.stellen = len(stellen)
    mit = np.isin(kennung, list(idx))
    s = np.array([idx[k] for k in kennung[mit]], dtype=np.int64)
    s_, h_, w_, bericht.doppelt_verschieden = utc_stunden(s, utc[mit], werte[mit], 4)
    von = (h_.min().astype(datetime) - timedelta(days=1)).date()
    bis = (h_.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    bericht.stunden = setze_utc(reihe, "rad", s_, h_, w_)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "15-Minuten-Werte je Zählstelle zu Stunden zusammengefasst")]
    return reihe
