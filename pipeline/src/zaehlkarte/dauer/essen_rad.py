"""Essen: automatische Radverkehrszählungen der Stadt (Amt für Stadtplanung und Bauordnung) an der
Grugatrasse und der Huyssenallee – Stundenwerte je Richtung seit Juni 2018, eine CSV je Quartal
im Open-Data-Portal der Stadt (über Open.NRW).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12–14.py):
- Je Quartal eine CSV: erste Spalte Datum und Stunde in Ortszeit („01.04.2026 00:00“), dann vier
  Spalten – Grugatrasse Richtung Rüttenscheid (West) und Richtung Ruhr (Ost), Huyssenallee Richtung
  Rüttenscheid (Süd) und Richtung Stadtkern (Nord). Die Köpfe wechseln (Schreibweise, Trenner `;`
  oder Tab, 2026 heißt die zweite Spalte fälschlich „Huyssenallee Stadtkern_Nord“); die Reihenfolge
  bleibt – belegt durch die kumulierten Jahresdateien (Tagessumme je Stelle = Summe der Spalten
  1+2 bzw. 3+4). Leere Zelle = nicht gezählt.
- Lizenz je Ressource: die Quartale 2018–2020 „Andere geschlossene Lizenz“, ab 2021 dl-de/by-2-0 –
  übernommen nur Ressourcen mit `lizenz_ressource`.
- Zeitumstellung: Am Tag der Sommerzeit fehlt 2 Uhr; am Rückstelltag steht 2 Uhr nur einmal
  (`rueck` in sources.yaml).
- Lage: nur in der Datensatzbeschreibung, als Gauß-Krüger-Koordinaten (`stellen` in sources.yaml,
  umgerechnet).
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

QUARTAL = re.compile(r"(20\d{2})\s*Q([1-4])")
ZEIT = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{1,2}):00")


@dataclass
class Bericht:
    dateien: list[str] = field(default_factory=list)
    stunden_datei: int = 0
    leer: Counter = field(default_factory=Counter)  # je Stelle: Stunden mit leerer Richtung
    unlesbar: int = 0
    kopf_abweichend: list[str] = field(default_factory=list)
    stunden: int = 0
    sommerzeit: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{len(self.dateien)} Quartale ({self.dateien[0] if self.dateien else '–'} bis "
             f"{self.dateien[-1] if self.dateien else '–'}): {self.stunden_datei} Stunden, "
             f"{self.unlesbar} Zeilen unlesbar; Stunden mit leerer Richtung (nicht gezählt): "
             + ", ".join(f"{k} {n}" for k, n in self.leer.items())
             + f"; Stunden in der Karte: rad {self.stunden}; 2 Uhr am Tag der Sommerzeit "
             f"verworfen: {self.sommerzeit}"]
        if self.kopf_abweichend:
            z.append("Kopf weicht ab (Spalten nach Reihenfolge übernommen): "
                     + "; ".join(self.kopf_abweichend))
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Quartalsdateien mit offener Lizenz über die CKAN-API holen (nur neue oder geänderte)."""
    import requests

    from zaehlkarte.fetch import UA, lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    r = requests.get(q["api"], params={"id": q["paket"]}, headers=UA, timeout=120)
    r.raise_for_status()
    gewaehlt, geschlossen = {}, []
    for res in r.json()["result"]["resources"]:
        name = (res.get("name") or "").strip()
        m = QUARTAL.search(name)
        if not m or "umuliert" in name:
            continue
        if q["lizenz_ressource"] not in (res.get("license") or ""):
            geschlossen.append(f"{m[1]} Q{m[2]}")
            continue
        gewaehlt[f"quartal_{m[1]}_Q{m[2]}.csv"] = res["url"]
    if not gewaehlt:
        raise ValueError(f"{q['code']}: keine Quartalsdatei mit offener Lizenz gefunden")
    abruf = ordner / "abruf.json"
    vorher = (json.loads(abruf.read_text(encoding="utf-8")).get("dateien", {})
              if abruf.exists() else {})
    neu = []
    for name, url in sorted(gewaehlt.items()):
        if vorher.get(name) != url or not (ordner / name).exists():
            lade(url, ordner / name)
            neu.append(name)
    abruf.write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dateien": dict(sorted(gewaehlt.items())), "ohne_offene_lizenz": sorted(geschlossen),
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(gewaehlt)} Quartale mit offener Lizenz, {len(neu)} neu geladen; "
            f"nicht übernommen (geschlossene Lizenz): {', '.join(sorted(geschlossen)) or 'keine'}"]


