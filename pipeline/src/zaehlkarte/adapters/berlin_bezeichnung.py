# Portiert aus vizsim/berlin-traffic-counts_schulwege (pipeline/src/schulwege/bezeichnung.py,
# MIT, © vizsim). In der Zählkarte unter AGPL-3.0-or-later.
"""Was in der Bezeichnung einer Zählstelle steckt: PLZ, Bezirk, Straßennamen.

Typische Formen (Kopfzeile `bez`):
  "Friedrichstraße / Krausenstraße (Mitte, 10117) über Arm3"
  "Weimarer Straße (nördl. Kantstraße)   (Charlottenburg, 10625)"
  "Ungarnstraße südwestl. Indischen Straße über Arm 1 (Mitte, 13349)"
  "Goettinger Strasse suedlich Thorwaldsenstrasse    ( Berlin 41 )"   (vor 1993, keine PLZ)
Die Arme (`arm1=Friedrichstr. (N),450,0000`) nennen meist die Straßen am Knoten, oft mit
Himmelsrichtung oder Platzhaltern wie "((Osten))".
"""

from __future__ import annotations

import re
import unicodedata

# "(Bezirk, 12345)", "(Bezirk; 12345)", "(Bezirk 12345)", "(Pankow, Buch, 13125)" – überall im Text
_PLZ_HINTEN = re.compile(r"\(([^()]*?)[,;\s]*(?<!\d)(1[0-4]\d{3})\s*\)")
# "(13189 Pankow)", "(14055, Charlottenburg)"
_PLZ_VORN = re.compile(r"\(\s*(1[0-4]\d{3})(?!\d)[,;\s]*([^()]*?)\)")
_ARM_ZUSATZ = re.compile(r"\s*über\s+Arm\s*\d+.*$", re.IGNORECASE)
_LEER = re.compile(r"\s+")


def plz_und_bezirk(bez: str) -> tuple[str | None, str | None]:
    """Letzte "(Bezirk, PLZ)"-Klammer -> (PLZ, Bezirk)."""
    for muster, i_plz, i_bezirk in ((_PLZ_HINTEN, 2, 1), (_PLZ_VORN, 1, 2)):
        treffer = list(muster.finditer(bez))
        if treffer:
            m = treffer[-1]
            return m.group(i_plz), (m.group(i_bezirk).strip(" ,;") or None)
    return None, None


def kurzname(bez: str) -> str:
    """Anzeigename: ohne "(Bezirk, PLZ)", ohne "über Arm 3", ohne Ortsangabe am Ende."""
    s = bez.replace("\xa0", " ")
    ort = ortsteil(s)
    s = _PLZ_HINTEN.sub(" ", s)
    s = _PLZ_VORN.sub(" ", s)
    s = re.sub(r"\(\s*Berl+in[^()]*\)", " ", s)  # alte Postbezirke "( Berlin 41 )", "Berllin"
    s = _ARM_ZUSATZ.sub("", s)
    s = re.sub(r"\(\s*[,;]?\s*\)", " ", s)  # leere Klammern
    if ort:  # "… ( Koepenick )" am Ende
        s = re.sub(rf"\(\s*{re.escape(ort)}\s*[,;]?\s*\)\s*$", " ", s.rstrip())
    return _LEER.sub(" ", s).strip(" ,;-/!")


_ORT = re.compile(
    r"\(\s*\(?\s*(?:Berlin\s*[-\d]*\s*-?\s*)?"  # "(Rudow)", "( Berlin 1147-Mahlsdorf )"
    r"([A-ZÄÖÜ][\wäöüß.-]+(?:[- ][A-ZÄÖÜ][\wäöüß.-]+)*)"
    r"\s*\)?\s*[,;]?\s*\)"
)


def ortsteil(bez: str) -> str | None:
    """Ortsangabe ohne PLZ, z. B. "(Rudow)", "( Berlin 1147-Mahlsdorf )" -> "Mahlsdorf"."""
    plz, bezirk = plz_und_bezirk(bez)
    if bezirk:
        return bezirk
    treffer = [m.group(1) for m in _ORT.finditer(bez.replace("\xa0", " "))]
    treffer = [t for t in treffer if not re.search(r"(?i)stra(ß|ss)e|platz|allee|damm|weg\b", t)]
    return treffer[-1] if treffer else None


