# AGENTS.md — Quellen finden, prüfen, einbauen

Learnings aus dem Aufbau (November 2026). Ergänzen, wenn etwas Neues auffällt.

## Was gesucht ist
Zwei Familien, beide mit gezählten Werten im Zeitverlauf:
- **Kurzzeitzählungen** der Kommunen mit **Werten je Zählung** – am besten je Intervall (15/60
  Minuten) und Richtung, mindestens Tagessummen je Verkehrsart.
- **Dauerzählstellen** der Kommunen (fest eingebaute Detektoren, Kameras) mit Stunden- oder
  Tageswerten über Monate und Jahre – Abschnitt `dauer:` in sources.yaml, Code in
  `src/zaehlkarte/dauer/`.

Nicht gemeint: Jahresmittel (DTV/DTVw), Verkehrsmengenkarten und Modellwerte – dafür
`vizsim/svz`. Prüffrage: Ein Wert je Stelle und Jahr → svz; Werte je Intervall oder Tag →
hier; beides → jedes Repo seinen Teil (Hamburg: DTV-Tabelle svz, Detektor-Stunden hier).
Klassische Rad-Zählsäulen (Eco-Counter u. a.) sind vorerst nicht dabei; Stundenwerte der BASt
auch nicht (nicht kommunal).

## Wo suchen
- **Open-Data-Portale der Städte und Länder:** MobiData BW (CKAN, Gruppe
  `verkehrszaehldaten`, Pakete `zaehldaten-*`), opendata.potsdam.de, opendata.ruhr, Open.NRW.
  CKAN-API: `/api/3/action/package_search?q=Verkehrszählung`. Für Baden-Württemberg reicht
  GovData mit `fq=organization:open-data-baden-wurttemberg` (= daten.bw, sammelt Freiburg,
  Mannheim, Heilbronn, Konstanz, Stuttgart und das Portal re@di der Städte der TechnologieRegion
  Karlsruhe, `opendata.readi.de`).
- **GovData je Land sortieren:** Die Pakete tragen den Regionalschlüssel
  (`extras.politicalGeocodingURI`, `…/regionalKey/<Land, 2 Ziffern>…`). Die Suche nach
  „Verkehrszählung“/„Zählstelle“/„DTV“ füllt sich mit den Zählstellen der Landes- und
  Bundesstraßen (Bayern und Schleswig-Holstein: ein Paket je Zählstelle und Jahr) – ausblenden mit
  `fq=-organization:open-data-bayern AND -organization:land-schleswig-holstein`. Rundgang
  November 2026 (Werkzeug `tools/laender.py` auf dem Branch `werkzeug/erkundung`): kommunale
  Kurzzeitzählungen nur Moers, Münster, Xanten, Konstanz, Ravensburg & Co., Potsdam – und neu
  Olpe; sonst Rad- und Dauerzähler, DTV-Karten, Lärmkartierung.
- **FragDenStaat:** rund 200 Anfragen zu „Verkehrszählung“, meist zu einzelnen Straßen. Was
  geliefert wurde, liegt oft als PDF im Anhang; die Antworten verraten, wie eine Stadt zählt und
  was sie herausgibt (Kassel: Excel mit 15-Minuten-Werten, Osnabrück: Radar-Textdateien,
  Bremen: Liste plus 5 Euro je Zählstelle und Tag). Die Anhänge samt Antworttexten holt
  `tools/laender.py` über `/api/v1/request/<id>/` (Feld `messages[].attachments`). API:
  `https://fragdenstaat.de/api/v1/request/search/?q=Verkehrsz%C3%A4hlung` (Volltext: „Verkehrszählung
  Freiburg“ liefert 67 Treffer, keiner zu Freiburg – nach Behörde filtern; `/api/v1/request/?q=`
  ignoriert `q`). Behörden samt Funktionsadresse: `/api/v1/publicbody/?q=Stadt Freiburg`.
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
- **Olpe** (`olpe_radar`): je Messung eine JSON-Datei, zwei Formate. Geräte-Export
  (`header`, `request` mit Exportfenster, `data[].vehicle_data[]` mit `date`, `direction`,
  `code`, `length` in dm, `v1`) – Zeiten in UTC, teils mit „Z“ und Millisekunden; dazu
  `measurement_data[]` = ein GPS-Punkt je Tag, auch für Tage nach dem Export (das Gerät stand da
  schon an der nächsten Stelle: Günsestraße 26 zeigt sonst auf Oberveischede). Tabelle (CSV/JSON
  mit deutschen Spalten „Datum“, „Klasse“, „Fahrzeugklassen-Bezeichnung“) in Ortszeit ohne Lage.
  Klassen-Codes (aus der Tabelle): 2 PkwA, 3 Lkw, 5 Bus, 7 Pkw, 8 LkwA, 9 Sattel-Kfz, 10 Krad,
  11 Lfw, 230 Radfahrer; 6 und 250 ohne Namen (Länge ≈ 4,2 m, Tempo ≈ 50 km/h -> Kfz). Die
  Geräte fallen zeitweise aus (Hatzenbergstraße: 23 Stunden ohne Fahrzeug) -> Lücken über das
  erwartete Aufkommen erkennen, nicht über feste Uhrzeiten (ruhige Straßen sind sonntags früh
  wirklich leer).
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
- **Miovision-Excel** („Tabellenbericht“: Blatt „Übersicht“ mit Studienname, Zeitintervall,
  Zeitzone, Breiten-/Längengrad, je Klasse ein Blatt, Blatt „Rohdaten“): dasselbe Format wie die
  Excel-Dateien von MobiData BW – Kassel hat 2021 so geliefert (FragDenStaat); `mobidata_bw`
  liest das Blatt „Rohdaten“.
