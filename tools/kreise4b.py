"""Runde 4b, Schritt 0: die Webseiten der 294 Landkreise aus der deutschen Wikipedia.

In Runde 4 fand tools/runde4_kreisweb.py in der „Liste der Landkreise in Deutschland“ keinen
einzigen Artikel (eine Tabelle, null Links im erwarteten Format). Hier: die Listenseite gepackt
ablegen (zum Nachsehen), Links in beiden Formen lesen (`/wiki/…` und `./…`), und für jeden Kreis
ohne Treffer den Artikel über seinen Namen holen („Landkreis …“, „Kreis …“, Abkürzungen des
Gemeindeverzeichnisses ausgeschrieben). Aus der Infobox Kreisschlüssel und Website; ein Treffer
zählt nur, wenn der Kreisschlüssel zum Kreis passt.

Ergebnis: ergebnis/runde4b/kreise_web.json (je Kreisschlüssel die Kandidaten mit Herkunft, Format
wie tools/runde4_kreisweb.py) und kreise_web_protokoll.json. Nur über tools/robots.py.

    python3 tools/kreise4b.py ergebnis/runde4b
"""

import gzip
import json
import pathlib
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/runde4b")
ZIEL.mkdir(parents=True, exist_ok=True)
ZIELE = json.loads((pathlib.Path(__file__).parent / "runde4_ziele.json").read_text())
KREISE = {k["ags"]: k for land in ZIELE.values() for k in land["kreise"]}
WIKI = "https://de.wikipedia.org"
LISTE = WIKI + "/wiki/Liste_der_Landkreise_in_Deutschland"
LINK = re.compile(r'<a\b[^>]*?\bhref="(?:/wiki/|\./|https://de\.wikipedia\.org/wiki/)([^"#?]+)"'
                  r'[^>]*>(.*?)</a>', re.S)
protokoll: dict = {"start": time.strftime("%FT%TZ", time.gmtime())}
kandidaten: dict[str, list[dict]] = {}


def schreib():
    (ZIEL / "kreise_web.json").write_text(json.dumps(kandidaten, ensure_ascii=False, indent=1))
    (ZIEL / "kreise_web_protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False,
                                                               indent=1))


def hole(url):
    inhalt, end, _ = R.oeffne(url, zeit=60, grenze=8_000_000)
    return inhalt.decode("utf-8", "replace"), end


def infobox(text):
    """(Kreisschlüssel, Website) aus der Infobox eines Kreis-Artikels."""
    box = re.search(r'<table[^>]*class="[^"]*(?:infobox|float-right)[^"]*"[^>]*>(.*?)</table>',
                    text, re.S)
    teil = box.group(1) if box else text[:120_000]
    m = re.search(r"Kreisschlüssel.{0,400}?(\d{2})\s*(\d)\s*(\d{2})\b", teil, re.S)
    w = re.search(r'Website.{0,600}?href="(https?://[^"]+)"', teil, re.S)
    return ("".join(m.groups()) if m else None), (w.group(1) if w else None)


def neu(ks, web, quelle, **mehr):
    if not web or not web.startswith("http"):
        return
    liste = kandidaten.setdefault(ks, [])
    s = re.sub(r"^https?://(www\.)?", "", web.lower()).rstrip("/")
    if any(re.sub(r"^https?://(www\.)?", "", x["web"].lower()).rstrip("/") == s for x in liste):
        return
    liste.append({"web": web, "quelle": quelle} | mehr)


def titel(k):
    """Artikeltitel für einen Kreis des Gemeindeverzeichnisses, in dieser Reihenfolge."""
    n = k["name"]
    lang = n
    for a, b in (("i.d.OPf.", "in der Oberpfalz"), ("a.d.", "an der "), ("i.d.", "in der "),
                 ("a.", "am "), ("i.", "im ")):
        lang = lang.replace(a, b)
    lang = re.sub(r"\s+", " ", lang).strip()
    if re.search(r"kreis|region", n, re.I):
        return list(dict.fromkeys([n, lang]))
    vor = {"44": "Landkreis ", "43": "Kreis ", "45": "Regionalverband "}.get(k.get("tk"), "Landkreis ")
    return list(dict.fromkeys([vor + lang, vor + n, "Landkreis " + lang, "Kreis " + lang]))


def artikel_pruefen(pfad, quelle, erwartet=None):
    url = WIKI + "/wiki/" + pfad
    try:
        text, end = hole(url)
    except Exception as e:  # noqa: BLE001
        protokoll.setdefault("fehler_artikel", []).append(f"{pfad}: {e!r}"[:160])
        return None
    ks, web = infobox(text)
    if erwartet and ks != erwartet:
        protokoll.setdefault("schluessel_passt_nicht", []).append(f"{pfad}: {ks} statt {erwartet}")
        return None
    if ks in KREISE and web:
        neu(ks, web, quelle, artikel=urllib.parse.unquote(pfad))
        return ks
    if ks in KREISE:
        protokoll.setdefault("ohne_website", []).append(urllib.parse.unquote(pfad))
    return None


def main():
    p = protokoll.setdefault("liste", {})
    if not R.erlaubt(LISTE):
        p["fehler"] = "robots.txt"
    else:
        text, end = hole(LISTE)
        (ZIEL / "wiki_liste.html.gz").write_bytes(gzip.compress(text.encode()))
        p |= {"bytes": len(text), "end": end, "a_tags": text.count("<a "),
              "tabellen": len(re.findall(r'<table[^>]*wikitable', text)),
              "hrefs_wiki": text.count('href="/wiki/'), "hrefs_punkt": text.count('href="./'),
              "probe": [m.group(1) for m in LINK.finditer(text)][:40]}
        artikel = []
        for pfad, inhalt in LINK.findall(text):
            ti = urllib.parse.unquote(pfad).replace("_", " ")
            if ":" in pfad or "Liste_" in pfad or not re.search(r"kreis|region", ti, re.I):
                continue
            if pfad not in artikel:
                artikel.append(pfad)
        p["artikel"] = len(artikel)
        print(f"Liste: {len(text)} Zeichen, {len(artikel)} Kreis-Artikel", flush=True)
        for i, pfad in enumerate(artikel):
            artikel_pruefen(pfad, "wikipedia")
            if i % 25 == 0:
                schreib()
                print(f"  {i}/{len(artikel)}: {len(kandidaten)} Kreise mit Website", flush=True)
    schreib()
    # Kreise ohne Treffer über den Namen
    offen = [ks for ks in KREISE if not kandidaten.get(ks)]
    protokoll["nach_namen"] = {"offen": len(offen)}
    for ks in offen:
        for t in titel(KREISE[ks]):
            pfad = urllib.parse.quote(t.replace(" ", "_"), safe="()_-,.")
            if artikel_pruefen(pfad, "wikipedia_name", erwartet=ks):
                break
        schreib()
    protokoll["kreise_mit_kandidat"] = sum(1 for ks in KREISE if kandidaten.get(ks))
    protokoll["kreise_ohne"] = [KREISE[ks]["name"] for ks in KREISE if not kandidaten.get(ks)]
    protokoll["ende"] = time.strftime("%FT%TZ", time.gmtime())
    schreib()
    print(json.dumps({k: v for k, v in protokoll.items() if k not in ("liste",)},
                     ensure_ascii=False)[:3000], flush=True)


if __name__ == "__main__":
    main()
