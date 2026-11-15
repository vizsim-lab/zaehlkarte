"""Runde 4 (15.11.2026), Teil 1: alle Landkreise mit ihrer richtigen Webseite und die Gemeinden
und Verbände ab 10.000 Einwohnern – mit neuen Begriffen neben den alten.

Anlass: Lückenanalyse vom 15.11. (Projekt-Doc claude/recherche-luecken-2026-11.md). Runde 3
erreichte nur 121 von 242 Landkreisen außerhalb von Hessen und NRW; Begriffe der Verkehrsplanung
allein verfehlen andere Absender:
- Fuß in der Innenstadt (Stadtmarketing, Wirtschaftsförderung): Frequenzmessung, Passanten,
  Besucherzahlen, Personenzählung, Laserscanner, hystreet;
- Verkehrsversuche: Kiezblock, Superblock, Modalfilter, Schulstraße, Wirkungsanalyse,
  Vorher-Nachher;
- Rad-Zählsäulen: Zählsäule, Fahrradbarometer, Eco-Counter, Radzählstation;
- Sensoren und Datenplattformen: Verkehrsdetektion, Verkehrssensor, LoRaWAN, SensorThings,
  Datenplattform, Telraam, Open Data.

Ziele: tools/runde4_ziele.json (Gemeindeverzeichnis von Destatis, Stand 30.09.2026; Webseiten aus
den früheren Läufen) und ergebnis/runde4/kreise_web.json (tools/runde4_kreisweb.py). Je Webseite
wie tools/land.py: Startseite, Sitemap, Suche der Seite – die Suche mit neuen Begriffen, bei Kreisen
und bisher nicht erreichten Seiten auch mit den alten. Eine Kreis-Webseite gilt erst, wenn Titel
oder Adresse den Namen des Kreises tragen.

Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py, auch für die Kennungen von Claude).
Aufruf: python3 tools/runde4.py ergebnis/runde4/<LAND> <LAND>
"""

import concurrent.futures as cf
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse

ZIEL = pathlib.Path(sys.argv[1])
LAND_CODE = sys.argv[2]
# tools/land.py liest beim Import sys.argv (Ziel, Teile, Land) – Hessen kennt es nicht
sys.argv = [sys.argv[0], str(ZIEL), "keine", LAND_CODE if LAND_CODE != "HE" else "NW"]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import land as L  # noqa: E402

ZIELE = json.loads((pathlib.Path(__file__).parent / "runde4_ziele.json").read_text())[LAND_CODE]
KREISWEB = ZIEL.parent / "kreise_web.json"
ZIEL.mkdir(parents=True, exist_ok=True)

_Z = r"z(?:ae|ä|a)hl"
NEU = (rf"frequenzmess|frequenz{_Z}|passant|besucher{_Z}|besucherfrequenz|personen{_Z}"
       rf"|fu(?:ss|ß)verkehrs{_Z}|fu(?:ss|ß)g(?:ae|ä|a)ngerfrequenz|laserscan|hystreet|paxcounter"
       r"|verkehrsversuch|kiezblock|superblock|modalfilter|schulstra(?:ss|ß)e|wirkungsanalys"
       r"|vorher-?nachher|begleituntersuch"
       rf"|{_Z}s(?:ae|ä|a)ule|fahrradbarometer|radbarometer|eco-?counter|rad{_Z}station"
       r"|verkehrsdetektion|verkehrssensor|verkehrsdashboard|mobilit(?:ae|ä|a)tsdaten|datenplattform"
       r"|urban-?data|lorawan|sensorthings|frost-?server|telraam|open-?data|opendata|offene-?daten")
MUSTER_NEU = re.compile(NEU, re.I)
L.MUSTER = re.compile(L.MUSTER.pattern + "|" + NEU, re.I)  # pruefe_seite nutzt L.MUSTER

