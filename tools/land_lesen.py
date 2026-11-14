"""Werkzeug: die starken Treffer aus tools/land.py lesen (Runde 3, Teil 2) – kompakt.

Je Kommune bis zu sechs Seiten aus Sitemap, Suche und Startseite, deren Adresse oder Linktext nach
Zählwerten klingt (STARK in land.py), ohne Bebauungspläne und Ausschreibungen. Je Seite: Titel,
Zählbegriffe mit Anzahl, kurze Auszüge um die stärksten Begriffe und die verlinkten Dateien (PDF,
XLSX, CSV) eine Ebene tief – PDF als Text (pdftotext, höchstens 60 Seiten), XLSX mit Blattnamen
und ersten Zeilen, CSV mit den ersten Zeilen. Die Dateien selbst bleiben nicht liegen.

Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py, auch für die Kennungen von Claude).
Nur Standardbibliothek (+ pdftotext). Aufruf: python3 tools/land_lesen.py ergebnis/runde3/NI [minuten]
"""

import concurrent.futures as cf
import io
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/runde3/NI")
MINUTEN = float(sys.argv[2]) if len(sys.argv) > 2 else 50
ENDE = time.time() + MINUTEN * 60
JE_KOMMUNE = 6

_Z = r"z(?:ae|ä|a)hl"
STARK = re.compile(
    rf"verkehrs{_Z}|{_Z}stell|{_Z}dat|verkehrsmeng|rad{_Z}|radverkehrs{_Z}|fahrrad{_Z}|verkehrserheb"
    rf"|knotenpunkt{_Z}|querschnitts{_Z}|verkehrsst(?:ae|ä|a)rke|verkehrsbelast|dauer{_Z}|passanten{_Z}"
    rf"|fu(?:ss|ß)g(?:ae|ä|a)nger{_Z}|{_Z}ergebnis|verkehrsmessung", re.I)
GEWICHT = [(rf"verkehrs{_Z}", 5), (rf"{_Z}stell", 5), (rf"{_Z}dat|{_Z}ergebnis", 5), (r"knotenpunkt|knotenstr", 4),
           (r"querschnitt", 4), (r"verkehrsmeng", 4), (rf"dauer{_Z}", 4), (rf"rad{_Z}|fahrrad{_Z}", 3),
           (r"verkehrsst(?:ae|ä|a)rke|verkehrserheb", 3), (r"verkehrsbelast|verkehrsmessung", 2),
           (r"\.(?:pdf|xlsx?|csv)(?:\?|$|\s)", 1)]
RAUS = re.compile(r"bebauungsplan|b-?plan|bauleitplan|fl(?:ae|ä)chennutzungsplan|stellenaus|stellenangebot"
                  r"|ausschreibung|vergabe|/jobs?/|karriere|bewerb|wahl(?:ergebnis|en)|haushaltsplan", re.I)
DATEI = re.compile(r"\.(pdf|xlsx?|csv|zip)(?:\?|$)", re.I)
ZAEHL = re.compile(rf"{_Z}|verkehrsmeng|verkehrsdaten|verkehrserheb|verkehrsbelast|verkehrsst(?:ae|ä|a)rk"
                   r"|messung|querschnitt|knotenpunkt|auswertung|ergebnis|verkehrsuntersuchung|mobilit", re.I)
