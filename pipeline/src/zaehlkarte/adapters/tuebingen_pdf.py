"""Tübingen: Verkehrszählungen an einzelnen Werktagen (24 Stunden, Kfz und Rad je Querschnitt) aus
den Anlagen 1 und 3 zur Vorlage 242/2022 („Bericht Verkehrszählungen Juni/Juli 2022“) im
Ratsinformationssystem der Stadt – ohne Lizenz (CLAUDE.md, „Quellen ohne Lizenz“).

Aufbau der PDFs (Stand November 2026; Werkzeug-Branch `werkzeug/bw`, tools/bw_ol.py):
- Je Zählstelle ein Kasten: oben links die Straße (fett), darunter ein Zusatz („Neckarbrücke“,
  „südl. Adlerkreuzung nach Nord“, „alle Kfz“). Rechts je Spalte ein Zähltag – ein Datum,
  „n/a“, „DTV 2019“ oder „2019 KW 47, 48“ – und darunter ein Wert „6.361 Kfz/24h“ (auch
  „Rad/24h“, „Bus/24h“), Prozente (Veränderung) und in kleiner Schrift ein Vermerk:
  „Hochrechnung 16h → 24h“, „Dauerzählstelle Ø Di-Do“, „Dauerzählstelle“, „Zählung“,
  „Baustelle Alberstr. W → S“, in Anlage 3 der Ort der Zählung („östl. Knollstr.“) oder
  „Monitoring SZV“. Anlage 1 hat drei Spalten (vor dem Verkehrsversuch, Versuch 2019, Versuch
  2022), Anlage 3 zwei.
- Gelesen wird über die Lage der Wörter (pdfplumber): Zeilen nach der Höhe, Spalten nach den
  Daten der ersten Zeile des Kastens, ein Wert = Zahl und Einheit in derselben Spalte.
- In der Karte: je Spalte mit einem Datum ein Tageswert (Tagessumme, `summen`), Kfz und Rad.
  Nicht übernommen: Hochrechnungen („Hochrechnung“), Mittel über Tage („Ø“), Spalten ohne
  Datum (DTV, Kalenderwochen, n/a), Bus allein und alles aus Kästen, die die Quelldatei nicht
  unter `stellen` nennt (etwa „Kfz ohne Bus“) – der Bericht zählt sie.
- Zählstelle aus der Quelldatei (`stellen`): Kasten („Straße | Zusatz“), wo der Ort im Vermerk
  steht auch der Vermerk, -> Kennung, Name, Lage. Kfz- und Rad-Kasten derselben Stelle ergeben am
  selben Tag eine Zählung; nennen zwei Kästen für denselben Tag verschiedene Werte, gilt keiner.
- Laut Vorlage an einzelnen Werktagen gezählt (Di–Do, Schultag, Vorlesungszeit), über 24 Stunden;
  die Werte der Tabellen sind ungerundet (gerundet sind nur die im Text der Vorlage).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.config import Pfade
from zaehlkarte.modell import Zaehlung

EINHEIT = {"Kfz/24h": "kfz", "Rad/24h": "rad", "Bus/24h": None}  # None: nicht in der Karte
_ZAHL = re.compile(r"^\d{1,3}(?:\.\d{3})*$")
_DATUM = re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$")
NICHT = ("Hochrechnung", "Ø")  # Vermerke, deren Werte keine Zählwerte des Tages sind


@dataclass(frozen=True)
class Wort:
    text: str
    x0: float
    top: float
    size: float
    fett: bool


@dataclass
class Spalte:
    x0: float
    kopf: str  # Datum oder was statt dessen dasteht
    werte: dict[str, int] = field(default_factory=dict)  # Einheit -> Wert
    vermerk: str = ""


@dataclass
class Kasten:
    datei: str
    seite: int
    titel: str
    zusatz: str
    spalten: list[Spalte]

    @property
    def schluessel(self) -> str:
        return f"{self.titel} | {self.zusatz}".strip(" |")


@dataclass
class Bericht:
    kaesten: int = 0
    werte: int = 0
    uebernommen: int = 0
    nicht: Counter = field(default_factory=Counter)  # Grund -> Anzahl Werte
    ohne_stelle: list[str] = field(default_factory=list)
    widerspruch: list[str] = field(default_factory=list)
    zaehlungen: int = 0

    def zeilen(self) -> list[str]:
        return [f"{self.kaesten} Kästen, {self.werte} Werte, {self.uebernommen} übernommen, "
                f"{self.zaehlungen} Zählungen",
                "nicht übernommen: " + (", ".join(f"{k} {n}" for k, n in self.nicht.most_common())
                                        or "–"),
                *[f"Kasten ohne Zählstelle (nicht in der Karte): {k}" for k in self.ohne_stelle],
                *[f"widersprüchlich (nicht übernommen): {k}" for k in self.widerspruch]]


def zeilen(woerter: list[Wort], toleranz: float = 1.5) -> list[list[Wort]]:
    """Wörter einer Seite -> Zeilen (nach der Höhe, je Zeile von links nach rechts)."""
    out: list[list[Wort]] = []
    for w in sorted(woerter, key=lambda w: (w.top, w.x0)):
        if out and abs(out[-1][0].top - w.top) <= toleranz:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(z, key=lambda w: w.x0) for z in out]


def _gruppen(woerter: list[Wort], luecke: float = 20) -> list[list[Wort]]:
    """Wörter einer Zeile -> Gruppen nah beieinander liegender Wörter (eine Angabe je Gruppe)."""
    out: list[list[Wort]] = []
    for w in woerter:
        if out and w.x0 - out[-1][-1].x0 < luecke + 6 * len(out[-1][-1].text):
            out[-1].append(w)
        else:
            out.append([w])
    return out


def _ist_kopf(zeile: list[Wort]) -> bool:
    """Erste Zeile eines Kastens: links ein fettes Wort in Normalgröße (keine Überschrift)."""
    w = zeile[0]
    return w.fett and 9 <= w.size <= 12 and w.x0 < 150


def kaesten(seiten: list[list[Wort]], datei: str = "") -> list[Kasten]:
    """Seiten (je eine Liste von Wörtern) -> Kästen mit Spalten, Werten und Vermerken."""
    out: list[Kasten] = []
    for nr, woerter in enumerate(seiten, start=1):
        kasten: Kasten | None = None
        for zeile in zeilen(woerter):
            if _ist_kopf(zeile):
                links = [w for w in zeile if w.fett and w.x0 < 150]
                rechts = [w for w in zeile if w not in links]
                spalten = [Spalte(g[0].x0, " ".join(w.text for w in g)) for g in _gruppen(rechts)]
                # Überschriften („Ost“, „Teilorte“) haben keine Zähltage: kein Kasten
                kasten = Kasten(datei, nr, " ".join(w.text for w in links), "", spalten)
                if spalten:
                    out.append(kasten)
                continue
            if kasten is None or not kasten.spalten:
                continue
            erste = kasten.spalten[0].x0 - 5
            links = [w for w in zeile if w.x0 < erste]
            if links and not kasten.zusatz and links[0].size >= 9:
                kasten.zusatz = " ".join(w.text for w in links)
            je: dict[int, list[Wort]] = defaultdict(list)
            for w in zeile:
                if w.x0 >= erste:
                    i = max(k for k, s in enumerate(kasten.spalten) if s.x0 - 5 <= w.x0)
                    je[i].append(w)
            for i, ws in je.items():
                s = kasten.spalten[i]
                if ws[0].size < 9:  # Vermerk unter der Spalte
                    s.vermerk = " ".join(filter(None, [s.vermerk, " ".join(w.text for w in ws)]))
                    continue
                for a, b in zip(ws, ws[1:], strict=False):
                    if _ZAHL.match(a.text) and b.text in EINHEIT:
                        s.werte[b.text] = int(a.text.replace(".", ""))
    return out


def datum(text: str) -> date | None:
    m = _DATUM.match(text.strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def _stelle(k: Kasten, s: Spalte, stellen: list[dict]) -> tuple[dict | None, str | None]:
    """Die Zählstelle der Quelldatei zu Kasten und Spalte (mit Vermerk, wo sie einen nennt) und
    die Richtung, wo die Zählstelle ihre Werte je Richtung aus eigenen Kästen hat."""
    passend = []
    for st in stellen:
        if k.schluessel in st.get("kaesten", []):
            passend.append((st, None))
        for richtung, schluessel in st.get("je_richtung", {}).items():
            if schluessel == k.schluessel:
                passend.append((st, richtung))
    for st, richtung in passend:
        if st.get("vermerk") and st["vermerk"] == s.vermerk:
            return st, richtung
    return next(((st, r) for st, r in passend if not st.get("vermerk")), (None, None))


def _zahl(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def zaehlungen(kaesten_: list[Kasten], quelle: dict, bericht: Bericht) -> Iterator[Zaehlung]:
    """Kästen -> Zählungen (je Zählstelle und Tag eine, Kfz und Rad zusammen)."""
    stellen = quelle["stellen"]
    dateien = {d["datei"]: d for d in quelle["dateien"]}
    # (Stelle, Tag) -> Gruppe -> Richtung (None: Querschnitt) -> Werte
    werte: dict[tuple[str, date], dict[str, dict[str | None, set[int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(set)))
    vermerke: dict[tuple[str, date], set[str]] = defaultdict(set)
    datei_je: dict[tuple[str, date], str] = {}
    ohne: set[str] = set()
    for k in kaesten_:
        bericht.kaesten += 1
        for s in k.spalten:
            for einheit, wert in s.werte.items():
                bericht.werte += 1
                tag = datum(s.kopf)
                gruppe = EINHEIT.get(einheit)
                st, richtung = _stelle(k, s, stellen)
                if gruppe is None:
                    bericht.nicht[einheit] += 1
                elif tag is None:
                    bericht.nicht[f"kein Datum ({s.kopf})"] += 1
                elif any(n in s.vermerk for n in NICHT):
                    bericht.nicht[s.vermerk] += 1
                elif st is None:
                    bericht.nicht["Kasten ohne Zählstelle"] += 1
                    ohne.add(k.schluessel)
                else:
                    werte[(st["id"], tag)][gruppe][richtung].add(wert)
                    if s.vermerk and s.vermerk != st.get("vermerk"):
                        vermerke[(st["id"], tag)].add(
                            f"{s.vermerk} ({richtung})" if richtung else s.vermerk)
                    datei_je[(st["id"], tag)] = k.datei
                    bericht.uebernommen += 1
    bericht.ohne_stelle = sorted(ohne)
    nach_id = {st["id"]: st for st in stellen}
    for (sid, tag), gruppen in sorted(werte.items()):
        st = nach_id[sid]
        richtungen = list(st.get("je_richtung", {})) or [None]
        summen: dict[str, int] = {}
        je_richtung: list[str] = []
        for g, je in gruppen.items():
            if any(len(w) > 1 for w in je.values()):
                bericht.widerspruch.append(f"{sid} {tag} {g}: {dict(je)}")
                continue
            if set(je) != set(richtungen):
                bericht.widerspruch.append(f"{sid} {tag} {g}: nur {sorted(je)}")
                continue
            summen[g] = sum(next(iter(je[r])) for r in richtungen)
            if richtungen != [None]:
                einheit = {"kfz": "Kfz", "rad": "Rad"}[g]
                je_richtung.append(", ".join(f"{r} {_zahl(next(iter(je[r])))}" for r in richtungen)
                                   + f" {einheit}/24 h (Summe beider Richtungen)")
        if not summen:
            continue
        datei = dateien[datei_je[(sid, tag)]]
        vermerk = [f"Vermerk der Tabelle: {v}" for v in sorted(vermerke[(sid, tag)])]
        bemerkung = "; ".join([datei["titel"], *je_richtung, *vermerk])
        bericht.zaehlungen += 1
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=f"{sid}_{tag:%Y%m%d}",
            stelle_roh=sid,
            name=st["name"],
            typ="Q",
            lon=st.get("lon"),
            lat=st.get("lat"),
            lage="geokodiert" if st.get("lon") is not None else None,
            datum=tag,
            fenster=[(0, 1440)],
            intervall=None,
            summen=summen,
            land=quelle["land"],
            richtungen=2 if richtungen != [None] else st.get("richtungen"),
            kategorien=" und ".join({"kfz": "Kfz", "rad": "Rad"}[g] for g in summen)
                       + " je 24 Stunden (Tabelle der Stadt)",
            rohdatei=datei["url"],
            bemerkung=bemerkung,
            hinweise=list(st.get("hinweise", [])),
            zusatz={"genauigkeit": st.get("genauigkeit")},
        )


def lese_pdf(pfad: Path) -> list[list[Wort]]:
    import pdfplumber

    seiten = []
    with pdfplumber.open(pfad) as pdf:
        for s in pdf.pages:
            seiten.append([Wort(w["text"], w["x0"], w["top"], round(w["size"], 1),
                                "Bold" in w["fontname"])
                           for w in s.extract_words(extra_attrs=["size", "fontname"],
                                                    x_tolerance=1.5)])
    return seiten


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    alle: list[Kasten] = []
    for d in quelle["dateien"]:
        pfad = pfade.roh / quelle["code"] / d["datei"]
        if pfad.exists():
            alle += kaesten(lese_pdf(pfad), d["datei"])
    yield from zaehlungen(alle, quelle, bericht)
