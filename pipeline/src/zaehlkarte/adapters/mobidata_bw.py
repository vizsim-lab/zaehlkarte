"""MobiData BW: 24-Stunden-Zählungen im Schussental (Ravensburg, Weingarten, Berg, Baienfurt,
Baindt), alle vom Stadtplanungsamt Ravensburg aufbereitet, per Video an Kreuzungen gezählt.

Ein Adapter für alle fünf Kommunen (sources.yaml verweist per `adapter: mobidata_bw`); je
Kommune zwei Dateien:
- Übersichts-Excel: je Zählstelle ID, NAME, Lage und bis zu vier Zählungen als Spaltenblöcke
  KFZ_n / RAD_n / FUSSGAENGER_n / SV_n / DATUM_n (24-Stunden-Summen; ein Kopf heißt `Datum_4`).
  Achtung: KFZ_n ist dort nur die Klasse PKW, SV_n die Klasse LKW – nachgerechnet an allen
  Zählungen mit Excel (Ravensburg 1000, 16.11.2023: KFZ 14.217 = PKW, SV 1.919 = LKW). Kfz
  insgesamt ist also KFZ_n + SV_n.
- ZIP mit je Zählung einer Excel und einer PDF (`<ID>/<TT.MM.JJJJ>/<Name>.xlsx`, manchmal ohne
  Datumsordner). Blatt „Rohdaten“: Zeit, Quelle, Ziel, Abbiegeart, Klasse, Volumen – je
  15 Minuten (dreimal 10 Minuten) über 24 Stunden.

Zählungen mit Excel bekommen Stundenwerte; Zählungen, die nur in der Übersicht stehen, nur die
Tagessummen. Klassen der Quelle: PKW, LKW, Fahrrad, Fußgänger. Schwerverkehr = Klasse „LKW“
(ob samt Lieferwagen und Bussen, sagt die Quelle nicht).
Fußgänger = Querungen an den ausgewerteten Überwegen, nicht alle Fußwege der Kreuzung.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

KLASSEN = {"pkw": ("kfz",), "lkw": ("kfz", "sv"), "fahrrad": ("rad",), "fußgänger": ("fuss",)}
_ZEIT = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})")
_DATUM = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
_STRASSE = re.compile(r"^([ABLK])\s?(\d+)$")  # "B32", "L 288"
_PLZ = re.compile(r"^\d{5}$")
SPALTEN = {"KFZ": "kfz", "RAD": "rad", "FUSSGAENGER": "fuss", "SV": "sv"}


@dataclass
class Bericht:
    excel: int = 0
    nur_uebersicht: int = 0
    abweichung: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        out = [f"{self.excel} Zählungen mit Stundenwerten, {self.nur_uebersicht} nur Tagessummen"]
        return out + [f"Abweichung zur Übersicht: {a}" for a in self.abweichung[:10]]


def name_aus(roh: object, ort: str) -> str:
    """'B32_Ulmerstraße_88212_Ravensburg' -> 'B 32 / Ulmerstraße'."""
    teile = [t.strip() for t in str(roh).split("_") if t.strip()]
    teile = [t for t in teile if not _PLZ.match(t) and t.lower() != ort.lower()]
    schoen = []
    for t in teile:
        m = _STRASSE.match(t.replace(" ", ""))
        schoen.append(f"{m.group(1)} {m.group(2)}" if m else t)
    return " / ".join(schoen)


def _zahl(v: object) -> int | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int | float):
        return int(round(v))
    s = str(v).replace("\xa0", "").strip()
    return int(s) if s.isdigit() else None


def _datum(v: object) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    m = _DATUM.match(str(v or "").strip())
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else None


def lese_uebersicht(pfad: Path) -> tuple[dict[str, dict], dict[tuple[str, date], dict]]:
    """(Stellen je ID, Tagessummen je (ID, Datum)) aus der Übersichts-Excel."""
    import openpyxl

    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    zeilen = list(wb.worksheets[0].iter_rows(values_only=True))
    wb.close()
    kopf = [str(c or "").strip().upper() for c in zeilen[0]]
    stellen, summen = {}, {}
    for z in zeilen[1:]:
        r = dict(zip(kopf, z, strict=False))
        if r.get("ID") is None:
            continue
        sid = str(_zahl(r["ID"]) or r["ID"]).strip()
        try:
            lat, lon = float(r["BREITENGRAD"]), float(r["LAENGENGRAD"])
        except (TypeError, ValueError):
            lat = lon = None
        stellen[sid] = {"name": r.get("NAME"), "lon": lon, "lat": lat}
        for n in range(1, 5):
            tag = _datum(r.get(f"DATUM_{n}"))
            if tag is None:
                continue
            werte = {g: _zahl(r.get(f"{k}_{n}")) for k, g in SPALTEN.items()}
            # KFZ_n = nur PKW (siehe Modulkopf) -> Kfz = PKW + LKW, sonst unbekannt
            pkw = werte["kfz"]
            sv = werte["sv"]
            werte["kfz"] = pkw + sv if pkw is not None and sv is not None else None
            summen[(sid, tag)] = werte
    return stellen, summen


def lese_zaehlung(pfad: Path) -> dict:
    """Eine Zählungs-Excel -> {datum, lon, lat, intervall, stunden: {Gruppe: [24 Werte]}}."""
    import openpyxl

    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    meta = {
        str(r[0]).strip(): r[1]
        for r in wb["Zusammenfassung"].iter_rows(values_only=True)
        if r and r[0] is not None and len(r) > 1
    }
    m = re.match(r"\s*(\d+):(\d+)", str(meta.get("Zeitintervall") or "0:15"))
    intervall = int(m.group(1)) * 60 + int(m.group(2)) if m else 15
    start = _ZEIT.search(str(meta.get("Dauer") or ""))
    tag = date(int(start.group(3)), int(start.group(2)), int(start.group(1))) if start else None
    tag = _datum(pfad.parent.name) or tag
    werte: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    intervalle: dict[str, dict[int, set]] = defaultdict(lambda: defaultdict(set))
    klassen = set()
    for row in wb["Rohdaten"].iter_rows(min_row=2, values_only=True):
        if len(row) < 8 or row[6] is None:
            continue
        zm = _ZEIT.search(str(row[0]))
        if not zm:
            continue
        if tag and date(int(zm.group(3)), int(zm.group(2)), int(zm.group(1))) != tag:
            continue  # Intervall des Folgetags (Ende 00:00)
        klasse = str(row[6]).strip().lower()
        klassen.add(klasse)
        h, minute = int(zm.group(4)), int(zm.group(5))
        intervalle[klasse][h].add(minute)
        werte[klasse][h] += _zahl(row[7]) or 0
    wb.close()
    stunden: dict[str, list[int | None]] = {}
    for klasse, gruppen in KLASSEN.items():
        if klasse not in klassen:
            continue
        reihe = [
            werte[klasse][h] if len(intervalle[klasse][h]) * intervall >= 60 else None
            for h in range(24)
        ]
        for g in gruppen:
            if g not in stunden:
                stunden[g] = reihe
            else:
                stunden[g] = [
                    None if a is None or b is None else a + b
                    for a, b in zip(stunden[g], reihe, strict=True)
                ]
    if "pkw" not in klassen:  # Kfz nur mit Pkw – sonst wäre es nur der Lkw-Teil
        stunden.pop("kfz", None)
    koord = re.findall(r"-?\d+\.\d+", str(meta.get("Koordinaten") or ""))
    lat, lon = (float(koord[0]), float(koord[1])) if len(koord) == 2 else (None, None)
    return {
        "datum": tag,
        "lon": lon,
        "lat": lat,
        "intervall": intervall,
        "stunden": stunden,
        "klassen": sorted(klassen),
    }


def _id_aus_pfad(pfad: Path) -> str | None:
    for teil in (pfad.parent.name, pfad.parent.parent.name):
        if teil.isdigit():
            return teil
    return None


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "mobidata" / quelle["paket"]
    stellen, summen = lese_uebersicht(ordner / quelle["uebersicht"])
    ort = quelle["name"]
    gesehen: set[tuple[str, date]] = set()

    def zaehlung(sid: str, tag: date | None, **kw) -> Zaehlung:
        s = stellen.get(sid, {})
        dateiname = kw.pop("dateiname", None)
        lon = kw.pop("lon", None) or s.get("lon")
        lat = kw.pop("lat", None) or s.get("lat")
        return Zaehlung(
            quelle=quelle["code"],
            kennung=f"{sid}_{tag:%Y%m%d}" if tag else sid,
            stelle_roh=sid,
            name=name_aus(s.get("name") or dateiname or sid, ort),
            typ="K",
            lon=lon,
            lat=lat,
            lage="quelle" if lon is not None else None,
            datum=tag,
            fenster=[(0, 24 * 60)],
            land=quelle["land"],
            rohdatei=quelle.get("portal"),
            **kw,
        )

    for pfad in sorted((ordner / "zip").rglob("*.xlsx")):
        sid = _id_aus_pfad(pfad)
        if sid is None:
            continue
        d = lese_zaehlung(pfad)
        hinweise = []
        soll = summen.get((sid, d["datum"])) if d["datum"] else None
        if soll:
            for g, wert in soll.items():
                reihe = d["stunden"].get(g)
                ist = sum(reihe) if reihe and None not in reihe else None
                if wert and ist is not None and abs(ist - wert) > max(2, 0.02 * wert):
                    bericht.abweichung.append(f"{sid} {d['datum']} {g}: {ist} statt {wert}")
                    hinweise.append(f"Übersicht nennt {g} = {wert}, Stundenwerte ergeben {ist}")
        gesehen.add((sid, d["datum"]))
        bericht.excel += 1
        yield zaehlung(
            sid,
            d["datum"],
            lon=d["lon"],
            lat=d["lat"],
            intervall=d["intervall"],
            h0=0,
            stunden=d["stunden"],
            kategorien=",".join(d["klassen"]),
            hinweise=hinweise,
            dateiname=pfad.stem,
        )
    for (sid, tag), werte in sorted(summen.items()):
        if (sid, tag) in gesehen or not any(werte.values()):
            continue
        bericht.nur_uebersicht += 1
        if werte.get("kfz") is None:
            werte["sv"] = None
        yield zaehlung(
            sid,
            tag,
            intervall=None,
            summen={g: v for g, v in werte.items() if v is not None},
            kategorien="Übersicht: KFZ,RAD,FUSSGAENGER,SV",
            hinweise=["nur Tagessummen aus der Übersicht (keine Excel im ZIP)"],
        )
