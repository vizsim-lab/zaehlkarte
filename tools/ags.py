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
    "https://www.destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis/Administrativ/_inhalt.html",
]

ZIEL.mkdir(parents=True, exist_ok=True)
protokoll: dict = {"seiten": {}, "dateien": {}, "fehler": {}}
links: list[str] = []
for seite in SEITEN:
    try:
        html, url, art = oeffne(seite, zeit=60)
        text = html.decode("utf-8", "replace")
        gefunden = sorted({urllib.parse.urljoin(url, h.replace("&amp;", "&"))
                           for h in re.findall(r'href="([^"]+?\.xlsx[^"]*)"', text)})
        protokoll["seiten"][seite] = {"abgerufen_von": url, "xlsx": gefunden}
        links += [g for g in gefunden if g not in links]
        print("ok", seite, len(gefunden), flush=True)
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
