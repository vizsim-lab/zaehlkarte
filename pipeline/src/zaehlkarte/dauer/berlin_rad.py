"""Berlin: Zählstellen für den Radverkehr (Senatsverwaltung, Abt. Verkehrsmanagement) – eine
Excel-Datei mit den Stundenwerten aller Zählstellen, ein Blatt je Jahr seit 2012, einmal jährlich
nach Abschluss des Zähljahres veröffentlicht.

Aufbau (Stand November 2026, Datei vom 25.06.2026, Werkzeug-Branch `werkzeug/dauer2`):
- Blätter „Jahresdatei JJJJ“: Spalte A die Stunde (Ortszeit, Beginn), dann je Zählstelle eine
  Spalte, Kopf „<Kennung>\\n<Inbetriebnahme>“ (etwa „02-MI-JAN-N“, meist eine Richtung). Das Blatt
  2012 reicht bis Ende 2013 – doppelte Stunden mit gleichem Wert zählen einmal, mit verschiedenem
  gar nicht.
- Farbig markierte Zellen (Blatt „Legende“): orange „keine (0) oder unplausible Zähldaten“, hellgelb
  „keine Zähldaten“, Theme-Farbe 5 „Datenlücken/fehlerhafte Daten durch Rekonstruktion aufgefüllt“;
  dazu Theme-Farbe 7 an der fehlenden Stunde der Sommerzeit. Jede markierte Zelle gilt als nicht
  gezählt – rekonstruierte Werte kommen nicht in die Karte. Leere Zelle = nicht gezählt.
- Rückstellung der Uhr: eine Zeile um 2 Uhr mit beiden Stunden (im Mittel 1,7-mal so viel wie 1 und
  3 Uhr, an anderen Sonntagen 0,9-mal; 2012–2025) -> `doppelt`. Sommerzeit: 2 Uhr leer.
- Blatt „Standortdaten“: Kennung, Beschreibung (mit Richtung), Breite, Länge, Installationsdatum.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.modell import LEER, Dauerstelle, Messreihe, kuerze, setze_lokal

DATEI = "gesamtdatei-stundenwerte.xlsx"


@dataclass
class Bericht:
    blaetter: list[str] = field(default_factory=list)
    zellen: int = 0
    markiert: Counter = field(default_factory=Counter)  # Füllung -> Zellen (nicht gezählt)
    leer: int = 0
    doppelt_gleich: int = 0
    doppelt_anders: int = 0
    stellen: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    stunden: int = 0

    def zeilen(self) -> list[str]:
        z = [f"Blätter {self.blaetter[0]}–{self.blaetter[-1]}: {self.zellen} Zellen, davon "
             f"{self.leer} leer; markiert (nicht gezählt): "
             + ", ".join(f"{k} {n}" for k, n in self.markiert.most_common()),
             f"doppelte Stunden: {self.doppelt_gleich} gleich (einmal gezählt), "
             f"{self.doppelt_anders} verschieden (nicht gezählt); {self.stellen} Zählstellen; "
             f"Stunden in der Karte: rad {self.stunden}"]
        if self.ohne_lage:
            z.append(f"ohne Lage (nicht in der Karte): {', '.join(self.ohne_lage)}")
        return z


def hole(q: dict, pfade: Pfade) -> list[str]:
    """Die Excel-Datei holen (unverändert) und Prüfsumme und Abrufzeitpunkt merken."""
    from zaehlkarte.fetch import lade, sha256

    ordner = pfade.roh / q["code"]
    jetzt = datetime.now(UTC).replace(microsecond=0)
    p = lade(q["datei"], ordner / DATEI)
    (ordner / "abruf.json").write_text(json.dumps({
        "abgerufen": jetzt.isoformat().replace("+00:00", "Z"), "url": q["datei"],
        "bytes": p.stat().st_size, "sha256": sha256(p),
    }, indent=1) + "\n", encoding="utf-8")
    return [f"{q['code']}: Gesamtdatei geholt ({p.stat().st_size / 1e6:.1f} MB)"]


def _markierung(zelle) -> str | None:
    f = zelle.fill
    if f is None or not f.fill_type:
        return None
    fg = f.fgColor
    if fg.type == "rgb":
        return {"FFFFC000": "0/unplausibel", "FFFFEB9C": "keine Daten"}.get(fg.rgb, f"rgb {fg.rgb}")
    if fg.type == "theme":
        return {5: "rekonstruiert", 7: "Sommerzeit"}.get(fg.theme, f"theme {fg.theme}")
    return f"{fg.type}"


def lies(pfad: Path, bericht: Bericht) -> tuple[dict[str, tuple], dict[tuple[str, datetime], int]]:
    """-> (Standorte je Kennung, Werte je (Kennung, Stunde) mit -1 = nicht gezählt)."""
    import openpyxl

    wb = openpyxl.load_workbook(pfad, data_only=True)  # nicht read_only: die Füllfarben zählen
    orte = {}
    for z in wb["Standortdaten"].iter_rows(min_row=2, values_only=True):
        if z and z[0] and z[2] is not None and z[3] is not None:
            orte[str(z[0]).strip()] = (str(z[1] or z[0]).strip(), float(z[2]), float(z[3]))
    werte: dict[tuple[str, datetime], int] = {}
    for name in wb.sheetnames:
        if not name.startswith("Jahresdatei"):
            continue
        bericht.blaetter.append(name.split()[-1])
        ws = wb[name]
        zeilen = ws.iter_rows()
        kopf = [str(c.value or "").split()[0] if c.value else "" for c in next(zeilen)]
        for z in zeilen:
            t = z[0].value
            if not isinstance(t, datetime):
                continue
            for k, c in enumerate(z[1:], 1):
                kennung = kopf[k] if k < len(kopf) else ""
                if not kennung:
                    continue
                bericht.zellen += 1
                m = _markierung(c)
                if m:
                    bericht.markiert[m] += 1
                    w = LEER
                elif isinstance(c.value, (int, float)) and c.value >= 0:
                    w = int(round(c.value))
                else:
                    bericht.leer += 1
                    w = LEER
                schluessel = (kennung, t)
                if schluessel in werte:
                    if werte[schluessel] == w:
                        bericht.doppelt_gleich += 1
                    else:
                        bericht.doppelt_anders += 1
                        werte[schluessel] = LEER
                    continue
                werte[schluessel] = w
    return orte, werte


def lese(q: dict, pfade: Pfade, bericht: Bericht) -> Messreihe:
    pfad = pfade.roh / q["code"] / DATEI
    if not pfad.exists():
        raise ValueError(f"{q['code']}: keine Gesamtdatei in {pfad.parent} – erst "
                         "`zaehlkarte dauer fetch`")
    orte, werte = lies(pfad, bericht)
    kennungen = sorted({k for k, _ in werte})
    stellen, idx = [], {}
    for k in kennungen:
        if k not in orte:
            bericht.ohne_lage.append(k)
            continue
        name, lat, lon = orte[k]
        idx[k] = len(stellen)
        stellen.append(Dauerstelle(quelle=q["code"], kennung=k, name=name, abschnitt=None,
                                   richtung=None, lon=round(lon, 6), lat=round(lat, 6),
                                   land=q["land"]))
    bericht.stellen = len(stellen)
    eintraege = [(idx[k], t, w) for (k, t), w in werte.items() if k in idx]
    s = np.array([e[0] for e in eintraege], dtype=np.int64)
    t = np.array([e[1] for e in eintraege], dtype="datetime64[h]")
    w = np.array([e[2] for e in eintraege], dtype=np.int64)
    tag = t.astype("datetime64[D]")
    stunde = (t - tag).astype(np.int64)
    reihe = Messreihe.leer(q["code"], tag.min().astype(date), tag.max().astype(date), stellen,
                           ("rad",))
    bericht.stunden, _ = setze_lokal(reihe, "rad", s, tag, stunde, w, anzahl=1, rueck="zusammen")
    kuerze(reihe)
    reihe.verfahren = [(reihe.von, reihe.tag(reihe.tage - 1),
                        "Stundenwerte je Zählstelle wie geliefert; farbig markierte Werte "
                        "(rekonstruiert, unplausibel, fehlend) nicht übernommen")]
    return reihe
