"""Prüft die Abrufe der Pipeline (sources.yaml und Code) gegen robots.txt nach RFC 9309.

Für die Kennung der Pipeline („zaehlkarte-pipeline“, sonst gilt die Gruppe „*“) und für „*“:
erlaubt oder gesperrt, dazu Crawl-delay. Ergebnis: ergebnis/robots_audit/audit.json und .md.
Aufruf: python3 tools/robots_audit.py
"""

import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path("ergebnis/robots_audit")
ZIEL.mkdir(parents=True, exist_ok=True)

# Je Quelle die Abrufe, wie Pipeline und Code sie stellen (Platzhalter durch Beispiele ersetzt)
ABRUFE = {
    "berlin (Kurzzeit)": [
        "https://raw.githubusercontent.com/vizsim/berlin-traffic-counts_schulwege/d09e6f06aaa84dd339a6e9ea91dfbf25b642c1a0/data/rohdaten-2019-2025.7z",
        "https://vizsim.github.io/berlin-traffic-counts_schulwege/data/rohdaten-fuss-2019-2025/x.zda",
    ],
    "ravensburg & Co. (MobiData BW)": [
        "https://mobidata-bw.de/daten/portal/RV_Zaehl/Verkehrszaehlungen_RV.xlsx",
        "https://mobidata-bw.de/daten/portal/RV_Zaehl/Zaehldaten_PDF-Excel_RV.zip",
    ],
    "moers": [
        "https://www.offenesdatenportal.de/api/3/action/package_show?id=verkehrszahlung-in-moers-2021",
        "https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021",
        "https://www.offenesdatenportal.de/dataset/0f1d1c6c/resource/4bcf5776/download/ackerstrasse.txt",
    ],
    "olpe": [
        "https://opendata.olpe.de/api/3/action/package_search?q=Verkehrsmessung&rows=200",
        "https://opendata.olpe.de/dataset/x",
        "https://opendata.olpe.de/dataset/x/resource/y/download/z.json",
    ],
    "potsdam": [
        "https://opendata.potsdam.de/api/explore/v2.1/catalog/datasets/verkehrszahlungen/exports/json",
        "https://opendata.potsdam.de/explore/dataset/verkehrszahlungen/information/",
    ],
    "muenster": ["https://opendata.stadt-muenster.de/sites/default/files/Verkehrsz%C3%A4hlung.zip"],
    "konstanz": ["https://offenedaten-konstanz.de/sites/default/files/Schottenstrasse_2.csv"],
    "xanten": [
        "https://opendata.ruhr/dataset/dd58836a-5e0c-4b05-97df-d3bd714e702e/resource/fea95307-56ea-425c-9a77-535b88d10598/download/20210104_gesamtubersicht_zahldaten_xanten_knotenpunkte.pdf",
    ],
    "berlin_viz": [
        "https://mdhopendata.blob.core.windows.net/verkehrsdetektion?restype=container&comp=list",
        "https://api.viz.berlin.de/daten/verkehrsdetektion",
    ],
    "hamburg_kfz/rad": [
        "https://iot.hamburg.de/v1.1/Datastreams?$filter=properties/serviceName%20eq%20%27x%27",
        "https://download.geofabrik.de/europe/germany/hamburg-latest.osm.pbf",
    ],
    "ettlingen": ["https://opendata.readi.de/datastore/dump/a903967d-9177-4db6-977c-267fd745a390"],
    "mobidata_rad": ["https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_202601.csv.gz"],
    "muenster_rad": [
        "https://codeload.github.com/od-ms/radverkehr-zaehlstellen/tar.gz/refs/heads/main",
        "https://opendata.stadt-muenster.de/sites/default/files/fahrradzaehl-standorte_0.geojson",
    ],
    "aachen_rad": [
        "https://offenedaten.aachen.de/api/3/action/package_show?id=radzaehlstellen-der-stadt-aachen",
        "https://offenedaten.aachen.de/dataset/radzaehlstellen-der-stadt-aachen",
        "https://offenedaten.aachen.de/dataset/x/resource/y/download/z.csv",
    ],
    "berlin_rad": [
        "https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/weitere-radinfrastruktur/zaehlstellen-und-fahrradbarometer/gesamtdatei-stundenwerte.xlsx",
    ],
    "muenchen_rad": [
        "https://opendata.muenchen.de/api/3/action/package_show?id=x",
        "https://opendata.muenchen.de/dataset/x/resource/y/download/z.csv",
        "https://geoportal.muenchen.de/geoserver/mor_wfs/ows?service=WFS&version=1.0.0&request=GetFeature&typeName=mor_wfs:raddauerzaehlstellen",
    ],
    "wuerzburg_rad": ["https://opendata.wuerzburg.de/api/explore/v2.1/catalog/datasets/x/exports/csv"],
    "rhein_kreis_neuss_rad": ["https://opendata.rhein-kreis-neuss.de/api/explore/v2.1/catalog/datasets/eco-counter-data/exports/csv"],
    "dortmund_rad": ["https://open-data.dortmund.de/api/explore/v2.1/catalog/datasets/fb61-dauerzaehlstelle-radverkehr-schnettkerbruecke/exports/csv"],
    "essen_rad / duesseldorf_rad": [
        "https://open.nrw/api/3/action/package_show?id=radverkehrszahlungen-e",
        "https://open.nrw/api/3/action/package_search?q=x",
        "https://ckan.open.nrw.de/dataset/x/resource/y/download/z.csv",
        "https://opendata.duesseldorf.de/sites/default/files/x.csv",
        "https://www.essen.de/x.csv",
    ],
    "leipzig_rad": ["https://geodienste.leipzig.de/l3/OpenData/wfs?service=WFS&request=GetFeature&typeName=x"],
    "rostock_rad": ["https://geo.sv.rostock.de/download/opendata/radmonitore/radmonitore_daten.csv"],
    "bochum_rad": ["https://gitlab.opencode.de/api/v4/projects/x/repository/archive"],
    "bonn_rad": ["https://opendata.bonn.de/data.json", "https://opendata.bonn.de/sites/default/files/x.csv"],
    "mannheim/ulm/… (MobiData)": ["https://mobidata-bw.de/fahrradzaehldaten/v2/"],
}
KENNUNGEN = ("zaehlkarte-pipeline", "*")


def main():
    aus, md = {}, ["| Quelle | Abruf | Pipeline | * | Crawl-delay |", "|---|---|---|---|---|"]
    for quelle, urls in ABRUFE.items():
        for url in urls:
            try:
                r = R.regeln(url)
                ok = {k: r.erlaubt(k, url) for k in KENNUNGEN}
                verz = r.verzoegerung(KENNUNGEN)
                art = "alles erlaubt" if r.alles is True else "alles gesperrt" if r.alles is False else "Regeln"
            except Exception as e:  # noqa: BLE001
                ok, verz, art = {k: None for k in KENNUNGEN}, None, f"Fehler {e!r}"[:100]
            aus.setdefault(quelle, []).append({"url": url, **ok, "crawl_delay": verz, "robots": art})
            t = urllib.parse.urlsplit(url)
            md.append(f"| {quelle} | {t.netloc}{t.path[:60]}{'?…' if t.query else ''} | "
                      f"{'ja' if ok['zaehlkarte-pipeline'] else 'NEIN'} | {'ja' if ok['*'] else 'NEIN'} | "
                      f"{verz} ({art}) |")
    (ZIEL / "audit.json").write_text(json.dumps(aus, ensure_ascii=False, indent=1))
    (ZIEL / "audit.md").write_text("\n".join(md) + "\n")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    print("\n".join(md))


if __name__ == "__main__":
    main()
