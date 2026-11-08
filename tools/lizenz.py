"""Werkzeug: Lizenzangaben zum Münster-Datensatz „Verkehrszählung – Manuelle Verkehrserhebung“
abrufen (Portalseite, Portal-API, Open.NRW, GovData) und unverändert ablegen."""

import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/lizenz")
ID = "verkehrsz%C3%A4hlung-manuelle-verkehrserhebung"
ADRESSEN = {
    "muenster_seite.html": f"https://opendata.stadt-muenster.de/dataset/{ID}",
    "muenster_api_show.json": f"https://opendata.stadt-muenster.de/api/3/action/package_show?id={ID}",
    "muenster_api_search.json": "https://opendata.stadt-muenster.de/api/3/action/package_search?q="
    + urllib.parse.quote("Verkehrszählung"),
    "muenster_start.html": "https://opendata.stadt-muenster.de/",
    "muenster_lizenzen.html": "https://opendata.stadt-muenster.de/lizenzen",
    "muenster_nutzung.html": "https://opendata.stadt-muenster.de/nutzungsbedingungen",
    "opennrw_search.json": "https://ckan.open.nrw.de/api/3/action/package_search?rows=20&q="
    + urllib.parse.quote('"Manuelle Verkehrserhebung"'),
    "govdata_search.json": "https://www.govdata.de/ckan/api/3/action/package_search?rows=20&q="
    + urllib.parse.quote('"Manuelle Verkehrserhebung"'),
}
ZIEL.mkdir(parents=True, exist_ok=True)
protokoll = {}
for datei, url in ADRESSEN.items():
    try:
        anfrage = urllib.request.Request(url, headers={"User-Agent": "zaehlkarte-werkzeug/0.1"})
        with urllib.request.urlopen(anfrage, timeout=60) as antwort:
            inhalt = antwort.read()
            (ZIEL / datei).write_bytes(inhalt)
            protokoll[datei] = {"url": url, "status": antwort.status, "bytes": len(inhalt),
                                "final": antwort.geturl()}
    except urllib.error.HTTPError as e:
        protokoll[datei] = {"url": url, "status": e.code}
    except Exception as e:  # noqa: BLE001 – Werkzeug, alles protokollieren
        protokoll[datei] = {"url": url, "fehler": repr(e)[:300]}
(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, indent=1, ensure_ascii=False))
print(json.dumps(protokoll, indent=1, ensure_ascii=False))
