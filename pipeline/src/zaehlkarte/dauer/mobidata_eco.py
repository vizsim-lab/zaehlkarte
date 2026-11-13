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
- Kanäle: `channels_all` enthält nur die Rad-Kanäle – Pkw- und Personen-Kanäle derselben Geräte
  (Ludwigsburg, Reutlingen, Böblingen) zählt MobiData nicht mit (Abgleich mit dem älteren Format
  je Kanal, Juni 2025, rad_erkunden9.py).
- `ohne` in sources.yaml: Zählstellen, die nicht in die Karte kommen – Name nennt Fuß- und
  Radverkehr, ein Gerät („Hardware …“) neben seinen eigenen Zählstellen, eine Stelle des Landes.
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
BLOCK = 64  # Zählstellen je Durchgang beim Setzen der Stunden


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


def kompakt(df) -> tuple[np.ndarray, ...]:
    """Zeilen eines Monats -> (Kennung, Tag in Ortszeit als Tage seit 1970, Stunde, UTC-Stunde,
    Wert mit -1 = nicht gezählt) als schmale Zahlenfelder (17 Byte je Zeile)."""
    import pandas as pd

    ts = df["iso_timestamp"].str
    tag = ts.slice(0, 10).to_numpy().astype("datetime64[D]")
    if np.isnat(tag).any():
        raise ValueError("iso_timestamp ohne Datum")
    stunde = ts.slice(11, 13).astype(np.int64).to_numpy()
    versatz = ts.slice(19, 22).astype(np.int64).to_numpy()  # „+02:00“ -> 2
    tage = tag.view(np.int64)
    utc = tage * 24 + stunde - versatz
    roh = df["channels_all"].str.strip()
    leer = roh.isin(["", "na", "NA", "nan"]).to_numpy()
    zahl = pd.to_numeric(roh.where(~leer, "-1"), errors="raise").to_numpy()
    werte = np.where(leer, LEER, zahl).astype(np.int32)
    sid = pd.to_numeric(df["counter_site_id"], errors="raise").to_numpy().astype(np.int32)
    return (sid, tage.astype(np.int32), stunde.astype(np.int8), utc.astype(np.int32), werte)


def _block(i, tag, stunde, utc, werte, bericht: Bericht):
    """Zeilen eines Blocks von Zählstellen: gleiche Stunde (UTC) mehrfach mit gleichem Wert ->
    einmal; mit verschiedenen Werten -> einmal als nicht gezählt. -> Felder ohne Doppelte und
    Maske „ohne Wert in der Quelle“."""
    o = np.lexsort((werte, utc, i))
    i, tag, stunde, utc, werte = i[o], tag[o], stunde[o], utc[o], werte[o]
    folge = np.r_[False, (i[1:] == i[:-1]) & (utc[1:] == utc[:-1])]
    gleich = folge & np.r_[False, werte[1:] == werte[:-1]]
    bericht.doppelt_gleich += int(gleich.sum())
    i, tag, stunde, utc, werte = (x[~gleich] for x in (i, tag, stunde, utc, werte))
    folge = np.r_[False, (i[1:] == i[:-1]) & (utc[1:] == utc[:-1])]
    widerspruch = folge | np.r_[folge[1:], False]
    bericht.doppelt_anders += int(widerspruch.sum())
    na = werte == LEER
    werte = np.where(widerspruch, LEER, werte).astype(np.int32)
    return tuple(x[~folge] for x in (i, tag, stunde, werte, na))


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    """Alle Monate als schmale Felder sammeln, dann je Block von Zählstellen Doppelte klären und
    die Stunden setzen – so bleiben auch 66 Mio. Zeilen (2013–2026) bei rund 1,5 GB Speicher."""
    ordner = pfade.roh / q["code"]
    dateien = sorted(ordner.glob("stunden_*.csv.gz"))
    if not dateien:
        raise ValueError(f"{q['code']}: keine Monatsdateien in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    abruf = json.loads((ordner / "abruf.json").read_text(encoding="utf-8"))
    abgerufen = datetime.fromisoformat(abruf["abgerufen"].replace("Z", "+00:00"))
    frisch = int(q.get("frisch_tage", 3))
    grenze = (abgerufen - timedelta(days=frisch)).date()
    grenze_tag = (grenze - date(1970, 1, 1)).days
    ohne = {int(k): v for k, v in (q.get("ohne") or {}).items()}
    felder: list[list[np.ndarray]] = [[] for _ in range(5)]
    meta = {}
    for p in dateien:
        df = lies_monat(p)
        bericht.monate += 1
        bericht.anzahl += len(df)
        for _, z in df.drop_duplicates("counter_site_id", keep="last").iterrows():
            meta[int(z["counter_site_id"])] = z  # die jüngste Angabe je Zählstelle gilt
        for liste, x in zip(felder, kompakt(df), strict=True):
            liste.append(x)
        del df
    gesammelt = []
    for liste in felder:  # Feld für Feld, damit nie alles doppelt im Speicher liegt
        gesammelt.append(np.concatenate(liste))
        liste.clear()
    sid, tage, stunde, utc, werte = gesammelt
    del gesammelt
    ids = np.array(sorted(meta), dtype=np.int64)
    idx = np.searchsorted(ids, sid).astype(np.int32)
    del sid
    ist_ohne = np.isin(ids, list(ohne))
    for k in ids[ist_ohne].tolist():
        bericht.ohne.append(f"{meta[k]['counter_site']} ({k}): {ohne[k]}")
    neu_index = (np.cumsum(~ist_ohne) - 1).astype(np.int32)
    stellen = []
    for k in ids[~ist_ohne].tolist():
        z = meta[k]
        bericht.je_kommune[z["domain_name"]] += 1
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=str(k), name=" ".join(z["counter_site"].split()),
            abschnitt=z["domain_name"].strip() or None, richtung=None,
            lon=round(float(z["longitude"]), 6), lat=round(float(z["latitude"]), 6),
            land=q["land"]))
    bericht.stellen = len(stellen)
    von = np.datetime64(int(tage.min()), "D").astype(date)
    bis = min(np.datetime64(int(tage.max()), "D").astype(date), grenze - timedelta(days=1))
    if not stellen or bis < von:
        raise ValueError(f"{q['code']}: keine Stunden vor {grenze}")
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    for a in range(0, len(ids), BLOCK):
        zeilen = np.flatnonzero((idx >= a) & (idx < a + BLOCK))
        i, tg, st, w, na = _block(idx[zeilen], tage[zeilen], stunde[zeilen], utc[zeilen],
                                  werte[zeilen], bericht)
        del zeilen
        behalten = ~ist_ohne[i]
        bericht.na += int((na & behalten).sum())
        alt = tg < grenze_tag
        bericht.frisch += int((behalten & ~alt).sum())
        m = behalten & alt
        gesetzt, sommer = setze_lokal(reihe, "rad", neu_index[i[m]], tg[m].astype("datetime64[D]"),
                                      st[m], w[m], anzahl=1, rueck="zusammen")
        bericht.stunden += gesetzt
        bericht.sommerzeit += sommer
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle (beide Richtungen zusammen), wie MobiData "
                        f"BW sie bündelt; die jüngsten {frisch} Tage noch nicht übernommen")]
    return reihe
