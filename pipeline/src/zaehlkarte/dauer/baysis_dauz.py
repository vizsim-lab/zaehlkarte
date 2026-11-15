"""Bayern: Dauerzählstellen der Bayerischen Straßenbauverwaltung (BAYSIS) – Stundenwerte je
Fahrtrichtung für Kfz und Schwerverkehr, in der Karte nur die Zählstellen an Staats- und
Kreisstraßen (Wunsch der Projektleitung, 15.11.2026: keine Autobahnen und Bundesstraßen;
`strassenklassen` in der Quelldatei).

Freigabe: Die Projektleitung hat am 15.11.2026 entschieden, die Werte über die Schnittstelle zu
holen, über die die öffentliche Seite „Dauerzählstellen“ von BAYSIS sie lädt – die Mobilithek
(Angebot 798871611185745920, Zentralstelle für Verkehrsmanagement) nennt diese Seite als Zugang,
Nutzungsbedingungen GeoNutzV; eine dokumentierte Datei gibt es nicht. Beide Server haben keine
robots.txt (404).

Höflich abrufen: Der Server (auch das GIS-Portal) lehnt Folgen von Anfragen ab – nach fünf, sechs
Anfragen in rund einer Minute kommt „Connection refused“, drei bis vier Minuten lang
(Werkzeug-Branch `werkzeug/bw`, tools/bw_fl6.py und bw_fl7.py, zehn Sekunden Abstand). Deshalb eine
Anfrage nach der anderen, `pause` Sekunden dazwischen, nach einer Ablehnung eine, zwei, drei
Minuten warten, nach `abbruch` Ablehnungen in Folge für diesen Lauf aufhören, je Lauf höchstens
`budget_minuten` – was fehlt, holt der nächste Lauf (der Cache des Workflows hält die Monate). Und
so wenige Anfragen wie möglich: je Anfrage bis zu `block_monate` Monate, und eine Zählstelle wird
erst wieder gefragt, wenn BAYSIS neue Monate hat (`hole`).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/bw`, tools/bw_fl4.py bis bw_fl7.py):
- Liste und Lage der Zählstellen: ArcGIS-Ebene „dauerzaehlstellen“ des Diensts
  BAYSIS_Verkehrsdaten, Operation `find` je Straßenklasse (`liste` in der Quelldatei, `{klasse}`
  wird ersetzt): Attribute unter ihren Aliasnamen („Zählstellennummer“, „Straßenbezeichnung“,
  „Straßenklasse“, „Status“, „Abschnittsnummer“, „Station“) und der Punkt in WGS84 – die
  Operation `query` derselben Ebene liefert keine Geometrie. Zählstellen „geplant“ bleiben draußen.
- Werte: `POST <api>` mit JSON `{"zaehlstellennummer": "9639", "abfrageArt": …}`:
  `stammdaten` (Bezeichnung, Straße, Abschnitt, Station, `inRichtung`/`gegenRichtung`,
  Fahrstreifen, Gerätetyp, `lkW_Unterscheidung` 8+1 …; je Feld `{"wert": …}`) und
  `stundenwerte` mit `vonDatum`/`bisDatum` (JJJJ-MM-TT): je Stunde eine Zeile mit `datum`
  (TT.MM.JJJJ), `stunde` (01–24, Ende der Stunde in Ortszeit wie im BASt-Format: 01 = 0–1 Uhr),
  `kfZ_R1`, `kfZ_R2`, `lkW_R1`, `lkW_R2` und je Wert ein Prüfkennzeichen (`kfzKennR1` …) der BASt:
  „-“ korrekt, „u“ korrekt, aber unregelmäßig, „a“ Ausfall, „d“ fehlerhaft, „s“/„k“ Schätzwert,
  „z“ Zeitumstellung. `kfZ_GQ`/`lkW_GQ` sind die Summe beider Richtungen – nicht verwendet. Ein
  Jahr einer Zählstelle: 8.760 Zeilen, rund 10 MB, acht Sekunden (2025). Werte gibt es mindestens
  ab Juni 2022, für Juni 2019 keine (`ab` in der Quelldatei); die Verfügbarkeit der Seite nennt
  nur die jüngsten 45 Monate.
- In der Karte (wie die Landes-Dauerzählstellen Baden-Württembergs): je Fahrtrichtung eine Stelle
  (beide am selben Punkt; R1 = „Richtung <inRichtung>“, R2 = „Richtung <gegenRichtung>“). Eine
  Stunde zählt, wenn ihr Kennzeichen „-“ oder „u“ ist; sonst ist sie nicht gezählt. Gruppen: Kfz
  -> kfz; „LKW“ (in BAYSIS „SV“) -> sv bei Zählgeräten mit 8+1 Fahrzeugarten (Schwerverkehr laut
  Zählgerät), sonst lkw – nie ineinander umgerechnet.
- Zeitumstellung: Im Frühjahr steht 2–3 Uhr als Zeile mit „z“ da – die Stunde gibt es nicht
  (setze_lokal verwirft sie). Im Herbst steht 2–3 Uhr nur einmal da, mit „z“ – nicht gezählt, der
  Tag ist nicht vollständig.
- Rohdaten: je Zählstelle und Monat die Zeilen der Antwort, wie geliefert
  (`werte/<nr>/JJJJ-MM.json.gz`, ein Monat ohne Zeilen als leere Liste), die Stammdaten je
  Zählstelle (`stamm/<nr>.json`), die Listen je Straßenklasse (`liste_<klasse>.json`) und der
  Stand der Abrufe (`stand.json`: wann jede Zählstelle zuletzt gefragt wurde, wann ihre Stammdaten,
  der jüngste Tag mit Zeilen und der Lauf, der ihn gebracht hat).
"""

