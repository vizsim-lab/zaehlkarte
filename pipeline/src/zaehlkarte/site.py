"""Kartendaten schreiben: public/data/{manifest,index}.json und details/NN.json, am Ende die
Datenlage (datenlage.json und docs/DATENLAGE.md, `zaehlkarte.datenlage`).

Vertrag mit dem Frontend (js/data/laden.js, js/data/modell.js): Feldnamen in `index.json`
(`stellen.felder`, `zaehlungen.felder`), Aufbau von `details/NN.json` und die Dateinamen in
`manifest.dateien`. Wer sie ändert, zieht das Frontend und tests/ im selben Schritt mit.

- index.json: alles, was Karte und Filter brauchen – spaltenweise, damit es klein bleibt.
  Kennwerte je Zählung als Liste in der Reihenfolge von GRUPPEN: `w` = Summe 7–19 Uhr (nur,
  wo jede Stunde gezählt ist), `w24` = Summe über 24 Stunden, `sp` = stärkste gezählte Stunde.
  `l` = Lieferung (Index in `lieferungen`), wo eine Quelle mehrere mit eigener Lizenz hat.
- details/NN.json: Stundenreihen aller Gruppen und die Angaben zur Zählung; je Stelle in
  einer Datei (`stellen.chunk`), geladen erst beim Klick. Ohne Stundenreihe gibt es dort
  `spitzen` ([{von, bis, name, nach, werte}], Minuten ab Mitternacht) und `fenstersummen`
  (Summe je Gruppe über das ganze Zählfenster).
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import date
from pathlib import Path

from zaehlkarte import datenlage as datenlage_
from zaehlkarte import kennzahlen as kz
from zaehlkarte.build import Gebaut, Stelle
from zaehlkarte.config import Pfade, quellen
from zaehlkarte.lizenz import ohne_lizenz
from zaehlkarte.modell import GRUPPEN, Zaehlung

VERSION = 1
TAG = {"schule": "s", "ferien": "f", "feiertag": "h", "wochenende": "w"}
LAGEN = ["gps", "quelle", "geokodiert", "uebertragen"]
CHUNK_BYTES = 350_000
STELLEN_FELDER = ["id", "quelle", "name", "typ", "lon", "lat", "lage", "chunk"]
ZAEHLUNGEN_FELDER = ["stelle", "datum", "tag", "fenster", "g", "w", "w24", "sp", "l"]
GRUPPEN_NAMEN = {
    "kfz": "Kfz",
    "sv": "Schwerverkehr",
    "rad": "Rad",
    "fuss": "Fuß",
    "kind": "Kinder/Jugendliche",
}
def fenster_text(fenster: list[tuple[int, int]]) -> str:
    """[(420, 1140)] -> '7–19'; [(360, 600), (900, 1140)] -> '6–10, 15–19'; 6:30 -> '6:30'."""

    def uhr(m: int) -> str:
        return f"{m // 60}" if m % 60 == 0 else f"{m // 60}:{m % 60:02d}"

    return ", ".join(f"{uhr(a)}–{uhr(b)}" for a, b in fenster) if fenster else ""


def _liste(werte: list[int | None]) -> list[int | None] | None:
    return werte if any(v is not None for v in werte) else None


def kennwerte(z: Zaehlung) -> dict:
    """Die Zeile einer Zählung in index.json (ohne `stelle`)."""
    gruppen = z.gruppen()
    maske = sum(1 << i for i, g in enumerate(GRUPPEN) if g in gruppen)
    sp = [(kz.spitzenstunde(z, g) or (None, None))[1] for g in GRUPPEN]
    return {
        "datum": z.datum.isoformat() if z.datum else None,
        "tag": TAG.get(z.tagtyp or ""),
        "fenster": fenster_text(z.fenster),
        "g": maske,
        "w": _liste([kz.summe(z, g, 7, 19) for g in GRUPPEN]),
        "w24": _liste([kz.tag24(z, g) for g in GRUPPEN]),
        "sp": _liste(sp),
    }


def detail(z: Zaehlung) -> dict:
    d = {
        "kennung": z.kennung,
        "name": z.name,
        "h0": z.h0,
        "stunden": {g: z.stunden[g] for g in GRUPPEN if g in z.stunden},
        "summen": {g: v for g, v in z.summen.items() if v is not None},
        "spitzen": z.spitzen,
        "fenstersummen": {g: v for g, v in z.fenstersummen.items() if v is not None},
        "intervall": z.intervall,
        "richtungen": z.richtungen,
        "kategorien": z.kategorien,
        "rohdatei": z.rohdatei,
        "lieferung": z.lieferung,
        "tagname": z.tagname,
        "bemerkung": z.bemerkung,
        "hinweise": z.hinweise,
    }
    return {k: v for k, v in d.items() if v not in (None, "", [], {})}


def _abruf(q: dict, pfade: Pfade) -> str | None:
    """Datum des Abrufs (TT.MM.JJJJ) aus der Datei, die `fetch` schreibt (Potsdam: Teil der
    Quellenangabe nach NB-16-OGD); None ohne Rohdaten."""
    pfad = pfade.roh / q["abruf"] if q.get("abruf") else None
    if pfad is None or not pfad.exists():
        return None
    return date.fromisoformat(pfad.read_text(encoding="utf-8").strip()).strftime("%d.%m.%Y")


def _lizenzen(q: dict, pfade: Pfade) -> list[dict]:
    if "lieferungen" in q:
        felder = ("code", "titel", "herausgeber", "lizenz", "lizenz_url", "herkunft_url")
        out = [{**{k: lf.get(k) for k in felder}, **ohne_lizenz(lf)} for lf in q["lieferungen"]]
        if "geokodierung" in q:
            g = q["geokodierung"]
            out.append({"code": "lage", **{k: g.get(k) for k in felder[1:]}})
        return out
    titel = q.get("titel") or f"Straßenverkehrszählungen {q['name']}"
    if "{abruf}" in titel:
        datum = _abruf(q, pfade)
        titel = titel.replace("{abruf}", datum) if datum else titel.replace("/{abruf}", "")
    out = [
        {
            "code": q["code"],
            "titel": titel,
            "herausgeber": q.get("traeger"),
            "lizenz": q.get("lizenz"),
            "lizenz_url": q.get("lizenz_url"),
            "herkunft_url": q.get("portal"),
            **ohne_lizenz(q),
        }
    ]
    if "geokodierung" in q:
        g = q["geokodierung"]
        felder = ("titel", "herausgeber", "lizenz", "lizenz_url", "herkunft_url")
        out.append({"code": "lage", **{k: g.get(k) for k in felder}})
    return out


def _schreibe_json(pfad: Path, inhalt: dict, eingerueckt: bool) -> None:
    text = json.dumps(inhalt, ensure_ascii=False, indent=1 if eingerueckt else None,
                      separators=None if eingerueckt else (",", ":"))
    pfad.write_text(text + "\n", encoding="utf-8")


def _statistik(stellen: list[Stelle], ohne: list[Zaehlung]) -> dict:
    zs = [z for s in stellen for z in s.zaehlungen]
    gruppen = Counter(g for z in zs for g in z.gruppen())
    jahre = sorted(z.datum.year for z in zs if z.datum)
    return {
        "stellen": len(stellen),
        "zaehlungen": len(zs),
        "ohne_lage": len(ohne),
        "gruppen": {g: gruppen[g] for g in GRUPPEN},
        "von": jahre[0] if jahre else None,
        "bis": jahre[-1] if jahre else None,
        "lage": dict(Counter(z.lage for z in zs)),
    }


def schreibe(gebaut: Gebaut, pfade: Pfade | None = None, erzeugt: date | None = None) -> list[Path]:
    pfade = pfade or Pfade()
    ziel = pfade.karte
    (ziel / "details").mkdir(parents=True, exist_ok=True)
    live = quellen(pfade)
    codes = list(live)
    stellen = sorted(gebaut.stellen, key=lambda s: (codes.index(s.quelle), s.id))

    # Chunks: Stellen reihum, damit jede Datei ähnlich groß wird
    roh = [[detail(z) for z in s.zaehlungen] for s in stellen]
    groesse = sum(len(json.dumps(r, ensure_ascii=False, separators=(",", ":"))) for r in roh)
    n_chunks = max(1, math.ceil(groesse / CHUNK_BYTES))

    lieferungen = [f"{c}:{lf['code']}" for c, q in live.items() for lf in q.get("lieferungen", [])]
    stellen_werte, zaehlungen_werte = [], []
    chunks: list[dict[str, dict]] = [{} for _ in range(n_chunks)]
    for i, s in enumerate(stellen):
        chunk = i % n_chunks
        stellen_werte.append(
            [s.id, codes.index(s.quelle), s.name, s.typ, s.lon, s.lat, LAGEN.index(s.lage), chunk]
        )
        for z, d in zip(s.zaehlungen, roh[i], strict=True):
            chunks[chunk][str(len(zaehlungen_werte))] = d
            k = kennwerte(z)
            lf = f"{z.quelle}:{z.lieferung}"
            k["l"] = lieferungen.index(lf) if lf in lieferungen else None
            zaehlungen_werte.append([i, *(k[f] for f in ZAEHLUNGEN_FELDER[1:])])

    index = {
        "version": VERSION,
        "quellen": codes,
        "lagen": LAGEN,
        "gruppen": list(GRUPPEN),
        "lieferungen": lieferungen,
        "stellen": {"felder": STELLEN_FELDER, "werte": stellen_werte},
        "zaehlungen": {"felder": ZAEHLUNGEN_FELDER, "werte": zaehlungen_werte},
    }
    je_quelle = {c: [s for s in stellen if s.quelle == c] for c in codes}
    manifest = {
        "version": VERSION,
        "erzeugt": (erzeugt or date.today()).isoformat(),
        "dateien": {
            "index": "index.json",
            "details": "details/{n}.json",
            "datenlage": "datenlage.json",
        },
        "details_anzahl": n_chunks,
        "gruppen": [{"id": g, "name": GRUPPEN_NAMEN[g]} for g in GRUPPEN],
        "quellen": [
            {
                "code": c,
                "name": q["name"],
                "land": q["land"],
                "traeger": q.get("traeger"),
                "art": q.get("art"),
                "weg": q.get("weg"),
                "portal": q.get("portal"),
                "lizenzen": _lizenzen(q, pfade),
                **_statistik(je_quelle[c], [z for z in gebaut.ohne_lage if z.quelle == c]),
            }
            for c, q in live.items()
        ],
        "statistik": _statistik(stellen, gebaut.ohne_lage),
    }
    dateien = {
        ziel / "index.json": index,
        ziel / "manifest.json": manifest,
    }
    for n, inhalt in enumerate(chunks):
        dateien[ziel / "details" / f"{n}.json"] = {"zaehlungen": inhalt}
    for alt in (ziel / "details").glob("*.json"):
        if alt not in dateien:
            alt.unlink()
    for pfad, inhalt in dateien.items():
        _schreibe_json(pfad, inhalt, eingerueckt=pfad.name == "manifest.json")
    zaehlungen = Counter({c: sum(len(s.zaehlungen) for s in je_quelle[c]) for c in codes})
    dl = datenlage_.schreibe(pfade, date.fromisoformat(manifest["erzeugt"]), zaehlungen)
    return [*dateien, dl[0]]
