"""Bonn: Fahrradmessstellen der Bundesstadt Bonn (Eco-Counter) – Stundenwerte je Zählstelle als
Jahresdatei im Open-Data-Portal der Stadt (eine CSV je Jahr, erscheint nach Ende des Jahres).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer`, tools/rad_erkunden15–16.py):
- Katalog `data.json` (DCAT): je Jahr ein Datensatz „Fahrradmessstellen Ergebnisse Radzählungen
  JJJJ“ (CC0) mit einer Stundenauswertung, teils dazu einer 15-Minuten-Auswertung.
- Jahresdatei: zwei Kopfzeilen („Zeitraum;…“, leer), dann `Time;5.01 BN - Kennedybrücke
  (Nordseite);…` – eine Spalte je Zählstelle (Kennung „N.NN“), dahinter Summen der Brücken (beide
  Seiten) und eine Summenspalte, zuletzt eine Zeile „Summe“. Zeit in Ortszeit, je nach Jahr als
  „01.01.2025 00:00“ oder „1. Jan. 2024 00:00“. Leere Zelle = nicht gezählt.
- Übernommen nur die Spalten der Zählstellen (Kennung vorn) mit Lage in `stellen`; die Summen der
  Brücken stehen schon als ihre zwei Seiten in der Karte.
- Nicht übernommen: 2019 (Open.NRW führt den Datensatz unter geschlossener Lizenz; Mac-Roman) und
  2022 (nur je Kanal, Kanäle derselben Stelle zählen teils gleichzeitig – `ohne_jahre`).
- Zeitumstellung: siehe `rueck` in sources.yaml und die Hinweise an der Quelle.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_lokal

JAHR = re.compile(r"^Fahrradmessstellen Ergebnisse Radzählungen (20\d{2})$")
STELLE = re.compile(r"^(\d+\.\d+) BN - (.+?)\s*$")
MONATE = {"jan": 1, "feb": 2, "mär": 3, "märz": 3, "mrz": 3, "apr": 4, "mai": 5, "jun": 6,
          "juni": 6, "jul": 7, "juli": 7, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11,
          "dez": 12}
ZIFFERN = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})")
WORT = re.compile(r"^(\d{1,2})\.\s*([^\W\d_]+)\.?\s+(\d{4})\s+(\d{1,2}):(\d{2})")


@dataclass
class Bericht:
    dateien: list[str] = field(default_factory=list)
    stunden_datei: int = 0
    unlesbar: Counter = field(default_factory=Counter)  # je Datei: Zeilen ohne lesbare Zeit
    leer: int = 0
    ohne_lage: set[str] = field(default_factory=set)
    stellen: int = 0
    stunden: int = 0
    sommerzeit: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{len(self.dateien)} Jahresdateien ({', '.join(self.dateien)}): {self.stunden_datei} "
             f"Stunden, leere Zellen (nicht gezählt) {self.leer}; {self.stellen} Zählstellen; "
             f"Stunden in der Karte: rad {self.stunden}; 2 Uhr am Tag der Sommerzeit verworfen: "
             f"{self.sommerzeit}"]
        if any(self.unlesbar.values()):
            z.append("Zeilen ohne lesbare Zeit (außer „Summe“): "
                     + ", ".join(f"{k} {n}" for k, n in self.unlesbar.items() if n))
        if self.ohne_lage:
            z.append(f"Spalten ohne Lage (nicht in der Karte): {', '.join(sorted(self.ohne_lage))}")
        return z


def zeit(s: str) -> datetime | None:
    """„01.01.2025 00:00“ oder „1. Jan. 2024 00:00“ (Ortszeit) -> datetime; sonst None."""
    s = s.strip()
    m = ZIFFERN.match(s)
    if m:
        return datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4]), int(m[5]))
    m = WORT.match(s)
    if m and m[2].lower() in MONATE:
        return datetime(int(m[3]), MONATE[m[2].lower()], int(m[1]), int(m[4]), int(m[5]))
    return None


def text(roh: bytes) -> str:
    for kodierung in ("utf-8-sig", "cp1252"):
        try:
            t = roh.decode(kodierung)
            break
        except UnicodeDecodeError:
            continue
    else:
        t = roh.decode("mac_roman")
    return t.replace("\r\n", "\n").replace("\r", "\n")


def lies_jahr(t: str) -> tuple[dict[int, tuple[str, str]], list[tuple[datetime, list[str]]], int]:
    """-> ({Spalte: (Kennung, Name)} der Zählstellen, [(Zeit, Zellen)], Zeilen ohne lesbare Zeit
    außer „Summe“)."""
    zz = t.split("\n")
    k = next((i for i, z in enumerate(zz[:10]) if z.startswith("Time;")), None)
    if k is None:
        raise ValueError("kein Kopf „Time;…“")
    kopf = zz[k].split(";")
    spalten = {}
    for i, name in enumerate(kopf[1:], start=1):
        m = STELLE.match(name.strip())
        if m:
            spalten[i] = (m[1], m[2])
    zeilen, weg = [], 0
    for z in zz[k + 1:]:
        if not z.strip():
            continue
        f = z.split(";")
        t0 = zeit(f[0])
        if t0 is None:
            weg += f[0].strip().lower() != "summe"
            continue
        zeilen.append((t0, f))
    return spalten, zeilen, weg


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Je Jahr ab `ab_jahr` (ohne `ohne_jahre`) die Stundenauswertung aus dem Katalog holen; nur
    Datensätze mit CC0. Scheitert ein Jahr, bleibt die Datei des letzten Abrufs."""
    import requests

    from zaehlkarte.fetch import UA, lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    r = requests.get(q["katalog"], headers=UA, timeout=120)
    r.raise_for_status()
    ohne = set(q.get("ohne_jahre") or [])
    gewaehlt, uebersprungen = {}, []
    for ds in r.json().get("dataset", []):
        m = JAHR.match((ds.get("title") or "").strip())
        if not m or int(m[1]) < q["ab_jahr"] or int(m[1]) in ohne:
            continue
        if "cc-zero" not in (ds.get("license") or ""):
            uebersprungen.append(f"{m[1]} (Lizenz {ds.get('license')})")
            continue
        verteilung = [(d.get("title") or "", d.get("downloadURL") or d.get("accessURL") or "")
                      for d in ds.get("distribution", [])]
        verteilung = [(t, u) for t, u in verteilung if u.lower().endswith(".csv")]
        stunde = [u for t, u in verteilung if re.search(r"stunde|stündlich|1h", t, re.I)]
        if not stunde and len(verteilung) == 1:
            stunde = [verteilung[0][1]]
        if stunde:
            gewaehlt[int(m[1])] = stunde[0]
        else:
            uebersprungen.append(f"{m[1]} (keine Stundenauswertung)")
    if not gewaehlt:
        raise ValueError(f"{q['code']}: keine Jahresdatei im Katalog gefunden")
    fehler = []
    for jahr, url in sorted(gewaehlt.items()):
        try:
            lade(url, ordner / f"jahr_{jahr}.csv")
        except Exception as e:  # noqa: BLE001 – ein Jahr darf die anderen nicht aufhalten
            fehler.append(f"{jahr} ({e!r})")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dateien": {str(j): u for j, u in sorted(gewaehlt.items())}, "fehler": fehler,
        "uebersprungen": uebersprungen,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(gewaehlt) - len(fehler)} Jahresdateien geholt"
            + (f"; Fehler: {', '.join(fehler)}" if fehler else "")
            + (f"; übersprungen: {', '.join(uebersprungen)}" if uebersprungen else "")]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    ohne = set(q.get("ohne_jahre") or [])
    dateien = [p for p in sorted(ordner.glob("jahr_*.csv"))
               if int(p.stem.removeprefix("jahr_")) not in ohne]
    if not dateien:
        raise ValueError(f"{q['code']}: keine Jahresdateien in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    kennungen = [str(k) for k in q["stellen"]]
    idx = {k: i for i, k in enumerate(kennungen)}
    stellen = []
    for k in kennungen:
        info = q["stellen"][k]
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=info["name"], abschnitt=info.get("abschnitt"),
            richtung=None, lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
            hinweise=list(info.get("hinweise") or [])))
    s_, t_, h_, w_ = [], [], [], []
    for p in dateien:
        spalten, zeilen, weg = lies_jahr(text(p.read_bytes()))
        bericht.dateien.append(p.stem.removeprefix("jahr_"))
        bericht.unlesbar[p.stem.removeprefix("jahr_")] = weg
        bericht.stunden_datei += len(zeilen)
        if any(t0.minute for t0, _ in zeilen):
            raise ValueError(f"{q['code']}: {p.name} ist keine Stundenauswertung")
        for spalte, (kennung, name) in spalten.items():
            if kennung not in idx:
                bericht.ohne_lage.add(f"{kennung} {name}")
                continue
            i = idx[kennung]
            for t0, f in zeilen:
                v = f[spalte].strip() if spalte < len(f) else ""
                if not re.fullmatch(r"\d+", v):
                    bericht.leer += 1  # leer (oder unlesbar): nicht gezählt, die Zelle bleibt leer
                    continue
                s_.append(i)
                t_.append(t0.date())
                h_.append(t0.hour)
                w_.append(int(v))
    if not s_:
        raise ValueError(f"{q['code']}: keine gezählte Stunde einer Zählstelle mit Lage")
    t = np.array(t_, dtype="datetime64[D]")
    reihe = Messreihe.leer(q["code"], t.min().astype(date), t.max().astype(date), stellen, ("rad",))
    bericht.stunden, bericht.sommerzeit = setze_lokal(
        reihe, "rad", np.array(s_, dtype=np.int64), t, np.array(h_, dtype=np.int64),
        np.array(w_, dtype=np.int64), anzahl=1, rueck=q.get("rueck", "einfach"))
    bericht.stellen = len(stellen)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle aus den Jahresdateien der Stadt")]
    return reihe
