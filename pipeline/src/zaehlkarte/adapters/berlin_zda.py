"""Berlin: manuelle Knotenstrom- und Querschnittszählungen (ZDA-Dateien, zwei IFG-Lieferungen).

Archive und Lizenzen stehen in der Quelldatei (`lieferungen`, die neuere zuerst). Je Datei eine
Zählung; Werte je Richtung und Kategorie in 1-, 15- oder 60-Minuten-Intervallen.

Verortung, in dieser Reihenfolge:
1. `gps=` im Kopf (Dateien ab 2021) -> lage "gps"
2. Geokodier-Cache aus vizsim/berlin-traffic-counts_schulwege (Straßenkreuzung aus OSM) für die
   Fuß- und Radzählungen -> lage "geokodiert"
3. Ergänzung für die übrigen Zählungen (`pipeline/geokodierung/berlin_ergaenzung.csv`, derselbe
   Geocoder, Workflow „Berlin geokodieren“ – Liste von `zaehlkarte geokodier-liste`)
   -> lage "geokodiert"
4. sonst keine Lage; `build` überträgt sie von Zählungen derselben Zählstellen-Kennung, wenn die
   eindeutig an einem Ort liegen -> lage "uebertragen"

Doppelte Zählungen (Regeln aus dem Schulwege-Projekt): dieselbe Zählung in beiden Lieferungen
(2019) -> die neuere Lieferung gilt; „X“ und „X_24h“ -> die 24-Stunden-Fassung; gleicher Inhalt
unter zwei Schreibweisen der Kennung („Q-001022“/„Q0001022“) -> einmal.

Stundenwerte: Intervalle zählen zur Stunde ihres Beginns. Eine Stunde, die das Zählfenster nur
teilweise abdeckt (Fenster ab 6:30), ist None statt eines zu kleinen Werts. Eine Richtung, die
für eine Gruppe durchweg -1 hat, wurde dafür nicht gezählt und fällt aus der Summe (Hinweis an
der Zählung); fehlt sonst in einer Stunde ein Wert, ist die Stunde None.

Ströme und Arme: Jede Richtung der Datei („; 1 -> 3“) ist ein Strom von Arm 1 nach Arm 3, mit
denselben Stundenwerten je Gruppe wie in der Summe. Die Arme stehen im Kopf als
`armN=Name,Winkel,Kennzeichen` („arm2=Tempelhofer Ufer (W),650,1011“). Der Winkel ist in
Zehntelgrad gegen den Uhrzeigersinn ab Nord angegeben – nachgeprüft an den Armen mit
Himmelsrichtung im Namen: 2019–2025 liegen 98 % von 17.485 höchstens 45° neben ihr (Median 10°),
1990–2019 96 % von 10.280 (Median 15°); im Uhrzeigersinn gelesen wären es 40 %. In `arme` steht
er im Uhrzeigersinn ab Nord, vom Knoten weg (650 -> 295°); 0 ist Nord. Arme ohne Namen kommen nur
hinein, wenn ein Strom sie nennt; das Kennzeichen bleibt draußen (Bedeutung unbekannt).
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from zaehlkarte.adapters import berlin_bezeichnung as bez_
from zaehlkarte.adapters import kategorien, zda
from zaehlkarte.config import Pfade
from zaehlkarte.modell import GRUPPEN, Zaehlung

BBOX = (13.05, 52.33, 13.78, 52.69)  # grob Berlin; GPS außerhalb gilt als unbrauchbar
NAMEN = {"kfz": "Kfz", "sv": "Schwerverkehr", "rad": "Rad", "fuss": "Fuß", "kind": "Kinder"}


@dataclass
class Bericht:
    dateien: Counter = field(default_factory=Counter)
    ohne_gruppe: Counter = field(default_factory=Counter)
    doppelt: Counter = field(default_factory=Counter)
    lage: Counter = field(default_factory=Counter)

    def zeilen(self) -> list[str]:
        out = [f"{k}: {n} Dateien" for k, n in self.dateien.items()]
        out += [f"ohne Kfz/Rad/Fuß: {n} ({k})" for k, n in self.ohne_gruppe.items()]
        out += [f"doppelt – {k}: {n}" for k, n in self.doppelt.items()]
        out += [f"Lage {k}: {n}" for k, n in self.lage.items()]
        return out


def knoten_norm(knoten: str) -> str | None:
    """'K 10921', 'K0010921', 'Q-10051' -> 'K10921' / 'Q10051'."""
    m = re.match(r"\s*([A-Za-z])\s*-?\s*0*(\d+)", knoten or "")
    return f"{m.group(1).upper()}{int(m.group(2))}" if m else None


def name_norm(datei: str) -> str:
    """'Q-001001_20190313.zda', 'Q0001001_20190313.ZDA' -> 'Q1001_20190313'."""
    stamm = datei.rsplit(".", 1)[0]
    m = re.match(r"([A-Za-z])-?0*(\d+)(_.*)?$", stamm)
    return f"{m.group(1).upper()}{int(m.group(2))}{m.group(3) or ''}" if m else stamm.upper()


def parse_gps(text: str) -> tuple[float | None, float | None]:
    """'52.54172, 13.42288' -> (lon, lat); vertauschte Reihenfolge wird erkannt."""
    zahlen = re.findall(r"-?\d+(?:\.\d+)?", text or "")
    if len(zahlen) != 2:
        return None, None
    a, b = (float(x) for x in zahlen)
    for lon, lat in ((b, a), (a, b)):
        if BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]:
            return round(lon, 6), round(lat, 6)
    return None, None


def bemerkung(text: str) -> str | None:
    """Bemerkung ohne den Namen des Zählbüros („Durchführung der Erhebungen: …“)."""
    s = re.split(r"Durchf(?:ü|ue)hrung der Erhebung", text.replace("\\n", " ").replace("\\,", ","))
    s = re.sub(r"\s+", " ", s[0]).strip(" ;,.-")
    return s[:240] or None


def _stunden(z: zda.Zaehlung) -> tuple[list[int], set[int]]:
    """Beginn jedes Intervalls und die Stunden, die das Zählfenster ganz abdeckt."""
    beginne = z.intervall_beginne
    minuten: Counter = Counter()
    for b in beginne:
        minuten[b // 60] += z.intervall
    return beginne, {h for h, m in minuten.items() if m >= 60}


def _reihe(
    zeilen: list[list[int | None]], idx: list[int], beginne: list[int], voll: set[int],
    h0: int, h1: int,
) -> list[int | None] | None:
    """Stundenwerte einer Richtung für eine Gruppe (Spalten `idx`); None, wenn die Richtung die
    Gruppe nicht gezählt hat. Fehlt in einer Stunde ein Wert, ist die Stunde None."""
    if not zeilen or not any(zl[j] is not None for zl in zeilen for j in idx if j < len(zl)):
        return None
    summen: dict[int, int | None] = dict.fromkeys(voll, 0)
    for i, b in enumerate(beginne):
        h = b // 60
        if summen.get(h) is None:
            continue
        zl = zeilen[i] if i < len(zeilen) else []
        werte = [zl[j] if j < len(zl) else None for j in idx]
        summen[h] = None if any(v is None for v in werte) else summen[h] + sum(werte)
    return [summen.get(h) if h in voll else None for h in range(h0, h1 + 1)]


def stromreihen(
    z: zda.Zaehlung, sp: dict[str, list[int]]
) -> tuple[int | None, dict[str, dict[str, list[int | None]]]]:
    """(h0, {Richtung: {Gruppe: Stundenwerte ab h0}}) – je Richtung nur die Gruppen, die sie
    gezählt hat."""
    beginne, voll = _stunden(z)
    if not voll:
        return None, {}
    h0, h1 = min(voll), max(voll)
    out: dict[str, dict[str, list[int | None]]] = {}
    for richtung, zeilen in z.werte.items():
        if not zeilen:
            continue
        reihen = {g: _reihe(zeilen, idx, beginne, voll, h0, h1) for g, idx in sp.items()}
        out[richtung] = {g: r for g, r in reihen.items() if r is not None}
    return h0, out


def stundenreihen(
    z: zda.Zaehlung, sp: dict[str, list[int]]
) -> tuple[int | None, dict[str, list[int | None]], dict[str, int]]:
    """(h0, {Gruppe: Stundenwerte ab h0}, {Gruppe: Richtungen ohne Zählung}): die Summe der
    Ströme; eine Stunde ist None, wenn sie einem gezählten Strom fehlt."""
    h0, je_richtung = stromreihen(z, sp)
    if h0 is None:
        return None, {}, {}
    out: dict[str, list[int | None]] = {}
    ohne: dict[str, int] = {}
    for g in sp:
        reihen = [r[g] for r in je_richtung.values() if g in r]
        if not reihen:
            continue
        summe = [None if any(r[k] is None for r in reihen) else sum(r[k] for r in reihen)
                 for k in range(len(reihen[0]))]
        if any(v is not None for v in summe):
            out[g] = summe
            ohne[g] = len(je_richtung) - len(reihen)
    return h0, out, ohne


_ARM = re.compile(r"^(?P<name>.*?)(?:,\s*(?P<winkel>-?\d+)\s*,\s*\d+)?\s*$")
_STROM = re.compile(r"^(\d+)->(\d+)$")


def arme(kopf: dict[str, str], genannt: set[int] = frozenset()) -> list[dict]:
    """arm1..arm8 -> [{"nr", "name", "winkel"}], Winkel in Grad im Uhrzeigersinn ab Nord (aus
    Zehntelgrad gegen den Uhrzeigersinn); Arme ohne Namen nur, wenn ein Strom sie nennt."""
    out = []
    for nr in range(1, 9):
        if f"arm{nr}" not in kopf:
            continue
        m = _ARM.match(kopf[f"arm{nr}"].strip())
        name = re.sub(r"\s+", " ", m["name"]).strip() if m else ""
        if not name and nr not in genannt:
            continue
        winkel = round((3600 - int(m["winkel"])) % 3600 / 10, 1) if m and m["winkel"] else None
        out.append({"nr": nr, "name": name, "winkel": winkel})
    return out


def stroeme(je_richtung: dict[str, dict[str, list[int | None]]]) -> list[dict]:
    """{"1->3": {Gruppe: Werte}} -> [{"von": 1, "nach": 3, "stunden": {…}}] in der Reihenfolge
    von GRUPPEN; Richtungen ohne Arm-Nummern („; Nord“) und ohne Werte bleiben draußen."""
    out = []
    for richtung, reihen in je_richtung.items():
        m = _STROM.match(richtung)
        if not m or not reihen:
            continue
        out.append({"von": int(m[1]), "nach": int(m[2]),
                    "stunden": {g: reihen[g] for g in GRUPPEN if g in reihen}})
    return out


def lade_geokodierung(pfad: Path) -> dict[str, tuple[float, float, str]]:
    """Cache datei -> (lon, lat, methode); leere Zeilen = nicht geokodierbar."""
    if not pfad.exists():
        return {}
    out = {}
    with pfad.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["geo_lon"] and row["geo_lat"]:
                lon, lat = float(row["geo_lon"]), float(row["geo_lat"])
                out[row["datei"]] = (lon, lat, row["geo_methode"])
    return out


def lade_rohdatei_links(pfad: Path) -> dict[str, str]:
    """Liste der Rohdateien, die das Schulwege-Projekt veröffentlicht: datei -> 'f' | 'r'."""
    if not pfad.exists():
        return {}
    out: dict[str, str] = {}
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        art, _, datei = zeile.partition(" ")
        out.setdefault(datei, art)
    return out


def _zaehlung(z: zda.Zaehlung, quelle: dict, lieferung: dict, geo: dict, links: dict) -> Zaehlung:
    bez = re.sub(r"\s+", " ", z.kopf.get("bez", "").replace("\xa0", " ")).strip()
    knoten = knoten_norm(z.kopf.get("knoten", ""))
    sp = kategorien.spalten(z.kategorien)
    h0, stunden, ohne = stundenreihen(z, sp)
    _, je_richtung = stromreihen(z, sp)
    stroeme_ = stroeme(je_richtung)
    lon, lat = parse_gps(z.kopf.get("gps", ""))
    lage = "gps" if lon is not None else None
    if lon is None and z.datei in geo:
        lon, lat, _ = geo[z.datei]
        lage = "geokodiert"
    hinweise = [
        f"{NAMEN[g]}: {n} von {len(z.werte)} Richtungen nicht gezählt"
        for g, n in ohne.items()
        if n
    ]
    code = bez_.alter_postbezirk(bez)
    plz, _ = bez_.plz_und_bezirk(bez)
    vorlage = lieferung.get("rohdatei_url")
    if "rohdatei_url_liste" in lieferung:  # nur die Dateien, die es einzeln online gibt
        art = links.get(z.datei)
        vorlage = lieferung["rohdatei_url_liste"].get(art) if art else None
    return Zaehlung(
        quelle=quelle["code"],
        kennung=z.stamm,
        stelle_roh=knoten,
        name=bez_.kurzname(bez) or bez or z.stamm,
        typ=knoten[0] if knoten and knoten[0] in "KQ" else "",
        lon=lon,
        lat=lat,
        lage=lage,
        datum=z.datum,
        fenster=z.fenster,
        intervall=z.intervall,
        h0=h0,
        stunden={g: stunden[g] for g in GRUPPEN if g in stunden},
        land=quelle["land"],
        gebiet=("west" if len(code) <= 2 else "ost") if code else None,
        richtungen=len(z.werte),
        kategorien=",".join(z.kategorien),
        rohdatei=vorlage.format(datei=z.datei) if vorlage else None,
        lizenz=lieferung["code"],
        lieferung=lieferung["code"],
        bemerkung=bemerkung(z.kopf.get("bemerk", "")),
        hinweise=hinweise + z.hinweise[:3],
        arme=arme(z.kopf, {n for st in stroeme_ for n in (st["von"], st["nach"])}),
        stroeme=stroeme_,
        zusatz={
            "datei": z.datei,
            "bez": bez,
            "arme": bez_.strassen_aus_armen(z.kopf),
            "plz": plz,
            "ortsteil": bez_.ortsteil(bez),
        },
    )


def _fingerabdruck(z: zda.Zaehlung) -> tuple:
    werte = repr(sorted(z.werte.items())).encode()
    return knoten_norm(z.kopf.get("knoten", "")), z.datum, hashlib.sha1(werte).hexdigest()


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    """Alle Zählungen beider Lieferungen, ohne Doppelte, mit Lage, wo bekannt."""
    bericht = bericht if bericht is not None else Bericht()
    geo = lade_geokodierung(pfade.roh / quelle["geokodierung"]["datei"])
    if "geokodierung_ergaenzung" in quelle:  # nur, wo der Cache nichts hat
        ergaenzung = lade_geokodierung(pfade.pipeline / quelle["geokodierung_ergaenzung"]["datei"])
        geo = {**ergaenzung, **geo}
    links = lade_rohdatei_links(pfade.config / quelle["rohdatei_liste"])
    gesehen_namen: dict[str, str] = {}  # name_norm ohne _24h -> Lieferung
    gesehen_fp: set[tuple] = set()
    for lieferung in quelle["lieferungen"]:
        pfad = pfade.roh / lieferung["datei"]
        if not pfad.exists():
            raise FileNotFoundError(f"{pfad} fehlt – erst `zaehlkarte fetch`")
        eintraege = []
        for name, raw in zda.lese_archiv(pfad):
            bericht.dateien[lieferung["code"]] += 1
            eintraege.append((name, zda.parse(raw, name)))
        namen = {name_norm(n).lower() for n, _ in eintraege}
        # gleiche Kennung in zwei Schreibweisen: die ohne Minus zuerst
        eintraege.sort(key=lambda e: ("-" in e[0], e[0]))
        hier: set[str] = set()
        for name, z in eintraege:
            nn = name_norm(name)
            kurz = nn[:-4] if nn.lower().endswith("_24h") else nn
            if not nn.lower().endswith("_24h") and f"{nn.lower()}_24h" in namen:
                bericht.doppelt["12-Stunden-Fassung einer 24-Stunden-Zählung"] += 1
                continue
            if gesehen_namen.get(kurz, lieferung["code"]) != lieferung["code"]:
                bericht.doppelt["auch in der neueren Lieferung"] += 1
                continue
            if kurz in hier:
                bericht.doppelt["gleiche Kennung in zwei Schreibweisen"] += 1
                continue
            fp = _fingerabdruck(z)
            if fp in gesehen_fp:
                bericht.doppelt["gleicher Inhalt unter anderem Namen"] += 1
                continue
            gesehen_fp.add(fp)
            gesehen_namen[kurz] = lieferung["code"]
            hier.add(kurz)
            zaehlung = _zaehlung(z, quelle, lieferung, geo, links)
            if not zaehlung.gruppen():
                bericht.ohne_gruppe[z.kopf.get("art", "")[:40]] += 1
                continue
            bericht.lage[zaehlung.lage or "fehlt"] += 1
            yield zaehlung


def geokodier_liste(quelle: dict, pfade: Pfade) -> list[dict]:
    """Zählungen ohne Lage (kein GPS, nicht im Cache) als Eingabe für den Schulwege-Geocoder:
    Spalten datei, bez, name, arme (mit | getrennt), plz, ortsteil."""
    q = {k: v for k, v in quelle.items() if k != "geokodierung_ergaenzung"}
    return [
        {**{k: z.zusatz[k] or "" for k in ("datei", "bez", "plz", "ortsteil")},
         "name": z.name, "arme": "|".join(z.zusatz["arme"])}
        for z in lese(q, pfade)
        if z.lon is None
    ]
