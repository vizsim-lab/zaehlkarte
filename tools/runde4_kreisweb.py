"""Runde 4, Schritt 0: die Webseiten aller Landkreise (Runde 3 erreichte nur 121 von 242 Kreisen
außerhalb von Hessen und NRW – OSM nennt an den Kreisgrenzen kaum Webseiten, und die geratenen
Adressen gab es oft nicht).

Wege, in dieser Reihenfolge:
1. Wikipedia: „Liste der Landkreise in Deutschland“, je Kreis der Artikel, aus der Infobox
   Kreisschlüssel und Website.
2. OpenStreetMap: Landratsämter und Kreisverwaltungen (office=government) und Kreisgrenzen
   (admin_level 6) mit Webseite, je Land eine Abfrage an die Overpass-Server, die robots.txt
   erlaubt.
Ergebnis: ergebnis/runde4/kreise_web.json – je Kreisschlüssel die Kandidaten mit Herkunft.

Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py, auch für die Kennungen von Claude).
Nur Standardbibliothek. Aufruf: python3 tools/runde4_kreisweb.py ergebnis/runde4
"""

import json
import pathlib
import re
import sys
import time
import traceback
import unicodedata
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/runde4")
ZIEL.mkdir(parents=True, exist_ok=True)
ZIELE = json.loads((pathlib.Path(__file__).parent / "runde4_ziele.json").read_text())
KREISE = {k["ags"]: k for land in ZIELE.values() for k in land["kreise"]}
WIKI = "https://de.wikipedia.org"
LISTE = WIKI + "/wiki/Liste_der_Landkreise_in_Deutschland"
OVERPASS = ("https://maps.mail.ru/osm/tools/overpass/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter")
ISO = {"01": "DE-SH", "03": "DE-NI", "05": "DE-NW", "06": "DE-HE", "07": "DE-RP", "08": "DE-BW",
       "09": "DE-BY", "10": "DE-SL", "12": "DE-BB", "13": "DE-MV", "14": "DE-SN", "15": "DE-ST",
       "16": "DE-TH"}
protokoll: dict = {"start": time.strftime("%FT%TZ", time.gmtime())}
kandidaten: dict[str, list[dict]] = {}


