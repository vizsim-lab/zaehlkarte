"""Dritter Schritt: Gibt es in Hamburg einen Nachfolger der „(veraltet)“-Verkehrsdienste?"""
from __future__ import annotations

import json
import sys
import traceback
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return json.loads(r.read())


def sta(basis, pfad, **params):
    q = urllib.parse.urlencode(params, safe="$(),;'/=", quote_via=urllib.parse.quote)
    return hole_json(f"{basis}/{pfad}?{q}")


def main(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    out = {}
    for basis in ("https://iot.hamburg.de/v1.1", "https://iot.hamburg.de/v1.0"):
        dienste: Counter = Counter()
        beispiele = {}
        url = f"{basis}/Datastreams?" + urllib.parse.urlencode(
            {"$select": "id,name,properties,phenomenonTime", "$top": "100",
             "$filter": "properties/topic eq 'Verkehr'"}, safe="$(),;'/=", quote_via=urllib.parse.quote)
        seiten = 0
        try:
            while url and seiten < 400:
                a = hole_json(url)
                for d in a.get("value", []):
                    p = d.get("properties") or {}
                    s = (p.get("serviceName"), p.get("layerName"), "veraltet" in (d.get("name") or ""))
                    dienste[s] += 1
                    ende = (d.get("phenomenonTime") or "").split("/")[-1]
                    if s not in beispiele or ende > beispiele[s]["ende"]:
                        beispiele[s] = {"name": d.get("name"), "ende": ende, "id": d.get("@iot.id")}
                url = a.get("@iot.nextLink")
                seiten += 1
        except Exception:  # noqa: BLE001
            out[f"{basis} fehler"] = traceback.format_exc()
        out[basis] = [{"dienst": k[0], "layer": k[1], "veraltet": k[2], "n": n, **beispiele[k]}
                      for k, n in sorted(dienste.items(), key=lambda x: str(x[0]))]
        out[f"{basis} seiten"] = seiten
    # MultiDatastreams mit Verkehr
    for basis in ("https://iot.hamburg.de/v1.1",):
        try:
            m = sta(basis, "MultiDatastreams", **{"$top": "5", "$count": "true",
                                                    "$filter": "properties/topic eq 'Verkehr'"})
            out[f"{basis} multidatastreams"] = {"n": m.get("@iot.count"), "beispiel": m.get("value", [])[:2]}
        except Exception:  # noqa: BLE001
            out[f"{basis} multidatastreams fehler"] = traceback.format_exc()
    (ziel / "erkundung3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]) / "hamburg")