SUCHE_ALT = ("Verkehrszählung", "Zählstelle")
SUCHE_NEU = ("Frequenzmessung", "Radzählstelle", "Verkehrsversuch")
SUCHE_KREIS = ("Verkehrszählung", "Zählstelle", "Radzählstelle", "Verkehrsdaten")
FRIST = 150

# Verbände über den Kreisen und Gemeinden (Regionalverbände, Netzwerke, Mobilitätsgesellschaften)
EXTRA = {
    "NW": [("RVR", "Regionalverband Ruhr", "https://www.rvr.ruhr/"),
           ("ZNM", "Zukunftsnetz Mobilität NRW", "https://www.zukunftsnetz-mobilitaet.nrw.de/"),
           ("AGFS", "AGFS NRW", "https://www.agfs-nrw.de/"),
           ("RRH", "Radregion Rheinland e.V.", "https://www.radregionrheinland.de/"),
           ("RKB", "Region Köln/Bonn e.V.", "https://www.region-koeln-bonn.de/")],
    "NI": [("RGB", "Regionalverband Großraum Braunschweig", "https://www.regionalverband-braunschweig.de/")],
    "BW": [("VRS", "Verband Region Stuttgart", "https://www.region-stuttgart.org/"),
           ("MRN", "Metropolregion Rhein-Neckar", "https://www.m-r-n.com/"),
           ("TRK", "TechnologieRegion Karlsruhe", "https://technologieregion-karlsruhe.de/")],
    "HE": [("RVFRM", "Regionalverband FrankfurtRheinMain", "https://www.region-frankfurt.de/"),
           ("IVM", "ivm GmbH (Verkehrs- und Mobilitätsmanagement Region Frankfurt RheinMain)",
            "https://www.ivm-rheinmain.de/"),
           ("ZRK", "Zweckverband Raum Kassel", "https://www.zrk-kassel.de/"),
           ("AGNH", "Arbeitsgemeinschaft Nahmobilität Hessen", "https://www.nahmobil-hessen.de/")],
    "BY": [("PVM", "Planungsverband Äußerer Wirtschaftsraum München", "https://www.pv-muenchen.de/"),
           ("EMN", "Metropolregion Nürnberg", "https://www.metropolregion-nuernberg.de/")],
    "SL": [],
    "HH": [("MRH", "Metropolregion Hamburg", "https://metropolregion.hamburg.de/")],
}

protokoll: dict = {"start": time.strftime("%FT%TZ", time.gmtime())}


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return re.sub(r"[^a-z0-9]+", " ", s)


def kern(name):
    n = re.sub(r"\b(landkreis|kreis|region|regionalverband|staedteregion|städteregion)\b", " ",
               name, flags=re.I)
    n = re.sub(r"kreis\b", "", n, flags=re.I)
    return {t for t in norm(n).split() if len(t) >= 4}


def passt_kreis(k, end, titel):
    """Gehört die Seite zum Kreis? Ein Namensteil (ab 4 Zeichen) in Titel oder Adresse."""
    teile = kern(k["name"])
    host = norm(urllib.parse.urlsplit(end).netloc).replace(" ", "")
    text = norm(titel)
    return any(t in host or t in text.split() or t in text.replace(" ", "") for t in teile)


def geraten_kreis(k):
    name = re.sub(r"\(.*?\)", " ", k["name"].split(",")[0])
    voll = re.sub(r"[^a-z0-9]+", "-", norm(name)).strip("-")
    rumpf = re.sub(r"[^a-z0-9]+", "-", norm(re.sub(r"\b(Landkreis|Kreis|Region)\s+", "", name))).strip("-")
    rumpf = re.sub(r"-?kreis$", "", rumpf) if rumpf.endswith("kreis") and rumpf != "kreis" else rumpf
    kandidaten = [f"https://www.landkreis-{rumpf}.de/", f"https://www.kreis-{rumpf}.de/",
                  f"https://www.lk-{rumpf}.de/", f"https://www.lra-{rumpf}.de/",
                  f"https://www.{rumpf}.de/", f"https://www.landkreis{rumpf.replace('-', '')}.de/",
                  f"https://www.{voll}.de/", f"https://www.{voll.replace('-', '')}.de/"]
    return list(dict.fromkeys(kandidaten))


