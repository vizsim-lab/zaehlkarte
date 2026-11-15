"""Nürnberg: je Zählstelle (Nummer, Name) eine Lage aus OSM – Regeln aus geo.py."""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shapely.geometry import LineString, Point  # noqa: E402
from shapely.ops import nearest_points  # noqa: E402

import geo  # noqa: E402
from geo import RICHTUNG, haufen, lonlat, norm, xy  # noqa: E402

RICHT = r"(nördl|südl|östl|westl|nordöstl|nordwestl|südöstl|südwestl|nördlich|südlich|östlich|westlich|west)\.?"
BAHN = re.compile(r"(Bahnbrücke|Eisenbahnbrücke|DB-Brücke|Eisenbahnüberführung|Bahnüberführung)", re.I)
BAUWERK = re.compile(r"(brücke|überführung|unterführung|tunnel|autobahn|^FSW$)", re.I)


def richtung(t: str) -> str:
    t = t.lower().rstrip(".")
    t = {"nördlich": "nördl", "südlich": "südl", "östlich": "östl", "westlich": "westl", "west": "westl"}.get(t, t)
    return t


def zerlege(name: str):
    """'Erlenstegenstraße 104 (B 14 Stadtgrenze)' -> ('Erlenstegenstraße', '104', ['B 14 Stadtgrenze'])."""
    name = re.sub(r"\b(nördl|südl|östl|westl|nordöstl|nordwestl|südöstl|südwestl)\.+(?=\S)", r"\1. ", name)
    name = re.sub(r"\b(Nördl|Südl|Östl|Westl)\.", lambda m: m.group(1).lower() + ".", name)
    name = re.sub(r"\bwest\.", "westl.", name)
    name = name.replace("Str:", "Str.")
    name = re.sub(r"\bDürrrenhof", "Dürrenhof", name)
    if name.count("(") > name.count(")"):
        name = name + ")"
    name = re.sub(r"\s+[-–]\s+(Nord|Süd|Ost|West)\b", r" (\1)", name)
    zus = re.findall(r"\(([^()]*)\)", name)
    haupt = re.sub(r"\([^()]*\)", " ", name)
    m = re.match(r"^(.*?)\s+(zwischen\s+.+)$", haupt)
    if m:
        haupt, zus = m.group(1), zus + [m.group(2)]
    haupt = re.sub(r"-\s*FG\s*\d+\s*-|\bFG\s*\d+\b", " ", haupt)
    haupt = re.sub(r"\s+", " ", haupt).strip(" -–")
    nr = None
    m = re.match(r"^(.*?\D)\s+(\d+[a-z]?)$", haupt)
    if m and not re.search(r"\b(A|B)$", m.group(1)):
        haupt, nr = m.group(1).strip(), m.group(2)
    zus = [z.strip().rstrip(".") if not re.search(r"(Str|str)\.$", z.strip()) else z.strip()
           for z in zus if z.strip() and not re.fullmatch(r"(FG\s*\d*|Fußgängerbereich|Abbieger|Nord|Süd|Ost|West)", z.strip())]
    return haupt, nr, zus


LANDMARKE = {
    "schleuse": r"Schleuse Nürnberg", "paketpostamt": r"Paket|Briefzentrum|Post", "mülldeponie": r"Deponie",
    "hallenbad altenfurt": r"Hallenbad", "langwasser bad": r"Langwasser Bad", "verkehrsmuseum": r"DB Museum",
    "metro": r"^Metro", "südkaserne": r"Südkaserne", "schloß stein": r"Faber-Castell", "b14 stein schloß": r"Faber-Castell",
    "sportplatz": r".", "opernhaus": r"Opernhaus",
}


