"""Nächste benannte Straße zu Zählstellen ohne Straßennamen, aus einem OpenStreetMap-Abzug
(Geofabrik, .osm.pbf; © OpenStreetMap-Mitwirkende, ODbL 1.0).

Für Quellen, deren Zählstellen nur einen Punkt und eine Kennung haben (Hamburg). Gesucht wird
die nächste Straße mit Namen im Umkreis von `UMKREIS_M` Metern – zuerst unter den Fahrstraßen,
dann unter allen benannten Wegen (Rad- und Fußwege). Ohne Treffer bleibt der Name leer; die
Adapter nennen die Stelle dann nach ihrer Kennung.

Geofabrik sperrt `*.osm.pbf` per robots.txt für alle Robots; die Pipeline lädt den Abzug mit einer
Ausnahme in sources.yaml (Beschluss vom 14.11.2026), nur einmal. Overpass war die erlaubte
Alternative, aber unzuverlässig (AGENTS.md, „robots.txt und die Pipeline“).
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path

FAHRSTRASSEN = {
    "motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential",
    "living_street", "motorway_link", "trunk_link", "primary_link", "secondary_link",
    "tertiary_link", "road", "busway",
}
# zweite Wahl: Zufahrten (oft mit Namen von Arealen) sowie Rad- und Fußwege
WEGE = {"service", "cycleway", "footway", "path", "pedestrian", "track", "bridleway", "steps"}
UMKREIS_M = 50.0
ZELLE = 0.002  # Grad, Raster für die Suche (rund 140 × 220 m)
LIZENZ = "Straßennamen: © OpenStreetMap-Mitwirkende, ODbL 1.0 (nächste benannte Straße)"


def _abstand_m(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Abstand Punkt–Strecke in Metern (Koordinaten schon in Metern)."""
    dx, dy = bx - ax, by - ay
    laenge = dx * dx + dy * dy
    t = 0.0 if laenge == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / laenge))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


Segment = tuple[float, float, float, float, str, str]  # lon/lat von A und B, Name, highway


def _strecken(pts: list[tuple[float, float]], name: str, hw: str, box) -> list[Segment]:
    out = []
    for (a, b), (c, d) in zip(pts, pts[1:], strict=False):
        if (max(a, c) < box[0] or min(a, c) > box[2]
                or max(b, d) < box[1] or min(b, d) > box[3]):
            continue
        out.append((a, b, c, d, name, hw))
    return out


def _box(punkte: dict[str, tuple[float, float]], rand: float = 0.01):
    lons = [p[0] for p in punkte.values()]
    lats = [p[1] for p in punkte.values()]
    return (min(lons) - rand, min(lats) - rand, max(lons) + rand, max(lats) + rand)


def naechste_strassen(osm: Path, punkte: dict[str, tuple[float, float]],
                      umkreis_m: float = UMKREIS_M) -> dict[str, dict]:
    """Aus einem Abzug: {Kennung: (lon, lat)} -> {Kennung: {name, highway, abstand_m}}."""
    import osmium

    if not punkte:
        return {}
    box = _box(punkte)
    segmente: list[Segment] = []

    class Wege(osmium.SimpleHandler):
        def way(self, w):  # noqa: D102
            hw, name = w.tags.get("highway"), w.tags.get("name")
            if not hw or not name or (hw not in FAHRSTRASSEN and hw not in WEGE):
                return
            pts = [(n.location.lon, n.location.lat) for n in w.nodes if n.location.valid()]
            segmente.extend(_strecken(pts, name, hw, box))

    Wege().apply_file(str(osm), locations=True)
    return naechste(punkte, segmente, umkreis_m)


def naechste(punkte: dict[str, tuple[float, float]], segmente: list[Segment],
             umkreis_m: float = UMKREIS_M) -> dict[str, dict]:
    """{Kennung: (lon, lat)} -> {Kennung: {name, highway, abstand_m}} (nur mit Treffer)."""
    if not punkte:
        return {}
    lat0 = sum(p[1] for p in punkte.values()) / len(punkte)
    mx, my = 111_320.0 * math.cos(math.radians(lat0)), 110_540.0

    raster: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, (a, b, c, d, _, _) in enumerate(segmente):
        for x in range(math.floor(min(a, c) / ZELLE), math.floor(max(a, c) / ZELLE) + 1):
            for y in range(math.floor(min(b, d) / ZELLE), math.floor(max(b, d) / ZELLE) + 1):
                raster[(x, y)].append(i)

    out: dict[str, dict] = {}
    for kennung, (lon, lat) in punkte.items():
        zx, zy = math.floor(lon / ZELLE), math.floor(lat / ZELLE)
        besser: dict[bool, tuple[float, int]] = {}
        for x in (zx - 1, zx, zx + 1):
            for y in (zy - 1, zy, zy + 1):
                for i in raster.get((x, y), ()):
                    a, b, c, d, _, hw = segmente[i]
                    m = _abstand_m(lon * mx, lat * my, a * mx, b * my, c * mx, d * my)
                    fahr = hw in FAHRSTRASSEN
                    if m <= umkreis_m and (fahr not in besser or m < besser[fahr][0]):
                        besser[fahr] = (m, i)
        if besser:
            m, i = besser.get(True) or besser[False]
            out[kennung] = {"name": segmente[i][4], "highway": segmente[i][5],
                            "abstand_m": round(m, 1)}
    return out
