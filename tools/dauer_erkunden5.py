"""Fünfter Schritt Hamburg: Namen und Lage der Zählstellen, Zuordnung Kfz/SV/Rad zu Things,
Abrufweg für Stundenwerte (Seitengröße, verschachteltes $expand), Rückreichweite erneut,
alter Dienst (Stundenwerte 2020–2023?)."""
from __future__ import annotations

import json
import statistics
import sys
import time
import traceback
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}
BASIS = "https://iot.hamburg.de/v1.1"
SAFE = "$(),;'/=:"

KFZ = "HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren"
RAD = "HH_STA_Verkehrsdaten_Rad_Infrarotdetektoren"
ALT_KFZ = "HH_STA_AutomatisierteVerkehrsmengenerfassung"
ALT_RAD = "HH_STA_HamburgerRadzaehlnetz"


def hole_json(url):
    t = time.time()
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180) as r:
        d = json.loads(r.read())
    return d, round(time.time() - t, 2)


def url_von(pfad, **params):
    return f"{BASIS}/{pfad}?" + urllib.parse.urlencode(params, safe=SAFE, quote_via=urllib.parse.quote)


def alle(pfad, **params):
    url, werte = url_von(pfad, **params), []
    while url:
        d, _ = hole_json(url)
        werte += d.get("value", [])
        url = d.get("@iot.nextLink")
    return werte


def filt(dienst, layer):
    return f"properties/serviceName eq '{dienst}' and properties/layerName eq '{layer}'"


