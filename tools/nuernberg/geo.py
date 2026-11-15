"""Nürnberg: Lage der Zählstellen aus OpenStreetMap ableiten (Analyse, nicht Teil der Pipeline).

Eingaben: Overpass-Abzüge aus werkzeug/erkundung (ergebnis/ohne_lizenz/holen23–30/geo_nuernberg_*).
Regeln je Name „Straße [Nr] (Zusatz)“:
- Brücke/Steg: Mitte der Brücke (bridge=yes mit dem Namen)
- Tor: Torbau (POI), auf die nächste Straße gelegt
- „(östl. X)“ usw.: Kreuzung Straße × X, 35 m in die Richtung versetzt
- „(zw. A und B)“: Mitte zwischen beiden Kreuzungen
- „Stadtgrenze“: Schnitt der Straße mit der Stadtgrenze, 30 m stadteinwärts
- Bahn-/Autobahnbrücke: Kreuzung der Straße mit Bahn bzw. Autobahn
- Landmarke: nächster Punkt der Straße zur Landmarke
- Hausnummer: Adresse, auf die Straße gelegt – auch vor „(östl. X)“, außer bei Bauwerken
- „(nördl. Ortsteil)“: ungefähr, 300 m vom Ort in der Richtung
- sonst: Mitte der Straße (ungefähr)
"""
from __future__ import annotations

import glob
import json
import math
import re
from collections import defaultdict

import pyproj
from shapely.geometry import LineString, MultiLineString, Point, Polygon, MultiPolygon
from shapely.ops import linemerge, nearest_points, unary_union, polygonize

from pfade import ERGEBNIS

H = str(ERGEBNIS)
ZU = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
AB = pyproj.Transformer.from_crs("EPSG:25832", "EPSG:4326", always_xy=True)


def lade(muster: str) -> list[dict]:
    els, ids = [], set()
    for f in sorted(glob.glob(f"{H}/*/{muster}/*.json")):
        if f.endswith("protokoll.json"):
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for e in d.get("elements", []):
            k = (e["type"], e["id"])
            if k not in ids:
                ids.add(k)
                els.append(e)
    return els


def norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"\bstr\.?$", "straße", s)
    s = re.sub(r"str\.(?=\s|$)", "straße", s)
    s = re.sub(r"\bäuß\.", "äußere", s)
    s = re.sub(r"\bhptstr\.?", "hauptstraße", s)
    s = s.replace("ß", "ss")
    return re.sub(r"[^a-zäöü0-9]", "", s)


def xy(lon, lat):
    return ZU.transform(lon, lat)


def lonlat(x, y):
    lon, lat = AB.transform(x, y)
    return round(lon, 6), round(lat, 6)


