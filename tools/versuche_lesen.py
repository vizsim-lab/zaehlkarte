"""Verkehrsversuche, Kiezblocks, Schulstraßen: Seiten und Berichte lesen (15.11.2026).

Die Kandidaten kommen aus Runde 4/4b (gesichtet, `tools/versuche_ziele.json`). Je Seite: Titel,
Begriffe, kurze Auszüge, die verlinkten Dateien (PDF, XLSX) eine Ebene tief und Unterseiten
derselben Website, die nach Auswertung oder Bericht klingen, samt deren Dateien. In jedem Text wird
gezählt, was auf Zählwerte je Intervall hindeutet: Uhrzeit-Intervalle („07:00 - 08:00“,
„7–9 Uhr“), Angaben je Stunde („Kfz/h“), Zählstellen und Querschnitte, vorher/nachher, Zeilen mit
vielen Zahlen (Tabellen). Dazu wenige kurze Auszüge um solche Stellen. Keine Volltexte und keine
Dateien im Ergebnis – CLAUDE.md: keine Berichte spiegeln, nur Zahlen übernehmen.

Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py, auch für die Kennungen von Claude).
Aufruf: python3 tools/versuche_lesen.py ergebnis/versuche [minuten]
"""

import concurrent.futures as cf
import json
import pathlib
import re
import sys
import time
import urllib.parse

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/versuche")
MINUTEN = sys.argv[2] if len(sys.argv) > 2 else "50"
sys.argv = [sys.argv[0], str(ZIEL), MINUTEN]  # land_lesen liest Ziel und Minuten beim Import
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import land_lesen as LL  # noqa: E402
import robots as R  # noqa: E402

ZIELE = json.loads((pathlib.Path(__file__).parent / "versuche_ziele.json").read_text())
DATEI = re.compile(r"\.(pdf|xlsx?|csv)(?:[?#]|$)|[?&]ext=pdf|loaddocument|/download/|media\.php/", re.I)
UNTERSEITE = re.compile(r"auswertung|evaluation|ergebnis|bericht|z(?:ae|ä)hlung|verkehrsversuch|wirkung"
                        r"|dokumentation|abschluss|zwischenbilanz|kiezblock|superblock|modalfilter", re.I)
RAUS = re.compile(r"datenschutz|impressum|barrierefrei|kontakt|newsletter|login|anmeld|formular|flyer"
                  r"|stellenangebot|stellenausschreib|karriere|ausschreibung|vergabe|veranstaltung|kalender|/suche|search|sitemap"
                  r"|facebook|instagram|twitter|youtube|linkedin|mastodon|whatsapp|\.jpe?g|\.png", re.I)
_Z = r"z(?:ae|ä|a)hl"
INTERVALL = re.compile(r"\b(?:[01]?\d|2[0-3])[:.][0-5]\d\s*(?:-|–|bis)\s*(?:[01]?\d|2[0-4])[:.][0-5]\d\b")
UHR_SPANNE = re.compile(r"\b(?:[01]?\d|2[0-3])\s*(?:-|–|bis)\s*(?:[01]?\d|2[0-4])\s*Uhr\b", re.I)
PRO_H = re.compile(r"\b(?:kfz|fz|pkw|lkw|sv|rad|r(?:ae|ä)der|radfahrende|fu(?:ss|ß)g(?:ae|ä)nger|personen)"
                   r"\s*/\s*(?:h|std|stunde)\b|\bje stunde\b|\bpro stunde\b|spitzenstunde", re.I)
ZAEHLWORT = re.compile(rf"{_Z}stelle|{_Z}punkt|{_Z}querschnitt|querschnitt|knotenstr(?:o|ö)m|{_Z}ung|gez(?:ae|ä)hlt"
                       rf"|{_Z}ergebnis|{_Z}daten|{_Z}werte", re.I)
VORHER = re.compile(r"\bvorher\b|\bnachher\b|vor dem (?:verkehrs)?versuch|w(?:ae|ä)hrend des (?:verkehrs)?versuchs"
                    r"|vorher-?nachher|nullfall|analysefall", re.I)
ARTEN = re.compile(r"\bkfz\b|\bpkw\b|\blkw\b|schwerverkehr|radverkehr|radfahrende|fu(?:ss|ß)verkehr"
                   r"|fu(?:ss|ß)g(?:ae|ä)nger|zu fu(?:ss|ß)", re.I)
ZAHL = re.compile(r"(?<![\d.,])\d{1,3}(?:\.\d{3})*(?![\d,])|(?<![\d.,])\d{1,5}(?![\d.,])")
protokoll = {"start": time.strftime("%FT%TZ", time.gmtime())}


def zahlenzeilen(text):
    """Zeilen mit mindestens fünf Zahlen – ein Hinweis auf Tabellen mit Zählwerten."""
    return sum(1 for z in text.splitlines() if len(ZAHL.findall(z)) >= 5)


def kennzahlen(text):
    return {"intervalle": len(INTERVALL.findall(text)), "uhr_spannen": len(UHR_SPANNE.findall(text)),
            "je_stunde": len(PRO_H.findall(text)), "zaehlwoerter": len(ZAEHLWORT.findall(text)),
            "vorher_nachher": len(VORHER.findall(text)), "verkehrsarten": len(ARTEN.findall(text)),
            "zahlenzeilen": zahlenzeilen(text), "zeichen": len(text)}


