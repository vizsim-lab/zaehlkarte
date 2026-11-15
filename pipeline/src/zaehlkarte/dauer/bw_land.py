"""Baden-Württemberg: Dauerzählstellen des Landes (Verkehrsministerium, über MobiData BW) –
Stundenwerte je Fahrstreifen für Kfz und Schwerverkehr an Autobahnen, Bundes- und Landesstraßen.

Aufbau (Stand November 2026; Werkzeug-Branch `werkzeug/bw`, tools/bw_dauer.py bis bw_dauer4.py):
- Datensatz `stundenwerte_dauerzaehlstellen`: je Monat ein ZIP `Stundenwerte_JJJJMM.zip` (ab
  Januar 2025, rund zwei Monate Verzug). Ältere Monate ersetzt das Land gelegentlich – das
  DCAT-Dokument nennt das Datum jeder Ressource; geändertes Datum -> neu laden. Dazu je Jahr
  2016–2024 ein ZIP `Stundenwerte_JJJJ.zip` (45–54 MB; 2024 aus Monats-ZIPs) – nicht im
  DCAT-Dokument, aber in der Beschreibung des Datensatzes; neu geladen, wenn sich das Datum des
  Gesamtarchivs (`Stundenwerte_Archiv.zip`) ändert.
- Je Stelle und Monat eine CSV `BW_<Nummer>_<JJMM>.csv` (UTF-8 oder Windows-1252), abgeleitet aus
  den Dateien für die BASt („BASt-Bestandsbandformat für Verkehrsmengendaten“, Version 2004):
  1. TK25-Blatt; Zählstellennummer; Land; Straßenklasse; Straßennummer; Name
  2. Fahrstreifen Richtung I; Fahrstreifen Richtung II; Fernziel I; Himmelsrichtung I;
     Fernziel II; Himmelsrichtung II – bis 2025 steht nur ein Fernziel da, mal das der einen,
     mal das der anderen Richtung; die Karte nennt dann nur die Himmelsrichtung.
  3. Anzahl der Gruppen; Anzahl der Arten; die Gruppen (KFZ und SV bei 8+1 Fahrzeugarten, KFZ und
     LK – die Lkw-ähnlichen – bei zwei Klassen); die Arten (Mot, Pkw, Lfw, …)
  4. Spaltennamen: Datum;Uhrzeit;KFZFS1;K_KFZFS1;SVFS1;K_SVFS1;…;MotFS1;K_MotFS1;…
  Die Fahrstreifen sind über die Fahrbahn durchnummeriert: erst die der Richtung I, dann II.
- Zeilen: Datum `JJMMTT`, dahinter die Statuskennung („i“ = eingefügter Datensatz), Uhrzeit
  `hh:mm` als Ende der Stunde in Ortszeit (01:00 = 0–1 Uhr, 24:00 = 23–24 Uhr), je Fahrstreifen
  Wert und Prüfkennzeichen. Prüfkennzeichen laut BASt: „-“ korrekt, „u“ korrekt, aber
  unregelmäßig (etwa Großveranstaltung), „a“ Ausfall, „d“ fehlerhaft, „s“ Schätzwert wegen
  fehlender Werte, „k“ Schätzwert wegen fehlerhafter Werte, „z“ Zeitumstellung. In den Daten
  stehen dazu „h“, „t“ (ab 2026) und „S“, die die Beschreibung nicht nennt.
- In der Karte: je Fahrtrichtung eine Stelle (beide am selben Punkt), Wert = Summe ihrer
  Fahrstreifen – nur, wenn auf allen „-“ oder „u“ steht und die Zeile nicht eingefügt ist; sonst
  ist die Stunde nicht gezählt. Gruppen: KFZ -> kfz, SV -> sv (Schwerverkehr laut Zählgerät:
  LoA + LmA + Sat + Bus), LK -> lkw (Lkw-ähnliche bei zwei Klassen) – nie ineinander umgerechnet.
- Zeitumstellung: Im Frühjahr steht die ausgefallene Stunde 2–3 Uhr als Zeile 03:00 mit 0 und „z“
  da (ab 2026 mit „i“) – die Stunde gibt es nicht. Im Herbst steht 2–3 Uhr nur einmal da, mit „z“
  (bis 2022 im Median das Anderthalbfache eines Sonntags davor – wohl beide Stunden –, seit 2023
  etwa eine) – nicht gezählt, der Tag ist nicht vollständig. „z“ steht nur an diesen Zeilen.
- Dieselbe Stelle und derselbe Monat zweimal in einem ZIP: gleicher Inhalt zählt einmal,
  verschiedener gar nicht. In einem späteren ZIP ersetzt der Monat den früheren.
- Stelle: die Zählstellennummer (vier Ziffern, Kennung der BASt). Das TK25-Blatt davor wechselt
  bei einigen Stellen (Kappelberg-Tunnel 2026: 7121 -> 7221), die Straße bei Umstufungen (Horb-Nord:
  B 14 -> B 28, Lörrach-Stetten: B 317 -> Gemeindestraße) – Name, Straße und Richtungen kommen aus
  der jüngsten Datei. Bis 2017 kürzen einige Autobahn-Stellen den Namen („Ma-Sa_W_V“).
- Lage: Die CSV nennen keine Koordinaten. Sie kommt aus den Grunddaten der Zählstellenkarte
  (Datensatz `karte_strassenverkehrszaehlung`: svznr, zstart – DZ Dauerzählstelle, MZ, TM –,
  klasse, nummer, gpsx1/gpsy1, RI/RII). Eine Datei heißt meist nach der SVZ-Nummer des Abschnitts
  ihrer Stelle, sonst nach Blatt und Zählstellennummer; die SVZ-Nummer wechselt zwischen den
  Jahren teils auf Nachbarabschnitte, gern auf solche mit temporären Messstellen (TM). Zugeordnet
  wird ein Abschnitt aus den Dateinamen der Stelle, dessen Straße passt (Klasse, Nummer ohne
  Buchstaben) und der kein TM ist: Dauerzählstellen (DZ) vor MZ (Autobahnen, einige
  Bundesstraßen), dann der Abschnitt, unter dem die Stelle am häufigsten kam, dann der jüngere;
  jeder Abschnitt nur einer Stelle. Bleibt eine Stelle ohne Abschnitt, gilt der einzige noch freie
  DZ-Abschnitt derselben Straße auf ihrem Kartenblatt (SVZ-Nummer beginnt mit dem Blatt), wenn
  keine andere Stelle ihn ebenso beansprucht. Sonst: keine Lage, nicht in der Karte (Bericht).
"""

