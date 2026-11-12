"""Verkehrsdetektion Berlin (VIZ): Stundenwerte der Infrarot-Detektoren, monatsweise im
öffentlichen Archiv der Digitalen Plattform Stadtverkehr Berlin (Azure-Container).

Aufbau laut ReadMe.txt des Archivs (Stand Februar 2026) und den Dateien selbst:
- alte Qualitätssicherung 2015–2024: `JJJJ/alte_qualitaetssicherung/Messquerschnitte/
  mq_hr_JJJJ_MM.csv.gz` – Stundenwerte je Messquerschnitt (eine Richtung, alle Fahrstreifen),
  `mq_name;tag;stunde;qualitaet;q_kfz_mq_hr;…;q_lkw_mq_hr;…`. Die Quelle bildet eine Stunde nur
  bei mindestens 75 % gültigen Messintervallen, einen Messquerschnitt nur, wenn ALLE seine
  Detektoren gültig sind; fehlende Stunden fehlen als Zeile.
- neue Qualitätssicherung 2023–2025: `JJJJ/neue_qualitaetssicherung/Fahrstreifendetektoren/
  detektor(en)_JJJJ_MM.tgz` – eine CSV je Fahrstreifen-Detektor (Name wie DET_NAME_ALT der
  Stammdaten), Spaltennamen und Hüllen wechseln (CSV oder CSV.GZ im Archiv; „qkfz“ oder „kfz“;
  Vollständigkeit in Prozent oder als Anteil). Fehlende Stunden stehen als NaN darin, oft als
  zweite Zeile neben der gültigen.
- Stammdaten (Juli 2022): je Detektor Messquerschnitt, Straße, Lage, Fahrtziel, Spur,
  WGS84-Koordinaten, Kennzeichen „deinstalliert“.

Verwendet wird je Monat ein Verfahren: vor `neue_qs_ab` die Messquerschnitte der alten
Qualitätssicherung wie geliefert, ab dann die Detektoren der neuen, summiert nach der Regel der
Quelle (eine Stunde je Messquerschnitt nur, wenn jeder seiner Detektoren gültig ist; gültig =
Wert vorhanden und mindestens `vollstaendig_mindestens` % der Messintervalle). Detektoren, die
die Stammdaten als deinstalliert führen, zählen nie mit – 2025 liefern einige davon Werte,
etwa über Fahrstreifen, die laut Stammdaten heute Rad- oder Busspuren sind (Vergleich im
Werkzeug-Branch `werkzeug/dauer`, tools/dauer_vergleich.py). Wo beide Verfahren denselben Monat
abdecken, vergleicht der Bericht sie.
"""

from __future__ import annotations

import base64
import calendar
import gzip
import hashlib
import io
import json
import re
import tarfile
import urllib.parse
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, umstellungen

UA = {"User-Agent": "zaehlkarte-pipeline (+https://github.com/vizsim-lab/zaehlkarte)"}
ORDNER = "berlin_viz"
GRUPPEN = ("kfz", "lkw")  # Lkw = Klasse des Detektors
ALT = re.compile(
    r"^(\d{4})/alte_qualitaetssicherung/Messquerschnitte/mq_hr_(\d{4})_(\d{2})\.csv\.gz$")
NEU = re.compile(
    r"^(\d{4})/neue_qualitaetssicherung/Fahrstreifendetektoren/detektor(?:en)?_(\d{4})_(\d{2})\.tgz$")


