# AGENTS.md — Quellen finden, prüfen, einbauen

Learnings aus dem Aufbau (November 2026). Ergänzen, wenn etwas Neues auffällt.

## Was gesucht ist
Kurzzeitzählungen der Kommunen mit **Werten je Zählung** – am besten je Intervall (15/60
Minuten) und Richtung, mindestens Tagessummen je Verkehrsart. Nicht gemeint: Dauerzählstellen
(Rad-Zählsäulen, aVME), Verkehrsmengenkarten und DTV-Mittelwerte (dafür `vizsim/svz`).

## Wo suchen
- **Open-Data-Portale der Städte und Länder:** MobiData BW (CKAN, Gruppe
  `verkehrszaehldaten`, Pakete `zaehldaten-*`), opendata.potsdam.de, opendata.ruhr, Open.NRW.
  CKAN-API: `/api/3/action/package_search?q=Verkehrszählung`.
- **FragDenStaat:** rund 200 Anfragen zu „Verkehrszählung“, meist zu einzelnen Straßen. Was
  geliefert wurde, liegt oft als PDF im Anhang. API:
  `https://fragdenstaat.de/api/v1/request/search/?q=Verkehrsz%C3%A4hlung`.
- **Ratsinformationssysteme:** Antworten auf Anfragen nennen Zahl und Format der Zählungen
  (Dresden AF0915/25, München DAVe-Vorlage).
- **Zählsoftware:** München und Wolfsburg nutzen DAVe (Open Source, Export in offene Formate),
  Lübeck die Plattform mytrafficdata (datacollect) – dort lohnt eine Anfrage nach dem Export
  statt nach PDFs.
- **Stadtseiten statt Portale:** Neue Funde (Halle, Chemnitz, Saarbrücken, Mönchengladbach,
  Lübeck, Essen) kamen fast nur über die Suche mit Filter auf die Domain der Stadt, etwa
  „Verkehrszählungen Verkehrsmengen Zählstellen Stadtgebiet“. Begriffe auf Stadtseiten:
  „Bereitstellung von Verkehrsdaten“ (Gera), „Verkehrsmengendaten“ (Halle),
  „Verkehrserhebungen“ (Mönchengladbach, Essen, Saarbrücken), „Verkehrsdaten“ (Kiel). Allgemeine
  Suchen liefern fast nur Gutachten aus Bebauungsplänen. Außer MobiData BW sammelt kein
  Landesportal kommunale Kurzzeitzählungen.

## Formate, die vorkommen
- **Berlin ZDA** (`berlin_zda`): Text, Kopf `schlüssel=wert`, `data=`, je Richtung `; 1 -> 2`
  und Werte je Intervall und Kategorie, `-1` = nicht gezählt. 83 Kategorien-Schreibweisen;
  Zuordnung zu Kfz/SV/Rad/Fuß/Kinder in `adapters/kategorien.py`.
- **MobiData BW** (`mobidata_bw`): Übersichts-Excel (ID, NAME, Lage, bis zu vier Zählungen je
  Stelle als Spaltenblöcke) + ZIP mit Excel und PDF je Zählung. Blatt „Rohdaten“ = lange
  Tabelle (Zeit, Quelle, Ziel, Abbiegeart, Klasse, Volumen). Zeiten mit „CET“/„CEST“.
- **Münster** (`muenster`, XLS und PDF): je Zählung ein Knotenstromplan, zwei Blatthälften = zwei
  Stunden („Spitzenstunde: 07.00 - 08.00 Uhr“). Je Arm Tabellen „S“ (Zufahrt) und „Q“
  (Querschnitt) nach Kfz, Pkw, Bus, Lkw, Lz, Krad, Rad; Knotensumme = Summe der S. Die
  Vorlagen (KNOTEN1–6, 2–4 Arme) liegen verschieden; der Adapter sucht die Beschriftungen
  S/Q und die Kategorie-Namen statt fester Zellen. Prüfung: Summe Q = 2 × Summe S stimmt (auf 2 %
  genau) in 1.379 von 1.382 Blatthälften. Lage: `Zählstellen.csv` (UTM 32N), sonst
  Gauß-Krüger im Blatt.
- **Moers** (`moers_radar`): Seitenradar (Impactor), eine Zeile je Fahrzeug
  `TT.MM.JJ hh:mm:ss;00;Tempo;Länge;Spur`, je Messstelle eine Datei, je Jahr ein Datensatz auf
  offenesdatenportal.de. Die Lage steht nur als Adresse im Namen der Ressource
  („Eupener Straße gegenüber 26“, „Bruchstraße Ecke …“, „Orsoyer Allee an VZ 274“) ->
  `werkzeuge/geokodiere_moers.py` (Nominatim, Overpass für Kreuzungen, Photon bei Tippfehlern).
  Ein Gerät stand auf 2007 statt 2017.