_ALTER_POSTBEZIRK = re.compile(r"Berl+in\s*(\d{1,4})\b")  # auch Tippfehler "Berllin 61"


def alter_postbezirk(bez: str) -> str | None:
    """Postbezirk vor 1993: West "( Berlin 41 )" -> "41", Ost "( Berlin 1017-Frdh )" -> "1017"."""
    m = _ALTER_POSTBEZIRK.search(bez or "")
    return m.group(1) if m else None


# --- Straßennamen ------------------------------------------------------------------------

# Lage-Wörter zwischen zwei Straßennamen: "Weimarer Straße (nördl. Kantstraße)"
_LAGE = re.compile(
    r"\b(?:nord|süd|sued|ost|west|nordost|nordwest|südost|suedost|südwest|suedwest)?"
    r"(?:nördl|noerdl|südl|suedl|östl|oestl|westl)(?:ich|\.)?(?:\s+der|\s+des)?\b\.?"
    r"|\b(?:auf|in)?\s*(?:Höhe|Hoehe)\b(?:\s+(?:der|des|von))?"
    r"|\bzwischen\b|\bund\b|\bbis\b|\bam\s+Knotenpunkt\b|\bKnotenpunkt\b|\bKreuzung\b|\bEcke\b"
    r"|\bnahe\b|\bvor\b|\bbei\b|\bgegenüber\b|\bEinmündung\b",
    re.IGNORECASE,
)
# Lagewörter allein ("westl.", "nordöstl.") -> Himmelsrichtung, für den Vergleich zweier Zählungen
_RICHTUNG = re.compile(
    r"\b(nord|süd|sued|ost|west)?(nördl|noerdl|südl|suedl|östl|oestl|westl)", re.I
)
_RICHTUNG_KURZ = {
    "nord": "N", "nördl": "N", "noerdl": "N", "süd": "S", "sued": "S", "südl": "S", "suedl": "S",
    "ost": "O", "östl": "O", "oestl": "O", "west": "W", "westl": "W",
}  # fmt: skip


# … mit der Straße, auf die sie sich beziehen: "(südl. Zimmerstraße)" -> ("S", {"zimmerstrasse"})
_RICHTUNG_BEZUG = re.compile(
    r"\b(nord|süd|sued|ost|west)?(nördl|noerdl|südl|suedl|östl|oestl|westl)\w*(?:\.\s*|\s+)"
    r"(?:der\s+|des\s+|vom\s+|von\s+|zur\s+|zum\s+)?([^()/,;]+)",
    re.I,
)


def lage_mit_bezug(text: str) -> frozenset[tuple[str, frozenset[str]]]:
    """Lage mit Bezug: „Heesestraße (westl. Schwabenallee)“ -> {("W", {"schwabenallee"})}.
    Die Bezugsstraßen kommen aus strassen_aus_text („Sybelstraße auf Höhe Mittelinsel“ ->
    Sybelstraße, „Reaumurstraße - Scheelestr.“ -> beide); ohne Straße („Nr. 30“) kein Eintrag."""
    out = set()
    for vor, haupt, bezug in _RICHTUNG_BEZUG.findall(text):
        strassen = frozenset(schluessel(s) for s in strassen_aus_text(bezug)) - {""}
        if strassen:
            out.add((_RICHTUNG_KURZ.get(vor.lower(), "") + _RICHTUNG_KURZ[haupt.lower()], strassen))
    return frozenset(out)


_VEKTOR = {"N": (0, 1), "S": (0, -1), "O": (1, 0), "W": (-1, 0)}


def gegenueber(a: str, b: str) -> bool:
    """Himmelsrichtungen mehr als 90° auseinander: N/S, O/W, NW/SO, NW/S … – nicht S/W
    („südl.“ und „westl.“ einer schräg laufenden Straße können dieselbe Seite meinen)."""
    va = [sum(_VEKTOR[c][k] for c in a) for k in (0, 1)]
    vb = [sum(_VEKTOR[c][k] for c in b) for k in (0, 1)]
    return va[0] * vb[0] + va[1] * vb[1] < 0


def lagewoerter(text: str) -> frozenset[str]:
    """Lageangaben in einer Bezeichnung: "Heesestraße (westl. Schwabenallee)" -> {"W"},
    "nordöstl." -> {"NO"}. Zwei Zählungen mit verschiedenen Lagewörtern liegen auf
    verschiedenen Seiten derselben Kreuzung."""
    return frozenset(
        _RICHTUNG_KURZ.get(vor.lower(), "") + _RICHTUNG_KURZ[haupt.lower()]
        for vor, haupt in _RICHTUNG.findall(text)
    )


