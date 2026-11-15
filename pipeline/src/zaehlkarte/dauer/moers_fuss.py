"""Moers: Fußgängerzählung in der Steinstraße (Laser der MoersMarketing GmbH) –
Personen je Stunde seit 5. Mai 2022, je Monat eine CSV im Datensatz „Besuchszahlen Steinstraße –
nach Stunden (Stadt Moers)“ auf offenesdatenportal.de.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer`, `tools/moers_fuss_erkunden.py`,
Ergebnis `ergebnis/moers_fuss/`):
- Je Auflösung ein Datensatz (Stunden, Tage), darin je Monat eine Ressource („Besucherzahlen
  Moers im Juni 2024 nach Stunden“). Vollständig stehen die Ressourcen nur im DCAT-Dokument
  (`ckan.paket`, Weg `dcat`); die CKAN-API sperrt robots.txt, Crawl-delay 10 s. Die Tagesdatei
  ist die Summe der Stunden je Ortstag (an allen 1.553 geprüften Tagen) – sie bringt nichts dazu.
- Vier Spaltenfolgen: bis Juli 2023 deutsch („Lage;Zeitpunkt der Messung;Wochentag;Fußgänger
  insgesamt;…“, Windows-1252; Mai 2022 und März 2023 mit Tabulator, Februar 2023 englisch mit
  Tabulator), ab August 2023 englisch („location;time of measurement;weekday;pedestrians
  count;…“, UTF-8 mit BOM), ab September 2024 mit `collection_type`. Zeit „2024-06-01 00:00:00
  +0200“: Ortszeit mit Abstand zu UTC, die beiden Stunden 2 Uhr am Tag der Rückstellung stehen
  getrennt (`setze_utc`).
- Zeilen, die gegen den Kopf verschoben sind: Juli 2022 mit einer leeren Spalte `incidents`, die
  der Kopf nicht hat; Februar 2023 mit „Steinstraße“ und „ Moers“ in zwei Spalten. Der Leser sucht
  die Zeit in der Zeile und liest den Wert relativ zu ihr: alle zu Fuß Gehenden (beide
  Richtungen, Erwachsene und Kinder) stehen zwei Spalten hinter der Zeit, nach dem Wochentag.
- `collection_type` „modelled“: geschätzt, nicht gemessen -> nicht gezählt (fast nur 5 und
  6 Uhr, 2026 an 121 Tagen). Leer (150 Nachtstunden mit Werten 0–7 bis Februar 2025) zählt wie
  gemessen. Vor September 2024 kennzeichnet die Datei nicht, ob eine Stunde geschätzt ist.
- Die Datei „August 2024“ enthält den August 2023 (dieselben Werte): Zeilen außerhalb des Monats
  der Datei (laut Titel der Ressource, sonst Dateiname) zählen nicht. Derselbe Zeitpunkt zweimal
  mit verschiedenen Werten: nicht gezählt (`utc_stunden`).
- Vom 1. bis 4. Mai 2022 nur Nullen – der Laser zählt laut Titel der ersten Datei „ab 5. Mai
  2022“: Zeilen vor `ab` (Quelldatei) zählen nicht.
- Lage: die Datei nennt nur „Steinstraße, Moers“ – Punkt in der Quelldatei (`lage`).
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from urllib.parse import unquote, urlparse

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import Dauerstelle, Messreihe, kuerze, setze_utc, utc_stunden

_ZEIT = re.compile(r"\s*(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2}) ([+-])(\d{2})(\d{2})\s*")
KOPF_ZEIT = ("time of measurement", "zeitpunkt der messung")
KOPF_WERT = ("pedestrians count", "fußgänger insgesamt")
KOPF_ART = ("collection_type", "collection type")
GESCHAETZT = ("modelled", "mixed")  # geschätzt bzw. teils geschätzt (Tagesdatei: „mixed“)
MONATE = {m: i + 1 for i, m in enumerate(
    ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
     "oktober", "november", "dezember"])} | {"marz": 3, "maerz": 3}
_MONAT = re.compile(r"\b(" + "|".join(MONATE) + r")\s*-?\s*(20\d{2})\b", re.I)


@dataclass
class Bericht:
    dateien: int = 0
    gelesen: int = 0
    unlesbar: int = 0
    geschaetzt: int = 0
    vor_beginn: int = 0
    widerspruch: int = 0
    stunden: int = 0
    ausserhalb: dict[str, int] = field(default_factory=dict)
    ohne_kopf: list[str] = field(default_factory=list)
    bis: str | None = None

    def zeilen(self) -> list[str]:
        return [
            f"{self.dateien} Monatsdateien, {self.gelesen} Zeilen ({self.unlesbar} unlesbar), "
            f"{self.stunden} Stunden in der Karte; jüngster Wert {self.bis}",
            f"nicht gezählt: {self.geschaetzt} geschätzt (modelled), {self.vor_beginn} vor dem "
            f"Beginn der Zählung, {self.widerspruch} Zeitpunkte doppelt mit verschiedenen Werten",
            *[f"Zeilen außerhalb des Monats der Datei (nicht gezählt): {d} {n}"
              for d, n in sorted(self.ausserhalb.items())],
            *[f"Kopf nicht erkannt (Datei nicht gelesen): {d}" for d in self.ohne_kopf],
        ]


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Die Monatsdateien „nach Stunden“ aus dem DCAT-Dokument des Datensatzes – nur neue oder
    geänderte (Crawl-delay 10 s je Abruf)."""
    from zaehlkarte import abruf, ckan

    ordner = pfade.roh / q["code"]
    (ordner / "monate").mkdir(parents=True, exist_ok=True)
    paket = ckan.paket(q["ckan"], q["paket"], wege=("dcat",))
    gewaehlt: dict[str, dict] = {}
    for r in paket["resources"]:
        url = r.get("url") or ""
        datei = unquote(urlparse(url).path.rsplit("/", 1)[-1])
        if not re.search(q["dateien"], datei, re.I):
            continue
        gewaehlt[datei] = {"url": url, "name": r.get("name"),
                           "stand": r.get("last_modified") or r.get("created")}
    if not gewaehlt:
        raise ValueError(f"{q['code']}: keine Datei „{q['dateien']}“ in {q['paket']}")
    pfad = ordner / "abruf.json"
    vorher = (json.loads(pfad.read_text(encoding="utf-8")).get("dateien", {})
              if pfad.exists() else {})
    offen = [d for d, info in sorted(gewaehlt.items())
             if vorher.get(d) != info or not (ordner / "monate" / d).exists()]
    for d in offen:
        abruf.lade(gewaehlt[d]["url"], ordner / "monate" / d)
    pfad.write_text(json.dumps({
        "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "paket": q["paket"], "titel": paket.get("title"), "dateien": gewaehlt,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(gewaehlt)} Monatsdateien, {len(offen)} neu geholt"]


def monat(*texte: str | None) -> tuple[int, int] | None:
    """(Jahr, Monat) aus dem Titel der Ressource oder dem Dateinamen – der erste Treffer zählt."""
    for t in texte:
        if t and (m := _MONAT.search(t.lower().replace("_", "-"))):
            return int(m[2]), MONATE[m[1].lower()]
    return None


def text_von(roh: bytes) -> str:
    """UTF-8 (mit oder ohne BOM), sonst Windows-1252 (die frühen Dateien)."""
    try:
        return roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        return roh.decode("cp1252")


def lies_datei(text: str) -> list[tuple[datetime, int, str | None]] | None:
    """Monatsdatei -> [(Zeit in UTC ohne Zone, Wert, collection_type)]; None: Kopf unbekannt.

    Der Wert steht zwei Spalten hinter der Zeit; Zeilen ohne Zeit oder ohne Zahl fehlen (der
    Aufrufer zählt sie als unlesbar)."""
    kopfzeile = text.split("\n", 1)[0]
    trenn = "\t" if kopfzeile.count("\t") > kopfzeile.count(";") else ";"
    leser = csv.reader(io.StringIO(text), delimiter=trenn)
    kopf = [k.strip().lower() for k in next(leser, [])]
    i_zeit = next((i for i, k in enumerate(kopf) if k in KOPF_ZEIT), None)
    i_wert = next((i for i, k in enumerate(kopf) if k in KOPF_WERT), None)
    i_art = next((i for i, k in enumerate(kopf) if k in KOPF_ART), None)
    if i_zeit is None or i_wert != i_zeit + 2:
        return None
    out = []
    for r in leser:
        pos = next((i for i, x in enumerate(r) if _ZEIT.fullmatch(x)), None)
        if pos is None:
            if any(x.strip() for x in r):
                out.append((None, -1, None))  # unlesbar
            continue
        schieb = pos - i_zeit
        j, mo, t, h, mi, s, vz, oh, om = _ZEIT.fullmatch(r[pos]).groups()
        wert = r[i_wert + schieb].strip() if i_wert + schieb < len(r) else ""
        if mi != "00" or s != "00" or not wert.isdigit():
            out.append((None, -1, None))
            continue
        abstand = timedelta(hours=int(oh), minutes=int(om)) * (1 if vz == "+" else -1)
        lokal = datetime(int(j), int(mo), int(t), int(h), tzinfo=timezone(abstand))
        art = (r[i_art + schieb].strip().lower() or None
               if i_art is not None and i_art + schieb < len(r) else None)
        out.append((lokal, int(wert), art))
    return out


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    pfad = ordner / "abruf.json"
    if not pfad.exists():
        raise ValueError(f"{q['code']}: kein Abruf in {ordner} – erst `zaehlkarte dauer fetch`")
    dateien = json.loads(pfad.read_text(encoding="utf-8"))["dateien"]
    ab: date = q["ab"]
    utc, werte = [], []
    for datei, info in sorted(dateien.items()):
        roh = ordner / "monate" / datei
        if not roh.exists():
            continue
        zeilen = lies_datei(text_von(roh.read_bytes()))
        if zeilen is None:
            bericht.ohne_kopf.append(datei)
            continue
        bericht.dateien += 1
        soll = monat(info.get("name"), datei)
        for lokal, wert, art in zeilen:
            bericht.gelesen += 1
            if lokal is None:
                bericht.unlesbar += 1
                continue
            if soll and (lokal.year, lokal.month) != soll:
                bericht.ausserhalb[datei] = bericht.ausserhalb.get(datei, 0) + 1
                continue
            if lokal.date() < ab:
                bericht.vor_beginn += 1
                continue
            if art in GESCHAETZT:
                bericht.geschaetzt += 1
                wert = -1  # geschätzt: nicht gezählt, auch nicht über eine zweite Zeile
            utc.append(lokal.astimezone(UTC).replace(tzinfo=None))
            werte.append(wert)
    if not utc:
        raise ValueError(f"{q['code']}: keine Werte in {ordner / 'monate'}")
    lage = q["lage"]
    stelle = Dauerstelle(
        quelle=q["code"], kennung=lage["kennung"], name=lage["name"],
        abschnitt=lage.get("abschnitt"), richtung=None, lon=float(lage["lon"]),
        lat=float(lage["lat"]), land=q["land"], hinweise=list(lage.get("hinweise") or []))
    st, stunde, summe, bericht.widerspruch = utc_stunden(
        np.zeros(len(utc), dtype=np.int64), np.array(utc, dtype="datetime64[m]"),
        np.array(werte, dtype=np.int64), anzahl=1)
    if not len(st):
        raise ValueError(f"{q['code']}: keine gezählte Stunde")
    erste = min(utc) + timedelta(hours=2)  # Ortszeit liegt höchstens 2 Stunden vor UTC
    letzte = max(utc) + timedelta(hours=2)
    reihe = Messreihe.leer(q["code"], erste.date() - timedelta(days=1), letzte.date(), [stelle],
                           ("fuss",))
    bericht.stunden = setze_utc(reihe, "fuss", st, stunde, summe)
    kuerze(reihe)
    bericht.bis = reihe.tag(reihe.tage - 1).isoformat()
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "zu Fuß Gehende je Stunde laut Datei (beide Richtungen, Erwachsene und "
                        "Kinder), ohne als geschätzt gekennzeichnete Stunden, zu Tagessummen "
                        "zusammengefasst")]
    return reihe
