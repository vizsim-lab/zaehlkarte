"""Gedächtnis der Quellen, die ihre Stundenwerte nur kurz vorhalten (Hamburg: zwei Monate,
Leipzig: 31 Tage): Die Zählkarte hebt die Stunden selbst auf.

Je UTC-Monat eine Datei `gedaechtnis/stunden_JJJJ-MM.csv.gz` im Rohdatenordner der Quelle: je
Stelle, Gruppe und UTC-Tag die 24 Werte wie geliefert (leer = nicht geliefert). Liefert die Quelle
auch Tageswerte (Hamburg, Layer „1-Tag“; die Zählkarte nimmt sie vor der ersten gezählten Stunde
einer Stelle, `Messreihe.tageswerte`), stehen sie je Jahr in `gedaechtnis/tage_JJJJ.csv.gz`: je
Stelle, Gruppe und Monat die Werte der Tage 1–31 wie geliefert, nach dem Tag der Quelle (Hamburg:
Ortstage). Der Workflow
„Dauerzählstellen bauen“ legt die Dateien im Release `dauerzaehlstellen` ab und holt sie vor dem
nächsten Lauf zurück (pipeline/werkzeuge/gedaechtnis.py) – nie mit weniger Werten; eine zweite
Kopie jeder Fassung liegt im Release `gedaechtnis-kopie-JJJJ`.

`frische` sagt, ob das Gedächtnis noch wächst: Ist die jüngste Stunde einer Quelle älter als ein
paar Tage, scheitert ihr Abruf seit mindestens einem Wochenlauf – und was die Quelle danach
nicht mehr vorhält, fehlt für immer (`zaehlkarte dauer frische`, letzter Schritt des Workflows).
"""

from __future__ import annotations

import csv
import gzip
import io
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np

KOPF = ["stelle", "gruppe", "tag", *(f"h{h:02d}" for h in range(24))]
KOPF_TAGE = ["stelle", "gruppe", "monat", *(f"d{d:02d}" for d in range(1, 32))]

Gedaechtnis = dict[tuple[str, str, str], list[int | None]]  # (Stelle, Gruppe, UTC-Tag) -> 24
# (Stelle, Gruppe, Monat JJJJ-MM) -> 31 Tageswerte (Tag 1–31; leer = nicht geliefert)
Tagesgedaechtnis = dict[tuple[str, str, str], list[int | None]]


def _lies_datei(pfad: Path, g: dict, kopf: list[str] = KOPF) -> None:
    with gzip.open(pfad, "rt", encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter=";")
        if next(r, None) != kopf:
            raise ValueError(f"{pfad.name}: unerwarteter Kopf")
        for z in r:
            g[(z[0], z[1], z[2])] = [int(x) if x != "" else None for x in z[3:len(kopf)]]


def lies(ordner: Path) -> Gedaechtnis:
    g: Gedaechtnis = {}
    for pfad in sorted(ordner.glob("stunden_*.csv.gz")):
        _lies_datei(pfad, g)
    return g


def lies_tage(ordner: Path) -> Tagesgedaechtnis:
    g: Tagesgedaechtnis = {}
    for pfad in sorted(ordner.glob("tage_*.csv.gz")):
        _lies_datei(pfad, g, KOPF_TAGE)
    return g


def juengste_stunde(ordner: Path) -> datetime | None:
    """Jüngste gelieferte Stunde (Beginn, UTC) – aus der jüngsten Monatsdatei mit einem Wert."""
    for pfad in sorted(ordner.glob("stunden_*.csv.gz"), reverse=True):
        g: Gedaechtnis = {}
        _lies_datei(pfad, g)
        if (t := letzte_stunde(g)) is not None:
            return t
    return None


def frische(roh: Path, codes: list[str], jetzt: datetime, tage: float
            ) -> tuple[list[str], list[str]]:
    """-> (Zeilen für den Bericht, Codes der Quellen, deren jüngste Stunde älter als `tage` ist
    oder die gar keine haben). `codes`: die Quellen mit Gedächtnis, `roh`: pipeline/data/raw."""
    zeilen, alt = [], []
    for code in codes:
        t = juengste_stunde(roh / code / "gedaechtnis")
        if t is None:
            zeilen.append(f"Gedächtnis {code}: keine Stunden")
            alt.append(code)
            continue
        alter = (jetzt - t).total_seconds() / 86400
        vor = f"{alter:.1f}".replace(".", ",")
        z = f"Gedächtnis {code}: jüngste Stunde {t:%d.%m.%Y, %H} Uhr UTC (vor {vor} Tagen)"
        if alter > tage:
            z += (f" – älter als {tage:g} Tage: Der Abruf scheitert seit mindestens einem "
                  "Wochenlauf, und die Quelle hält die Stunden nur kurz vor")
            alt.append(code)
        zeilen.append(z)
    return zeilen, alt