def lies_quartal(text: str) -> tuple[list[str], list[tuple[date, int, list[str]]], int]:
    """-> (Kopf, [(Tag, Stunde, vier Werte als Text)], unlesbare Zeilen)."""
    erste = text.split("\n", 1)[0]
    trenner = "\t" if erste.count("\t") > erste.count(";") else ";"
    zeilen = list(csv.reader(io.StringIO(text), delimiter=trenner))
    kopf, out, weg = [k.strip() for k in zeilen[0]], [], 0
    for z in zeilen[1:]:
        if not z or not "".join(z).strip():
            continue
        m = ZEIT.match(z[0].strip())
        if not m or len(z) < 5:
            weg += 1
            continue
        out.append((date(int(m[3]), int(m[2]), int(m[1])), int(m[4]),
                    [x.strip() for x in z[1:5]]))
    return kopf, out, weg


def _kopf_passt(kopf: list[str], spalten: list[list[str]]) -> bool:
    """Jede Wertespalte nennt die Stelle, zu der sie laut Reihenfolge gehört."""
    return all(stelle in k.lower() for k, (stelle, _) in zip(kopf[1:5], spalten, strict=True))


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    dateien = sorted(ordner.glob("quartal_*.csv"))
    if not dateien:
        raise ValueError(f"{q['code']}: keine Quartalsdateien in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    spalten = q["spalten"]  # [[Stelle, Richtung], …] in der Reihenfolge der Datei
    namen = list(dict.fromkeys(s for s, _ in spalten))
    stellen = []
    for k in namen:
        info = q["stellen"][k]
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=info["name"], abschnitt=info.get("abschnitt"),
            richtung=None, lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
            hinweise=list(info.get("hinweise") or [])))
    s_, t_, h_, w_ = [], [], [], []
    for p in dateien:
        bericht.dateien.append(p.stem.removeprefix("quartal_").replace("_", " "))
        kopf, zeilen, weg = lies_quartal(p.read_text(encoding="utf-8-sig", errors="replace"))
        bericht.unlesbar += weg
        bericht.stunden_datei += len(zeilen)
        if not _kopf_passt(kopf, spalten):
            bericht.kopf_abweichend.append(f"{p.stem}: {' | '.join(kopf[1:5])}")
        for tag, stunde, werte in zeilen:
            for i, k in enumerate(namen):
                teil = [werte[j] for j, (s, _) in enumerate(spalten) if s == k]
                if any(not re.fullmatch(r"\d+", x) for x in teil):
                    bericht.leer[k] += 1
                    w = LEER
                else:
                    w = sum(int(x) for x in teil)
                # dieselbe Stunde in zwei Dateien: nicht gezählt (setze_lokal: zu viele Einträge)
                s_.append(i)
                t_.append(tag)
                h_.append(stunde)
                w_.append(w)
    t = np.array(t_, dtype="datetime64[D]")
    reihe = Messreihe.leer(q["code"], t.min().astype(date), t.max().astype(date), stellen, ("rad",))
    bericht.stunden, bericht.sommerzeit = setze_lokal(
        reihe, "rad", np.array(s_, dtype=np.int64), t, np.array(h_, dtype=np.int64),
        np.array(w_, dtype=np.int64), anzahl=1, rueck=q.get("rueck", "einfach"))
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Richtung, je Zählstelle beide Richtungen zusammen; nur "
                        "Quartale mit offener Lizenz (ab 2021)")]
    return reihe
