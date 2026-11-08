"""Werkzeug: Rohdaten weiterer Städte holen und auf den Branch legen (nur zum Ansehen).

- Konstanz: Datensatz „Mobile Verkehrszählungen Rad- und Fußverkehr“ (API + alle Ressourcen)
- Moers: alle Datensätze „Verkehrszählungen 20xx (Stadt Moers)“ auf offenesdatenportal.de
  (API-Metadaten samt Lizenz, alle Ressourcen)
- Potsdam: Datensatz „verkehrszahlungen“ (Opendatasoft-Export) und die ersten PDFs
"""

import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/staedte")
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
protokoll = {}


def hole(url: str, timeout: int = 120) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as a:
        return a.read()


def lege(pfad: pathlib.Path, url: str) -> None:
    try:
        inhalt = hole(url)
        pfad.parent.mkdir(parents=True, exist_ok=True)
        pfad.write_bytes(inhalt)
        protokoll[str(pfad)] = {"url": url, "bytes": len(inhalt)}
    except Exception as e:  # noqa: BLE001
        protokoll[str(pfad)] = {"url": url, "fehler": repr(e)[:200]}


def sicher(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.unquote(urllib.parse.unquote(name)))[-120:]


# Konstanz
k = ZIEL / "konstanz"
for api in ("https://offenedaten-konstanz.de/api/3/action/package_show?id=mobile-verkehrsz-hlungen-rad-und-fu-verkehr",
            "https://offenedaten-konstanz.de/api/3/action/package_search?q=Verkehrsz%C3%A4hlung&rows=50"):
    lege(k / sicher(api.split("action/")[1] + ".json"), api)
lege(k / "seite.html", "https://offenedaten-konstanz.de/dataset/mobile-verkehrsz-hlungen-rad-und-fu-verkehr")
try:
    paket = json.loads((k / sicher("package_show?id=mobile-verkehrsz-hlungen-rad-und-fu-verkehr.json")).read_text())
    ressourcen = paket["result"][0]["resources"] if isinstance(paket["result"], list) else paket["result"]["resources"]
    for r in ressourcen:
        url = r.get("url") or ""
        url = url.replace("%25", "%")  # doppelt kodierte Umlaute in den Metadaten
        if url:
            lege(k / "dateien" / sicher(url.rsplit("/", 1)[-1]), url)
except Exception as e:  # noqa: BLE001
    protokoll["konstanz_ressourcen"] = {"fehler": repr(e)[:200]}

# Moers
m = ZIEL / "moers"
such = "https://www.offenesdatenportal.de/api/3/action/package_search?rows=100&q=" + urllib.parse.quote("Verkehrszählungen Moers")
lege(m / "suche.json", such)
try:
    treffer = json.loads((m / "suche.json").read_text())["result"]["results"]
    for p in treffer:
        if "moers" not in (p.get("title") or "").lower() and "moers" not in json.dumps(p.get("organization") or {}).lower():
            continue
        (m / sicher(p["name"])).mkdir(parents=True, exist_ok=True)
        (m / sicher(p["name"]) / "paket.json").write_text(json.dumps(p, ensure_ascii=False, indent=1))
        for r in p.get("resources", []):
            url = r.get("url") or ""
            if url:
                lege(m / sicher(p["name"]) / sicher(url.rsplit("/", 1)[-1]), url)
except Exception as e:  # noqa: BLE001
    protokoll["moers"] = {"fehler": repr(e)[:200]}

# Potsdam (Opendatasoft)
pd = ZIEL / "potsdam"
lege(pd / "export.json", "https://opendata.potsdam.de/api/explore/v2.1/catalog/datasets/verkehrszahlungen/exports/json")
lege(pd / "meta.json", "https://opendata.potsdam.de/api/explore/v2.1/catalog/datasets/verkehrszahlungen")
try:
    saetze = json.loads((pd / "export.json").read_text())
    links = []
    for s in saetze:
        for v in s.values():
            if isinstance(v, dict) and v.get("url"):
                links.append(v["url"])
            elif isinstance(v, str) and v.lower().endswith(".pdf"):
                links.append(v)
    for url in links[:6]:
        lege(pd / "pdf" / sicher(url.rsplit("/", 1)[-1]), url)
except Exception as e:  # noqa: BLE001
    protokoll["potsdam"] = {"fehler": repr(e)[:200]}

ZIEL.mkdir(parents=True, exist_ok=True)
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, indent=1, ensure_ascii=False))
print(json.dumps({k: v for k, v in protokoll.items() if "fehler" in v}, indent=1, ensure_ascii=False)[:3000])
print(len(protokoll), "Abrufe")