def ziele():
    kreisweb = json.loads(KREISWEB.read_text()) if KREISWEB.exists() else {}
    aus = []
    for k in ZIELE["kreise"]:
        web = [x["web"] for x in kreisweb.get(k["ags"], []) if x["quelle"] == "wikipedia"]
        web += k["web"]
        web += [x["web"] for x in kreisweb.get(k["ags"], []) if x["quelle"] != "wikipedia"]
        web += geraten_kreis(k)
        herkunft = {w: "geraten" for w in geraten_kreis(k)} | {w: "vorher_oder_liste" for w in k["web"]}
        herkunft |= {x["web"]: x["quelle"] for x in kreisweb.get(k["ags"], [])}
        aus.append(k | {"web": list(dict.fromkeys(web)), "herkunft": herkunft})
    for g in ZIELE["gemeinden"]:
        aus.append(g | {"web": g["web"] or L.geraten(g | {"art": "gemeinde"})})
    for v in ZIELE["verbaende"]:
        if v["web"]:
            aus.append(v)
    for a, n, w in EXTRA.get(LAND_CODE, []):
        aus.append({"ags": a, "name": n, "art": "verband", "web": [w], "vorher": "neu"})
    # dieselbe Seite nur einmal (Mitgliedsgemeinden verweisen oft auf ihren Verband)
    gesehen, eindeutig = {}, []
    for z in aus:
        schluessel = re.sub(r"^https?://(www\.)?", "", (z["web"] or [""])[0].lower()).rstrip("/")
        if schluessel and schluessel in gesehen and z["art"] != "kreis":
            gesehen[schluessel].setdefault("auch", []).append(z["ags"])
            continue
        gesehen[schluessel] = z
        eindeutig.append(z)
    return eindeutig