- **Konstanz** (`konstanz_mobil`): je Standort eine CSV (`;`, BOM), Spaltennamen je Datei anders
  („Fahrradfahrer inkl. Lastenraeder (stadteinwaerts)“, „Stadteinwaerts_PKW“,
  „Fussgaenger-Ri-Schweiz“) – Verkehrsart aus dem Namen, Summen und „Andere“ weg. Zwei
  Gerätearten: 15 Minuten auf vollen Viertelstunden (Beginn des Intervalls) und 5-Minuten-
  Protokolle mit Sekunden. Die Protokolle schreiben jede Zeile 2–25 s nach dem Ende ihres
  Intervalls (kein Weglaufen der Uhr über Wochen), die erste Zeile nach dem Einschalten ist
  leer (Gartenstraße 16:35: 0 statt sonst 8–16) -> runden, als Ende nehmen. Doppelte Zeilen mit
  gleichen Werten oder einer leeren Hälfte; Mitternachtszeilen fehlen in der Jakobstraße ab dem
  dritten Tag. Die URLs tragen den Upload-Zähler des Portals (`_2.csv`) – Kennungen ohne ihn.
- **Münster PDF** (`muenster_pdf`): Ausdrucke derselben Excel-Vorlagen. Senkrechte Tabellen
  stehen gedreht im PDF – pdfplumber liest sie rückwärts („zfK“, „0301“), solange man die
  Zeichen nicht je Drehrichtung mit `char_dir_rotated="btt"` bzw. `"ttb"` zusammensetzt.
  Spalten über die Tabellenrahmen (dünne Rechtecke), nicht über Textmitten: Beschriftungen
  stehen linksbündig, Zahlen rechtsbündig. 2017 gibt es eine Vorlage nur mit Kfz, Pkw, SV;
  Radar-Berichte („Class/Volume Report“, 48 h, ohne Knotennummer) und Scans liest der
  Adapter nicht.
- **Potsdam** (`potsdam_pdf`): je Zählung ein Zählplan „FAHRZEUG-VERTEILUNG“ (PDF aus der
  Excel-Vorlage „StromPlan“), Knotenliste mit Lage über die Opendatasoft-API. Tabelle je
  Verkehrsart (RAD, NFZ, SV, KFZ, FZ) mit den Zeilen FSp, NSp, 6h und je Zufahrt einer Spalte plus
  SUMME. Spalten über die Lage der Wörter: neben der Tabelle stehen Zahlen des Stromplans, in
  manchen Plänen fehlt eine Zufahrtsspalte im Text, Zufahrten heißen auch „NG“, „SG“. Kontrolle:
  die Kfz-Werte der Tabelle stimmen in allen Plänen mit „[FSp] : 1644 KFZ/h“ und „6h : 9544 KFZ“
  im Text überein. Beginn der Spitzenstunde aus „Sph-Beginn: 7.30 Uhr und 15.30 Uhr“ – die Uhrzeit
  hinter „KFZ/h“ ist meist die Mitte, in einigen Vorlagen der Beginn. Oben steht das Druckdatum,
  das Zähldatum kommt nach „DATUM“. „6h“ ohne Zeitangabe = 7–10 und 15–18 Uhr (potsdam.de).
  Werte mit Nachkommastellen sind errechnet (Plan nicht übernommen), „nurRad“-Pläne haben Kfz 0
  (= nicht gezählt), „_Qw“/„_Qs“/„_Qbr“ sind Querschnitte am Knoten, „KordonZ“ ein 24-Stunden-
  Tagesgang ohne Tagesdatum (nicht übernommen).
- **Xanten** (`xanten_pdf`): zwei PDFs eines Planungsbüros („Gesamtübersicht Zähldaten“, Knoten
  und Querschnitte) mit Viertelstunden je Strom und Fahrzeugart; Text mit pdfplumber, je Zeile
  Dezimalstunde („7,25“ = 7:15), Art und Ströme, die Zeile „Summe“ prüft die Viertelstunde
  (alle 816 stimmen). Lage: die Karte im Bericht ist ein Rasterbild – Marker über die Farbe
  gefunden, über die zwölf Knotenpunkte (OSM) affin auf Koordinaten umgerechnet (Restfehler
  4–19 m). An Kreisverkehren haben die Straßen in OSM keinen gemeinsamen Knoten.
