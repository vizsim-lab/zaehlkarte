"""Dresden: Rad-Dauerzählstellen der Landeshauptstadt über die OGC-API-Schnittstelle des
Themenstadtplans (cardo, `kommisdd.dresden.de/net4/public/ogcapi`), ohne Lizenzangabe
(CLAUDE.md, „Quellen ohne Lizenz“).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/erkundung`, tools/holen.py Runden 4–8):
- Ebene `L1780` „Radverkehr – Dauerzählstellen – alle Zählwerte (veröffentlicht)“: eine Zeile je
  Zählstelle und Stunde – `ids` (Zählstelle), `fremd_id` („F01020“), `bezeichnung`, `lage`,
  `status` („Aktiv“, „Inaktiv“, „Historisch“), `r1`/`w1` und `r2`/`w2` (Richtung und Wert),
  `messzeit`, Punkt. Ebene `L1781`: je aktiver Zählstelle der jüngste Wert, mit Lage; die
  Kennung des Objekts dort ist `ids` in `L1780`.
- Abfrage `items?filter=…&format=csv&delimiter=Semicolon&propertynames=…`: Filter in der Syntax
  des Servers (`ids==1077 and messzeit>="2025-01-01T00:00:00"`), Zeiten nur als ISO; kein
  `offset` und keine Seiten – je Jahr ein Abruf aller Zählstellen (2025: 270.000 Zeilen, 8 MB).
  Die Zeilen-ID (`id`) vergibt der Server bei jedem Aufbau der Ebene neu (je Zählstelle ein
  Block) – kein Schlüssel.
- Zeit: CSV-Ausgabe und Filter in Ortszeit („2025-10-26 02:00:00“, 0 Uhr nur als Datum
  „2025-10-26“); die GeoJSON-Ausgabe zeigt dieselbe Zeile in UTC („26.10.2025 00:00:00“). Am Tag
  der Sommerzeit fehlt 2 Uhr; am Tag der Rückstellung steht 2 Uhr einmal (bis 2024), seit 2025
  dazu eine Zeile mit krummer Minute („02:13:00“). Solche Zeilen – auch „03:11:00“ am Tag der
  Sommerzeit und vereinzelt an anderen Tagen – sind keine Stundenwerte: ihre Stunde gilt als
  nicht gezählt (nie aufgeteilt oder verschoben). Die Uhrzeit gilt wie geliefert als Beginn der
  Stunde (nicht belegt: an Werktagen ist die Stunde ab 8 Uhr die stärkste am Morgen).
- Zählstellen mit nur einer Richtung (`r2` leer, Carolabrücke): der Wert ist `w1`; sonst ist
  eine Stunde nur gezählt, wenn beide Richtungen einen Wert haben.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_lokal

FELDER = ("ids", "w1", "w2", "messzeit")
STAMM = ("fremd_id", "bezeichnung", "lage", "status", "r1", "r2")


@dataclass
class Bericht:
    gelesen: int = 0  # Zeilen der Jahresdateien
    stellen: int = 0
    ohne_werte: list[str] = field(default_factory=list)
    ohne_stamm: list[str] = field(default_factory=list)
    krumm: int = 0
    leer: int = 0
    stunden: int = 0
    sommerzeit: int = 0
    bis: str | None = None

    def zeilen(self) -> list[str]:
        z = [f"{self.gelesen} Zeilen, {self.stellen} Zählstellen, {self.stunden} Stunden in der "
             f"Karte (krumme Zeitstempel, Stunde nicht gezählt: {self.krumm}; ohne Wert einer "
             f"Richtung: {self.leer}; 2 Uhr am Tag der Sommerzeit verworfen: {self.sommerzeit}); "
             f"jüngster Wert {self.bis}"]
        if self.ohne_werte:
            z.append(f"Ohne Werte: {', '.join(self.ohne_werte)}")
        if self.ohne_stamm:
            z.append(f"Werte ohne Stammdaten (nicht in der Karte): {', '.join(self.ohne_stamm)}")
        return z


def items_url(q: dict, ebene: str, filter_: str | None = None, felder=None, csv_: bool = True,
              limit: int | None = None) -> str:
    """URL einer Abfrage – selbst kodiert (Leerzeichen als %20, wie in der Erkundung geprüft)."""
    teile = []
    if filter_:
        teile.append("filter=" + urllib.parse.quote(filter_, safe=""))
    if csv_:
        teile += ["format=csv", "delimiter=Semicolon"]
    if felder:
        teile.append("propertynames=" + ",".join(felder))
    if limit:
        teile.append(f"limit={limit}")
    return f"{q['api']}{ebene}/items" + ("?" + "&".join(teile) if teile else "")


def jahr_filter(jahr: int) -> str:
    return f'messzeit>="{jahr}-01-01T00:00:00" and messzeit<"{jahr + 1}-01-01T00:00:00"'


def stamm_aus_feature(f: dict, kennung: int | None = None) -> dict:
    p = f.get("properties") or {}
    lon, lat = (f.get("geometry") or {}).get("coordinates", [None, None])[:2]
    ids = kennung if kennung is not None else p.get("ids", f.get("id"))
    return {"ids": int(ids), **{k: (p.get(k) or "").strip() for k in STAMM},
            "lon": lon, "lat": lat}


def ids_in(text: str) -> set[int]:
    return {int(r["ids"]) for r in csv.DictReader(io.StringIO(text), delimiter=";")
            if (r.get("ids") or "").strip().isdigit()}


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Aktive Zählstellen (L1781) mit Lage, je Jahr die Stunden aller Zählstellen (L1780, ältere
    Jahre als das Vorjahr nur, wenn sie fehlen), Stammdaten von Zählstellen, die nur in den
    Stunden vorkommen (eine Zeile der Ebene L1780 als GeoJSON)."""
    from zaehlkarte import abruf

    ordner = pfade.roh / q["code"]
    (ordner / "werte").mkdir(parents=True, exist_ok=True)
    pfad_stamm = ordner / "stellen.json"
    stamm: dict[str, dict] = {}
    if pfad_stamm.exists():
        stamm = json.loads(pfad_stamm.read_text(encoding="utf-8"))["stellen"]
    aktuell = abruf.hole(items_url(q, q["aktuell"], csv_=False), timeout=120).json()
    for f in aktuell.get("features") or []:
        if f.get("id") is not None:
            s = stamm_aus_feature(f, int(f["id"]))
            stamm[str(s["ids"])] = s
    heute = datetime.now(UTC).date()
    geholt, fehler, gesehen = [], [], set()
    for jahr in range(q["ab_jahr"], heute.year + 1):
        ziel = ordner / "werte" / f"{jahr}.csv"
        if jahr >= heute.year - 1 or not ziel.exists():
            try:
                r = abruf.hole(items_url(q, q["werte"], jahr_filter(jahr), FELDER), timeout=600)
                r.encoding = "utf-8"
                if not r.text.startswith('"ids"'):
                    raise ValueError(r.text[:200])
                ziel.write_text(r.text, encoding="utf-8")
                geholt.append(jahr)
            except Exception as e:  # noqa: BLE001 – ein Jahr darf die anderen nicht aufhalten
                fehler.append(f"{jahr}: {e!r}"[:200])
        if ziel.exists():
            gesehen |= ids_in(ziel.read_text(encoding="utf-8"))
    for ids in sorted(gesehen - {int(k) for k in stamm}):
        try:
            fc = abruf.hole(items_url(q, q["werte"], f"ids=={ids}", csv_=False, limit=1),
                            timeout=120).json()
            stamm[str(ids)] = stamm_aus_feature(fc["features"][0], ids)
        except Exception as e:  # noqa: BLE001
            fehler.append(f"Stammdaten {ids}: {e!r}"[:200])
    pfad_stamm.write_text(json.dumps({"stellen": stamm}, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "jahre": geholt, "stellen": len(stamm), "fehler": fehler},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if not geholt and not any((ordner / "werte").glob("*.csv")):
        raise ValueError(f"{q['code']}: nichts geholt – {'; '.join(fehler)}")
    return [f"{q['code']}: {len(stamm)} Zählstellen, Jahre {geholt}"
            + (f", Fehler: {'; '.join(fehler[:5])}" if fehler else "")]


def zeit(text: str) -> tuple[date, int, bool] | None:
    """„2025-10-26 02:00:00“ -> (Tag, 2, True); „2025-10-26“ -> 0 Uhr; krumme Minute -> False."""
    text = text.strip()
    try:
        if len(text) == 10:
            return date.fromisoformat(text), 0, True
        t = datetime.fromisoformat(text)
    except ValueError:
        return None
    return t.date(), t.hour, t.minute == 0 and t.second == 0


def wert(text: str) -> int | None:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return int(round(float(text)))
    except ValueError:
        return None


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    pfad_stamm = ordner / "stellen.json"
    if not pfad_stamm.exists():
        raise ValueError(f"{q['code']}: keine Stammdaten in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    stamm = json.loads(pfad_stamm.read_text(encoding="utf-8"))["stellen"]
    roh: dict[int, list[tuple[date, int, int]]] = {}
    for p in sorted((ordner / "werte").glob("*.csv")):
        for r in csv.DictReader(io.StringIO(p.read_text(encoding="utf-8")), delimiter=";"):
            bericht.gelesen += 1
            z = zeit(r.get("messzeit") or "")
            ids = (r.get("ids") or "").strip()
            if z is None or not ids.isdigit():
                continue
            tag, stunde, voll = z
            s = stamm.get(ids) or {}
            eine = not (s.get("r2") or "").strip() and bool(s)
            w1, w2 = wert(r.get("w1")), wert(r.get("w2"))
            if not voll:
                bericht.krumm += 1
                w = -1
            elif w1 is None or (w2 is None and not eine):
                bericht.leer += 1
                w = -1
            else:
                w = w1 + (0 if eine else w2)
            roh.setdefault(int(ids), []).append((tag, stunde, w))
    stellen: list[Dauerstelle] = []
    eintraege: list[tuple[int, date, int, int]] = []
    for ids in sorted(roh, key=lambda k: ((stamm.get(str(k)) or {}).get("fremd_id") or "", k)):
        s = stamm.get(str(ids))
        if not s or s.get("lon") is None:
            bericht.ohne_stamm.append(str(ids))
            continue
        werte = roh[ids]
        if not any(w >= 0 for _, _, w in werte):
            bericht.ohne_werte.append(s.get("bezeichnung") or str(ids))
            continue
        hinweise = []
        if not (s.get("r2") or "").strip():
            hinweise.append(f"Zählt nur eine Richtung ({s.get('r1') or 'ohne Angabe'}).")
        if (s.get("status") or "Aktiv") not in ("Aktiv", "A"):
            hinweise.append(f"Laut Quelle nicht mehr in Betrieb (Status „{s['status']}“).")
        i = len(stellen)
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=s.get("fremd_id") or str(ids),
            name=s.get("bezeichnung") or str(ids), abschnitt=s.get("lage") or None, richtung=None,
            lon=round(float(s["lon"]), 6), lat=round(float(s["lat"]), 6), land=q["land"],
            hinweise=hinweise))
        eintraege += [(i, t, h, w) for t, h, w in werte]
    if not stellen:
        raise ValueError(f"{q['code']}: keine Werte – erst `zaehlkarte dauer fetch`")
    bericht.stellen = len(stellen)
    tage = [t for _, t, _, w in eintraege if w >= 0]
    von, bis = min(tage), max(tage)
    bericht.bis = bis.isoformat()
    eintraege = [e for e in eintraege if von <= e[1] <= bis]
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    st = np.array([e[0] for e in eintraege], dtype=np.int64)
    tg = np.array([e[1] for e in eintraege], dtype="datetime64[D]")
    hh = np.array([e[2] for e in eintraege], dtype=np.int64)
    ww = np.array([e[3] for e in eintraege], dtype=np.int64)
    bericht.stunden, bericht.sommerzeit = setze_lokal(reihe, "rad", st, tg, hh, ww, anzahl=1,
                                                      rueck=q.get("rueck", "einfach"))
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Richtung aus der OGC-API der Stadt, Richtungen summiert")]
    return reihe