from __future__ import annotations

import calendar
import csv
import io
import json
import re
import zipfile
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

GRUPPE = {"KFZ": "kfz", "SV": "sv", "LK": "lkw", "LKW": "lkw"}  # Gruppe der Quelle -> der Karte
GUT = ("-", "u")  # Prüfkennzeichen gezählter Werte
HIMMEL = {"N": "Norden", "O": "Osten", "S": "Süden", "W": "Westen"}
MONAT = re.compile(r"Stundenwerte_(\d{6})\.zip$")
DATEI = re.compile(r"[A-Z]{2}_(\d+)_(\d{2})(\d{2})\.csv$", re.I)  # 2018 einmal „BY_…“
ZEILE = re.compile(r"^\d{6}[^;]*;\d{2}:\d{2}")


@dataclass
class Bericht:
    zip_dateien: list[str] = field(default_factory=list)
    dateien: int = 0  # CSV (je Stelle und Monat)
    cp1252: int = 0  # CSV nicht in UTF-8
    datensaetze: int = 0  # Stundenzeilen
    eingefuegt: int = 0  # davon mit Statuskennung „i“
    # (Gruppe, Prüfkennzeichen) -> Fahrstreifen-Stunden
    kennungen: Counter = field(default_factory=Counter)
    stellen: int = 0  # Zählstellen in den Dateien
    richtungen: int = 0  # Stellen in der Karte (je Fahrtrichtung)
    ohne_lage: list[str] = field(default_factory=list)
    lage: Counter = field(default_factory=Counter)  # Art des zugeordneten Abschnitts
    gleich: int = 0  # Stelle und Monat zweimal im selben ZIP, gleicher Inhalt (einmal gezählt)
    doppelt: list[str] = field(default_factory=list)  # … verschiedener Inhalt (nicht gezählt)
    fehler: list[str] = field(default_factory=list)  # Dateien, die nicht lesbar waren
    unbekannte_gruppen: Counter = field(default_factory=Counter)
    stunden: Counter = field(default_factory=Counter)  # Gruppe -> gezählte Stunden
    sommerzeit: int = 0  # Einträge um 2 Uhr am Tag der Sommerzeit (verworfen)

    def zeilen(self) -> list[str]:
        alle = Counter()
        for (_, k), n in self.kennungen.items():
            alle[k or "leer"] += n
        nicht = {k: n for k, n in alle.items() if k not in GUT}
        z = [f"{len(self.zip_dateien)} ZIP ({_spanne(self.zip_dateien)}), {self.dateien} CSV "
             f"({self.cp1252} in Windows-1252), {self.datensaetze} Stundenzeilen, davon "
             f"{self.eingefuegt} eingefügt (nicht gezählt)",
             f"{self.stellen} Zählstellen, in der Karte {self.richtungen} Stellen je Richtung; "
             "Lage: " + (", ".join(f"{k} {n}" for k, n in self.lage.most_common()) or "–"),
             "Fahrstreifen-Stunden nach Prüfkennzeichen: "
             + ", ".join(f"{k} {n}" for k, n in alle.most_common()),
             "davon nicht gezählt (alles außer „-“ und „u“): "
             + (", ".join(f"{k} {n}" for k, n in sorted(nicht.items())) or "–"),
             "Stunden in der Karte: " + ", ".join(f"{g} {n}" for g, n in self.stunden.items())
             + f"; Einträge um 2 Uhr am Tag der Sommerzeit verworfen: {self.sommerzeit}"]
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {'; '.join(self.ohne_lage)}")
        if self.gleich:
            z.append(f"Stelle und Monat zweimal im selben ZIP, gleicher Inhalt: {self.gleich}")
        if self.doppelt:
            z.append("Stelle und Monat zweimal im selben ZIP, verschieden (nicht gezählt): "
                     + "; ".join(self.doppelt[:20]))
        if self.unbekannte_gruppen:
            z.append(f"unbekannte Gruppen (nicht übernommen): {dict(self.unbekannte_gruppen)}")
        if self.fehler:
            z.append(f"nicht lesbar ({len(self.fehler)}): {'; '.join(self.fehler[:20])}")
        return z


