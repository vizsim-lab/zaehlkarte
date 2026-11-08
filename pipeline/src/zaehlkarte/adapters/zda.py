# Portiert aus vizsim/berlin-traffic-counts_schulwege (pipeline/src/schulwege/zda.py,
# MIT, © vizsim).
# In der Zählkarte unter AGPL-3.0-or-later.
"""ZDA-Dateien der Berliner Verkehrszählungen lesen.

Aufbau: Kopf `schlüssel=wert` bis zur Zeile `data=`, danach je Richtung eine Marke
`; 1 -> 2` und die Zählwerte, ein Intervall nach dem anderen, je Kategorie aus `art` ein
Wert. Was in den echten Dateien vorkommt und hier abgefangen wird:

- Kodierung: fast immer Windows-1252, einige wenige UTF-8.
- Trenner Tab, Leerzeichen oder Komma; ältere Dateien brechen die Werte um (ein
  Intervall über zwei Zeilen). Deshalb wird je Richtung ein Zahlenstrom gelesen und nach
  der Zahl der Kategorien geschnitten.
- `art` mit leeren Kategorien am Ende ("Erw,Jugend,,,,,"): die haben keine Datenspalte.
- `zeit` mit Leerzeichen ("0700, 1900"); `intv` 1, 15 oder 60 Minuten.
- -1 heißt "nicht gezählt" (-> None).
- `data=` am Ende der Zeile davor statt auf eigener Zeile ("bemerk=… (>2 mm).\n.data=",
  Fahrrad-Zählstellen Anfang 2019).
- Schlüssel mal groß, mal klein ("Arm1"/"arm1"), Endung .zda oder .ZDA.
"""

from __future__ import annotations

import re
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

_RICHTUNG = re.compile(r"(\d+)\s*->\s*(\d+)")
_TRENNER = re.compile(r"[\s,;]+")
_DATUM = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")


@dataclass
class Zaehlung:
    datei: str  # Dateiname mit Endung, wie im Archiv
    kopf: dict[str, str]  # Schlüssel klein geschrieben
    kategorien: list[str]  # aus `art`, ohne leere
    intervall: int  # Minuten
    fenster: list[tuple[int, int]]  # Minuten ab Mitternacht, [von, bis)
    werte: dict[str, list[list[int | None]]]  # Richtung -> Intervalle -> Wert je Kategorie
    kodierung: str
    hinweise: list[str] = field(default_factory=list)

    @property
    def stamm(self) -> str:
        return self.datei.rsplit(".", 1)[0]

    @property
    def datum(self) -> date | None:
        return parse_datum(self.kopf.get("datum", ""))

    @property
    def intervall_beginne(self) -> list[int]:
        """Beginn jedes Intervalls in Minuten ab Mitternacht, Fenster nacheinander."""
        return [m for von, bis in self.fenster for m in range(von, bis, self.intervall)]


def dekodiere(raw: bytes) -> tuple[str, str]:
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace"), "cp1252"


def parse_zeit(zeit: str) -> list[tuple[int, int]]:
    """'0700,1900' / '0700, 1900' -> [(420, 1140)]; mehrere Fenster paarweise."""
    teile = [t for t in zeit.replace(" ", "").split(",") if t]
    fenster = []
    for von, bis in zip(teile[::2], teile[1::2], strict=False):
        if not (von.isdigit() and bis.isdigit() and len(von) == len(bis) == 4):
            continue
        a = int(von[:2]) * 60 + int(von[2:])
        b = int(bis[:2]) * 60 + int(bis[2:])
        if b > a:
            fenster.append((a, b))
    return fenster


def parse_datum(text: str) -> date | None:
    m = _DATUM.search(text)
    if not m:
        return None
    tag, monat, jahr = (int(g) for g in m.groups())
    if jahr < 100:
        jahr += 1900 if jahr >= 70 else 2000
    try:
        return date(jahr, monat, tag)
    except ValueError:
        return None


