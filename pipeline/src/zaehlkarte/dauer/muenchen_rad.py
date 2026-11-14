"""München: Raddauerzählstellen der Stadt – 15-Minuten-Werte je Zählstelle (beide Richtungen und
Summe) seit Juni 2008, im Open-Data-Portal als Jahresdateien und für das laufende Jahr als
Monatsdateien; die Lage im WFS des Geoportals.

Aufbau (Stand November 2026, Werkzeug-Branch `werkzeug/dauer2`, tools/rad_erkunden4.py und 7):
- Spalten `datum`, `uhrzeit_start`, `uhrzeit_ende`, `zaehlstelle` (Kurzname, etwa „Arnulf“),
  `richtung_1`, `richtung_2`, `gesamt`, bis 2024 `kommentar` (etwa „Baustelle“, „Ausfall nach
  Beschädigung“ – dann `NA`); 2022 vorn zusätzlich `t`. Datum als 2008-06-01, 20230101 oder
  2024.01.01, Uhrzeit mit oder ohne Sekunden, Werte teils mit Leerzeichen aufgefüllt.
- Gezählt ist eine Viertelstunde mit Zahl in `gesamt`, und `gesamt` = `richtung_1` + `richtung_2`;
  `NA` oder eine fehlende Zeile heißt nicht gezählt.
- Zeitumstellung: Jeder Tag hat 96 Zeilen. Die fehlende Stunde der Sommerzeit steht mit Nullen
  darin (verworfen); am Rückstelltag steht 2 Uhr nur einmal und hat nicht mehr Fahrten als an
  anderen Sonntagen (2016, 2021, 2025) – eine der beiden Stunden fehlt also, der Tag ist nicht
  vollständig gezählt (`rueck="einfach"`).
- Jahresdatei „15 Minuten Werte JJJJ“ (Paket „…Jahreszahlen“), wo es sie gibt; sonst die
  Monatsdateien „15 Minuten-Werte - <Monat> JJJJ“.
"""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
          "Oktober", "November", "Dezember"]
JAHR = re.compile(r"^15 Minuten Werte (\d{4})\s*$")
MONAT = re.compile(r"15 Minuten.*?(" + "|".join(MONATE) + r")\s+(\d{4})")


