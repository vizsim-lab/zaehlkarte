"""Ettlingen: automatische Zählstellen der Stadt im Datastore des Open-Data-Portals re@di
(TechnologieRegion Karlsruhe) – Stundenwerte je Fahrtrichtung und Fahrzeugklasse.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer`, tools/dauer_ettlingen.py):
- Der ganze Datastore kommt als CSV über `/datastore/dump/<Ressource>` (rund 40 MB).
- Eine Zeile je Strom, Stunde und Fahrzeugklasse: `timestamp` (Beginn der Stunde, UTC, ohne
  Zonenangabe), `series_name` (Klasse: PKW, Leichtes Nutzfahrzeug, LKW, LKW+Anhänger, Motorrad),
  `y` (Anzahl). Klassen ohne Fahrzeug fehlen in der Stunde; eine Stunde ganz ohne Zeile gilt als
  nicht gezählt (auch tagsüber fehlen Stunden – Ausfälle, keine leeren Stunden).
- Übernommen werden nur die Ströme der Plattform UrbanPulse (`source` = „UrbanPulse“, seit
  20.08.2026): je Fahrtrichtung ein Strom (`sid`), dazu `sensor_id`, `lane_index`, `direction`
  und die Lage des Sensors (`latitude`, `longitude` – alle Richtungen am selben Punkt).
- Nicht übernommen (ohne `source`): die älteren Kennungen 46–54 (Mai 2025 bis August 2026) –
  laufende Tageszähler ohne Richtung und Lage, deren Zeitstempel sich nicht sicher einer Stunde
  zuordnen lassen –, Testimporte vom 05.08.2026 (Zeitstempel minutengenau) und Übergangszeilen
  vom 20.08.2026 (Bezeichnung „Straße | …“).
- Gruppen aus `klassen` in sources.yaml (Gruppe -> Klassen der Quelle, deren Summe sie ist; eine
  Klasse darf in mehreren Gruppen stehen, Lkw etwa bei Kfz und bei Lkw); andere Klassen zählen
  nicht mit und stehen im Bericht.
- Namen: die Quelle schreibt sie uneinheitlich („Strasse“, „Pforzheimer-Str-14“) – `stellen` in
  sources.yaml nennt je Sensor Straße und Abschnitt; ohne Eintrag gilt die Bezeichnung der Quelle.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc

PLATTFORM = "UrbanPulse"
ROH = "datastore.csv.gz"


@dataclass
class Bericht:
    zeilen_gesamt: int = 0
    zeilen_strom: int = 0  # Zeilen der UrbanPulse-Ströme
    nicht_volle_stunde: int = 0
    stroeme: int = 0
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    stunden: Counter = field(default_factory=Counter)  # je Gruppe in der Karte
    frisch: int = 0
    andere_klassen: Counter = field(default_factory=Counter)

    def zeilen(self) -> list[str]:
        z = [f"{self.zeilen_gesamt} Zeilen, davon {self.zeilen_strom} aus {PLATTFORM}-Strömen "
             f"({self.nicht_volle_stunde} nicht zur vollen Stunde, verworfen); {self.stroeme} "
             f"Ströme, {self.stellen} Zählstellen",
             "Stunden in der Karte: " + ", ".join(f"{g} {n}" for g, n in self.stunden.items())
             + f"; noch nicht übernommen (jünger als frisch_tage): {self.frisch}"]
        if self.andere_klassen:
            z.append("Klassen ohne Gruppe (nicht mitgezählt): "
                     + ", ".join(f"{k} ({n})" for k, n in self.andere_klassen.most_common()))
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage[:10])}")
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Den ganzen Datastore als CSV holen (unverändert, gepackt) und den Abrufzeitpunkt merken."""
    from zaehlkarte.fetch import lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now(UTC).replace(microsecond=0)
    csv_pfad = lade(q["dump"], ordner / "datastore.csv")
    roh = csv_pfad.read_bytes()
    with gzip.GzipFile(ordner / ROH, "wb", mtime=0) as f:
        f.write(roh)
    csv_pfad.unlink()
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "url": q["dump"],
        "bytes": len(roh), "sha256": hashlib.sha256(roh).hexdigest(),
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Datastore geholt ({len(roh) / 1e6:.1f} MB)"]


def _richtung(text: str) -> str | None:
    """„Rastatter Strasse - Richtung Bruchhausen“ -> „Richtung Bruchhausen“ (die Straße steht
    schon im Namen); „Rcihtung“ ist ein Tippfehler der Quelle."""
    t = " ".join(text.split())
    if " - " in t:
        t = t.split(" - ", 1)[1]
    return t.replace("Rcihtung", "Richtung") or None


def lies_csv(pfad: Path):
    import pandas as pd

    with gzip.open(pfad, "rt", encoding="utf-8-sig") as f:
        return pd.read_csv(f, dtype=str, keep_default_na=False)


