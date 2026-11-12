"""Kartendaten der Dauerzählstellen schreiben: public/data/dauer/ (gitignored, gebaut vom
Workflow „Dauerzählstellen bauen“ und mit der Seite ausgeliefert).

Vertrag mit dem Frontend (js/data/dauer.js, tests/web/vertrag.spec.js) – wer ihn ändert, zieht
beide im selben Schritt mit:
- dauer/index.json: Stellen spaltenweise (`stellen.felder`; `g` = Bitmaske der Gruppen in der
  Reihenfolge von `gruppen`), Quellen mit Lizenzen, ihren Gruppen und ihrem eigenen Standardtag,
  Zeitraum (`von`, `bis`), Kalender je Land (ein Zeichen je Tag ab `von`: s Schultag, f Ferien,
  h Feiertag, w Wochenende, u unbekannt) und die Namen der übrigen Dateien (`dateien`).
- dauer/tage/JJJJ.json: Tagessummen aller Stellen eines Jahres je Gruppe, in der Reihenfolge der
  Stellen; null = an dem Tag nicht vollständig gezählt (nie 0), null statt Liste = im Jahr kein
  vollständiger Tag. Das braucht die Karte für den gewählten Tag.
- dauer/NN.json: je Stelle die ganze Reihe der Tagessummen ab `von`, die gezählten Stunden je
  Gruppe und Tag (`n`), Tage mit doppelter Stunde 2–3 Uhr (`doppelt`, Rückstellung der Uhr) und
  die Stundenwerte der jüngsten 12 Monate der Quelle ab `stunden_von` – geladen erst beim Klick.
"""

from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import GRUPPEN, Messreihe, tagessummen
from zaehlkarte.kalender import Ferienkalender, tagtyp

VERSION = 1
CHUNK_BYTES = 900_000
STUNDEN_TAGE = 365  # Stundenwerte: die jüngsten 12 Monate je Quelle
STELLEN_FELDER = ["id", "quelle", "name", "abschnitt", "richtung", "lon", "lat", "von", "bis", "g",
                  "chunk"]
GRUPPEN_NAMEN = {"kfz": "Kfz", "lkw": "Lkw (Detektor)", "sv": "Schwerverkehr (Detektor)",
                 "rad": "Rad", "fuss": "Fuß"}
TAG = {"schule": "s", "ferien": "f", "feiertag": "h", "wochenende": "w"}


def _liste(werte: np.ndarray) -> list[int | None]:
    return [None if v < 0 else int(v) for v in werte.tolist()]


def kalender(land: str, ferien: Path | None, von: date, tage: int) -> str:
    kal = Ferienkalender.lade(ferien) if ferien else None
    return "".join(TAG.get(tagtyp(von + timedelta(days=i), land, kal)[0] or "", "u")
                   for i in range(tage))


def _lizenzen(q: dict) -> list[dict]:
    return [{
        "code": q["code"],
        "titel": q.get("titel") or q["name"],
        "herausgeber": q.get("herausgeber") or q.get("traeger"),
        "lizenz": q.get("lizenz"),
        "lizenz_url": q.get("lizenz_url"),
        "herkunft_url": q.get("portal"),
    }]


