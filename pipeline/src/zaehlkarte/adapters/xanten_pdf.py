"""Xanten: Verkehrszählung für das Mobilitätskonzept (Video, 25.08.2020, Open Data).

Quelle: opendata.ruhr, Datensatz „Mobilitätskonzept“ der Stadt Xanten (dl-de/zero-2-0), zwei
PDFs „Gesamtübersicht Zähldaten Xanten“: 12 Knotenpunkte (7–9 und 15–18 Uhr) und 6 Querschnitte
(24 Stunden), je Viertelstunde, Strom bzw. Richtung und Fahrzeugart (Pkw, Krad, Lieferwagen bis
3,5 t, Lkw ab 3,5 t, Lastzug, Bus). Gezählt per Video am Dienstag, 25.08.2020 (Bericht zum
Mobilitätskonzept, Kap. 3.1).

- Je Block („Knotenpunkt 3“, „Querschnitt 5“) Name und Datum aus dem Kopf; je Zeile Beginn der
  Viertelstunde (Dezimalstunde „7,25“), Fahrzeugart und die Werte je Strom. Die Zeile mit
  „Summe“ nennt die Viertelstunde über alle Arten und Ströme – Prüfung.
- Kfz = alle Arten; Schwerverkehr = Lkw + Lastzug + Bus. Rad und Fuß sind nicht gezählt.
- Die Hochrechnungen auf den Tag (DTV) in den PDFs bleiben draußen.
- Lage aus sources.yaml (OpenStreetMap; Querschnitte nach der Zählstellenkarte des Berichts).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

ARTEN = ("PKW", "KRAD", "LIEFER", "LKW", "LASTZUG", "BUS")
SCHWER = ("LKW", "LASTZUG", "BUS")
_KOPF = re.compile(r"^(Knotenpunkt|Querschnitt)\s+(\d+)\b.*?Datum der Zählung:\s*\w+\.?\s*"
                   r"(\d{2})\.(\d{2})\.(\d{4})")
_ZEILE = re.compile(
    r"^(?:Summe\s*(?P<summe>\d+)\s+)?(?:\d{1,2}:\d{2}\s+\d{1,2}:\d{2}\s+)?"
    r"(?P<h>\d{1,2}),(?P<f>\d{2})\s+(?:\d\s+)?(?:99\s+)?"
    rf"(?P<art>{'|'.join(ARTEN)})\s+(?P<werte>\d+(?:\s+\d+)*)\s*$"
)


@dataclass
class Bericht:
    bloecke: int = 0
    viertelstunden: int = 0
    summe_falsch: list[str] = field(default_factory=list)
    unvollstaendig: int = 0
    ohne_lage: list[str] = field(default_factory=list)

    def zeilen(self) -> list[str]:
        return [
            f"{self.bloecke} Zählstellen, {self.viertelstunden} Viertelstunden",
            f"Viertelstunden mit falscher Summe: {len(self.summe_falsch)}",
            *[f"  {s}" for s in self.summe_falsch[:10]],
            f"Stunden mit fehlenden Viertelstunden (weggelassen): {self.unvollstaendig}",
            *[f"ohne Lage: {k}" for k in self.ohne_lage],
        ]


@dataclass
class Block:
    art: str  # "K" | "Q"
    nummer: int
    name: str
    datum: date
    # Beginn der Viertelstunde (Minuten) -> {Fahrzeugart: Summe über die Ströme}
    werte: dict[int, dict[str, int]] = field(default_factory=lambda: defaultdict(dict))
    summen: dict[int, int] = field(default_factory=dict)

    @property
    def kennung(self) -> str:
        return f"{self.art}{self.nummer}"


def lese_text(seiten: list[str]) -> list[Block]:
    """Text der Seiten -> Blöcke je Zählstelle (eine Zählstelle kann über mehrere Seiten gehen)."""
    bloecke: list[Block] = []
    aktuell: Block | None = None
    for text in seiten:
        zeilen = [z.strip() for z in text.splitlines()]
        for i, z in enumerate(zeilen):
            m = _KOPF.match(z)
            if m:
                name = next((x for x in zeilen[i + 1:i + 3] if x), "")
                name = re.sub(r"\s*/\s*", "/", name)
                aktuell = Block("K" if m[1] == "Knotenpunkt" else "Q", int(m[2]), name,
                                date(int(m[5]), int(m[4]), int(m[3])))
                bloecke.append(aktuell)
                continue
            m = _ZEILE.match(z)
            if not m or aktuell is None:
                continue
            minute = int(m["h"]) * 60 + round(int(m["f"]) * 60 / 100)
            aktuell.werte[minute][m["art"]] = sum(int(v) for v in m["werte"].split())
            if m["summe"] is not None:
                aktuell.summen[minute] = int(m["summe"])
    return bloecke


def stunden(block: Block, bericht: Bericht) -> dict[int, tuple[int, int]]:
    """{Stunde: (Kfz, Schwerverkehr)} – nur Stunden mit allen vier Viertelstunden und Arten."""
    je_stunde: dict[int, list[dict[str, int]]] = defaultdict(list)
    for minute, arten in sorted(block.werte.items()):
        bericht.viertelstunden += 1
        summe = sum(arten.values())
        if minute in block.summen and block.summen[minute] != summe:
            bericht.summe_falsch.append(f"{block.kennung} {minute // 60}:{minute % 60:02d}: "
                                        f"{summe} statt {block.summen[minute]}")
        if set(arten) == set(ARTEN):
            je_stunde[minute // 60].append(arten)
    out = {}
    for h, liste in je_stunde.items():
        if len(liste) != 4:
            bericht.unvollstaendig += 1
            continue
        out[h] = (sum(sum(a.values()) for a in liste), sum(a[s] for a in liste for s in SCHWER))
    return out


def _fenster(hs: list[int]) -> list[tuple[int, int]]:
    fenster: list[tuple[int, int]] = []
    for h in sorted(hs):
        if fenster and fenster[-1][1] == h * 60:
            fenster[-1] = (fenster[-1][0], h * 60 + 60)
        else:
            fenster.append((h * 60, h * 60 + 60))
    return fenster


def lese_pdf(pfad: Path) -> list[Block]:
    import pdfplumber

    with pdfplumber.open(pfad) as pdf:
        return lese_text([s.extract_text() or "" for s in pdf.pages])


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "xanten"
    orte = quelle.get("orte", {})
    for datei in quelle["dateien"]:
        pfad = ordner / datei["datei"]
        if not pfad.exists():
            continue
        for b in lese_pdf(pfad):
            bericht.bloecke += 1
            hs = stunden(b, bericht)
            if not hs:
                continue
            ort = orte.get(b.kennung) or {}
            if not ort:
                bericht.ohne_lage.append(b.kennung)
            h0, h1 = min(hs), max(hs)
            arme = list(dict.fromkeys(b.name.split("/"))) if b.art == "K" else []
            yield Zaehlung(
                quelle=quelle["code"],
                kennung=f"{b.kennung}_{b.datum:%Y%m%d}",
                stelle_roh=b.kennung,
                name=b.name if b.art == "K" else f"{b.name} (Querschnitt {b.nummer})",
                typ=b.art,
                lon=ort.get("lon"),
                lat=ort.get("lat"),
                lage="geokodiert" if ort else None,
                datum=b.datum,
                fenster=_fenster(list(hs)),
                intervall=15,
                h0=h0,
                stunden={
                    "kfz": [hs[h][0] if h in hs else None for h in range(h0, h1 + 1)],
                    "sv": [hs[h][1] if h in hs else None for h in range(h0, h1 + 1)],
                },
                land=quelle["land"],
                richtungen=len(b.name.split("/")) if b.art == "K" else 2,
                kategorien="Pkw, Krad, Lieferwagen (bis 3,5 t), Lkw (ab 3,5 t), Lastzug, Bus – "
                           "Schwerverkehr = Lkw, Lastzug und Bus; Rad und Fuß nicht gezählt",
                rohdatei=datei.get("url"),
                bemerkung=f"Verkehrserhebung zum Mobilitätskonzept per Video ({datei['titel']}, "
                          f"{'Knotenpunkt' if b.art == 'K' else 'Querschnitt'} {b.nummer})",
                hinweise=list(ort.get("hinweise", [])),
                zusatz={"datei": datei["datei"], "arme": arme,
                        "genauigkeit": ort.get("genauigkeit")},
            )
