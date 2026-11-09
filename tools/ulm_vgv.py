"""Werkzeug: Ulm – Datensatz „vgv_ulm“ (Verkehrszählungen des VGV-Projekts) im Datenhub ansehen:
Paket, je Ressource Felder, Zahl der Zeilen, erste und letzte Zeilen; dazu die Paketliste."""

import json
import pathlib
import sys
import urllib.parse
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/ulm")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
API = "https://datenhub.ulm.de/ckan/api/3/action/"
protokoll = {}


def hole(aktion, **q):
    url = API + aktion + ("?" + urllib.parse.urlencode(q) if q else "")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as a:
        return json.loads(a.read())["result"]


def schreibe(name, obj):
    (ZIEL / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


try:
    paket = hole("package_show", id="vgv_ulm")
    schreibe("vgv_paket.json", paket)
    ressourcen = {}
    for r in paket.get("resources", []):
        rid = r["id"]
        eintrag = {"name": r.get("name"), "url": r.get("url"), "format": r.get("format"),
                   "beschreibung": r.get("description"), "datastore": r.get("datastore_active")}
        try:
            erst = hole("datastore_search", resource_id=rid, limit=5)
            eintrag["felder"] = erst.get("fields")
            eintrag["zeilen"] = erst.get("total")
            eintrag["erste"] = erst.get("records")
            felder = [f["id"] for f in erst.get("fields", [])]
            zeit = next((f for f in felder if f.lower() in ("timestamp", "zeit", "time", "datum",
                                                              "date", "zeitstempel")), None)
            if zeit:
                eintrag["letzte"] = hole("datastore_search", resource_id=rid, limit=5,
                                         sort=f"{zeit} desc").get("records")
                eintrag["frueheste"] = hole("datastore_search", resource_id=rid, limit=2,
                                            sort=f"{zeit} asc").get("records")
        except Exception as e:  # noqa: BLE001
            eintrag["fehler"] = repr(e)[:200]
            if r.get("url"):
                try:
                    with urllib.request.urlopen(urllib.request.Request(r["url"], headers=UA),
                                                timeout=120) as a:
                        eintrag["datei_anfang"] = a.read(4000).decode("utf-8", "replace")
                except Exception as e2:  # noqa: BLE001
                    eintrag["datei_fehler"] = repr(e2)[:200]
        ressourcen[rid] = eintrag
    schreibe("vgv_ressourcen.json", ressourcen)
except Exception as e:  # noqa: BLE001
    protokoll["vgv"] = repr(e)[:300]

try:
    schreibe("pakete.json", hole("package_list"))
except Exception as e:  # noqa: BLE001
    protokoll["package_list"] = repr(e)[:300]

schreibe("protokoll.json", protokoll)
print(json.dumps(protokoll, ensure_ascii=False, indent=1))