def pruefe(z):
    frist = time.time() + FRIST
    erg = {"ags": z["ags"], "name": z["name"], "art": z["art"], "einw": z.get("einw"),
           "vorher": z.get("vorher"), "auch": z.get("auch", []), "web": None, "titel": "",
           "generator": "", "sitemap_urls": 0, "sitemaps": 0, "treffer": [], "suche": [],
           "start_treffer": [], "versuche": []}
    inhalt = None
    for kandidat in z["web"]:
        if time.time() > frist:
            break
        try:
            inhalt, end, _ = L.seite(kandidat)
        except L.Gesperrt:
            erg["versuche"].append([kandidat, "robots.txt oder nicht erreichbar"])
            continue
        except Exception as e:  # noqa: BLE001
            erg["versuche"].append([kandidat, repr(e)[:120]])
            continue
        p = L.Links()
        try:
            p.feed(inhalt.decode("utf-8", "replace"))
        except Exception:  # noqa: BLE001
            pass
        titel = " ".join(p.titel.split())[:150]
        if z["art"] == "kreis" and not passt_kreis(z, end, titel):
            erg["versuche"].append([kandidat, f"passt nicht: {end} „{titel}“"])
            inhalt = None
            continue
        erg["web"], erg["titel"], erg["generator"] = end, titel, p.generator[:80]
        erg["herkunft"] = (z.get("herkunft") or {}).get(kandidat, "liste_oder_geraten")
        break
    if not erg["web"]:
        return erg
    for href, text in p.links:
        if L.MUSTER.search(href + " " + text):
            erg["start_treffer"].append([urllib.parse.urljoin(erg["web"], href), text])
    erg["start_treffer"] = erg["start_treffer"][:80]
    urls, n = L.sitemap_urls(erg["web"], min(frist, time.time() + 70))
    erg["sitemap_urls"], erg["sitemaps"] = len(urls), n
    erg["treffer"] = sorted({u for u in urls if L.MUSTER.search(urllib.parse.unquote(u))})[:150]
    if z["art"] == "kreis":
        begriffe = SUCHE_KREIS
    elif z.get("vorher") == "erreicht":
        begriffe = SUCHE_NEU
    else:
        begriffe = SUCHE_ALT + SUCHE_NEU
    for f in p.formen:
        if f["method"] != "get" or not f["felder"]:
            continue
        feld = next((x for x in f["felder"]
                     if re.search(r"such|search|query|^q$|keyword|term|text|swr|sword", x, re.I)), None)
        if not feld:
            continue
        ziel = urllib.parse.urljoin(erg["web"], f["action"] or erg["web"])
        for begriff in begriffe:
            if time.time() > frist:
                erg["suche"].append({"begriff": begriff, "fehler": "Zeit"})
                break
            q = dict(f["versteckt"]) | {feld: begriff}
            url = ziel + ("&" if "?" in ziel else "?") + urllib.parse.urlencode(q)
            try:
                inhalt, end, _ = L.seite(url, zeit=25)
                s = L.Links()
                s.feed(inhalt.decode("utf-8", "replace"))
                funde = [[urllib.parse.urljoin(end, h), t] for h, t in s.links
                         if L.MUSTER.search(h + " " + t)]
                erg["suche"].append({"begriff": begriff, "url": url, "laenge": len(inhalt),
                                     "treffer": len(funde)})
                erg.setdefault("such_treffer", [])
                for x in funde:
                    if x not in erg["such_treffer"]:
                        erg["such_treffer"].append(x)
            except L.Gesperrt:
                erg["suche"].append({"begriff": begriff, "url": url, "fehler": "robots.txt"})
                break
            except Exception as e:  # noqa: BLE001
                erg["suche"].append({"begriff": begriff, "url": url, "fehler": repr(e)[:120]})
        break
    if "such_treffer" in erg:
        erg["such_treffer"] = erg["such_treffer"][:100]
    alle = [u for u in erg["treffer"]] + [u for u, _ in erg.get("such_treffer", [])] + \
        [u for u, _ in erg["start_treffer"]]
    erg["neu_treffer"] = sum(1 for u in alle if MUSTER_NEU.search(urllib.parse.unquote(u)))
    return erg


def main():
    liste = ziele()
    L.schreibe("ziele.json", liste)
    protokoll["ziele"] = {"alle": len(liste), "kreise": sum(1 for z in liste if z["art"] == "kreis"),
                          "gemeinden": sum(1 for z in liste if z["art"] == "gemeinde"),
                          "verbaende": sum(1 for z in liste if z["art"] == "verband")}
    aus = []
    with cf.ThreadPoolExecutor(max_workers=24) as pool:
        for erg in pool.map(pruefe, liste):
            aus.append(erg)
            if len(aus) % 50 == 0:
                L.schreibe("webseiten.json", aus)
                print("webseiten", len(aus), round(time.time() - L.START), flush=True)
    L.schreibe("webseiten.json", aus)
    kreise = [e for e in aus if e["art"] == "kreis"]
    protokoll["webseiten"] = {
        "seiten": len(aus), "erreicht": sum(1 for e in aus if e["web"]),
        "kreise": len(kreise), "kreise_erreicht": sum(1 for e in kreise if e["web"]),
        "kreise_nicht_erreicht": [e["name"] for e in kreise if not e["web"]],
        "mit_sitemap": sum(1 for e in aus if e["sitemap_urls"]),
        "mit_suche": sum(1 for e in aus if any("fehler" not in s for s in e["suche"])),
        "mit_treffern": sum(1 for e in aus if e["treffer"] or e.get("such_treffer") or e["start_treffer"]),
        "mit_neuen_treffern": sum(1 for e in aus if e.get("neu_treffer")),
    }
    protokoll["ende"] = time.strftime("%FT%TZ", time.gmtime())
    L.schreibe("protokoll.json", protokoll)
    print(json.dumps(protokoll, ensure_ascii=False)[:2500], flush=True)


if __name__ == "__main__":
    main()
