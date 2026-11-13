"""Baden-Württemberg: Rad-Zählstellen der Städte und Landkreise (Eco-Counter), gebündelt von
MobiData BW – Stundenwerte je Zählstelle in Monatsdateien seit Januar 2013.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden2.py bis 6):
- Eine CSV je Monat (`fahrradzaehler_stundenwerten_JJJJMM.csv.gz`), eine Zeile je Zählstelle und
  Stunde: `iso_timestamp` (Beginn der Stunde in Ortszeit mit Versatz, etwa
  `2026-10-01T08:00:00+02:00`), `channels_in`, `channels_out`, `channels_unknown`, `channels_all`
  (Summe der drei; `na` = nicht gezählt), dazu Kommune bzw. Landkreis (`domain_name`), Name und Lage
  der Zählstelle.
- In der Karte: `channels_all` je Zählstelle (beide Richtungen zusammen). Fehlt eine Stunde oder
  steht dort `na`, ist sie nicht gezählt.
- Rückstellung der Uhr: Fast alle Stellen haben am Rückstelltag nur eine Zeile um 2 Uhr
  (`02:00+01:00`), deren Wert beide Stunden enthält – im Mittel 1,3- bis 1,7-mal so viel wie 1 und
  3 Uhr, an anderen Sonntagen 0,8- bis 0,9-mal (2023–2026). Einige Stellen liefern beide Stunden
  getrennt. Beides ergibt die Summe (`doppelt`).
- Rekonstruierte Werte: Eco-Counter füllt Ausfälle teils rechnerisch auf. Das Bündel kennzeichnet
  sie nicht – im eingefrorenen älteren Format (Juni 2025) mit Status je Kanal stecken Stunden mit
  Status 4 (rekonstruiert) unverändert in `channels_all`. Die Zählkarte kann sie nicht erkennen;
  der Hinweis steht an der Quelle (Entscheidung des Nutzers, 13.11.2026).
- `ohne` in sources.yaml: Zählstellen, die nicht in die Karte kommen (Fuß und Rad zusammen gezählt).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

SPALTEN = ["domain_name", "counter_site", "counter_site_id", "longitude", "latitude",
           "iso_timestamp", "channels_all"]


@dataclass
class Bericht:
    monate: int = 0
    anzahl: int = 0  # Zeilen aller Monatsdateien
    doppelt_gleich: int = 0  # gleiche Zeile mehrfach (verworfen)
    doppelt_anders: int = 0  # gleiche Stunde mit verschiedenen Werten (nicht gezählt)
    na: int = 0
    stellen: int = 0
    ohne: list[str] = field(default_factory=list)
    stunden: int = 0
    frisch: int = 0
    sommerzeit: int = 0
    je_kommune: Counter = field(default_factory=Counter)

    def zeilen(self) -> list[str]:
        return [f"{self.monate} Monatsdateien, {self.anzahl} Zeilen ({self.na} ohne Wert, "
                f"{self.doppelt_gleich} doppelt verworfen, {self.doppelt_anders} widersprüchlich = "
                f"nicht gezählt); {self.stellen} Zählstellen",
                "je Kommune/Kreis: "
                + ", ".join(f"{k} {n}" for k, n in self.je_kommune.most_common()),
                f"Stunden in der Karte: rad {self.stunden}; noch nicht übernommen (jünger als "
                f"frisch_tage): {self.frisch}; Zeilen um 2 Uhr am Tag der Sommerzeit verworfen: "
                f"{self.sommerzeit}",
                *([f"nicht in der Karte: {'; '.join(self.ohne)}"] if self.ohne else [])]


def _monate(ab: str, bis: date) -> list[str]:
    j, m = int(ab[:4]), int(ab[5:7])
    out = []
    while (j, m) <= (bis.year, bis.month):
        out.append(f"{j}{m:02d}")
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    return out


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Monatsdateien holen (unverändert): fehlende immer, die jüngsten `nachladen_monate` neu."""
    import requests

    from zaehlkarte.fetch import lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now(UTC).replace(microsecond=0)
    monate = _monate(q["ab"], jetzt.date())
    neu = set(monate[-int(q.get("nachladen_monate", 2)):])
    geladen, fehlt = [], []
    for m in monate:
        ziel = ordner / f"stunden_{m}.csv.gz"
        if ziel.exists() and m not in neu:
            continue
        try:
            lade(q["monate"].format(monat=m), ziel)
            geladen.append(m)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404 and m in neu:
                fehlt.append(m)  # der laufende Monat kann noch fehlen
                continue
            raise
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "geladen": geladen, "fehlt": fehlt,
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(geladen)} Monatsdateien geladen"
            + (f", noch nicht da: {', '.join(fehlt)}" if fehlt else "")]


