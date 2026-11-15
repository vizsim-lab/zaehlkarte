"""Kevelaer: Lage der Knotenpunkte (OSM) und der Querschnitte (Zählstellenplan im Zwischenbericht).

Ergebnis: der Block `orte:` in pipeline/config/quellen/kurzzeit/kevelaer.yaml (auf `main`). Nicht
Teil der Pipeline – das Ergebnis steht fest in der Quelldatei.

1. Knotenpunkte: gemeinsamer Knoten der Straßen der Arme in OSM (Overpass-Abzug holen31); stoßen
   sie an einen Kreisverkehr, dessen Mitte. Mehrere Kandidaten: der dem Plan nächste mit den
   meisten Straßen.
2. Zählstellenplan (Zwischenbericht, Abb. 2.3.1.2-2, Seite 38, Rasterbild): blaue Punkte =
   Knotenpunkte, rote Balken = Querschnitte. Affin über die Knotenpunkte, an denen sich alle Arme
   an einer Stelle treffen (Passpunkte), Querschnitte damit umgerechnet und auf die genannte
   Straße gelegt (höchstens 150 m).

Aufruf (Python mit numpy, pillow, pyproj; poppler-utils für pdfimages), aus der Wurzel des Branchs:
    python -I tools/kevelaer/lage.py
Schreibt arbeit/lage.json, arbeit/kontrolle.png (OSM-Straßen und Ergebnis über dem Plan – nur zur
Kontrolle, nicht ins Git: der Plan gehört der Stadt) und gibt den Block `orte:` aus.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from pyproj import Transformer

HIER = Path(__file__).resolve().parent
HOLEN31 = HIER.parents[1] / "ergebnis" / "ohne_lizenz" / "holen31"
OSM = HOLEN31 / "geo_kevelaer_strassen" / "16_interpreter.json"
ZWISCHENBERICHT = HOLEN31 / "kevelaer_seite_de" / "10_zwischenbericht.pdf"
ARBEIT = HIER / "arbeit"
ZU_UTM = Transformer.from_crs(4326, 25832, always_xy=True)
ZU_GEO = Transformer.from_crs(25832, 4326, always_xy=True)

# Arme je Knotenpunkt mit den Namen in OSM (Bericht: „Wellener Landstraße L491“ = Weller Landstraße
# (L 491), „Geldener Straße“ = Gelderner Straße, „Weller Landstraße L261“ = L 361)
ARME = {
    1: ["Wettener Straße", "Gewerbering", "Hoogeweg"],
    2: ["Kölner Straße", "Wettener Straße", "Feldstraße"],
    3: ["Kölner Straße", "Weller Landstraße|L 491", "Mühlenhoeksweg"],
    4: ["Rheinstraße", "Kölner Straße", "Klever Straße"],
    5: ["Weller Landstraße|L 491", "Südstraße"],
    6: ["Weller Landstraße|L 361", "Walbecker Straße", "Weller Landstraße|L 491"],
    7: ["Weller Landstraße|L 361", "Twistedener Straße"],
    8: ["Weller Landstraße|L 361", "Wember Straße"],
    9: ["Wember Straße", "Hüls", "Heideweg"],
    10: ["Twistedener Straße", "Walbecker Straße", "Kroatenstraße"],
    11: ["Twistedener Straße", "Römerstraße", "Marktstraße", "Venloer Straße"],
    12: ["Marktstraße", "Gelderner Straße", "Bahnstraße", "Hauptstraße"],
    13: ["Wember Straße", "Kroatenstraße", "Egmontstraße"],
    14: ["Klever Straße", "Lindenstraße"],
    15: ["Egmontstraße", "Kardinal-von-Galen-Straße", "Blumenstraße"],
    16: ["Grotendonker Straße", "Rheinstraße", "Schravelen"],
}
QUER = {1: "Gelderner Straße", 2: "Sonnenstraße", 3: "Koxheidestraße", 4: "Biegstraße", 5: "Händelstraße",
        6: "Weezer Straße", 7: "Feldstraße", 8: "Willibrordstraße", 9: "Busmannstraße", 10: "Wettener Straße",
        11: "Hoogeweg", 12: "Nordstraße", 13: "Wasserstraße"}
# ungefähre Lage im Plan (Pixel), nur um die erkannten Punkte und Balken zuzuordnen
PLAN_KP = {1: (1062, 610), 2: (955, 622), 3: (1057, 882), 4: (810, 453), 5: (945, 910), 6: (612, 1128),
           7: (340, 1024), 8: (124, 832), 9: (307, 607), 10: (535, 722), 11: (633, 643), 12: (722, 576),
           13: (468, 525), 14: (689, 318), 15: (502, 494), 16: (881, 272)}
PLAN_Q = {1: (970, 850), 2: (885, 778), 3: (573, 808), 4: (607, 703), 5: (604, 963), 6: (440, 118),
          7: (930, 630), 8: (733, 527), 9: (643, 600), 10: (1205, 680), 11: (905, 452), 12: (396, 327),
          13: (378, 525)}


def utm(lon, lat):
    return ZU_UTM.transform(lon, lat)


def geo(x, y):
    lon, lat = ZU_GEO.transform(x, y)
    return round(lon, 6), round(lat, 6)


def wege():
    el = json.load(open(OSM))["elements"]
    for e in el:
        e["xy"] = [utm(p["lon"], p["lat"]) for p in e.get("geometry", [])]
        e["knoten_xy"] = dict(zip(e.get("nodes", []), e["xy"]))
    return el


def passt(e, name: str) -> bool:
    n, _, ref = name.partition("|")
    return e["tags"].get("name") == n and (not ref or e["tags"].get("ref") == ref)


def kreuzungen(el, namen: list[str]):
    """Knoten, die Wege mindestens zweier der Namen teilen; Kreisverkehr: alle seine Knoten."""
    je_knoten = defaultdict(set)
    xy = {}
    for e in el:
        for i, n in enumerate(namen):
            if passt(e, n):
                for k, p in e["knoten_xy"].items():
                    je_knoten[k].add(i)
                    xy[k] = p
    return [(len(v), xy[k], k) for k, v in je_knoten.items() if len(v) >= 2]


def kreisel(el):
    """Kreisverkehre (junction=roundabout), über gemeinsame Knoten zu Ringen verbunden."""
    ringe = [e for e in el if e["tags"].get("junction") in ("roundabout", "circular") and e["xy"]]
    eltern = list(range(len(ringe)))

    def wurzel(i):
        while eltern[i] != i:
            eltern[i] = eltern[eltern[i]]
            i = eltern[i]
        return i

    for i, a in enumerate(ringe):
        for j in range(i):
            if set(a["knoten_xy"]) & set(ringe[j]["knoten_xy"]):
                eltern[wurzel(i)] = wurzel(j)
    gruppen = defaultdict(dict)
    for i, e in enumerate(ringe):
        gruppen[wurzel(i)].update(e["knoten_xy"])
    out = []
    for knoten in gruppen.values():
        xs, ys = zip(*knoten.values())
        out.append((set(knoten), (sum(xs) / len(xs), sum(ys) / len(ys))))
    return out


def kandidaten(el, ringe, namen):
    """(Zahl der Straßen, Lage, Art) – Knoten der Straßen und Kreisverkehre, an die sie stoßen."""
    out = [(c, xy, "kreuzung") for c, xy, _ in kreuzungen(el, namen)]
    for knoten, mitte in ringe:
        dran = {i for e in el for i, n in enumerate(namen)
                if passt(e, n) and set(e["knoten_xy"]) & knoten}
        if len(dran) >= 2:
            out.append((len(dran), mitte, "kreisverkehr"))
    return out


def plan_bild(ordner: Path) -> Path:
    """Das Rasterbild des Zählstellenplans (Seite 38, zweites Bild) aus dem Zwischenbericht."""
    subprocess.run(["pdfimages", "-f", "38", "-l", "38", "-j", str(ZWISCHENBERICHT),
                    str(ordner / "zp")], check=True)
    bild = ordner / "zp-001.jpg"
    if Image.open(bild).size != (1292, 1159):
        raise SystemExit(f"Seite 38: unerwartetes Bild {Image.open(bild).size}")
    return bild


def blobs(plan: Path, farbe: str):
    im = np.array(Image.open(plan).convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    if farbe == "blau":
        m = (b > 120) & (r < 90) & (g < 110) & (b - r > 60)
    else:
        m = (r > 170) & (g < 90) & (b < 90)
    # Zusammenhangskomponenten (einfach, 4er-Nachbarschaft)
    seen = np.zeros_like(m)
    out = []
    for y, x in zip(*np.where(m)):
        if seen[y, x]:
            continue
        stack, pts = [(y, x)], []
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            pts.append((cx, cy))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < m.shape[0] and 0 <= nx < m.shape[1] and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if len(pts) >= 30:
            xs, ys = zip(*pts)
            out.append((sum(xs) / len(xs), sum(ys) / len(ys), len(pts)))
    return out


def affin(quell, ziel):
    A = np.array([[x, y, 1] for x, y in quell])
    loes = [np.linalg.lstsq(A, np.array([p[i] for p in ziel]), rcond=None)[0] for i in (0, 1)]
    return lambda x, y: (loes[0] @ [x, y, 1], loes[1] @ [x, y, 1])


def auf_strasse(el, name, p, max_m=150):
    best = None
    for e in el:
        if e["tags"].get("name") != name or len(e["xy"]) < 2:
            continue
        for a, b in zip(e["xy"], e["xy"][1:]):
            ax, ay = a
            bx, by = b
            dx, dy = bx - ax, by - ay
            t = max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy or 1)))
            q = (ax + t * dx, ay + t * dy)
            d = math.dist(p, q)
            if best is None or d < best[0]:
                best = (d, q)
    return best if best and best[0] <= max_m else None


HINWEIS_PLAN = ("Lage nach dem Zählstellenplan im Zwischenbericht zur Verkehrsuntersuchung "
                "(Abb. 2.3.1.2-2), auf Koordinaten umgerechnet und auf die Straße gelegt (etwa ±30 m).")
HINWEISE = {
    "wellener": ("K3", "K5", "Straßenname im Bericht „Wellener Landstraße“ – in OpenStreetMap "
                 "„Weller Landstraße“ (L 491)."),
    "l261": ("K7", "K8", "Der Kopf der Seite nennt „Weller Landstraße L261“, die Arme derselben "
             "Seite und Knotenpunkt 6 „L361“ (so auch OpenStreetMap)."),
    "geldener": ("K12", "Q1", "Straßenname im Bericht „Geldener Straße“ – in OpenStreetMap "
                 "„Gelderner Straße“."),
}


def orte_yaml(out: dict) -> str:
    """Der Block `orte:` der Quelldatei (Anker für wiederholte Hinweise)."""
    zeilen = ["orte:"]
    gesetzt: set[str] = set()
    for k, v in out.items():
        lon, lat = v["lonlat"]
        teile = [f"lon: {lon}", f"lat: {lat}", f"genauigkeit: {v['genauigkeit']}"]
        if k == "Q1":
            texte = [HINWEIS_PLAN, HINWEISE["geldener"][2]]
            teile.append("hinweise: [" + ", ".join(json.dumps(t, ensure_ascii=False) for t in texte) + "]")
        elif k == "Q2":
            zeilen.append(f"  {k}: &plan {{{', '.join(teile)}, hinweise: [{json.dumps(HINWEIS_PLAN, ensure_ascii=False)}]}}")
            continue
        elif k[0] == "Q":
            zeilen.append(f"  {k}: {{<<: *plan, lon: {lon}, lat: {lat}}}")
            continue
        else:
            for anker, (a, b, text) in HINWEISE.items():
                if k in (a, b):
                    if anker in gesetzt:
                        teile.append(f"hinweise: *{anker}")
                    else:
                        teile.append(f"hinweise: &{anker} [{json.dumps(text, ensure_ascii=False)}]")
                        gesetzt.add(anker)
        zeilen.append(f"  {k}: {{{', '.join(teile)}}}")
    return "\n".join(zeilen) + "\n"


def kontrollbild(plan: Path, f, el, out: dict, ziel: Path) -> None:
    o, ex, ey = f(0, 0), f(1000, 0), f(0, 1000)
    inv = np.linalg.inv(np.array([[(ex[0] - o[0]) / 1000, (ey[0] - o[0]) / 1000],
                                  [(ex[1] - o[1]) / 1000, (ey[1] - o[1]) / 1000]]))

    def zu_plan(x, y):
        v = inv @ np.array([x - o[0], y - o[1]])
        return float(v[0]), float(v[1])

    im = Image.open(plan).convert("RGB")
    dr = ImageDraw.Draw(im)
    for e in el:
        if len(e["xy"]) > 1 and e["tags"].get("highway") in (
                "primary", "secondary", "tertiary", "residential", "unclassified", "living_street"):
            dr.line([zu_plan(*p) for p in e["xy"]], fill=(0, 160, 0), width=1)
    for k, v in out.items():
        x, y = zu_plan(*utm(*v["lonlat"]))
        dr.ellipse([x - 5, y - 5, x + 5, y + 5], outline=(255, 0, 255), width=2)
        dr.text((x + 7, y - 7), k, fill=(255, 0, 255))
    im.save(ziel)


def main():
    ARBEIT.mkdir(exist_ok=True)
    el = wege()
    ringe = kreisel(el)
    with tempfile.TemporaryDirectory() as tmp:
        plan = plan_bild(Path(tmp))
        blau, rot = blobs(plan, "blau"), blobs(plan, "rot")
        plan_kp = {nr: min(blau, key=lambda b: math.dist(b[:2], p))[:2] for nr, p in PLAN_KP.items()}
        plan_q = {nr: min(rot, key=lambda b: math.dist(b[:2], p))[:2] for nr, p in PLAN_Q.items()}
        for nr, p in PLAN_KP.items():
            assert math.dist(plan_kp[nr], p) < 25, f"K{nr}: kein blauer Punkt"
        for nr, p in PLAN_Q.items():
            assert math.dist(plan_q[nr], p) < 30, f"Q{nr}: kein roter Balken"
        kand = {nr: kandidaten(el, ringe, namen) for nr, namen in ARME.items()}
        # Passpunkte: alle Straßen treffen sich an genau einer Stelle (Knoten oder Kreisverkehr)
        sicher = {}
        for nr, ks in kand.items():
            alle = len(set(ARME[nr]))
            voll = [k for k in ks if k[0] == alle]
            if voll and max(math.dist(voll[0][1], k[1]) for k in voll) < 30:
                sicher[nr] = voll[0][1]
        f = affin([plan_kp[n] for n in sicher], [sicher[n] for n in sicher])
        rest = {n: math.dist(f(*plan_kp[n]), sicher[n]) for n in sicher}
        gut = [n for n in sicher if rest[n] < 40]
        f = affin([plan_kp[n] for n in gut], [sicher[n] for n in gut])
        print("Passpunkte:", sorted(gut), file=sys.stderr)
        out = {}
        for nr, ks in sorted(kand.items()):
            p_plan = f(*plan_kp[nr])
            nah = [k for k in ks if math.dist(k[1], p_plan) < 60]
            if not nah:
                print(f"K{nr}: keine Kreuzung nahe dem Plan", file=sys.stderr)
                continue
            c, p, art = max(nah, key=lambda k: (k[0], -math.dist(k[1], p_plan)))
            out[f"K{nr}"] = {"lonlat": geo(*p), "genauigkeit": art, "strassen": c,
                             "abstand_plan": round(math.dist(p, p_plan))}
        for nr, name in QUER.items():
            p = f(*plan_q[nr])
            s = auf_strasse(el, name, p)
            out[f"Q{nr}"] = {"lonlat": geo(*(s[1] if s else p)), "genauigkeit": "plan",
                             "abstand_strasse": round(s[0]) if s else None}
        kontrollbild(plan, f, el, out, ARBEIT / "kontrolle.png")
    json.dump({"orte": out, "passpunkte": sorted(gut)}, open(ARBEIT / "lage.json", "w"),
              ensure_ascii=False, indent=1)
    for k, v in out.items():
        print(k, {a: b for a, b in v.items() if a != "lonlat"}, file=sys.stderr)
    print(orte_yaml(out), end="")


if __name__ == "__main__":
    main()
