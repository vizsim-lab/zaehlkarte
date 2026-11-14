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
    # package_show sperrt robots.txt, package_search nicht (Teil 1)
    url = ("https://www.govdata.de/ckan/api/3/action/package_search?rows=1&q="
           + urllib.parse.quote(f'name:"{name}"'))
    try:
        inhalt, _, _ = h.seite(url)
        p = json.loads(inhalt)["result"]["results"][0]
        aus[name] = {
            "license_id": p.get("license_id"), "license_title": p.get("license_title"),
            "extras": {e["key"]: e["value"] for e in p.get("extras", [])},
            "ressourcen": [{k: v for k, v in r.items() if v not in (None, "", [])}
                           for r in p.get("resources", [])],
        }
    except Exception as e:  # noqa: BLE001
        aus[name] = {"fehler": repr(e)[:300]}
h.schreibe("lizenzen.json", aus)