- **Seitenradar als Text, eine Zeile je Fahrzeug** (Osnabrück 2021 auf Anfrage: km/h, Uhrzeit,
  Datum, Richtung 1/2, Länge): wie Moers; ohne Lizenzangabe nicht in der Karte.
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
  e6f7280, `tools/mobidata_holen.py` auf dem Branch `werkzeug/mobidata`), dann `git fetch`.
- Die Nutzungsbedingungen der LHP (Potsdam) stehen erst nach JavaScript auf der Seite – lesen mit
  Playwright; die Opendatasoft-API und die CKAN-APIs von GovData und Open.NRW sperren
  Abruf-Werkzeuge per robots.txt (die Websuche mit Filter auf govdata.de/open.nrw geht).
  FragDenStaat: die Links „/anhang/…“ liefern eine HTML-Seite, die Datei liegt unter
  media.frag-den-staat.de/files/foi/<Nachricht>/<Name>.
- Nicht abrufbar (Stand November 2026): mobil.osnabrueck.de; wuppertal.de nur mit Playwright
  (`tools/laender2.py` auf `werkzeug/erkundung`), bau.bremen.de nur über das Abruf-Werkzeug. Der Datenhub Ulm
  braucht im Browser JavaScript, seine CKAN-API (`datenhub.ulm.de/ckan/api/3/action/…`) geht.
  Die Mobilithek-Suche wertet `searchString` ohne JavaScript nicht aus (GovData führt ihre
  Angebote als Organisation `mcloud`). Open.NRW (`ckan.open.nrw.de`) lief aus GitHub Actions in
  Zeitüberschreitungen; GovData spiegelt es (Organisation `open-nrw`).
- Baden-Württemberg (November 2026, GovData/daten.bw, re@di, Stadtportale, FragDenStaat): offene
  Kurzzeitzählungen nur bei MobiData BW (Ravensburg und Umland) und in Konstanz. Sonst sind nur
  Dauerzählungen offen – Freiburg (Rad-Zählstellen; 25 Sensoren im Testbetrieb, der WFS
  `digit_verkehrszaehl` zeigt nur drei Standorte vom Mai 2024; Stadtradeln = GPS-Spuren, keine
  Zählung), Ettlingen (Sensoren, CC BY-NC 4.0; im Datastore stehen alte Kennungen 46–54 ohne
  Richtung neben UrbanPulse-Strömen je Spur ab August 2026), Ulm (Kameras „vgv_ulm“, eine Zeile
  je Verkehrsteilnehmer, Standorte nur als Kürzel), Mannheim (Eco-Counter), Heidelberg
  (Kameras). Die Geschwindigkeitsdisplays in Konstanz taugen laut Stadt nicht für
  Verkehrsmengen; Heilbronn hat nur Kfz-Bestand und Fahrleistung (Statistisches Landesamt);
  Aalen zählt mit eigenem Seitenradar, veröffentlicht aber nichts. Karlsruhe hat 2023 Zählungen
  eines Verkehrsversuchs als Excel herausgegeben (FragDenStaat) – alles in der Datenlage.