from __future__ import annotations

import gzip
import json
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_lokal

GUT = ("-", "u")  # Prüfkennzeichen gezählter Werte (BASt)
SPALTEN = {("kfz", 1): ("kfZ_R1", "kfzKennR1"), ("kfz", 2): ("kfZ_R2", "kfzKennR2"),
           ("lkw", 1): ("lkW_R1", "lkwKennR1"), ("lkw", 2): ("lkW_R2", "lkwKennR2")}
AKTIV = ("aktiv (in Betrieb)", "inaktiv (außer Betrieb)", "unbekannt")  # nicht „geplant“


@dataclass
class Bericht:
    zaehlstellen: int = 0
    richtungen: int = 0
    ohne_stamm: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)
    ohne_werte: list[str] = field(default_factory=list)
    monate: int = 0
    gelesen: int = 0
    unlesbar: int = 0
    kennzeichen: Counter = field(default_factory=Counter)
    stunden: Counter = field(default_factory=Counter)
    sommerzeit: int = 0
    lkw_klassen: Counter = field(default_factory=Counter)
    bis: str | None = None

    def zeilen(self) -> list[str]:
        z = [f"{self.zaehlstellen} Zählstellen, {self.richtungen} Richtungen in der Karte; "
             f"{self.monate} Monatsdateien, {self.gelesen} Stundenzeilen ({self.unlesbar} "
             f"unlesbar); Stunden in der Karte: "
             + ", ".join(f"{g} {n}" for g, n in sorted(self.stunden.items()))
             + f"; Zeilen um 2 Uhr am Tag der Sommerzeit verworfen: {self.sommerzeit}; "
               f"jüngster Tag {self.bis}",
             "Prüfkennzeichen (Werte): " + ", ".join(
                 f"{k!r} {n}" for k, n in self.kennzeichen.most_common()),
             "Fahrzeugarten (lkW_Unterscheidung): " + ", ".join(
                 f"{k} {n}" for k, n in self.lkw_klassen.most_common())]
        for name, liste in (("ohne Stammdaten", self.ohne_stamm), ("ohne Lage", self.ohne_lage),
                            ("ohne Werte", self.ohne_werte)):
            if liste:
                z.append(f"{name} (nicht in der Karte): {'; '.join(liste)}")
        return z