# Hausnummern weg – aber nummerierte Straßen ("Straße 42") behalten
_HAUSNUMMER = re.compile(r"\bNr\.?\s*\d+\S*|(?<!Straße )\b\d+[a-z]?(?:/\d+)?\b")
_TRENNER = re.compile(r"\s+-\s*|\s*-\s+|[/;,()\[\]\"]|\s{3,}")
# Keine Straßen: Himmelsrichtungen und Platzhalter aus den Arm-Angaben
_KEINE_STRASSE = {
    "n",
    "s",
    "o",
    "w",
    "no",
    "nw",
    "so",
    "sw",
    "nord",
    "süd",
    "sued",
    "ost",
    "west",
    "norden",
    "süden",
    "sueden",
    "osten",
    "westen",
    "nordosten",
    "nordwesten",
    "südosten",
    "südwesten",
    "mittelinsel",
    "nebenspur",
    "nordfahrbahn",
    "südfahrbahn",
    "nur fußverkehr",
    "linksabbieger",
    "rechtsabbieger",
    "komplett",
    "fußgänger",
    "gehweg",
    "fußweg",
}
_ABK = [
    (re.compile(r"(?<=\w)str\.?(?=\s|$)", re.IGNORECASE), "straße"),  # "Friedrichstr."
    (re.compile(r"\bStr\.?(?=\s|$)"), "Straße"),  # "Potsdamer Str."
    (re.compile(r"\bCh\.?(?=\s|$)"), "Chaussee"),  # "Oranienburger Ch."
    (re.compile(r"\bPl\.?(?=\s|$)"), "Platz"),
    (re.compile(r"(?<=\w)sttraße\b", re.IGNORECASE), "straße"),  # Tippfehler "Schillersttraße"
]


def _bereinige(name: str) -> str:
    s = _LEER.sub(" ", name.replace("\xa0", " ")).strip(" ,:;-!")
    for muster, ersatz in _ABK:
        s = muster.sub(ersatz, s)
    return s.strip(" .")


def strassen_aus_text(text: str) -> list[str]:
    """Straßennamen aus Bezeichnung oder Arm-Angabe, in Lesereihenfolge, ohne Dubletten."""
    s = kurzname(text)
    s = _LAGE.sub(" / ", s)
    s = _HAUSNUMMER.sub(" ", s)
    namen: list[str] = []
    for teil in _TRENNER.split(s):
        name = _bereinige(teil)
        if len(name) < 3 or not re.search(r"[A-Za-zÄÖÜäöüß]{3}", name):
            continue
        if name.lower() in _KEINE_STRASSE:
            continue
        if name not in namen:
            namen.append(name)
    return namen


def strassen_aus_armen(kopf: dict[str, str]) -> list[str]:
    """Straßen aus arm1..arm8 ("Friedrichstr. (N),450,0000" -> "Friedrichstraße")."""
    namen: list[str] = []
    for i in range(1, 9):
        wert = kopf.get(f"arm{i}", "")
        if not wert:
            continue
        # Name = alles vor den beiden Zahlenfeldern am Ende
        name = re.sub(r",\s*-?\d+\s*,\s*\d+\s*$", "", wert)
        for n in strassen_aus_text(name):
            if n not in namen:
                namen.append(n)
    return namen


def schluessel(name: str) -> str:
    """Vergleichsform: klein, Umlaute ausgeschrieben, nur Buchstaben/Ziffern.

    "Köpenicker Straße", "Koepenicker Strasse", "Köpenicker Str." -> "koepenickerstrasse"
    """
    s = _bereinige(name).lower()
    s = s.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if c.isalnum())
    return s


def schluessel_varianten(name: str) -> list[str]:
    """Vergleichsformen inkl. Beugung: "Indischen Straße" -> auch "Indische Straße"."""
    varianten = [schluessel(name)]
    gebeugt = re.sub(
        r"(\w+)en\s+(Straße|Allee|Weg|Platz|Damm|Ufer|Ring|Chaussee|Brücke|Steig|Pfad)\b",
        r"\1e \2",
        _bereinige(name),
    )
    if schluessel(gebeugt) not in varianten:
        varianten.append(schluessel(gebeugt))
    return varianten
