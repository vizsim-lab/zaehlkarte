"""Weitere Städte für Dauerzählstellen: Kataloge (CKAN, Opendatasoft) durchsuchen und die
Kandidaten Heidelberg, Ulm, Freiburg, Osnabrück, Leipzig genauer ansehen. Nur Metadaten und
kleine Stichproben (je Ressource höchstens wenige Zeilen)."""
from __future__ import annotations

import json
import re
import sys
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url, n=2_000_000):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read(n)


def hole_json(url):
    _, _, b = hole(url, 20_000_000)
    return json.loads(b)


def versuch(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return {"fehler": repr(e)[:400], "spur": traceback.format_exc()[-600:]}


def ckan_suche(basis, q, rows=25):
    url = f"{basis}package_search?" + urllib.parse.urlencode({"q": q, "rows": rows})
    d = hole_json(url)["result"]
    return {"anzahl": d.get("count"), "treffer": [
        {"name": p.get("name"), "titel": p.get("title"), "lizenz": p.get("license_id") or p.get("license_title"),
         "geaendert": p.get("metadata_modified"), "org": (p.get("organization") or {}).get("title"),
         "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url"),
                         "datastore": r.get("datastore_active"), "id": r.get("id")} for r in p.get("resources", [])][:8]}
        for p in d.get("results", [])]}


def ckan_paket(basis, name):
    p = hole_json(f"{basis}package_show?id={urllib.parse.quote(name)}")["result"]
    return {"titel": p.get("title"), "lizenz": p.get("license_id"), "lizenz_titel": p.get("license_title"),
            "geaendert": p.get("metadata_modified"), "notes": (p.get("notes") or "")[:1500],
            "extras": p.get("extras"),
            "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url"),
                            "datastore": r.get("datastore_active"), "id": r.get("id"),
                            "geaendert": r.get("last_modified") or r.get("metadata_modified"),
                            "beschreibung": (r.get("description") or "")[:300]} for r in p.get("resources", [])]}


def ckan_datastore(basis, rid, sortfeld=None):
    out = {}
    d = hole_json(f"{basis}datastore_search?" + urllib.parse.urlencode({"resource_id": rid, "limit": 2}))["result"]
    out["gesamt"] = d.get("total")
    out["felder"] = [f.get("id") for f in d.get("fields", [])]
    out["erste"] = d.get("records")
    if sortfeld:
        for richtung in ("asc", "desc"):
            d = hole_json(f"{basis}datastore_search?" + urllib.parse.urlencode(
                {"resource_id": rid, "limit": 1, "sort": f"{sortfeld} {richtung}"}))["result"]
            out[f"sort_{richtung}"] = d.get("records")
    return out


