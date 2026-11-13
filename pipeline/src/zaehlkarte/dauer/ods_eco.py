"""Eco-Counter-Zählstellen in Opendatasoft-Portalen: Würzburg (eine Zeile je Zählstelle und
Stunde) und Rhein-Kreis Neuss (eine Zeile je Kanal und Stunde) – Stundenwerte in UTC mit dem
Status von Eco-Counter.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12–14.py):
- Felder `id` (Zählstelle), `date` (Beginn der Stunde, UTC), `counts`, `status`, in Neuss dazu
  `channel_id`. Würzburg führt den Status als Liste (`["raw"]`, `["deleted"]`), Neuss als Text
  (`raw`, `modified`, leer).
- Gezählt ist nur `raw` (Rohwert) und `validated` (geprüft); jeder andere Status mit Wert (etwa
  `modified`) gilt als nicht gezählt, eine Zeile ohne Wert (`deleted`, leer) ebenso.
- Dieselbe Stunde zweimal: gleicher Wert zählt einmal, verschiedene gar nicht.
- Kanäle (`kanaele: true`): Je Zählstelle die Summe ihrer Kanäle; eine Stunde ist gezählt, wenn
  jeder Kanal der Stelle einen Wert hat. Die Kanäle in Neuss sind Zählschleifen (laut Quelle
  Induktionsschleifen im Boden – Fußverkehr zählen sie nicht).
- Rückstellung der Uhr: Am Rückstelltag fehlt in beiden Portalen die Stunde 0 Uhr UTC (die erste
  der beiden Stunden 2–3 Uhr Ortszeit); 2 Uhr ist dann nicht vollständig, der Tag auch nicht.
- Lage: Würzburg im eigenen Datensatz der Zählstellen (`standorte`), Neuss im Feld
  `coordinates` jeder Zeile (der Datensatz der Zählstellen ist leer) – Namen und Abschnitte dort
  aus der Datensatzbeschreibung (`stellen` in sources.yaml).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import ods
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc, utc_stunden

GEZAEHLT = {"raw", "validated"}
DATEI = "daten.csv"


@dataclass
class Bericht:
    zeilen_gesamt: int = 0
    status: Counter = field(default_factory=Counter)
    ohne_wert: int = 0
    doppelt_verschieden: int = 0
    kanaele: int = 0
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{self.zeilen_gesamt} Zeilen; Status: "
             + ", ".join(f"{k or 'leer'} {n}" for k, n in self.status.most_common())
             + f"; ohne Wert {self.ohne_wert}; doppelt mit verschiedenen Werten "
             f"{self.doppelt_verschieden} (nicht gezählt)",
             f"{self.stellen} Zählstellen"
             + (f" mit {self.kanaele} Kanälen" if self.kanaele else "")
             + f"; Stunden in der Karte: rad {self.stunden}"]
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def status_text(s: str) -> str:
    """`["raw"]` -> `raw`; mehrere Einträge mit Komma (`raw,modified`)."""
    teile = [x.strip().strip("\"'") for x in s.strip().strip("[]").split(",")]
    return ",".join(x for x in teile if x)


def felder(q: dict) -> str:
    return "id,date,counts,status" + (",channel_id" if q.get("kanaele") else "")


def hole(q: dict, pfade: Pfade) -> list[str]:
    ordner = pfade.roh / q["code"]
    log = [f"{q['code']}: " + ods.hole_export(q["basis"], q["datensatz"], felder(q), ordner, DATEI)]
    # Lage: eigener Datensatz der Zählstellen oder je Stelle die erste Zeile der Daten
    if q.get("standorte"):
        zeilen = ods.datensaetze(q["basis"], q["standorte"], select="id,name,location")
        lage = {str(z["id"]): {"name": z.get("name"), "lon": (z.get("location") or {}).get("lon"),
                               "lat": (z.get("location") or {}).get("lat")} for z in zeilen}
    else:
        lage = {}
        for k in q.get("stellen") or {}:
            z = ods.datensaetze(q["basis"], q["datensatz"], select="id,counter_name,coordinates",
                                where=f'id="{k}"', limit="1")
            if z:
                c = z[0].get("coordinates") or {}
                lage[str(k)] = {"name": z[0].get("counter_name"), "lon": c.get("lon"),
                                "lat": c.get("lat")}
    (ordner / "standorte.json").write_text(json.dumps(lage, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8")
    log.append(f"{q['code']}: Lage von {len(lage)} Zählstellen")
    return log


def _stelle(q: dict, k: str, info: dict) -> Dauerstelle:
    konf = (q.get("stellen") or {}).get(k) or {}
    name = konf.get("name") or (info.get("name") or "").strip() or f"Zählstelle {k}"
    richtung = konf.get("richtung")
    if not konf.get("name") and " Richtung " in name:  # „Greinberg Richtung Innenstadt“
        name, rest = name.split(" Richtung ", 1)
        richtung = f"Richtung {rest}"
    return Dauerstelle(quelle=q["code"], kennung=k, name=name, abschnitt=konf.get("abschnitt"),
                       richtung=richtung, lon=round(float(info["lon"]), 6),
                       lat=round(float(info["lat"]), 6), land=q["land"],
                       hinweise=list(konf.get("hinweise") or []))


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import pandas as pd

    ordner = pfade.roh / q["code"]
    if not (ordner / DATEI).exists():
        raise ValueError(f"{q['code']}: kein Export in {ordner} – erst `zaehlkarte dauer fetch`")
    lage = json.loads((ordner / "standorte.json").read_text(encoding="utf-8"))
    df = pd.read_csv(ordner / DATEI, sep=";", dtype=str, keep_default_na=False)
    bericht.zeilen_gesamt = len(df)
    st = df["status"].map(status_text)
    bericht.status = Counter(st.tolist())
    wert = pd.to_numeric(df["counts"], errors="coerce")
    da = wert.notna()
    bericht.ohne_wert = int((~da).sum())
    gezaehlt = da & st.isin(GEZAEHLT) & (wert >= 0)
    t = pd.to_datetime(df["date"], utc=True, errors="coerce")
    da &= t.notna()
    if q.get("kanaele"):  # eine Zeile ohne Kanal gehört zu keiner Summe
        da &= df["channel_id"].str.strip() != ""
    df, t = df[da], t[da]
    w = np.where(gezaehlt[da], wert[da], -1).astype(np.int64)
    kennung = df["id"].astype(str).to_numpy()
    kanal = df["channel_id"].astype(str).to_numpy() if q.get("kanaele") else kennung
    # Stellen: mit Daten und Lage
    stellen, idx = [], {}
    for k in sorted(set(kennung), key=lambda x: (len(x), x)):
        info = lage.get(k)
        if not info or info.get("lon") is None or info.get("lat") is None:
            bericht.ohne_lage.append(k)
            continue
        idx[k] = len(stellen)
        stellen.append(_stelle(q, k, info))
    if not stellen:
        raise ValueError(f"{q['code']}: keine Zählstelle mit Lage")
    bericht.stellen = len(stellen)
    mit = np.isin(kennung, list(idx))
    kennung, kanal, w = kennung[mit], kanal[mit], w[mit]
    utc = t[mit].dt.tz_localize(None).to_numpy().astype("datetime64[m]")
    # je Kanal die Stunden (Doppelte geprüft), dann je Stelle die Summe aller ihrer Kanäle
    kanaele, k_idx = np.unique(kanal, return_inverse=True)
    stelle_je_kanal = np.empty(len(kanaele), dtype=np.int64)
    stelle_je_kanal[k_idx] = [idx[k] for k in kennung]
    bericht.kanaele = len(kanaele) if q.get("kanaele") else 0
    k_, h_, w_, bericht.doppelt_verschieden = utc_stunden(k_idx, utc, w, 1)
    s_ = stelle_je_kanal[k_]
    n_kanaele = np.bincount(stelle_je_kanal, minlength=len(stellen))
    if not len(h_):
        raise ValueError(f"{q['code']}: keine gezählte Stunde")
    basis = h_.min()
    schluessel = s_ * (int((h_.max() - basis).astype(np.int64)) + 1) + (h_ - basis).astype(np.int64)
    _, erste, inv, n = np.unique(schluessel, return_index=True, return_inverse=True,
                                 return_counts=True)
    summe = np.bincount(inv, weights=w_).astype(np.int64)
    voll = n == n_kanaele[s_[erste]]
    s_, h_, summe = s_[erste][voll], h_[erste][voll], summe[voll]
    if not len(h_):
        raise ValueError(f"{q['code']}: keine Stunde, in der alle Kanäle gezählt sind")
    von = (h_.min().astype(datetime) - timedelta(days=1)).date()
    bis = (h_.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    bericht.stunden = setze_utc(reihe, "rad", s_, h_, summe)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle" + (" (Summe ihrer Kanäle)" if q.get("kanaele")
                                                        else "")
                        + "; nur Rohwerte und geprüfte Werte (Status „raw“, „validated“); UTC in "
                        "Ortszeit umgerechnet")]
    return reihe