class OSM:
    def __init__(self):
        self.wege = [e for e in lade("geo_nuernberg_strassen") if e["type"] == "way"]
        self.bruecken = [e for e in lade("geo_nuernberg_bruecken") if e["type"] == "way"]
        self.bahn = [e for e in lade("geo_nuernberg_bahn") if e["type"] == "way"]
        self.orte = lade("geo_nuernberg_orte") + lade("geo_nuernberg_orte2")
        self.adressen = lade("geo_nuernberg_adressen")
        self.grenze_els = lade("geo_nuernberg_grenze")
        self.wasser = [e for e in lade("geo_nuernberg_wasser") + lade("geo_nuernberg_grenzen") if e["type"] == "way"]
        self.knoten: dict[int, tuple[float, float]] = {}
        self.nach_name: dict[str, list[dict]] = defaultdict(list)
        self.nach_ref: dict[str, list[dict]] = defaultdict(list)
        self.knoten_wege: dict[int, set[int]] = defaultdict(set)
        self.weg_id: dict[int, dict] = {}
        for w in self.wege + self.bruecken:
            if w["id"] in self.weg_id:
                continue
            self.weg_id[w["id"]] = w
            geo = w.get("geometry") or []
            w["xy"] = [xy(p["lon"], p["lat"]) for p in geo]
            for nid, p in zip(w.get("nodes", []), w["xy"]):
                self.knoten[nid] = p
                self.knoten_wege[nid].add(w["id"])
            t = w.get("tags", {})
            for k in ("name", "alt_name", "old_name", "bridge:name", "tunnel:name", "official_name"):
                if t.get(k):
                    for teil in t[k].split(";"):
                        self.nach_name[norm(teil)].append(w)
            if t.get("ref"):
                for r in t["ref"].split(";"):
                    self.nach_ref[norm(r)].append(w)
        for w in self.bahn:
            w["xy"] = [xy(p["lon"], p["lat"]) for p in w.get("geometry") or []]
        for w in self.wasser:
            w["xy"] = [xy(p["lon"], p["lat"]) for p in w.get("geometry") or []]
        self.grenze = self._grenze()

    def _grenze(self):
        linien = []
        for r in self.grenze_els:
            if r["type"] != "relation" or r.get("tags", {}).get("name") != "Nürnberg":
                continue
            for m in r.get("members", []):
                if m.get("role") in ("outer", "") and m.get("geometry"):
                    linien.append(LineString([xy(p["lon"], p["lat"]) for p in m["geometry"]]))
        if not linien:
            return None
        polys = list(polygonize(unary_union(linien)))
        return unary_union(polys) if polys else None

    # --- Straßen ---------------------------------------------------------------------------
    def strasse(self, name: str, nur_kfz: bool = False) -> list[dict]:
        n = norm(name)
        ws = list(self.nach_name.get(n, [])) or list(self.nach_ref.get(n, []))
        if not ws and n.endswith("strasse"):  # „Pirckheimer Straße“ ↔ „Pirckheimerstraße“
            ws = self.nach_name.get(n.replace(" ", ""), [])
        if nur_kfz:
            ws = [w for w in ws if w["tags"].get("highway") not in ("footway", "path", "cycleway", "steps", "platform", "bus_stop", "pedestrian")] or ws
        return ws

    def linie(self, ws: list[dict]):
        ls = [LineString(w["xy"]) for w in ws if len(w["xy"]) >= 2]
        if not ls:
            return None
        m = linemerge(MultiLineString(ls))
        return m

    def kreuzungen(self, a: str, b: str) -> list[tuple[float, float]]:
        wa, wb = self.strasse(a), self.strasse(b)
        ida, idb = {w["id"] for w in wa}, {w["id"] for w in wb}
        pts = []
        for w in wa:
            for nid in w.get("nodes", []):
                if self.knoten_wege[nid] & idb:
                    pts.append(self.knoten[nid])
        if not pts and wa and wb:  # ohne gemeinsamen Knoten: geometrischer Schnitt oder nächste Stelle < 25 m
            la, lb = self.linie(wa), self.linie(wb)
            if la is not None and lb is not None:
                s = la.intersection(lb)
                if not s.is_empty:
                    pts = [(p.x, p.y) for p in getattr(s, "geoms", [s]) if p.geom_type == "Point"]
                else:
                    p1, p2 = nearest_points(la, lb)
                    if p1.distance(p2) < 25:
                        pts = [((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)]
        return haufen(pts)

    def versetzt(self, strasse_ws: list[dict], punkt, richtung: str, meter: float = 35.0):
        """Punkt auf der Straße, von `punkt` aus `meter` weit in Himmelsrichtung."""
        ziel = RICHTUNG[richtung]
        best = None
        for w in strasse_ws:
            l = LineString(w["xy"]) if len(w["xy"]) >= 2 else None
            if l is None or l.distance(Point(punkt)) > 15:
                continue
            d0 = l.project(Point(punkt))
            for d in (d0 + meter, d0 - meter):
                if 0 <= d <= l.length:
                    q = l.interpolate(d)
                elif d < 0:
                    q = l.interpolate(0)
                else:
                    q = l.interpolate(l.length)
                v = (q.x - punkt[0], q.y - punkt[1])
                lv = math.hypot(*v)
                if lv < 3:
                    continue
                cos = (v[0] * ziel[0] + v[1] * ziel[1]) / lv
                if best is None or cos > best[0]:
                    best = (cos, (q.x, q.y))
        if best is None or best[0] < 0.2:
            return None
        return best[1]


RICHTUNG = {
    "nördl": (0, 1), "südl": (0, -1), "östl": (1, 0), "westl": (-1, 0),
    "nordöstl": (0.707, 0.707), "nordwestl": (-0.707, 0.707), "südöstl": (0.707, -0.707), "südwestl": (-0.707, -0.707),
}


def haufen(pts, r=60.0):
    """Punkte in Gruppen (r m) -> Mittelpunkte, größte Gruppe zuerst."""
    gruppen = []
    for p in pts:
        for g in gruppen:
            if math.dist(g[0], p) < r:
                g.append(p)
                break
        else:
            gruppen.append([p])
    gruppen.sort(key=len, reverse=True)
    return [(sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)) for g in gruppen]
