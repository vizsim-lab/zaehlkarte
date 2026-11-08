"""Moers: Messstellen der Radar-Verkehrszählungen geokodieren (Nominatim und Overpass, OSM).

Die Stadt nennt je Messung nur eine Adresse („Eupener Straße gegenüber 26“, „Bruchstraße Ecke
Max-Beckmann-Straße“, „Orsoyer Allee an VZ 274“). Daraus:
- Straße und Hausnummer -> Nominatim (strukturierte Suche in Moers), Genauigkeit `hausnummer`;
- „Ecke“/„Kv“ (Kreisverkehr) -> gemeinsamer Knoten beider Straßen in OSM (Overpass),
  Genauigkeit `kreuzung`;
- nur eine Straße -> Mitte der Straße (Nominatim), Genauigkeit `strasse` – ungefähr;
- nichts gefunden (Tippfehler im Namen) -> Photon (unscharfe Suche).

Läuft dort, wo Nominatim und Overpass erreichbar sind (GitHub Actions):
    python3 geokodiere_moers.py ROHDATEN ZIEL
ROHDATEN  pipeline/data/raw/moers (je Datensatz ein Ordner mit paket.json)
ZIEL      pipeline/geokodierung/moers.csv – nicht von Hand ändern.
Nur Standardbibliothek; höchstens eine Anfrage je Sekunde (Nutzungsregeln von Nominatim).
"""

from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-geokodierung/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
NOMINATIM = "https://nominatim.openstreetmap.org/search"
OVERPASS = "https://overpass-api.de/api/interpreter"
PHOTON = "https://photon.komoot.io/api/"
_letzte = [0.0]


def hole(url: str, daten: bytes | None = None) -> object:
    warten = 1.1 - (time.time() - _letzte[0])
    if warten > 0:
        time.sleep(warten)
    _letzte[0] = time.time()
    anfrage = urllib.request.Request(url, data=daten, headers=UA)
    with urllib.request.urlopen(anfrage, timeout=90) as a:
        return json.loads(a.read())


def adresse(name: str) -> tuple[list[str], str | None]:
    """'Verkehrszählung Eupener Straße gegenüber 26' -> (['Eupener Straße'], '26');
    'Bruchstraße Ecke Max-Beckmann-Straße' -> (['Bruchstraße', 'Max-Beckmann-Straße'], None)."""
    t = re.sub(r"^\s*Verkehr\w*\s+", "", name).replace("_", " ")
    t = re.sub(r"\b(zwischen|Zufahrt)\b.*$", "", t)  # „zwischen A- und B-Straße“: nur die erste
    t = re.sub(r"\ban VZ \d+\b", " ", t)
    t = re.sub(r"\bHöhe\s+(?:Nr\.|Hausnr\.)?\s*(?=\d)", " ", t)  # „Höhe Nr. 13f“
    # „Höhe Pusenweg“ ist eine Kreuzung, „Höhe Grundschule“ nur ein Hinweis
    t = re.sub(r"\bHöhe\s+(?=\S*(straße|weg|allee|platz|ring|damm|gasse)\b)", " | ", t)
    t = re.sub(r"\bHöhe\b.*$", "", t)
    t = re.sub(r"\bLaterne an Grundstück\b", " ", t)
    t = re.sub(r"\b(geg\w*über|ggü\.?|Hausnr\.?|nach|vor|\d+\.\s*Laterne)(?=\s|$)", " ", t)
    t = re.sub(r"(\d+\s*[a-zA-Z]?)\s*-\s*\d+\s*[a-zA-Z]?\b", r"\1", t)  # 63-75, 6b - 8
    t = re.sub(r"\b(Ecke|Kv|KV)\b", " | ", t)
    teile = [" ".join(s.split()) for s in t.split("|") if s.strip()]
    nummer = None
    strassen = []
    for teil in teile:
        m = re.match(r"^(.*?\D)\s*(\d+\s*[a-zA-Z]?)$", teil)
        if m and len(teile) == 1:
            strassen.append(m.group(1).strip())
            nummer = m.group(2).replace(" ", "")
        else:
            strassen.append(re.sub(r"\s*\d+\s*[a-zA-Z]?$", "", teil).strip())
    return [s for s in strassen if s], nummer


def nummer_aus_dateiname(datei: str) -> str | None:
    """'ackerstrasse40t3005112014.txt' -> '40' (Hausnummer vor der Angabe t30/t50)."""
    m = re.match(r"^(\D+?)[-_]?(\d{1,3}[a-z]?)[-_]?t\d{2}", datei.lower())
    if not m or m.group(1).rstrip("-_").endswith("vz"):  # „an-vz-274“: Verkehrszeichen
        return None
    return m.group(2)


def aus_dateiname(datei: str) -> str:
    """'westerbruchstrasse-zw.-brieger-und-franz-haniel-strasset5030012017.txt' ->
    'Westerbruchstraße' (nur als Ersatz, wenn der Name der Messung keine Straße nennt)."""
    slug = re.split(r"[-_]|\d", datei.lower(), maxsplit=1)[0]
    return slug.replace("strasse", "straße").capitalize()


def varianten(strasse: str) -> list[str]:
    """'Zwickauerstraße' -> ['Zwickauerstraße', 'Zwickauer Straße']."""
    out = [strasse]
    m = re.match(r"^(\w+?er)(straße|weg|allee)$", strasse, re.IGNORECASE)
    if m:
        out.append(f"{m.group(1)} {m.group(2).capitalize()}")
    return out