@dataclass
class Bericht:
    monate_alt: list[str] = field(default_factory=list)
    monate_neu: list[str] = field(default_factory=list)
    stunden: int = 0
    unbekannt: Counter = field(default_factory=Counter)  # Messquerschnitte ohne Stammdaten
    widerspruch: int = 0  # doppelte Stunden mit verschiedenen Werten (verworfen)
    unvollstaendig_neu: int = 0  # Detektor-Stunden mit Wert, aber zu wenigen Messintervallen
    deinstalliert_neu: int = 0  # Stunden mit Wert von laut Stammdaten deinstallierten Detektoren
    ohne_datei: Counter = field(default_factory=Counter)  # Monat -> MQ ohne Detektordatei
    vergleich: Counter = field(default_factory=Counter)
    abweichung: list[float] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        z = [f"{len(self.monate_alt)} Monate alte QS ({_spanne(self.monate_alt)}), "
             f"{len(self.monate_neu)} Monate neue QS ({_spanne(self.monate_neu)}), "
             f"{self.stunden} Stunden je Messquerschnitt"]
        if self.unbekannt:
            z.append("ohne Stammdaten (nicht in der Karte): "
                     + ", ".join(f"{k} ({n} Std.)" for k, n in self.unbekannt.most_common(10)))
        if self.widerspruch:
            z.append(f"doppelte Stunden mit verschiedenen Werten verworfen: {self.widerspruch}")
        if self.unvollstaendig_neu:
            z.append("neue QS: Detektor-Stunden unter der Vollständigkeitsgrenze: "
                     f"{self.unvollstaendig_neu}")
        if self.deinstalliert_neu:
            z.append("neue QS: Stunden mit Wert von laut Stammdaten deinstallierten Detektoren "
                     f"(nicht gezählt): {self.deinstalliert_neu}")
        for monat, n in sorted(self.ohne_datei.items()):
            z.append(f"{monat}: {n} Messquerschnitte ohne Datei für einen ihrer Detektoren")
        v = self.vergleich
        if v["beide"]:
            med = float(np.median(self.abweichung)) if self.abweichung else 0.0
            z.append(f"Vergleich alte/neue QS: {v['beide']} Stunden in beiden, "
                     f"{100 * v['gleich'] / v['beide']:.1f} % gleich (±2 %), Median-Abweichung "
                     f"{100 * med:.1f} %; nur alte QS {v['nur_alt']}, nur neue QS {v['nur_neu']}")
        return z


def _spanne(monate: list[str]) -> str:
    return f"{monate[0]} bis {monate[-1]}" if monate else "–"


# ---------------------------------------------------------------- holen


def blob_liste(archiv: str) -> list[dict]:
    """Alle Dateien des Containers (Azure Blob List API, seitenweise)."""
    eintraege, marker = [], ""
    while True:
        params = {"restype": "container", "comp": "list", "maxresults": "5000"}
        if marker:
            params["marker"] = marker
        antwort = requests.get(archiv, params=params, headers=UA, timeout=120)
        antwort.raise_for_status()
        wurzel = ET.fromstring(antwort.content)
        for b in wurzel.iter("Blob"):
            p = b.find("Properties")
            eintraege.append({
                "name": b.findtext("Name"),
                "groesse": int(p.findtext("Content-Length") or 0),
                "geaendert": p.findtext("Last-Modified"),
                "md5": p.findtext("Content-MD5"),
            })
        marker = wurzel.findtext("NextMarker") or ""
        if not marker:
            return eintraege


def md5_b64(pfad: Path) -> str:
    h = hashlib.md5()  # noqa: S324 – Prüfsumme des Archivs (Content-MD5), keine Sicherheit
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return base64.b64encode(h.digest()).decode()


