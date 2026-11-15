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
ABFRAGE = """[out:json][timeout:90];
area["name"="Moers"]["admin_level"="8"]->.a;
(
  way(area.a)["name"="Steinstraße"];
  way(area.a)["name"="Neuer Wall"];
  way(area.a)["name"="Neumarkt"];
  node(area.a)["name"="Neumarkt"];
  node(area.a)["man_made"~"surveillance|monitoring_station"];
  node(area.a)["description"~"[Ll]aser|[Zz]ähl|hystreet"];
);
out tags geom;"""

ziel = Path(sys.argv[1])
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
    for i, pfad in enumerate(SEITEN):
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
    out.append("== OpenStreetMap (Overpass)")
    antwort = None
    for server in OVERPASS:
        try:
            if not robots.erlaubt(server):
                out.append(f"   {server}: gesperrt")
                continue
            daten = urllib.parse.urlencode({"data": ABFRAGE}).encode()
            inhalt, _, _ = robots.oeffne(server, daten=daten, zeit=180, grenze=20_000_000)
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