def _wert(feld) -> str:
    return str((feld or {}).get("wert") or "").strip() if isinstance(feld, dict) else ""


def monate(ab: str, bis: date) -> list[str]:
    """„2023-01“ bis zum Monat von `bis` -> ["2023-01", …]."""
    j, m = int(ab[:4]), int(ab[5:7])
    out = []
    while (j, m) <= (bis.year, bis.month):
        out.append(f"{j}-{m:02d}")
        j, m = (j + 1, 1) if m == 12 else (j, m + 1)
    return out


def _monatsende(monat: str) -> date:
    import calendar

    j, m = int(monat[:4]), int(monat[5:7])
    return date(j, m, calendar.monthrange(j, m)[1])


def bloecke(fehlend: list[str], hoechstens: int = 12) -> list[tuple[str, str]]:
    """Fehlende Monate (sortiert) -> zusammenhängende Abschnitte (erster, letzter Monat) mit
    höchstens `hoechstens` Monaten, der jüngste zuerst."""
    out: list[list[str]] = []
    for m in sorted(fehlend):
        if out and len(out[-1]) < hoechstens and monate(out[-1][-1], _monatsende(m))[1:2] == [m]:
            out[-1].append(m)
        else:
            out.append([m])
    return [(b[0], b[-1]) for b in reversed(out)]


def zeilen_je_monat(zeilen: list[dict]) -> dict[str, list[dict]]:
    """Zeilen einer Antwort -> {„JJJJ-MM“: Zeilen}, nach dem Datum der Zeile (TT.MM.JJJJ)."""
    out: dict[str, list[dict]] = defaultdict(list)
    for z in zeilen:
        d = _wert(z.get("datum"))
        if len(d) == 10:
            out[f"{d[6:10]}-{d[3:5]}"].append(z)
    return out


def _schreibe_json_gz(pfad: Path, daten) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp = pfad.with_suffix(".teil")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False, separators=(",", ":"))
    tmp.replace(pfad)


def _lies_json_gz(pfad: Path):
    with gzip.open(pfad, "rt", encoding="utf-8") as f:
        return json.load(f)


class Abbruch(Exception):
    """Der Server lehnt zu oft ab oder das Zeitbudget ist aufgebraucht."""


class Abrufer:
    """Anfragen an BAYSIS: eine nach der anderen, mit Pause; Ablehnungen (Verbindung abgelehnt,
    Zeitüberschreitung, 5xx) mit wachsender Wartezeit wiederholt; nach `abbruch` Ablehnungen in
    Folge oder nach dem Zeitbudget: Abbruch für diesen Lauf."""

    def __init__(self, q: dict, schlafe=time.sleep, uhr=time.monotonic):
        self.q, self.schlafe, self.uhr = q, schlafe, uhr
        self.pause = float(q.get("pause", 15))
        self.abbruch = int(q.get("abbruch", 4))
        self.ende = uhr() + 60 * float(q.get("budget_minuten", 40))
        self.anfragen = 0
        self.ablehnungen = 0
        self.bytes = 0  # Größe der Antworten (entpackt)
        self.kodierung: Counter = Counter()  # Content-Encoding der Antworten (gzip oder ohne)

    def json(self, url: str, nutzlast: dict | None = None, timeout: float = 300):
        import requests

        from zaehlkarte import abruf

        folge = 0
        while True:
            if self.uhr() > self.ende:
                raise Abbruch("Zeitbudget aufgebraucht")
            try:
                if nutzlast is None:
                    r = abruf.hole(url, timeout=timeout)
                else:
                    r = abruf.hole(url, daten=json.dumps(nutzlast, ensure_ascii=False).encode(),
                                   kopf={"Content-Type": "application/json",
                                         "Accept": "application/json"}, timeout=timeout)
                self.anfragen += 1
                self.bytes += len(r.content)
                self.kodierung[r.headers.get("Content-Encoding") or "ohne"] += 1
                self.schlafe(self.pause)
                return r.json()
            except (requests.ConnectionError, requests.Timeout) as e:
                fehler = e
            except requests.HTTPError as e:
                if e.response is None or e.response.status_code < 500:
                    raise
                fehler = e
            folge += 1
            self.ablehnungen += 1
            if folge >= self.abbruch:
                raise Abbruch(f"{folge} Ablehnungen in Folge: {fehler!r}"[:200])
            self.schlafe(60 * folge)