class Geokodierer:
    def __init__(self):
        self.o = geo.OSM()
        self.adr = defaultdict(list)
        for a in self.o.adressen:
            t = a.get("tags", {})
            c = a.get("center") or ({"lat": a["lat"], "lon": a["lon"]} if "lat" in a else None)
            if c and t.get("addr:street") and t.get("addr:housenumber"):
                for hn in re.split(r"[;,]", t["addr:housenumber"]):
                    self.adr[(norm(t["addr:street"]), hn.strip().lower())].append(xy(c["lon"], c["lat"]))
        self.sport = []
        for e in geo.lade("geo_nuernberg_sport"):
            c = e.get("center") or ({"lat": e["lat"], "lon": e["lon"]} if "lat" in e else None)
            if c:
                self.sport.append((e.get("tags", {}), xy(c["lon"], c["lat"])))
        self.poi = []
        for e in self.o.orte + geo.lade("geo_nuernberg_orte3") + geo.lade("geo_nuernberg_altstadt"):
            t = e.get("tags", {})
            c = e.get("center") or ({"lat": e["lat"], "lon": e["lon"]} if "lat" in e else None)
            if c and t.get("name"):
                self.poi.append((t["name"], t, xy(c["lon"], c["lat"])))

    # --- Hilfen ---------------------------------------------------------------------------
    def auf_strasse(self, ws, p, max_m=150):
        best = None
        for w in ws:
            if len(w["xy"]) < 2:
                continue
            l = LineString(w["xy"])
            d = l.distance(Point(p))
            if best is None or d < best[0]:
                q = l.interpolate(l.project(Point(p)))
                best = (d, (q.x, q.y))
        if best is None or best[0] > max_m:
            return None
        return best[1]

    def hausnummer(self, ws, strasse: str, nr: str, max_m: float = 120):
        """Punkt auf der Straße an der Adresse. Gleichnamige Straßen anderer Orte liegen im Ausschnitt
        mit (Fürth hat auch einen Nordring): Adressen in der Stadt zuerst, außerhalb nur bis 50 m
        hinter der Grenze (Gerasmühle); davon die der Straße nächste."""
        g = self.o.grenze
        treffer = []
        for a in self.adr.get((norm(strasse), nr.lower()), []):
            drin = self.in_stadt(a)
            if not drin and g.distance(Point(a)) > 50:
                continue
            if q := self.auf_strasse(ws, a, max_m):
                treffer.append((not drin, math.dist(q, a), q))
        return min(treffer)[2] if treffer else None

    def in_stadt(self, p) -> bool:
        g = self.o.grenze
        return g is None or g.contains(Point(p))

    def mitte(self, ws):
        l = self.o.linie(ws)
        if l is None:
            return None
        teile = list(getattr(l, "geoms", [l]))
        teile.sort(key=lambda g: g.length, reverse=True)
        q = teile[0].interpolate(0.5, normalized=True)
        return (q.x, q.y), sum(g.length for g in teile)

    def poi_suche(self, muster: str, nahe=None, max_m=3000):
        rx = re.compile(muster, re.I)
        kand = [(n, t, p) for n, t, p in self.poi if rx.search(n)]
        if nahe is not None:
            kand = [k for k in kand if math.dist(k[2], nahe) < max_m]
            kand.sort(key=lambda k: math.dist(k[2], nahe))
        return kand

    def stadtgrenze(self, ws):
        g = self.o.grenze
        l = self.o.linie(ws)
        if g is None or l is None:
            return None
        s = l.intersection(g.boundary)
        if s.is_empty:
            return None
        pts = [(p.x, p.y) for p in getattr(s, "geoms", [s]) if p.geom_type == "Point"]
        if not pts:
            return None
        p = haufen(pts, 80)[0]
        # 30 m stadteinwärts entlang der Straße
        for w in ws:
            if len(w["xy"]) < 2:
                continue
            lw = LineString(w["xy"])
            if lw.distance(Point(p)) < 5:
                d0 = lw.project(Point(p))
                for d in (d0 + 30, d0 - 30):
                    if 0 <= d <= lw.length:
                        q = lw.interpolate(d)
                        if g.contains(q):
                            return (q.x, q.y)
        return p

    def kreuzung_mit_linien(self, ws, linien_xy):
        l = self.o.linie(ws)
        if l is None:
            return []
        pts = []
        for lx in linien_xy:
            if len(lx) < 2:
                continue
            s = l.intersection(LineString(lx))
            if not s.is_empty:
                pts += [(p.x, p.y) for p in getattr(s, "geoms", [s]) if p.geom_type == "Point"]
        return haufen(pts, 80)

    def querstrasse(self, ws, text: str) -> str | None:
        """Name der kreuzenden Straße, der `text` am nächsten kommt (Abkürzungen, Tippfehler)."""
        import difflib
        o = self.o
        ids = {w["id"] for w in ws}
        namen = set()
        for w in ws:
            for nid in w.get("nodes", []):
                for wid in o.knoten_wege[nid] - ids:
                    t = o.weg_id[wid]["tags"]
                    for k in ("name", "tunnel:name", "bridge:name"):
                        if t.get(k):
                            namen.add(t[k])
        if not namen:
            return None
        namen = sorted(namen)  # gleiche Ähnlichkeit: immer dieselbe Wahl (Mengen haben keine feste Reihenfolge)
        n0 = norm(text)
        best = max(namen, key=lambda n: difflib.SequenceMatcher(None, n0, norm(n)).ratio())
        r = difflib.SequenceMatcher(None, n0, norm(best)).ratio()
        # Präfix-Abkürzung: „Dr.-G.-Heinem.-Str.“
        if r < 0.62:
            teile = [t for t in re.split(r"[\s.\-]+", text.lower().replace("str", "")) if t]
            for n in namen:
                nn = n.lower()
                if teile and all(t[:3] in nn for t in teile):
                    return n
            return None
        return best

    # --- Regeln ---------------------------------------------------------------------------
    def lage(self, name: str, gruppe: str | None = None) -> dict | None:
        haupt, nr, zus = zerlege(name)
        o = self.o
        ws = o.strasse(haupt)
        # Brücke / Steg als Hauptname
        if re.search(r"(brücke|steg)$", haupt, re.I):
            bw = [w for w in o.strasse(haupt) if w["tags"].get("bridge")] or o.strasse(haupt)
            if not bw:
                bw = [w for w in o.bruecken if norm(haupt) in (norm(w["tags"].get("bridge:name", "")), norm(w["tags"].get("name", "")))]
            if bw:
                kfz = [w for w in bw if w["tags"].get("highway") not in ("footway", "path", "cycleway", "steps")] or bw
                m = self.mitte(kfz)
                if m:
                    return {"p": m[0], "genauigkeit": "bruecke", "regel": f"Brücke {haupt}"}
        # Tunnel: Weg mit tunnel=* und dem Namen der Straße („Celtistunnel“ -> Celtisstraße, Tunnel)
        if re.search(r"tunnel$", haupt, re.I):
            stamm = norm(re.sub(r"(?i)\s*tunnel$", "", haupt))
            tw = [w for w in o.wege if w["tags"].get("tunnel") in ("yes", "building_passage")
                  and norm(w["tags"].get("name", "")).startswith(stamm) and w["tags"].get("highway") not in ("footway", "path", "cycleway", "steps")]
            if tw:
                m = self.mitte(tw)
                if m:
                    return {"p": m[0], "genauigkeit": "tunnel", "regel": f"Tunnel {haupt}"}
        # Tor der Altstadt
        if re.search(r"tor$", haupt, re.I) and not ws:
            k = self.poi_suche(rf"^{re.escape(haupt)}$|^{re.escape(haupt)}turm$")
            if k:
                p = k[0][2]
                alle = [w for w in o.wege if w["tags"].get("highway") in ("primary", "secondary", "tertiary", "residential", "unclassified", "pedestrian", "living_street", "service")]
                q = self.auf_strasse(alle, p, 80)
                return {"p": q or p, "genauigkeit": "tor", "regel": f"Tor {k[0][0]}"}
        # „Wiener Str./ Marthweg“: Kreuzung beider
        if not ws and "/" in haupt:
            a, b = [t.strip() for t in haupt.split("/", 1)]
            k = o.kreuzungen(a, b)
            if k:
                return {"p": k[0], "genauigkeit": "kreuzung_ohne_richtung", "regel": f"{a} × {b}"}
        if not ws:
            return {"fehler": f"Straße nicht gefunden: {haupt}"}
        # nur Straßen in Nürnberg (Ausnahme: ausdrücklich Stein/Fürth)
        if not any("Stein" in z or "Fürth" in z for z in zus):
            drin = [w for w in ws if any(self.in_stadt(p) for p in w["xy"])]
            ws = drin or ws
        # Hausnummer an der Straße selbst vor „35 m neben der Querstraße“: Wo beides genannt ist und
        # weit auseinanderliegt, bestätigen die Zählstellenpläne die Hausnummer (11b, 17a, 51, 121,
        # 231). Nicht bei Bauwerken (Brücke, Tunnel, Bahn, Autobahn) – die bezeichnen die Stelle selbst.
        if nr and zus and not any(BAUWERK.search(z) for z in zus):
            p = self.hausnummer(ws, haupt, nr)
            if p:
                return {"p": p, "genauigkeit": "hausnummer", "regel": f"{haupt} {nr}"}
        for z in zus:
            # zwischen A und B
            m = re.match(r"^zw(?:ischen|\.)\s+(.+?)\s+und\s+(.+)$", z)
            if m:
                xa, xb = m.group(1).strip(), m.group(2).strip()
                if xa.endswith("-"):  # „Volta- und Gugelstr.“
                    xa = xa[:-1] + (re.search(r"(straße|str\.?|weg|ring|gasse|platz)$", xb) or re.search(r"$", xb)).group(0)
                a = o.kreuzungen(haupt, xa)
                b = o.kreuzungen(haupt, xb)
                if a and b:
                    p = ((a[0][0] + b[0][0]) / 2, (a[0][1] + b[0][1]) / 2)
                    return {"p": self.auf_strasse(ws, p) or p, "genauigkeit": "zwischen", "regel": f"zw. {m.group(1)} und {m.group(2)}"}
            # Richtung + Querstraße / Landmarke
            m = re.match(rf"^(?:[AB]\s*\d+\s+)?{RICHT}\s+(.+)$", z, re.I)
            if m:
                r, x = richtung(m.group(1)), m.group(2).strip()
                if BAHN.search(x):
                    k = self.kreuzung_mit_linien(ws, [w["xy"] for w in o.bahn if w["tags"].get("railway") == "rail"])
                    if k:
                        q = o.versetzt(ws, k[0], r, 25) or k[0]
                        return {"p": q, "genauigkeit": "bahn", "regel": f"{r}. Bahnbrücke"}
                if re.match(r"^(AS|AK|Kreuz)\s", x):
                    kand = self.poi_suche(re.escape(x.split(" ", 1)[1]))
                    if kand:
                        p = self.auf_strasse(ws, kand[0][2], 2000)
                        if p:
                            q = o.versetzt(ws, p, r, 300) or p
                            return {"p": q, "genauigkeit": "ungefaehr", "regel": f"{r}. {x}"}
                if x in ("FSW",):
                    x = "Frankenschnellweg"
                # Ortsteil („nördl. Kornburg“, „südl. Gaulnhofen“): keine Querstraße – ungefähr, 300 m
                # in der Richtung vom Ort aus (wie bei den Anschlussstellen)
                if not o.strasse(x) and (ort := [pp for n_, t_, pp in self.poi if t_.get("place") and norm(n_) == norm(x)]):
                    p = self.auf_strasse(ws, ort[0], 2000)
                    if p:
                        q = o.versetzt(ws, p, r, 300) or p
                        return {"p": q, "genauigkeit": "ungefaehr", "regel": f"{r}. {x} (Ortsteil)"}
                k = o.kreuzungen(haupt, x)
                if not k and (q := self.querstrasse(ws, x)):
                    k = o.kreuzungen(haupt, q)
                if k:
                    p = k[0]
                    q = o.versetzt(ws, p, r, 35)
                    alle = [o.versetzt(ws, kk, r, 35) or kk for kk in k]
                    return {"p": q or p, "genauigkeit": "kreuzung" if q else "kreuzung_ohne_richtung",
                            "regel": f"{r}. {x}" + ("" if len(k) == 1 else f" ({len(k)} Kreuzungen)"), "kandidaten": alle}
                # Querstraße mit Hausnummer, Landmarke
                kand = self.poi_suche(re.escape(x))
                if kand:
                    p = self.auf_strasse(ws, kand[0][2], 400)
                    if p:
                        q = o.versetzt(ws, p, r, 35) or p
                        return {"p": q, "genauigkeit": "landmarke", "regel": f"{r}. {kand[0][0]}"}
            # Stadtgrenze
            if re.search(r"Stadtgrenze", z):
                if "Fürth" in z:
                    p = self.stadtgrenze(ws)
                else:
                    p = self.stadtgrenze(ws)
                if p:
                    return {"p": p, "genauigkeit": "stadtgrenze", "regel": "Stadtgrenze"}
            # Bahn-/Autobahnbrücke
            if BAHN.fullmatch(z.strip()) or re.match(r"^Bahnüberführung", z):
                k = self.kreuzung_mit_linien(ws, [w["xy"] for w in o.bahn if w["tags"].get("railway") in ("rail", "light_rail")])
                if k:
                    return {"p": k[0], "genauigkeit": "bahn", "regel": "Bahnbrücke" + ("" if len(k) == 1 else f" ({len(k)} Kreuzungen)"), "kandidaten": k}
            if z == "Autobahnbrücke":
                k = self.kreuzung_mit_linien(ws, [w["xy"] for w in o.wege if w["tags"].get("highway") == "motorway"])
                if k:
                    return {"p": k[0], "genauigkeit": "autobahn", "regel": "Autobahnbrücke", "kandidaten": k}
            # Adresse an anderer Straße: „Hans-Böckler-Straße 94“
            m = re.match(r"^(.*?\D)\s+(\d+[a-z]?)$", z)
            if m and (norm(m.group(1)), m.group(2).lower()) in self.adr:
                treffer = [(math.dist(p, a), p) for a in self.adr[(norm(m.group(1)), m.group(2).lower())]
                           if (p := self.auf_strasse(ws, a, 250))]
                if treffer:
                    return {"p": min(treffer)[1], "genauigkeit": "adresse", "regel": f"bei {z}"}
            # Kreisverkehr: Mitte des Kreisels an der Straße, in Richtung versetzt
            m = re.match(rf"^{RICHT}\s*Kreisverkehr$", z, re.I)
            if m:
                ids = {w["id"] for w in ws}
                kreis = [w for w in o.wege if w["tags"].get("junction") in ("roundabout", "circular")
                         and any(o.knoten_wege[nid] & ids for nid in w.get("nodes", []))]
                if kreis:
                    pts = [p for w in kreis for p in w["xy"]]
                    mitte = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
                    a = self.auf_strasse(ws, mitte, 80) or mitte
                    q = o.versetzt(ws, a, richtung(m.group(1)), 40) or a
                    return {"p": q, "genauigkeit": "kreuzung", "regel": f"{richtung(m.group(1))}. Kreisverkehr"}
            # „Brücke FSW“: Kreuzung mit dem Frankenschnellweg
            if re.fullmatch(r"Brücke FSW", z):
                k = self.kreuzung_mit_linien(ws, [w["xy"] for w in o.strasse("Frankenschnellweg")])
                if k:
                    return {"p": k[0], "genauigkeit": "bruecke", "regel": "Brücke über den Frankenschnellweg"}
            # bekannte Landmarken
            if (muster := LANDMARKE.get(z.lower())) is not None:
                if z.lower() == "sportplatz":
                    kand = [(t.get("name", "Sportplatz"), t, p) for n, t, p in self.poi if t.get("leisure") in ("pitch", "sports_centre", "stadium")]
                    kand += [(t.get("name") or "Sportplatz", t, (e_xy)) for t, e_xy in self.sport]
                else:
                    kand = self.poi_suche(muster)
                best = None
                for n_, t_, pp in kand:
                    q = self.auf_strasse(ws, pp, 600)
                    if q and (best is None or math.dist(q, pp) < best[0]):
                        best = (math.dist(q, pp), q, n_)
                if best:
                    return {"p": best[1], "genauigkeit": "landmarke", "regel": f"bei {best[2]} ({best[0]:.0f} m)"}
            # Brücke über einen Fluss: „Rednitzbrücke Katzwang“, „Pegnitzbrücke Muggenhof“
            m = re.match(r"^(Pegnitz|Rednitz)brücke", z)
            if m:
                fl = [w["xy"] for w in o.wasser if (w.get("tags") or {}).get("name") == m.group(1)]
                k = self.kreuzung_mit_linien(ws, fl)
                if k:
                    return {"p": k[0], "genauigkeit": "bruecke", "regel": z, "kandidaten": k}
            # Querstraße ohne Richtung (Kreuzung)
            if o.strasse(z) or self.querstrasse(ws, z):
                k = o.kreuzungen(haupt, z) or o.kreuzungen(haupt, self.querstrasse(ws, z) or z)
                if k:
                    return {"p": k[0], "genauigkeit": "kreuzung_ohne_richtung", "regel": f"an {z}", "kandidaten": k}
            # Landmarke
            kand = self.poi_suche(re.escape(z.replace("HP ", "").replace("Bahnhof ", "")))
            if kand:
                best = None
                for n, t, pp in kand:
                    q = self.auf_strasse(ws, pp, 500)
                    if q and (best is None or math.dist(q, pp) < best[0]):
                        best = (math.dist(q, pp), q, n)
                if best:
                    return {"p": best[1], "genauigkeit": "landmarke", "regel": f"bei {best[2]}"}
        # Hausnummer
        if nr and (p := self.hausnummer(ws, haupt, nr)):
            return {"p": p, "genauigkeit": "hausnummer", "regel": f"{haupt} {nr}"}
        # Außenkordon ohne Zusatz: Stadtgrenze
        if gruppe == "kordon":
            p = self.stadtgrenze(ws)
            if p:
                return {"p": p, "genauigkeit": "stadtgrenze", "regel": "Außenkordon: Stadtgrenze"}
        m = self.mitte(ws)
        if m:
            return {"p": m[0], "genauigkeit": "strasse", "regel": f"Mitte {haupt} ({m[1]:.0f} m)", "laenge": m[1]}
        return {"fehler": "keine Regel"}


if __name__ == "__main__":
    g = Geokodierer()
    for n in sys.argv[1:]:
        r = g.lage(n)
        if r and "p" in r:
            r["lonlat"] = lonlat(*r["p"])
        print(n, "->", {k: v for k, v in (r or {}).items() if k != "p"})
