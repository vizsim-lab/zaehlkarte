# Nürnberg: Lage der Zählstellen (Werkzeuge, November 2026)

Woher die Lagen im Block `orte:` von `pipeline/config/quellen/kurzzeit/nuernberg.yaml` (auf
`main`) kommen. Die Berichte der Querschnittszählung nennen je Zählstelle nur Nummer und Namen
(„Pirckheimerstraße 78 (östl. Labenwolfstraße)“); die Lage wird daraus und aus den
Zählstellenplänen der Berichte bestimmt. Nicht Teil der Pipeline – das Ergebnis steht fest in der
Quelldatei.

## Eingaben

- **OpenStreetMap** über Overpass, geholt in den Runden `holen23`–`holen30` dieses Branchs
  (`ergebnis/ohne_lizenz/holenNN/geo_nuernberg_*`): Straßen mit Knoten und Geometrie, Orte und
  Landmarken, Bahn, Gewässer, Anschlussstellen, Stadtgrenze (Relation 62780), Sportplätze und die
  Adressen der Straßen, deren Zählstellen eine Hausnummer tragen. ODbL.
- **Die 16 Berichte** (2007–2025) als `bericht_JJJJ.pdf`, wie sie die Pipeline mit Prüfsumme holt
  (`uv run zaehlkarte fetch`); Pfad über `NBG_BERICHTE` (siehe `pfade.py`).

## Ablauf

Python mit shapely, pyproj, numpy, pdfplumber und PyYAML; Zwischenstände in `arbeit/`.

1. `adapter_lesen.py` – aus `pipeline/` eines Checkouts von `main` mit `uv run python …`: liest
   die Berichte mit dem Adapter der Pipeline (Nummern, Namen, Jahre; Nummern der Tabellen
   „Außenkordon“ und „Pegnitzbrücken“).
2. `lauf_geo.py` – je Nummer und Name eine Lage aus OSM nach den Regeln in `geo.py` und `orte.py`:
   Kreuzung mit der genannten Querstraße und 35 m in die genannte Richtung; Hausnummer (auch vor
   der Querstraße – wo beides weit auseinanderliegt, bestätigen die Pläne die Hausnummer, etwa
   11b, 17a, 51, 121, 231), außer bei Bauwerken; Brücke, Tunnel, Bahn- und Autobahnbrücke,
   Stadtgrenze (Außenkordon), Kreisverkehr, Landmarke; „nördl. Ortsteil“ ungefähr; sonst Mitte
   der Straße. Querstraßen mit Tippfehlern über die Ähnlichkeit des Namens
   (`pruefe_querstrassen.py` listet sie zum Durchsehen).
3. `plan.py` – Zählstellenpläne der Berichte 2012 (Seiten 23, 26, 27) und 2022–2025 (Vektorkarten):
   je Etikett der Punkt daneben, in PDF-Koordinaten.
4. `georef.py` – je Plan eine Affintransformation auf UTM über die sicher verorteten Zählstellen
   (Kreuzung, Hausnummer, Brücke …), Ausreißer weg; Median-Rest 28–44 m.
5. `kombiniere.py` – Regel und Plan je Name: Liegt eine sichere Regel nah am Plan (≤ 150 m), gilt
   die Regel; stimmen mindestens zwei Pläne überein, gilt der Plan (auf die Straße gelegt); ein
   einzelner Plan nur, wo die Regel unsicher ist und der Planpunkt an der genannten Straße liegt.
   Einzelne Pläne mit falschem Etikett (rund 10 km daneben: 7, 271, 275, 452) bleiben so draußen.
6. `vereinheitliche.py` – Varianten einer Nummer (Namen in verschiedenen Jahren) teilen sich die
   Lage, wo sie dieselbe Stelle meinen; abweichende Namen derselben Nummer (`GLEICH`: 10d, 12a,
   29/9) bekommen die Lage der übrigen und einen Hinweis.
7. `export_orte.py` – der Block `orte:` (je Nummer eine Lage oder eine Liste mit `wenn`) samt
   Hinweisen zur Genauigkeit; prüft, dass jeder Name die bestimmte Lage bekommt (Auswahl wie im
   Adapter).
8. `ersetze_orte.py <…/nuernberg.yaml>` – ersetzt den Block in der Quelldatei.

Ergebnis (15.11.2026): 533 von 553 Nummern verortet; ohne Lage bleiben Rampen der
Anschlussstellen Königshof und Hafen, Parkplatzausfahrten und einzelne Plätze der Altstadt.
