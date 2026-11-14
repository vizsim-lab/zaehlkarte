"""Gedächtnis der Quellen, die ihre Stundenwerte nur kurz vorhalten (Hamburg: zwei Monate,
Leipzig: 31 Tage): Die Zählkarte hebt die Stunden selbst auf.

Je UTC-Monat eine Datei `gedaechtnis/stunden_JJJJ-MM.csv.gz` im Rohdatenordner der Quelle: je
Stelle, Gruppe und UTC-Tag die 24 Werte wie geliefert (leer = nicht geliefert). Der Workflow
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
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

KOPF = ["stelle", "gruppe", "tag", *(f"h{h:02d}" for h in range(24))]

Gedaechtnis = dict[tuple[str, str, str], list[int | None]]  # (Stelle, Gruppe, UTC-Tag) -> 24


def _lies_datei(pfad: Path, g: Gedaechtnis) -> None:
    with gzip.open(pfad, "rt", encoding="utf-8", newline="") as f:
        r = csv.reader(f, delimiter=";")
        if next(r, None) != KOPF:
            raise ValueError(f"{pfad.name}: unerwarteter Kopf")
        for z in r:
            g[(z[0], z[1], z[2])] = [int(x) if x != "" else None for x in z[3:27]]


def lies(ordner: Path) -> Gedaechtnis:
    g: Gedaechtnis = {}
    for pfad in sorted(ordner.glob("stunden_*.csv.gz")):
        _lies_datei(pfad, g)
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


def schreibe(ordner: Path, g: Gedaechtnis) -> list[str]:
    """Je UTC-Monat eine Datei, sortiert und ohne Zeitstempel im gzip – gleicher Inhalt, gleiche
    Bytes (der Workflow lädt nur Geändertes hoch). -> geänderte Dateien."""
    ordner.mkdir(parents=True, exist_ok=True)
    je_monat: dict[str, list] = defaultdict(list)
    for (stelle, gruppe, tag), werte in g.items():
        je_monat[tag[:7]].append((stelle, gruppe, tag, werte))
    geaendert = []
    for monat, zeilen in sorted(je_monat.items()):
        puffer = io.StringIO()
        w = csv.writer(puffer, delimiter=";", lineterminator="\n")
        w.writerow(KOPF)
        for stelle, gruppe, tag, werte in sorted(zeilen, key=lambda z: z[:3]):
            w.writerow([stelle, gruppe, tag, *("" if v is None else v for v in werte)])
        daten = gzip.compress(puffer.getvalue().encode("utf-8"), compresslevel=9, mtime=0)
        pfad = ordner / f"stunden_{monat}.csv.gz"
        if not pfad.exists() or pfad.read_bytes() != daten:
            pfad.write_bytes(daten)
            geaendert.append(pfad.name)
    return geaendert


def setze(g: Gedaechtnis, stelle: str, gruppe: str, utc: datetime, wert: int) -> None:
    """Einen Stundenwert (Beginn der Stunde in UTC) eintragen; ein neuer ersetzt den alten."""
    tag = utc.astimezone(UTC).date().isoformat()
    g.setdefault((stelle, gruppe, tag), [None] * 24)[utc.astimezone(UTC).hour] = wert


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