def zeitspanne(ds):
    bs, es = [], []
    for d in ds:
        if d.get("phenomenonTime"):
            b, e = d["phenomenonTime"].split("/")
            bs.append(b)
            es.append(e)
    bs.sort()
    es.sort()
    if not bs:
        return {"mit_zeit": 0}
    return {"mit_zeit": len(bs), "beginn": [bs[0], bs[len(bs) // 2], bs[-1]],
            "ende": [es[0], es[len(es) // 2], es[-1]],
            "beginn_haeufig": Counter(b[:10] for b in bs).most_common(5)}


def main(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    out = {"abgefragt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}

    # 1. Rückreichweite erneut (Vergleich mit 17:31 UTC am 12.11.)
    for dienst, layer in ((KFZ, "Anzahl_Kfz_Zaehlstelle_1-Stunde"), (KFZ, "Anzahl_Schwerverkehr_Zaehlstelle_1-Stunde"),
                          (KFZ, "Anzahl_Kfz_Zaehlstelle_15-Min"), (KFZ, "Anzahl_Kfz_Zaehlstelle_5-Min"),
                          (RAD, "Anzahl_Fahrraeder_Zaehlstelle_1-Stunde"), (RAD, "Anzahl_Fahrraeder_Zaehlstelle_15-Min"),
                          (ALT_KFZ, "Anzahl_Kfz_Zaehlstelle_1-Stunde"), (ALT_RAD, "Anzahl_Fahrraeder_Zaehlstelle_1-Stunde"),
                          (ALT_KFZ, "Anzahl_Kfz_Zaehlstelle_1-Tag")):
        k = f"spanne {dienst} {layer}"
        try:
            ds = alle("Datastreams", **{"$filter": filt(dienst, layer), "$select": "id,phenomenonTime", "$top": "1000"})
            out[k] = {"n": len(ds), **zeitspanne(ds)}
        except Exception:
            out[k] = traceback.format_exc()[-1500:]
        print(k, out[k] if isinstance(out[k], str) else {x: out[k][x] for x in ("n", "mit_zeit")}, flush=True)

    # 2. Things und Locations: alle Eigenschaften einiger Beispiele, dazu Häufigkeiten der Schlüssel
    for dienst in (KFZ, RAD):
        k = f"things {dienst}"
        try:
            ds = alle("Datastreams", **{"$filter": filt(dienst, "Anzahl_Kfz_Zaehlstelle_1-Stunde" if dienst == KFZ
                                                        else "Anzahl_Fahrraeder_Zaehlstelle_1-Stunde"),
                                        "$select": "id,name,properties", "$top": "1000",
                                        "$expand": "Thing($select=id,name,description,properties;"
                                                   "$expand=Locations($select=id,name,description,properties,location))"})
            things = {}
            for d in ds:
                t = d.get("Thing") or {}
                things[t.get("@iot.id")] = t
            schluessel_t = Counter(k2 for t in things.values() for k2 in (t.get("properties") or {}))
            schluessel_l = Counter(k2 for t in things.values() for loc in t.get("Locations", [])
                                   for k2 in (loc.get("properties") or {}))
            loc_namen = Counter(loc.get("name") for t in things.values() for loc in t.get("Locations", []))
            out[k] = {"datastreams": len(ds), "things": len(things),
                      "thing_schluessel": schluessel_t.most_common(), "location_schluessel": schluessel_l.most_common(),
                      "location_namen_haeufig": loc_namen.most_common(10),
                      "location_typen": Counter((loc.get("location") or {}).get("type") for t in things.values()
                                                for loc in t.get("Locations", [])).most_common(),
                      "beispiele": list(things.values())[:6],
                      "ds_schluessel": Counter(k2 for d in ds for k2 in (d.get("properties") or {})).most_common(),
                      "ds_beispiele": [{x: d.get(x) for x in ("@iot.id", "name", "properties")} for d in ds[:4]]}
            # je Thing: welche Layer (Kfz-Stunde, SV-Stunde) hängen dran?
            if dienst == KFZ:
                sv = alle("Datastreams", **{"$filter": filt(KFZ, "Anzahl_Schwerverkehr_Zaehlstelle_1-Stunde"),
                                            "$select": "id,properties", "$top": "1000",
                                            "$expand": "Thing($select=id)"})
                sv_things = {d["Thing"]["@iot.id"] for d in sv if d.get("Thing")}
                out[k]["sv_things"] = len(sv_things)
                out[k]["sv_ohne_kfz_thing"] = len(sv_things - set(things))
                out[k]["sv_ds_beispiel"] = sv[:2]
        except Exception:
            out[k] = traceback.format_exc()[-1500:]
        print(k, "ok" if isinstance(out[k], dict) else out[k][-300:], flush=True)

    # 3. Abrufweg: Seitengröße und verschachteltes $expand
    try:
        ds = alle("Datastreams", **{"$filter": filt(KFZ, "Anzahl_Kfz_Zaehlstelle_1-Stunde"), "$select": "id", "$top": "5"})[:5]
        i = ds[0]["@iot.id"]
        tests = {}
        for top in (1000, 5000, 10000, 20000):
            try:
                d, s = hole_json(url_von(f"Datastreams({i})/Observations", **{"$select": "phenomenonTime,result",
                                                                             "$orderby": "phenomenonTime asc",
                                                                             "$top": str(top)}))
                tests[f"top{top}"] = {"geliefert": len(d.get("value", [])), "sekunden": s,
                                     "naechste": bool(d.get("@iot.nextLink")),
                                     "naechste_url": (d.get("@iot.nextLink") or "")[:300]}
            except Exception as e:
                tests[f"top{top}"] = repr(e)[:300]
        try:
            d, s = hole_json(url_von("Datastreams", **{
                "$filter": filt(KFZ, "Anzahl_Kfz_Zaehlstelle_1-Stunde"), "$select": "id", "$top": "50",
                "$expand": "Observations($select=phenomenonTime,result;$orderby=phenomenonTime asc;"
                           "$filter=phenomenonTime ge 2026-11-01T00:00:00Z;$top=2000)"}))
            tests["expand50"] = {"datastreams": len(d.get("value", [])), "sekunden": s,
                                 "obs": [len(x.get("Observations", [])) for x in d.get("value", [])][:50],
                                 "obs_naechste": [bool(x.get("Observations@iot.nextLink")) for x in d.get("value", [])][:10],
                                 "naechste": bool(d.get("@iot.nextLink"))}
        except Exception as e:
            tests["expand50"] = repr(e)[:500]
        out["abruf"] = tests
    except Exception:
        out["abruf"] = traceback.format_exc()[-1500:]
    print("abruf", out.get("abruf"), flush=True)

    # 4. Lücken in einer Stundenreihe: wie viele Stunden fehlen, fehlen ganze Tage?
    try:
        ds = alle("Datastreams", **{"$filter": filt(KFZ, "Anzahl_Kfz_Zaehlstelle_1-Stunde"), "$select": "id", "$top": "1000"})
        probe = {}
        for d in ds[:: max(1, len(ds) // 8)][:8]:
            i = d["@iot.id"]
            obs = alle(f"Datastreams({i})/Observations", **{"$select": "phenomenonTime,result",
                                                            "$orderby": "phenomenonTime asc", "$top": "10000"})
            zeiten = [o["phenomenonTime"].split("/")[0] for o in obs]
            dauer = Counter()
            for o in obs:
                a, b = o["phenomenonTime"].split("/")
                dauer[b[14:19]] += 1
            tage = Counter(z[:10] for z in zeiten)
            werte = [o["result"] for o in obs]
            probe[i] = {"n": len(obs), "erste": zeiten[:2], "letzte": zeiten[-2:],
                        "doppelt": len(zeiten) - len(set(zeiten)),
                        "tage": len(tage), "tage_24": sum(1 for v in tage.values() if v == 24),
                        "tage_verteilung": Counter(tage.values()).most_common(8),
                        "ende_minute": dauer.most_common(4),
                        "nicht_ganzzahlig": sum(1 for v in werte if not isinstance(v, int)),
                        "negativ": sum(1 for v in werte if isinstance(v, (int, float)) and v < 0),
                        "median": statistics.median(werte) if werte else None, "max": max(werte) if werte else None}
        out["luecken"] = probe
    except Exception:
        out["luecken"] = traceback.format_exc()[-1500:]
    print("luecken ok" if isinstance(out.get("luecken"), dict) else out.get("luecken"), flush=True)

    (ziel / "erkundung5.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
