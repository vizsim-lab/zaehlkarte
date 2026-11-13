"""Münster: Radverkehr-Zählstellen der Stadt (Eco-Counter) – 15-Minuten-Werte je Zählstelle und
Kanal mit Status, nächtlich aktualisiert im GitHub-Repository der Stadt (od-ms).

Aufbau (Stand November 2026, Klon von `od-ms/radverkehr-zaehlstellen`, Werkzeug-Branch
`werkzeug/dauer2`):
- Je Zählstelle ein Ordner (Kennung von Eco-Counter, etwa `100034978`) mit einer CSV je Monat:
  `Datetime` (Ortszeit ohne Versatz, Beginn der Viertelstunde), die Gesamtspalte
  `<Kennung> (<Name>)`, je Kanal eine Spalte und zu jeder Spalte `<Kennung>-status`.
- Status: `0` (Rohwert) und `validated` (geprüft) gelten als gezählt; `4` (in langen Läufen bis zu
  fünf Wochen – das Muster der Rekonstruktion bei Ausfällen) und `modified` (von Hand geändert) als
  nicht gezählt, ebenso jeder unbekannte Status (steht im Bericht).
- Die Gesamtspalte ist die Summe der Kanäle (3.705.717 von 3.705.803 Viertelstunden); weicht sie
  ab, ist die Viertelstunde nicht gezählt. Pkw-Kanäle (Bohlweg) sind leer.
- Rückstellung der Uhr: eine Viertelstundenfolge um 2 Uhr mit beiden Stunden (im Mittel 1,8-mal so
  viel wie 1 und 3 Uhr, an anderen Oktober-Sonntagen 0,9-mal) -> `doppelt`. Sommerzeit: 2 Uhr fehlt.
- Lage: GeoJSON der Stadt mit denselben Kennungen (`fahrradzaehl-standorte_0.geojson`).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import tarfile
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

GEZAEHLT = {"0", "validated"}
NICHT = {"4", "modified"}


@dataclass
class Bericht:
    dateien: int = 0
    viertelstunden: int = 0
    status: Counter = field(default_factory=Counter)
    unbekannt: Counter = field(default_factory=Counter)
    summe_abweichend: int = 0
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{self.dateien} Monatsdateien, {self.viertelstunden} Viertelstunden; Status: "
             + ", ".join(f"{k or 'leer'} {n}" for k, n in self.status.most_common())
             + f"; Gesamtspalte ≠ Summe der Kanäle: {self.summe_abweichend} (nicht gezählt)",
             f"{self.stellen} Zählstellen; Stunden in der Karte: rad {self.stunden}"]
        if self.unbekannt:
            z.append("unbekannter Status (nicht gezählt): "
                     + ", ".join(f"{k} ({n})" for k, n in self.unbekannt.most_common()))
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Das Repository als Archiv (Stand des Zweigs) und die Standorte holen; aus dem Archiv nur die
    Monatsdateien und site_min.json behalten."""
    import requests

    from zaehlkarte.fetch import UA, lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now(UTC).replace(microsecond=0)
    r = requests.get(q["archiv"], headers=UA, timeout=600)
    r.raise_for_status()
    daten = r.content
    ziel = ordner / "repo"
    if ziel.exists():
        import shutil

        shutil.rmtree(ziel)
    n = 0
    with tarfile.open(fileobj=io.BytesIO(daten), mode="r:gz") as tf:
        for m in tf.getmembers():
            teile = Path(m.name).parts[1:]  # erster Teil: <repo>-<zweig>/
            if not m.isfile() or not teile:
                continue
            if not ((len(teile) == 2 and teile[0].isdigit() and teile[1].endswith(".csv"))
                    or teile == ("site_min.json",)):
                continue
            pfad = ziel.joinpath(*teile)
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_bytes(tf.extractfile(m).read())
            n += 1
    lade(q["standorte"], ordner / "standorte.geojson")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "url": q["archiv"],
        "bytes": len(daten), "sha256": hashlib.sha256(daten).hexdigest(), "dateien": n,
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Archiv geholt ({len(daten) / 1e6:.1f} MB, {n} Dateien)"]


