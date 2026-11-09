"""Adapter: je Quellformat ein Modul mit `lese(quelle, pfade, bericht)` und `Bericht`.

sources.yaml wählt den Adapter per `adapter:`; mehrere Quellen dürfen denselben nutzen
(MobiData BW: fünf Kommunen, ein Format)."""

from zaehlkarte.adapters import (
    berlin_zda,
    konstanz_mobil,
    mobidata_bw,
    moers_radar,
    muenster,
    olpe_radar,
    potsdam_pdf,
    xanten_pdf,
)

ADAPTER = {
    "berlin_zda": berlin_zda,
    "mobidata_bw": mobidata_bw,
    "muenster": muenster,
    "moers_radar": moers_radar,
    "olpe_radar": olpe_radar,
    "konstanz_mobil": konstanz_mobil,
    "potsdam_pdf": potsdam_pdf,
    "xanten_pdf": xanten_pdf,
}
