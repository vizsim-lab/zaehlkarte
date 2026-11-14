"""Leipzig: Dauerzählstellen Radverkehr der Stadt (Verkehrs- und Tiefbauamt) – Stundenwerte je
Zählstelle im WFS des Geoportals, aber nur die der letzten 31 Tage; dazu die Standorte.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden12–14.py):
- Ebene `radverkehr_dauerzaehlstelle_anzahl_stunde_zeitreihe` (CSV über `outputFormat=csv`):
  `objectid`, `stationname`, `stationid` (`de.sn.stlp.statisch.rad.<Kennung>`, die Kennung von
  Eco-Counter), `phenomenontime` (Beginn der Stunde, Ortszeit ohne Versatz), `count`, Lage als
  `POINT (x y)` in UTM 33 (ETRS89). „Für die letzten 31 Tage bis einschließlich gestern“
  (Datensatzbeschreibung), täglich neu.
- Jede Zeile stammt aus einer täglichen Lieferung (`fme_tstamp`); eine spätere Lieferung kann
  eine Stunde erneut bringen, mit geändertem Wert (etwa 0 Uhr des Folgetags). Es gilt die jüngste
  Lieferung – wie im Gedächtnis, wo ein neuer Wert den alten ersetzt.
- Rückstellung der Uhr: 2 Uhr steht in einer Lieferung zweimal da (zwei Stunden). Welche die erste
  ist, sagt die Reihenfolge der `objectid` (sie folgt je Stelle der Zeit); steht 2 Uhr nur einmal
  da, ist unklar, welche Stunde es ist – nicht gezählt. Dieselbe Stunde sonst zweimal in einer
  Lieferung: gleicher Wert zählt einmal, verschiedene gar nicht.
- Weil die Quelle nur 31 Tage vorhält, hebt die Zählkarte die Stunden selbst auf (Gedächtnis wie
  Hamburg, `gedaechtnis.py`: je UTC-Monat eine Datei, vom Workflow im Release abgelegt). Jeder
  Abruf übernimmt alle gelieferten Stunden; ein neuer Wert ersetzt den alten derselben Stunde.
- Standorte: Ebene `radverkehr_dauerzaehlstelle_standort_statisch`. Eine Stelle (Jahnallee)
  liefert keine Stunden und fehlt deshalb in der Karte.
- Tageswerte zweier Jahre gibt es auch (`…_anzahl_tag_zeitreihe`) – ohne Stunden lässt sich ein
  Tag nicht auf Vollständigkeit prüfen (Konzept, Entscheidung 5); sie weichen zudem meist etwas
  von der Summe der Stundenwerte ab. Nicht übernommen.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from zaehlkarte.config import Pfade
from zaehlkarte.dauer import gedaechtnis
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc
from zaehlkarte.koordinaten import utm_zu_wgs84

ORT = ZoneInfo("Europe/Berlin")
GEDAECHTNIS = True  # hebt die Stunden selbst auf (bau.mit_gedaechtnis, `zaehlkarte dauer frische`)
PUNKT = re.compile(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)")
ZEIT = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}):00(?::00(?:\.0+)?)?(Z|[+-]\d{2}:?\d{2})?$")


@dataclass
class Bericht:
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    monate: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{self.stellen} Zählstellen; Stunden in der Karte: rad {self.stunden}; Gedächtnis: "
             f"{len(self.monate)} Monate ({self.monate[0] if self.monate else '–'} bis "
             f"{self.monate[-1] if self.monate else '–'})"]
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def kennung(stationid: str) -> str:
    return stationid.strip().rsplit(".", 1)[-1]


def _ortszeit(tag: str, stunde: str, fold: int) -> datetime | None:
    """Ortszeit -> UTC; None für die Stunde, die es nicht gibt (Sommerzeit)."""
    t = datetime.fromisoformat(f"{tag}T{stunde}:00:00").replace(tzinfo=ORT, fold=fold)
    u = t.astimezone(UTC)
    if u.astimezone(ORT).replace(tzinfo=None) != t.replace(tzinfo=None):
        return None
    return u


def _doppeldeutig(tag: str, stunde: str) -> bool:
    t = datetime.fromisoformat(f"{tag}T{stunde}:00:00")
    return t.replace(tzinfo=ORT, fold=0).utcoffset() != t.replace(tzinfo=ORT, fold=1).utcoffset()


def lies_stunden(text: str) -> tuple[list[tuple[str, datetime, int]], Counter]:
    """CSV der Stundenebene -> [(Kennung, UTC-Beginn, Anzahl)], verworfene Zeilen je Grund."""
    weg: Counter = Counter()
    je: dict[tuple[str, str, str], list[tuple[str, int, int]]] = defaultdict(list)
    out = []
    for z in csv.DictReader(io.StringIO(text)):
        m = ZEIT.match((z.get("phenomenontime") or "").strip())
        w = (z.get("count") or "").strip()
        if not m:
            weg["Zeit"] += 1
            continue
        if not re.fullmatch(r"\d+(?:\.0+)?", w):
            weg["Wert"] += 1
            continue
        k, wert = kennung(z["stationid"]), int(float(w))
        if m[3]:  # mit Versatz: eindeutig
            v = m[3] if m[3] != "Z" else "+00:00"
            v = v if ":" in v else f"{v[:3]}:{v[3:]}"
            out.append((k, datetime.fromisoformat(f"{m[1]}T{m[2]}:00:00{v}").astimezone(UTC), wert))
            continue
        try:
            oid = int(z.get("objectid") or 0)
        except ValueError:
            oid = 0
        je[(k, m[1], m[2])].append(((z.get("fme_tstamp") or "")[:10], oid, wert))
    for (k, tag, stunde), alle in je.items():
        juengste = max(lieferung for lieferung, _, _ in alle)  # jüngste Lieferung gilt
        eintraege = sorted((oid, wert) for lieferung, oid, wert in alle if lieferung == juengste)
        if _doppeldeutig(tag, stunde):
            if len(eintraege) != 2:
                weg["2 Uhr der Rückstellung nicht zweimal"] += len(eintraege)
                continue
            for fold, (_, wert) in enumerate(eintraege):
                out.append((k, _ortszeit(tag, stunde, fold), wert))
            continue
        if len({w for _, w in eintraege}) > 1:
            weg["doppelt mit verschiedenen Werten"] += len(eintraege)
            continue
        if (u := _ortszeit(tag, stunde, 0)) is None:
            weg["Stunde der Sommerzeit"] += len(eintraege)
            continue
        out.append((k, u, eintraege[0][1]))
    return out, weg


def lies_standorte(text: str) -> dict[str, tuple[str, float, float]]:
    """CSV der Standorte -> Kennung: (Name, lon, lat)."""
    out = {}
    for z in csv.DictReader(io.StringIO(text)):
        if m := PUNKT.search(z.get("geom") or ""):
            lon, lat = utm_zu_wgs84(float(m[1]), float(m[2]), zone=33)
            out[kennung(z["stationid"])] = ((z.get("stationname") or "").strip(), lon, lat)
    return out


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Standorte und die Stunden der letzten 31 Tage holen und ins Gedächtnis übernehmen."""
    from zaehlkarte import abruf

    ordner = pfade.roh / q["code"]
    gordner = ordner / "gedaechtnis"
    gordner.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now(UTC).replace(microsecond=0)
    texte = {}
    for name in ("standorte", "stunden"):
        r = abruf.hole(q["wfs"], params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeName": q["ebenen"][name], "outputFormat": "csv"}, timeout=300)
        r.encoding = "utf-8"
        texte[name] = r.text
    werte, weg = lies_stunden(texte["stunden"])
    if not werte:
        raise ValueError(f"{q['code']}: keine Stundenwerte geliefert ({dict(weg)})")
    (ordner / "standorte.csv").write_text(texte["standorte"], encoding="utf-8")
    g = gedaechtnis.lies(gordner)
    vorher = sum(v is not None for w in g.values() for v in w)
    for k, t, w in werte:
        gedaechtnis.setze(g, k, "rad", t, w)
    geaendert = gedaechtnis.schreibe(gordner, g)
    nachher = sum(v is not None for w in g.values() for v in w)
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "stunden": len(werte),
        "von": min(t for _, t, _ in werte).isoformat(),
        "bis": max(t for _, t, _ in werte).isoformat(), "verworfen": dict(weg),
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(werte)} Stunden geholt (verworfen: {dict(weg) or 'keine'}), "
            f"Gedächtnis {vorher} -> {nachher} Stunden, "
            f"geändert: {', '.join(geaendert) or 'nichts'}"]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    if not (ordner / "standorte.csv").exists():
        raise ValueError(f"{q['code']}: keine Standorte in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    lage = lies_standorte((ordner / "standorte.csv").read_text(encoding="utf-8"))
    g = gedaechtnis.lies(ordner / "gedaechtnis")
    bericht.monate = sorted({tag[:7] for _, _, tag in g})
    stellen: list[Dauerstelle] = []
    for k in sorted({st for st, gr, _ in g if gr == "rad"}, key=lambda x: (len(x), x)):
        if k not in lage:
            bericht.ohne_lage.append(k)
            continue
        name, lon, lat = lage[k]
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=name or f"Zählstelle {k}", abschnitt=None,
            richtung=None, lon=round(lon, 6), lat=round(lat, 6), land=q["land"]))
    if not stellen:
        raise ValueError(f"{q['code']}: Gedächtnis leer oder ohne Lage – erst "
                         "`zaehlkarte dauer fetch`")
    bericht.stellen = len(stellen)
    idx = {s.kennung: i for i, s in enumerate(stellen)}
    s_, t_, w_ = gedaechtnis.felder(g, "rad", idx)
    von = (t_.min().astype(datetime) - timedelta(days=1)).date()
    bis = (t_.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, ("rad",))
    bericht.stunden = setze_utc(reihe, "rad", s_, t_, w_)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle, von der Zählkarte aufgehoben (die Quelle hält "
                        "nur 31 Tage vor)")]
    return reihe