def gebraucht(name: str, q: dict) -> bool:
    return bool(ALT.match(name) or NEU.match(name)) or name in (q["stammdaten"], "ReadMe.txt")


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Liste, Stammdaten, ReadMe und alle Monatsarchive (MQ der alten, Detektoren der neuen QS).

    Vorhandene Dateien mit passender Prüfsumme (Content-MD5 der Liste) bleiben; die Liste mit
    Prüfsummen und Änderungsdatum liegt als `liste.json` daneben – sie gehört zur Herkunft."""
    from zaehlkarte.fetch import lade

    ordner = pfade.roh / ORDNER
    ordner.mkdir(parents=True, exist_ok=True)
    liste = blob_liste(q["archiv"])
    if not any(e["name"] == q["stammdaten"] for e in liste):
        raise ValueError(f"{q['code']}: Stammdaten {q['stammdaten']} nicht im Archiv")
    noetig = [e for e in liste if gebraucht(e["name"], q)]
    neu = 0
    for e in noetig:
        ziel = ordner / e["name"]
        if ziel.exists() and (not e["md5"] or md5_b64(ziel) == e["md5"]):
            continue
        lade(f"{q['archiv']}/{urllib.parse.quote(e['name'])}", ziel)
        if e["md5"] and (ist := md5_b64(ziel)) != e["md5"]:
            raise ValueError(f"{e['name']}: Prüfsumme {ist} statt {e['md5']}")
        neu += 1
    (ordner / "liste.json").write_text(json.dumps(noetig, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return [f"{q['code']}: {len(noetig)} Dateien ({neu} neu geladen)"]


# ---------------------------------------------------------------- lesen


@dataclass
class Stammdaten:
    stellen: list[Dauerstelle]
    index: dict[str, int]  # MQ-Kurzname -> Stelle
    detektoren: dict[str, list[str]]  # MQ-Kurzname -> Detektoren (DET_NAME_ALT)
    deinstalliert: set[str]


def lies_stammdaten(pfad: Path, q: dict) -> Stammdaten:
    import openpyxl

    wb = openpyxl.load_workbook(pfad, read_only=True, data_only=True)
    zeilen = list(wb.worksheets[0].iter_rows(values_only=True))
    kopf = [str(k or "").strip().upper() for k in zeilen[0]]
    spalte = {k: i for i, k in enumerate(kopf)}

    def wert(z, name):
        v = z[spalte[name]] if name in spalte else None
        return str(v).strip() if v is not None and str(v).strip() else None

    je_mq: dict[str, list] = {}
    for z in zeilen[1:]:
        if wert(z, "MQ_KURZNAME") and wert(z, "DET_NAME_ALT"):
            je_mq.setdefault(wert(z, "MQ_KURZNAME"), []).append(z)
    stellen, index, detektoren, weg = [], {}, {}, set()
    for mq, dets in sorted(je_mq.items()):
        erster = dets[0]
        try:
            lon = float(wert(erster, "LÄNGE (WGS84)"))
            lat = float(wert(erster, "BREITE (WGS84)"))
        except (TypeError, ValueError):
            continue
        ziel, himmel = wert(erster, "POS_DETAIL"), wert(erster, "RICHTUNG")
        richtung = (f"Richtung {ziel}" + (f" ({himmel})" if himmel else "")) if ziel else himmel
        hinweise, spuren = [], []
        for d in dets:
            name = wert(d, "DET_NAME_ALT")
            spur = wert(d, "ANNOTATION") or wert(d, "SPUR") or name
            if wert(d, "DEINSTALLIERT"):
                weg.add(name)
                hinweise.append(f"Detektor {name} ({spur}) laut Stammdaten 2022 deinstalliert")
            else:
                spuren.append(spur)
            if wert(d, "KOMMENTAR"):
                hinweise.append(f"{spur}: {wert(d, 'KOMMENTAR')} (Stammdaten 2022)")
        detektoren[mq] = [wert(d, "DET_NAME_ALT") for d in dets]
        index[mq] = len(stellen)
        stellen.append(Dauerstelle(
            quelle=q["code"], kennung=mq, name=wert(erster, "STRASSE") or mq,
            abschnitt=wert(erster, "POSITION"), richtung=richtung, lon=round(lon, 6),
            lat=round(lat, 6), land=q["land"], fahrstreifen=spuren, hinweise=hinweise,
        ))
    return Stammdaten(stellen, index, detektoren, weg)


def _monat(text: str) -> tuple[int, int]:
    j, m = text.split("-")[:2]
    return int(j), int(m)


def _doppelte(d: pd.DataFrame, schluessel: list[str], rueckstellung: set[date],
              bericht: Bericht) -> pd.DataFrame:
    """Doppelte Stunden: am Tag der Rückstellung Stunde 2 zweimal (summieren, `doppelt`),
    sonst gleiche Werte einmal, verschiedene gar nicht."""
    d = d.drop_duplicates()
    d = d.assign(doppelt=False)
    mehrfach = d.duplicated(schluessel, keep=False)
    if not mehrfach.any():
        return d
    einfach, mehr = d[~mehrfach], d[mehrfach]
    werte = [c for c in ("kfz", "lkw") if c in d.columns]
    teile = [einfach]
    for _, g in mehr.groupby(schluessel, sort=False):
        tag, stunde = g["tag"].iloc[0].date(), int(g["stunde"].iloc[0])
        if tag in rueckstellung and stunde == 2 and len(g) == 2:
            s = g.iloc[[0]].copy()
            for c in werte:
                s[c] = g[c].sum(min_count=2)
            s["doppelt"] = True
            teile.append(s)
        elif len(g[werte].drop_duplicates()) == 1:
            teile.append(g.iloc[[0]])
        else:
            bericht.widerspruch += 1
    return pd.concat(teile, ignore_index=True)


def lies_alte(pfad: Path, reihe: Messreihe, sd: Stammdaten, bericht: Bericht) -> int:
    """Messquerschnitte eines Monats (alte QS) in die Reihe. -> Anzahl gesetzter Kfz-Stunden."""
    df = pd.read_csv(pfad, sep=";", dtype={"mq_name": str, "tag": str}, usecols=lambda c: c in {
        "mq_name", "tag", "stunde", "qualitaet", "q_kfz_mq_hr", "q_lkw_mq_hr"})
    d = pd.DataFrame({
        "mq": df["mq_name"].str.strip(),
        "tag": pd.to_datetime(df["tag"], format="%d.%m.%Y", errors="coerce"),
        "stunde": pd.to_numeric(df["stunde"], errors="coerce"),
        "kfz": pd.to_numeric(df["q_kfz_mq_hr"], errors="coerce"),
        "lkw": pd.to_numeric(df["q_lkw_mq_hr"], errors="coerce") if "q_lkw_mq_hr" in df else np.nan,
    })
    qual = pd.to_numeric(df["qualitaet"], errors="coerce") if "qualitaet" in df else 1.0
    d = d[d["tag"].notna() & d["stunde"].between(0, 23) & (d["kfz"] >= 0) & ~(qual < 0.75)]
    bekannt = d["mq"].isin(sd.index)
    for mq, n in d.loc[~bekannt, "mq"].value_counts().items():
        bericht.unbekannt[mq] += int(n)
    d = d[bekannt]
    rueck = {umstellungen(j)[1] for j in d["tag"].dt.year.unique()}
    d = _doppelte(d, ["mq", "tag", "stunde"], rueck, bericht)
    return _schreibe(reihe, d)


def _schreibe(reihe: Messreihe, d: pd.DataFrame) -> int:
    """Zeilen (mq, tag, stunde, kfz, lkw, doppelt) in die Felder der Reihe. -> Kfz-Stunden."""
    idx = {st.kennung: i for i, st in enumerate(reihe.stellen)}
    s = d["mq"].map(idx).to_numpy()
    t = ((d["tag"] - pd.Timestamp(reihe.von)).dt.days).to_numpy()
    h = d["stunde"].astype(int).to_numpy()
    innen = (t >= 0) & (t < reihe.tage)
    s, t, h = s[innen], t[innen], h[innen]
    n = 0
    for g in ("kfz", "lkw"):
        w = d[g].to_numpy(dtype=float)[innen]
        ok = ~np.isnan(w) & (w >= 0)
        reihe.werte[g][s[ok], t[ok], h[ok]] = np.rint(w[ok]).astype(np.int32)
        if g == "kfz":
            n = int(ok.sum())
    dop = d["doppelt"].to_numpy(dtype=bool)[innen]
    reihe.doppelt[s[dop], t[dop]] = True
    return n


_SPALTEN = {
    "datum": ("datum (ortszeit)", "datum"),
    "stunde": ("stunde des tages (ortszeit)", "stunde"),
    "kfz": ("qkfz", "kfz"),
    "lkw": ("qlkw", "lkw"),
    "voll": ("vollständigkeit", "vollstaendigkeit", "datapoints_rel"),
}


def _detektor_csv(inhalt: bytes, jahr: int, monat: int, mindestens: float,
                  rueckstellung: set[date], bericht: Bericht) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(inhalt), sep=";", dtype=str)
    namen = {c.strip().lower(): c for c in df.columns}
    spalte = {k: next((namen[n] for n in kandidaten if n in namen), None)
              for k, kandidaten in _SPALTEN.items()}
    if not spalte["datum"] or not spalte["stunde"] or not spalte["kfz"]:
        raise ValueError(f"unbekannte Spalten: {list(df.columns)}")
    voll = pd.to_numeric(df[spalte["voll"]], errors="coerce") if spalte["voll"] else None
    if voll is not None and (spalte["voll"].strip().lower() == "datapoints_rel" or voll.max() <= 1):
        voll = voll * 100  # Anteil -> Prozent
    d = pd.DataFrame({
        "tag": pd.to_datetime(df[spalte["datum"]].str.strip(), format="%Y-%m-%d", errors="coerce"),
        "stunde": pd.to_numeric(df[spalte["stunde"]], errors="coerce"),
        "kfz": pd.to_numeric(df[spalte["kfz"]], errors="coerce"),
        "lkw": pd.to_numeric(df[spalte["lkw"]], errors="coerce") if spalte["lkw"] else np.nan,
    })
    d = d[d["tag"].notna() & d["stunde"].between(0, 23) & d["kfz"].notna()]
    d = d[(d["tag"].dt.year == jahr) & (d["tag"].dt.month == monat)]
    if voll is not None:
        genug = voll.reindex(d.index) >= mindestens
        bericht.unvollstaendig_neu += int((~genug).sum())
        d = d[genug]
    return _doppelte(d, ["tag", "stunde"], rueckstellung, bericht)


def lies_neue(pfad: Path, reihe: Messreihe, sd: Stammdaten, mindestens: float,
              bericht: Bericht, jahr: int, monat: int) -> int:
    """Detektoren eines Monats (neue QS) zu Messquerschnitten summieren -> Kfz-Stunden."""
    rueck = {umstellungen(jahr)[1]}
    tage = calendar.monthrange(jahr, monat)[1]
    erster = (date(jahr, monat, 1) - reihe.von).days
    det: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    with tarfile.open(pfad, mode="r:*") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            name = re.sub(r"\.csv(\.gz)?$", "", Path(m.name).name)
            inhalt = tf.extractfile(m).read()
            if m.name.lower().endswith(".gz"):
                inhalt = gzip.decompress(inhalt)
            d = _detektor_csv(inhalt, jahr, monat, mindestens, rueck, bericht)
            if name in sd.deinstalliert:
                bericht.deinstalliert_neu += len(d)
                continue
            kfz = np.full((tage, 24), np.nan)
            lkw = np.full((tage, 24), np.nan)
            dop = np.zeros((tage, 24), dtype=bool)
            t = (d["tag"].dt.day - 1).to_numpy()
            h = d["stunde"].astype(int).to_numpy()
            kfz[t, h] = d["kfz"].to_numpy()
            lkw[t, h] = d["lkw"].to_numpy()
            dop[t, h] = d["doppelt"].to_numpy()
            det[name] = (kfz, lkw, dop)
    n = 0
    ohne = 0
    for mq, i in sd.index.items():
        # gebraucht: jeder Detektor des Messquerschnitts, der nicht als deinstalliert gilt
        noetig = [x for x in sd.detektoren[mq] if x not in sd.deinstalliert]
        if not noetig:
            continue
        if any(x not in det for x in noetig):
            ohne += 1
            continue
        kfz = np.stack([det[x][0] for x in noetig])
        lkw = np.stack([det[x][1] for x in noetig])
        gueltig = np.isfinite(kfz).all(axis=0)
        bereich = slice(max(erster, 0), min(erster + tage, reihe.tage))
        a = bereich.start - erster
        b = a + (bereich.stop - bereich.start)
        summe = np.where(gueltig, np.nansum(kfz, axis=0), LEER)[a:b]
        reihe.werte["kfz"][i, bereich] = np.rint(summe).astype(np.int32)
        lkw_ok = gueltig & np.isfinite(lkw).all(axis=0)
        lkw_summe = np.where(lkw_ok, np.nansum(lkw, axis=0), LEER)[a:b]
        reihe.werte["lkw"][i, bereich] = np.rint(lkw_summe).astype(np.int32)
        n += int(gueltig[a:b].sum())
        dop = np.stack([det[x][2] for x in noetig]).any(axis=0) & gueltig
        reihe.doppelt[i, bereich] |= dop.any(axis=1)[a:b]
    if ohne:
        bericht.ohne_datei[f"{jahr}-{monat:02d}"] = ohne
    return n


def vergleiche(alt: Messreihe, neu: Messreihe, bericht: Bericht) -> None:
    """Gleiche Monate in beiden Verfahren: Anteil gleicher Kfz-Stunden (±2 %)."""
    a, n = alt.werte["kfz"], neu.werte["kfz"]
    beide = (a >= 0) & (n >= 0)
    bericht.vergleich["beide"] += int(beide.sum())
    bericht.vergleich["nur_alt"] += int(((a >= 0) & (n < 0)).sum())
    bericht.vergleich["nur_neu"] += int(((a < 0) & (n >= 0)).sum())
    if beide.any():
        x, y = a[beide].astype(float), n[beide].astype(float)
        rel = np.abs(x - y) / np.maximum(x, 1)
        bericht.vergleich["gleich"] += int(((np.abs(x - y) <= 1) | (rel <= 0.02)).sum())
        bericht.abweichung.extend(np.quantile(rel, [0.5]).tolist())


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    ordner = pfade.roh / ORDNER
    sd = lies_stammdaten(ordner / q["stammdaten"], q)
    alte, neue = {}, {}
    for pfad in sorted(ordner.rglob("*")):
        rel = pfad.relative_to(ordner).as_posix()
        if m := ALT.match(rel):
            alte[(int(m[2]), int(m[3]))] = pfad
        elif m := NEU.match(rel):
            neue[(int(m[2]), int(m[3]))] = pfad
    monate = sorted(set(alte) | set(neue))
    if not monate:
        raise ValueError(f"{q['code']}: keine Monatsarchive in {ordner} – "
                         "erst `zaehlkarte dauer fetch`")
    ab = _monat(str(q["neue_qs_ab"]))
    mindestens = float(q.get("vollstaendig_mindestens", 75))
    von = date(*monate[0], 1)
    bis = date(monate[-1][0], monate[-1][1], calendar.monthrange(*monate[-1])[1])
    reihe = Messreihe.leer(q["code"], von, bis, sd.stellen, GRUPPEN)
    verfahren = {}
    for jm in monate:
        if jm < ab and jm in alte:
            n = lies_alte(alte[jm], reihe, sd, bericht)
            bericht.monate_alt.append(f"{jm[0]}-{jm[1]:02d}")
            verfahren[jm] = "alt"
            if jm in neue:  # zum Vergleich: dasselbe Monat nach dem neuen Verfahren
                tag0, tag1 = date(*jm, 1), date(*jm, calendar.monthrange(*jm)[1])
                stueck = Messreihe.leer(q["code"], tag0, tag1, sd.stellen, GRUPPEN)
                lies_neue(neue[jm], stueck, sd, mindestens, Bericht(), *jm)
                teil = Messreihe(q["code"], tag0, stueck.tage, sd.stellen,
                                 {g: w[:, (tag0 - von).days:(tag1 - von).days + 1]
                                  for g, w in reihe.werte.items()}, stueck.doppelt)
                vergleiche(teil, stueck, bericht)
        elif jm >= ab and jm in neue:
            n = lies_neue(neue[jm], reihe, sd, mindestens, bericht, *jm)
            bericht.monate_neu.append(f"{jm[0]}-{jm[1]:02d}")
            verfahren[jm] = "neu"
        else:
            continue
        bericht.stunden += n
    reihe.verfahren = _abschnitte(verfahren)
    return reihe


def _abschnitte(verfahren: dict[tuple[int, int], str]) -> list[tuple[date, date, str]]:
    """Zusammenhängende Monate je Verfahren -> [(von, bis, Text)] für die Hinweise."""
    text = {
        "alt": "alte Qualitätssicherung: Stundenwerte je Messquerschnitt wie geliefert",
        "neu": "neue Qualitätssicherung: Fahrstreifen von der Zählkarte je Messquerschnitt "
               "summiert (nur Stunden, in denen jeder Fahrstreifen gültig gezählt ist)",
    }
    out: list[tuple[date, date, str]] = []
    for jm, v in sorted(verfahren.items()):
        anfang, ende = date(*jm, 1), date(*jm, calendar.monthrange(*jm)[1])
        if out and out[-1][2] == text[v] and (anfang - out[-1][1]).days == 1:
            out[-1] = (out[-1][0], ende, text[v])
        else:
            out.append((anfang, ende, text[v]))
    return out
