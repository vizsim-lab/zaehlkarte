"""Werkzeug: KMK-Ferienkalender ab 2021/22 (Links von der KMK-Seite, sonst übliche Dateinamen)
als PDF und Text, und die Anhänge der Rostocker FragDenStaat-Anfrage „Verkehrszählung“ (2020)."""

import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
protokoll = {}


def hole(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as a:
        return a.read()


# 1. KMK
ferien = ZIEL / "ferien"
ferien.mkdir(parents=True, exist_ok=True)
links = set()
for seite in ("https://www.kmk.org/service/ferien.html",
              "https://www.kmk.org/service/ferien/archiv-der-ferientermine.html"):
    try:
        html = hole(seite).decode("utf-8", "replace")
        (ferien / ("seite_" + seite.rsplit("/", 1)[-1])).write_text(html, encoding="utf-8")
        for m in re.finditer(r'href="([^"]+\.pdf)"', html):
            links.add(urllib.parse.urljoin(seite, m.group(1)))
    except Exception as e:  # noqa: BLE001
        protokoll[seite] = repr(e)[:200]
kandidaten = {}
for url in sorted(links):
    m = re.search(r"(20)?(2[1-5])[_-](2[2-6])", url.rsplit("/", 1)[-1])
    if m and "FER" in url.upper():
        kandidaten.setdefault(f"20{m.group(2)}_{m.group(3)}", url)
for a in range(21, 26):
    sj = f"20{a}_{a + 1}"
    for name in (f"FER20{a}_{a + 1}.pdf", f"FER{a}_{a + 1}.pdf", f"FER20{a}_{a + 1}-neu.pdf"):
        kandidaten.setdefault(sj + "?" + name, "https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/" + name)
protokoll["links"] = sorted(links)
fertig = set()
for schluessel, url in sorted(kandidaten.items()):
    sj = schluessel.split("?")[0]
    if sj in fertig:
        continue
    try:
        daten = hole(url)
        if not daten.startswith(b"%PDF"):
            raise ValueError("kein PDF")
        pdf = ferien / f"kmk_{sj}.pdf"
        pdf.write_bytes(daten)
        subprocess.run(["pdftotext", "-layout", str(pdf), str(pdf.with_suffix(".txt"))], check=False)
        protokoll[sj] = {"url": url, "bytes": len(daten)}
        fertig.add(sj)
    except Exception as e:  # noqa: BLE001
        protokoll.setdefault(sj + "_fehler", []).append(f"{url}: {e!r}"[:200])

# 2. Rostock (FragDenStaat, Anfrage „Verkehrszählung“, 2020)
rostock = ZIEL / "rostock"
rostock.mkdir(parents=True, exist_ok=True)
anhaenge = [
    "519369/anhang/Anschreiben_konvertiert_geschwaerzt.pdf",
    "519369/anhang/Z_1250_konvertiert.pdf",
    "519369/anhang/ZUS_alle_Jahre_konvertiert.pdf",
    "519369/anhang/ZUS_pro_Jahr_konvertiert.pdf",
    "519697/anhang/K_0824.pdf",
    "519697/anhang/K_0828.pdf",
    "519697/anhang/Z_0824_konvertiert.pdf",
    "519697/anhang/Z_0828_konvertiert.pdf",
]
for a in anhaenge:
    url = "https://fragdenstaat.de/anfrage/verkehrszahlung-14/" + a
    try:
        daten = hole(url)
        pfad = rostock / a.rsplit("/", 1)[-1]
        pfad.write_bytes(daten)
        subprocess.run(["pdftotext", "-layout", str(pfad), str(pfad.with_suffix(".txt"))], check=False)
        protokoll[url] = len(daten)
    except Exception as e:  # noqa: BLE001
        protokoll[url] = repr(e)[:200]
try:
    api = hole("https://fragdenstaat.de/api/v1/request/?slug=verkehrszahlung-14")
    (rostock / "anfrage.json").write_bytes(api)
except Exception as e:  # noqa: BLE001
    protokoll["api"] = repr(e)[:200]
(ZIEL / "ferien_rostock_protokoll.json").write_text(json.dumps(protokoll, indent=1, ensure_ascii=False))
print(json.dumps({k: v for k, v in protokoll.items() if k != "links"}, indent=1)[:3000])