def nominatim(strasse: str, nummer: str | None) -> dict | None:
    for s in varianten(strasse):
        q = {"street": f"{nummer} {s}" if nummer else s, "city": "Moers", "country": "Deutschland",
             "format": "jsonv2", "addressdetails": 1, "limit": 1}
        treffer = hole(f"{NOMINATIM}?{urllib.parse.urlencode(q)}")
        if treffer:
            return treffer[0]
    return None


def photon(text: str) -> dict | None:
    """Ersatz bei Tippfehlern im Namen („Humboldstraße“): Photon sucht unscharf."""
    q = {"q": f"{text}, Moers", "limit": 1, "lang": "de", "lat": 51.45, "lon": 6.63}
    treffer = hole(f"{PHOTON}?{urllib.parse.urlencode(q)}").get("features", [])
    if not treffer:
        return None
    eig = treffer[0]["properties"]
    if eig.get("city") != "Moers" and "Moers" not in str(eig.get("county", "")) + str(
            eig.get("district", "")) + str(eig.get("locality", "")):
        return None
    lon, lat = treffer[0]["geometry"]["coordinates"]
    name = ", ".join(str(eig[k]) for k in ("name", "street", "housenumber", "city") if eig.get(k))
    return {"lon": lon, "lat": lat, "hausnummer": bool(eig.get("housenumber")), "treffer": name}


def kreuzung(a: str, b: str) -> tuple[float, float] | None:
    abfrage = f"""[out:json][timeout:60];
area["name"="Moers"]["boundary"="administrative"]->.m;
way(area.m)["highway"]["name"="{a}"]->.a;
way(area.m)["highway"]["name"="{b}"]->.b;
node(w.a)(w.b);
out;"""
    daten = hole(OVERPASS, urllib.parse.urlencode({"data": abfrage}).encode())
    knoten = daten.get("elements", [])
    if not knoten:
        return None
    lon = sum(k["lon"] for k in knoten) / len(knoten)
    lat = sum(k["lat"] for k in knoten) / len(knoten)
    return lon, lat


def verorte(name: str) -> dict:
    strassen, nummer = adresse(name)
    if not strassen:
        return {"genauigkeit": ""}
    if len(strassen) >= 2:
        for a, b in ((strassen[0], strassen[1]), *[(x, y) for x in varianten(strassen[0])
                                                    for y in varianten(strassen[1])]):
            p = kreuzung(a, b)
            if p:
                return {"lon": p[0], "lat": p[1], "genauigkeit": "kreuzung",
                        "treffer": f"{a} / {b}"}
    if nummer:
        t = nominatim(strassen[0], nummer)
        if t and t.get("address", {}).get("house_number"):
            return {"lon": float(t["lon"]), "lat": float(t["lat"]), "genauigkeit": "hausnummer",
                    "treffer": t.get("display_name", "")}
    t = nominatim(strassen[0], None)
    if t:
        return {"lon": float(t["lon"]), "lat": float(t["lat"]), "genauigkeit": "strasse",
                "treffer": t.get("display_name", "")}
    p = photon(f"{strassen[0]} {nummer or ''}".strip())
    if p:
        return {"lon": p["lon"], "lat": p["lat"], "treffer": p["treffer"],
                "genauigkeit": "hausnummer" if p["hausnummer"] else "strasse"}
    return {"genauigkeit": ""}


def main(roh: str, ziel: str) -> None:
    zeilen = []
    for paket in sorted(Path(roh).glob("*/paket.json")):
        p = json.loads(paket.read_text(encoding="utf-8"))
        for r in p.get("resources", []):
            datei = urllib.parse.unquote((r.get("url") or "").rsplit("/", 1)[-1])
            if not datei:
                continue
            name = r.get("name") or datei
            abfrage = name
            if not adresse(abfrage)[0]:
                abfrage = aus_dateiname(datei)
            if adresse(abfrage)[1] is None and (nr := nummer_aus_dateiname(datei)):
                abfrage = f"{' '.join(adresse(abfrage)[0][:1])} {nr}"
            try:
                ort = verorte(abfrage)
            except Exception as e:  # noqa: BLE001 – Werkzeug: Fehler je Zeile festhalten
                ort = {"genauigkeit": "", "treffer": f"Fehler: {e!r}"[:200]}
            strassen, nummer = adresse(abfrage)
            zeilen.append({
                "paket": paket.parent.name, "datei": datei, "name": name,
                "abfrage": " / ".join(strassen) + (f" {nummer}" if nummer else ""),
                "lon": f"{ort['lon']:.6f}" if "lon" in ort else "",
                "lat": f"{ort['lat']:.6f}" if "lat" in ort else "",
                "genauigkeit": ort["genauigkeit"], "treffer": ort.get("treffer", ""),
            })
            print(zeilen[-1]["genauigkeit"] or "-", name, flush=True)
    with open(ziel, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(zeilen[0]))
        w.writeheader()
        w.writerows(sorted(zeilen, key=lambda z: (z["paket"], z["datei"])))
    print(sum(1 for z in zeilen if z["lon"]), "von", len(zeilen), "verortet ->", ziel)


if __name__ == "__main__":
    main(*sys.argv[1:3])
