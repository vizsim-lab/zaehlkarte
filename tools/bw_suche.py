"""Werkzeug: Kurzzeitzählungen in Baden-Württemberg suchen – MobiData BW und GovData (CKAN),
FragDenStaat (API), Freiburg (Stadtseiten, Statistik-Jahrbücher als Text)."""

import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/bw")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
protokoll = {}


def hole(url, roh=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as a:
        daten = a.read()
    return daten if roh else json.loads(daten)


def kurz(paket):
    return {
        "name": paket.get("name"), "titel": paket.get("title"),
        "org": (paket.get("organization") or {}).get("title"),
        "lizenz": paket.get("license_id"), "geaendert": paket.get("metadata_modified"),
        "notiz": re.sub(r"\s+", " ", paket.get("notes") or "")[:600],
        "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url")}
                       for r in paket.get("resources", [])][:40],
    }


# 1. CKAN-Suchen
SUCHEN = {
    "mobidata": ("https://mobidata-bw.de/api/3/action/package_search",
                 ["groups:verkehrszaehldaten", "Verkehrszählung", "Zählung", "Knotenpunkt", "Zähldaten",
                  "Freiburg", "Karlsruhe", "Mannheim", "Ulm", "Tübingen", "Heilbronn", "Pforzheim",
                  "Reutlingen", "Esslingen", "Ludwigsburg"]),
    "govdata": ("https://www.govdata.de/ckan/api/3/action/package_search",
                ["Verkehrszählung", "Verkehrszählungen", "Zähldaten Verkehr", "Knotenpunktzählung",
                 "Querschnittszählung", "Knotenstrom", "Verkehrsmengen", "Freiburg Verkehr"]),
}
for portal, (api, begriffe) in SUCHEN.items():
    funde = {}
    for b in begriffe:
        q = {"fq": b, "rows": 1000} if b.startswith("groups:") else {"q": b, "rows": 1000}
        try:
            r = hole(api + "?" + urllib.parse.urlencode(q))["result"]
            protokoll[f"{portal}:{b}"] = r["count"]
            for p in r["results"]:
                funde.setdefault(p["name"], kurz(p))["treffer"] = funde.get(p["name"], {}).get("treffer", []) + [b]
        except Exception as e:  # noqa: BLE001
            protokoll[f"{portal}:{b}"] = repr(e)[:200]
    (ZIEL / f"{portal}.json").write_text(json.dumps(funde, ensure_ascii=False, indent=1))

# 2. FragDenStaat: Anfragen zu Verkehrszählungen in BW-Städten
fds = {}
for stadt in ("Freiburg", "Karlsruhe", "Mannheim", "Ulm", "Tübingen", "Heilbronn", "Pforzheim",
              "Reutlingen", "Esslingen", "Ludwigsburg", "Heidelberg", "Stuttgart", "Konstanz"):
    try:
        r = hole("https://fragdenstaat.de/api/v1/request/?" + urllib.parse.urlencode(
            {"q": f"Verkehrszählung {stadt}", "limit": 50}))
        fds[stadt] = [{"titel": o.get("title"), "url": o.get("url"), "status": o.get("status"),
                       "ergebnis": o.get("resolution"), "datum": o.get("first_message"),
                       "behoerde": (o.get("public_body") or {}).get("name")
                       if isinstance(o.get("public_body"), dict) else o.get("public_body")}
                      for o in r.get("objects", [])]
    except Exception as e:  # noqa: BLE001
        fds[stadt] = repr(e)[:200]
(ZIEL / "fragdenstaat.json").write_text(json.dumps(fds, ensure_ascii=False, indent=1))

# 3. Freiburg: Seiten und Jahrbücher
freiburg = ZIEL / "freiburg"
freiburg.mkdir(exist_ok=True)
for name, url in {
    "opendata.html": "https://www.freiburg.de/opendata",
    "fritz.html": "https://fritz.freiburg.de/",
    "jahrbuch_2019.pdf": "https://fritz.freiburg.de/Bibliothek/statistik_veroeffentlichungen_Jahrbuch_2019.pdf",
    "jahrbuch_2017.pdf": "https://fritz.freiburg.de/Bibliothek/statistik_veroeffentlichungen_Jahrbuch_2017-NIEDRIG.pdf",
    "jahrbuch_merge.pdf": "https://freiburg.de/pb/site/Freiburg/get/params_E1740955684/1631036/Jahrbuch_merge.pdf",
}.items():
    try:
        daten = hole(url, roh=True)
        (freiburg / name).write_bytes(daten)
        if daten.startswith(b"%PDF"):
            subprocess.run(["pdftotext", "-layout", str(freiburg / name), str(freiburg / name) + ".txt"],
                           check=False)
        protokoll[url] = len(daten)
    except Exception as e:  # noqa: BLE001
        protokoll[url] = repr(e)[:200]
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1))
print(json.dumps(protokoll, ensure_ascii=False, indent=1)[:4000])
