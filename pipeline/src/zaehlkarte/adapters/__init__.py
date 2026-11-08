"""Adapter: je Quellformat ein Modul mit `lese(quelle, pfade, bericht)` und `Bericht`.

sources.yaml wählt den Adapter per `adapter:`; mehrere Quellen dürfen denselben nutzen
(MobiData BW: fünf Kommunen, ein Format)."""

from zaehlkarte.adapters import berlin_zda, mobidata_bw, muenster

ADAPTER = {"berlin_zda": berlin_zda, "mobidata_bw": mobidata_bw, "muenster": muenster}