def _lage(pfad: Path) -> dict[str, tuple[float, float, str]]:
    g = json.loads(pfad.read_text(encoding="utf-8"))
    out = {}
    for f in g.get("features", []):
        lon, lat = f["geometry"]["coordinates"][:2]
        name = f["properties"].get("name") or ""
        out[str(f["properties"]["id"])] = (float(lon), float(lat), name)
    return out


def lies_stelle(ordner: Path, bericht: Bericht) -> tuple[list[str], list[int]]:
    """-> (Zeitstempel „JJJJ-MM-TT HH:MM“, Werte mit -1 = nicht gezählt) aller Monatsdateien."""
    sid = ordner.name
    zeiten, werte = [], []
    for p in sorted(ordner.glob("*.csv")):
        bericht.dateien += 1
        with p.open(encoding="utf-8") as f:
            r = csv.reader(f)
            kopf = next(r)
            i_st = kopf.index(f"{sid}-status")
            kanaele = [i for i, k in enumerate(kopf) if i > 1 and not k.endswith("-status")]
            for z in r:
                if not z or not z[0]:
                    continue
                bericht.viertelstunden += 1
                st = z[i_st].strip()
                bericht.status[st] += 1
                w = LEER
                if z[1] != "" and st in GEZAEHLT:
                    gesamt = round(float(z[1]))
                    summe = sum(round(float(z[i])) for i in kanaele if z[i] != "")
                    if gesamt == summe:
                        w = gesamt
                    else:
                        bericht.summe_abweichend += 1
                elif st not in GEZAEHLT | NICHT and st != "":
                    bericht.unbekannt[st] += 1
                zeiten.append(z[0])
                werte.append(w)
    return zeiten, werte


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    repo = ordner / "repo"
    if not repo.exists():
        raise ValueError(f"{q['code']}: kein Archiv in {ordner} – erst `zaehlkarte dauer fetch`")
    lage = _lage(ordner / "standorte.geojson")
    namen = {}
    if (repo / "site_min.json").exists():
        for s in json.loads((repo / "site_min.json").read_text(encoding="utf-8")):
            namen[str(s["directory"])] = s["name"]
    stellen, s_, t_, h_, w_ = [], [], [], [], []
    ordner_stellen = sorted(p for p in repo.iterdir() if p.is_dir() and p.name.isdigit())
    for o in ordner_stellen:
        sid = o.name
        if sid not in lage:
            bericht.ohne_lage.append(sid)
            continue
        zeiten, werte = lies_stelle(o, bericht)
        if not zeiten:
            continue
        i = len(stellen)
        lon, lat, name = lage[sid]
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=sid, name=namen.get(sid) or name, abschnitt=None,
            richtung=None, lon=round(lon, 6), lat=round(lat, 6), land=q["land"]))
        z = np.array(zeiten)
        s_.append(np.full(len(z), i, dtype=np.int64))
        t_.append(np.array([x[:10] for x in zeiten], dtype="datetime64[D]"))
        h_.append(np.array([int(x[11:13]) for x in zeiten], dtype=np.int64))
        w_.append(np.array(werte, dtype=np.int64))
    if not stellen:
        raise ValueError(f"{q['code']}: keine Zählstelle mit Lage")
    bericht.stellen = len(stellen)
    s, t, h, w = (np.concatenate(x) for x in (s_, t_, h_, w_))
    reihe = Messreihe.leer(q["code"], t.min().astype(date), t.max().astype(date), stellen, ("rad",))
    bericht.stunden, _ = setze_lokal(reihe, "rad", s, t, h, w, anzahl=4, rueck="zusammen")
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "15-Minuten-Werte je Zählstelle (Summe der Kanäle) zu Stunden "
                        "zusammengefasst; nur Rohwerte und geprüfte Werte (Status 0 und "
                        "„validated“), rekonstruierte und geänderte nicht")]
    return reihe
