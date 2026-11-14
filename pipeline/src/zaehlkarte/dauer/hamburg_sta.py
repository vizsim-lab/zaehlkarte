"""Hamburg: Infrarot-Detektoren (Wärmebildkameras) der automatisierten Verkehrsmengenerfassung –
Stundenwerte je Zählstelle aus der SensorThings API der Urban Data Platform (iot.hamburg.de).

Eine Quelle je Dienst (sources.yaml: `dienst`, `layer` je Gruppe), beide mit diesem Adapter:
- HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren: Kfz und Schwerverkehr je Zählstelle
  (Layer Anzahl_Kfz_Zaehlstelle_1-Stunde, Anzahl_Schwerverkehr_Zaehlstelle_1-Stunde)
- HH_STA_Verkehrsdaten_Rad_Infrarotdetektoren: Fahrräder je Zählstelle
  (Anzahl_Fahrraeder_Zaehlstelle_1-Stunde)

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer`, tools/dauer_erkunden4/5.py):
- Ein Thing ist eine Zählstelle: eine Richtung an einem Knotenarm, beim Rad auch ein
  Querschnitt ohne Richtung. Kennung `assetID` aus Knotenpunkt (4 Ziffern), 9, Arm und Richtung
  (etwa 0248931); Schwerverkehr hängt an denselben Things wie Kfz. Lage als Punkt (Mittelpunkt
  des gezählten Abschnitts), Richtung als Text („Nordost nach Südwest“). Straßennamen gibt es
  nicht – die Zählkarte nimmt die nächste benannte Straße aus OpenStreetMap (strassen.py).
- Je Datastream eine Observation je Stunde in UTC (phenomenonTime „…T00:00:00Z/…T00:59:59Z“),
  Wert = Anzahl. Ganze Tage fehlen gelegentlich bei allen Stellen zugleich.
- Wie weit zurück: Kfz und Rad ab 29.08.2026, Schwerverkehr ab 28.02.2026. Ob ältere Stunden
  verschwinden, ist offen – deshalb hebt die Zählkarte die Stunden selbst auf: Monatsdateien
  `gedaechtnis/stunden_JJJJ-MM.csv.gz` (je Stelle, Gruppe und UTC-Tag die 24 Werte wie
  geliefert, leer = nicht geliefert), die der Workflow „Dauerzählstellen bauen“ im Release
  ablegt und vor dem nächsten Lauf zurückholt; dazu `gedaechtnis/strassen.json`.
- Werte können sich laut Quelle in den ersten Tagen noch ändern: jeder Abruf holt die letzten
  `nachladen_tage` erneut, in die Karte kommen nur Stunden, die mindestens `frisch_tage` alt sind.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import requests

from zaehlkarte import abruf
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import gedaechtnis
from zaehlkarte.dauer.gedaechtnis import Gedaechtnis, letzte_stunde
from zaehlkarte.dauer.gedaechtnis import lies as lies_gedaechtnis
from zaehlkarte.dauer.gedaechtnis import schreibe as schreibe_gedaechtnis
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc

UA = abruf.UA
ZEIT = re.compile(r"^(\d{4}-\d{2}-\d{2})T(\d{2}):00:00(?:\.0+)?Z/\1T\2:59:59(?:\.\d+)?Z$")
# „… bezüglich Zählstelle 0248 auf dem Richtungsarm Nordost von Nordost nach Südwest“
ARM = re.compile(r"Richtungsarm (\S+)")


@dataclass
class Bericht:
    datastreams: Counter = field(default_factory=Counter)
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    stunden: Counter = field(default_factory=Counter)  # je Gruppe in der Karte
    frisch: int = 0  # Stunden jünger als `frisch_tage` (aufgehoben, noch nicht in der Karte)
    monate: list[str] = field(default_factory=list)
    strassen: Counter = field(default_factory=Counter)

    def zeilen(self) -> list[str]:
        z = [", ".join(f"{g}: {n} Datastreams" for g, n in self.datastreams.items())
             + f"; {self.stellen} Zählstellen",
             "Stunden in der Karte: " + ", ".join(f"{g} {n}" for g, n in self.stunden.items())
             + f"; noch nicht übernommen (jünger als frisch_tage): {self.frisch}",
             f"Gedächtnis: {len(self.monate)} Monate ({self.monate[0] if self.monate else '–'} "
             f"bis {self.monate[-1] if self.monate else '–'})"]
        if self.strassen:
            z.append(f"Straßennamen aus OSM: {self.strassen['osm']}, nach Kennung benannt: "
                     f"{self.strassen['kennung']}")
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage[:10])}")
        return z


# ---------------------------------------------------------------- Abruf


def _sitzung() -> requests.Session:
    s = requests.Session()
    s.headers.update(UA)
    return s


def _json(sitzung: requests.Session, url: str, versuche: int = 4) -> dict:
    for i in range(versuche):
        try:
            r = abruf.hole(url, sitzung=sitzung, timeout=180, status_pruefen=False)
            if r.status_code < 500:
                r.raise_for_status()
                return r.json()
        except (requests.ConnectionError, requests.Timeout):
            if i == versuche - 1:
                raise
        time.sleep(5 * (i + 1))
    r.raise_for_status()
    return r.json()


def _url(basis: str, pfad: str, **params: str) -> str:
    return f"{basis}/{pfad}?" + urllib.parse.urlencode(params, safe="$(),;'/=:",
                                                       quote_via=urllib.parse.quote)


def _filter(q: dict, layer: str) -> str:
    return f"properties/serviceName eq '{q['dienst']}' and properties/layerName eq '{layer}'"


def datastreams(q: dict, sitzung: requests.Session) -> dict[str, list[dict]]:
    """Je Gruppe alle Datastreams des Layers mit Thing und Location (wie geliefert)."""
    out: dict[str, list[dict]] = {}
    for gruppe, layer in q["layer"].items():
        url = _url(q["api"], "Datastreams", **{
            "$filter": _filter(q, layer), "$top": "500",
            "$select": "id,name,properties,phenomenonTime",
            "$expand": "Thing($select=id,name,description,properties;"
                       "$expand=Locations($select=id,name,description,location))"})
        werte: list[dict] = []
        while url:
            d = _json(sitzung, url)
            werte += d.get("value", [])
            url = d.get("@iot.nextLink")
        out[gruppe] = werte
    return out


def _kennung(ds: dict) -> str | None:
    t = ds.get("Thing") or {}
    return (t.get("properties") or {}).get("assetID") or t.get("name")


def beobachtungen(q: dict, sitzung: requests.Session, gruppe: str, seit: datetime | None,
                  ids: set[int] | None = None) -> dict[int, list[tuple[str, object]]]:
    """Observations eines Layers ab `seit` (UTC, None = alle) -> {Datastream: [(Zeit, Wert)]}.

    Seitenweise je `je_seite` Datastreams mit verschachteltem $expand; ist eine Reihe länger als
    eine Seite, folgt der Abruf ihrem eigenen nextLink. `ids`: nur diese Datastreams (einzeln)."""
    innen = "$select=phenomenonTime,result;$orderby=phenomenonTime asc;$top=10000"
    if seit is not None:
        innen += f";$filter=phenomenonTime ge {seit.strftime('%Y-%m-%dT%H:%M:%SZ')}"
    out: dict[int, list[tuple[str, object]]] = {}

    def nimm(ds: dict) -> None:
        reihe = out.setdefault(ds["@iot.id"], [])
        reihe += [(o.get("phenomenonTime", ""), o.get("result"))
                  for o in ds.get("Observations", [])]
        weiter = ds.get("Observations@iot.nextLink")
        while weiter:
            d = _json(sitzung, weiter)
            reihe += [(o.get("phenomenonTime", ""), o.get("result")) for o in d.get("value", [])]
            weiter = d.get("@iot.nextLink")

    if ids is not None:
        for i in sorted(ids):
            nimm(_json(sitzung, _url(q["api"], f"Datastreams({i})", **{
                "$select": "id", "$expand": f"Observations({innen})"})))
        return out
    url = _url(q["api"], "Datastreams", **{
        "$filter": _filter(q, q["layer"][gruppe]), "$select": "id",
        "$top": str(q.get("je_seite", 10 if seit is None else 40)),
        "$expand": f"Observations({innen})"})
    while url:
        d = _json(sitzung, url)
        for ds in d.get("value", []):
            nimm(ds)
        url = d.get("@iot.nextLink")
    return out


# ---------------------------------------------------------------- Gedächtnis


def uebernimm(g: Gedaechtnis, gruppe: str, stelle: str,
              obs: list[tuple[str, object]]) -> tuple[int, int]:
    """Observations in das Gedächtnis (neue Werte ersetzen alte derselben Stunde).
    -> (übernommen, verworfen: Zeit nicht als volle Stunde oder Wert keine Anzahl)."""
    ok = weg = 0
    for zeit, wert in obs:
        m = ZEIT.match(zeit or "")
        if not m or not isinstance(wert, int) or isinstance(wert, bool) or wert < 0:
            weg += 1
            continue
        g.setdefault((stelle, gruppe, m[1]), [None] * 24)[int(m[2])] = wert
        ok += 1
    return ok, weg


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Datastreams (Stellen) und Stundenwerte holen, ins Gedächtnis übernehmen, Straßennamen
    für neue Stellen aus OSM ergänzen."""
    ordner = pfade.roh / q["code"]
    gordner = ordner / "gedaechtnis"
    gordner.mkdir(parents=True, exist_ok=True)
    sitzung = _sitzung()
    jetzt = datetime.now(UTC).replace(microsecond=0)
    ds = datastreams(q, sitzung)
    (ordner / "stellen.json").write_text(json.dumps(
        {"abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "datastreams": ds},
        ensure_ascii=False, indent=1), encoding="utf-8")
    g = lies_gedaechtnis(gordner)
    bekannt = {(s, gr) for s, gr, _ in g}
    letzte = letzte_stunde(g)
    seit = letzte - timedelta(days=int(q.get("nachladen_tage", 14))) if letzte else None
    log, neu_ok, neu_weg = [], 0, 0
    for gruppe in q["layer"]:
        kennung = {d["@iot.id"]: _kennung(d) for d in ds[gruppe]}
        fehlend = {i for i, k in kennung.items() if k and (k, gruppe) not in bekannt}
        teile = [beobachtungen(q, sitzung, gruppe, seit)]
        if seit is not None and fehlend:  # neue Stellen: ganze Reihe
            teile.append(beobachtungen(q, sitzung, gruppe, None, ids=fehlend))
        for teil in teile:
            for i, obs in teil.items():
                if kennung.get(i):
                    a, b = uebernimm(g, gruppe, kennung[i], obs)
                    neu_ok, neu_weg = neu_ok + a, neu_weg + b
    geaendert = schreibe_gedaechtnis(gordner, g)
    log.append(f"{q['code']}: {sum(len(v) for v in ds.values())} Datastreams, {neu_ok} Stunden "
               f"geholt ab {seit.isoformat() if seit else 'Beginn'} ({neu_weg} verworfen), "
               f"Gedächtnis geändert: {', '.join(geaendert) or 'nichts'}")
    log += _strassen(q, pfade, ds, gordner)
    return log


def _punkte(ds: dict[str, list[dict]]) -> dict[str, tuple[float, float]]:
    punkte = {}
    for liste in ds.values():
        for d in liste:
            k = _kennung(d)
            locs = (d.get("Thing") or {}).get("Locations") or []
            geo = ((locs[0].get("location") or {}).get("geometry") or {}) if locs else {}
            if k and geo.get("type") == "Point":
                punkte[k] = (float(geo["coordinates"][0]), float(geo["coordinates"][1]))
    return punkte


def _strassen(q: dict, pfade: Pfade, ds: dict[str, list[dict]], gordner: Path) -> list[str]:
    """Straßennamen für Stellen ohne Eintrag in gedaechtnis/strassen.json – über Overpass
    (`overpass` in sources.yaml: Server in der Reihenfolge, in der sie versucht werden)."""
    from zaehlkarte.dauer.strassen import LIZENZ, naechste_strassen_overpass

    pfad = gordner / "strassen.json"
    alt = json.loads(pfad.read_text(encoding="utf-8")) if pfad.exists() else {}
    stellen = alt.get("stellen", {})
    fehlt = {k: p for k, p in _punkte(ds).items() if k not in stellen}
    if not fehlt or not q.get("overpass"):
        return []
    treffer, server = naechste_strassen_overpass(q["overpass"], fehlt)
    for k in fehlt:
        stellen[k] = treffer.get(k) or {"name": None}
    neu = {"lizenz": LIZENZ, "osm": server or alt.get("osm"),
           "stand": datetime.now(UTC).date().isoformat(), "stellen": dict(sorted(stellen.items()))}
    pfad.write_text(json.dumps(neu, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Straßennamen für {len(fehlt)} neue Stellen ({len(treffer)} gefunden)"]


# ---------------------------------------------------------------- Lesen


def _stellen(q: dict, ds: dict[str, list[dict]], namen: dict[str, dict],
             bericht: Bericht) -> list[Dauerstelle]:
    erste: dict[str, dict] = {}
    spuren: dict[str, list[str]] = defaultdict(list)
    for gruppe in q["layer"]:
        for d in ds.get(gruppe, []):
            k = _kennung(d)
            if not k:
                continue
            erste.setdefault(k, d)
            for z in (d.get("properties") or {}).get("zaehlfelder") or []:
                if f"Zählfeld {z}" not in spuren[k]:
                    spuren[k].append(f"Zählfeld {z}")
    punkte = _punkte(ds)
    # Ein Name je Arm: Kennung = Knotenpunkt (4), 9, Arm, Richtung – alle Stellen eines Arms
    # (beide Richtungen, Querschnitt) heißen nach dem Treffer, der seiner Straße am nächsten liegt.
    def arm_von(k: str) -> str:
        return k[:6] if len(k) == 7 and k.isdigit() and k[4] == "9" else k

    je_arm: dict[str, tuple[str, float]] = {}
    for k in erste:
        n = namen.get(k) or {}
        if n.get("name"):
            alt = je_arm.get(arm_von(k))
            if alt is None or n.get("abstand_m", 1e9) < alt[1]:
                je_arm[arm_von(k)] = (n["name"], n.get("abstand_m", 1e9))
    # Knotenpunkt -> Straßennamen seiner Arme (für „Knotenpunkt mit …“)
    je_knoten: dict[str, set[str]] = defaultdict(set)
    for arm, (name, _) in je_arm.items():
        je_knoten[arm[:4]].add(name)
    out = []
    for k, d in sorted(erste.items()):
        if k not in punkte:
            bericht.ohne_lage.append(k)
            continue
        thing = d.get("Thing") or {}
        locs = thing.get("Locations") or [{}]
        name = je_arm.get(arm_von(k), (None, 0))[0]
        bericht.strassen["osm" if name else "kennung"] += 1
        arm = ARM.search(locs[0].get("description") or "")
        arm = arm[1] if arm and arm[1] != "Zählquerschnitt" else None
        andere = sorted(je_knoten.get(k[:4], set()) - {name})
        if arm:
            abschnitt = (f"Knotenpunkt mit {' / '.join(andere)}, Arm {arm}" if andere
                         else f"Knotenpunkt {k[:4]}, Arm {arm}")
        else:
            abschnitt = "Querschnitt"
        richtung = ((thing.get("properties") or {}).get("richtung") or "").strip()
        richtung = (f"von {richtung}" if richtung and richtung != "Keine Richtung"
                    else "ohne Richtung (Querschnitt)")
        lon, lat = punkte[k]
        out.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=name or f"Zählstelle {k}", abschnitt=abschnitt,
            richtung=richtung, lon=round(lon, 6), lat=round(lat, 6), land=q["land"],
            fahrstreifen=spuren[k], hinweise=[]))
    bericht.stellen = len(out)
    return out


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    if not (ordner / "stellen.json").exists():
        raise ValueError(f"{q['code']}: keine Stammdaten in {ordner} – "
                         "erst `zaehlkarte dauer fetch`")
    meta = json.loads((ordner / "stellen.json").read_text(encoding="utf-8"))
    ds = meta["datastreams"]
    for gruppe in q["layer"]:
        bericht.datastreams[gruppe] = len(ds.get(gruppe, []))
    spfad = ordner / "gedaechtnis" / "strassen.json"
    namen = (json.loads(spfad.read_text(encoding="utf-8")).get("stellen", {})
             if spfad.exists() else {})
    stellen = _stellen(q, ds, namen, bericht)
    g = lies_gedaechtnis(ordner / "gedaechtnis")
    bericht.monate = sorted({tag[:7] for _, _, tag in g})
    abgerufen = datetime.fromisoformat(meta["abgerufen"].replace("Z", "+00:00"))
    grenze = np.datetime64((abgerufen - timedelta(days=int(q.get("frisch_tage", 7))))
                           .replace(tzinfo=None, minute=0, second=0), "h")
    idx = {s.kennung: i for i, s in enumerate(stellen)}
    gruppen = tuple(q["layer"])
    je: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for gruppe in gruppen:
        if (f := gedaechtnis.felder(g, gruppe, idx)) is not None:
            je[gruppe] = f
    if not je:
        raise ValueError(f"{q['code']}: Gedächtnis leer – erst `zaehlkarte dauer fetch`")
    zeiten = np.concatenate([t for _, t, _ in je.values()])
    zeiten = zeiten[zeiten < grenze]
    if not zeiten.size:
        raise ValueError(f"{q['code']}: keine Stunden vor {grenze}")
    von = (zeiten.min().astype(datetime) - timedelta(days=1)).date()
    bis = (zeiten.max().astype(datetime) + timedelta(days=1)).date()
    reihe = Messreihe.leer(q["code"], von, bis, stellen, gruppen)
    for gruppe, (s_, t_, w_) in je.items():
        alt = t_ < grenze
        bericht.frisch += int((~alt).sum())
        bericht.stunden[gruppe] = setze_utc(reihe, gruppe, s_[alt], t_[alt], w_[alt])
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle wie geliefert (UTC, in Ortszeit umgerechnet); "
                        f"die jüngsten {int(q.get('frisch_tage', 7))} Tage noch nicht übernommen")]
    return reihe
