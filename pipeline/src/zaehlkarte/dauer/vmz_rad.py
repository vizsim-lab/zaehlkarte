"""VMZ Niedersachsen: alle Rad-Zählstellen auf vmz-niedersachsen.de – die der Landesbehörde
(NLStBV) an Bundes- und Landesstraßen und die von Hannover, der Region Hannover, Braunschweig,
Verden (Aller), der Samtgemeinde Gellersen, Rotenburg (Wümme) und Jemgum. Stundenwerte je
Zählstelle seit 2017 über die Schnittstelle der Zählerabfrage, ohne Lizenzangabe (CLAUDE.md,
„Quellen ohne Lizenz“).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/erkundung`, tools/holen.py, Runden 4–6):
- Zählstellen: in der Seite der Zählstellenübersicht (`liste`) als Startzustand der Karte
  eingebettet (`JSON.parse('…')`, darin `featureSources["niedersachsen-radzaehler"].data`): je
  Zählstelle `externalId`, `name`, `group` („70_Stadt Hannover“, „zzz_Stadt Braunschweig“),
  `source` (LHH, Region Hannover, NLSTBV) und die Lage als Punkt. Dieselbe Liste als
  `/geojson/niedersachsen-radzaehler.geojson` sperrt robots.txt – sie wird nicht geholt.
- Werte: `<api>values/<von>/<bis>/hourly?stationIds=<id>,<id>,…` (JSON; mit `format=csv` als
  Tabelle mit einer Spalte je Zählstelle) – je Zählstelle `values`: [{datetime: „2026-10-20
  07:00:00“ (Ortszeit), value: „151“}]; eine fehlende Stunde = nicht gezählt. Vom Endtag `<bis>`
  kommt nur die Stunde ab 0 Uhr (`toDateTime` = Beginn des Endtags): je Jahr darum bis zum 1.1.
  des Folgejahrs abrufen und nur die Stunden des Jahrs ablegen – sonst stünde 0 Uhr am 1.1. in
  zwei Dateien (doppelt = nicht gezählt) und der 31.12. wäre nie vollständig. Ein Abruf je Jahr
  für bis zu zehn Zählstellen, abgelegt je Zählstelle und Jahr; Jahre vor dem Vorjahr holt `hole`
  nur, wenn sie fehlen.
- Störungen: `<api>problems/<von>/<bis>?stationIds=…` – Zeiträume je Zählstelle (bisher nur
  `missing_data`, ganze Tage); jede Stunde darin gilt als nicht gezählt, auch wenn ein Wert dasteht.
- Namen: „B 210, Hinte, LK Aurich“ -> Name „B 210“, Abschnitt „Hinte, LK Aurich“; „Lister Meile,
  LHH“ -> „Lister Meile“ (Abschnitt: der Ort der Gruppe, „Hannover“). Doppelt geführte Zählstellen
  zählen einmal.
- Zeitumstellung: Am Tag der Umstellung auf Sommerzeit fehlt 2 Uhr (wie erwartet); am Tag der
  Rückstellung steht 2 Uhr nur einmal (`rueck: einfach` – der Tag gilt als nicht vollständig).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_lokal

EIGNER = ("LHH", "Stadt ", "Gemeinde ", "Samtgemeinde ", "Region ")  # Zusatz am Ende des Namens
ZEIT = re.compile(r"^(\d{4})-(\d{2})-(\d{2}) (\d{2}):00:00$")
BLOCK = 10  # Zählstellen je Abruf (ein Jahr Stundenwerte je Zählstelle: rund 0,4 MB JSON)


@dataclass
class Bericht:
    stellen: int = 0
    ohne_werte: list[str] = field(default_factory=list)
    stunden: int = 0
    leer: int = 0
    stoerungen: int = 0
    sommerzeit: int = 0
    bis: str | None = None

    def zeilen(self) -> list[str]:
        z = [f"{self.stellen} Zählstellen, {self.stunden} Stunden in der Karte (leere Zellen: "
             f"{self.leer}, Störungen der Quelle: {self.stoerungen} Zeiträume, 2 Uhr am Tag der "
             f"Sommerzeit verworfen: {self.sommerzeit}); jüngster Wert {self.bis}"]
        if self.ohne_werte:
            z.append(f"Ohne Werte: {', '.join(self.ohne_werte)}")
        return z


def zaehlstellen(html: str) -> list[dict]:
    """Die Zählstellen aus der Seite der Zählstellenübersicht (Startzustand der Karte)."""
    i = html.find("JSON.parse('")
    k = html.find("');", i)
    if i < 0 or k < 0:
        raise ValueError("Startzustand der Karte (JSON.parse) nicht gefunden")
    # JavaScript-Zeichenkette in einfachen Anführungszeichen: \\ -> \ und \' -> '
    zustand = json.loads(re.sub(r"\\(['\\])", r"\1", html[i + len("JSON.parse('"):k]))
    quellen = zustand.get("reHydratedState", {}).get("featureSources", {})
    fc = (quellen.get("niedersachsen-radzaehler") or {}).get("data") or {}
    out, gesehen = [], set()
    for f in fc.get("features", []):
        p = f.get("properties") or {}
        kennung = str(p.get("externalId") or "").strip()
        if not kennung or kennung in gesehen:
            continue  # die Seite führt manche Zählstelle doppelt
        gesehen.add(kennung)
        lon, lat = f["geometry"]["coordinates"][:2]
        out.append({"kennung": kennung, "name": (p.get("name") or "").strip(),
                    "gruppe": p.get("group") or "", "quelle": p.get("source") or "",
                    "lon": float(lon), "lat": float(lat)})
    return out


def ort_der_gruppe(gruppe: str) -> str:
    """„70_Stadt Hannover“ -> „Hannover“, „zzz_Samtgemeinde Gellersen“ -> „Gellersen“."""
    g = re.sub(r"^[^_]*_", "", gruppe).strip()
    return re.sub(r"^(Stadt|Gemeinde|Samtgemeinde)\s+", "", g)


def name_und_abschnitt(name: str, gruppe: str) -> tuple[str, str | None]:
    """„B 210, Hinte, LK Aurich“ -> („B 210“, „Hinte, LK Aurich“); „Lister Meile, LHH“ ->
    („Lister Meile“, „Hannover“) – ohne Abschnitt im Namen der Ort der Gruppe; nur der Eigner
    („Stadt Rotenburg (Wümme)“) -> der Ort als Name, ohne Abschnitt."""
    teile = [t.strip() for t in name.split(",") if t.strip()] or [name]
    if teile[-1].startswith(EIGNER):
        if len(teile) == 1:
            return ort_der_gruppe(gruppe), None
        teile = teile[:-1]
    return teile[0], ", ".join(teile[1:]) or ort_der_gruppe(gruppe)


def lies_werte(werte: list) -> tuple[list[tuple[date, int, int]], int]:
    """Abgelegte Werte einer Zählstelle ([[Zeit, Wert], …]) -> ([(Tag, Stunde, Wert)], Einträge
    ohne lesbaren Wert)."""
    out, leer = [], 0
    for zeit, wert in werte:
        m = ZEIT.match(str(zeit).strip())
        if not m or wert in (None, ""):
            leer += 1
            continue
        out.append((date(int(m[1]), int(m[2]), int(m[3])), int(m[4]), int(float(wert))))
    return out, leer


def stoerstunden(stoerungen: list[dict]) -> dict[str, list[tuple[date, int]]]:
    """Störungen der Quelle -> je Zählstelle die Stunden (Ortszeit) darin."""
    out: dict[str, list[tuple[date, int]]] = {}
    for p in stoerungen:
        try:
            a = datetime.strptime(p["start_datetime"], "%Y-%m-%d %H:%M:%S")
            b = datetime.strptime(p["end_datetime"], "%Y-%m-%d %H:%M:%S")
        except (KeyError, ValueError):
            continue
        t = a.replace(minute=0, second=0)
        while t <= b:
            out.setdefault(str(p.get("station_id")), []).append((t.date(), t.hour))
            t += timedelta(hours=1)
    return out


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Zählstellen aus der Übersicht, dann je Zählstelle und Jahr die Stundenwerte und je Jahr die
    Störungen. Ältere Jahre als das Vorjahr nur, wenn sie noch fehlen."""
    from zaehlkarte import abruf

    ordner = pfade.roh / q["code"]
    (ordner / "werte").mkdir(parents=True, exist_ok=True)
    seite = abruf.hole(q["liste"], timeout=120)
    seite.encoding = "utf-8"
    stellen = zaehlstellen(seite.text)
    if not stellen:
        raise ValueError(f"{q['code']}: keine Zählstelle in der Übersicht")
    (ordner / "stellen.json").write_text(json.dumps(
        {"stellen": stellen}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    heute = datetime.now(UTC).date()
    geholt, fehler = 0, []
    for jahr in range(q["ab_jahr"], heute.year + 1):
        bis = min(date(jahr + 1, 1, 1), heute)  # vom Endtag nur 0 Uhr (Kopf)
        ziel = ordner / f"stoerungen_{jahr}.json"
        if jahr >= heute.year - 1 or not ziel.exists():
            r = abruf.hole(f"{q['api']}problems/{jahr}-01-01/{bis}",
                           params={"stationIds": ",".join(s["kennung"] for s in stellen)},
                           timeout=120)
            ziel.write_text(r.text, encoding="utf-8")
        offen = [s for s in stellen if jahr >= heute.year - 1
                 or not (ordner / "werte" / f"{s['kennung']}_{jahr}.json").exists()]
        for i in range(0, len(offen), BLOCK):
            block = offen[i:i + BLOCK]
            try:
                r = abruf.hole(f"{q['api']}values/{jahr}-01-01/{bis}/hourly",
                               params={"stationIds": ",".join(s["kennung"] for s in block)},
                               timeout=300)
                antwort = r.json()
            except Exception as e:  # noqa: BLE001 – ein Block darf die anderen nicht aufhalten
                fehler.append(f"{jahr} {block[0]['kennung']}…: {e!r}"[:200])
                continue
            for s in block:
                werte = ((antwort.get(s["kennung"]) or {}).get("values")) or []
                (ordner / "werte" / f"{s['kennung']}_{jahr}.json").write_text(json.dumps(
                    [[w.get("datetime"), w.get("value")] for w in werte
                     if str(w.get("datetime", "")).startswith(f"{jahr}-")]), encoding="utf-8")
                geholt += 1
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "stellen": len(stellen), "dateien": geholt, "fehler": fehler},
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(stellen)} Zählstellen, {geholt} Jahresdateien geholt"
            + (f", Fehler: {'; '.join(fehler[:5])}" if fehler else "")]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    if not (ordner / "stellen.json").exists():
        raise ValueError(f"{q['code']}: keine Zählstellen in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    liste = json.loads((ordner / "stellen.json").read_text(encoding="utf-8"))
    stoer: dict[tuple, dict] = {}  # je Zeitraum einmal (die Jahresabrufe überlappen am 1.1.)
    for p in sorted(ordner.glob("stoerungen_*.json")):
        try:
            for x in json.loads(p.read_text(encoding="utf-8")) or []:
                stoer[(x.get("station_id"), x.get("start_datetime"), x.get("end_datetime"))] = x
        except json.JSONDecodeError:
            continue
    bericht.stoerungen = len(stoer)
    gestoert = stoerstunden(list(stoer.values()))

    stellen: list[Dauerstelle] = []
    eintraege: list[tuple[int, date, int, int]] = []
    for s in liste["stellen"]:
        werte: list[tuple[date, int, int]] = []
        for p in sorted((ordner / "werte").glob(f"{s['kennung']}_*.json")):
            w, leer = lies_werte(json.loads(p.read_text(encoding="utf-8")))
            werte += w
            bericht.leer += leer
        if not werte:
            bericht.ohne_werte.append(s["name"])
            continue
        i = len(stellen)
        name, abschnitt = name_und_abschnitt(s["name"], s["gruppe"])
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=s["kennung"], name=name, abschnitt=abschnitt,
            richtung=None, lon=round(s["lon"], 6), lat=round(s["lat"], 6), land=q["land"]))
        eintraege += [(i, t, h, w) for t, h, w in werte]
        eintraege += [(i, t, h, -1) for t, h in gestoert.get(s["kennung"], [])]
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
                        "Stundenwerte je Zählstelle aus der Zählerabfrage der VMZ Niedersachsen")]
    return reihe
