"""Pläne georeferenzieren: Affintransformation PDF -> UTM aus sicher geokodierten Zählstellen (OSM)."""
import json, math, sys
import numpy as np
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from geo import xy, lonlat
from pfade import ARBEIT
SICHER = {"kreuzung", "bruecke", "hausnummer", "zwischen", "bahn", "autobahn", "adresse"}
erg = json.load(open(ARBEIT / "geo_erg.json"))
plaene = json.load(open(ARBEIT / "plaene.json"))
osm = {}
for nr, vs in erg.items():
    for v in vs:
        if v.get("genauigkeit") in SICHER:
            osm[nr] = xy(*v["lonlat"])
            break
def fit(P, Q):
    A = np.hstack([P, np.ones((len(P), 1))])
    M, *_ = np.linalg.lstsq(A, Q, rcond=None)
    return M
ergebnis = {}
for name, pl in plaene.items():
    pts = [p for p in pl["punkte"] if p["nummer"] in osm]
    if len(pts) < 8:
        print(name, "zu wenige Passpunkte", len(pts)); continue
    P = np.array([[p["x"], p["y"]] for p in pts]); Q = np.array([osm[p["nummer"]] for p in pts])
    aktiv = np.ones(len(pts), bool)
    for _ in range(6):
        M = fit(P[aktiv], Q[aktiv])
        R = np.linalg.norm(np.hstack([P, np.ones((len(P), 1))]) @ M - Q, axis=1)
        grenze = max(3 * np.median(R[aktiv]), 60)
        neu = R < grenze
        if (neu == aktiv).all(): break
        aktiv = neu
    massstab = math.sqrt(abs(np.linalg.det(M[:2, :])))
    print(f"{name}: {aktiv.sum()}/{len(pts)} Passpunkte, Median-Rest {np.median(R[aktiv]):.0f} m, 90%: {np.percentile(R[aktiv], 90):.0f} m, Maßstab {massstab:.1f} m/pt")
    ausreisser = sorted([(pts[i]["nummer"], round(R[i])) for i in range(len(pts)) if not aktiv[i]], key=lambda x: -x[1])
    print("   Abweichung OSM-Regel ↔ Plan (>Grenze):", ausreisser[:25])
    for p in pl["punkte"]:
        e, n = np.array([p["x"], p["y"], 1]) @ M
        ergebnis.setdefault(p["nummer"], []).append({"plan": name, "lonlat": lonlat(e, n), "rest_median": float(np.median(R[aktiv]))})
json.dump(ergebnis, open(ARBEIT / "plan_orte.json", "w"), indent=0)
print(len(ergebnis), "Nummern mit Lage aus einem Plan")
