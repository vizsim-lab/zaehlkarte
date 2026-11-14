"""Düsseldorf: Dauerzählstellen Radverkehr der Landeshauptstadt – Stundenwerte je Zählstelle (bis
2021 je Richtung eine Datei) als „Wetterabhängige Jahresübersicht“, eine CSV je Zählstelle und
Jahr, über Open.NRW (Katalog der Stadt).

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer`, tools/rad_erkunden15–16.py):
- Je Jahr ein Paket `wetterabhangige-jahresubersicht-der-dauerzahlstellen-radverkehr-JJJJ-d`;
  ab 2020 dl-de/by-2-0 – die Lizenz steht je Ressource (2020 zwei Koblenzer Dateien
  geschlossen), bis 2019 „Andere geschlossene Lizenz“. Ein Paket für 2022 gibt es nicht.
- Formate je Jahr: 2020 `Zeit;Stunde;Anzahl;Wetter;…` („01.01.2020;00:00:00;2“), 2021 teils
  `datum;stunde;anzahl` (das Datum auch ohne Punkte: „1012021“), teils `Zeit;<Stelle>;Wetter;…`,
  ab 2023 `Zeit;<Stelle> IN;<Stelle> OUT;Symbol Wetter;…` („26-03-2023 01:00:00“). Zählwerte
  stehen vor der ersten Wetter-Spalte; Ortszeit; leere Zelle = nicht gezählt.
- Zuordnung Ressource -> Zählstelle über den Namen der Ressource (`muster` in sources.yaml); eine
  Stunde ist gezählt, wenn jede Datei und jede Spalte der Stelle im Jahr einen Wert hat.
- Summen anderer Stellen stehen unter `ohne` (Fleher Deich Rampe = Ost + West, Oberkasseler
  Brücke = OKB Nord + Süd, Koblenzer Straße = die drei Koblenzer Stellen). In einer Datei mit
  drei Wertespalten ist eine die Summe der beiden anderen (Fleher Deich, OKB Süd 2024): geprüft und
  weggelassen. 2021 ist „Koblenzer einwärts nach TLS“ eine Kopie von „vor TLS“ (`ohne_dateien`).
- Zeitumstellung: am Tag der Sommerzeit 2020/2021 steht 3 Uhr zweimal, einmal ganz leer (zählt
  nicht), ab 2023 fehlt 2 Uhr; am Rückstelltag steht 2 Uhr nur einmal (`rueck: einfach`).
- Lage: Standorte der Stadt (dl-de/zero-2-0), für neuere Stellen OpenStreetMap (`stellen`).
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from urllib.parse import unquote, urlparse

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

DATUM = re.compile(r"^(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})$")
DATUM_ZIFFERN = re.compile(r"^(\d{1,2})(\d{2})(\d{4})$")  # „1012021“ = 01.01.2021
ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
UHR = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


@dataclass
class Bericht:
    dateien: int = 0
    je_jahr: Counter = field(default_factory=Counter)
    nicht_zugeordnet: list[str] = field(default_factory=list)
    unlesbar: Counter = field(default_factory=Counter)  # je Datei: Zeilen ohne lesbare Zeit
    summenspalte: list[str] = field(default_factory=list)
    doppelt: int = 0
    ohne: list[str] = field(default_factory=list)
    ohne_lage: list[str] = field(default_factory=list)
    stellen: int = 0
    stunden: int = 0
    sommerzeit: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{self.dateien} Dateien ("
             + ", ".join(f"{j}: {n}" for j, n in sorted(self.je_jahr.items()))
             + f"); {self.stellen} Zählstellen; Stunden in der Karte: rad {self.stunden}; doppelte "
             f"Stunden mit Wert (nicht gezählt): {self.doppelt}; 2 Uhr am Tag der Sommerzeit "
             f"verworfen: {self.sommerzeit}"]
        if self.summenspalte:
            z.append("Summenspalte weggelassen: " + "; ".join(self.summenspalte))
        if any(self.unlesbar.values()):
            z.append("Zeilen ohne lesbare Zeit: "
                     + ", ".join(f"{k} {n}" for k, n in self.unlesbar.items() if n))
        if self.ohne:
            z.append("nicht in der Karte (sources.yaml `ohne`): "
                     + ", ".join(sorted(set(self.ohne))))
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(sorted(set(self.ohne_lage)))}")
        if self.nicht_zugeordnet:
            z.append(f"keiner Zählstelle zugeordnet: {', '.join(self.nicht_zugeordnet)}")
        return z


def norm(name: str) -> str:
    """Name einer Ressource -> Schlüssel zum Vergleich: ohne „ - Wetterabhängige …“, Jahr und
    IN/OUT, Umlaute ausgeschrieben, nur Buchstaben und Ziffern."""
    s = re.split(r"\s+-\s+wetterabh", name.strip().lower())[0]
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b20\d\d\b|\bin\b|\bout\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def zuordnung(q: dict, name: str) -> str | None:
    n = norm(name)
    for k, info in q["stellen"].items():
        if re.fullmatch(info["muster"], n):
            return k
    return None


def zeit(datum: str, uhr: str | None) -> datetime | None:
    """Ortszeit aus Datum (und Uhrzeit) in den Formaten der Jahre 2020–2025; nur volle Stunden."""
    teile = datum.strip().split()
    if uhr is None and len(teile) == 2:
        datum, uhr = teile
    datum = datum.strip()
    m = DATUM.match(datum) or DATUM_ZIFFERN.match(datum)
    if m:
        tag, monat, jahr = int(m[1]), int(m[2]), int(m[3])
    elif m := ISO.match(datum):
        jahr, monat, tag = int(m[1]), int(m[2]), int(m[3])
    else:
        return None
    u = UHR.match((uhr or "").strip())
    if not u or int(u[2]) or (u[3] and int(u[3])):
        return None
    try:
        return datetime(jahr, monat, tag, int(u[1]))
    except ValueError:
        return None


def text(roh: bytes) -> str:
    for kodierung in ("utf-8-sig", "cp1252"):
        try:
            return roh.decode(kodierung).replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError:
            continue
    return roh.decode("latin-1")


def lies_datei(t: str) -> tuple[list[str], dict[datetime, int], int, int, str | None]:
    """-> (Wertespalten, {Stunde: Summe der Spalten oder LEER}, unlesbare Zeilen, doppelte
    Stunden mit Wert, weggelassene Summenspalte). Zeilen, in denen jede Wertespalte leer ist,
    fehlen (Füllzeile am Tag der Sommerzeit)."""
    zz = [z for z in t.split("\n") if z.strip()]
    kopf = [k.strip() for k in zz[0].split(";")]
    stunde_extra = len(kopf) > 2 and kopf[1].lower() == "stunde"
    ende = next((i for i, k in enumerate(kopf) if "wetter" in k.lower()), len(kopf))
    spalten = list(range(2 if stunde_extra else 1, ende))
    zeilen, weg = [], 0
    for z in zz[1:]:
        f = z.split(";")
        t0 = zeit(f[0], f[1] if stunde_extra and len(f) > 1 else None)
        if t0 is None:
            weg += 1
            continue
        werte = [f[i].strip() if i < len(f) else "" for i in spalten]
        if not any(werte):
            continue
        zeilen.append((t0, werte))
    summe = None
    if len(spalten) >= 3:  # eine Spalte die Summe der anderen? (Fleher Deich, OKB Süd 2024)
        voll = [[int(v) for v in w] for _, w in zeilen if all(re.fullmatch(r"\d+", v) for v in w)]
        for j in range(len(spalten)):
            if len(voll) >= 24 and all(w[j] == sum(w) - w[j] for w in voll):
                summe = kopf[spalten[j]]
                spalten = spalten[:j] + spalten[j + 1:]
                zeilen = [(t0, w[:j] + w[j + 1:]) for t0, w in zeilen]
                break
    stunden: dict[datetime, int] = {}
    doppelt = 0
    for t0, werte in zeilen:
        w = sum(int(v) for v in werte) if all(re.fullmatch(r"\d+", v) for v in werte) else LEER
        if t0 in stunden:  # dieselbe Stunde zweimal mit Wert: nicht gezählt
            doppelt += 1
            stunden[t0] = LEER
            continue
        stunden[t0] = w
    return [kopf[i] for i in spalten], stunden, weg, doppelt, summe


def hole(q: dict, pfade: Pfade, pause: float = 60) -> list[str]:
    """Die Jahrespakete ab `ab_jahr` über die Katalog-API von Open.NRW suchen und die CSV-Dateien
    mit offener Lizenz holen – nur neue oder geänderte (der Server lehnt Abrufe oft ab: je Datei
    mehrere Versuche, sonst bleibt der letzte Stand)."""
    import requests

    from zaehlkarte.fetch import UA, lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    r = requests.get(q["api"], params={"q": q["suche"], "rows": 100}, headers=UA, timeout=120)
    r.raise_for_status()
    gewaehlt, geschlossen = {}, []
    for paket in r.json()["result"]["results"]:
        m = re.fullmatch(q["paket_muster"], paket["name"])
        if not m or int(m[1]) < q["ab_jahr"]:
            continue
        for res in paket.get("resources", []):
            url = res.get("url") or ""
            if not url.lower().endswith(".csv"):
                continue
            name = (res.get("name") or "").strip()
            if q["lizenz_ressource"] not in (res.get("license") or paket.get("license_id") or ""):
                geschlossen.append(f"{m[1]} {name.split(' - ')[0]}")
                continue
            datei = f"{m[1]}/{unquote(urlparse(url).path.rsplit('/', 1)[-1])}"
            gewaehlt[datei] = {"url": url, "name": name, "jahr": int(m[1])}
    if not gewaehlt:
        raise ValueError(f"{q['code']}: keine Datei mit offener Lizenz gefunden")
    abruf = ordner / "abruf.json"
    vorher = (json.loads(abruf.read_text(encoding="utf-8")).get("dateien", {})
              if abruf.exists() else {})
    offen = [d for d, info in sorted(gewaehlt.items())
             if vorher.get(d, {}).get("url") != info["url"] or not (ordner / d).exists()]
    neu, fehler = 0, {}
    # Der Server lehnt Abrufe zeitweise ab („Connection refused“): je Datei drei Versuche, danach
    # ein zweiter Durchgang für die gescheiterten nach einer Minute; sonst bleibt der letzte Stand
    for durchgang in range(2):
        if durchgang and offen:
            time.sleep(pause)
        for datei in offen:
            for versuch in range(3):
                try:
                    lade(gewaehlt[datei]["url"], ordner / datei)
                    neu += 1
                    fehler.pop(datei, None)
                    break
                except Exception as e:  # noqa: BLE001 – gezählt wird, was am Ende fehlt
                    fehler[datei] = repr(e)
                    time.sleep(pause / 12 * (versuch + 1))
        offen = list(fehler)
    fehler = [f"{d} ({e})" for d, e in fehler.items()]
    abruf.write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dateien": {k: v for k, v in sorted(gewaehlt.items()) if (ordner / k).exists()},
        "ohne_offene_lizenz": sorted(geschlossen), "fehler": fehler,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(gewaehlt)} Dateien mit offener Lizenz, {neu} neu geladen"
            + (f"; Fehler: {', '.join(fehler)}" if fehler else "")
            + f"; nicht übernommen (geschlossene Lizenz): {', '.join(geschlossen) or 'keine'}"]


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    abruf = ordner / "abruf.json"
    if not abruf.exists():
        raise ValueError(f"{q['code']}: keine Dateien in {ordner} – erst `zaehlkarte dauer fetch`")
    dateien = json.loads(abruf.read_text(encoding="utf-8"))["dateien"]
    ohne = q.get("ohne") or {}
    ohne_dateien = {int(j): set(v) for j, v in (q.get("ohne_dateien") or {}).items()}
    je = defaultdict(list)  # (Stelle, Jahr) -> [{Stunde: Wert}] je Datei
    for datei, info in sorted(dateien.items()):
        k = zuordnung(q, info["name"])
        if k is None:
            bericht.nicht_zugeordnet.append(f"{info['jahr']} {info['name'].split(' - ')[0]}")
            continue
        if k in ohne or k in ohne_dateien.get(info["jahr"], set()):
            bericht.ohne.append(k if k in ohne else f"{k} {info['jahr']}")
            continue
        if "lat" not in q["stellen"][k]:
            bericht.ohne_lage.append(k)
            continue
        _, stunden, weg, doppelt, summe = lies_datei(text((ordner / datei).read_bytes()))
        bericht.dateien += 1
        bericht.je_jahr[info["jahr"]] += 1
        bericht.unlesbar[datei] = weg
        bericht.doppelt += doppelt
        if summe:
            bericht.summenspalte.append(f"{info['jahr']} {k}: „{summe}“")
        je[(k, info["jahr"])].append(stunden)
    if not je:
        raise ValueError(f"{q['code']}: keine Datei einer Zählstelle mit Lage")
    schluessel = list(dict.fromkeys(k for k, _ in sorted(je)))
    idx = {k: i for i, k in enumerate(schluessel)}
    stellen = []
    for k in schluessel:
        info = q["stellen"][k]
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=k, name=info["name"], abschnitt=info.get("abschnitt"),
            richtung=None, lon=float(info["lon"]), lat=float(info["lat"]), land=q["land"],
            hinweise=list(info.get("hinweise") or [])))
    s_, t_, h_, w_ = [], [], [], []
    for (k, _), teile in je.items():
        for t0 in set().union(*teile):
            ws = [teil.get(t0, LEER) for teil in teile]
            s_.append(idx[k])
            t_.append(t0.date())
            h_.append(t0.hour)
            w_.append(LEER if min(ws) < 0 else sum(ws))
    t = np.array(t_, dtype="datetime64[D]")
    reihe = Messreihe.leer(q["code"], t.min().astype(date), t.max().astype(date), stellen, ("rad",))
    bericht.stunden, bericht.sommerzeit = setze_lokal(
        reihe, "rad", np.array(s_, dtype=np.int64), t, np.array(h_, dtype=np.int64),
        np.array(w_, dtype=np.int64), anzahl=1, rueck=q.get("rueck", "einfach"))
    bericht.stellen = len(stellen)
    bericht.unlesbar = Counter({k: n for k, n in bericht.unlesbar.items() if n})
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle, alle Richtungen zusammen, aus den "
                        "Jahresdateien der Stadt (ab 2020; 2022 nicht veröffentlicht)")]
    return reihe