def _schreibe(ordner: Path, g: dict, kopf: list[str], datei: str, laenge: int) -> list[str]:
    """Je Datei (`datei` mit den ersten `laenge` Zeichen des Schlüssels: Monat bzw. Jahr) sortiert
    und ohne Zeitstempel im gzip – gleicher Inhalt, gleiche Bytes (der Workflow lädt nur Geändertes
    hoch). -> geänderte Dateien."""
    ordner.mkdir(parents=True, exist_ok=True)
    je_datei: dict[str, list] = defaultdict(list)
    for (stelle, gruppe, zeit), werte in g.items():
        je_datei[zeit[:laenge]].append((stelle, gruppe, zeit, werte))
    geaendert = []
    for teil, zeilen in sorted(je_datei.items()):
        puffer = io.StringIO()
        w = csv.writer(puffer, delimiter=";", lineterminator="\n")
        w.writerow(kopf)
        for stelle, gruppe, zeit, werte in sorted(zeilen, key=lambda z: z[:3]):
            w.writerow([stelle, gruppe, zeit, *("" if v is None else v for v in werte)])
        daten = gzip.compress(puffer.getvalue().encode("utf-8"), compresslevel=9, mtime=0)
        pfad = ordner / datei.format(teil)
        if not pfad.exists() or pfad.read_bytes() != daten:
            pfad.write_bytes(daten)
            geaendert.append(pfad.name)
    return geaendert


def schreibe(ordner: Path, g: Gedaechtnis) -> list[str]:
    """Je UTC-Monat eine Datei `stunden_JJJJ-MM.csv.gz`. -> geänderte Dateien."""
    return _schreibe(ordner, g, KOPF, "stunden_{}.csv.gz", 7)


def schreibe_tage(ordner: Path, g: Tagesgedaechtnis) -> list[str]:
    """Je Jahr eine Datei `tage_JJJJ.csv.gz`. -> geänderte Dateien."""
    return _schreibe(ordner, g, KOPF_TAGE, "tage_{}.csv.gz", 4)


def setze(g: Gedaechtnis, stelle: str, gruppe: str, utc: datetime, wert: int) -> None:
    """Einen Stundenwert (Beginn der Stunde in UTC) eintragen; ein neuer ersetzt den alten."""
    tag = utc.astimezone(UTC).date().isoformat()
    g.setdefault((stelle, gruppe, tag), [None] * 24)[utc.astimezone(UTC).hour] = wert


def setze_tag(g: Tagesgedaechtnis, stelle: str, gruppe: str, tag: date, wert: int) -> None:
    """Einen Tageswert (Tag der Quelle) eintragen; ein neuer ersetzt den alten."""
    g.setdefault((stelle, gruppe, tag.isoformat()[:7]), [None] * 31)[tag.day - 1] = wert


def letzter_tag(g: Tagesgedaechtnis) -> date | None:
    letzter = None
    for (_, _, monat), werte in g.items():
        d = max((i for i, v in enumerate(werte) if v is not None), default=None)
        if d is not None:
            t = date.fromisoformat(f"{monat}-01") + timedelta(days=d)
            letzter = t if letzter is None or t > letzter else letzter
    return letzter


def letzte_stunde(g: Gedaechtnis) -> datetime | None:
    letzte = None
    for (_, _, tag), werte in g.items():
        h = max((i for i, v in enumerate(werte) if v is not None), default=None)
        if h is not None:
            t = datetime.fromisoformat(tag).replace(tzinfo=UTC) + timedelta(hours=h)
            letzte = t if letzte is None or t > letzte else letzte
    return letzte


def felder(g: Gedaechtnis, gruppe: str, idx: dict[str, int]
           ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Alle Stunden einer Gruppe als Felder (Stelle, UTC-Stunde als datetime64[h], Wert) – nur
    Stellen aus `idx` (Kennung -> Index der Stelle), nur gelieferte Stunden. None: keine."""
    zeilen = [(idx[st], tag, werte) for (st, gr, tag), werte in g.items()
              if gr == gruppe and st in idx]
    if not zeilen:
        return None
    s_ = np.array([z[0] for z in zeilen], dtype=np.int64)
    basis = np.array([z[1] for z in zeilen], dtype="datetime64[h]")
    w_ = np.array([[-1 if v is None else v for v in z[2]] for z in zeilen], dtype=np.int64)
    da = w_ >= 0
    t_ = (basis[:, None] + np.arange(24).astype("timedelta64[h]"))[da]
    return np.repeat(s_, da.sum(axis=1)), t_, w_[da]


def tagesfelder(g: Tagesgedaechtnis, gruppe: str, idx: dict[str, int]
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Alle Tageswerte einer Gruppe als Felder (Stelle, Tag als datetime64[D], Wert) – nur Stellen
    aus `idx`, nur gelieferte Tage (Tage 29–31, die es im Monat nicht gibt, bleiben leer)."""
    zeilen = [(idx[st], monat, werte) for (st, gr, monat), werte in g.items()
              if gr == gruppe and st in idx]
    if not zeilen:
        return None
    s_ = np.array([z[0] for z in zeilen], dtype=np.int64)
    basis = np.array([f"{z[1]}-01" for z in zeilen], dtype="datetime64[D]")
    w_ = np.array([[-1 if v is None else v for v in z[2]] for z in zeilen], dtype=np.int64)
    tage = basis[:, None] + np.arange(31).astype("timedelta64[D]")
    im_monat = tage.astype("datetime64[M]") == basis.astype("datetime64[M]")[:, None]
    da = (w_ >= 0) & im_monat
    return np.repeat(s_, da.sum(axis=1)), tage[da], w_[da]
