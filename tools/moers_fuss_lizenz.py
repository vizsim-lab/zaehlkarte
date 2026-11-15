"""Moers, Fußgänger in der Steinstraße: Lizenz und Lage prüfen.

Das DCAT-Dokument der beiden Datensätze auf offenesdatenportal.de nennt keine Lizenz
(ergebnis/moers_fuss/pakete.json). Hier: die HTML-Seiten der Datensätze und einer Ressource
(Seitenleiste „Lizenz“, Tabelle „Zusätzliche Informationen“), gepackt nach
ergebnis/moers_fuss_lizenz/ – und die Lage aus OpenStreetMap (Steinstraße, Neumarkt, Neuer Wall
und Messgeräte in Moers, Overpass).

Nur über tools/robots.py (RFC 9309 für die eigene Kennung, `*` und die Kennungen von Claude,
Crawl-delay je Host).

    python3 tools/moers_fuss_lizenz.py <zielordner>
"""

from __future__ import annotations

import gzip
import html
import json
import re
import sys
import traceback
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robots  # noqa: E402

BASIS = "https://www.offenesdatenportal.de"
SEITEN = [
    "/dataset/fubgangerinnen-und-fubganger-auf-der-steinstrabe-in-moers-im-mai-2022",
    "/dataset/besucherzahlen-steinstrabe-2022-nach-tagen-stadt-moers",
    "/dataset/fubgangerinnen-und-fubganger-auf-der-steinstrabe-in-moers-im-mai-2022"
    "/resource/1b03b5c8-3f6f-482d-ac56-3a4bd60b7c51",
    "/dataset/besucherzahlen-steinstrabe-2022-nach-tagen-stadt-moers"
    "/resource/e1a8f7da-f532-48d2-8fc1-14c77f095c5b",
]
OVERPASS = ("https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter")
# Ausschnitt um die Altstadt statt der Fläche „Moers“ (die lief bei allen drei Servern in die
# Zeitgrenze, wie in Augsburg); zweiter Versuch noch kleiner, nur Wege mit Namen
ABFRAGE = """[out:json][timeout:25][bbox:51.4480,6.6220,51.4550,6.6380];
way["highway"]["name"~"^(Steinstraße|Neuer Wall|Neumarkt)$"];
out tags geom;"""
NOMINATIM = "https://nominatim.openstreetmap.org/search"
STRASSEN = ["Steinstraße", "Neuer Wall", "Neumarkt"]

ziel = Path(sys.argv[1])  # mit --nur-osm: nur die Lage
ziel.mkdir(parents=True, exist_ok=True)
out: list[str] = []