def lies_monat(pfad: Path):
    import pandas as pd

    return pd.read_csv(pfad, dtype=str, keep_default_na=False, usecols=SPALTEN,
                       compression="gzip", encoding="utf-8-sig")


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    import pandas as pd

    ordner = pfade.roh / q["code"]
    dateien = sorted(ordner.glob("stunden_*.csv.gz"))
    if not dateien:
        raise ValueError(f"{q['code']}: keine Monatsdateien in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    abruf = json.loads((ordner / "abruf.json").read_text(encoding="utf-8"))
    abgerufen = datetime.fromisoformat(abruf["abgerufen"].replace("Z", "+00:00"))
    grenze = np.datetime64((abgerufen - timedelta(days=int(q.get("frisch_tage", 3)))).date(), "D")
    ohne = {str(k): v for k, v in (q.get("ohne") or {}).items()}
    teile, meta = [], {}
    for p in dateien:
        df = lies_monat(p)
        bericht.monate += 1
        bericht.anzahl += len(df)
        for _, z in df.drop_duplicates("counter_site_id", keep="last").iterrows():
            meta[z["counter_site_id"]] = z  # die jüngste Angabe je Zählstelle gilt
        teile.append(df[["counter_site_id", "iso_timestamp", "channels_all"]])
    df = pd.concat(teile, ignore_index=True)
    vorher = len(df)
    df = df.drop_duplicates()
    bericht.doppelt_gleich = vorher - len(df)
    bericht.doppelt_anders = int(
        df.duplicated(["counter_site_id", "iso_timestamp"], keep=False).sum())
    for sid in sorted(set(df["counter_site_id"]) & set(ohne)):
        bericht.ohne.append(f"{meta[sid]['counter_site']} ({sid}): {ohne[sid]}")
    df = df[~df["counter_site_id"].isin(ohne)]
    ids = sorted(set(df["counter_site_id"]), key=int)
    stellen = []
    for sid in ids:
        z = meta[sid]
        bericht.je_kommune[z["domain_name"]] += 1
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=sid, name=" ".join(z["counter_site"].split()),
            abschnitt=z["domain_name"].strip() or None, richtung=None,
            lon=round(float(z["longitude"]), 6), lat=round(float(z["latitude"]), 6),
            land=q["land"]))
    bericht.stellen = len(stellen)
    idx = {sid: i for i, sid in enumerate(ids)}
    ts = df["iso_timestamp"].str
    tag = ts.slice(0, 10).to_numpy().astype("datetime64[D]")
    stunde = ts.slice(11, 13).astype(int).to_numpy()
    roh = df["channels_all"].str.strip()
    leer = roh.isin(["", "na", "NA", "nan"])
    bericht.na = int(leer.sum())
    zahl = pd.to_numeric(roh.where(~leer, "-1"), errors="raise")
    werte = np.where(leer, LEER, zahl).astype(np.int64)
    alt = tag < grenze
    bericht.frisch = int((~alt).sum())
    s_ = df["counter_site_id"].map(idx).to_numpy(dtype=np.int64)[alt]
    tag, stunde, werte = tag[alt], stunde[alt], werte[alt]
    von, bis = tag.min().astype(date), tag.max().astype(date)
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    bericht.stunden, bericht.sommerzeit = setze_lokal(reihe, "rad", s_, tag, stunde, werte,
                                                      anzahl=1, rueck="zusammen")
    kuerze(reihe)
    frisch = int(q.get("frisch_tage", 3))
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle (beide Richtungen zusammen), wie MobiData "
                        f"BW sie bündelt; die jüngsten {frisch} Tage noch nicht übernommen")]
    return reihe
