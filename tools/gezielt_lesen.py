"""Werkzeug: Seiten aus einer Liste („Kommune | URL“) gezielt lesen – wie tools/land_lesen.py, aber
mit mehr Auszügen je Seite und Datei. Jeder Abruf nur, wenn robots.txt ihn erlaubt.
Aufruf: python3 tools/gezielt_lesen.py ergebnis/runde3/gezielt1 tools/r3_gezielt_1.txt
"""

import concurrent.futures as cf
import json
import pathlib
import sys

sys.argv = [sys.argv[0], sys.argv[1], "40"] + sys.argv[2:]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import land_lesen as L  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
ZIEL.mkdir(parents=True, exist_ok=True)
LISTE = pathlib.Path(sys.argv[3])
_auszuege = L.auszuege
L.auszuege = lambda text, n: _auszuege(text, n * 3)  # mehr Auszüge als in der Durchsicht

ziele = [[x.strip() for x in z.split(" | ")] for z in LISTE.read_text().splitlines()
         if " | " in z and not z.startswith("#")]

# Links der HTML-Seiten (für die nächste Ebene) und auf Wunsch der ganze Text („Kommune | URL | voll“)
_text_alt = L.Text.text
_pdf_alt = L.pdf


def eins(kz):
    kommune, url, *opt = kz
    erg = {"kommune": kommune}
    gemerkt = {}

    def text(self):
        t = _text_alt(self)
        gemerkt["links"] = [[h, x] for h, x in self.links if h and not h.startswith(("mailto:", "tel:", "#", "javascript:"))]
        gemerkt["text"] = t
        return t
    L.Text.text = text  # je Aufruf gemerkt; die Werkzeugläufe sind kurz, Verwechslungen egal

    def pdf(inhalt):
        t, seiten = _pdf_alt(inhalt)
        gemerkt.setdefault("text", t)
        return t, seiten
    L.pdf = pdf
    e = L.lies(url)
    erg |= e
    if gemerkt.get("links") and e.get("art") == "html":
        import urllib.parse
        basis = e.get("end") or url
        erg["links"] = [[urllib.parse.urljoin(basis, h), x] for h, x in gemerkt["links"]
                        if L.ZAEHL.search(urllib.parse.unquote(h) + " " + x)][:60]
    if "voll" in opt:
        erg["volltext"] = (gemerkt.get("text") or "")[:60000]
    return erg


with cf.ThreadPoolExecutor(max_workers=1) as pool:  # nacheinander: Text.text wird je Aufruf ersetzt
    aus = list(pool.map(eins, ziele))
(ZIEL / "seiten.json").write_text(json.dumps(aus, ensure_ascii=False, indent=0))
print(len(aus), "gelesen", sum(1 for a in aus if "fehler" not in a))