def schreibe(gelesen: list[tuple[dict, Messreihe]], pfade: Pfade | None = None,
             erzeugt: date | None = None) -> tuple[list[Path], list[str]]:
    """-> (geschriebene Dateien, Berichtszeilen)."""
    pfade = pfade or Pfade()
    ziel = pfade.karte / "dauer"
    (ziel / "tage").mkdir(parents=True, exist_ok=True)
    bericht: list[str] = []
    von = min(r.von for _, r in gelesen)
    bis = max(r.tag(r.tage - 1) for _, r in gelesen)
    tage_gesamt = (bis - von).days + 1
    gruppen = [g for g in GRUPPEN if any(g in r.werte for _, r in gelesen)]

    # je Quelle: Tagessummen, Stellen mit mindestens einem vollständigen Tag
    stellen_werte, details, quellen_meta = [], [], []
    jahreswerte: dict[int, dict[str, list]] = {
        j: {g: [] for g in gruppen} for j in range(von.year, bis.year + 1)}
    for q, r in gelesen:
        tagesweise = {g: tagessummen(r, g) for g in gruppen if g in r.werte}
        summen = {g: s for g, (s, _) in tagesweise.items()}
        stunden_ab = max(0, r.tage - STUNDEN_TAGE)
        anzahl, ohne = 0, 0
        for i, st in enumerate(r.stellen):
            voll = np.zeros(r.tage, dtype=bool)
            for s in summen.values():
                voll |= s[i] >= 0
            if not voll.any():
                ohne += 1
                continue
            a, b = int(np.argmax(voll)), int(r.tage - 1 - np.argmax(voll[::-1]))
            maske = sum(1 << k for k, g in enumerate(gruppen)
                        if g in summen and (summen[g][i] >= 0).any())
            stellen_werte.append([st.id, q["code"], st.name, st.abschnitt, st.richtung, st.lon,
                                  st.lat, r.tag(a).isoformat(), r.tag(b).isoformat(), maske])
            stunden = {}
            for g, w in r.werte.items():
                feld = w[i, stunden_ab:]
                stunden[g] = [None if (zeile < 0).all() else _liste(zeile) for zeile in feld]
            details.append({
                "kennung": st.kennung,
                "fahrstreifen": st.fahrstreifen,
                "hinweise": st.hinweise,
                "von": r.tag(a).isoformat(),
                "tage": {g: _liste(s[i, a:b + 1]) for g, s in summen.items()},
                "n": {g: n[i, a:b + 1].tolist() for g, (_, n) in tagesweise.items()},
                "doppelt": [r.tag(int(t)).isoformat() for t in np.flatnonzero(r.doppelt[i])
                            if a <= t <= b],
                "stunden_von": r.tag(stunden_ab).isoformat(),
                "stunden": stunden,
            })
            # Jahresdateien: Tage des Jahres im Bereich der Quelle
            for j in jahreswerte:
                t0 = max((date(j, 1, 1) - r.von).days, 0)
                t1 = min((date(j, 12, 31) - r.von).days, r.tage - 1)
                for g in gruppen:
                    if g not in summen or t1 < t0 or not (summen[g][i, t0:t1 + 1] >= 0).any():
                        jahreswerte[j][g].append(None)
                        continue
                    vorne = (r.von + timedelta(days=t0) - date(j, 1, 1)).days
                    hinten = (date(j, 12, 31) - (r.von + timedelta(days=t1))).days
                    jahreswerte[j][g].append([None] * vorne + _liste(summen[g][i, t0:t1 + 1])
                                             + [None] * hinten)
            anzahl += 1
        bericht.append(f"{q['code']}: {anzahl} Stellen mit vollständigen Tagen, {ohne} ohne")
        land_kal = kalender(q["land"], pfade.config / q["ferien"] if q.get("ferien") else None,
                            von, tage_gesamt)
        quellen_meta.append({
            "code": q["code"], "name": q["name"], "land": q["land"], "traeger": q.get("traeger"),
            "art": q.get("art"), "weg": q.get("weg"), "portal": q.get("portal"),
            "archiv": q.get("archiv_seite") or q.get("archiv"),
            "quellenvermerk": q.get("quellenvermerk"), "lizenzen": _lizenzen(q),
            "hinweise": [" ".join(h.split()) for h in q.get("hinweise", [])],
            "stellen": anzahl, "von": r.von.isoformat(), "bis": r.tag(r.tage - 1).isoformat(),
            "gruppen": [g for g in gruppen if g in r.werte],
            "standardtag": standardtag([(q, r)], {q["land"]: land_kal}, von).isoformat(),
            "stunden_von": r.tag(stunden_ab).isoformat(),
            "verfahren": [{"von": a.isoformat(), "bis": b.isoformat(), "text": t}
                          for a, b, t in r.verfahren],
        })

    # Chunks der Details: der Reihe nach, bis eine Datei etwa CHUNK_BYTES erreicht
    chunks: list[dict] = [{}]
    groesse = 0
    for zeile, d in zip(stellen_werte, details, strict=True):
        n = len(json.dumps(d, separators=(",", ":")))
        if groesse and groesse + n > CHUNK_BYTES:
            chunks.append({})
            groesse = 0
        chunks[-1][zeile[0]] = d
        groesse += n
        zeile.append(len(chunks) - 1)

    laender = sorted({q["land"] for q, _ in gelesen})
    ferien = {q["land"]: pfade.config / q["ferien"] for q, _ in gelesen if q.get("ferien")}
    kal = {land: kalender(land, ferien.get(land), von, tage_gesamt) for land in laender}
    index = {
        "version": VERSION,
        "erzeugt": (erzeugt or date.today()).isoformat(),
        "gruppen": gruppen,
        "gruppen_namen": {g: GRUPPEN_NAMEN[g] for g in gruppen},
        "dateien": {"tage": "dauer/tage/{jahr}.json", "details": "dauer/{n}.json"},
        "details_anzahl": len(chunks),
        "von": von.isoformat(),
        "bis": bis.isoformat(),
        "jahre": list(jahreswerte),
        "kalender": kal,
        "standardtag": standardtag(gelesen, kal, von).isoformat(),
        "quellen": quellen_meta,
        "stellen": {"felder": STELLEN_FELDER, "werte": stellen_werte},
    }
    dateien: dict[Path, dict] = {ziel / "index.json": index}
    for j, werte in jahreswerte.items():
        tage_jahr = 366 if calendar.isleap(j) else 365
        dateien[ziel / "tage" / f"{j}.json"] = {"jahr": j, "tage": tage_jahr, "werte": werte}
    for n, inhalt in enumerate(chunks):
        dateien[ziel / f"{n}.json"] = {"stellen": inhalt}
    for alt in [*ziel.glob("*.json"), *(ziel / "tage").glob("*.json")]:
        if alt not in dateien:
            alt.unlink()
    for pfad, inhalt in dateien.items():
        pfad.write_text(json.dumps(inhalt, ensure_ascii=False, separators=(",", ":")) + "\n",
                        encoding="utf-8")
    groesse_mb = sum(p.stat().st_size for p in dateien) / 1e6
    bericht.append(f"{len(dateien)} Dateien, {groesse_mb:.1f} MB, {len(chunks)} Detail-Dateien")
    return list(dateien), bericht


