"""Teil 5: Lizenz je Ressource zweier GovData-Pakete (Rad-Zählnetz Hessen, WFS Frankfurt) und die
Seite des Rad-Datensatzes auf Open Data Hessen. Nur Abruf mit robots.txt-Prüfung (hessen2.seite)."""
import json
import pathlib
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.argv = [sys.argv[0], "ergebnis/hessen5"]
import hessen2 as h  # noqa: E402

aus = {}
for name in ("dauerzahlstellen-fur-den-radverkehr-in-hessen", "wfs-verkehrsmengen-frankfurt-am-main"):
    url = "https://www.govdata.de/ckan/api/3/action/package_show?id=" + name
    try:
        inhalt, _, _ = h.seite(url)
        p = json.loads(inhalt)["result"]
        aus[name] = {
            "license_id": p.get("license_id"), "license_title": p.get("license_title"),
            "extras": {e["key"]: e["value"] for e in p.get("extras", [])},
            "ressourcen": [{k: r.get(k) for k in ("name", "url", "format", "license", "license_id",
                                                  "licenseAttributionByText", "rights", "access_url")}
                           for r in p.get("resources", [])],
        }
    except Exception as e:  # noqa: BLE001
        aus[name] = {"fehler": repr(e)[:300]}
for q in ("Dauerzählstellen Radverkehr", "Radverkehr Hessen Zählstellen"):
    url = "https://opendata.hessen.de/search?query=" + urllib.parse.quote(q)
    aus["suche " + q] = h.lies("Land", url, 1)
for slug in ("dauerzaehlstellen-fuer-den-radverkehr-in-hessen", "dauerzahlstellen-fur-den-radverkehr-in-hessen-0"):
    aus[slug] = h.lies("Land", "https://opendata.hessen.de/dataset/" + slug, 1)
h.schreibe("lizenzen.json", aus)