- **PDF je Knoten** (Magdeburg-Angebot): noch kein Adapter (Ansatz wie `potsdam_pdf` bzw.
  `muenster_pdf`).
- **MobiData BW `KFZ_n` = nur Pkw.** Nachgerechnet an allen 174 Zählungen mit Excel:
  `KFZ_n` = Klasse PKW, `SV_n` = Klasse LKW (Ravensburg 1000, 16.11.2023: 14.217 + 1.919 =
  16.136 Kfz). Wer die Übersicht allein nutzt (wie `vizsim/svz`), unterschätzt Kfz um den
  Lkw-Anteil (rund 12 %).
- **Berlin vergibt Zählstellen-Kennungen neu.** Dieselbe Kennung kann Jahrzehnte später an
  einem anderen Ort liegen -> Stellen nach Lage trennen („K10921-2“), Lage nur übertragen,
  wenn alle verorteten Zählungen der Kennung an einem Ort liegen.
- **Dieselbe Berliner Zählung steckt in beiden Lieferungen (2019)**, teils mit anderen Werten
  -> die neuere Lieferung gilt; „X“ und „X_24h“ -> nur die 24-Stunden-Fassung.
- **Angebrochene Stunden** (Zählfenster ab 6:30) sind keine kleine Stunde, sondern keine:
  die Pipeline lässt sie weg.
- **Fußgänger bei Videozählungen** = Querungen an den ausgewerteten Überwegen, nicht alle
  Fußwege der Kreuzung.
- **Ferien:** bewegliche Ferientage legen die Schulen selbst fest (BW: 3–5 je Schuljahr) –
  ein „Schultag“ kann vor Ort frei gewesen sein. Die KMK-Kalender ab 1999/2000 stehen im
  Archiv auf kmk.org (`Ferien99_00.pdf` … `FER19_20.pdf`); `pdftotext -layout` und die
  Spaltenköpfe (Herbst, Weihnachten, …) reichen zum Auslesen.
- **Münster:** Formelfehler in den Zählblättern lassen Ströme aus – mal in der Kfz-Zelle
  (Kfz 26 bei 315 Pkw), mal in den Fahrzeugarten (S-Zeile ohne den zweiten Strom) -> je Arm
  den größeren der beiden Werte. Leere Vorlagen stehen auf 0 -> eine Stunde mit
  lauter Null-Kfz gilt als nicht gezählt. Einige Dateien tragen fremde Blätter (ein Blatt
  „Radverkehr“ vom Neutor 2007 in einer Datei von 2012) -> nur Blätter vom selben Zähltag.
  Datum: Dateiname und Excel-Datum im Blatt widersprechen sich in rund 20 Dateien (Tippfehler,
  31.04., Sonntagszählungen unter dem Datum des Mittwochs davor) – Regel im Adapter-Kopf.
- **Lizenzangaben bei GovData können falsch sein:** Münster steht dort mit
  „other-closed“, das Portal der Stadt (Datensatzseite, API, Nutzungsbedingungen) nennt
  dl-de/by-2-0. Konstanz: Portal der Stadt CC0 1.0, MobiData BW CC BY 4.0. Immer beim Portal
  der Kommune nachsehen.
- **Potsdam: eigene Nutzungsbedingungen (NB-16-OGD)** statt einer Standardlizenz – Weiterverwendung
  samt Veränderung erlaubt, Pflicht: „Name © LHP/NB-16-OGD/Datum der Entnahme“, Hinweis auf
  Veränderung und darauf, dass Dritte nur nach diesen Bedingungen weiterverwenden dürfen. Die
  Karte setzt das in `titel`/`lizenz` der Quelle um; das Datum schreibt `fetch` (`abruf.txt`).
- **Ein Gerät kann wochenlang zu wenig zählen, ohne dass die Datei es sagt:** Z-Brücke Konstanz
  ab 3. Oktober 2020 unter einem Zehntel der Tage davor. Die Karte zeigt die Werte und einen
  Hinweis (`hinweise_zeitraum` in sources.yaml), sortiert nichts aus.

## Sackgassen
- mobidata-bw.de, GovData, opendata.potsdam.de (auch de.ftp.opendatasoft.com),
  opendata.stadt-muenster.de, offenedaten-konstanz.de, fragdenstaat.de und kmk.org sind aus
  manchen Entwicklungsumgebungen nicht erreichbar (Proxy). Abruf dann über GitHub Actions
  (`zaehlkarte fetch` im Workflow „Kartendaten neu bauen“). Braucht man die Rohdateien selbst in
  der Sandbox: ein Werkzeug-Workflow auf einem eigenen Branch legt sie dort ab (Muster: Commit
  e6f7280, `tools/mobidata_holen.py`), dann `git fetch`.
