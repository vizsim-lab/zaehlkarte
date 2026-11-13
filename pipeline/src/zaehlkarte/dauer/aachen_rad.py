"""Aachen: Radzählstellen der Stadt – Stundenwerte je Zählstelle und Richtung (UTC), eine CSV je
Jahr im Open-Data-Portal, täglich aktualisiert; die Standorte stehen in einem PDF.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden4.py):
- CSV: `Zeitstempel_von (UTC)`, `Zeitstempel_bis (UTC)`, dann je Kanal eine Spalte
  „<Kennung> | <Name> | <Richtung>“ (etwa „418432 | Alexianergraben | Radfahrer Richtung Norden“).
  Leere Zelle = nicht gezählt; fehlt eine Stunde in der Datei, gilt sie ebenso als nicht gezählt.
- In der Karte: je Zählstelle die Summe ihrer Kanäle; eine Stunde ist gezählt, wenn jeder Kanal
  einen Wert hat. An der Hohenstaufenallee zählen eigene Kanäle Radfahrende gegen die
  Fahrtrichtung („Falschfahrer“) – sie gehören zur Zählstelle.
- Standorte: PDF „Standorte Radzählstellen“ (Kennung, Name, „Breite, Länge“, Daten seit). Offenbare
  Tippfehler darin korrigiert `lage` in sources.yaml (mit Vermerk), statt die Rohdatei zu ändern.
- Mehrere Ressourcen für dasselbe Jahr: die jüngste gilt.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_utc

ZEILE_PDF = re.compile(
    r"^(\d{5,7})\s+(.+?)\s+(\d{1,2}\.\d+),\s*(\d{1,2}\.\d+)\s+(\d{4}-\d{2}-\d{2})\s*$")


@dataclass
class Bericht:
    dateien: list[str] = field(default_factory=list)
    stunden_datei: int = 0
    stellen: int = 0
    kanaele: int = 0
    leer: Counter = field(default_factory=Counter)  # je Zählstelle: Stunden mit leerem Kanal
    ohne_lage: list[str] = field(default_factory=list)
    lage_korrigiert: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"Dateien {', '.join(self.dateien)}: {self.stunden_datei} Stunden; {self.stellen} "
             f"Zählstellen mit {self.kanaele} Kanälen; Stunden in der Karte: rad {self.stunden}",
             "Stunden mit leerem Kanal (nicht gezählt): "
             + ", ".join(f"{k} {n}" for k, n in self.leer.most_common(8))]
        if self.lage_korrigiert:
            z.append(f"Lage aus sources.yaml statt PDF: {', '.join(self.lage_korrigiert)}")
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Alle Jahres-CSV und das PDF der Standorte über die CKAN-API des Portals holen."""
    import requests

    from zaehlkarte.fetch import UA, lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now(UTC).replace(microsecond=0)
    r = requests.get(q["api"], params={"id": q["paket"]}, headers=UA, timeout=120)
    r.raise_for_status()
    paket = r.json()["result"]
    jahre: dict[str, dict] = {}
    pdf = None
    for res in paket["resources"]:
        name = (res.get("name") or "") + " " + (res.get("url") or "")
        if m := re.search(r"(20\d{2})\.csv", name, re.I):
            alt = jahre.get(m.group(1))
            stand = res.get("last_modified") or res.get("created") or ""
            if not alt or stand > (alt.get("last_modified") or alt.get("created") or ""):
                jahre[m.group(1)] = res
        elif (res.get("format") or "").upper() == "PDF" and "standort" in name.lower():
            pdf = res
    if not jahre or pdf is None:
        raise ValueError(f"{q['code']}: Ressourcen nicht gefunden ({len(jahre)} Jahre, "
                         f"PDF {pdf is not None})")
    for j, res in sorted(jahre.items()):
        lade(res["url"], ordner / f"jahr_{j}.csv")
    lade(pdf["url"], ordner / "standorte.pdf")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"),
        "dateien": {j: res["url"] for j, res in sorted(jahre.items())}, "standorte": pdf["url"],
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(jahre)} Jahresdateien ({', '.join(sorted(jahre))}) und "
            "Standorte geholt"]


def standorte_aus_text(text: str) -> dict[str, tuple[str, float, float]]:
    """Text des PDF -> Kennung: (Name, Breite, Länge)."""
    out = {}
    for zeile in text.splitlines():
        if m := ZEILE_PDF.match(zeile.strip()):
            out[m.group(1)] = (m.group(2).strip(), float(m.group(3)), float(m.group(4)))
    return out


