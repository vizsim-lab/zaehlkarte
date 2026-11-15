"""orte_einheitlich.json -> Block `orte:` für pipeline/config/quellen/kurzzeit/nuernberg.yaml.

Je Nummer eine Lage; liegen Varianten (Namen) einer Nummer an verschiedenen Stellen oder trägt eine
Variante einen eigenen Hinweis (Name im Bericht vertauscht), eine Liste: `wenn` (Teil des Namens)
wählt den Eintrag, der Eintrag ohne `wenn` gilt für die übrigen Namen. Prüft am Ende, dass jeder
Name genau die Lage bekommt, die vereinheitliche.py bestimmt hat (Auswahl wie im Adapter).
"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import orte as O
from pfade import ARBEIT

HINWEIS = {
    "plan": ("plan", "Lage nach dem Zählstellenplan im Bericht (auf Koordinaten umgerechnet, etwa ±50 m)."),
    "strasse": ("strasse", "Lage ungefähr: Mitte der Straße – der Bericht nennt keine genauere Stelle."),
    "kreuzung_ohne_richtung": ("kreuzung", "Lage an der Kreuzung – auf welcher Seite gezählt wurde, nennt der Bericht nicht."),
    "landmarke": ("landmarke", "Lage beim im Namen genannten Ort (OpenStreetMap)."),
    "ungefaehr": ("ungefaehr", "Lage ungefähr – der Bericht nennt als Bezug nur einen Ortsteil oder eine Anschlussstelle."),
}
verankert = set()
o = json.load(open(ARBEIT / "orte_einheitlich.json"))
je = defaultdict(list)
for e in o.values():
    if e["lonlat"]:
        je[e["nummer"]].append(e)


def schluessel(n):
    m = re.match(r"(\d+)(.*)", n)
    return (int(m.group(1)), m.group(2)) if m else (9999, n)


def q(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def eintrag(ll, es_):
    g = es_[0]["genauigkeit"]
    anzahl[g] += 1
    h = HINWEIS.get(g)
    teile = [f"lon: {ll[0]}", f"lat: {ll[1]}", f"genauigkeit: {g}"]
    eigen = sorted({e["hinweis"] for e in es_ if e.get("hinweis")})
    if eigen:  # eigener Hinweis: ohne Anker, mit dem Hinweis zur Genauigkeit
        teile.append("hinweise: [" + ", ".join(q(x) for x in ([h[1]] if h else []) + eigen) + "]")
    elif h:
        if h[0] in verankert:
            teile.append(f"hinweise: *{h[0]}")
        else:
            verankert.add(h[0])
            teile.append(f"hinweise: &{h[0]} [{q(h[1])}]")
    return teile


def unterscheidet(t: str, eigene, fremde) -> bool:
    t = t.casefold()
    return all(t in n.casefold() for n in eigene) and not any(t in n.casefold() for n in fremde)


zeilen, anzahl, soll = [], Counter(), {}
for nr in sorted(je, key=schluessel):
    gruppen = defaultdict(list)
    for e in je[nr]:
        gruppen[(tuple(e["lonlat"]), e.get("hinweis") or "")].append(e)
        soll[(nr, e["name"])] = tuple(e["lonlat"])
    if len(gruppen) == 1:
        ((ll, _), es_), = gruppen.items()
        zeilen.append(f'  "{nr}": {{{", ".join(eintrag(ll, es_))}}}')
        continue
    # die Gruppe mit den meisten Zählungen gilt ohne `wenn`
    reihe = sorted(gruppen.items(), key=lambda kv: (-sum(len(e["jahre"]) for e in kv[1]), kv[0]))
    zeilen.append(f'  "{nr}":')
    eintraege = []
    for i, ((ll, _), es_) in enumerate(reihe):
        if i == 0:
            eintraege.append(f'    - {{{", ".join(eintrag(ll, es_))}}}')
            continue
        eigene = [e["name"] for e in es_]
        fremde = [e["name"] for (k, x) in gruppen.items() if x is not es_ for e in x]
        kand = sorted({O.zerlege(n)[0] for n in eigene}) + sorted({z for n in eigene for z in O.zerlege(n)[2]}) + sorted(eigene)
        wenn = next((t for t in kand if unterscheidet(t, eigene, fremde)), None)
        if wenn is None:
            raise SystemExit(f"{nr}: kein unterscheidender Namensteil für {eigene} gegen {fremde}")
        eintraege.append(f'    - {{wenn: {q(wenn)}, {", ".join(eintrag(ll, es_))}}}')
    zeilen += eintraege[1:] + eintraege[:1]  # Einträge mit `wenn` zuerst, der ohne zuletzt
open(ARBEIT / "orte_block.yaml", "w").write("\n".join(zeilen) + "\n")

# Probe: Auswahl wie im Adapter (src/zaehlkarte/adapters/nuernberg_pdf.py)
import yaml
orte = yaml.safe_load("orte:\n" + "\n".join(zeilen) + "\n")["orte"]
falsch = []
for (nr, name), ll in soll.items():
    ort = orte.get(nr) or {}
    if isinstance(ort, list):
        ort = next((x for x in ort if x.get("wenn") and x["wenn"].casefold() in name.casefold()),
                   next((x for x in ort if not x.get("wenn")), {}))
    if (ort.get("lon"), ort.get("lat")) != ll:
        falsch.append((nr, name))
print(len(je), "Nummern;", dict(anzahl), "| falsch zugeordnet:", falsch or "keine")