def main(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    out = {}

    # 1. Kataloge breit durchsuchen
    kataloge = {
        "govdata": "https://ckan.govdata.de/api/3/action/",
        "mobidata_bw": "https://mobidata-bw.de/ckan/api/3/action/",
        "open_nrw": "https://ckan.open.nrw.de/api/3/action/",
        "leipzig": "https://opendata.leipzig.de/api/3/action/",
        "heidelberg": "https://ckan.datenplattform.heidelberg.de/api/3/action/",
        "ulm": "https://datenhub.ulm.de/ckan/api/3/action/",
        "konstanz": "https://offenedaten-konstanz.de/api/3/action/",
        "darmstadt": "https://opendata.darmstadt.de/api/3/action/",
        "kaiserslautern": "https://opendata.kaiserslautern.de/api/3/action/",
        "osnabrueck": "https://opendata.osnabrueck.de/api/3/action/",
        "wiesbaden": "https://opendata.cloud.wiesbaden.de/api/3/action/",
    }
    fragen = ["Dauerzählstelle", "Dauerzählstellen Kfz", "Verkehrszählung Stundenwerte", "Verkehrsdetektion",
              "Zählkamera", "Wärmebildkamera Verkehr", "Verkehrsstärke", "TrafficFlowObserved", "Verkehrszählung"]
    for k, basis in kataloge.items():
        for q in (fragen if k in ("govdata", "mobidata_bw", "open_nrw") else ["Verkehrszählung", "Zählstelle", "Verkehr"]):
            out[f"suche {k} {q}"] = versuch(lambda: ckan_suche(basis, q))
            print(k, q, (out[f"suche {k} {q}"] or {}).get("anzahl", out[f"suche {k} {q}"]), flush=True)

    # Opendatasoft (Mannheim)
    for q in ("verkehr", "zählung"):
        out[f"ods mannheim {q}"] = versuch(lambda: hole_json(
            "https://mannheim.opendatasoft.com/api/explore/v2.1/catalog/datasets?"
            + urllib.parse.urlencode({"where": f'search("{q}")', "limit": 50})))

    # 2. Heidelberg im Detail
    hd = "https://ckan.datenplattform.heidelberg.de/api/3/action/"
    for name in ("mobility_main_trafficcamera", "mobility_main_bikecounter", "verkehrsleitrechnerdaten-in-heidelberg",
                 "verkehr-in-heidelberg-ngsi-ld"):
        p = versuch(lambda: ckan_paket(hd, name))
        out[f"heidelberg {name}"] = p
        if isinstance(p, dict) and "ressourcen" in p:
            for r in p["ressourcen"][:20]:
                if r.get("datastore"):
                    r["probe"] = versuch(lambda: ckan_datastore(hd, r["id"], "dateObserved"))
    # 3. Ulm
    ul = "https://datenhub.ulm.de/ckan/api/3/action/"
    for name in ("vgv_ulm", "fahrradzahler_lupferbruecke"):
        out[f"ulm {name}"] = versuch(lambda: ckan_paket(ul, name))
    # erste Zeilen der jüngsten Ulmer Datei
    try:
        rs = out["ulm vgv_ulm"]["ressourcen"]
        r = sorted(rs, key=lambda x: x.get("geaendert") or "")[-1]
        _, typ, b = hole(r["url"], 4000)
        out["ulm probe"] = {"url": r["url"], "typ": typ, "anfang": b.decode("utf-8", "replace")[:3000]}
    except Exception as e:  # noqa: BLE001
        out["ulm probe"] = repr(e)
    # 4. Freiburg WFS
    fr = "https://geoportal.freiburg.de/wfs/digit_verkehrszaehl/digit_verkehrszaehl"
    out["freiburg cap"] = versuch(lambda: hole(f"{fr}?REQUEST=GetCapabilities&SERVICE=WFS", 60000)[2].decode("utf-8", "replace")[:6000])
    try:
        cap = out["freiburg cap"] if isinstance(out["freiburg cap"], str) else ""
        typen = re.findall(r"<(?:wfs:)?Name>([^<]+)</(?:wfs:)?Name>", cap)
        out["freiburg typen"] = typen
        for t in typen[:6]:
            out[f"freiburg {t}"] = versuch(lambda: hole(
                f"{fr}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={urllib.parse.quote(t)}&COUNT=3"
                "&OUTPUTFORMAT=application/json", 200000)[2].decode("utf-8", "replace")[:5000])
            out[f"freiburg {t} hits"] = versuch(lambda: hole(
                f"{fr}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={urllib.parse.quote(t)}&RESULTTYPE=hits",
                5000)[2].decode("utf-8", "replace")[:800])
    except Exception as e:  # noqa: BLE001
        out["freiburg typen"] = repr(e)
    # 5. Osnabrück und Leipzig: Seiten nach Daten-Links durchsuchen
    for k, url in (("osnabrueck", "https://datenplattform.osnabrueck.de/verkehrszaehlung/"),
                   ("leipzig", "https://www.leipzig.de/verkehrszaehlungen"),
                   ("hamburg_verkehrsstaerken", "https://www.hamburg.de/politik-und-verwaltung/behoerden/bvm/verkehrsstaerken-kfz-193324")):
        try:
            st, typ, b = hole(url, 3_000_000)
            t = b.decode("utf-8", "replace")
            links = sorted(set(re.findall(r'(?:href|src)="([^"]+)"', t)))
            daten = [x for x in links if re.search(r"api|csv|json|download|daten|dashboard|arcgis|geojson|\.xlsx|opendata", x, re.I)]
            out[f"seite {k}"] = {"status": st, "typ": typ, "laenge": len(t), "daten_links": daten[:80],
                                 "titel": re.findall(r"<title>([^<]*)</title>", t)[:1],
                                 "api_hinweise": sorted(set(re.findall(r"https?://[^\s\"'<>]*(?:api|csv|json)[^\s\"'<>]*", t)))[:40]}
        except Exception as e:  # noqa: BLE001
            out[f"seite {k}"] = repr(e)[:400]
        print("seite", k, "ok" if isinstance(out[f"seite {k}"], dict) else out[f"seite {k}"], flush=True)

    (ziel / "staedte1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
