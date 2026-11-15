# Kevelaer: Lage der Zählstellen (Werkzeug, November 2026)

Woher der Block `orte:` in `pipeline/config/quellen/kurzzeit/kevelaer.yaml` (auf `main`) kommt.
Der Bericht „Ergebnisse der Verkehrszählungen 2019“ nennt je Knotenpunkt die Straßen der Arme, je
Querschnitt eine Straße – keine Koordinaten. Nicht Teil der Pipeline; das Ergebnis steht fest in
der Quelldatei. Die Zählwerte selbst liest der Adapter `kevelaer_pdf` auf `main` (Bildseiten:
`pipeline/werkzeuge/abschrift_kevelaer.py`).

## Eingaben (Runde `holen31` dieses Branchs)

- `ergebnis/ohne_lizenz/holen31/geo_kevelaer_strassen/16_interpreter.json`: Straßen im Kernort
  aus OpenStreetMap (Overpass, `out body geom`), ODbL.
- `ergebnis/ohne_lizenz/holen31/kevelaer_seite_de/10_zwischenbericht.pdf`: Zwischenbericht zur
  Verkehrsuntersuchung, Seite 38 = Zählstellenplan (Abb. 2.3.1.2-2, Rasterbild): blaue Punkte =
  Knotenpunkte, rote Balken = Querschnitte, daneben die Nummern.

## Ablauf

`python -I tools/kevelaer/lage.py` (numpy, pillow, pyproj; pdfimages aus poppler-utils), aus der
Wurzel des Branchs. Gibt den Block `orte:` aus, schreibt `arbeit/lage.json` und
`arbeit/kontrolle.png` (nicht im Git – der Plan gehört der Stadt).

1. Knotenpunkte: Knoten, die Wege der genannten Straßen teilen; stoßen die Straßen an einen
   Kreisverkehr (K1, K2 „Europa-Kreisel“, K15), dessen Mitte. Namen wie in OSM: „Wellener
   Landstraße L491“ des Berichts = Weller Landstraße (L 491), „Geldener Straße“ = Gelderner
   Straße, „Weller Landstraße L261“ (Kopf von K7, K8) = L 361 wie die Arme derselben Seite.
2. Plan: Punkte und Balken nach Farbe, je Nummer der nächste zur ungefähren Lage (Pixel im Kopf
   des Skripts). Affin über die Knotenpunkte, an denen sich alle Arme an einer Stelle treffen
   (13 Passpunkte), Rest 1–12 m; die übrigen (K3, K11, K16) liegen 2–5 m neben dem Plan.
3. Querschnitte: Balkenmitte umgerechnet und auf die genannte Straße gelegt (0–5 m entfernt).

Kontrolle: `arbeit/kontrolle.png` zeigt die OSM-Straßen (grün) über dem Plan – sie decken sich –
und die Ergebnisse (magenta) auf den Punkten und Balken.
