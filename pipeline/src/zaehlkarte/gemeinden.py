"""Gemeinde je Zählstelle: der amtliche Gemeindeschlüssel (AGS) aus den Verwaltungsgrenzen VG250
des BKG (`config/gemeinden.yaml`).

Wozu: Die Karte zeigt beim Klick auf eine Kommune der Datenlage, was es dort gibt (Steckbrief).
Für die eigenen Quellen einer Kommune reicht die Verknüpfung in der Datenlage (`quellen`). Bei
Quellen, die mehrere Kommunen bündeln (MobiData BW, VMZ Niedersachsen), und bei Quellen des Landes
oder des Bundes (`ebene`) sagt erst die Lage einer Stelle, zu welcher Kommune sie gehört. Darum
bekommt jede Dauerzählstelle beim Bau den Schlüssel der Gemeinde, in der sie liegt (`ags` in
dauer/index.json); ein Kreis der Datenlage umfasst die Stellen mit seinem Kreisschlüssel (die
ersten fünf Ziffern).

Gelesen wird nur die Ebene der Gemeinden (`VG250_GEM`) aus dem ZIP „Ebenen“ in geografischen
Koordinaten (geo84) – als Shapefile, ohne weitere Bibliothek (Formtyp Polygon). Eine Stelle gehört
zur Gemeinde, deren Fläche sie enthält (bei Land- und Wasserfläche zugleich zur Landfläche). Liegt
sie knapp außerhalb jeder Fläche – VG250 ist generalisiert, Zählstellen stehen auch auf Brücken über
Grenzflüsse –, gehört sie zur nächsten Gemeinde im Umkreis von `RAND_M` Metern; sonst bleibt `ags`
leer. Die Datei ist über ihre Prüfsumme gepinnt; eine neue Fassung (jährlich zum 01.01.) kommt nur
mit neuer URL und Prüfsumme in die Konfiguration.
"""

from __future__ import annotations

import hashlib
import math
import struct
import urllib.parse
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from zaehlkarte.config import Pfade, konfiguration

EBENE = "VG250_GEM"
RAND_M = 300.0
GRAD_M = 111_320.0  # Meter je Grad Breite (Näherung, für den Abstand zum Rand)
LAND = {"3", "4"}  # Geofaktor (GF): Landfläche ohne bzw. mit Struktur; 1 und 2 sind Gewässer
Ring = np.ndarray  # [n, 2] Länge/Breite, geschlossen (erster = letzter Punkt)


def datei(pfade: Pfade, cfg: dict) -> Path:
    """Ablage des ZIP unter pipeline/data/raw/vg250/ (Name wie in der URL)."""
    return pfade.roh / "vg250" / Path(urllib.parse.urlsplit(cfg["url"]).path).name


def sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def hole(pfade: Pfade | None = None) -> list[str]:
    """Das ZIP holen, wenn es fehlt oder die Prüfsumme nicht stimmt – sonst nichts tun."""
    from zaehlkarte import abruf

    pfade = pfade or Pfade()
    cfg = konfiguration(pfade).get("gemeinden")
    if not cfg:
        return ["Gemeinden: keine config/gemeinden.yaml – Zählstellen ohne Gemeinde"]
    ziel = datei(pfade, cfg)
    if ziel.is_file() and sha256(ziel) == cfg["sha256"]:
        return [f"Gemeinden: {ziel.name} liegt vor (Prüfsumme stimmt)"]
    abruf.lade(cfg["url"], ziel)
    if (summe := sha256(ziel)) != cfg["sha256"]:
        ziel.unlink()
        raise ValueError(f"Gemeinden: Prüfsumme {summe} statt {cfg['sha256']} – hat das BKG die "
                         "Datei ersetzt? URL und sha256 in config/gemeinden.yaml prüfen")
    return [f"Gemeinden: {ziel.name} geholt ({ziel.stat().st_size / 1e6:.0f} MB)"]


def _dbf(daten: bytes, kodierung: str) -> list[dict[str, str] | None]:
    """Sätze einer dBASE-Datei als Text (gelöschte Sätze: None, damit die Reihenfolge der Formen
    stimmt)."""
    anzahl = struct.unpack_from("<I", daten, 4)[0]
    kopf, laenge = struct.unpack_from("<HH", daten, 8)
    felder, pos = [], 32
    while daten[pos] != 0x0D:
        felder.append((daten[pos:pos + 11].split(b"\0", 1)[0].decode("ascii"), daten[pos + 16]))
        pos += 32
    saetze: list[dict[str, str] | None] = []
    for i in range(anzahl):
        satz = daten[kopf + i * laenge: kopf + (i + 1) * laenge]
        if satz[:1] == b"*":
            saetze.append(None)
            continue
        werte, p = {}, 1
        for name, breite in felder:
            werte[name] = satz[p:p + breite].decode(kodierung, errors="replace").strip()
            p += breite
        saetze.append(werte)
    return saetze


