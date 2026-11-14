"""Bochum: Zählstellen Rad- und Fußverkehr der Stadt (Eco-Counter) – 15-Minuten-Werte je Richtung,
Rad und Fuß getrennt, täglich über die Eco-Counter-API abgerufen und im GitLab der Stadt
(openCode.de) abgelegt; eine Gesamtdatei je Zählstelle.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12–14.py):
- `data/<stelle>/bochum_ecocounter_<stelle>.csv`: `timestamp` (Ortszeit mit Versatz),
  `timestamp_utc`, `name`, `radfahrende_in`, `radfahrende_out`, an den Rad- und
  Fußverkehr-Zählstellen dazu `passanten_in`, `passanten_out` (eigene Kanäle – Gruppe Fuß).
- Eine Viertelstunde ist gezählt, wenn beide Richtungen der Verkehrsart einen Wert haben; eine
  Stunde, wenn alle vier Viertelstunden gezählt sind (in UTC – die Zeitumstellung ist damit
  eindeutig). An einzelnen Tagen stehen nur volle Stunden da (die übrigen Viertelstunden leer) –
  nicht gezählt.
- Laut README verarbeitet die Stadt die Kanäle der API selbst („pick best block“ je Richtung,
  Summe bei der alten Springorumtrasse); an der Springorumtrasse Süd vermutet sie für Rad fehlende
  Kanäle – die Stelle steht unter `ohne`.
- Lage und Namen: Tabelle im README des Repositories (`stellen` in der Quelldatei).
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

GRUPPEN = {"rad": ("radfahrende_in", "radfahrende_out"), "fuss": ("passanten_in", "passanten_out")}


@dataclass
class Bericht:
    viertelstunden: int = 0
    unvollstaendig: Counter = field(default_factory=Counter)  # je Stelle und Gruppe
    doppelt_verschieden: int = 0
    stellen: int = 0
    ohne: list[str] = field(default_factory=list)
    stunden: Counter = field(default_factory=Counter)  # je Gruppe
    mit_fuss: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        z = [f"{self.viertelstunden} Viertelstunden; ohne beide Richtungen (nicht gezählt): "
             + (", ".join(f"{k} {n}" for k, n in self.unvollstaendig.most_common()) or "keine")
             + f"; doppelt mit verschiedenen Werten: {self.doppelt_verschieden}; "
             f"{self.stellen} Zählstellen (mit Fuß: {', '.join(self.mit_fuss) or 'keine'}); "
             "Stunden in der Karte: "
             + ", ".join(f"{g} {self.stunden[g]}" for g in GRUPPEN)]
        if self.ohne:
            z.append(f"nicht in der Karte (`ohne` in der Quelldatei): {', '.join(self.ohne)}")
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
    stellen: list[Dauerstelle] = []
    je_gruppe: dict[str, tuple[list, list, list]] = {g: ([], [], []) for g in GRUPPEN}
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
        i = len(stellen)
        for g, spalten in GRUPPEN.items():
            if not all(c in df.columns for c in spalten):
                continue
            werte = [pd.to_numeric(df[c], errors="coerce") for c in spalten]
            beide = werte[0].notna() & werte[1].notna() & t.notna()
            da = (t.notna() & (werte[0].notna() | werte[1].notna())).to_numpy()  # leer: fehlt
            if not da.any():
                continue
            if g == "fuss":
                bericht.mit_fuss.append(k)
            bericht.unvollstaendig[f"{k} {g}"] = int((~beide & t.notna()).sum())
            w = np.where(beide, werte[0].fillna(0) + werte[1].fillna(0), -1)[da]
            s_l, t_l, w_l = je_gruppe[g]
            s_l.append(np.full(int(da.sum()), i, dtype=np.int64))
            t_l.append(t[da].dt.tz_localize(None).to_numpy().astype("datetime64[m]"))
            w_l.append(w.astype(np.int64))
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=info["name"], abschnitt=info.get("abschnitt"),
            richtung=None, lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
            hinweise=list(info.get("hinweise") or [])))
    if not stellen:
        raise ValueError(f"{q['code']}: keine Dateien in {ordner} – erst `zaehlkarte dauer fetch`")
    bericht.unvollstaendig = Counter({k: n for k, n in bericht.unvollstaendig.items() if n})
    bericht.stellen = len(stellen)
    gruppen = tuple(g for g in GRUPPEN if je_gruppe[g][0])
    stunden = {}
    for g in gruppen:
        s_l, t_l, w_l = je_gruppe[g]
        s_, h_, w_, doppelt = utc_stunden(np.concatenate(s_l), np.concatenate(t_l),
                                          np.concatenate(w_l), 4)
        bericht.doppelt_verschieden += doppelt
        stunden[g] = (s_, h_, w_)
    alle = np.concatenate([h for _, h, _ in stunden.values()])
    von = (alle.min().astype(datetime) - timedelta(days=1)).date()
    bis = (alle.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, gruppen)
    for g, (s_, h_, w_) in stunden.items():
        bericht.stunden[g] = setze_utc(reihe, g, s_, h_, w_)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "15-Minuten-Werte (je Verkehrsart beide Richtungen) zu Stunden "
                        "zusammengefasst")]
    return reihe
