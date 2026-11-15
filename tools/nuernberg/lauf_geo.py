"""Alle Zählstellen geokodieren: je Nummer alle Namen (jüngster zuerst), Ergebnis je (Nummer, Name)."""
import json, sys, re, math
from collections import defaultdict, Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import orte as O
from geo import lonlat
from pfade import ARBEIT

z = json.load(open(ARBEIT / "adapter_out.json"))
gruppen = json.load(open(ARBEIT / "gruppen.json"))
kordon, bruecken = set(gruppen["kordon"]), set(gruppen["bruecken"])
namen = defaultdict(dict)
for x in sorted(z, key=lambda x: -x["jahr"]):
    namen[x["nummer"]].setdefault(x["name"], x["jahr"])
g = O.Geokodierer()
erg = {}
for nr, ns in sorted(namen.items()):
    gruppe = "kordon" if nr in kordon else "bruecke" if nr in bruecken else None
    erg[nr] = []
    for name, jahr in ns.items():
        try:
            r = g.lage(name, gruppe)
        except Exception as e:
            r = {"fehler": repr(e)[:200]}
        r = r or {"fehler": "None"}
        if "p" in r:
            r["lonlat"] = lonlat(*r["p"])
            r.pop("p")
        erg[nr].append({"name": name, "jahr": jahr, "gruppe": gruppe, **r})
json.dump(erg, open(ARBEIT / "geo_erg.json", "w"), ensure_ascii=False, indent=1)
c = Counter(v[0].get("genauigkeit", "FEHLER") for v in erg.values())
print(len(erg), "Nummern", sorted(c.items(), key=lambda x: -x[1]))
print("Kordon:", len(kordon), "Brücken:", len(bruecken))