def _shp(daten: bytes) -> list[tuple[tuple[float, float, float, float], list[Ring]] | None]:
    """Formen eines Shapefiles mit Polygonen (Typ 5): je Satz (Umriss, Ringe); leere Formen None."""
    out: list[tuple[tuple[float, float, float, float], list[Ring]] | None] = []
    pos = 100
    while pos + 8 <= len(daten):
        laenge = struct.unpack_from(">i", daten, pos + 4)[0] * 2  # in 16-Bit-Worten
        inhalt = pos + 8
        typ = struct.unpack_from("<i", daten, inhalt)[0]
        if typ == 0:
            out.append(None)
        elif typ == 5:
            box = struct.unpack_from("<4d", daten, inhalt + 4)
            n_teile, n_punkte = struct.unpack_from("<ii", daten, inhalt + 36)
            teile = struct.unpack_from(f"<{n_teile}i", daten, inhalt + 44)
            punkte = np.frombuffer(daten, "<f8", 2 * n_punkte,
                                   inhalt + 44 + 4 * n_teile).reshape(-1, 2).copy()
            grenzen = [*teile, n_punkte]
            out.append((box, [punkte[a:b] for a, b in zip(grenzen, grenzen[1:], strict=False)
                              if b - a >= 4]))
        else:
            raise ValueError(f"Shapefile: Formtyp {typ} – erwartet sind Polygone (5)")
        pos = inhalt + laenge
    return out


def _innen(x: float, y: float, ringe: list[Ring]) -> bool:
    """Gerade-ungerade-Regel über alle Ringe (Löcher inbegriffen)."""
    kreuzt = 0
    for r in ringe:
        y1, y2 = r[:-1, 1], r[1:, 1]
        mit = (y1 > y) != (y2 > y)
        if not mit.any():
            continue
        x1, x2 = r[:-1, 0][mit], r[1:, 0][mit]
        a, b = y1[mit], y2[mit]
        kreuzt += int(np.count_nonzero(x1 + (y - a) * (x2 - x1) / (b - a) > x))
    return kreuzt % 2 == 1


def _abstand_m(x: float, y: float, ringe: list[Ring]) -> float:
    """Kürzester Abstand zum Rand in Metern (Breitenkreis-Näherung, für kurze Wege genau genug)."""
    kx = math.cos(math.radians(y)) * GRAD_M
    best = math.inf
    for r in ringe:
        ax, ay = (r[:-1, 0] - x) * kx, (r[:-1, 1] - y) * GRAD_M
        dx, dy = (r[1:, 0] - x) * kx - ax, (r[1:, 1] - y) * GRAD_M - ay
        l2 = dx * dx + dy * dy
        t = np.clip(-(ax * dx + ay * dy) / np.where(l2 == 0, 1, l2), 0, 1)
        best = min(best, float(np.hypot(ax + t * dx, ay + t * dy).min()))
    return best


