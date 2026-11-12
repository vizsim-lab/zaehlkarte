"""Zweiter Erkundungsschritt: Hamburg (Tageswerte, Lage, ob der Dienst noch läuft) und Berlin
(doppelte Zeilen in der neuen Qualitätssicherung)."""
from __future__ import annotations

import io
import json
import sys
import tarfile
import gzip
import traceback
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url, timeout=300):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def sta(basis, pfad, **params):
    q = urllib.parse.urlencode(params, safe="$(),;'/=", quote_via=urllib.parse.quote)
    return json.loads(hole(f"{basis}/{pfad}?{q}", 120))


def hamburg(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    out = {}
    # läuft der Server überhaupt noch? jüngste Beobachtungen insgesamt
    for basis in ("https://iot.hamburg.de/v1.1", "https://iot.hamburg.de/v1.0"):
        try:
            o = sta(basis, "Observations", **{"$top": "5", "$orderby": "phenomenonTime desc",
                                                "$expand": "Datastream($select=name,properties)"})
            out[f"{basis} juengste"] = [{"zeit": x.get("phenomenonTime"), "ds": (x.get("Datastream") or {}).get("name"),
                                         "dienst": ((x.get("Datastream") or {}).get("properties") or {}).get("serviceName")}
                                        for x in o.get("value", [])]
        except Exception as e:  # noqa: BLE001
            out[f"{basis} juengste"] = repr(e)
    for basis, dienst, layer in (("https://iot.hamburg.de/v1.1", "HH_STA_AutomatisierteVerkehrsmengenerfassung", "Anzahl_Kfz_Zaehlstelle_1-Tag"),
                                 ("https://iot.hamburg.de/v1.0", "HH_STA_HamburgerRadzaehlnetz", "Anzahl_Fahrraeder_Zaehlstelle_1-Tag")):
        filt = f"properties/serviceName eq '{dienst}' and properties/layerName eq '{layer}'"
        try:
            ds = sta(basis, "Datastreams", **{"$filter": filt, "$top": "3", "$count": "true",
                                               "$expand": "Thing($expand=Locations),Sensor,ObservedProperty"})
            out[f"{dienst} datastreams"] = ds.get("@iot.count")
            out[f"{dienst} beispiel"] = ds.get("value", [])[:2]
            for d in ds.get("value", [])[:2]:
                obs = sta(basis, f"Datastreams({d['@iot.id']})/Observations",
                          **{"$top": "400", "$orderby": "phenomenonTime asc"})
                werte = obs.get("value", [])
                out[f"{dienst} obs {d['@iot.id']}"] = {"n": len(werte), "erste": werte[:3], "letzte": werte[-3:],
                                                      "felder": sorted({k for w in werte for k in w}),
                                                      "naechste": obs.get("@iot.nextLink")}
                obs2 = sta(basis, f"Datastreams({d['@iot.id']})/Observations",
                           **{"$top": "5", "$orderby": "phenomenonTime desc"})
                out[f"{dienst} obs {d['@iot.id']} juengste"] = obs2.get("value", [])
                cnt = sta(basis, f"Datastreams({d['@iot.id']})/Observations", **{"$top": "0", "$count": "true"})
                out[f"{dienst} obs {d['@iot.id']} anzahl"] = cnt.get("@iot.count")
            # Lage aller Zählstellen: Anzahl Things mit Location
            things = sta(basis, "Things", **{"$filter": f"Datastreams/properties/serviceName eq '{dienst}'",
                                              "$top": "2", "$count": "true", "$expand": "Locations"})
            out[f"{dienst} things"] = {"anzahl": things.get("@iot.count"), "beispiel": things.get("value", [])[:2]}
        except Exception:  # noqa: BLE001
            out[f"{dienst} fehler"] = traceback.format_exc()
    (ziel / "erkundung2.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


def berlin(ziel: Path):
    ziel.mkdir(parents=True, exist_ok=True)
    blob = "https://mdhopendata.blob.core.windows.net/verkehrsdetektion"
    out = {}
    for name in ("2024/neue_qualitaetssicherung/Fahrstreifendetektoren/detektoren_2024_06.tgz",
                 "2025/neue_qualitaetssicherung/Fahrstreifendetektoren/detektor_2025_06.tgz",
                 "2025/neue_qualitaetssicherung/Fahrstreifendetektoren/detektor_2025_03.tgz"):
        daten = hole(f"{blob}/{name}", 600)
        bericht = {"glieder": 0, "zeilen": 0, "doppelt_gleich": 0, "doppelt_verschieden": 0,
                   "beispiele_verschieden": [], "stunden_formate": Counter(), "tage": Counter(),
                   "vollstaendigkeit": Counter(), "kopf": Counter()}
        with tarfile.open(fileobj=io.BytesIO(daten), mode="r:*") as tf:
            for m in tf.getmembers():
                if not m.isfile():
                    continue
                inhalt = tf.extractfile(m).read()
                if m.name.endswith(".gz"):
                    inhalt = gzip.decompress(inhalt)
                zeilen = inhalt.decode("utf-8", "replace").splitlines()
                bericht["glieder"] += 1
                bericht["kopf"][zeilen[0]] += 1
                kopf = zeilen[0].split(";")
                gesehen = {}
                for z in zeilen[1:]:
                    t = z.split(";")
                    if len(t) < 3:
                        continue
                    bericht["zeilen"] += 1
                    bericht["stunden_formate"][len(t[1])] += 1
                    bericht["tage"][t[0][:7]] += 1
                    schluessel = (t[0], int(float(t[1])))
                    rest = tuple(t[2:])
                    if schluessel in gesehen:
                        if gesehen[schluessel] == rest:
                            bericht["doppelt_gleich"] += 1
                        else:
                            bericht["doppelt_verschieden"] += 1
                            if len(bericht["beispiele_verschieden"]) < 8:
                                bericht["beispiele_verschieden"].append({"datei": m.name, "kopf": kopf, "a": [*schluessel, *gesehen[schluessel]], "b": [*schluessel, *rest]})
                    else:
                        gesehen[schluessel] = rest
                    for i, k in enumerate(kopf):
                        if k.lower().startswith(("vollst", "datapoints")) and i < len(t):
                            try:
                                bericht["vollstaendigkeit"][round(float(t[i]) / 25) * 25 if t[i] != "NaN" else "NaN"] += 1
                            except ValueError:
                                bericht["vollstaendigkeit"]["?"] += 1
        bericht = {k: (dict(v) if isinstance(v, Counter) else v) for k, v in bericht.items()}
        out[name] = bericht
        print("Berlin:", name, flush=True)
    (ziel / "doppelte.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str))


if __name__ == "__main__":
    wurzel = Path(sys.argv[1])
    for teil, fn in (("hamburg", hamburg), ("berlin", berlin)):
        try:
            fn(wurzel / teil)
        except Exception:  # noqa: BLE001
            (wurzel / teil).mkdir(parents=True, exist_ok=True)
            (wurzel / teil / "fehler2.txt").write_text(traceback.format_exc())
