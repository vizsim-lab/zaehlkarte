"""Entfernt Inhalte früherer Abrufe, die robots.txt nach RFC 9309 sperrt (Liste aus
`nachpruefen.json`, Teil „nachpruefen“ von tools/nrw2.py). Aufruf: python3 tools/robots_bereinigen.py
ergebnis/nrw4/nachpruefen.json"""

import glob
import json
import pathlib
import sys

gesperrt = {u.split(" (Prüfung")[0] for u in json.load(open(sys.argv[1]))["gesperrt"]}
HINWEIS = "robots.txt (nachträglich nach RFC 9309 geprüft) – Inhalt entfernt"
n = 0
for f in glob.glob("ergebnis/*/webseiten.json"):
    daten = json.load(open(f))
    for e in daten:
        web = e.get("web") if isinstance(e.get("web"), str) else (e.get("web") or [None])[0]
        if (e.get("suche") or {}).get("url") in gesperrt:
            e["such_treffer"], e["suche"] = [], {"url": e["suche"]["url"], "fehler": HINWEIS}
            n += 1
        if web in gesperrt:
            e["start_treffer"], e["titel"], e["generator"] = [], None, None
            e["fehler_start"] = HINWEIS
            n += 1
    pathlib.Path(f).write_text(json.dumps(daten, ensure_ascii=False, indent=1))
for f in glob.glob("ergebnis/*/seiten.json"):
    daten = json.load(open(f))
    neu = []
    for e in daten:
        if e.get("url") in gesperrt and "fehler" not in e:
            for u in e.get("unter") or []:
                if u.get("datei"):
                    for p in pathlib.Path(f).parent.joinpath("dateien").glob(u["datei"] + "*"):
                        p.unlink()
            e = {"kommune": e.get("kommune"), "url": e["url"], "fehler": HINWEIS}
            n += 1
        neu.append(e)
    pathlib.Path(f).write_text(json.dumps(neu, ensure_ascii=False, indent=1))
print("entfernt:", n)