def vollstaendig(r: Messreihe) -> np.ndarray:
    """bool [Stellen, Tage]: an dem Tag in mindestens einer Gruppe vollständig gezählt."""
    voll = np.zeros((len(r.stellen), r.tage), dtype=bool)
    for g in r.werte:
        voll |= tagessummen(r, g)[0] >= 0
    return voll


def standardtag(gelesen: list[tuple[dict, Messreihe]], kal: dict[str, str], von: date,
                anteil: float = 0.8) -> date:
    """Tag, den die Karte zuerst zeigt: der jüngste Schultag der letzten 12 Monate, an dem
    mindestens `anteil` so viele Stellen vollständig gezählt sind wie am besten Schultag dort
    (vollständig in mindestens einer Gruppe; mit einer Quelle: ihr eigener Standardtag)."""
    je_tag: dict[date, int] = {}
    for q, r in gelesen:
        voll = vollstaendig(r).sum(axis=0)
        for t in range(r.tage):
            tag = r.tag(t)
            if kal.get(q["land"], "")[(tag - von).days: (tag - von).days + 1] == "s":
                je_tag[tag] = je_tag.get(tag, 0) + int(voll[t])
    if not je_tag:
        return max(r.tag(r.tage - 1) for _, r in gelesen)
    letzter = max(je_tag)
    jahr = {t: n for t, n in je_tag.items() if (letzter - t).days < 365}
    grenze = anteil * max(jahr.values())
    return max(t for t, n in jahr.items() if n >= grenze)


def statistik(gelesen: list[tuple[dict, Messreihe]]) -> list[str]:
    """Kurzbericht: vollständige Tage je Jahr und Quelle, Quintile je Gruppe."""
    zeilen = []
    for q, r in gelesen:
        voll = vollstaendig(r)
        je_jahr: dict[int, int] = {}
        for t in range(r.tage):
            je_jahr[r.tag(t).year] = je_jahr.get(r.tag(t).year, 0) + int(voll[:, t].sum())
        teile = ", ".join(f"{j}: {n}" for j, n in sorted(je_jahr.items()))
        zeilen.append(f"{q['code']}: vollständige Tage je Jahr (Stellen × Tage) – {teile}")
        for g in r.werte:
            werte = tagessummen(r, g)[0]
            werte = werte[werte >= 0]
            if werte.size:
                q4 = np.quantile(werte, [0.2, 0.4, 0.6, 0.8]).round(-1).astype(int).tolist()
                zeilen.append(f"{q['code']}: {g}-Tagessummen, Quintilgrenzen {q4}, "
                              f"Median {int(np.median(werte))}, Maximum {int(werte.max())}")
    return zeilen