def lies_standorte(pfad: Path) -> dict[str, tuple[str, float, float]]:
    """PDF -> Kennung: (Name, Breite, Länge)."""
    import pdfplumber

    with pdfplumber.open(pfad) as pdf:
        return standorte_aus_text("\n".join(seite.extract_text() or "" for seite in pdf.pages))


def lies_jahr(pfad: Path) -> tuple[list[str], list[str], list[list[str]]]:
    """-> (Zeitstempel, Kanalspalten, Zeilen der Werte)."""
    text = pfad.read_text(encoding="utf-8-sig")
    zeilen = list(csv.reader(io.StringIO(text)))
    kopf = zeilen[0]
    return [z[0] for z in zeilen[1:] if z], kopf[2:], [z[2:] for z in zeilen[1:] if z]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    dateien = sorted(ordner.glob("jahr_*.csv"))
    if not dateien:
        raise ValueError(f"{q['code']}: keine Jahresdateien in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    lage = lies_standorte(ordner / "standorte.pdf")
    for k, v in (q.get("lage") or {}).items():
        name = lage.get(str(k), (v.get("name", ""), 0.0, 0.0))[0]
        lage[str(k)] = (name, float(v["lat"]), float(v["lon"]))
        bericht.lage_korrigiert.append(f"{k} ({v.get('grund', '')})")
    je_stelle: dict[str, dict] = {}  # Kennung -> {"name", "kanaele": set, "falsch": bool}
    stunden: dict[str, dict[str, list[int]]] = {}  # Kennung -> Zeitstempel -> [Summe, fehlt]
    for p in dateien:
        bericht.dateien.append(p.stem.removeprefix("jahr_"))
        zeiten, spalten, werte = lies_jahr(p)
        bericht.stunden_datei += len(zeiten)
        teile = [[x.strip() for x in s.split("|")] for s in spalten]
        gruppen: dict[str, list[int]] = {}
        for i, t in enumerate(teile):
            kennung = t[0]
            gruppen.setdefault(kennung, []).append(i)
            info = je_stelle.setdefault(kennung, {"name": t[1] if len(t) > 1 else kennung,
                                                  "kanaele": set(), "falsch": set()})
            info["kanaele"].add(t[2] if len(t) > 2 else spalten[i])
            if len(t) > 2 and "falschfahrer" in t[2].lower():
                info["falsch"].add(t[2])
        for ts, zeile in zip(zeiten, werte, strict=True):
            for kennung, idx in gruppen.items():
                vals = [zeile[i].strip() if i < len(zeile) else "" for i in idx]
                ziel = stunden.setdefault(kennung, {})
                if ts in ziel:  # dieselbe Stunde zweimal (etwa in zwei Dateien): nicht gezählt
                    ziel[ts] = [LEER, 1]
                    continue
                if any(v == "" for v in vals):
                    bericht.leer[kennung] += 1
                    ziel[ts] = [LEER, 1]
                else:
                    ziel[ts] = [sum(int(float(v)) for v in vals), 0]
    stellen, s_, t_, w_ = [], [], [], []
    for kennung in sorted(stunden, key=int):
        if kennung not in lage:
            bericht.ohne_lage.append(f"{kennung} ({je_stelle[kennung]['name']})")
            continue
        name, lat, lon = lage[kennung]
        info = je_stelle[kennung]
        hinweise = []
        if info["falsch"]:
            hinweise.append("Gezählt werden auch Radfahrende gegen die Fahrtrichtung "
                            "(eigener Kanal der Quelle, in der Summe enthalten).")
        i = len(stellen)
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=kennung, name=info["name"] or name, abschnitt=None,
            richtung=None, lon=round(lon, 6), lat=round(lat, 6), land=q["land"],
            hinweise=hinweise))
        bericht.kanaele += len(info["kanaele"])
        for ts, (w, fehlt) in stunden[kennung].items():
            s_.append(i)
            t_.append(ts[:19])
            w_.append(LEER if fehlt else w)
    if not stellen:
        raise ValueError(f"{q['code']}: keine Zählstelle mit Lage")
    bericht.stellen = len(stellen)
    t = np.array(t_, dtype="datetime64[h]")
    s, w = np.array(s_, dtype=np.int64), np.array(w_, dtype=np.int64)
    von = (t.min().astype(datetime) - timedelta(days=1)).date()
    bis = (t.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    gezaehlt = w >= 0
    bericht.stunden = setze_utc(reihe, "rad", s[gezaehlt], t[gezaehlt], w[gezaehlt])
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle (Summe ihrer Kanäle); UTC in Ortszeit "
                        "umgerechnet")]
    return reihe
