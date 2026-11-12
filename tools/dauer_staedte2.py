"""Weitere Städte, zweiter Blick: Osnabrück (SensorThings), Freiburg (WFS), Heidelberg (CKAN),
Ulm (CKAN-Datastore). Schreibt nach jedem Teil, damit ein Abbruch nichts verliert."""
from __future__ import annotations

import json
import re
import sys
import traceback
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url, n=5_000_000, timeout=60):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read(n)


def js(url):
    return json.loads(hole(url, 30_000_000)[2])


def versuch(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return {"fehler": repr(e)[:300], "spur": traceback.format_exc()[-400:]}


def q(basis, pfad, **p):
    return f"{basis}/{pfad}?" + urllib.parse.urlencode(p, safe="$(),;'/=:", quote_via=urllib.parse.quote)


def main(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    out = {}

    def sichern():
        (ziel / "staedte2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))

    # 1. Osnabrück: SensorThings
    os_ = "https://daten-api.osnabrueck.de/v1.1"
    out["os things"] = versuch(lambda: js(q(os_, "Things", **{
        "$filter": "substringof('Verkehr',name)", "$top": "50",
        "$expand": "Locations,Datastreams($select=id,name,description,unitOfMeasurement,properties,"
                   "phenomenonTime;$expand=ObservedProperty($select=name,definition))"})))
    try:
        ths = out["os things"]["value"]
        out["os things_anzahl"] = len(ths)
        beispiele = {}
        for t in ths[:3]:
            for d in t.get("Datastreams", [])[:6]:
                i = d["@iot.id"]
                beispiele[i] = {
                    "anzahl": versuch(lambda: js(q(os_, f"Datastreams({i})/Observations", **{"$top": "0", "$count": "true"})).get("@iot.count")),
                    "erste": versuch(lambda: js(q(os_, f"Datastreams({i})/Observations", **{"$top": "3", "$orderby": "phenomenonTime asc"})).get("value")),
                    "letzte": versuch(lambda: js(q(os_, f"Datastreams({i})/Observations", **{"$top": "3", "$orderby": "phenomenonTime desc"})).get("value")),
                }
        out["os beobachtungen"] = beispiele
    except Exception:  # noqa: BLE001
        out["os beobachtungen"] = traceback.format_exc()[-600:]
    out["os govdata"] = versuch(lambda: js("https://ckan.govdata.de/api/3/action/package_show?id=verkehrszahlung-osnabruck")["result"])
    out["os govdata2"] = versuch(lambda: js("https://ckan.govdata.de/api/3/action/package_show?id=verkehrszahlung-osnabruckd277a")["result"])
    out["os api_seite"] = versuch(lambda: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", hole(
        "https://datenplattform.osnabrueck.de/daten-api-osnabrueck/")[2].decode("utf-8", "replace")))[:6000])
    out["os verkehr_seite"] = versuch(lambda: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", hole(
        "https://datenplattform.osnabrueck.de/verkehrszaehlung/")[2].decode("utf-8", "replace")))[:8000])
    sichern()
    print("osnabrueck ok", flush=True)

    # 2. Freiburg: WFS ganz
    fr = "https://geoportal.freiburg.de/wfs/digit_verkehrszaehl/digit_verkehrszaehl"
    try:
        cap = hole(f"{fr}?REQUEST=GetCapabilities&SERVICE=WFS", 2_000_000)[2].decode("utf-8", "replace")
        typen = re.findall(r"<FeatureType[^>]*>\s*<Name>([^<]+)</Name>", cap) or re.findall(r"<Name>([^<]+)</Name>", cap)
        out["fr typen"] = typen
        for t in typen[:8]:
            out[f"fr {t}"] = versuch(lambda: hole(
                f"{fr}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={urllib.parse.quote(t)}&COUNT=3"
                "&OUTPUTFORMAT=geojson", 300000)[2].decode("utf-8", "replace")[:4000])
            out[f"fr {t} hits"] = versuch(lambda: hole(
                f"{fr}?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES={urllib.parse.quote(t)}&RESULTTYPE=hits",
                5000)[2].decode("utf-8", "replace")[:600])
    except Exception:  # noqa: BLE001
        out["fr typen"] = traceback.format_exc()[-600:]
    sichern()
    print("freiburg ok", flush=True)

    # 3. Heidelberg: CKAN unter anderen Pfaden, Ressourcenseite, Datastore-Dump
    hd = "https://ckan.datenplattform.heidelberg.de"
    for pfad in ("/api/action/package_show?id=mobility_main_trafficcamera",
                 "/api/3/action/package_show?id=mobility_main_trafficcamera",
                 "/ckan/api/3/action/package_show?id=mobility_main_trafficcamera"):
        out[f"hd {pfad}"] = versuch(lambda: (lambda r: {"status": r[0], "typ": r[1], "anfang": r[2][:3000].decode("utf-8", "replace")})(hole(hd + pfad, 3_000_000)))
    out["hd seite"] = versuch(lambda: sorted(set(re.findall(r'href="([^"]*(?:download|datastore|dump|\.csv)[^"]*)"', hole(
        f"{hd}/dataset/mobility_main_trafficcamera/resource/b95871b2-7de0-46b1-b377-db497250f8a0")[2].decode("utf-8", "replace"))))[:30])
    out["hd paket_seite"] = versuch(lambda: sorted(set(re.findall(r'href="(/[a-z]*/?dataset/mobility_main_trafficcamera/resource/[^"]+)"', hole(
        f"{hd}/dataset/mobility_main_trafficcamera")[2].decode("utf-8", "replace"))))[:40])
    out["hd dump"] = versuch(lambda: hole(f"{hd}/datastore/dump/b95871b2-7de0-46b1-b377-db497250f8a0?limit=3", 20000)[2].decode("utf-8", "replace")[:3000])
    sichern()
    print("heidelberg ok", flush=True)

    # 4. Ulm: Datastore der Kameras
    ul = "https://datenhub.ulm.de/ckan/api/3/action/"
    for rid in ("7f6bab64-4901-4b0a-8f64-77e35f6184f4", "44587a3b-cbfe-47ef-8d28-48a5c6913ad1"):
        out[f"ulm {rid}"] = versuch(lambda: js(f"{ul}datastore_search?resource_id={rid}&limit=3")["result"])
        if isinstance(out[f"ulm {rid}"], dict):
            r = out[f"ulm {rid}"]
            out[f"ulm {rid}"] = {"gesamt": r.get("total"), "felder": r.get("fields"), "erste": r.get("records")}
    sichern()
    print("ulm ok", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
