"""Werkzeug: Länder, zweite Runde.

1. Olpe: Open-Data-Portal (CKAN) – alle Verkehrsmessungen, Lizenz, Beschreibung, Beispieldateien.
2. GovData: Rest der großen Suchen ohne die Landesstraßen-Zählstellen (Bayern, Schleswig-Holstein).
3. Dateien: FragDenStaat-Anhänge (PDF -> Text), Falkensee, Hamburger Leistungsverzeichnis.
4. Seiten im Browser (Playwright): Mobilithek-Suche, Wuppertal, Bremen.
"""

import gzip
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/laender2")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
protokoll = {}


def hole(url, roh=False, timeout=120, limit=80_000_000):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as a:
        daten = a.read(limit)
    return daten if roh else json.loads(daten)


def schreibe(name, obj):
    (ZIEL / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def kurz(p):
    return {"name": p.get("name"), "titel": p.get("title"), "org": (p.get("organization") or {}).get("title"),
            "lizenz": p.get("license_id"), "lizenz_titel": p.get("license_title"),
            "lizenz_url": p.get("license_url"), "geaendert": p.get("metadata_modified"),
            "notiz": re.sub(r"\s+", " ", p.get("notes") or "")[:1500],
            "extras": {e.get("key"): e.get("value") for e in p.get("extras") or []},
            "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url"),
                            "beschreibung": (r.get("description") or "")[:300]} for r in p.get("resources", [])]}


# 1. Olpe ----------------------------------------------------------------------------------
OLPE = "https://opendata.olpe.de/api/3/action/"
olpe = ZIEL / "olpe"
olpe.mkdir(exist_ok=True)
pakete = {}
for q in ("Verkehrsmessung", "Verkehrsmessungen", "Verkehr", "Geschwindigkeit", "Zählung"):
    try:
        r = hole(OLPE + "package_search?" + urllib.parse.urlencode({"q": q, "rows": 500}))["result"]
        protokoll[f"olpe:{q}"] = r["count"]
        for p in r["results"]:
            pakete[p["name"]] = kurz(p)
    except Exception as e:  # noqa: BLE001
        protokoll[f"olpe:{q}"] = repr(e)[:200]
try:
    r = hole(OLPE + "package_list")
    protokoll["olpe:pakete"] = len(r["result"])
    (olpe / "paketliste.json").write_text(json.dumps(r["result"], ensure_ascii=False, indent=1))
except Exception as e:  # noqa: BLE001
    protokoll["olpe:pakete"] = repr(e)[:200]
schreibe("olpe/pakete.json", pakete)
proben = 0
for name, p in pakete.items():
    if not re.search(r"verkehr", (p["titel"] or "") + name, re.I):
        continue
    for res in p["ressourcen"]:
        url = res["url"] or ""
        if proben >= 14 or not re.search(r"\.(txt|csv|json)$", url, re.I):
            continue
        try:
            daten = hole(url, roh=True, limit=3_000_000)
            datei = olpe / re.sub(r"[^\w.-]+", "_", urllib.parse.unquote(url.rsplit("/", 1)[-1]))[-90:]
            datei.write_bytes(daten)
            protokoll[f"olpe:{datei.name}"] = len(daten)
            proben += 1
        except Exception as e:  # noqa: BLE001
            protokoll[f"olpe:{url[-60:]}"] = repr(e)[:200]

# 2. GovData-Rest -------------------------------------------------------------------------
GOV = "https://www.govdata.de/ckan/api/3/action/package_search?"
rest = {}
for q in ("Verkehrszählung", "Zählstelle", "Zählstellen", "DTV", "Verkehrsmessung", "Messstelle Verkehr"):
    try:
        r = hole(GOV + urllib.parse.urlencode({
            "q": q, "rows": 1000,
            "fq": "-organization:open-data-bayern AND -organization:land-schleswig-holstein"}), timeout=180)["result"]
        protokoll[f"govdata_rest:{q}"] = r["count"]
        for p in r["results"]:
            k = kurz(p)
            k["ressourcen"] = k["ressourcen"][:8]
            rest.setdefault(p["name"], k).setdefault("treffer", []).append(q)
    except Exception as e:  # noqa: BLE001
        protokoll[f"govdata_rest:{q}"] = repr(e)[:200]