BEGRIFFE = {
    "knotenstrom": r"knotenstr(?:o|ö)m|knotenpunktz(?:ae|ä)hl",
    "querschnitt": r"querschnittsz(?:ae|ä)hl|querschnittsmess|querschnitt",
    "verkehrszaehlung": r"verkehrsz(?:ae|ä)hlung",
    "zaehlstelle": r"z(?:ae|ä)hlstelle|z(?:ae|ä)hlpunkt",
    "zaehldaten": r"z(?:ae|ä)hldaten|z(?:ae|ä)hlergebnis|z(?:ae|ä)hlwerte|z(?:ae|ä)hlprotokoll",
    "verkehrsmenge": r"verkehrsmenge|verkehrsst(?:ae|ä)rke|verkehrsbelastung|verkehrsaufkommen",
    "kfz_tag": r"kfz\s*/\s*(?:24\s*h|tag|d)\b|fz\s*/\s*24\s*h|\bdtv",
    "kfz_stunde": r"kfz\s*/\s*h\b|spitzenstunde",
    "intervall": r"viertelstunde|15[- ]?min|stundenwerte|stundenweise",
    "rad": r"radverkehr|fahrr(?:ae|ä)der|radfahrende|radfahrer",
    "fuss": r"fu(?:ß|ss)verkehr|fu(?:ß|ss)g(?:ae|ä)nger|passanten",
    "schwerverkehr": r"schwerverkehr|\blkw\b",
    "datei": r"\bexcel\b|\.xlsx?\b|\bcsv\b",
    "open_data": r"open[- ]?data|offene daten|opendata|datenportal",
    "lizenz": r"datenlizenz|dl-de|cc[- ]by|\bcc0\b|creative commons|nutzungsbedingung",
    "radar": r"seitenradar|radarmess|radarger(?:ae|ä)t|verkehrsstatistikger(?:ae|ä)t|messger(?:ae|ä)t|viacount"
             r"|sierzega|sdr[- ]?traffic|topo ?box|dialog-?display|geschwindigkeitsanzeig|geschwindigkeitsmess",
    "dauerzaehl": r"dauerz(?:ae|ä)hl|induktionsschleife|detektor|z(?:ae|ä)hlschleife",
    "radzaehl": r"eco-?counter|z(?:ae|ä)hls(?:ae|ä)ule|fahrradbarometer|radz(?:ae|ä)hl|fahrradz(?:ae|ä)hl",
    "kamera": r"videoz(?:ae|ä)hl|kamera|w(?:ae|ä)rmebild",
    "recht": r"informationsfreiheit|transparenzsatzung|\bifg\b|umweltinformation",
    "bplan": r"bebauungsplan|b-plan",
}
BEGRIFFE = {k: re.compile(v, re.I) for k, v in BEGRIFFE.items()}
KERN = ("knotenstrom", "verkehrszaehlung", "zaehldaten", "zaehlstelle", "querschnitt", "dauerzaehl",
        "radzaehl", "radar", "open_data", "lizenz", "datei", "verkehrsmenge", "kamera")


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.teile, self.links, self._a, self._at, self._weg, self.titel, self._t = [], [], None, [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._weg += 1
        elif tag == "a":
            self._a, self._at = dict(attrs).get("href"), []
        elif tag == "title":
            self._t = True
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div", "td", "th"):
            self.teile.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._weg = max(0, self._weg - 1)
        elif tag == "a" and self._a is not None:
            self.links.append([self._a, " ".join("".join(self._at).split())[:160]])
            self._a = None
        elif tag == "title":
            self._t = False

    def handle_data(self, d):
        if self._t:
            self.titel += d
        if self._weg:
            return
        self.teile.append(d)
        if self._a is not None:
            self._at.append(d)

    def text(self):
        t = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.teile))
        return re.sub(r"\n\s*\n+", "\n", t).strip()


def auszuege(text, n):
    fenster = []
    for k in KERN:
        for m in list(BEGRIFFE[k].finditer(text))[:2]:
            a, b = max(0, m.start() - 200), min(len(text), m.end() + 200)
            if any(a < y and b > x for x, y in fenster):
                continue
            fenster.append((a, b))
            if len(fenster) >= n:
                break
        if len(fenster) >= n:
            break
    return [" ".join(text[a:b].split()) for a, b in sorted(fenster)]


def zaehle(text):
    return {k: n for k, rx in BEGRIFFE.items() if (n := len(rx.findall(text)))}


def pdf(inhalt):
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / "a.pdf"
        p.write_bytes(inhalt)
        try:
            subprocess.run(["pdftotext", "-layout", "-l", "60", str(p), str(p) + ".txt"], check=False,
                           timeout=120, capture_output=True)
            text = pathlib.Path(str(p) + ".txt").read_text(errors="replace")
        except Exception as e:  # noqa: BLE001
            return f"(pdftotext: {e!r})", None
        seiten = None
        try:
            info = subprocess.run(["pdfinfo", str(p)], capture_output=True, timeout=30, text=True).stdout
            m = re.search(r"Pages:\s+(\d+)", info)
            seiten = int(m[1]) if m else None
        except Exception:  # noqa: BLE001
            pass
        return text, seiten


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def xlsx(inhalt):
    """Blattnamen und die ersten Zeilen des ersten Blatts (ohne openpyxl)."""
    z = zipfile.ZipFile(io.BytesIO(inhalt))
    namen = [s.get("name") for s in ET.fromstring(z.read("xl/workbook.xml")).iter(f"{{{NS['m']}}}sheet")]
    geteilt = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(f"{{{NS['m']}}}si"):
            geteilt.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    zeilen = []
    blatt = next((n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)), None)
    if blatt:
        for row in ET.fromstring(z.read(blatt)).iter(f"{{{NS['m']}}}row"):
            werte = []
            for c in row.iter(f"{{{NS['m']}}}c"):
                v = c.find("m:v", NS)
                w = v.text if v is not None else ""
                if c.get("t") == "s" and w:
                    w = geteilt[int(w)] if int(w) < len(geteilt) else w
                elif c.get("t") == "inlineStr":
                    w = "".join(t.text or "" for t in c.iter(f"{{{NS['m']}}}t"))
                werte.append(str(w)[:40])
            zeilen.append(" | ".join(werte)[:300])
            if len(zeilen) >= 12:
                break
    return namen, zeilen


