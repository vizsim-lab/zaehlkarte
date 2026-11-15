"""Je Zählstellennummer: Varianten (Namen) zusammenführen, wo sie dieselbe Stelle meinen; sonst getrennt."""
import json, sys, math, re
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import xy, lonlat, norm
from pfade import ARBEIT
import orte as O

RANG = {"plan": 0, "kreuzung": 1, "bruecke": 1, "hausnummer": 1, "zwischen": 1, "bahn": 1, "autobahn": 1,
        "adresse": 1, "stadtgrenze": 1, "tunnel": 1, "landmarke": 2, "kreuzung_ohne_richtung": 3, "strasse": 4, None: 9}
GLEICH = {  # Nummer -> (Teil des abweichenden Namens, Teil des Namens mit der Lage, Grund)
    "10d": ("Äußere Sulzbacher", "Äußere Bayreuther", "die Werte passen zur Reihe der übrigen Jahre"),
    "12a": ("Äußere Bayreuther", "Äußere Sulzbacher", "Nummer 12 ist die Sulzbacher Straße"),
    "29/9": ("Jitzhak-Rabin", "Bayernstraße", "wie in den späteren Berichten"),
}
o = json.load(open(ARBEIT / "orte_final.json"))
je = defaultdict(list)
for k, e in o.items():
    je[e["nummer"]].append(e)
for nr, es in je.items():
    gut = [e for e in es if e["lonlat"]]
    if not gut:
        continue
    def rang(e):
        r = RANG.get(e["genauigkeit"], 9)
        if e["genauigkeit"] == "plan" and abs(e.get("plan_jahre") or 1) < 2:
            r = 2  # nur ein Plan: schwächer als eine ausdrückliche Beschreibung
        return (r, -len(O.zerlege(e["name"])[2]), -len(e["jahre"]))
    lead = min(gut, key=rang)
    for e in es:
        if e is lead:
            continue
        h1, h2 = norm(O.zerlege(e["name"])[0]), norm(O.zerlege(lead["name"])[0])
        d = math.dist(xy(*e["lonlat"]), xy(*lead["lonlat"])) if e["lonlat"] else None
        tausch = GLEICH.get(nr)
        ziel = None
        if tausch and tausch[0] in e["name"]:
            ziel = next((x for x in gut if tausch[1] in x["name"]), None)
        elif d is None or (h1 == h2 and d < 400) or (d is not None and d < 150) or \
                (h1 == h2 and RANG.get(e["genauigkeit"], 9) >= 3) or \
                (h1 == h2 and not O.zerlege(e["name"])[2] and O.zerlege(lead["name"])[2]):
            ziel = lead
        if ziel is not None and ziel["lonlat"]:
            e["lonlat_eigen"], e["genauigkeit_eigen"] = e["lonlat"], e["genauigkeit"]
            e["lonlat"], e["genauigkeit"], e["wie"] = ziel["lonlat"], ziel["genauigkeit"], ziel["name"]
# abweichender Name einer Nummer (auch wenn er die Lage bestimmt hat): Hinweis an diesen Zählungen
for nr, (falsch, richtig, grund) in GLEICH.items():
    es = je.get(nr, [])
    andere = sorted({x["name"] for x in es if richtig in x["name"]}, key=lambda n: (-max(
        len(x["jahre"]) for x in es if x["name"] == n), n))
    for e in es:
        if falsch in e["name"] and andere:
            js = [str(j) for j in e["jahre"]]
            wer = (f"Der Bericht {js[0]} nennt" if len(js) == 1
                   else f"Die Berichte {', '.join(js[:-1])} und {js[-1]} nennen")
            e["hinweis"] = f"{wer} die Zählstelle so; die Lage ist die von „{andere[0]}“ ({grund})."
json.dump(o, open(ARBEIT / "orte_einheitlich.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(e["genauigkeit"] for e in o.values()))
n_orte = defaultdict(set)
for e in o.values():
    if e["lonlat"]:
        n_orte[e["nummer"]].add(tuple(e["lonlat"]))
print("Nummern mit mehreren Lagen:", {k: len(v) for k, v in n_orte.items() if len(v) > 1})