def schreib() -> None:
    (ziel / "bericht.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def text(s: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return " ".join(html.unescape(s).split())


def lizenz_abschnitte(seite: str) -> list[str]:
    """Abschnitte und Zeilen, die eine Lizenz nennen (Seitenleiste, Tabelle, Links)."""
    funde = []
    for m in re.finditer(r'<section[^>]*class="[^"]*license[^"]*"[^>]*>.*?</section>', seite,
                         flags=re.S | re.I):
        funde.append("Seitenleiste: " + text(m.group(0)))
        for a in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', m.group(0), flags=re.S):
            funde.append(f"  Link: {a.group(1)} -> {text(a.group(2))}")
    for m in re.finditer(r"<tr[^>]*>\s*<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", seite,
                         flags=re.S | re.I):
        th, td = text(m.group(1)), text(m.group(2))
        if re.search(r"lizenz|licen", th, re.I):
            funde.append(f"Tabelle: {th} = {td}")
    for m in re.finditer(r'<a[^>]*href="([^"]*(?:dl-de|govdata\.de/dl|creativecommons|'
                         r'opendefinition|licen)[^"]*)"[^>]*>(.*?)</a>', seite,
                         flags=re.S | re.I):
        funde.append(f"Link: {m.group(1)} -> {text(m.group(2))}")
    for m in re.finditer(r"(Datenlizenz Deutschland[^<]{0,80}|Lizenz nicht angegeben|"
                         r"License not specified|Andere[^<]{0,40}Lizenz)", seite):
        funde.append("Text: " + " ".join(m.group(1).split()))
    return list(dict.fromkeys(funde))


try:
    out.append("== robots.txt")
    for url in [BASIS + p for p in SEITEN] + list(OVERPASS):
        out.append(f"  {url}: {'erlaubt' if robots.erlaubt(url) else 'GESPERRT'}")
    out.append("== Seiten")
    for i, pfad in enumerate([] if "--nur-osm" in sys.argv else SEITEN):
        url = BASIS + urllib.parse.quote(pfad, safe="/-")
        try:
            if not robots.erlaubt(url):
                out.append(f"-- {pfad}: gesperrt")
                continue
            inhalt, _, _ = robots.oeffne(url, zeit=120, grenze=5_000_000)
            (ziel / f"seite_{i}.html.gz").write_bytes(gzip.compress(inhalt))
            seite = inhalt.decode("utf-8", "replace")
            titel = re.search(r"<title>(.*?)</title>", seite, flags=re.S)
            out.append(f"-- {pfad}: {len(inhalt)} Bytes, Titel {text(titel.group(1)) if titel else '?'}")
            for f in lizenz_abschnitte(seite) or ["(keine Lizenzangabe gefunden)"]:
                out.append("   " + f[:400])
            for m in re.finditer(r"<tr[^>]*>\s*<th[^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>", seite,
                                 flags=re.S | re.I):
                out.append(f"   | {text(m.group(1))[:60]} = {text(m.group(2))[:200]}")
        except Exception as e:  # noqa: BLE001
            out.append(f"-- {pfad}: Fehler {e!r}"[:300])
        schreib()
    out.append("== OpenStreetMap (Nominatim, strukturierte Suche in Moers)")
    out.append(f"   {NOMINATIM}: {'erlaubt' if robots.erlaubt(NOMINATIM + '?street=x') else 'GESPERRT'}")
    funde = {}
    for strasse in STRASSEN:
        q = {"street": strasse, "city": "Moers", "country": "Deutschland", "format": "jsonv2",
             "limit": 5, "extratags": 1, "polygon_geojson": 1}
        url = f"{NOMINATIM}?{urllib.parse.urlencode(q)}"
        try:
            if not robots.erlaubt(url):
                out.append(f"   {strasse}: gesperrt")
                continue
            inhalt, _, _ = robots.oeffne(url, zeit=60, grenze=5_000_000)
            treffer = json.loads(inhalt)
            funde[strasse] = treffer
            for t in treffer:
                g = t.get("geojson") or {}
                koord = g.get("coordinates")
                if g.get("type") == "LineString":
                    punkte = " ".join(f"{x:.6f},{y:.6f}" for x, y in koord[:20])
                elif g.get("type") == "MultiLineString":
                    punkte = " | ".join(" ".join(f"{x:.6f},{y:.6f}" for x, y in linie[:12])
                                        for linie in koord[:4])
                else:
                    punkte = str(koord)[:200]
                out.append(f"   {strasse}: {t.get('osm_type')} {t.get('osm_id')} "
                           f"{t.get('category')}/{t.get('type')} Mitte {t.get('lon')},{t.get('lat')} | "
                           f"{t.get('display_name')} | {g.get('type')}: {punkte}")
        except Exception as e:  # noqa: BLE001
            out.append(f"   {strasse}: Fehler {e!r}"[:300])
    (ziel / "nominatim.json").write_text(json.dumps(funde, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    schreib()
    out.append("== OpenStreetMap (Overpass)")
    antwort = None
    for server in OVERPASS:
        try:
            if not robots.erlaubt(server):
                out.append(f"   {server}: gesperrt")
                continue
            daten = urllib.parse.urlencode({"data": ABFRAGE}).encode()
            inhalt, _, _ = robots.oeffne(server, daten=daten, zeit=90, grenze=20_000_000)
            antwort = json.loads(inhalt)
            out.append(f"   {server}: {len(antwort.get('elements', []))} Elemente")
            break
        except Exception as e:  # noqa: BLE001
            out.append(f"   {server}: Fehler {e!r}"[:300])
    if antwort:
        (ziel / "osm.json").write_text(json.dumps(antwort, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
        for el in antwort.get("elements", []):
            tags = el.get("tags", {})
            geom = el.get("geometry") or ([{"lat": el["lat"], "lon": el["lon"]}]
                                          if "lat" in el else [])
            punkte = " ".join(f"{p['lon']:.6f},{p['lat']:.6f}" for p in geom[:12])
            out.append(f"   {el['type']} {el['id']}: " + ", ".join(
                f"{k}={v}" for k, v in sorted(tags.items())
                if k in ("name", "highway", "man_made", "surveillance", "description",
                         "monitoring_station", "operator", "area", "place"))
                + f" | {len(geom)} Punkte: {punkte}")
except Exception:  # noqa: BLE001
    out.append(traceback.format_exc())
schreib()