(ZIEL / "govdata_rest.json.gz").write_bytes(gzip.compress(json.dumps(rest, ensure_ascii=False).encode()))

# 3. Dateien ---------------------------------------------------------------------------------
DATEIEN = json.loads(pathlib.Path(__file__).with_name("laender2_dateien.json").read_text(encoding="utf-8"))
dateien = ZIEL / "dateien"
dateien.mkdir(exist_ok=True)
for name, urls in DATEIEN.items():
    for url in urls if isinstance(urls, list) else [urls]:
        try:
            daten = hole(url, roh=True, timeout=300)
            if daten[:15].lower().startswith((b"<!doctype", b"<html")):
                raise ValueError("HTML statt Datei")
            (dateien / name).write_bytes(daten)
            if daten.startswith(b"%PDF"):
                subprocess.run(["pdftotext", "-layout", str(dateien / name), str(dateien / name) + ".txt"],
                               check=False)
            protokoll[f"datei:{name}"] = len(daten)
            break
        except Exception as e:  # noqa: BLE001
            protokoll[f"datei:{name}"] = repr(e)[:200]

# 4. Seiten im Browser ---------------------------------------------------------------------
SEITEN = {
    "mobilithek_verkehrszaehlung": "https://mobilithek.info/offers?searchString=Verkehrsz%C3%A4hlung",
    "mobilithek_zaehldaten": "https://mobilithek.info/offers?searchString=Z%C3%A4hldaten",
    "mobilithek_verkehrsstaerke": "https://mobilithek.info/offers?searchString=Verkehrsst%C3%A4rke",
    "wuppertal_zaehlungen": "https://www.wuppertal.de/vv/produkte/104/104.31_Verkehrszaehlungen.php",
    "wuppertal_belastungsdaten": "https://www.wuppertal.de/vv/produkte/104/104.31_Verkehrsbelastungsdaten.php",
    "wuppertal_belastung": "https://www.wuppertal.de/vv/produkte/104/104-51_Verkehrsbelastung.php",
    "bremen_mengenkarten": "https://bau.bremen.de/mobilitaet/verkehrsdaten/verkehrsmengenkarten-59016",
    "olpe_portal": "https://opendata.olpe.de/dataset/?q=Verkehrsmessung",
}
seiten = ZIEL / "seiten"
seiten.mkdir(exist_ok=True)
try:
    wms = hole("https://maps.wuppertal.de/verkehr?request=GetCapabilities&service=WMS&version=1.1.1", roh=True)
    (seiten / "wuppertal_wms.xml").write_bytes(wms)
    protokoll["wuppertal_wms"] = len(wms)
except Exception as e:  # noqa: BLE001
    protokoll["wuppertal_wms"] = repr(e)[:200]
try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        seite = browser.new_page(locale="de-DE", user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"))
        for name, url in SEITEN.items():
            try:
                seite.goto(url, wait_until="networkidle", timeout=60_000)
                seite.wait_for_timeout(2500)
                (seiten / f"{name}.txt").write_text(seite.inner_text("body"), encoding="utf-8")
                links = seite.eval_on_selector_all(
                    "a", "els => els.map(e => [e.innerText.trim().slice(0, 160), e.href])")
                (seiten / f"{name}_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=1),
                                                           encoding="utf-8")
                protokoll[f"seite:{name}"] = "ok"
            except Exception as e:  # noqa: BLE001
                protokoll[f"seite:{name}"] = repr(e)[:200]
        browser.close()
except Exception as e:  # noqa: BLE001
    protokoll["playwright"] = repr(e)[:300]

schreibe("protokoll.json", protokoll)
print(json.dumps(protokoll, ensure_ascii=False, indent=1)[:6000])