- Übrige Länder (November 2026, GovData je Land, Landes- und Stadtportale, alle
  FragDenStaat-Anfragen samt Anhängen, Stadtseiten): neu offen nur Olpe (in der Karte). Neu in der
  Datenlage: Bremen, Augsburg, Amberg, Wuppertal, Falkensee, Lingen (Ems); präzisiert: Kassel
  (Excel geliefert), Osnabrück (Radar-Textdateien geliefert), Düsseldorf, Hamburg
  (Leistungsverzeichnis: 15-Minuten-Werte in der Zähldatenbank).
  - Brandenburg: Das Landesamt für Umwelt lässt für die Lärmkartierung selbst zählen – 2023 in
    mehreren Städten Knotenpunkte von 6 bis 19 Uhr (Bericht „Datengrundlagen zur
    Immissionsberechnung 2023“, mindestens 20 Messpunkte). Auf eine Anfrage
    ([FragDenStaat 2023](https://fragdenstaat.de/anfrage/verkehrszaehlungen-im-stadtgebiet-brandenburg-an-der-havel/))
    kam nur der Auszug für Brandenburg an der Havel (DTV und Stundenmittel nach RLS-19, keine
    Zählwerte). Eine Anfrage beim LfU nach den gezählten Werten aller Messpunkte könnte mehrere
    Städte auf einmal bringen.
  - Kleine Gemeinden geben Messungen ihrer Geschwindigkeitsanzeigen und Radargeräte auf Anfrage
    meist heraus, fast immer als PDF-Bericht (Delbrück, Hatzenbühl, Marpingen, Merzig,
    Nieder-Olm, Karben, Michendorf) – kein Bestand, aber ein Zeichen, wo es Geräte gibt.
  - Nur Einzelwerte statt Zählungen: Hannover 2020 (ein Querschnittswert), Siegen 2024 (DTV aus
    Geschwindigkeitsmessungen), Dessau-Roßlau 2025 (DTV eines Statistikgeräts). Bonn misst per
    Bluetooth nur Reisezeiten. Nürnberg verweigert Daten der kommunalen Verkehrsüberwachung
    („einsatztaktische Gründe“), Dresden nennt 2025 seine automatischen Zählstellen mit Kosten.
- Geprüft ohne verwertbaren Fund (Stadtseite, Portal, FragDenStaat; November 2026 – eine Anfrage
  nach der Vorlage geht trotzdem überall): Mannheim, Tübingen, Heilbronn, Pforzheim, Reutlingen,
  Regensburg, Ingolstadt, Erlangen, Würzburg, Fürth, Cottbus, Wiesbaden, Darmstadt, Offenbach,
  Hanau, Schwerin, Greifswald, Hannover, Braunschweig, Oldenburg, Lüneburg, Hildesheim,
  Salzgitter, Duisburg, Bochum, Bielefeld, Bonn, Krefeld, Oberhausen, Siegen, Gelsenkirchen,
  Aachen, Hagen, Hamm, Mülheim, Leverkusen, Solingen, Herne, Neuss, Bottrop, Recklinghausen,
  Bergisch Gladbach, Remscheid, Gütersloh, Mainz, Ludwigshafen, Koblenz, Trier, Kaiserslautern,
  Worms, Flensburg, Neumünster, Norderstedt, Erfurt, Jena, Weimar, Zwickau, Dessau-Roßlau – meist
  nur Rad- oder Dauerzähler offen, sonst Zählwerte nur in Gutachten aus Bebauungsplänen.
- Leipzig 2023: Ablehnung, weil die Karte keinen Export hat – nicht nach „den Daten der
  Karte“ fragen, sondern nach den gelieferten Zählauswertungen der Büros.
- Dortmund gibt Werte nur gegen Gebühr heraus; offen ist nur der Zählstellenplan.
- Rostock 2020 (FragDenStaat „Verkehrszählung“): die „Übersichten“ sind ein Register, welcher
  Knoten wann gezählt wurde (2009–2019), ohne Werte; Werte nur in drei Beispielzählungen
  (`Z_xxxx`, Viertelstunden je Strom) und ohne Lizenzangabe – daher nicht in der Karte. Die Stadt
  gibt auf genaue Anfrage bis 50 Zählungen kostenlos als Excel heraus.

## Rechtliches (Stand 2026, keine Rechtsberatung)
Bayern und Niedersachsen haben kein Landes-IFG (Niedersachsen: Entwurf eines
Transparenzgesetzes liegt laut Justizministerin im Ministerium, im Landtag noch nicht –
[Drucksache 19/11074, Juni 2026](https://www.landtag-niedersachsen.de/drucksachen/drucksachen_19_12500/11001-11500/19-11074.pdf));
manche Städte haben eine Informationsfreiheitssatzung (Osnabrück, Lingen, Göttingen – so
genannt in ihren Antworten auf FragDenStaat). In Sachsen und Hessen gilt das Landesgesetz für
Kommunen nur per Satzung. Berlin hat das IFG im April 2026 um eine Ausnahme für Einrichtungen
der kritischen Infrastruktur ergänzt (§ 2 Abs. 3,
[GVBl. 2026 S. 158](https://pardok.parlament-berlin.de/starweb/adis/citat/VT/19/gvbl/g26110158.pdf));
Verkehrszählungen nennt sie nicht. Brandenburg bereitet eine ähnliche Änderung des AIG vor
([netzpolitik.org, Juli 2026](https://netzpolitik.org/?p=526375)); in Mecklenburg-Vorpommern,
Thüringen und Schleswig-Holstein gibt es Pläne, die Informationsfreiheit einzuschränken (etwa
Anfragen nur mit Wohnsitz im Land) – vor Anfragen dort den Stand prüfen
([heise, 2026](https://heise.de/-11242410)). Das UIG gilt überall – Zählungen gehen in die Lärmkartierung ein, darum mit
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

## Dauerzählstellen (November 2026)

- **Berlin (in der Karte, `berlin_viz`):** öffentlicher Azure-Container
  `https://mdhopendata.blob.core.windows.net/verkehrsdetektion`, Liste per
  `?restype=container&comp=list` (Content-MD5 je Datei; `fetch` lädt nur Geändertes). Aus
  manchen Entwicklungsumgebungen nicht erreichbar → Workflow. Fallen: drei Formate der neuen
  QS (CSV oder CSV.GZ im TGZ, „qkfz“/„kfz“, Vollständigkeit in Prozent oder als Anteil,
  Stunde „7“ oder „07“), je Stunde oft eine NaN-Zeile neben der gültigen; die Stammdaten
  (Juli 2022) kennen die neuen Messquerschnitte „…n“ nicht; das ReadMe beschreibt eine andere
  Stammdaten-Datei (Blätter DET/MQ, Gauß-Krüger) als die im Archiv (ein Blatt, WGS84).
- **Hamburg (in der Karte, `hamburg_kfz`, `hamburg_rad`, Adapter `hamburg_sta`):** SensorThings
  `https://iot.hamburg.de/v1.1`, Dienste `HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren` (829
  Zählstellen Kfz, 341 davon auch Schwerverkehr – an denselben Things) und
  `HH_STA_Verkehrsdaten_Rad_Infrarotdetektoren` (312); Layer je Zählstelle 5-Min, 15-Min,
  1-Stunde, 1-Tag, 1-Woche. Datastreams per `properties/serviceName` und `properties/layerName`
  filtern (die Things tragen den Dienst nicht). Fallen:
  - **Rückreichweite:** laut Datensatzbeschreibung im Transparenzportal Stundenwerte nur „für die
    letzten zwei Monate“ (beobachtet: Kfz und Rad ab 29.08.2026, Schwerverkehr ab 28.02.2026),
    Tageswerte das laufende und das letzte Jahr, Wochenwerte seit Beginn. Die Vollständigkeit
    eines Tags lässt sich nur an Stunden prüfen → die Zählkarte hebt die Stunden selbst auf
    (Gedächtnis, Monatsdateien im Release `dauerzaehlstellen`, `pipeline/werkzeuge/gedaechtnis.py`).
  - Ganze Tage fehlen bei allen Stellen zugleich (Ausfälle der Plattform); Werte können sich
    noch nach ein paar Tagen ändern → jeder Lauf holt 14 Tage erneut, in die Karte kommen nur
    Stunden, die sieben Tage alt sind.
  - UTC (laut Quelle). Die Rückstellung legt zwei UTC-Stunden auf 2 Uhr Ortszeit.
  - Keine Straßennamen, nur Kennung (`assetID` = Knotenpunkt, 9, Arm, Richtung) und Punkt →
    nächste benannte Straße aus dem Geofabrik-Abzug (OSM, ODbL), Kreuzungsname aus den
    übrigen Armen desselben Knotenpunkts.
  - Verschachteltes `$expand=Observations(…;$filter=phenomenonTime ge …;$top=10000)` über eine
    Seite Datastreams spart Abfragen; `$top` bis 20.000 geht.
  - Die alten Dienste `HH_STA_AutomatisierteVerkehrsmengenerfassung` und
    `HH_STA_HamburgerRadzaehlnetz` heißen „(veraltet)“, Tageswerte bis März 2026, Stundenwerte
    nur noch bei 5 Datastreams (2021–2023) – keine Hamburger Historie aus Stunden.
  - Lizenz dl-de/by-2-0 (beide Datensätze im Transparenzportal), Genauigkeit laut Quelle Kfz
    ±10 %, Schwerverkehrsanteil ±15 %, Rad ±10–20 %.
- **Geprüft, nicht aufgenommen (Stand 12.11.2026,** Werkzeug-Branch `werkzeug/dauer`,
  `tools/dauer_staedte1.py`, `dauer_staedte2.py`):
  - **Osnabrück:** SensorThings `https://daten-api.osnabrueck.de/v1.1` mit KI-Sensoren an
    rund zehn Kreuzungen (Things „Verkehrszaehlung …“ je Fahrstreifen bzw. Abbiegestrom; PKWs,
    LKWs, Busse, Motorräder, Fahrräder, Personen; 15-Minuten-Werte seit 2023, Zeitstempel
    unregelmäßig zum Zeitpunkt der Übertragung). Keine Lizenzangabe (GovData-Eintrag ohne
    Lizenz) → erst nach Klärung; die Stunden müssten aus 15-Minuten-Meldungen ohne festes
    Raster gebildet werden.
  - **Ulm** (`vgv_ulm`, CKAN-Datastore `datenhub.ulm.de`): eine Zeile je erkanntem
    Verkehrsteilnehmer (Zeit, Klasse, Kamera-Kürzel, Richtung), Millionen Zeilen. Keine
    Standorte, und ohne Betriebszeiten ist eine Stunde ohne Zeile nicht von einem Ausfall zu
    unterscheiden → nicht aufnehmbar.
  - **Heidelberg:** Kameradaten (TrafficFlowObserved, CC0) im CKAN der Datenplattform, aber die
    CKAN-API antwortet mit 404 (Metadaten zuletzt 2023); die Verkehrsrechnerdaten gibt es nur
    über eine API mit Schlüssel (`api-key` im MobiData-Eintrag) → nicht keyless.
  - **Freiburg:** WFS `digit_verkehrszaehl` nur mit der Ebene `zaehl_co2_aktuell` (letzte
    Werte vom Mai 2024, keine Reihe) – weiter Testbetrieb.
  - **Ettlingen:** Stundenwerte je Fahrzeugklasse, aber nur CC BY-NC 4.0 → nicht aufnehmen.
  - **Leipzig, Mannheim, Aachen, Ulm (Blautalradweg):** offen nur Rad-Zählsäulen (Eco-Counter)
    – eigener späterer Schritt (Konzept, Entscheidung 1). Leipzigs 24 Kfz-Dauerzählstellen nur
    im Dashboard, nicht als Daten.
  - **Darmstadt, Wiesbaden, Kaiserslautern:** keine offenen kommunalen Zeitreihen gefunden (in
    Darmstadt sind die „Verkehrssensoren“ bei sensoto.io die BASt-Zählstellen; das Portal
    `opendata.cloud.wiesbaden.de` war aus dem Workflow nicht erreichbar).
  - **Konstanz, Gelsenkirchen:** laut svz (AGENTS.md § 3) nur Echtzeit-Zähler (DATEX II) – nicht
    weiter geprüft.
  - **Nicht kommunal** (wie BASt, vorerst nicht): „Stundenwerte der Dauerzählstellen in
    Baden-Württemberg“ (Mobilithek). Kandidat mit einer Stelle: Bielefeld,
    Verkehrszählstelle Ostwestfalendamm (Rohdaten im BASt-Format, Open.NRW).
