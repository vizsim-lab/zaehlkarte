"""Runde 4, Teil 2: die Treffer aus tools/runde4.py lesen – wie tools/land_lesen.py, mit den neuen
Begriffen (Frequenzmessung/Passanten, Verkehrsversuch, Rad-Zählsäulen, Sensoren).

Welche Seiten: bei Kreisen und bei Seiten, die Runde 3 nicht erreicht hat, alles, was nach
Zählwerten klingt (alte und neue Begriffe); bei Gemeinden, die Runde 3 schon gelesen hat, nur
die Treffer der neuen Begriffe. Je Ziel höchstens sechs Seiten, ohne Bebauungspläne und
Ausschreibungen; je Seite Titel, Begriffe, Auszüge und die verlinkten Dateien eine Ebene tief.

Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py, auch für die Kennungen von Claude).
Aufruf: python3 tools/runde4_lesen.py ergebnis/runde4/<LAND> [minuten]
"""

import pathlib
import re
import sys
import urllib.parse

ZIEL = sys.argv[1]
MINUTEN = sys.argv[2] if len(sys.argv) > 2 else "50"
sys.argv = [sys.argv[0], ZIEL, MINUTEN]  # land_lesen liest Ziel und Minuten beim Import
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import land_lesen as LL  # noqa: E402

_Z = r"z(?:ae|ä|a)hl"
STARK_NEU = re.compile(
    rf"frequenzmess|frequenz{_Z}|passantenfreq|passanten{_Z}|besucher{_Z}|besucherfrequenz"
    rf"|personen{_Z}|fu(?:ss|ß)verkehrs{_Z}|fu(?:ss|ß)g(?:ae|ä|a)ngerfreq|laserscan|hystreet"
    r"|verkehrsversuch|kiezblock|superblock|modalfilter|wirkungsanalys|vorher-?nachher"
    rf"|{_Z}s(?:ae|ä|a)ule|fahrradbarometer|eco-?counter|rad{_Z}station|verkehrsdetektion"
    r"|verkehrssensor|telraam", re.I)
STARK_ALLE = re.compile(LL.STARK.pattern + "|" + STARK_NEU.pattern, re.I)
LL.GEWICHT = LL.GEWICHT + [
    (rf"frequenz|passant|besucher{_Z}|personen{_Z}|hystreet|laserscan", 4),
    (r"verkehrsversuch|kiezblock|superblock|modalfilter|wirkungsanalys|vorher-?nachher", 3),
    (rf"{_Z}s(?:ae|ä|a)ule|fahrradbarometer|eco-?counter|rad{_Z}station", 3),
    (r"verkehrsdetektion|verkehrssensor|telraam", 3)]
LL.ZAEHL = re.compile(LL.ZAEHL.pattern + r"|frequenz|passant|besucher|personen|versuch|evaluation"
                      r"|wirkung|vorher|nachher|sensor", re.I)
NEUE_BEGRIFFE = {
    "frequenz": rf"frequenzmess|passantenfreq|passanten{_Z}|besucher{_Z}|besucherfrequenz"
                rf"|personen{_Z}|laserscann|hystreet|fu(?:ß|ss)g(?:ae|ä)nger{_Z}|fu(?:ß|ss)g(?:ae|ä)ngerfrequenz",
    "versuch": r"verkehrsversuch|kiezblock|superblock|modalfilter|vorher-?nachher|wirkungsanalys"
               r"|evaluation|begleituntersuch|schulstra(?:ß|ss)e",
    "sensor": r"lorawan|sensorthings|frost-?server|datenplattform|urban data|dashboard|telraam"
              r"|verkehrssensor|verkehrsdetektion",
}
LL.BEGRIFFE |= {k: re.compile(v, re.I) for k, v in NEUE_BEGRIFFE.items()}
LL.KERN = tuple(LL.KERN) + tuple(NEUE_BEGRIFFE)


def kandidaten(eintrag):
    """Wie land_lesen.kandidaten, aber bei schon gelesenen Gemeinden nur die neuen Begriffe."""
    stark = STARK_ALLE if (eintrag.get("art") == "kreis" or eintrag.get("vorher") != "erreicht") \
        else STARK_NEU
    roh = [(u, "") for u in eintrag.get("treffer") or []]
    roh += [tuple(x) for x in (eintrag.get("such_treffer") or []) + (eintrag.get("start_treffer") or [])]
    beste = {}
    for u, t in roh:
        s = urllib.parse.unquote(u) + " " + (t or "")
        if not u.startswith("http") or not stark.search(s) or LL.RAUS.search(s):
            continue
        punkte = sum(g for rx, g in LL.GEWICHT if re.search(rx, s, re.I))
        if punkte > beste.get(u, (0, ""))[0]:
            beste[u] = (punkte, t)
    return sorted(beste.items(), key=lambda kv: -kv[1][0])[:LL.JE_KOMMUNE]


LL.kandidaten = kandidaten

if __name__ == "__main__":
    LL.main()
