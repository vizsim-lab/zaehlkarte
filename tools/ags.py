"""Werkzeug: Gemeindeverzeichnis (GV-ISys) des Statistischen Bundesamts als Excel ablegen – für
die Gemeindeschlüssel der Kommunen in der Datenlage (Schritt D des Strukturkonzepts).

Liest die Seite des Gemeindeverzeichnisses, sucht die Excel-Auszüge (alle politisch selbständigen
Gemeinden mit Schlüssel, Namen und Koordinaten, dazu die Kreise) und legt bis zu vier davon unter
ergebnis/ags/ ab, dazu die gefundenen Links. Ausgewertet wird lokal. Abruf nur, was robots.txt
erlaubt (tools/robots.py). Daten: © Statistisches Bundesamt (Destatis), dl-de/by-2-0.
"""

import json
import pathlib
import re
import sys
import urllib.parse

from robots import TEXTE, oeffne

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/ags")
SEITEN = [
    "https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/_inhalt.html",
    "https://www.destatis.de/EN/Themes/Countries-Regions/Regional-Statistics/OnlineListMunicipalities/"
    "list-municipalities-information-system.html",
]
# Unterseiten des Gemeindeverzeichnisses, auf denen die Excel-Auszüge liegen können (höchstens so
# viele Seiten – Crawl-delay 30 s)
UNTER = re.compile(r"/(Gemeindeverzeichnis|OnlineListMunicipalities)/")
HOECHSTENS = 10

ZIEL.mkdir(parents=True, exist_ok=True)
protokoll: dict = {"seiten": {}, "dateien": {}, "fehler": {}}
links: list[str] = []
offen, besucht = list(SEITEN), set()
while offen and len(besucht) < HOECHSTENS:
    seite = offen.pop(0)
    if seite in besucht:
        continue
    besucht.add(seite)
    try:
        html, url, art = oeffne(seite, zeit=60)
        text = html.decode("utf-8", "replace")
        hrefs = {urllib.parse.urljoin(url, h.replace("&amp;", "&"))
                 for h in re.findall(r'href="([^"#]+)', text)}
        xlsx = sorted(h for h in hrefs if ".xlsx" in h.lower())
        unter = sorted(h for h in hrefs if h.startswith("https://www.destatis.de/") and UNTER.search(h)
                       and h.split("?")[0].endswith(".html") and h not in besucht)
        protokoll["seiten"][seite] = {"abgerufen_von": url, "xlsx": xlsx, "unterseiten": unter}
        links += [g for g in xlsx if g not in links]
        offen += [u for u in unter if u not in offen]
        print("ok", seite, len(xlsx), len(unter), flush=True)
    except Exception as e:  # noqa: BLE001 – im Protokoll festhalten
        protokoll["fehler"][seite] = repr(e)
        print("fehler", seite, repr(e), flush=True)

for link in [x for x in links if "uszug" in x.lower()][:4]:
    name = urllib.parse.urlsplit(link).path.rsplit("/", 1)[-1]
    try:
        inhalt, ziel_url, art = oeffne(link, zeit=120)
        if not inhalt.startswith(b"PK"):
            raise ValueError(f"keine xlsx ({art})")
        (ZIEL / name).write_bytes(inhalt)
        protokoll["dateien"][name] = {"url": link, "abgerufen_von": ziel_url, "bytes": len(inhalt)}
        print("ok", name, len(inhalt), flush=True)
    except Exception as e:  # noqa: BLE001
        protokoll["fehler"][link] = repr(e)
        print("fehler", link, repr(e), flush=True)

protokoll["robots.txt"] = {k: v[:3000] for k, v in TEXTE.items()}
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1))