def schreib():
    (ZIEL / "kreise_web.json").write_text(json.dumps(kandidaten, ensure_ascii=False, indent=1))
    (ZIEL / "kreise_web_protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1))


def hole(url, **kw):
    inhalt, end, typ = R.oeffne(url, zeit=kw.pop("zeit", 60), **kw)
    return inhalt.decode("utf-8", "replace"), end


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", "", s)


def kern(name):
    """„Mühldorf a.Inn“ -> {muehldorf, inn}; „Rhein-Kreis Neuss“ -> {rhein, neuss}."""
    n = re.sub(r"\b(landkreis|kreis|region|regionalverband|staedteregion|städteregion)\b", " ",
               name, flags=re.I)
    n = re.sub(r"kreis\b", "", n, flags=re.I)
    teile = re.split(r"[\s\-/,().]+", n)
    return {norm(t) for t in teile if len(norm(t)) >= 4}


def neu(ks, web, quelle, **mehr):
    if not web or not web.startswith("http"):
        return
    liste = kandidaten.setdefault(ks, [])
    schluessel = re.sub(r"^https?://(www\.)?", "", web.lower()).rstrip("/")
    if any(re.sub(r"^https?://(www\.)?", "", x["web"].lower()).rstrip("/") == schluessel for x in liste):
        return
    liste.append({"web": web, "quelle": quelle} | mehr)


# ---------------------------------------------------------------- 1. Wikipedia
def wikipedia():
    p = protokoll.setdefault("wikipedia", {})
    if not R.erlaubt(LISTE):
        p["fehler"] = "robots.txt"
        p["robots"] = R.TEXTE.get(WIKI, "")[:500]
        return
    text, _ = hole(LISTE)
    tabellen = re.findall(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', text, re.S)
    artikel = []
    for t in tabellen:
        for zeile in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
            m = re.search(r'<a href="(/wiki/[^"#?]+)"[^>]*title="([^"]+)"', zeile)
            if m and m.group(1) not in artikel and not re.search(r":|Liste_", m.group(1)):
                artikel.append(m.group(1))
    p["artikel"] = len(artikel)
    gefunden = 0
    for pfad in artikel:
        url = WIKI + pfad
        try:
            text, _ = hole(url)
        except Exception as e:  # noqa: BLE001
            p.setdefault("fehler_artikel", []).append(f"{pfad}: {e!r}"[:160])
            continue
        infobox = re.search(r'<table[^>]*class="[^"]*(?:infobox|float-right)[^"]*"[^>]*>(.*?)</table>',
                            text, re.S)
        teil = infobox.group(1) if infobox else text[:80_000]
        m = re.search(r"Kreisschlüssel.{0,400}?(\d{2})\s*(\d)\s*(\d{2})\b", teil, re.S)
        if not m:
            p.setdefault("ohne_schluessel", []).append(urllib.parse.unquote(pfad))
            continue
        ks = "".join(m.groups())
        w = re.search(r"Website.{0,600}?href=\"(https?://[^\"]+)\"", teil, re.S)
        if ks in KREISE and w:
            neu(ks, w.group(1), "wikipedia", artikel=urllib.parse.unquote(pfad))
            gefunden += 1
        elif ks in KREISE:
            p.setdefault("ohne_website", []).append(urllib.parse.unquote(pfad))
        else:
            p.setdefault("schluessel_unbekannt", []).append(f"{urllib.parse.unquote(pfad)} {ks}")
        if gefunden % 25 == 0:
            schreib()
    p["mit_website"] = gefunden


# ---------------------------------------------------------------- 2. OpenStreetMap
ABFRAGE = """[out:json][timeout:300];
area["ISO3166-2"="%s"][admin_level=4]->.land;
(
  nwr(area.land)["office"="government"]["name"~"Landratsamt|Kreisverwaltung|Kreishaus|Landkreis|Kreis ",i];
  nwr(area.land)["amenity"="townhall"]["name"~"Landratsamt|Kreisverwaltung|Kreishaus",i];
  rel(area.land)["boundary"="administrative"]["admin_level"="6"];
);
out center tags;"""


def overpass(abfrage):
    for versuch in range(2):
        for server in OVERPASS:
            try:
                inhalt, _, _ = R.oeffne(server, daten=urllib.parse.urlencode({"data": abfrage}).encode(),
                                        kopf={"Content-Type": "application/x-www-form-urlencoded"},
                                        zeit=360, grenze=80_000_000)
                r = json.loads(inhalt)
                if r.get("elements"):
                    return r, server
            except Exception as e:  # noqa: BLE001
                protokoll.setdefault("overpass_fehler", []).append(f"{server}: {e!r}"[:200])
        time.sleep(30)
    return None, None


def osm():
    p = protokoll.setdefault("osm", {})
    for land, iso in ISO.items():
        r, server = overpass(ABFRAGE % iso)
        if r is None:
            p[iso] = "keine Antwort"
            continue
        n = 0
        aemter = []
        for e in r["elements"]:
            t = e.get("tags", {})
            web = t.get("website") or t.get("contact:website") or t.get("url")
            if e["type"] == "relation" and t.get("admin_level") == "6":
                ks = (t.get("de:regionalschluessel") or t.get("de:amtlicher_gemeindeschluessel") or "")[:5]
                if ks in KREISE and web:
                    neu(ks, web, "osm_grenze")
                    n += 1
            elif web:
                aemter.append((t.get("name") or "", web))
        # Ämter über den Namen zuordnen: „Landratsamt Böblingen“ -> Kreis Böblingen
        for ks, k in KREISE.items():
            if not ks.startswith(land):
                continue
            kn = kern(k["name"])
            for name, web in aemter:
                if kn and kn <= set(re.split(r"[^a-z0-9]+", norm_teile(name))):
                    neu(ks, web, "osm_amt", name=name)
                    n += 1
        p[iso] = {"server": server, "elemente": len(r["elements"]), "zugeordnet": n}
        schreib()


def norm_teile(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")


if __name__ == "__main__":
    for schritt in (wikipedia, osm):
        try:
            schritt()
        except Exception:  # noqa: BLE001
            protokoll[schritt.__name__ + "_ausnahme"] = traceback.format_exc()[-1500:]
        schreib()
    protokoll["kreise_mit_kandidat"] = sum(1 for ks in KREISE if kandidaten.get(ks))
    protokoll["kreise_ohne"] = [KREISE[ks]["name"] for ks in KREISE if not kandidaten.get(ks)]
    protokoll["ende"] = time.strftime("%FT%TZ", time.gmtime())
    schreib()
    print(json.dumps({k: v for k, v in protokoll.items() if k != "wikipedia"}, ensure_ascii=False)[:3000])
