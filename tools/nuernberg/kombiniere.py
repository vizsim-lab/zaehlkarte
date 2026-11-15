"""Lage je (Nummer, Name): Regel (OSM) und Zählstellenplan (georeferenziert) zusammenführen."""
import json, sys, math, re
from collections import defaultdict
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import orte as O
from geo import xy, lonlat, norm
from pfade import ARBEIT

SICHER = {"kreuzung", "bruecke", "hausnummer", "zwischen", "bahn", "autobahn", "adresse", "stadtgrenze", "tunnel"}
z = json.load(open(ARBEIT / "adapter_out.json"))
jahre = defaultdict(set)
for x in z:
    jahre[(x["nummer"], x["name"])].add(x["jahr"])
plaene = json.load(open(ARBEIT / "plan_orte.json"))  # nummer -> [{plan: "2025-21", lonlat}]
gruppen = json.load(open(ARBEIT / "gruppen.json"))
kordon, bruecken = set(gruppen["kordon"]), set(gruppen["bruecken"])
g = O.Geokodierer()

def planpunkt(nr, js):
    ps = [xy(*p["lonlat"]) for p in plaene.get(nr, []) if int(p["plan"][:4]) in js]
    if not ps: return None, 0
    if len(ps) == 1:  # ein Plan dieses Namens: zählen auch die Pläne anderer Jahre, wenn sie übereinstimmen
        alle = [xy(*p["lonlat"]) for p in plaene.get(nr, [])]
        ps = [p for p in alle if math.dist(p, ps[0]) < 150]
    # Median, Ausreißer (> 150 m vom Median) weg
    m = (float(np.median([p[0] for p in ps])), float(np.median([p[1] for p in ps])))
    gut = [p for p in ps if math.dist(p, m) < 150]
    if not gut: return None, 0
    return (sum(p[0] for p in gut) / len(gut), sum(p[1] for p in gut) / len(gut)), len(gut)

out = {}
for (nr, name), js in sorted(jahre.items()):
    gruppe = "kordon" if nr in kordon else "bruecke" if nr in bruecken else None
    r = g.lage(name, gruppe) or {}
    haupt = O.zerlege(name)[0]
    ws = g.o.strasse(haupt)
    p_plan, n_plan = planpunkt(nr, js)
    if p_plan is None:  # Plan eines anderen Jahrs mit demselben Straßennamen
        andere = [p for p in plaene.get(nr, [])]
        if andere and r.get("p") is None or (andere and r.get("genauigkeit") not in SICHER):
            ps = [xy(*p["lonlat"]) for p in andere]
            m = (float(np.median([p[0] for p in ps])), float(np.median([p[1] for p in ps])))
            if ws and g.auf_strasse(ws, m, 120):
                p_plan, n_plan = m, -len(ps)  # negativ: aus einem anderen Jahr
    e = {"nummer": nr, "name": name, "jahre": sorted(js), "gruppe": gruppe, "regel": r.get("regel"), "fehler": r.get("fehler")}
    rp, ra = r.get("p"), r.get("genauigkeit")
    # bei mehreren Kandidaten: der nächste zum Plan
    if rp is not None and p_plan is not None and r.get("kandidaten") and len(r["kandidaten"]) > 1:
        rp = min(r["kandidaten"], key=lambda k: math.dist(k, p_plan))
    d = math.dist(rp, p_plan) if rp is not None and p_plan is not None else None
    KFZ = [w for w in g.o.wege if w["tags"].get("highway") in ("motorway", "trunk", "primary", "secondary", "tertiary",
           "unclassified", "residential", "motorway_link", "trunk_link", "primary_link", "secondary_link", "living_street", "service")] \
        if not hasattr(g, "_kfz") else g._kfz
    g._kfz = KFZ
    def auf_plan(pp, streng):
        q = g.auf_strasse(ws, pp, 120) if ws else None
        if q is None and not streng:
            q = g.auf_strasse(KFZ, pp, 60) or pp
        return q
    if rp is not None and ra in SICHER and (d is None or d <= 150):
        wahl, art = rp, ra
    elif p_plan is not None and n_plan >= 2:  # mehrere Pläne stimmen überein
        wahl, art = auf_plan(p_plan, False), "plan"
        e["plan_jahre"] = n_plan
        if rp is not None and d is not None and d > 150:
            e["regel_verworfen"] = f"{ra}: {round(d)} m vom Plan"
    elif p_plan is not None and (rp is None or ra not in SICHER) and (q := auf_plan(p_plan, True)) is not None:
        wahl, art = q, "plan"
        e["plan_jahre"] = n_plan
    elif rp is not None:
        wahl, art = rp, ra
        if d is not None: e["pruefen"] = f"Plan {round(d)} m entfernt ({abs(n_plan)} Plan)"
    else:
        wahl, art = None, None
    e["abstand_plan"] = round(d) if d is not None else None
    e["genauigkeit"] = art
    e["lonlat"] = lonlat(*wahl) if wahl is not None else None
    out[f"{nr}|{name}"] = e
json.dump(out, open(ARBEIT / "orte_final.json", "w"), ensure_ascii=False, indent=1)
from collections import Counter
print(Counter(e["genauigkeit"] for e in out.values()))
print("prüfen:", sum(1 for e in out.values() if e.get("pruefen")))