def stellen(text, n=4):
    """Kurze Auszüge (je höchstens 240 Zeichen) um Intervalle und Angaben je Stunde in Zeilen mit
    Zahlen – genug, um zu sehen, ob es eine Zähltabelle ist, nicht der Bericht selbst."""
    zeilen = text.splitlines()
    aus, belegt = [], set()
    for i, z in enumerate(zeilen):
        if len(aus) >= n:
            break
        if not (INTERVALL.search(z) or PRO_H.search(z) or UHR_SPANNE.search(z)):
            continue
        if len(ZAHL.findall(z)) < 3 or i in belegt:
            continue
        stueck = " / ".join(" ".join(x.split()) for x in zeilen[max(0, i - 1):i + 2] if x.strip())
        aus.append(stueck[:240])
        belegt.update(range(i - 2, i + 3))
    return aus


def lies(url, tiefe=0, seite_host=None):
    """Eine Adresse lesen (HTML, PDF, XLSX, CSV); bei HTML eine Ebene Dateien und Unterseiten."""
    e = {"url": url, "tiefe": tiefe}
    if time.time() > LL.ENDE:
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
        text, e["seiten"] = LL.pdf(inhalt)
    elif inhalt[:2] == b"PK" and (re.search(r"\.xlsx", url, re.I) or "spreadsheet" in typ):
        e["art"] = "xlsx"
        try:
            e["blaetter"], zeilen = LL.xlsx(inhalt)
            text = "\n".join(zeilen)
        except Exception as x:  # noqa: BLE001
            e["xlsx_fehler"] = repr(x)[:120]
    elif re.search(r"\.csv(\?|$)", url, re.I) or "csv" in typ:
        e["art"] = "csv"
        text = inhalt[:20000].decode("utf-8", "replace")
    elif "html" in typ or inhalt.lstrip()[:1] == b"<":
        e["art"] = "html"
        t = LL.Text()
        try:
            t.feed(inhalt.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            pass
        text = t.text()
        e["titel"] = " ".join(t.titel.split())[:160]
        if tiefe <= 1:
            basis = end or url
            host = urllib.parse.urlsplit(basis).netloc
            dateien, unter, gesehen = [], [], {url, basis}
            for h, x in t.links:
                if not h or h.startswith(("mailto:", "tel:", "#", "javascript:")):
                    continue
                u = urllib.parse.urljoin(basis, h).split("#")[0]
                s = urllib.parse.unquote(u) + " " + x
                if u in gesehen or RAUS.search(s):
                    continue
                gesehen.add(u)
                if DATEI.search(u):
                    dateien.append([u, x])
                elif tiefe == 0 and urllib.parse.urlsplit(u).netloc == host and UNTERSEITE.search(s):
                    unter.append([u, x])
            je = 6 if tiefe == 0 else 3
            e["dateilinks"] = dateien[:15]
            e["dateien"] = [lies(u, tiefe + 1, host) | {"linktext": x[:120]} for u, x in dateien[:je]]
            if tiefe == 0:
                e["unterseitenlinks"] = unter[:12]
                e["unterseiten"] = [lies(u, 1, host) | {"linktext": x[:120]} for u, x in unter[:4]]
    else:
        e["art"] = "sonst"
        return e
    e["kennzahlen"] = kennzahlen(text)
    e["stellen"] = stellen(text)
    e["begriffe"] = LL.zaehle(text)
    e["auszuege"] = LL.auszuege(text, 3)
    return e


def main():
    ZIEL.mkdir(parents=True, exist_ok=True)
    print("ziele", len(ZIELE), flush=True)

    def eins(z):
        return {k: z[k] for k in ("land", "ags", "name", "linktext")} | lies(z["url"])

    aus = []
    with cf.ThreadPoolExecutor(max_workers=10) as pool:
        for i, r in enumerate(pool.map(eins, ZIELE)):
            aus.append(r)
            if i % 20 == 0:
                (ZIEL / "lesen.json").write_text(json.dumps(aus, ensure_ascii=False))
                print("lesen", i, flush=True)
    (ZIEL / "lesen.json").write_text(json.dumps(aus, ensure_ascii=False))

    def alle(e):
        yield e
        for k in ("dateien", "unterseiten"):
            for x in e.get(k) or []:
                yield from alle(x)

    flach = [x for e in aus for x in alle(e)]
    protokoll.update({"ziele": len(ZIELE), "adressen": len(flach),
                  "gelesen": sum(1 for x in flach if "fehler" not in x),
                  "robots": sum(1 for x in flach if x.get("fehler") == "robots.txt"),
                  "zeit": sum(1 for x in flach if x.get("fehler") == "Zeit"),
                  "pdf": sum(1 for x in flach if x.get("art") == "pdf"),
                  "mit_intervallen": sum(1 for x in flach if (x.get("kennzahlen") or {}).get("intervalle", 0) >= 4),
                  "ende": time.strftime("%FT%TZ", time.gmtime())})
    (ZIEL / "protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1))
    print(json.dumps(protokoll, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