def _spanne(namen: list[str]) -> str:
    return f"{min(namen)} … {max(namen)}" if namen else "–"


# ---------------------------------------------------------------- Abruf


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Monats-ZIPs (laut DCAT-Dokument), Jahresarchive und die Grunddaten der Zählstellenkarte
    holen – fehlende immer, vorhandene nur, wenn sich URL oder Datum der Ressource geändert hat."""
    from zaehlkarte import ckan
    from zaehlkarte.fetch import lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    meta_pfad = ordner / "abruf.json"
    meta = json.loads(meta_pfad.read_text(encoding="utf-8")) if meta_pfad.exists() else {}
    stand: dict[str, list[str]] = meta.get("stand", {})
    jetzt = datetime.now(UTC).replace(microsecond=0)

    soll: dict[str, tuple[str, str]] = {}
    archiv = ""
    for res in ckan.paket(q["portal_basis"], q["datensatz"], wege=("dcat",))["resources"]:
        url = res.get("url") or ""
        datum = res.get("last_modified") or res.get("created") or ""
        if (m := MONAT.search(url)) and m.group(1) >= q["ab"].replace("-", ""):
            soll[f"monat_{m.group(1)}.zip"] = (url, datum)
        elif url.endswith("/Stundenwerte_Archiv.zip"):
            archiv = datum
    if not soll:
        raise ValueError(f"{q['code']}: keine Monats-ZIPs im DCAT-Dokument von {q['datensatz']}")
    a = q["archiv"]
    for jahr in range(int(a["von"]), int(a["bis"]) + 1):
        soll[f"jahr_{jahr}.zip"] = (a["url"].format(jahr=jahr), archiv)
    k = q["karte"]
    karte = [r for r in ckan.paket(q["portal_basis"], k["datensatz"], wege=("dcat",))["resources"]
             if re.search(k["muster"], r.get("url") or "")]
    if not karte:
        raise ValueError(f"{q['code']}: keine Grunddaten der Zählstellenkarte ({k['muster']})")
    neueste = max(karte, key=lambda r: (r.get("last_modified") or r.get("created") or "",
                                        r["url"]))
    soll["karte.csv"] = (neueste["url"], neueste.get("last_modified") or "")

    geladen = []
    for name, (url, datum) in sorted(soll.items()):
        if (ordner / name).exists() and stand.get(name) == [url, datum]:
            continue
        lade(url, ordner / name)
        stand[name] = [url, datum]
        geladen.append(name)
        # nach jeder Datei festhalten – bricht der Lauf ab, bleibt das Geladene gültig
        meta_pfad.write_text(json.dumps({**meta, "stand": stand}, indent=1) + "\n",
                             encoding="utf-8")
    meta_pfad.write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "stand": stand,
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(geladen)} Dateien geladen"
            + (f" ({', '.join(geladen)})" if geladen else "")
            + f", {len(soll) - len(geladen)} unverändert"]


# ---------------------------------------------------------------- Lesen


@dataclass
class Datei:
    """Eine CSV einer Stelle und eines Monats."""

    zip: str  # das ZIP, aus dem sie kommt (jahr_2016, monat_202501, …)
    name: str  # Dateiname ohne Ordner
    monat: str  # JJJJMM aus dem Dateinamen
    stelle: str  # Zählstellennummer, 4 Ziffern
    blatt: str  # TK25-Blatt, 4 Ziffern
    kopf1: list[str]
    kopf2: list[str]
    gruppen: list[str]  # Gruppen der Quelle (KFZ, SV, LK)
    spalten: dict[str, int]
    zeilen: list[str]  # die Stundenzeilen


def lies_datei(zip_name: str, name: str, roh: bytes, bericht: Bericht) -> Datei | None:
    try:
        t = roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        t = roh.decode("cp1252", "replace")
        bericht.cp1252 += 1
    zeilen = t.splitlines()
    m = DATEI.search(name)
    if len(zeilen) < 4 or not m:
        bericht.fehler.append(f"{name}: kein Kopf")
        return None
    k1, k2, k3, sp = ([x.strip() for x in zeilen[i].split(";")] for i in range(4))
    try:
        blatt, stelle = f"{int(k1[0]):04d}", f"{int(k1[1]):04d}"
        n_gruppen = int(k3[0])
        int(k2[0]), int(k2[1])
    except (ValueError, IndexError):
        bericht.fehler.append(f"{name}: Kopf {zeilen[:3]}")
        return None
    return Datei(zip=zip_name, name=name.split("/")[-1], monat=f"20{m.group(2)}{m.group(3)}",
                 stelle=stelle, blatt=blatt, kopf1=k1, kopf2=k2,
                 gruppen=[g.upper() for g in k3[2:2 + n_gruppen]],
                 spalten={s: i for i, s in enumerate(sp) if s},
                 zeilen=[z for z in zeilen[4:] if ZEILE.match(z)])


def dateien(ordner: Path, bericht: Bericht) -> Iterator[Datei]:
    """Alle CSV der ZIPs in zeitlicher Folge (Jahresarchive, dann Monate; ZIPs in ZIPs)."""

    def aus_zip(zip_name: str, z: zipfile.ZipFile) -> Iterator[Datei]:
        for n in sorted(z.namelist()):
            if n.endswith("/"):
                continue
            if n.lower().endswith(".zip"):
                with zipfile.ZipFile(io.BytesIO(z.read(n))) as innen:
                    yield from aus_zip(zip_name, innen)
            elif n.lower().endswith(".csv"):
                bericht.dateien += 1
                if (d := lies_datei(zip_name, n, z.read(n), bericht)) is not None:
                    yield d

    for pfad in sorted(ordner.glob("jahr_*.zip")) + sorted(ordner.glob("monat_*.zip")):
        bericht.zip_dateien.append(pfad.stem.split("_", 1)[1])
        with zipfile.ZipFile(pfad) as z:
            yield from aus_zip(pfad.stem, z)


def strasse(klasse: str, nummer: str) -> str:
    """„L“, „2310“ -> „L 2310“; „B“, „31A“ -> „B 31a“; Gemeindestraße (G, 0) -> „“."""
    nummer = nummer.strip().lstrip("0").lower()
    if klasse.strip().upper() == "G" or not nummer:
        return ""
    return f"{klasse.strip().upper()} {nummer}"


def _nummer(text: str) -> str:
    """Straßennummer ohne Buchstaben und führende Nullen: „600A“ -> „600“."""
    return re.sub(r"\D", "", text).lstrip("0")


def lies_karte(pfad: Path) -> dict[str, dict]:
    """Grunddaten der Zählstellenkarte: svznr -> Zeile."""
    with pfad.open(encoding="utf-8-sig", newline="") as f:
        return {z["svznr"].strip(): z for z in csv.DictReader(f)}


def ordne_lage(kandidaten: dict[str, dict[str, tuple[int, str]]], meta: dict[str, dict],
               karte: dict[str, dict]) -> dict[str, tuple[str, str]]:
    """Stelle -> (SVZ-Nummer ihres Abschnitts in der Zählstellenkarte, wie gefunden) – siehe Kopf.
    `kandidaten`: je Stelle die Nummern aus ihren Dateinamen mit (Anzahl, jüngster Monat);
    `meta`: je Stelle Klasse, Nummer der Straße und Blatt (`blatt`) der jüngsten Datei."""

    def passt(z: dict, m: dict) -> bool:
        return (z["klasse"].strip().upper() == m["klasse"].strip().upper()
                and _nummer(z["nummer"]) == _nummer(m["nummer"]))

    paare = []
    for stelle, namen in kandidaten.items():
        for svznr, (anzahl, juengster) in namen.items():
            z = karte.get(svznr)
            if z is None or z["zstart"].strip() not in ("DZ", "MZ") or not passt(z, meta[stelle]):
                continue
            paare.append(((z["zstart"].strip() == "DZ", anzahl, juengster, svznr), stelle))
    paare.sort(reverse=True)
    lage: dict[str, tuple[str, str]] = {}
    for (_, _, _, svznr), stelle in paare:
        if stelle not in lage and svznr not in {v for v, _ in lage.values()}:
            lage[stelle] = (svznr, "Dateiname")
    # ohne Abschnitt: der einzige freie DZ-Abschnitt derselben Straße auf dem Blatt der Stelle
    vergeben = {v for v, _ in lage.values()}
    frei = [z for z in karte.values() if z["zstart"].strip() == "DZ" and z["svznr"] not in vergeben]
    wunsch = {s: [z["svznr"] for z in frei if passt(z, m) and z["svznr"][:4] == m["blatt"]]
              for s, m in meta.items() if s not in lage}
    begehrt = Counter(v for w in wunsch.values() for v in w)
    for stelle, w in wunsch.items():
        if len(w) == 1 and begehrt[w[0]] == 1:
            lage[stelle] = (w[0], "Straße und Kartenblatt")
    return lage


def richtung(kopf2: list[str], r: int) -> str | None:
    """Fahrtziel und Himmelsrichtung der Richtung r (1, 2) aus der zweiten Kopfzeile."""
    k = [x.strip() for x in kopf2] + [""] * 6
    ziel1, ziel2 = k[2], k[4]
    ziel, himmel = (k[2], k[3]) if r == 1 else (k[4], k[5])
    himmel = HIMMEL.get(himmel.upper(), himmel)
    if ziel1 and ziel2:  # bis 2025 nur ein Fernziel – dann nur die Himmelsrichtung
        return f"Richtung {ziel}" + (f" ({himmel})" if himmel else "")
    return f"Richtung {himmel}" if himmel else None


def _letzter_tag(monat: str) -> date:
    j, m = int(monat[:4]), int(monat[4:])
    return date(j, m, calendar.monthrange(j, m)[1])


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    """Zwei Durchgänge: erst die Köpfe (Stellen, Lage, Zeitraum, doppelte Dateien), dann die
    Stunden."""
    ordner = pfade.roh / q["code"]
    if not any(ordner.glob("monat_*.zip")):
        raise ValueError(f"{q['code']}: keine Monats-ZIPs in {ordner} – erst "
                         "`zaehlkarte dauer fetch`")
    karte = lies_karte(ordner / "karte.csv")

    # 1. Köpfe: je Stelle der jüngste Kopf, die Dateinamen als Kandidaten für die Lage
    meta: dict[str, dict] = {}
    kandidaten: dict[str, dict[str, tuple[int, str]]] = defaultdict(dict)
    inhalte: dict[tuple[str, str, str], dict[int, str]] = defaultdict(dict)
    gruppen_je_stelle: dict[str, set[str]] = defaultdict(set)
    monate: set[str] = set()
    for d in dateien(ordner, Bericht()):
        k1 = d.kopf1 + [""] * 6
        if d.stelle not in meta or d.monat >= meta[d.stelle]["monat"]:
            meta[d.stelle] = {"monat": d.monat, "klasse": k1[3], "nummer": k1[4],
                              "name": " ".join(k1[5].split()), "kopf2": d.kopf2,
                              "blatt": d.blatt}
        nr = DATEI.search(d.name).group(1)
        anzahl, juengster = kandidaten[d.stelle].get(nr, (0, ""))
        kandidaten[d.stelle][nr] = (anzahl + 1, max(juengster, d.monat))
        inhalte[(d.zip, d.stelle, d.monat)].setdefault(hash(tuple(d.zeilen)), d.name)
        gruppen_je_stelle[d.stelle] |= {GRUPPE[g] for g in d.gruppen if g in GRUPPE}
        monate.add(d.monat)
    # dieselbe Stelle und derselbe Monat mehrfach im selben ZIP
    nehmen: dict[tuple[str, str, str], str | None] = {}
    for schluessel, namen in inhalte.items():
        if len(namen) == 1:
            nehmen[schluessel] = next(iter(namen.values()))
        else:
            nehmen[schluessel] = None
            bericht.doppelt.append(f"{schluessel[1]} {schluessel[2]} ({', '.join(namen.values())})")
    bericht.stellen = len(meta)
    lage = ordne_lage(kandidaten, meta, karte)

    stellen: list[Dauerstelle] = []
    index: dict[tuple[str, int], int] = {}
    for stelle in sorted(meta):
        m = meta[stelle]
        name = " ".join(x for x in (strasse(m["klasse"], m["nummer"]), m["name"]) if x)
        if stelle not in lage:
            bericht.ohne_lage.append(f"{name} ({stelle})")
            continue
        svznr, wie = lage[stelle]
        z = karte[svznr]
        teile = [" ".join(z[k].replace('\\"', '"').split()) for k in ("RI", "RII")]
        bericht.lage[f"{z['zstart'].strip()} ({wie})"] += 1
        for r in (1, 2):
            index[(stelle, r)] = len(stellen)
            stellen.append(Dauerstelle(
                quelle=q["code"], kennung=f"{stelle}-{r}", name=name or stelle,
                abschnitt=" – ".join(t for t in teile if t) or None,
                richtung=richtung(m["kopf2"], r), lon=round(float(z["gpsx1"]), 6),
                lat=round(float(z["gpsy1"]), 6), land=q["land"]))
    bericht.richtungen = len(stellen)
    if not stellen:
        raise ValueError(f"{q['code']}: keine Stelle mit Lage")
    erster = min(monate)
    von = date(int(erster[:4]), int(erster[4:]), 1)
    gruppen = tuple(g for g in ("kfz", "lkw", "sv")
                    if any(g in gruppen_je_stelle[s] for s, _ in index))
    reihe = Messreihe.leer(q["code"], von, _letzter_tag(max(monate)), stellen, gruppen)

    # 2. Stunden
    for d in dateien(ordner, bericht):
        schluessel = (d.zip, d.stelle, d.monat)
        if nehmen.get(schluessel) != d.name or (d.stelle, 1) not in index:
            if nehmen.get(schluessel) is not None and (d.stelle, 1) in index:
                bericht.gleich += 1
            continue
        setze_datei(reihe, d, index, bericht)
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Fahrtrichtung (Summe der Fahrstreifen), nur Stunden mit "
                        "Prüfkennzeichen „-“ oder „u“ auf allen Fahrstreifen")]
    return reihe


def setze_datei(reihe: Messreihe, d: Datei, index: dict[tuple[str, int], int],
                bericht: Bericht) -> None:
    """Die Stundenzeilen einer Datei in die Reihe legen (je Richtung und Gruppe)."""
    n1, n2 = int(d.kopf2[0]), int(d.kopf2[1])
    spuren = {1: range(1, n1 + 1), 2: range(n1 + 1, n1 + n2 + 1)}
    gruppen = []
    for g in d.gruppen:
        if g not in GRUPPE:
            bericht.unbekannte_gruppen[g] += 1
            continue
        try:
            spalten = {r: ([d.spalten[f"{g}FS{s}"] for s in sp],
                           [d.spalten[f"K_{g}FS{s}"] for s in sp]) for r, sp in spuren.items()}
        except KeyError as e:
            bericht.fehler.append(f"{d.name}: Spalte {e}")
            return
        gruppen.append((g, spalten))
    if not d.zeilen or not gruppen:
        return
    breite = max(i for _, sp in gruppen for w, k in sp.values() for i in w + k) + 1
    felder = [z.split(";") for z in d.zeilen]
    feld = np.array([f[:breite] + [""] * (breite - len(f)) if len(f) < breite else f[:breite]
                     for f in felder])
    stunde = np.array([int(x[:2]) - 1 for x in feld[:, 1]], dtype=np.int64)  # Ende -> Beginn
    if not ((stunde >= 0) & (stunde <= 23)).all():
        bericht.fehler.append(f"{d.name}: Uhrzeit außerhalb 01:00–24:00")
        feld, stunde = feld[(stunde >= 0) & (stunde <= 23)], stunde[(stunde >= 0) & (stunde <= 23)]
    datum = feld[:, 0]
    try:
        tag = np.array([f"20{x[:2]}-{x[2:4]}-{x[4:6]}" for x in datum], dtype="datetime64[D]")
    except ValueError:
        bericht.fehler.append(f"{d.name}: Datum nicht lesbar")
        return
    eingefuegt = np.array([x[6:].strip().lower() == "i" for x in datum], dtype=bool)
    bericht.datensaetze += len(feld)
    bericht.eingefuegt += int(eingefuegt.sum())
    for g, spalten in gruppen:
        alle_k = [k for _, ks in spalten.values() for k in ks]
        werte, anzahl = np.unique(np.char.strip(feld[:, alle_k]), return_counts=True)
        for w, n in zip(werte.tolist(), anzahl.tolist(), strict=True):
            bericht.kennungen[(g, w)] += n
        for r, (w_spalten, k_spalten) in spalten.items():
            if not w_spalten:
                continue
            k = np.char.strip(feld[:, k_spalten])
            w = np.char.strip(feld[:, w_spalten])
            zahl = np.char.isdigit(w)
            gut = np.isin(k, GUT).all(axis=1) & zahl.all(axis=1) & ~eingefuegt
            summe = np.where(zahl, w, "0").astype(np.int64).sum(axis=1)
            gesetzt, sommer = setze_lokal(
                reihe, GRUPPE[g], np.full(len(feld), index[(d.stelle, r)], dtype=np.int64), tag,
                stunde, np.where(gut, summe, LEER), anzahl=1, rueck="einfach")
            bericht.stunden[GRUPPE[g]] += gesetzt
            bericht.sommerzeit += sommer