@dataclass
class Bericht:
    dateien: list[str] = field(default_factory=list)
    viertelstunden: int = 0
    na: int = 0
    summe_abweichend: int = 0
    kommentare: Counter = field(default_factory=Counter)
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    stunden: int = 0
    sommerzeit: int = 0

    def zeilen(self) -> list[str]:
        z = [f"{len(self.dateien)} Dateien ({', '.join(self.dateien)}): {self.viertelstunden} "
             f"Viertelstunden, {self.na} ohne Wert, {self.summe_abweichend} mit gesamt ≠ Summe der "
             f"Richtungen (nicht gezählt); {self.stellen} Zählstellen; Stunden in der Karte: rad "
             f"{self.stunden}; Zeilen um 2 Uhr am Tag der Sommerzeit verworfen: {self.sommerzeit}"]
        if self.kommentare:
            z.append("Kommentare der Quelle: "
                     + ", ".join(f"{k} ({n})" for k, n in self.kommentare.most_common()))
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def dateien_waehlen(ressourcen: list[dict]) -> dict[str, str]:
    """Ressourcen der Pakete -> {lokaler Name: URL}: Jahresdateien, für Jahre ohne Jahresdatei die
    Monatsdateien."""
    jahre: dict[str, str] = {}
    monate: dict[tuple[str, int], str] = {}
    for r in ressourcen:
        name, url = (r.get("name") or "").strip(), r.get("url") or ""
        if not url.lower().endswith(".csv"):
            continue
        if m := JAHR.match(name):
            jahre[m.group(1)] = url
        elif (m := MONAT.search(name)) and "Tageswerte" not in name:
            monate[(m.group(2), MONATE.index(m.group(1)) + 1)] = url
    out = {f"jahr_{j}.csv": u for j, u in jahre.items()}
    for (j, mo), u in monate.items():
        if j not in jahre:
            out[f"monat_{j}_{mo:02d}.csv"] = u
    return dict(sorted(out.items()))


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Pakete über die Suche des Portals finden (HTML; die CKAN-API sperrt es per robots.txt),
    ihre Ressourcen aus dem DCAT-Dokument oder der Seite des Pakets; Dateien holen (nur neue oder
    geänderte URLs), WFS."""
    from zaehlkarte import ckan
    from zaehlkarte.fetch import lade

    ordner = pfade.roh / q["code"]
    ordner.mkdir(parents=True, exist_ok=True)
    jetzt = datetime.now(UTC).replace(microsecond=0)
    namen = ckan.suche(q["ckan"], q["suche"])
    ressourcen = [x for n in namen for x in ckan.paket(q["ckan"], n)["resources"]]
    gewaehlt = dateien_waehlen(ressourcen)
    if not gewaehlt:
        raise ValueError(f"{q['code']}: keine 15-Minuten-Dateien gefunden")
    vorher = {}
    if (ordner / "abruf.json").exists():
        vorher = json.loads((ordner / "abruf.json").read_text(encoding="utf-8")).get("dateien", {})
    geladen = []
    for name, url in gewaehlt.items():
        if vorher.get(name) == url and (ordner / name).exists():
            continue
        lade(url, ordner / name)
        geladen.append(name)
    for alt in ordner.glob("*.csv"):
        if alt.name not in gewaehlt:
            alt.unlink()
    lade(q["wfs"], ordner / "standorte.geojson")
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "dateien": gewaehlt,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return [f"{q['code']}: {len(gewaehlt)} Dateien, davon {len(geladen)} neu geladen"]


def _tag(text: str) -> str:
    """„2008-06-01“, „20230101“, „2024.01.01“ -> „2008-06-01“."""
    z = re.sub(r"\D", "", text)
    if len(z) != 8:
        raise ValueError(f"Datum {text!r}")
    return f"{z[:4]}-{z[4:6]}-{z[6:]}"


def lies_datei(pfad: Path, bericht: Bericht):
    """-> Zeilen (Zählstelle, Tag, Stunde, Wert mit -1 = nicht gezählt)."""
    text = pfad.read_text(encoding="utf-8-sig")
    r = csv.reader(io.StringIO(text))
    kopf = [k.strip().lower() for k in next(r)]
    i = {k: kopf.index(k) for k in ("datum", "uhrzeit_start", "zaehlstelle", "richtung_1",
                                    "richtung_2", "gesamt")}
    i_k = kopf.index("kommentar") if "kommentar" in kopf else None
    for z in r:
        if not z or len(z) <= max(i.values()):
            continue
        z = [x.strip() for x in z]
        bericht.viertelstunden += 1
        if i_k is not None and z[i_k] not in ("", "NA"):
            bericht.kommentare[z[i_k]] += 1
        g, r1, r2 = z[i["gesamt"]], z[i["richtung_1"]], z[i["richtung_2"]]
        w = LEER
        if g in ("", "NA"):
            bericht.na += 1
        else:
            gesamt = round(float(g))
            beide = r1 not in ("", "NA") and r2 not in ("", "NA")
            if beide and round(float(r1)) + round(float(r2)) != gesamt:
                bericht.summe_abweichend += 1
            else:
                w = gesamt
        yield z[i["zaehlstelle"]], _tag(z[i["datum"]]), int(z[i["uhrzeit_start"]][:2]), w


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / q["code"]
    dateien = sorted(ordner.glob("*.csv"))
    if not dateien:
        raise ValueError(f"{q['code']}: keine Dateien in {ordner} – erst `zaehlkarte dauer fetch`")
    lage = {}
    geo = json.loads((ordner / "standorte.geojson").read_text(encoding="utf-8"))
    for f in geo.get("features", []):
        p = f["properties"]
        lage[p["zaehlstelle"].strip()] = (p.get("zaehlstelle_lang") or p["zaehlstelle"],
                                          float(p["latitude"]), float(p["longitude"]))
    zeilen = []
    for p in dateien:
        bericht.dateien.append(p.stem.removeprefix("jahr_").removeprefix("monat_"))
        zeilen.extend(lies_datei(p, bericht))
    namen = sorted({z[0] for z in zeilen})
    stellen, idx = [], {}
    for n in namen:
        if n not in lage:
            bericht.ohne_lage.append(n)
            continue
        lang, lat, lon = lage[n]
        idx[n] = len(stellen)
        stellen.append(Dauerstelle(quelle=q["code"], kennung=n, name=" ".join(lang.split()),
                                   abschnitt=None, richtung=None, lon=round(lon, 6),
                                   lat=round(lat, 6), land=q["land"]))
    bericht.stellen = len(stellen)
    zeilen = [z for z in zeilen if z[0] in idx]
    s = np.array([idx[z[0]] for z in zeilen], dtype=np.int64)
    t = np.array([z[1] for z in zeilen], dtype="datetime64[D]")
    h = np.array([z[2] for z in zeilen], dtype=np.int64)
    w = np.array([z[3] for z in zeilen], dtype=np.int64)
    reihe = Messreihe.leer(q["code"], t.min().astype(date), t.max().astype(date), stellen, ("rad",))
    bericht.stunden, bericht.sommerzeit = setze_lokal(reihe, "rad", s, t, h, w, anzahl=4,
                                                      rueck="einfach")
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "15-Minuten-Werte je Zählstelle (Summe beider Richtungen) zu Stunden "
                        "zusammengefasst; am Tag der Rückstellung der Uhr fehlt in der Quelle eine "
                        "Stunde, der Tag gilt als nicht vollständig gezählt")]
    return reihe