def _stellen(q: dict, df, bericht: Bericht) -> tuple[list[Dauerstelle], dict[str, int]]:
    """Eine Zählstelle je Strom (Fahrtrichtung). -> (Stellen, sid -> Index)."""
    namen = {str(k): v for k, v in (q.get("stellen") or {}).items()}
    erste = df.drop_duplicates("sid").set_index("sid")
    lage = (df[(df["latitude"] != "") & (df["longitude"] != "")]
            .drop_duplicates("sid").set_index("sid")[["latitude", "longitude"]])
    paare = Counter(zip(erste["sensor_id"], erste["lane_index"], strict=True))
    out, idx = [], {}
    for sid, z in erste.sort_values(["sensor_id", "lane_index"]).iterrows():
        if sid not in lage.index:
            bericht.ohne_lage.append(sid)
            continue
        # Kennung: Sensor und Fahrstreifen („395842-1“), bei Doppelung der Strom selbst
        kennung = (f"{z['sensor_id']}-{z['lane_index']}"
                   if z["sensor_id"] and paare[(z["sensor_id"], z["lane_index"])] == 1 else sid)
        n = namen.get(z["sensor_id"]) or {}
        idx[sid] = len(out)
        out.append(Dauerstelle(
            quelle=q["code"], kennung=kennung, name=n.get("name") or z["label"].strip(),
            abschnitt=n.get("abschnitt"), richtung=_richtung(z["direction"]),
            lon=round(float(lage.loc[sid, "longitude"]), 6),
            lat=round(float(lage.loc[sid, "latitude"]), 6), land=q["land"],
            fahrstreifen=[], hinweise=[]))
    bericht.stellen = len(out)
    return out, idx


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import pandas as pd

    ordner = pfade.roh / q["code"]
    if not (ordner / ROH).exists():
        raise ValueError(f"{q['code']}: kein Datastore in {ordner} – erst `zaehlkarte dauer fetch`")
    abruf = json.loads((ordner / "abruf.json").read_text(encoding="utf-8"))
    df = lies_csv(ordner / ROH)
    bericht.zeilen_gesamt = len(df)
    df = df[df["source"] == PLATTFORM].copy()
    bericht.zeilen_strom = len(df)
    ts = pd.to_datetime(df["timestamp"], utc=True, format="mixed")
    voll = (ts.dt.minute == 0) & (ts.dt.second == 0)
    bericht.nicht_volle_stunde = int((~voll).sum())
    df, ts = df[voll], ts[voll]
    df["t"] = ts.dt.tz_localize(None).to_numpy().astype("datetime64[h]")
    df["y"] = pd.to_numeric(df["y"], errors="raise").astype(np.int64)
    bericht.stroeme = int(df["sid"].nunique())
    stellen, idx = _stellen(q, df, bericht)
    # eine Klasse kann in mehreren Gruppen stehen (Lkw zählt bei Kfz und bei Lkw mit)
    bekannt = {k for ks in q["klassen"].values() for k in ks}
    bericht.andere_klassen.update(df.loc[~df["series_name"].isin(bekannt), "series_name"])

    abgerufen = datetime.fromisoformat(abruf["abgerufen"].replace("Z", "+00:00"))
    grenze = np.datetime64((abgerufen - timedelta(days=int(q.get("frisch_tage", 2))))
                           .replace(tzinfo=None, minute=0, second=0), "h")
    df = df[df["sid"].isin(idx)]
    if df.empty:
        raise ValueError(f"{q['code']}: keine Stunden aus {PLATTFORM}-Strömen")
    # Eine Stunde ist gezählt, wenn der Strom für sie eine Zeile liefert (gleich welcher Klasse);
    # fehlende Klassen sind 0. Je Gruppe die Summe ihrer Klassen.
    stunden = df.groupby(["sid", "t"], sort=False).size().index.to_frame(index=False)
    je = {}
    for gruppe, klassen in q["klassen"].items():
        summe = df[df["series_name"].isin(klassen)].groupby(["sid", "t"])["y"].sum()
        w = stunden.join(summe, on=["sid", "t"])["y"].fillna(0).astype(np.int64).to_numpy()
        je[gruppe] = w
    s_ = stunden["sid"].map(idx).to_numpy(dtype=np.int64)
    t_ = stunden["t"].to_numpy().astype("datetime64[h]")
    alt = t_ < grenze
    if not alt.any():
        raise ValueError(f"{q['code']}: keine Stunden vor {grenze}")
    von = (t_[alt].min().astype(datetime) - timedelta(days=1)).date()
    bis = (t_[alt].max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, tuple(q["klassen"]))
    bericht.frisch = int((~alt).sum())
    for gruppe, w_ in je.items():
        bericht.stunden[gruppe] = setze_utc(reihe, gruppe, s_[alt], t_[alt], w_[alt])
    kuerze(reihe)
    namen = ", ".join(f"{g}: {' + '.join(ks)}" for g, ks in q["klassen"].items())
    frisch = int(q.get("frisch_tage", 2))
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        f"Stundenwerte je Fahrtrichtung, Summe der Fahrzeugklassen ({namen}); "
                        f"UTC in Ortszeit umgerechnet; die jüngsten {frisch} Tage noch nicht "
                        "übernommen")]
    return reihe
