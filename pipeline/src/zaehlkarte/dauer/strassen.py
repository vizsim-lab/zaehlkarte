"""Nächste benannte Straße zu Zählstellen ohne Straßennamen, aus OpenStreetMap (© OpenStreetMap-
Mitwirkende, ODbL 1.0): über eine Overpass-API (`naechste_strassen_overpass`) oder aus einem
Abzug als .osm/.osm.pbf (`naechste_strassen`).

Für Quellen, deren Zählstellen nur einen Punkt und eine Kennung haben (Hamburg). Gesucht wird
die nächste Straße mit Namen im Umkreis von `UMKREIS_M` Metern – zuerst unter den Fahrstraßen,
dann unter allen benannten Wegen (Rad- und Fußwege). Ohne Treffer bleibt der Name leer; die
Adapter nennen die Stelle dann nach ihrer Kennung.

Overpass statt Abzug: Geofabrik sperrt `*.osm.pbf` per robots.txt für alle Robots (wie
openstreetmap.fr und BBBike), overpass-api.de seine API; die Overpass-Server in sources.yaml
erlauben sie (Prüfung November 2026). Für eine Handvoll neuer Stellen ist eine Abfrage im Umkreis
ohnehin leichter als ein Abzug der ganzen Stadt.
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


def overpass_abfrage(punkte: dict[str, tuple[float, float]], umkreis_m: float = UMKREIS_M) -> str:
    teile = "".join(f'way(around:{umkreis_m:g},{lat:.6f},{lon:.6f})["highway"]["name"];'
                    for lon, lat in punkte.values())
    return f"[out:json][timeout:60];({teile});out geom;"


def segmente_aus_overpass(antwort: dict, box) -> list[Segment]:
    """Antwort von Overpass (`out geom`) -> Strecken der benannten Straßen und Wege."""
    segmente: list[Segment] = []
    for el in antwort.get("elements", []):
        tags = el.get("tags") or {}
        hw, name = tags.get("highway"), tags.get("name")
        if el.get("type") != "way" or not name or (hw not in FAHRSTRASSEN and hw not in WEGE):
            continue
        pts = [(g["lon"], g["lat"]) for g in el.get("geometry") or [] if g]
        segmente.extend(_strecken(pts, name, hw, box))
    return segmente


def naechste_strassen_overpass(server: list[str], punkte: dict[str, tuple[float, float]],
                               umkreis_m: float = UMKREIS_M, je_abfrage: int = 10
                               ) -> tuple[dict[str, dict], str | None]:
    """Über Overpass (der erste Server, der antwortet): -> (Treffer wie oben, Server)."""
    from zaehlkarte import abruf

    if not punkte:
        return {}, None
    segmente: list[Segment] = []
    liste = sorted(punkte.items())
    genutzt = None
    for i in range(0, len(liste), je_abfrage):
        teil = dict(liste[i:i + je_abfrage])
        fehler: Exception | None = None
        for url in server:
            try:
                r = abruf.hole(url, daten={"data": overpass_abfrage(teil, umkreis_m)},
                               timeout=90)
                segmente += segmente_aus_overpass(r.json(), _box(teil))
                genutzt, fehler = url, None
                break
            except Exception as e:  # noqa: BLE001 – der nächste Server
                fehler = e
        if fehler is not None:
            raise fehler
    return naechste(punkte, segmente, umkreis_m), genutzt


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