def _attribute(a: dict) -> dict:
    """Attribute einer `find`-Antwort unter ihren Aliasnamen („Station\\n“) -> bereinigt."""
    return {" ".join(str(k).split()): (v.strip() if isinstance(v, str) else v)
            for k, v in a.items()}


def _stellen_der_liste(q: dict, listen: list[dict]) -> list[dict]:
    """`find`-Antworten -> Zählstellen der gewählten Straßenklassen, nicht „geplant“, je Nummer
    einmal: {nr, strasse, klasse, status, lon, lat}."""
    klassen = set(q["strassenklassen"])
    out: dict[str, dict] = {}
    for liste in listen:
        for r in liste.get("results") or []:
            a = _attribute(r.get("attributes") or {})
            nr = str(a.get("Zählstellennummer") or "").strip()
            if not nr or a.get("Straßenklasse") not in klassen or a.get("Status") not in AKTIV:
                continue
            g = r.get("geometry") or {}
            out[nr] = {"nr": nr, "strasse": a.get("Straßenbezeichnung"),
                       "klasse": a.get("Straßenklasse"), "status": a.get("Status"),
                       "lon": g.get("x"), "lat": g.get("y")}
    return [out[nr] for nr in sorted(out)]


def _lies_listen(ordner: Path, q: dict) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for k in q["strassenklassen"]
            if (p := ordner / f"liste_{k}.json").exists()]


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _monat(tag: date) -> str:
    return f"{tag.year}-{tag.month:02d}"


def juengster_tag(ordner: Path) -> date | None:
    """Jüngster Tag mit einer Zeile in den Monatsdateien einer Zählstelle (`werte/<nr>/`)."""
    for p in sorted(ordner.glob("*.json.gz"), reverse=True):
        tage = []
        for z in _lies_json_gz(p):
            d = _wert(z.get("datum"))
            try:
                tage.append(date(int(d[6:10]), int(d[3:5]), int(d[0:2])))
            except (ValueError, IndexError):
                continue
        if tage:
            return max(tage)
    return None


def start_der_frage(q: dict, ziel: list[str], bis: date | None) -> str:
    """Erster Monat, den eine Zählstelle neu gefragt wird: der Monat nach ihrer jüngsten Zeile
    (der Monat der jüngsten Zeile, wenn er nicht zu Ende ist), höchstens `block_monate` vor dem
    laufenden Monat; ohne Zeilen die jüngsten `block_monate`. Kann nach dem laufenden Monat liegen
    (nichts Neues zu erwarten). Die Monate davor, die fehlen, sind Lücken."""
    blk = int(q.get("block_monate", 12))
    start = _monat(bis + timedelta(days=1)) if bis else ziel[0]
    return max(start, ziel[max(0, len(ziel) - blk)])


def _lies_stand(ordner: Path) -> dict:
    p = ordner / "stand.json"
    st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {"neuester_tag": st.get("neuester_tag"), "seit": st.get("seit"),
            "gefragt": dict(st.get("gefragt") or {}), "stamm": dict(st.get("stamm") or {})}


