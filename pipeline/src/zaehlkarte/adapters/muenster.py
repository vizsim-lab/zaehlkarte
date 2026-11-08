"""Münster: manuelle Kfz-Knotenpunktzählungen der Stadt (Open Data, XLS 2000–2012, PDF 2010–2020).

Quelle: ZIP „Verkehrszählung“ (je Zählung eine XLS oder PDF; Dateiname = Knotennummer und
Zähltag, `<Knoten>_<TTMM>_<JJJJ>_<lfd. Nr.>…`) und `Zählstellen.csv` (Knotennummer, UTM 32N,
Lagebezeichnung). Gezählt von Hand (meist Studierende und Rentner) während der
Hauptverkehrszeiten im Hauptverkehrsstraßennetz. Ein Zählblatt ist ein Knotenstromplan mit den
Spitzenstunden (meist 7–8 und 16–17 Uhr); gelesen von `muenster_xls` und `muenster_pdf`.

- Gibt es eine Zählung als XLS und als PDF, gilt die XLS (Abweichungen im Bericht).
- Rad: Die Spalte „Rad“ der Kfz-Zählung ist nicht die ganze Radmenge – wo die Stadt den
  Radverkehr eigens gezählt hat (Blatt „Radverkehr“), liegt sie deutlich darunter oder steht
  auf 0. Sie geht deshalb nicht als Radverkehr in die Karte, sondern steht im Hinweis. Ein
  Blatt „Radverkehr“ gilt als Radzählung, wenn es zum selben Zähltag gehört (eins ist die
  Kopie aus einer anderen Datei).
- Zähltag aus dem Dateinamen. Ausnahmen, je mit Hinweis: Das Datum im Namen gibt es nicht
  (31.04.) oder es ist ein Wochenende, während das Zählblatt einen Werktag nennt – dann gilt
  das Blatt; oder der Name nennt zwei Daten und das Blatt bestätigt das zweite (so stehen
  einige Sonntagszählungen von 2011 unter dem Datum des Mittwochs davor).
- Knotennummer aus dem Dateinamen, sonst aus dem Blatt; ohne Knotennummer keine Lage (die
  Zählung fehlt dann, im Bericht).
- Lage aus der CSV; fehlt der Knoten dort, aus den Gauß-Krüger-Koordinaten im Blatt, über eine
  an den übrigen Knoten angepasste affine Abbildung auf UTM.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from zaehlkarte.adapters import muenster_pdf, muenster_xls
from zaehlkarte.adapters.muenster_xls import _uhr
from zaehlkarte.config import Pfade
from zaehlkarte.koordinaten import affin, affin_anpassen, utm_zu_wgs84
from zaehlkarte.modell import Zaehlung

_DATEI = re.compile(r"^(\d{6,8})[_-](\d{2})(\d{2})[_.-](\d{4})")
_DATEI_OHNE_KNOTEN = re.compile(r"^(\d{2})(\d{2})_(\d{4})_")
_TAGNAME = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")
# Gauß-Krüger-Werte im Blatt, die zu Münster passen können (Tippfehler fallen heraus)
_GK_RECHTS = (3390000, 3430000)
_GK_HOCH = (5735000, 5780000)
ENDUNGEN = (".xls", ".pdf")


@dataclass
class Bericht:
    dateien: dict[str, int] = field(default_factory=dict)
    ohne_knoten: list[str] = field(default_factory=list)
    unlesbar: list[str] = field(default_factory=list)
    doppelt: list[str] = field(default_factory=list)
    pdf_zur_xls: list[str] = field(default_factory=list)
    kfz_korrigiert: int = 0
    datum: list[str] = field(default_factory=list)
    stunden_leer: int = 0
    rad_blatt: int = 0
    rad_blatt_fremd: list[str] = field(default_factory=list)
    pdf_arme: list[int] = field(default_factory=lambda: [0, 0])
    lage_csv: int = 0
    lage_blatt: int = 0
    ohne_lage: list[str] = field(default_factory=list)
    anpassung: str = ""

    def zeilen(self) -> list[str]:
        out = [
            "gelesen: " + ", ".join(f"{n} {e}" for e, n in sorted(self.dateien.items())),
            f"Lage: {self.lage_csv} aus der CSV, {self.lage_blatt} aus dem Blatt, "
            f"{len(self.ohne_lage)} ohne",
            f"Kfz nachgerechnet (Quelle weicht ab): {self.kfz_korrigiert}",
            f"Stunden mit lauter Nullen (nicht gezählt): {self.stunden_leer}",
            f"Zähltag mit Hinweis: {len(self.datum)}",
            f"mit Blatt „Radverkehr“: {self.rad_blatt} (fremd: {len(self.rad_blatt_fremd)})",
            f"PDF-Arme mit Kfz = Summe der Fahrzeugarten: {self.pdf_arme[0]} "
            f"von {self.pdf_arme[1]}",
            f"PDF neben XLS derselben Zählung (übergangen): {len(self.pdf_zur_xls)}",
        ]
        if self.anpassung:
            out.append(f"Gauß-Krüger -> UTM: {self.anpassung}")
        out += [f"ohne Knotennummer/Datum: {d}" for d in self.ohne_knoten[:5]]
        out += [f"nicht lesbar: {d}" for d in self.unlesbar[:10]]
        out += [f"doppelt: {d}" for d in self.doppelt[:5]]
        return out


def name_schoen(roh: str) -> str:
    """'Freckenhorster Straße/ Telgter Straße' -> 'Freckenhorster Straße / Telgter Straße'."""
    return re.sub(r"\s*/\s*", " / ", " ".join(roh.split())).strip(" /")


def datei_kennung(pfad: Path) -> str:
    """Dateiname ohne Endung und ohne Ordnerpräfix aus dem ZIP („Verkehrszählung__“)."""
    return re.sub(r"^Verkehrszählung__", "", pfad.stem)


def _datum(tag: str, monat: str, jahr: str) -> date | None:
    """Datum aus Teilen des Dateinamens; None, wenn es das Datum nicht gibt oder das Jahr nicht
    in die Zeit der Zählungen passt (Tippfehler wie „1002“)."""
    try:
        d = date(int(jahr), int(monat), int(tag))
    except ValueError:
        return None
    return d if 1990 <= d.year <= 2030 else None


def aus_dateiname(kennung: str) -> tuple[str | None, date | None, date | None, bool]:
    """(Knoten, Datum, zweites Datum, ungültig) aus dem Dateinamen.

    Datum vorn: `<Knoten>_<TTMM>_<JJJJ>` (oder ohne Knoten `<TTMM>_<JJJJ>_`); zweites Datum am
    Ende: `_<Knoten>_<TTMM>_<JJJJ>` oder `_<Knoten><TTMMJJJJ>`. `ungültig` = vorn steht ein
    Datum, das es nicht gibt (31.04., Jahr 1002)."""
    m = _DATEI.match(kennung)
    if m:
        knoten, datum = m.group(1), _datum(*m.group(2, 3, 4))
    else:
        m = _DATEI_OHNE_KNOTEN.match(kennung)
        knoten, datum = None, (_datum(*m.groups()) if m else None)
    ungueltig = m is not None and datum is None
    zweites = None
    if knoten:
        rest = kennung[len(knoten):]
        m2 = re.search(rf"_{knoten}_?(\d{{2}})(\d{{2}})_?(\d{{4}})(?!\d)", rest)
        zweites = _datum(*m2.groups()) if m2 else None
    return knoten, datum, zweites, ungueltig


def zaehltag(
    name: date | None,
    zweites: date | None,
    blatt: date | None,
    wochentag: int | None,
    ungueltig: bool = False,
) -> tuple[date | None, str | None]:
    """Zähltag und, wo die Angaben abweichen, ein Hinweis (siehe Modulkopf)."""

    def den(d: date | None) -> str:
        return f"den {d:%d.%m.%Y}" if d else "ein ungültiges Datum"

    if name is None and zweites is not None:  # vorn kein (gültiges) Datum, aber am Ende
        name, zweites = zweites, None
    if name is None:
        if blatt is None:
            return None, None
        tag = blatt
        hinweis = (f"Der Dateiname nennt ein ungültiges Datum; die Karte folgt dem Zählblatt "
                   f"({den(blatt)})." if ungueltig else None)
    elif blatt in (None, name) and zweites in (None, name):
        tag, hinweis = name, None
    elif zweites is not None and zweites == blatt:
        tag = zweites
        hinweis = (f"Der Dateiname nennt {den(name)} und {den(zweites)}, das Zählblatt "
                   f"{den(zweites)}; die Karte nimmt {den(zweites)}.")
    elif blatt is not None and blatt.weekday() < 5 and name.weekday() >= 5:
        tag = blatt
        hinweis = (f"Der Dateiname nennt {den(name)} (ein {_TAGNAME[name.weekday()]}); die "
                   f"Karte folgt dem Zählblatt ({den(blatt)}).")
    else:
        tag = name
        hinweis = (f"Das Zählblatt nennt als Zähltag {den(blatt)}; die Karte folgt dem "
                   "Dateinamen." if blatt is not None and blatt != name else None)
    if tag.weekday() >= 5 and wochentag is not None and wochentag < 5:
        zusatz = (f"Laut Zählblatt war es ein {_TAGNAME[wochentag]} – der Zähltag "
                  f"({_TAGNAME[tag.weekday()]}, {tag:%d.%m.%Y}) ist unsicher.")
        hinweis = f"{hinweis} {zusatz}" if hinweis else zusatz
    return tag, hinweis


def lese_positionen(pfad: Path) -> dict[str, dict]:
    """Zählstellen.csv: KNOTEN, RECHTSWERT, HOCHWERT (UTM 32N), ZAEHLSTELLE."""
    out = {}
    with pfad.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                ost, nord = float(r["RECHTSWERT"]), float(r["HOCHWERT"])
            except (TypeError, ValueError):
                continue
            out[r["KNOTEN"].strip()] = {
                "utm": (ost, nord),
                "name": " ".join((r.get("ZAEHLSTELLE") or "").split()),
            }
    return out


def _gk(k: dict) -> tuple[float, float] | None:
    x, y = k.get("gk_x"), k.get("gk_y")
    if isinstance(x, float) and isinstance(y, float):
        if _GK_RECHTS[0] < x < _GK_RECHTS[1] and _GK_HOCH[0] < y < _GK_HOCH[1]:
            return x, y
    return None


def _utm(k: dict) -> tuple[float, float] | None:
    """UTM-Koordinaten aus dem Blatt (neuere PDFs), wenn sie in Münster liegen und nicht auf
    100 m gerundet sind (solche Angaben sind nur ungefähr)."""
    x, y = k.get("utm_x"), k.get("utm_y")
    if isinstance(x, float) and isinstance(y, float) and 390000 < x < 430000 and (
            5735000 < y < 5780000) and not (x % 100 == 0 and y % 100 == 0):
        return x, y
    return None


def _fenster(stunden: list[int]) -> list[tuple[int, int]]:
    """[7, 8, 16] -> [(420, 540), (960, 1020)] – aneinandergrenzende Stunden zusammen."""
    out: list[list[int]] = []
    for h in sorted(stunden):
        if out and out[-1][1] == h * 60:
            out[-1][1] = h * 60 + 60
        else:
            out.append([h * 60, h * 60 + 60])
    return [(a, b) for a, b in out]


def _reihe(werte: dict[int, dict], gruppe: str, h0: int, laenge: int) -> list[int | None]:
    return [werte[h0 + i][gruppe] if h0 + i in werte else None for i in range(laenge)]


def _lies(pfad: Path) -> dict:
    if pfad.suffix.lower() == ".pdf":
        return muenster_pdf.lese_datei(pfad)
    return muenster_xls.lese_datei(pfad)


def lese(quelle: dict, pfade: Pfade, bericht: Bericht | None = None) -> Iterator[Zaehlung]:
    bericht = bericht if bericht is not None else Bericht()
    ordner = pfade.roh / "muenster"
    positionen = lese_positionen(ordner / quelle["positionen"]["datei"])
    dateien = sorted(p for p in (ordner / "zip").rglob("*") if p.suffix.lower() in ENDUNGEN)
    # XLS zuerst: gibt es dieselbe Zählung auch als PDF, gilt die XLS
    dateien.sort(key=lambda p: (p.suffix.lower() != ".xls", p.name))
    gelesen = []
    for pfad in dateien:
        kennung = datei_kennung(pfad)
        endung = pfad.suffix.lower().lstrip(".")
        knoten, im_namen, zweites, ungueltig = aus_dateiname(kennung)
        try:
            d = _lies(pfad)
        except Exception as e:  # noqa: BLE001 – kaputte Datei überspringen, im Bericht
            bericht.unlesbar.append(f"{pfad.name}: {e}")
            continue
        bericht.dateien[endung] = bericht.dateien.get(endung, 0) + 1
        bericht.stunden_leer += d["kfz"]["leer"]
        if "stimmig" in d:
            bericht.pdf_arme[0] += d["stimmig"][0]
            bericht.pdf_arme[1] += d["stimmig"][1]
        knoten = knoten or d["kopf"].get("knoten")
        tag, hinweis_tag = zaehltag(
            im_namen, zweites, d["kopf"].get("datum"), d["kopf"].get("wochentag"), ungueltig
        )
        if knoten is None or tag is None:
            bericht.ohne_knoten.append(pfad.name)
            continue
        if not d["kfz"]["stunden"]:
            bericht.unlesbar.append(f"{pfad.name}: {'; '.join(d['kfz']['fehlt'])}")
            continue
        if hinweis_tag:
            bericht.datum.append(kennung)
        gelesen.append((pfad, kennung, knoten, tag, hinweis_tag, d))

    # Gauß-Krüger aus dem Blatt -> UTM, angepasst an die Knoten, die in beiden stehen
    paare = [
        (gk, positionen[kn]["utm"])
        for _, _, kn, _, _, d in gelesen
        if kn in positionen and (gk := _gk(d["kopf"]))
    ]
    parameter = None
    if len(paare) >= 10:
        parameter, rms, n = affin_anpassen(paare)
        bericht.anpassung = f"{n} Paare, mittlerer Restfehler {rms:.0f} m"
        if rms > 30:
            parameter = None

    gesehen: dict[tuple, str] = {}
    xls_tage: dict[tuple, tuple] = {}
    kennungen: set[str] = set()
    for pfad, kennung, knoten, tag, hinweis_tag, d in gelesen:
        k = d["kopf"]
        st = d["kfz"]["stunden"]
        werte = tuple(sorted((h, w["kfz"]) for h, w in st.items()))
        if (knoten, tag, werte) in gesehen:
            bericht.doppelt.append(f"{pfad.name} = {gesehen[(knoten, tag, werte)]}")
            continue
        if pfad.suffix.lower() == ".pdf" and (knoten, tag) in xls_tage:
            gleich = "gleich" if xls_tage[(knoten, tag)] == werte else "abweichend"
            bericht.pdf_zur_xls.append(f"{pfad.name} ({gleich})")
            continue
        gesehen[(knoten, tag, werte)] = pfad.name
        if pfad.suffix.lower() == ".xls":
            xls_tage[(knoten, tag)] = werte
        if kennung in kennungen:  # gleicher Name als XLS und PDF, verschiedene Zählungen
            kennung = f"{kennung}_pdf"
        kennungen.add(kennung)
        datei = re.sub(r"^Verkehrszählung__", "", pfad.name)

        hinweise = [hinweis_tag] if hinweis_tag else []
        lon = lat = lage = None
        if knoten in positionen:
            lon, lat = utm_zu_wgs84(*positionen[knoten]["utm"])
            lage = "quelle"
            bericht.lage_csv += 1
        elif utm := _utm(k):
            lon, lat = utm_zu_wgs84(*utm)
            lage = "quelle"
            hinweise.append("Lage aus den Koordinaten im Zählblatt (der Knoten fehlt in der "
                            "Positionsdatei der Stadt).")
            bericht.lage_blatt += 1
        elif parameter and (gk := _gk(k)):
            lon, lat = utm_zu_wgs84(*affin(parameter, *gk))
            lage = "quelle"
            hinweise.append("Lage aus den Gauß-Krüger-Koordinaten im Zählblatt (der Knoten fehlt "
                            "in der Positionsdatei der Stadt).")
            bericht.lage_blatt += 1
        else:
            bericht.ohne_lage.append(kennung)

        abweichend = [
            f"{_uhr(h)}: Kfz-Zellen {w['kfz_quelle']}, Fahrzeugarten {w['kfz_arten']}, "
            f"Karte {w['kfz']}"
            for h, w in sorted(st.items())
            if None not in (w["kfz_quelle"], w["kfz_arten"]) and w["kfz_quelle"] != w["kfz_arten"]
        ]
        if abweichend:
            bericht.kfz_korrigiert += 1
            hinweise.append("Im Zählblatt weichen die Kfz-Zellen und die Summe der Fahrzeugarten "
                            "voneinander ab (Formelfehler, die Ströme auslassen); die Karte nimmt "
                            "je Arm den größeren Wert (" + "; ".join(abweichend) + ").")

        rad_st: dict[int, dict] = {}
        rb = d["rad"]
        if rb and rb["stunden"]:
            rad_tag = rb["kopf"].get("datum")
            if rad_tag in (None, tag):
                rad_st = rb["stunden"]
                bericht.rad_blatt += 1
                hinweise.append("Rad aus dem eigenen Blatt „Radverkehr“ der Datei (eigene "
                                "Armaufteilung, nur Radverkehr).")
            else:
                bericht.rad_blatt_fremd.append(kennung)
                hinweise.append(f"Das Blatt „Radverkehr“ in der Datei gehört zu einer anderen "
                                f"Zählung ({rb['kopf'].get('name', '')}, {rad_tag:%d.%m.%Y}) und "
                                "fehlt deshalb.")
        if not rad_st:
            rad_kfz = [f"{_uhr(h)}: {w['rad']}" for h, w in sorted(st.items()) if w["rad"]]
            if rad_kfz:
                hinweise.append("Rad laut Spalte der Kfz-Zählung – keine vollständige "
                                "Radzählung, daher nicht in der Karte: " + "; ".join(rad_kfz) + ".")
        if d["kfz"]["fehlt"]:
            hinweise.append("Nicht übernommen: " + "; ".join(d["kfz"]["fehlt"]) + ".")
        if d["weitere"]:
            hinweise.append("Weitere Blätter oder Seiten der Datei mit anderen Zeiten oder Werten "
                            "sind nicht übernommen ("
                            + ", ".join(f"„{b}“" for b in d["weitere"]) + ").")

        alle_stunden = sorted(set(st) | set(rad_st))
        h0 = alle_stunden[0]
        laenge = alle_stunden[-1] - h0 + 1
        stunden = {"kfz": _reihe(st, "kfz", h0, laenge)}
        if all(w["sv"] is not None for w in st.values()):
            stunden["sv"] = _reihe(st, "sv", h0, laenge)
        if rad_st:
            stunden["rad"] = _reihe(rad_st, "rad", h0, laenge)

        n_arme = d["kfz"]["arme"]
        name = name_schoen(k.get("name") or positionen.get(knoten, {}).get("name") or knoten)
        yield Zaehlung(
            quelle=quelle["code"],
            kennung=kennung,
            stelle_roh=knoten,
            name=name,
            typ="Q" if n_arme == 2 else "K",
            lon=lon,
            lat=lat,
            lage=lage,
            datum=tag,
            fenster=_fenster(alle_stunden),
            intervall=60,
            h0=h0,
            stunden=stunden,
            land=quelle["land"],
            richtungen=n_arme or None,
            kategorien=(d.get("kategorien") or "Pkw, Bus, Lkw, Lz (Lastzug), Krad")
            + (", Rad" if "rad" in stunden else ""),
            rohdatei=quelle.get("portal"),
            bemerkung=f"Datei im ZIP der Stadt: {datei}",
            hinweise=hinweise,
            zusatz={"datei": datei, "blatt": d["blatt"], "arme": k.get("armnamen", {})},
        )