@dataclass
class Gemeinden:
    """Die Gemeindeflächen (je Fläche Schlüssel, Name, Land/Wasser, Umriss, Ringe) und die Angaben
    zur Quelle für die Karte (`meta`, wie ein Eintrag in `lizenzen`)."""

    ags: list[str]
    namen: list[str]
    land: np.ndarray
    box: np.ndarray
    ringe: list[list[Ring]]
    meta: dict

    def name(self, ags: str) -> str:
        return next((n for a, n in zip(self.ags, self.namen, strict=True) if a == ags), ags)

    def finde(self, lon: float, lat: float, rand_m: float = RAND_M) -> tuple[str | None, str]:
        """(Schlüssel, Art) – Art „innen“, „rand“ (bis `rand_m` außerhalb) oder „ohne“."""
        b = self.box
        kandidaten = np.flatnonzero((b[:, 0] <= lon) & (lon <= b[:, 2])
                                    & (b[:, 1] <= lat) & (lat <= b[:, 3]))
        innen = [i for i in kandidaten if _innen(lon, lat, self.ringe[i])]
        if innen:
            innen.sort(key=lambda i: not self.land[i])  # Landfläche vor Wasserfläche
            return self.ags[innen[0]], "innen"
        dy = rand_m / GRAD_M
        dx = dy / max(math.cos(math.radians(lat)), 0.1)
        nah = np.flatnonzero((b[:, 0] - dx <= lon) & (lon <= b[:, 2] + dx)
                             & (b[:, 1] - dy <= lat) & (lat <= b[:, 3] + dy))
        if nah.size:
            abstand, i = min((_abstand_m(lon, lat, self.ringe[i]), i) for i in nah)
            if abstand <= rand_m:
                return self.ags[i], "rand"
        return None, "ohne"

    def zuordne(self, punkte: list[tuple[float, float]]) -> tuple[list[str | None], list[str]]:
        """Je Punkt (Länge, Breite) der Gemeindeschlüssel oder None, dazu die Arten der Zuordnung
        („innen“, „rand“, „ohne“)."""
        treffer = [self.finde(lon, lat) for lon, lat in punkte]
        return [a for a, _ in treffer], [art for _, art in treffer]


def lese_zip(pfad: Path, meta: dict | None = None, ebene: str = EBENE) -> Gemeinden:
    """Die Gemeinden aus dem ZIP (Shapefile `ebene` in geografischen Koordinaten)."""
    with zipfile.ZipFile(pfad) as z:
        namen = {Path(n).name.upper(): n for n in z.namelist()}

        def lies(endung: str) -> bytes | None:
            name = namen.get(f"{ebene}.{endung}".upper())
            return z.read(name) if name else None

        shp, dbf, prj, cpg = lies("shp"), lies("dbf"), lies("prj"), lies("cpg")
    if shp is None or dbf is None:
        raise ValueError(f"{pfad.name}: {ebene}.shp/.dbf fehlt")
    if prj is not None and b"PROJCS" in prj:
        raise ValueError(f"{pfad.name}: {ebene} in projizierten Koordinaten – erwartet geo84")
    kodierung = (cpg or b"latin-1").decode("ascii").strip() or "latin-1"
    if kodierung.isdigit():
        kodierung = f"cp{kodierung}"
    formen, saetze = _shp(shp), _dbf(dbf, kodierung)
    if len(formen) != len(saetze):
        raise ValueError(f"{pfad.name}: {len(formen)} Formen, aber {len(saetze)} Sätze")
    ags, namen_g, land, box, ringe = [], [], [], [], []
    for form, satz in zip(formen, saetze, strict=True):
        if form is None or satz is None or not form[1]:
            continue
        ags.append(satz["AGS"])
        namen_g.append(satz.get("GEN", ""))
        land.append(satz.get("GF", "4") in LAND)
        box.append(form[0])
        ringe.append(form[1])
    return Gemeinden(ags, namen_g, np.array(land, dtype=bool),
                     np.array(box, dtype=float).reshape(-1, 4), ringe, meta or {})


def meta(cfg: dict) -> dict:
    """Angaben für die Karte („Quellen & Lizenzen“), aufgebaut wie ein Eintrag in `lizenzen`."""
    return {"code": "gemeinden", "titel": cfg["titel"], "herausgeber": cfg["herausgeber"],
            "lizenz": cfg["lizenz"], "lizenz_url": cfg["lizenz_url"], "herkunft_url": cfg["portal"],
            "quellenvermerk": cfg["quellenvermerk"], "stand": str(cfg["stand"])}


def lese(pfade: Pfade | None = None) -> tuple[Gemeinden | None, list[str]]:
    """(Gemeinden, Berichtszeilen) – None, wenn die Konfiguration oder die Datei fehlt oder ihre
    Prüfsumme nicht stimmt (dann bleibt `ags` leer, die Karte zeigt Bündel nicht je Kommune)."""
    pfade = pfade or Pfade()
    cfg = konfiguration(pfade).get("gemeinden")
    if not cfg:
        return None, ["Gemeinden: keine config/gemeinden.yaml – ags leer"]
    pfad = datei(pfade, cfg)
    if not pfad.is_file():
        return None, [f"Gemeinden: {pfad.name} fehlt (zaehlkarte dauer fetch) – ags leer"]
    if sha256(pfad) != cfg["sha256"]:
        return None, [f"Gemeinden: Prüfsumme von {pfad.name} stimmt nicht – ags leer"]
    return lese_zip(pfad, meta(cfg)), []