def _schreibe_stand(ordner: Path, stand: dict) -> None:
    tmp = ordner / "stand.teil"
    tmp.write_text(json.dumps(stand, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                   encoding="utf-8")
    tmp.replace(ordner / "stand.json")


def hole(q: dict, pfade: Pfade, *, abrufer: Abrufer | None = None,
         jetzt: datetime | None = None) -> list[str]:
    """Ein Lauf fragt, in dieser Reihenfolge, bis das Zeitbudget aufgebraucht ist:
    1. die Listen je Straßenklasse;
    2. Probe: unter den Zählstellen nahe am jüngsten Tag (höchstens `rueckstand_tage` dahinter)
       die, die am längsten nicht gefragt wurde – ihre Monate ab dem Tag nach ihrer jüngsten
       Zeile. Hat BAYSIS neue Monate veröffentlicht (die Werte erscheinen mit rund sechs Wochen
       Verzug), zeigt sie das;
    3. fehlende Stammdaten und neue Zählstellen (die jüngsten `block_monate` Monate);
    4. Zählstellen, die mehr als `rueckstand_tage` hinter dem jüngsten Tag liegen und seit dem
       Lauf, der ihn gebracht hat, nicht gefragt wurden – nach einer Veröffentlichung alle, je
       einmal;
    5. Lücken: ältere Monate ab `ab`, der jüngste Abschnitt zuerst;
    6. Zählstellen, die seit `nachladen_tage` nicht gefragt wurden (Sicherheitsnetz), und
       Stammdaten, die älter als `stamm_tage` sind.
    Stunden fragt er nur für Zählstellen, die BAYSIS kennt: Für zwei der Liste (9478, 9710) sind
    die Stammdaten leer (November 2026) – sie werden nur alle `stamm_tage` neu nachgesehen.
    Ein Lauf ohne neue Monate fragt so dreimal (zwei Listen, eine Probe). Alle Zeiten eines Laufs
    sind sein Beginn: Was ein Lauf fragt, gilt nach der Neuigkeit, die er findet, als gefragt.
    Eine Antwort, die nicht so aussieht wie erwartet (Fehlermeldung statt Liste, 4xx, kein JSON),
    ersetzt nichts im Cache; nach `fehler_abbruch` (5) solchen hört der Lauf auf."""
    import requests

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    a = abrufer or Abrufer(q)
    jetzt = jetzt or datetime.now(UTC)
    lauf = _iso(jetzt)
    log: list[str] = []
    fehler: list[str] = []
    versucht: set[str] = set()  # Stammdaten in diesem Lauf schon gefragt

    def fehlerhaft(text: str) -> None:
        fehler.append(text[:200])
        if len(fehler) >= int(q.get("fehler_abbruch", 5)):
            raise Abbruch(f"{len(fehler)} fehlerhafte Antworten")

    def frage(url: str, nutzlast: dict | None = None, timeout: float = 300):
        """Antwort oder None (fehlerhafte Antwort: gemerkt, weiter mit der nächsten Anfrage)."""
        try:
            return a.json(url, nutzlast, timeout=timeout)
        except (requests.HTTPError, ValueError) as e:
            was = f"{nutzlast['zaehlstellennummer']} {nutzlast['abfrageArt']}" if nutzlast else url
            fehlerhaft(f"{was}: {e!r}")
        return None

    try:
        for k in q["strassenklassen"]:  # Liste und Lage je Straßenklasse
            liste = frage(q["liste"].format(klasse=k), timeout=120)
            if isinstance(liste, dict) and isinstance(liste.get("results"), list) \
                    and liste["results"]:
                (ordner / f"liste_{k}.json").write_text(json.dumps(liste, ensure_ascii=False),
                                                         encoding="utf-8")
            else:
                log.append(f"{q['code']}: Liste {k} ohne Ergebnis – es bleibt die alte")
                if liste is not None:
                    fehlerhaft(f"Liste {k}: {str(liste)[:150]}")
    except Abbruch as e:
        return [*log, f"{q['code']}: Abruf abgebrochen ({e}) – es bleibt der Stand im Cache"]
    stellen = [s["nr"] for s in _stellen_der_liste(q, _lies_listen(ordner, q))]
    stand = _lies_stand(ordner)
    gefragt = stand["gefragt"]
    ziel = monate(q["ab"], jetzt.date())
    blk = int(q.get("block_monate", 12))
    rueck = timedelta(days=int(q.get("rueckstand_tage", 14)))
    bis = {nr: juengster_tag(ordner / "werte" / nr) for nr in stellen}
    n: Counter = Counter()

    def merke_neuesten() -> None:
        neu = max((b for b in bis.values() if b), default=None)
        if neu and (stand["neuester_tag"] is None or neu.isoformat() > stand["neuester_tag"]):
            stand["neuester_tag"], stand["seit"] = neu.isoformat(), lauf

    def stammdaten(nr: str) -> None:
        versucht.add(nr)
        d = frage(q["api"], {"zaehlstellennummer": nr, "abfrageArt": "stammdaten"})
        if not isinstance(d, list) or not all(isinstance(x, dict) for x in d):
            if d is not None:
                fehlerhaft(f"{nr} stammdaten: keine Liste ({str(d)[:120]})")
            return
        p = ordner / "stamm" / f"{nr}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        stand["stamm"][nr] = lauf
        n["stammdaten"] += 1
        _schreibe_stand(ordner, stand)

    def stunden(nr: str, von: str, bis_monat: str, art: str) -> bool:
        zeilen = frage(q["api"], {"zaehlstellennummer": nr, "abfrageArt": "stundenwerte",
                                  "vonDatum": f"{von}-01",
                                  "bisDatum": _monatsende(bis_monat).isoformat()}, timeout=600)
        if not isinstance(zeilen, list) or not all(isinstance(z, dict) for z in zeilen):
            if zeilen is not None:
                fehlerhaft(f"{nr} stundenwerte {von}–{bis_monat}: keine Liste "
                           f"({str(zeilen)[:120]})")
            return False
        je_monat = zeilen_je_monat(zeilen)
        for m in monate(von, _monatsende(bis_monat)):
            _schreibe_json_gz(ordner / "werte" / nr / f"{m}.json.gz", je_monat.get(m, []))
            n["monate"] += 1
            n["monate_leer"] += not je_monat.get(m)
        n[art] += 1
        bis[nr] = juengster_tag(ordner / "werte" / nr)
        merke_neuesten()
        _schreibe_stand(ordner, stand)
        return True

    def juengste_fragen(nr: str, art: str) -> None:
        start = start_der_frage(q, ziel, bis[nr])
        if start > ziel[-1] or stunden(nr, start, ziel[-1], art):  # sonst: der nächste Lauf
            gefragt[nr] = lauf
            _schreibe_stand(ordner, stand)

    def bekannt(nr: str) -> bool:  # Stammdaten da und nicht leer
        try:
            return bool(json.loads((ordner / "stamm" / f"{nr}.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return False

    def luecken() -> list[tuple[str, str, str]]:
        out = []
        for nr in filter(bekannt, stellen):
            start = start_der_frage(q, ziel, bis[nr])
            da = {p.name[:7] for p in (ordner / "werte" / nr).glob("*.json.gz")}
            out += [(von, bm, nr) for von, bm in bloecke(
                [m for m in ziel if m < start and m not in da], blk)]
        out.sort(key=lambda x: x[2])  # stabil: bei gleichen Monaten nach der Nummer
        return sorted(out, key=lambda x: (x[1], x[0]), reverse=True)

    merke_neuesten()
    status = "vollständig"
    try:
        neu = max((b for b in bis.values() if b), default=None)
        nah = [nr for nr in stellen if nr in gefragt and bis[nr] and bis[nr] >= neu - rueck]
        if nah:  # 2. Probe
            juengste_fragen(min(nah, key=lambda nr: (gefragt[nr], nr)), "probe")
        for nr in stellen:  # 3. fehlende Stammdaten, neue Zählstellen
            if not (ordner / "stamm" / f"{nr}.json").exists():
                stammdaten(nr)
            if nr not in gefragt and bekannt(nr):
                juengste_fragen(nr, "neu")
        bekannte = [nr for nr in stellen if nr in gefragt and bekannt(nr)]

        def zurueck(nr: str) -> bool:
            t = stand["neuester_tag"]
            return (t is not None and gefragt[nr] < (stand["seit"] or "")
                    and (bis[nr] is None or bis[nr] < date.fromisoformat(t) - rueck))

        for nr in sorted(filter(zurueck, bekannte), key=lambda nr: (gefragt[nr], nr)):  # 4.
            juengste_fragen(nr, "nachgeladen")
        for von, bm, nr in luecken():  # 5.
            stunden(nr, von, bm, "luecken")
        grenze = _iso(jetzt - timedelta(days=float(q.get("nachladen_tage", 35))))
        for nr in sorted((nr for nr in bekannte if gefragt[nr] < grenze),
                         key=lambda nr: (gefragt[nr], nr)):  # 6.
            juengste_fragen(nr, "sicherheitsnetz")
        grenze = _iso(jetzt - timedelta(days=float(q.get("stamm_tage", 91))))
        for nr in sorted((nr for nr in stellen if stand["stamm"].get(nr, "") < grenze
                          and nr not in versucht), key=lambda nr: (stand["stamm"].get(nr, ""), nr)):
            stammdaten(nr)
    except Abbruch as e:
        status = f"abgebrochen ({e}) – der nächste Lauf holt den Rest"
    offen = len(luecken())
    _schreibe_stand(ordner, stand)
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": lauf, "stellen": len(stellen), **dict(sorted(n.items())),
        "anfragen": a.anfragen, "ablehnungen": a.ablehnungen,
        "megabyte": round(a.bytes / 1e6, 1), "kodierung": dict(a.kodierung),
        "neuester_tag": stand["neuester_tag"], "offene_abschnitte": offen,
        "fehler": fehler, "status": status}, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    teile = ", ".join(f"{k} {v}" for k, v in sorted(n.items()))
    log += [f"{q['code']}: fehlerhafte Antwort – {f}" for f in fehler]
    return [*log, f"{q['code']}: {len(stellen)} Zählstellen; {teile or 'nichts Neues gefragt'}; "
            f"{a.anfragen} Anfragen ({a.bytes / 1e6:.0f} MB), {a.ablehnungen} Ablehnungen; "
            f"jüngster Tag {stand['neuester_tag']}; offen {offen} Abschnitte älterer Monate; "
            f"{status}"]


def _zeilen_als_felder(zeilen: list[dict], bericht: Bericht) -> dict[tuple[str, int], tuple]:
    """Stundenzeilen einer Zählstelle -> je (Gruppe der Quelle, Richtung) die Felder (Tag als
    Tage seit 1970, Stunde 0–23, Wert mit -1 = nicht gezählt)."""
    epoche = date(1970, 1, 1).toordinal()
    t_, h_ = [], []
    w_: dict[tuple[str, int], list[int]] = {k: [] for k in SPALTEN}
    for z in zeilen:
        bericht.gelesen += 1
        d, h = _wert(z.get("datum")), _wert(z.get("stunde"))
        try:
            tag = date(int(d[6:10]), int(d[3:5]), int(d[0:2])).toordinal() - epoche
            stunde = int(h) - 1
            if not 0 <= stunde <= 23:
                raise ValueError(h)
        except (ValueError, IndexError):
            bericht.unlesbar += 1
            continue
        t_.append(tag)
        h_.append(stunde)
        for k, (spalte, kenn) in SPALTEN.items():
            kz = _wert(z.get(kenn))
            bericht.kennzeichen[kz] += 1
            w = _wert(z.get(spalte))
            w_[k].append(int(w) if kz in GUT and w.isdigit() else -1)
    tage = np.array(t_, dtype=np.int64).astype("datetime64[D]")
    stunden = np.array(h_, dtype=np.int64)
    return {k: (tage, stunden, np.array(v, dtype=np.int64)) for k, v in w_.items()}


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    listen = _lies_listen(ordner, q)
    if not listen:
        raise ValueError(f"{q['code']}: keine Liste in {ordner} – erst `zaehlkarte dauer fetch`")
    stamm: dict[str, dict] = {}
    lage: dict[str, tuple[float, float]] = {}
    for s in _stellen_der_liste(q, listen):
        nr = s["nr"]
        p = ordner / "stamm" / f"{nr}.json"
        d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        if not isinstance(d, list) or not d or not isinstance(d[0], dict):
            bericht.ohne_stamm.append(f"{nr} ({s.get('strasse')})")
            continue
        stamm[nr] = {k: _wert(v) for k, v in d[0].items()}
        if isinstance(s["lon"], int | float) and isinstance(s["lat"], int | float):
            lage[nr] = (float(s["lon"]), float(s["lat"]))
    stellen: list[Dauerstelle] = []
    index: dict[tuple[str, int], int] = {}
    gruppe_lkw: dict[str, str] = {}
    for nr in sorted(stamm):
        s = stamm[nr]
        name = " ".join(x for x in (s.get("strasse"), s.get("zaehlstellenbezeichnug")) if x)
        if nr not in lage:
            bericht.ohne_lage.append(f"{name} ({nr})")
            continue
        lon, lat = lage[nr]
        klassen = s.get("lkW_Unterscheidung") or "?"
        bericht.lkw_klassen[klassen] += 1
        gruppe_lkw[nr] = "sv" if klassen == "8+1" else "lkw"
        for r, ziel in ((1, s.get("inRichtung")), (2, s.get("gegenRichtung"))):
            index[(nr, r)] = len(stellen)
            stellen.append(Dauerstelle(
                quelle=q["code"], kennung=f"{nr}-{r}", name=name, abschnitt=None,
                richtung=f"Richtung {ziel}" if ziel else None,
                lon=round(lon, 6), lat=round(lat, 6), land=q["land"]))
    nummern = sorted({nr for nr, _ in index})
    bericht.zaehlstellen, bericht.richtungen = len(nummern), len(stellen)
    if not stellen:
        raise ValueError(f"{q['code']}: keine Zählstelle mit Stammdaten und Lage")
    dateien = {nr: sorted((ordner / "werte" / nr).glob("*.json.gz")) for nr in nummern}
    alle = [p.name[:7] for ps in dateien.values() for p in ps]
    if not alle:
        raise ValueError(f"{q['code']}: keine Stundenwerte in {ordner / 'werte'}")
    von = date(int(min(alle)[:4]), int(min(alle)[5:7]), 1)
    gruppen = ("kfz", *sorted(set(gruppe_lkw.values())))
    reihe = Messreihe.leer(q["code"], von, _monatsende(max(alle)), stellen, gruppen)
    for nr in nummern:  # je Zählstelle lesen und setzen – nie alle Zeilen auf einmal im Speicher
        zeilen = [z for p in dateien[nr] for z in _lies_json_gz(p)]
        bericht.monate += len(dateien[nr])
        if not zeilen:
            bericht.ohne_werte.append(f"{stamm[nr].get('strasse')} {nr}")
            continue
        for (gruppe, r), (tage, stunden, werte) in _zeilen_als_felder(zeilen, bericht).items():
            g = "kfz" if gruppe == "kfz" else gruppe_lkw[nr]
            stelle = np.full(len(tage), index[(nr, r)], dtype=np.int64)
            n, verworfen = setze_lokal(reihe, g, stelle, tage, stunden, werte, rueck="einfach")
            bericht.stunden[g] += n
            bericht.sommerzeit += verworfen
    for g in [g for g in reihe.werte if g != "kfz" and (reihe.werte[g] < 0).all()]:
        del reihe.werte[g]  # eine Gruppe ohne einen gezählten Wert (etwa nur ohne Werte)
    kuerze(reihe)
    bericht.bis = reihe.tag(reihe.tage - 1).isoformat()
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Fahrtrichtung laut BAYSIS (nur Werte mit den "
                        "Prüfkennzeichen „-“ und „u“)")]
    return reihe
