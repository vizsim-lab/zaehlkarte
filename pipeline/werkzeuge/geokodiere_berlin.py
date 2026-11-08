"""Berliner Zählungen ohne Lage geokodieren – mit dem Geocoder aus
vizsim/berlin-traffic-counts_schulwege (Straßenkreuzungen aus OpenStreetMap).

Läuft in DESSEN Umgebung (Workflow „Berlin geokodieren“):
    cd schulwege/pipeline && uv run python geokodiere_berlin.py LISTE PBF PLZ_GPKG ZIEL

LISTE  von `zaehlkarte geokodier-liste` (datei, bez, name, arme mit | getrennt, plz, ortsteil)
PBF    OSM-Abzug Berlin (Geofabrik berlin-latest.osm.pbf)
ZIEL   pipeline/geokodierung/berlin_ergaenzung.csv – gleiche Spalten wie der Schulwege-Cache;
       Zeilen ohne Treffer bleiben leer stehen (nachvollziehbar, was versucht wurde).
"""

import sys
from pathlib import Path

import pandas as pd
from schulwege import geocode as g


def main(liste: str, pbf: str, plz: str, ziel: str) -> None:
    df = pd.read_csv(liste, dtype=str, keep_default_na=False)
    df["arme"] = df["arme"].map(lambda s: [a for a in s.split("|") if a])
    netz = g.Strassennetz.aus_pbf(Path(pbf))
    gebiete = g.Gebiete.lade(Path(plz), Path(pbf))
    geo = g.verorte_tabelle(df, netz, gebiete)
    geo = geo.sort_values("datei")
    for spalte in ("geo_lon", "geo_lat"):
        geo[spalte] = geo[spalte].map(lambda v: "" if pd.isna(v) else f"{v:.6f}")
    geo.to_csv(ziel, index=False)
    print(f"{geo['geo_methode'].notna().sum()} von {len(geo)} verortet -> {ziel}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