- Die Nutzungsbedingungen der LHP (Potsdam) stehen erst nach JavaScript auf der Seite – lesen mit
  Playwright; die Opendatasoft-API und die CKAN-APIs von GovData und Open.NRW sperren
  Abruf-Werkzeuge per robots.txt (die Websuche mit Filter auf govdata.de/open.nrw geht).
  FragDenStaat: die Links „/anhang/…“ liefern eine HTML-Seite, die Datei liegt unter
  media.frag-den-staat.de/files/foi/<Nachricht>/<Name>.
- Nicht abrufbar (Stand November 2026): wuppertal.de (Dienstleistung „Verkehrsbelastung“
  104.51 – lohnt einen zweiten Blick), bau.bremen.de, mobil.osnabrueck.de; datenhub.ulm.de
  braucht JavaScript.
- Geprüft ohne verwertbaren Fund (Stadtseite, Portal, FragDenStaat; November 2026 – eine Anfrage
  nach der Vorlage geht trotzdem überall): Karlsruhe (Zählwerte nur in Gutachten im
  Ratsinformationssystem), Mannheim, Freiburg, Ulm, Tübingen, Heilbronn, Pforzheim, Reutlingen,
  Augsburg, Regensburg, Ingolstadt, Erlangen, Würzburg, Cottbus, Bremen, Wiesbaden, Darmstadt,
  Offenbach, Schwerin, Greifswald, Hannover, Braunschweig, Oldenburg, Lüneburg, Duisburg,
  Bochum, Bielefeld, Bonn, Krefeld, Oberhausen, Siegen, Mainz, Ludwigshafen, Koblenz, Trier,
  Kaiserslautern, Worms, Flensburg, Erfurt, Jena – meist nur Rad- oder Dauerzähler offen.
- Leipzig 2023: Ablehnung, weil die Karte keinen Export hat – nicht nach „den Daten der
  Karte“ fragen, sondern nach den gelieferten Zählauswertungen der Büros.
- Dortmund gibt Werte nur gegen Gebühr heraus; offen ist nur der Zählstellenplan.
- Rostock 2020 (FragDenStaat „Verkehrszählung“): die „Übersichten“ sind ein Register, welcher
  Knoten wann gezählt wurde (2009–2019), ohne Werte; Werte nur in drei Beispielzählungen
  (`Z_xxxx`, Viertelstunden je Strom) und ohne Lizenzangabe – daher nicht in der Karte. Die Stadt
  gibt auf genaue Anfrage bis 50 Zählungen kostenlos als Excel heraus.

## Rechtliches (Stand 2026, keine Rechtsberatung)
Bayern und Niedersachsen haben kein Landes-IFG; in Sachsen und Hessen gilt es für Kommunen
nur per Satzung. Das UIG gilt überall – Zählungen gehen in die Lärmkartierung ein, darum mit
anführen. Sachsen: LfULG-Handlungsempfehlung (Mai 2026) verlangt Intervallwerte als CSV/XLSX
von beauftragten Büros. Kurzfassung je Land: `recht:` in `pipeline/config/sources.yaml`
(RP LTranspG, SH IZG-SH, SL SIFG, TH ThürTG gelten auch für Gemeinden; Belege dort).

Neue Gesetze ändern daran nichts (Stand November 2026): Das IVSG 2026 (Mobilithek) meint
Sperrungen, Baustellen, Belegungs- und Ladedaten, keine Verkehrsmengen; die EU-Verordnung 2022/670
verlangt nur, was schon digital vorliegt (Detektoren, Dauerzählstellen); das Datennutzungsgesetz
schafft keinen Anspruch, § 7 ist aber ein Argument für Excel/CSV statt PDF. Einziger Hebel zum
Einsammeln: das Landesmobilitätsgesetz Baden-Württemberg (Datenbereitstellungspflichten, Verordnung
noch offen). Belege: [IVSG](https://www.gesetze-im-internet.de/ivsg_2026/BJNR0940B0026.html),
[VO 2022/670, Erwägungsgrund 19](https://gesetze.legal/eu/vo_eu_2022_670/praeambel),
[DNG](https://www.gesetze-im-internet.de/dng/BJNR294200021.html),
[MobiData BW Factsheet](https://mobidata-bw.de/data/MobiData-BW-Factsheet-Datenbereitstellungspflichten.pdf).