def lies(url, tiefe=0):
    e = {"url": url}
    if time.time() > ENDE:
        return e | {"fehler": "Zeit"}
    try:
        inhalt, end, typ = R.oeffne(url, zeit=60, grenze=60_000_000)
    except R.Gesperrt:
        return e | {"fehler": "robots.txt"}
    except Exception as x:  # noqa: BLE001
        return e | {"fehler": repr(x)[:160]}
    e |= {"end": end if end != url else None, "typ": typ.split(";")[0], "bytes": len(inhalt)}
    text = ""
    if inhalt[:4] == b"%PDF":
        e["art"] = "pdf"
        text, e["seiten"] = pdf(inhalt)
    elif inhalt[:2] == b"PK" and (re.search(r"\.xlsx", url, re.I) or "spreadsheet" in typ):
        e["art"] = "xlsx"
        try:
            e["blaetter"], e["zeilen"] = xlsx(inhalt)
            text = "\n".join(e["zeilen"])
        except Exception as x:  # noqa: BLE001
            e["xlsx_fehler"] = repr(x)[:120]
    elif inhalt[:2] == b"PK":
        e["art"] = "zip"
        try:
            e["inhalt"] = zipfile.ZipFile(io.BytesIO(inhalt)).namelist()[:40]
        except Exception:  # noqa: BLE001
            pass
        return e
    elif re.search(r"\.csv(\?|$)", url, re.I) or "csv" in typ:
        e["art"] = "csv"
        text = inhalt[:6000].decode("utf-8", "replace")
        e["zeilen"] = text.splitlines()[:8]
    elif "html" in typ or inhalt.lstrip()[:1] == b"<":
        e["art"] = "html"
        t = Text()
        try:
            t.feed(inhalt.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            pass
        text = t.text()
        e["titel"] = " ".join(t.titel.split())[:160]
        if tiefe == 0:
            basis = end or url
            dateien, gesehen = [], set()
            for h, x in t.links:
                if not h or h.startswith(("mailto:", "tel:", "#", "javascript:")):
                    continue
                u = urllib.parse.urljoin(basis, h)
                s = urllib.parse.unquote(u) + " " + x
                if u in gesehen or not DATEI.search(u) or RAUS.search(s) or not ZAEHL.search(s):
                    continue
                gesehen.add(u)
                dateien.append([u, x])
            e["dateilinks"] = dateien[:12]
            e["dateien"] = [lies(u, 1) | {"linktext": x} for u, x in dateien[:3]]
    else:
        e["art"] = "sonst"
        return e
    e["begriffe"] = zaehle(text)
    e["auszuege"] = auszuege(text, 6 if tiefe == 0 else 4)
    return e


def kandidaten(eintrag):
    roh = [(u, "") for u in eintrag.get("treffer") or []]
    roh += [tuple(x) for x in (eintrag.get("such_treffer") or []) + (eintrag.get("start_treffer") or [])]
    beste = {}
    for u, t in roh:
        s = urllib.parse.unquote(u) + " " + (t or "")
        if not u.startswith("http") or not STARK.search(s) or RAUS.search(s):
            continue
        punkte = sum(g for rx, g in GEWICHT if re.search(rx, s, re.I))
        if punkte > beste.get(u, (0, ""))[0]:
            beste[u] = (punkte, t)
    return sorted(beste.items(), key=lambda kv: -kv[1][0])[:JE_KOMMUNE]


def main():
    eintraege = []
    for f in sorted(ZIEL.glob("webseiten*.json")):
        eintraege += json.loads(f.read_text())
    ziele = []
    for e in eintraege:
        for u, (p, t) in kandidaten(e):
            ziele.append((e, u, p, t))
    print("ziele", len(ziele), "kommunen", len({e["ags"] for e, *_ in ziele}), flush=True)

    def eins(z):
        e, u, p, t = z
        return {"ags": e["ags"], "name": e["name"], "art": e.get("art"), "auch": e.get("auch") or [],
                "punkte": p, "linktext": t} | lies(u)

    aus = []
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        for i, r in enumerate(pool.map(eins, ziele)):
            aus.append(r)
            if i % 100 == 0:
                (ZIEL / "lesen.json").write_text(json.dumps(aus, ensure_ascii=False))
                print("lesen", i, flush=True)
    (ZIEL / "lesen.json").write_text(json.dumps(aus, ensure_ascii=False))
    print(json.dumps({"ziele": len(ziele), "gelesen": sum(1 for a in aus if "fehler" not in a),
                      "robots": sum(1 for a in aus if a.get("fehler") == "robots.txt"),
                      "zeit": sum(1 for a in aus if a.get("fehler") == "Zeit")}), flush=True)


if __name__ == "__main__":
    main()
