"""Schema der Dauerzählstellen: Stellen und ihre Stundenwerte als Felder (Stelle × Tag × Stunde).

Werte sind Anzahlen je Stunde in Ortszeit (Stunde 8 = 8:00–8:59); -1 heißt „nicht gezählt“,
nie 0. Eine Tagessumme gibt es nur, wenn jede Stunde des Tages gezählt ist – am Tag der
Umstellung auf Sommerzeit hat der Tag 23 Stunden (2–3 Uhr gibt es nicht), am Tag der
Rückstellung steht in Stunde 2 die Summe beider Stunden 2–3 Uhr (`doppelt`).

Gruppen (wie die Quelle sie zählt, nicht umgerechnet und nicht ineinander gemischt):
- kfz   alle Kraftfahrzeuge
- lkw   Lkw laut Detektor (Berlin: Klasse des Detektors, nicht der Schwerverkehr der
        Kurzzeitzählungen)
- sv    Schwerverkehr laut Detektor (Hamburg: Klasse der Wärmebildkamera)
- rad   Fahrräder
- fuss  zu Fuß Gehende
Jede Quelle nennt in ihrer Messreihe nur die Gruppen, die sie zählt (`Messreihe.werte`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

GRUPPEN = ("kfz", "lkw", "sv", "rad", "fuss")  # Reihenfolge = Bits der Stellen im Frontend
LEER = -1


@dataclass
class Dauerstelle:
    quelle: str  # Code aus sources.yaml (Abschnitt `dauer:`)
    kennung: str  # stabil je Quelle (Berlin: Kurzname des Messquerschnitts, „TE001“)
    name: str  # Straße
    abschnitt: str | None  # Lage auf der Straße („zwischen … und …“)
    richtung: str | None  # Fahrtziel und Himmelsrichtung, wie die Quelle sie nennt
    lon: float
    lat: float
    land: str
    fahrstreifen: list[str] = field(default_factory=list)  # Spuren laut Stammdaten
    hinweise: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.quelle}:{self.kennung}"


@dataclass
class Messreihe:
    """Stundenwerte einer Quelle. `werte[gruppe]`: int32-Feld [Stellen, Tage, 24], -1 = nicht
    gezählt; `doppelt`: bool [Stellen, Tage] – Stunde 2 enthält zwei Stunden (Rückstellung)."""

    quelle: str
    von: date
    tage: int
    stellen: list[Dauerstelle]
    werte: dict[str, np.ndarray]
    doppelt: np.ndarray
    # Abschnitte der Reihe mit eigenem Verfahren, für die Hinweise: [(von, bis, Text)]
    verfahren: list[tuple[date, date, str]] = field(default_factory=list)

    @classmethod
    def leer(cls, quelle: str, von: date, bis: date, stellen: list[Dauerstelle],
             gruppen: tuple[str, ...]) -> Messreihe:
        if unbekannt := set(gruppen) - set(GRUPPEN):
            raise ValueError(f"{quelle}: unbekannte Gruppen {sorted(unbekannt)}")
        tage = (bis - von).days + 1
        form = (len(stellen), tage, 24)
        return cls(quelle, von, tage, stellen,
                   {g: np.full(form, LEER, dtype=np.int32) for g in gruppen},
                   np.zeros(form[:2], dtype=bool))

    def tag(self, i: int) -> date:
        return self.von + timedelta(days=i)

    def index(self, tag: date) -> int:
        return (tag - self.von).days


def umstellungen(jahr: int) -> tuple[date, date]:
    """(Sommerzeit-Beginn, Sommerzeit-Ende): letzter Sonntag im März bzw. Oktober (seit 1996)."""

    def letzter_sonntag(monat: int) -> date:
        d = date(jahr, monat, 31)
        return d - timedelta(days=(d.weekday() - 6) % 7)

    return letzter_sonntag(3), letzter_sonntag(10)


def erwartete_stunden(von: date, tage: int) -> np.ndarray:
    """bool [Tage, 24]: Stunden, die es am Tag in Ortszeit gibt (Sommerzeit-Beginn ohne 2 Uhr)."""
    erwartet = np.ones((tage, 24), dtype=bool)
    for jahr in range(von.year, (von + timedelta(days=tage - 1)).year + 1):
        beginn, _ = umstellungen(jahr)
        i = (beginn - von).days
        if 0 <= i < tage:
            erwartet[i, 2] = False
    return erwartet


def setze_utc(reihe: Messreihe, gruppe: str, stelle: np.ndarray, utc: np.ndarray,
              werte: np.ndarray) -> int:
    """Stundenwerte mit UTC-Beginn (datetime64, volle Stunden) in Ortszeit in die Reihe legen.

    Am Tag der Rückstellung fallen zwei UTC-Stunden auf 2 Uhr Ortszeit: beide da -> Summe und
    `doppelt`, nur eine -> die Stunde gilt als nicht gezählt. -> Anzahl gesetzter Stunden."""
    import pandas as pd

    if not len(utc):
        return 0
    lokal = pd.DatetimeIndex(utc).tz_localize("UTC").tz_convert("Europe/Berlin")
    d = pd.DataFrame({
        "s": stelle,
        "t": (lokal.tz_localize(None).normalize() - pd.Timestamp(reihe.von)).days,
        "h": lokal.hour,
        "w": werte.astype(np.int64),
    })
    d = d[(d["t"] >= 0) & (d["t"] < reihe.tage) & (d["w"] >= 0)]
    g = d.groupby(["s", "t", "h"], sort=False)["w"].agg(["sum", "count"]).reset_index()
    jahre = range(reihe.von.year, reihe.tag(reihe.tage - 1).year + 1)
    rueck = {(umstellungen(j)[1] - reihe.von).days for j in jahre}
    am_rueck = g["t"].isin(rueck) & (g["h"] == 2)
    voll = np.where(am_rueck, g["count"] == 2, g["count"] == 1)
    w = reihe.werte[gruppe]
    s, t, h = (g[k].to_numpy() for k in ("s", "t", "h"))
    w[s, t, h] = np.where(voll, g["sum"].to_numpy(), LEER).astype(np.int32)
    dop = (am_rueck & voll).to_numpy()
    reihe.doppelt[s[dop], t[dop]] = True
    return int(voll.sum())


def utc_stunden(stelle: np.ndarray, utc: np.ndarray, werte: np.ndarray, anzahl: int
                ) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    """Teilwerte mit UTC-Beginn (etwa Viertelstunden, datetime64) zu UTC-Stunden zusammenfassen.

    Eine Stunde gilt, wenn sie `anzahl` verschiedene Zeitpunkte hat und keiner nicht gezählt ist
    (Wert < 0). Derselbe Zeitpunkt zweimal: gleicher Wert zählt einmal, verschiedene gar nicht
    (die Stunde ist dann nicht gezählt). -> (Stelle, Stunde als datetime64[h], Summe, Anzahl der
    Zeitpunkte, die doppelt mit verschiedenen Werten kamen)."""
    stelle = np.asarray(stelle, dtype=np.int64)
    utc = np.asarray(utc).astype("datetime64[m]")
    werte = np.asarray(werte, dtype=np.int64)
    if not len(stelle):
        leer = np.array([], dtype=np.int64)
        return leer, np.array([], dtype="datetime64[h]"), leer, 0
    # gleiche (Stelle, Zeitpunkt): ein Eintrag, bei verschiedenen Werten „nicht gezählt“
    ordnung = np.lexsort((werte, utc, stelle))
    stelle, utc, werte = stelle[ordnung], utc[ordnung], werte[ordnung]
    neu = np.ones(len(stelle), dtype=bool)
    neu[1:] = (stelle[1:] != stelle[:-1]) | (utc[1:] != utc[:-1])
    gruppe = np.cumsum(neu) - 1
    erst = np.flatnonzero(neu)
    verschieden = np.zeros(len(erst), dtype=bool)
    np.logical_or.at(verschieden, gruppe, werte != werte[erst][gruppe])
    stelle, utc = stelle[erst], utc[erst]
    werte = np.where(verschieden, -1, werte[erst])
    stunde = utc.astype("datetime64[h]")
    basis = stunde.min()
    breite = int((stunde.max() - basis).astype(np.int64)) + 1
    k = stelle * breite + (stunde - basis).astype(np.int64)
    _, erste, inv, n = np.unique(k, return_index=True, return_inverse=True, return_counts=True)
    neg = np.bincount(inv, weights=(werte < 0).astype(np.int64))
    summe = np.bincount(inv, weights=np.maximum(werte, 0)).astype(np.int64)
    ok = (n == anzahl) & (neg == 0)
    return stelle[erste][ok], stunde[erste][ok], summe[ok], int(verschieden.sum())


def setze_lokal(reihe: Messreihe, gruppe: str, stelle: np.ndarray, tag: np.ndarray,
                stunde: np.ndarray, werte: np.ndarray, anzahl: int = 1,
                rueck: str = "zusammen") -> tuple[int, int]:
    """Werte mit Zeitstempel in Ortszeit (Tag als datetime64[D], Stunde 0–23) in die Reihe legen.

    `anzahl`: Einträge je Stunde (1 = Stundenwerte, 4 = Viertelstunden). Eine Stunde ist gezählt,
    wenn alle ihre Einträge da sind und keiner nicht gezählt ist (Wert < 0) – sonst bleibt sie
    leer, nie aufgefüllt. Am Tag der Umstellung auf Sommerzeit gibt es 2 Uhr nicht: Einträge dort
    werden verworfen (manche Quellen führen die Stunde mit Nullen). Am Tag der Rückstellung gibt
    es 2 Uhr zweimal:
    - `rueck="zusammen"`: Die Quelle fasst beide Stunden unter einer Uhrzeit zusammen (je Quelle
      belegt) oder liefert beide getrennt – beides ergibt die Summe und `doppelt`.
    - `rueck="einfach"`: Unter einer Uhrzeit steht nur eine der beiden Stunden – gezählt ist die
      Stunde nur, wenn beide getrennt kommen (doppelt so viele Einträge).
    -> (gesetzte Stunden, verworfene Einträge um 2 Uhr am Tag der Sommerzeit).

    Gezählt wird je Zelle (Stelle, Tag, Stunde) mit `np.bincount` – auch bei Millionen Einträgen
    ohne Tabelle je Eintrag; große Quellen rufen die Funktion je Block von Stellen auf (die Zellen
    reichen nur über die Stellen der Einträge)."""
    if rueck not in ("zusammen", "einfach"):
        raise ValueError(f"rueck: {rueck!r}")
    if not len(stelle):
        return 0, 0
    stelle, stunde = np.asarray(stelle), np.asarray(stunde)
    if ((stunde < 0) | (stunde > 23)).any():
        raise ValueError(f"{reihe.quelle}: Stunde außerhalb 0–23")
    t = (tag.astype("datetime64[D]", copy=False) - np.datetime64(reihe.von, "D")).view(np.int64)
    jahre = range(reihe.von.year, reihe.tag(reihe.tage - 1).year + 1)
    sommer = np.array([(umstellungen(j)[0] - reihe.von).days for j in jahre])
    rueck_tage = np.array([(umstellungen(j)[1] - reihe.von).days for j in jahre])
    drin = (t >= 0) & (t < reihe.tage)
    fehlt = drin & np.isin(t, sommer) & (stunde == 2)
    verworfen = int(fehlt.sum())
    drin &= ~fehlt
    s0 = int(stelle.min())
    k = stelle[drin].astype(np.int64) - s0
    k *= reihe.tage
    k += t[drin]
    del t
    k *= 24
    k += stunde[drin]
    w = np.asarray(werte)[drin]
    feld = reihe.werte[gruppe]
    n_zellen = (int(stelle.max()) - s0 + 1) * reihe.tage * 24
    anz = np.bincount(k, minlength=n_zellen)
    neg = np.bincount(k[w < 0], minlength=n_zellen)  # Einträge „nicht gezählt“ je Zelle
    summe = np.bincount(k, weights=np.maximum(w, 0), minlength=n_zellen)
    del k, w
    zellen = np.flatnonzero(anz)
    n, gueltig, summe = anz[zellen], neg[zellen] == 0, summe[zellen]
    del anz, neg
    s, rest = np.divmod(zellen, reihe.tage * 24)
    s += s0
    t, h = np.divmod(rest, 24)
    am_rueck = np.isin(t, rueck_tage) & (h == 2)
    if rueck == "zusammen":
        voll_rueck = (n == anzahl) | (n == 2 * anzahl)
    else:
        voll_rueck = n == 2 * anzahl
    voll = gueltig & np.where(am_rueck, voll_rueck, n == anzahl)
    feld[s, t, h] = np.where(voll, summe, LEER).astype(np.int32)
    dop = am_rueck & voll
    reihe.doppelt[s[dop], t[dop]] = True
    return int(voll.sum()), verworfen


def tagessummen(reihe: Messreihe, gruppe: str) -> tuple[np.ndarray, np.ndarray]:
    """(Summe [Stellen, Tage] mit -1 = nicht vollständig gezählt, gezählte Stunden [Stellen, Tage]).

    Vollständig heißt: jede Stunde, die es an dem Tag gibt, hat einen Wert."""
    w = reihe.werte[gruppe]
    erwartet = erwartete_stunden(reihe.von, reihe.tage)[None, :, :]
    gezaehlt = (w >= 0) & erwartet
    n = gezaehlt.sum(axis=2).astype(np.int16)
    summe = np.where(gezaehlt, w, 0).sum(axis=2, dtype=np.int64)
    voll = n == erwartet.sum(axis=2)
    return np.where(voll, summe, LEER).astype(np.int64), n


def kuerze(reihe: Messreihe) -> None:
    """Leere Tage vorn und hinten abschneiden (etwa die Ränder der Umrechnung UTC -> Ortszeit)."""
    da = np.zeros(reihe.tage, dtype=bool)
    for w in reihe.werte.values():
        da |= (w >= 0).any(axis=(0, 2))
    if not da.any():
        return
    a, b = int(np.argmax(da)), int(reihe.tage - 1 - np.argmax(da[::-1]))
    reihe.von = reihe.tag(a)
    reihe.tage = b - a + 1
    reihe.werte = {g: w[:, a:b + 1] for g, w in reihe.werte.items()}
    reihe.doppelt = reihe.doppelt[:, a:b + 1]
