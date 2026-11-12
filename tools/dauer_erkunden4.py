"""Vierter Schritt: Wie weit reichen die neuen Hamburger Dienste zurück (Stunde/Tag), Lage, Richtung."""
from __future__ import annotations

import json
import sys
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}
BASIS = "https://iot.hamburg.de/v1.1"


def hole_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.loads(r.read())


def sta(pfad, **params):
    q = urllib.parse.urlencode(params, safe="$(),;'/=", quote_via=urllib.parse.quote)
    return hole_json(f"{BASIS}/{pfad}?{q}")


def main(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    out = {}
    for dienst, layer in (("HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren", "Anzahl_Kfz_Zaehlstelle_1-Stunde"),
                          ("HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren", "Anzahl_Kfz_Zaehlstelle_1-Tag"),
                          ("HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren", "Anzahl_Schwerverkehr_Zaehlstelle_1-Stunde"),
                          ("HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren", "Anzahl_Kfz_Zaehlstelle_15-Min"),
                          ("HH_STA_Verkehrsdaten_Rad_Infrarotdetektoren", "Anzahl_Fahrraeder_Zaehlstelle_1-Stunde"),
                          ("HH_STA_Verkehrsdaten_Rad_Infrarotdetektoren", "Anzahl_Fahrraeder_Zaehlstelle_1-Tag")):
        k = f"{dienst} {layer}"
        try:
            filt = f"properties/serviceName eq '{dienst}' and properties/layerName eq '{layer}'"
            beginne, enden, n = [], [], 0
            url = f"{BASIS}/Datastreams?" + urllib.parse.urlencode(
                {"$filter": filt, "$select": "id,phenomenonTime", "$top": "100"}, safe="$(),;'/=",
                quote_via=urllib.parse.quote)
            while url:
                a = hole_json(url)
                for d in a.get("value", []):
                    n += 1
                    if d.get("phenomenonTime"):
                        b, e = d["phenomenonTime"].split("/")
                        beginne.append(b)
                        enden.append(e)
                url = a.get("@iot.nextLink")
            beginne.sort()
            out[k] = {"datastreams": n, "mit_zeit": len(beginne),
                      "beginn_min": beginne[:3], "beginn_median": beginne[len(beginne) // 2] if beginne else None,
                      "beginn_max": beginne[-3:], "ende_min": sorted(enden)[:3]}
            ds = sta("Datastreams", **{"$filter": filt, "$top": "1",
                                       "$expand": "Thing($expand=Locations),ObservedProperty,Sensor"})["value"][0]
            out[k]["beispiel"] = ds
            i = ds["@iot.id"]
            out[k]["obs_anzahl"] = sta(f"Datastreams({i})/Observations", **{"$top": "0", "$count": "true"}).get("@iot.count")
            out[k]["obs_erste"] = sta(f"Datastreams({i})/Observations", **{"$top": "3", "$orderby": "phenomenonTime asc"}).get("value")
            out[k]["obs_letzte"] = sta(f"Datastreams({i})/Observations", **{"$top": "3", "$orderby": "phenomenonTime desc"}).get("value")
        except Exception:  # noqa: BLE001
            out[k] = {"fehler": traceback.format_exc()}
        print(k, flush=True)
    (ziel / "erkundung4.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]) / "hamburg")