def _zahl(token: str) -> int | None:
    try:
        v = int(token)
    except ValueError:
        return None
    return None if v < 0 else v


def parse(raw: bytes, datei: str) -> Zaehlung:
    text, kodierung = dekodiere(raw)
    kopf: dict[str, str] = {}
    strom: dict[str, list[str]] = {}
    aktuell: str | None = None
    im_datenteil = False
    hinweise: list[str] = []
    for zeile in text.replace("\r", "").split("\n"):
        s = zeile.strip()
        if not s:
            continue
        if not im_datenteil:
            if s.lower() == "data=":
                im_datenteil = True
            elif "=" in s:
                k, v = s.split("=", 1)
                if v.lower().endswith("data="):  # "bemerk=… Vorwoche (>2 mm).\n.data="
                    v = v[: -len("data=")]
                    im_datenteil = True
                    hinweise.append("data= am Ende einer Kopfzeile")
                kopf[k.strip().lower()] = v.strip()
            continue
        if s.startswith(";"):
            m = _RICHTUNG.search(s)
            aktuell = f"{m.group(1)}->{m.group(2)}" if m else s.lstrip("; ")
            strom.setdefault(aktuell, [])
        elif aktuell is not None:
            strom[aktuell].extend(t for t in _TRENNER.split(s) if t)

    kategorien = [k.strip() for k in kopf.get("art", "").split(",") if k.strip()]
    try:
        intervall = int(kopf.get("intv", "") or 60)
    except ValueError:
        intervall = 60
    fenster = parse_zeit(kopf.get("zeit", ""))
    z = Zaehlung(datei, kopf, kategorien, max(intervall, 1), fenster, {}, kodierung)
    z.hinweise.extend(hinweise)
    if not fenster:
        z.hinweise.append(f"zeit unlesbar: {kopf.get('zeit', '')!r}")
    n_kat = max(len(kategorien), 1)
    n_soll = len(z.intervall_beginne)

    for richtung, tokens in strom.items():
        if len(tokens) % n_kat:
            z.hinweise.append(f"{richtung}: {len(tokens)} Werte passen nicht zu {n_kat} Kategorien")
        zeilen = [
            [_zahl(t) for t in tokens[i : i + n_kat]]
            for i in range(0, len(tokens) - n_kat + 1, n_kat)
        ]
        if n_soll and len(zeilen) != n_soll:
            z.hinweise.append(f"{richtung}: {len(zeilen)} statt {n_soll} Intervalle")
            zeilen = zeilen[:n_soll]
        if any(not re.fullmatch(r"-?\d+", t) for t in tokens):
            z.hinweise.append(f"{richtung}: nicht-numerische Werte")
        z.werte[richtung] = zeilen
    return z


def lese_archiv(pfad: Path) -> Iterator[tuple[str, bytes]]:
    """(Dateiname, Inhalt) aller .zda/.ZDA-Dateien eines .zip oder .7z – ohne Entpacken."""
    if pfad.suffix.lower() == ".zip":
        with zipfile.ZipFile(pfad) as zf:
            for info in sorted(zf.infolist(), key=lambda i: i.filename):
                name = info.filename.rsplit("/", 1)[-1]
                if not info.is_dir() and name.lower().endswith(".zda"):
                    yield name, zf.read(info)
    elif pfad.suffix.lower() == ".7z":
        import tempfile

        import py7zr

        # py7zr >= 1.0 liest nicht mehr in den Speicher -> in ein Temp-Verzeichnis entpacken
        with tempfile.TemporaryDirectory() as tmp, py7zr.SevenZipFile(pfad, "r") as sz:
            sz.extractall(path=tmp)
            for p in sorted(Path(tmp).rglob("*"), key=lambda p: p.name):
                if p.is_file() and p.name.lower().endswith(".zda"):
                    yield p.name, p.read_bytes()
    else:
        raise ValueError(f"unbekanntes Archiv: {pfad}")
