# AGENTS.md — Quellen finden, prüfen, einbauen

Learnings aus dem Aufbau (November 2026). Ergänzen, wenn etwas Neues auffällt.

## Was gesucht ist
Zwei Familien, beide mit gezählten Werten im Zeitverlauf:
- **Kurzzeitzählungen** mit **Werten je Zählung** – am besten je Intervall (15/60 Minuten) und
  Richtung, mindestens Tagessummen je Verkehrsart.
- **Dauerzählstellen** (fest eingebaute Detektoren, Kameras, Rad-Zählstellen) mit Stunden- oder
  Tageswerten über Monate und Jahre – Quellen in `pipeline/config/quellen/dauer/`, Code in
  `src/zaehlkarte/dauer/`.

Alle Zählungen mit Werten je Stunde (oder feiner) oder je Tag an einer bestimmten Stelle, gleich,
wer zählt (Beschluss der Projektleitung, 14.11.2026: „ich will gerne alle Zählungen … also muss es
nur in Abgrenzung zum svz Projekt sein“): Kommunen, Kreise, Länder, der Bund (BASt), gemeinsame
Plattformen wie die VMZ Niedersachsen. Bis dahin galten nur kommunale Zählstellen; was unten
unter „Nicht kommunal“ steht, ist seitdem Kandidat. Ebenso Quellen mit nur Tageswerten je Stelle
und Datum (in der Datenlage bisher „nur Summen“, etwa Planegg): ihr Tageswert gilt wie geliefert –
im Modell der Dauerzählstellen als Tageswert der Quelle (unten, „Tageswerte der Quelle“; zuerst
Augsburgs Radzählstationen). Ohne Lizenz nur, was eine öffentliche Stelle veröffentlicht oder
herausgegeben hat (CLAUDE.md, „Quellen ohne Lizenz“).

Nicht gemeint: Jahresmittel (DTV/DTVw), Verkehrsmengenkarten und Modellwerte – dafür
`vizsim/svz`. Prüffrage: Ein Wert je Stelle und Jahr → svz; Werte je Intervall oder Tag →
hier; beides → jedes Repo seinen Teil (Hamburg: DTV-Tabelle svz, Detektor-Stunden hier).
Rad-Zählsäulen und -schleifen (Eco-Counter u. a.) gehören seit November 2026 dazu.

## Wo suchen
- **Zuerst robots.txt.** Jeder Abruf eines Werkzeugs nur, wenn robots.txt ihn erlaubt – für die
  eigene Kennung, für `*` und für die Kennungen von Claude (ClaudeBot, Claude-User,
  Claude-SearchBot, anthropic-ai). Prüfen mit `tools/robots.py` (Branch `werkzeug/erkundung`):
  RFC 9309 mit `*` und `$`, Crawl-delay, Prüfung jeder Weiterleitung. `urllib.robotparser` taugt
  dafür nicht – in Python 3.12 (Runner) ignoriert es die Platzhalter, „Disallow: /*?*“ sperrte dort
  nichts. Gesperrt sind (Stand 14.11.2026) unter anderem: **fragdenstaat.de ganz für ClaudeBot und
  anthropic-ai** (für alle: `/anfrage/*/pdf/`, `/anfrage/*/download/`), **govdata.de ganz für
  alle**, `query.wikidata.org/sparql`, `overpass-api.de/api/` (andere Overpass-Server erlauben es),
  die CKAN-API (`/api/`) von offenesdatenportal.de, opendata.olpe.de, offenedaten.aachen.de,
  opendata.muenchen.de, opendata.ruhr (dort auch jede URL mit Query), mobidata-bw.de, die
  Opendatasoft-Portale (`/api/` und `/explore/dataset/*/download`), gitlab.opencode.de (`/api/v*`,
  `/*/raw`), geo.sv.rostock.de (ganz), Downloads `*.osm.pbf` bei Geofabrik. FragDenStaat und
  GovData daher nur über die Websuche (`site:fragdenstaat.de`, `site:govdata.de`); Anhänge liegen
  auf media.frag-den-staat.de (eigener Host, erlaubt). Ältere Abschnitte unten beschreiben noch die
  API-Wege – sie sind so nicht mehr zu gehen. Die Pipeline prüft robots.txt selbst
  (`pipeline/src/zaehlkarte/abruf.py`); Stand und Ausnahmen: „robots.txt und die Pipeline“.
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
- **Tübingen** (`tuebingen_pdf`, ohne Lizenz): Anlagen 1 und 3 zur Vorlage 242/2022 – je
  Zählstelle ein Kasten (fetter Straßenname, Zusatz darunter, je Spalte Zähltag, Wert „6.361
  Kfz/24h“, Veränderung in Prozent, kleiner Vermerk). Der Text von pdfplumber zerreißt die Spalten
  (Werte gestaffelt über drei Zeilen) – gelesen über die Lage der Wörter (Höhe, Größe, fett). Nur
  Spalten mit Datum; nicht übernommen: „Hochrechnung 16h → 24h“ (2011–2015 an fünf Stellen),
  „Dauerzählstelle Ø Di-Do“, „DTV 2019“, Kalenderwochen, Bus und „Kfz ohne Bus“. In den Teilorten
  steht der Ort im Vermerk (zwei Standorte in einem Kasten); die Vorlage nennt Orte genauer („Ecke
  Kielmeyerstraße“, „Westarm des Knotens in Weilheim“, „am Alten Friedhof in Derendingen“). Die
  Stuttgarter Straße hat je Richtung einen Kasten (Summe in der Karte, Richtungen in der
  Bemerkung). Die Vorlage selbst rundet auf 100, die Tabellen nicht.
- **Neubulach** (`neubulach_pdf`, ohne Lizenz): Kurzbericht des Büros IGV (2024), Tabelle
  „Übersicht der DTV-Werte“ mit einem Block je Arm („2.3 Oberhaugstetter Str. (K 4304)“) und den
  Zeilen 4h-Werte, 24h (DTVw), DTV, Tag/Nacht, M, P. Gezählt sind Knoten 1 über 24 Stunden (Zeile
  „24h (DTVw)“, laut Bericht nicht hochgerechnet) und sonst 15–19 Uhr („4h-Werte“; der Text
  spricht von vor- und nachmittags, Tabelle 1 und der Kopf der Tabelle nur von 15–19 Uhr). Knoten =
  halbe Summe der Arme. Der Strombelastungsplan hat Tippfehler (Knoten 2: 4.254 statt 4.244, die
  Ströme ergeben wie die Tabelle 4.244; Knoten 1: „3.041 (314)“, die Ströme 3.403 (105)) – daher
  zählt die Tabelle. Querschnitt 2 heißt in Tabelle 1 „Oberhaugstetter Straße (Ortsausgang
  West)“, in der Wertetabelle „Altbulacher Str.“; der Zählstellenplan zeigt ihn am Ortsausgang
  Richtung Altbulach.
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
  Archiv auf kmk.org (`Ferien99_00.pdf` … `FER2027_28.pdf`; PDFs 1999/2000–2027/28 auf
  `werkzeug/erkundung`, `ergebnis/ferien/`). `pipeline/werkzeuge/kmk_ferien.py` liest die Tabelle
  mit pdfplumber aus dem PDF – Zelle für Zelle, Name und Jahr je Spalte aus dem Kopf (bis
  2001/02 stehen die Sommerferien vorn, 2001/02 hat zwei Sommerspalten). Abgleich mit `--pruefe`:
  deckt sich mit NW 29, SN 21, BB 17 und HH 3 Schuljahren. Der frühere Weg über den Text von
  `pdftotext -layout` ordnete mehrzeilige Zellen über die Nähe zur Landeszeile zu und gab so
  Einzeltage an Nachbarländer (Mecklenburg-Vorpommern 2024/25 und 2025/26 – berichtigt im
  November 2026); er bleibt nur für Kalender ohne PDF. Kursiv gesetzte schul- und
  unterrichtsfreie Tage stehen unter dem Namen ihrer Spalte; den Buß- und Bettag in Bayern (Art. 4
  Nr. 3 BayFTG) führt die KMK nicht – von Hand nachtragen. Bayerns Frühjahrsferien (Fasching)
  stehen unter Ostern/Frühjahr vor den Osterferien. kmk.org ist aus der Sandbox nicht erreichbar
  (Werkzeug-Branch, `tools/kmk_pdf.py`). `zaehlkarte kalender` meldet im Wochenlauf, wenn die
  Ferien eines Landes in drei Monaten enden.
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
  Hinweis (`hinweise_zeitraum` in der Quelldatei), sortiert nichts aus.

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
  Zählung), Ettlingen (Sensoren, CC BY-NC 4.0; seit November 2026 als Dauerzählstellen in der
  Karte, siehe unten), Ulm (Kameras „vgv_ulm“, eine Zeile
  je Verkehrsteilnehmer, Standorte nur als Kürzel), Mannheim (Eco-Counter), Heidelberg
  (Kameras). Die Geschwindigkeitsdisplays in Konstanz taugen laut Stadt nicht für
  Verkehrsmengen; Heilbronn hat nur Kfz-Bestand und Fahrleistung (Statistisches Landesamt);
  Aalen zählt mit eigenem Seitenradar, veröffentlicht aber nichts. Karlsruhe hat 2023 Zählungen
  eines Verkehrsversuchs als Excel herausgegeben (FragDenStaat) – alles in der Datenlage.
- Hessen (November 2026, Kommune für Kommune: alle Gemeinden laut Wikidata (425) und alle 21
  Landkreise, je Website Sitemap, Suche und Startseite – 453 Seiten, 27 per robots.txt gesperrt;
  `tools/hessen.py`, `hessen2.py` auf `werkzeug/erkundung`, Ergebnisse `ergebnis/hessen*/` –,
  dazu Websuche je Stadt ab 20.000 Einwohnern und je Kreis, alle
  rund 5.600 FragDenStaat-Anfragen im Land, GovData/Open Data Hessen, Mobilithek, OSM): keine
  offenen kommunalen Kurzzeitzählungen. Offen sind nur automatische Zählungen – Darmstadt
  (Ampelschleifen, siehe Dauerzählstellen), Rüsselsheim (Detektoren, nur Echtzeit) – und
  Frankfurts 24-Stunden-Mittel (WFS, in `vizsim/svz`). Neu in der Datenlage: Darmstadt,
  Rüsselsheim, Marburg, Bad Homburg, Oberursel, Idstein, Dietzenbach, Bad Vilbel, Pfungstadt,
  Groß-Gerau, Bad Hersfeld, Karben, Mühltal, Rosbach; präzisiert: Frankfurt, Kassel. Nur mit
  Dauerzählstellen (ohne Stand der Kurzzeitzählungen): Gießen, Wiesbaden, Dreieich, Rödermark,
  Rodgau, Altenstadt, Baunatal und die Kreise Marburg-Biedenkopf, Waldeck-Frankenberg,
  Main-Kinzig und Odenwald sowie Offenbach (acht Rad-Zählstellen laut Pressemitteilung vom
  30.01.2024).
  - **Rad-Zählnetz des Landes** (wichtigster Fund): seit 2022 Induktionsschleifen je Richtung,
    Stufe 1 (2022) 270 Stellen, etwa die Hälfte in Zuständigkeit von Kreisen, Städten und
    Gemeinden, Stufe 2 (ab 2024) 301 weitere, davon 148 kommunal; Ziel Ende 2026: 571
    ([AGNH](https://www.nahmobil-hessen.de/unterstuetzung/daten-fuer-den-radverkehr/dauerzaehlstellen/)).
    Hessen Mobil beschafft und baut, das Land zahlt, die Kommunen wählen die Standorte und tragen
    teils den Betrieb (Bad Homburg: 300–500 Euro je Stelle und Jahr). Werte (Tag, Monat, Jahr,
    „ohne vorherige Plausibilisierung“) nur im Eco-Counter-Portal `hessen-mobil.eco-counter.com`
    (= `data.eco-counter.com/ParcPublic/?id=8080`), ohne Lizenzangabe; der GovData-Eintrag
    „Dauerzählstellen für den Radverkehr in Hessen“ verlinkt nur das Portal – seine Lizenz ließ sich
    nicht abrufen (die GovData-API sperrt Einzelabfragen per robots.txt, und die Suche führt die
    Lizenz nicht am Datensatz, auch nicht beim WFS Frankfurt, der dl-de/by-2-0 hat).
    Hebel: eine Anfrage bei Hessen Mobil (als Landesbehörde unter dem HDSIG) nach den Stundenwerten
    aller Stellen samt Lizenz – sie brächte die kommunalen Stellen mit. Kommunen mit Stellen laut
    eigener Meldung: Frankfurt (10), Oberursel (9), Offenbach (8, eine davon betreibt Hessen Mobil),
    Rödermark (5), Bad Homburg (4), Gießen, Baunatal, Dreieich, Rodgau, Wetzlar, Altenstadt, Eschborn
    (Zählstationen seit 2018); Kreise Marburg-Biedenkopf (2024 17 Stellen dazu), Waldeck-Frankenberg
    (6), Main-Kinzig (13 Standorte), Odenwald. Die AGNH verleiht mobile Zählgeräte (Rad, Fuß, Kfz)
    an Kommunen; die Werte liegen im Eco-Visio-Konto der Kommune – nicht veröffentlicht (Dietzenbach
    zählte 2025 mit Leihgeräten der Landesenergieagentur).
  - **Detektordaten der Verkehrsrechner** in der Mobilithek: Frankfurt (110000000002386001),
    Kassel (110000000002398000) und Wiesbaden (110000000003165001) nur nach Freigabe einer
    Subskription; Rüsselsheim (110000000003182000) Open Data, aber nur Echtzeit (DATEX II).
  - **Kameras und Sensoren:** Marburg Oberstadt (sechs Kameras seit 2024, Personen, Rad, Pkw,
    Lieferverkehr; nur PDF-Auswertungen eines Standorts), Kassel (Radarsensoren im Testfeld AUREA,
    nur Dashboard), Groß-Gerau (Radar-Messgerät 2025). Neu-Isenburgs „Passantenfrequenz“ misst
    Funksignale von Handys – keine Zählung im Sinne der Karte.
  - **Seitenradar und Messtafeln:** Mühltal (seit 2022 Berichte mit Summen je Zeitfenster,
    Gemeindebeschluss), Karben (2018 Rohdaten auf Anfrage, seit Oktober 2025 Monatsberichte),
    Reichelsheim (Wetterau; Bericht mit Tages- und Stundenwerten in Sitzungsunterlagen 2024),
    Rodenbach (Auswertungen als Bild), Bad Hersfeld (laut Masterplan). Viele kleine Gemeinden
    veröffentlichen nur Ergebnisse ihrer Geschwindigkeitsüberwachung (gemessene Fahrzeuge und
    Verstöße je Einsatz: Butzbach, Weiterstadt, Gudensberg, Naumburg, Schlitz, Königstein,
    Ginsheim-Gustavsburg, Kirchhain, Niedernhausen, Biebertal, Limburg) – keine Zählungen.
  - **Nur in Plänen und Gutachten:** Idstein (VEP 2035: 24 Knotenpunkte 2018), Bad Nauheim (VEP
    2015, Kordonerhebung 2012/13), Neu-Isenburg (Radverkehrskonzept 2015: 16 Knotenpunkte 2012),
    Oberursel (Querschnitte 2018 als Karte), Lahn-Dill-Kreis (Radverkehrskonzept: vier
    Rad-Zählstellen 2022, nur als Grafik), sonst Gutachten zu Bebauungsplänen.
  - **Nicht kommunal:** Frankfurt University of Applied Sciences („Automatisierte
    Verkehrsflusszählung“, Open Data, mobile Sensoren 2025), FID move (Rad am R3, Forschung),
    Videozählungen von Hessen Mobil (Herborn, Pfungstadt, Geisenheim), SVZ 2025.
  - **Recht:** Das HDSIG gilt für Kommunen nur mit Informationsfreiheitssatzung – gefunden in
    [Wiesbaden](https://www.wiesbaden.de/vv/produkte/0105/Informationsfreiheitssatzung),
    [Offenbach](https://www.offenbach.de/buerger_innen/buerger-service/stadtrecht/informationsfreiheitssatzung.php),
    [Neu-Isenburg](https://Neu-Isenburg.de/medien/downloads/buergerservice/verwaltung-im-rathaus/amtliche-bekanntmachungen/2023/Informationsfreiheitssatzung_neufassung_2023.pdf),
    [Hofheim](https://www.hofheim.fcio.net/fileadmin/dokumente/Politik_und_Verwaltung/Verwaltung/Stadtrecht/Allgemeine_Verwaltung/Hofheimer_Stadtrecht_Allgemeine_Verwaltung_Informationsfreiheitssatzung_A08.pdf),
    Solms (genannt in einer Antwort auf FragDenStaat 2024) und Kassel (laut HBDI 2020); sonst gilt
    das HUIG. Rosbach lehnte 2018 ab („keine rechtliche Grundlage“), Mühltal 2022 die
    Zusammenstellung älterer Messungen.
  - **Sackgassen:** frankfurt.de, darmstadt.de, kassel.de, wetzlar.de, bensheim.de und
    landkreiskassel.de sperren Abruf-Werkzeuge per robots.txt, ebenso Teile von wiesbaden.de;
    `offenedaten.frankfurt.de` und `opendata.darmstadt.de` sind kein CKAN (Darmstadt: Bestandsliste
    als CSV unter `sites/default/files/…-Datenbestand_DA_0.csv`); `opendata.cloud.wiesbaden.de`
    lief in Zeitüberschreitungen; Eco-Visio-API-Pfade geraten → 404; Mühltals Übersicht
    „Verkehrsmessdaten“ lädt ihre Liste per JavaScript.
- Nordrhein-Westfalen (November 2026, Kommune für Kommune: alle 396 Gemeinden und 53 Kreise bzw.
  kreisfreien Städte laut OSM-Grenzen – Wikidata sperrt Abruf-Werkzeuge per robots.txt –, je Website
  Sitemap, Suche und Startseite: 429 Seiten, 359 erreicht, 64 per robots.txt gesperrt, vor allem in
  Lippe, Herford, Minden-Lübbecke, Düren und im Rhein-Erft-Kreis; `tools/land.py`, `tools/nrw2.py`
  auf `werkzeug/erkundung`, Ergebnisse `ergebnis/nrw*/` –, dazu Websuche für die gesperrten Städte,
  Open.NRW, opendata.ruhr und offenesdatenportal.de über die Websuche, Mobilithek und der
  Musterdatenkatalog): keine neue offene Kurzzeitzählung mit Lizenz. Neu in der Datenlage: Kevelaer,
  Verl, Bad Honnef, Emsdetten, Ratingen, Marl, Gronau, Geseke, Mülheim an der Ruhr, Bottrop,
  Herscheid, Datteln; präzisiert: Paderborn, Köln. Nur mit Dauerzählstellen: Bielefeld, Neuss,
  Hennef, Rhein-Sieg-Kreis.
  - **Offen, aber ohne Lizenz:** Kevelaer – Zählung September 2019 (16 Knotenpunkte 6–10 und
    15–19 Uhr, Viertelstunden je Strom nach Pkw, Krad, Lieferwagen, Lkw; 13 Querschnitte 24 Stunden,
    Stundenwerte) als 74-seitiges PDF eines Büros auf kevelaer.de. Bester Fund des Landes: mit einer
    Lizenz käme die Zählung in die Karte (Text mit pdftotext lesbar, Intervalle „06:00 - 06:15“,
    ähnlich `xanten_pdf`).
  - **Nur Summen offen:** Paderborn (Juni 2018 rund 100 Stellen, nur Pläne der DTVw), Verl (gut 60
    Messberichte der Verkehrsmessungen, Stundenwerte nur als Diagramm), Bad Honnef
    (Zusammenfassung je Seitenradar-Zählung, die Liste lädt per JavaScript), Emsdetten (Wochenmittel
    an fünf Kamera-Zählstellen während der Sperrung der B 481), Münster (Monatsmittel der
    Ampelschleifen an fünf Kreuzungen seit 2021, Mobilithek -5042567686068911126 – keine Tageswerte,
    nicht in der Karte).
  - **Gezählt, nicht offen:** Ratingen (33 Kreuzungen 2024), Marl (67 eigene Zählstellen zur
    Straßenverkehrszählung 2025), Gronau, Geseke (Schulwege, Fuß und Rad, September 2026), Mülheim,
    Bottrop, Herscheid (verdeckte Messungen je Fahrzeug), Datteln; nur Ankündigungen von Zählungen
    durch Büros: Bad Salzuflen, Niederkassel, Unna, Gütersloh, Hilden; eigene Zählgeräte bzw.
    Geschwindigkeitsanzeigen mit Statistik: Augustdorf, Reken, Eschweiler, Freudenberg, Burbach,
    Warendorf, Brakel, Neuss (Dialog-Displays an 31 Standorten), Haan (Messergebnisse der
    Geschwindigkeitsanzeige 2018–2021, rund 80 Berichte – die PDF-Downloads sperrt robots.txt,
    Inhalt nicht geprüft).
  - **Dauerzählstellen:** Stadt Neuss (Rad-Zählstelle am RS5, Stundenwerte im Portal des
    Rhein-Kreises, in der Mobilithek „keine Lizenz“), Bielefeld (sieben Rad-Dauerzählstellen; der
    Open-Data-Eintrag verlinkt nur Webseite und Karte), Hennef (Horstmannsteg, Jahresberichte als
    PDF), Rhein-Sieg-Kreis (12 Rad-Zählstellen, interaktive Karte), Köln (17 und mehr, einige mit Kfz,
    nur Eco Public), Paderborn (Sensoren der Smart City), Emsdetten (KI-Kameras am
    Döring-Kreisverkehr). Detektordaten: Köln und Gelsenkirchen nur DATEX II (Echtzeit), Düsseldorf
    ohne Lizenz (Mobilithek 110000000002055001).
  - **Moers ist vollständig:** Die Einzel-Datensätze auf opendata.ruhr und Open.NRW („Verkehrszählung
    Boschheideweg“, „… Kirchweg“ von 2014 usw.) sind ältere Einträge derselben Messungen; auf
    offenesdatenportal.de gibt es genau die zehn Jahresdatensätze 2010–2021, die die Karte liest
    (`verkehrszahlung-kirschenallee` heißt dort „Verkehrszählungen 2010“).
  - **Für die Geschwindigkeitskontrollen** (`vizsim-lab/geschwindigkeitskontrollen`): Messstellen der
    mobilen Überwachung von Kreis Kleve, Kleve und Wesel (offenesdatenportal.de, dl-de/zero),
    Moers („Verkehrsüberwachung“), Düsseldorf (stationäre Überwachung), Köln (Messplatzliste 2022);
    Fallzahlen semistationärer Anlagen: Kreise Mettmann, Siegen-Wittgenstein, Hochsauerlandkreis.
  - **Nicht kommunal:** FH Aachen („Aachener Datenpool“ ACDatEP, Mobilithek 767690308516229120),
    Straßen.NRW (Straßenverkehrszählung, Dauerzählstellen), die Zählungen der Kreise zur
    Straßenverkehrszählung 2025 (Ergebnisse veröffentlicht die BASt).
  - **Sackgassen:** Open.NRW (`ckan.open.nrw.de`) aus Actions nicht erreichbar, seine API sperrt
    robots.txt – die Websuche mit `site:open.nrw` findet die Datensätze, auch die von opendata.ruhr
    und offenesdatenportal.de gespiegelten (dort aber ohne Ressourcen); opendata.ruhr sperrt `/api/`
    und jede URL mit Query (`/*?*`), offenesdatenportal.de `/api/` (Crawl-delay 10 s). Der
    Musterdatenkatalog (Themen der kommunalen Open-Data-Sätze) liegt bei der FITKO auf openCode (das
    Projekt fand die API nicht); ein Stand von 2023 liegt auf GitHub
    (`bertelsmannstift/musterdatenkatalog`, Kategorien „Individualverkehr – Messstellen“ und
    „Radverkehr – Messstellen“) – dort nichts Neues. Für gesperrte oder nicht erreichbare
    Gemeindeseiten (Herford, Hürth, Castrop-Rauxel, Herne, Remscheid, Hagen, Langenfeld, Stolberg,
    Kerpen, Bergheim, Brühl, Frechen, Pulheim, Erftstadt, Kamen, Bünde, Löhne, Greven, Steinfurt)
    fand die Websuche nichts Verwertbares, meist Gutachten zu Bebauungsplänen.
  - **Recht:** Das IFG NRW gilt für Gemeinden und Kreise unmittelbar.
- Niedersachsen (November 2026, Kommune für Kommune, Runde 3: Gemeinden, Samtgemeinden und
  Landkreise aus dem Gemeindeverzeichnis von Destatis, Webseiten aus OSM oder geraten – 910
  Websites in zwei Durchsichten, 790 erreicht; je Website Sitemap, Suche und Startseite; dazu die
  Mobilithek bundesweit; `tools/land.py`, `land_lesen.py`, `gezielt_lesen.py`,
  `mobilithek_alle.py` auf `werkzeug/erkundung`, Ergebnisse `ergebnis/runde3*/NI`): keine offene
  Kurzzeitzählung mit Lizenz.
  - **Offen, aber nur Tageswerte:** Braunschweig – acht Rad-Dauerzählstellen, je Quartal eine CSV
    mit einem Tageswert je Zählstelle (CC BY 4.0, seit 2023); ohne Stundenwerte nicht für die Karte
    (Tagessumme nicht prüfbar).
  - **Kreise zählen ihre Kreisstraßen selbst:** Landkreis Gifhorn 2025 an 138 Stellen je 24 Stunden
    (Video), Landkreis Harburg landkreisweit je Abschnitt eine Zählstelle – die aussichtsreichsten
    Anfragen im Land. Landkreis Lüneburg verleiht mobile Rad-Zählgeräte (Daten im Online-Konto).
  - **Gezählt, nicht offen:** Goslar (mobile Videodetektion, drei Rad-Dauerzählstellen seit 2018),
    Oldenburg (Ofenerdiek: Seitenradar, Zählplatten, Kameras; Zählsäule Pophankenweg seit 2023),
    Neustadt am Rübenberge (2021, 20 Standorte), Salzgitter (Rad, Juni 2025), Lastrup (Gerät der
    Gemeinde, je eine Woche auf Antrag); nur als Bild: Buxtehude (VEP, rund 40 Zählstellen); nur
    Auswertungen: Leer (drei Rad-Zählstellen).
  - **Osnabrück:** Die Mobilithek führt seit September 2025 den Datensatz der 66 TEU-Sensoren
    (01.01.2022–09.11.2023) als ZIP, eingestuft als freie Nutzung, aber ohne genannte Lizenz.
  - **Nicht kommunal oder ohne Wert:** Ankündigungen der Straßenverkehrszählung des Landes
    (Sittensen, Scheeßel), Radzählungen des Regionalverbands für den Radschnellweg (Lehre),
    einzelne Ergebnisse in Pressemitteilungen (Geeste: Radzählung an der Fährbrücke 2026,
    Bienenbüttel: Verkehrsmessung Wichmannsburg 2024). Geratene Adressen treffen
    gelegentlich die falsche Gemeinde (www.gronau.de ist Gronau in Westfalen).
- Bayern (November 2026, Kommune für Kommune, Runde 3 wie Niedersachsen: 1.489 Websites der
  Gemeinden, Verwaltungsgemeinschaften und Landkreise, 1.177 erreicht; Ergebnisse
  `ergebnis/runde3*/BY`): keine offene Kurzzeitzählung mit Lizenz.
  - **Rauschen:** Fast jede Gemeinde bindet den Text „Straßenverkehrszählungen; Durchführung“ aus
    dem BayernPortal ein (Zählungen des Landes, BAYSIS); auch „aktuelle Daten“ kleiner Gemeinden
    verweisen meist auf BAYSIS (Möhrendorf). Landkreise veröffentlichen SVZ-Datenblätter je
    Zählstelle (Deggendorf, DTV) – das gehört nach `vizsim/svz`.
  - **Veröffentlichte Messberichte kleiner Gemeinden:** Buchloe (PDF je Messung: Fahrzeuge und
    mittlere Geschwindigkeit je Tag) und Moorenweis (Auswertungen als PDF) – nur Tageswerte,
    Anfrage nach den Exporten der Geräte.
  - **Rad-Dauerzählstellen ohne offene Werte:** Landshut (zwei), Bayreuth (Mainradweg), Bamberg,
    Landkreis Bamberg (Pettstadt, 2026), Schwabach (drei Zählsäulen); Planegg veröffentlicht je
    Jahr eine Excel-Datei mit Tageswerten je Richtung, ohne Lizenz.
  - **Mobilithek:** Detektordaten Regensburg (eingeschränkte Lizenz, nur vermittelt), Stadtwerke
    Schweinfurt (ohne Lizenz), Kfz-Dauerzählstellen München (nur mit Vertrag); Fußverkehr stündlich
    offen in Augsburg (Annastraße, CC BY 4.0) und Würzburg (dl-de/by-2-0) – beide seit November
    2026 in der Karte.
  - **Gezählt, nicht offen:** Regensburg (eigene Zählungen März–Oktober, 6–10 und 15–19 Uhr);
    nur als Plan: Erlangen (Verkehrsbelastungsplan 2017).
- Übrige Länder, Runde 3 (November 2026, Kommune für Kommune wie Niedersachsen; Websites je Land:
  BW 1.375, RP 859, SH 334, SN 358, TH 265, ST 251, BB 247, MV 222, SL 46, dazu die Stadtstaaten;
  Ergebnisse `ergebnis/runde3*/<LAND>`): keine offene Kurzzeitzählung mit Lizenz.
  - **Werte als PDF ohne Lizenz:** Tübingen (Ratsinformationssystem, Vorlage 242/2022: 24-Stunden-
    Werte je Querschnitt für Kfz und Rad), Neubulach (Kurzbericht zum Lärmaktionsplan 2024) –
    seit November 2026 in der Karte, ohne Lizenz (`tuebingen_pdf`, `neubulach_pdf`).
  - **MobiData BW:** 18 weitere Kommunen und Kreise haben Rad-Zählstellen im Bündel und damit in
    der Karte (Rems-Murr-Kreis 25, Ludwigsburg 22, Ostalbkreis 11 …) – jetzt mit Datenlage-Eintrag.
  - **Gezählt, nicht offen:** Görlitz (Kameras an 30 Knoten), Landkreis Sächsische
    Schweiz-Osterzgebirge (Kreisstraßen ab 2026), Zweibrücken (2022), Greifswald (Rad 2019 an rund
    50 Stellen, Fuß und Rad 2024), Finsterwalde (VEP 2025), Birkenwerder, Bargteheide,
    Schwentinental, Plön, Husum (Rad), Elmstein (Display mit Datenerfassung je Fahrzeug), Binz
    (Auskunft gegen Gebühr).
  - **Rad-Dauerzählstellen ohne offene Werte:** Koblenz (zwei), Greifswald (drei), Schmölln.
  - **Mobilithek:** Verkehrszähldaten Konstanz (Kfz, CC BY 4.0, nur vermittelt); Heidelbergs
    Verkehrsrechnerdaten laut Mobilithek CC0, aber nur über eine Schnittstelle mit Schlüssel.
  - **Ohne Fund:** Sachsen-Anhalt und das Saarland (nur schon bekannte Einträge), die Stadtstaaten.
    Zählungen des Landesamts für Umwelt Brandenburg zur Lärmkartierung tauchen als Ankündigungen
    der Städte auf (Beelitz).
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
von beauftragten Büros. Kurzfassung je Land: `pipeline/config/recht.yaml`
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

**Quellen ohne Lizenz** (Beschluss der Projektleitung, 14.11.2026; Regel in CLAUDE.md): Was eine
Kommune ohne Lizenz veröffentlicht oder auf Anfrage herausgegeben hat, zeigt die Karte mit dem
Hinweis „ohne Lizenz“, Link zum Original und Link „Entfernen lassen“ (Issue-Formular
`daten-entfernen.yml`), aber nicht im CSV-Export. Die Abwägung (keine Rechtsberatung):
- Zählwerte sind Fakten; Rohdaten sind nicht urheberrechtlich geschützt
  ([Uni Bremen, Schutz von Datenbanken](https://www.uni-bremen.de/urheberrecht/wissensplattform/9-schutz-von-datenbanken)).
  Schützen kann sie nur das Recht des Datenbankherstellers (§§ 87a ff. UrhG), und nur gegen die
  Übernahme wesentlicher Teile – eine ganze Zählung ist eher wesentlich.
- Behörden können sich nach dem Datennutzungsgesetz nicht auf dieses Recht berufen, um die
  Weiterverwendung zu unterbinden ([netzpolitik.org, 2021](https://netzpolitik.org/?p=323225));
  einen generellen Ausschluss der Weiterverwendung in Landes-IFGs gibt es nicht mehr
  ([Bundeswirtschaftsministerium zum IWG](https://www.bundeswirtschaftsministerium.de/Redaktion/DE/Artikel/Digitale-Welt/open-data-iwg.html)).
  Bayern verlor 2026 vor dem OLG München gegen Markus Drenger, der Hauskoordinaten gespiegelt
  hatte – nach Takedown, Strafanzeige und Zivilklage, rund fünf Jahre nach der ersten Forderung
  ([netzpolitik.org, August 2026](https://netzpolitik.org/?p=529717)).
- Auf § 5 UrhG (amtliche Werke) nicht bauen: eng ausgelegt
  ([BGH, Bodenrichtwertsammlung](https://lexetius.com/2006,3016)); Karten und Grafiken in
  Berichten können geschützt sein ([BGH I ZR 59/19, 2021](https://www.haufe.de/id/entscheidung/bgh-urteil-vom-21012021-i-zr-5919-HI14366013.html))
  – darum nur die Zahlen übernehmen, Berichte verlinken.
- Folgen schlimmstenfalls: Bitte um Entfernung, Abmahnung (bei einer Privatperson die
  Anwaltskosten der ersten Abmahnung gedeckelt,
  [§ 97a Abs. 3 UrhG](https://www.gesetze-im-internet.de/urhg/__97a.html)). Darum: auf Bitte
  sofort entfernen; nie, wenn die Kommune Bedingungen gestellt hat (Amberg: Nutzungserklärung;
  Magdeburg: Entgelt für die Weitergabe im Gespräch). Der CSV-Export bleibt bei Quellen mit
  Lizenz, damit die Karte nichts ohne Lizenz an Dritte weiterreicht.

## robots.txt und die Pipeline (Stand 14.11.2026)
`tools/robots_audit.py` (Branch `werkzeug/erkundung`, Ergebnis `ergebnis/robots_audit/audit.md`)
hat die Abrufe der Pipeline gegen robots.txt geprüft; zehn Quellen holten über Wege, die
robots.txt für alle Robots sperrt. Seitdem:
- **Die Pipeline prüft jeden Abruf selbst** (`pipeline/src/zaehlkarte/abruf.py`): robots.txt nach
  RFC 9309 für ihre Kennung `zaehlkarte-pipeline` (sonst die Gruppe `*`), Crawl-delay je Host
  (höchstens 60 s), jedes Weiterleitungsziel. Gesperrtes nur mit einer Ausnahme in
  `pipeline/config/robots.yaml` (je Host oder Pfad eine: URL-Anfänge, die Quellen, die sie
  brauchen, Grund, seit, Anfrage beim Betreiber mit `an`, `gestellt`, `antwort` oder `verzicht`);
  das Protokoll von `fetch` und `dauer fetch` nennt jeden Abruf, der nur dank einer Ausnahme
  ging, mit dem Stand der Anfrage, und die Wartezeit.
  Neue Quellen: ohne erlaubten Weg keine Aufnahme, außer die Projektleitung beschließt eine
  Ausnahme. GitHub (Checkout, Releases, API mit dem Token des Workflows) ist kein Crawlen und
  bleibt außen vor.
- **Umgestellt auf erlaubte Wege** (`pipeline/src/zaehlkarte/ckan.py`, Muster in
  `ergebnis/wege2/`):
  - Moers (offenesdatenportal.de): DCAT-Dokument je Datensatz (`/dataset/<name>.jsonld`) – die
    HTML-Seite zeigt nur einen Teil der Ressourcen. Rund 200 Dateien mit 10 s Abstand: ein Lauf
    von „Kartendaten neu bauen“ dauert eine gute halbe Stunde länger.
  - Olpe: HTML-Suche und HTML-Seite je Datensatz. Die HTML-Suche findet je nach Wortform andere
    Datensätze („Verkehrsmessung“ 5, „Verkehrsmessungen“ 8; die API fand mit dem ersten Wort alle
    neun) – beide Formen plus die bekannten (`pakete`). Das DCAT-Dokument nennt keine Lizenz; die
    Lizenz kommt aus dem Link der Seite (`lizenz_link` der Lieferung).
  - Probelauf 14.11. (`tools/pipeline_probe.py`, `ergebnis/pipeline_probe/`): Olpe 9 Datensätze,
    13 Messungen, 128 Zählungen; Moers 2021 und Kirschenallee 47 Dateien, 181 Zählungen – beides
    genau wie in der Karte.
  - Aachen: HTML-Seite (kein DCAT-Dokument). Die Stadt legt täglich eine neue Datei für das
    laufende Jahr an und löscht die alte später; bei zwei Dateien eines Jahres gilt die jüngste
    laut Seite der Ressource („Daten wurden zuletzt aktualisiert“).
  - München: HTML-Suche, je Paket DCAT-Dokument oder HTML-Seite. Für die Werkzeuge nicht prüfbar
    (opendata.muenchen.de sperrt ClaudeBot ganz); für die Pipeline erlaubt (Gruppe `*`).
  - Hamburg: Straßennamen neuer Stellen kurz über Overpass statt aus dem Geofabrik-Abzug. Am
    14.11. antwortete aus Actions nur maps.mail.ru (VK, POST 15 s; GET 504);
    overpass.private.coffee lief in die Zeitgrenze, overpass.kumi.systems ist laut OSM-Wiki
    derselbe Server unter altem Namen (`ergebnis/overpass_probe/`). Darum zurück zum Abzug, mit
    Ausnahme (unten).
  - Moers-Geokodierung (`werkzeuge/geokodiere_moers.py`): Overpass über private.coffee statt
    overpass-api.de, Abrufe über `abruf` (Nominatim und Photon prüft es beim nächsten Lauf).
- **Ausnahmen** (die Projektleitung will die Quellen nicht verlieren; bis die Betreiber
  antworten): Potsdam (Opendatasoft-API, Zählpläne auf de.ftp.opendatasoft.com – ganz gesperrt),
  Würzburg, Rhein-Kreis Neuss, Dortmund (Opendatasoft `/api/explore/`; auch
  `/explore/dataset/*/download` ist gesperrt; seit 14.11.2026 auch für Würzburgs
  Passantenzählung und den RS5 der Stadt Neuss im Portal des Kreises), Rostock (geo.sv.rostock.de und opendata-hro.de
  ganz), Bochum (openCode-GitLab: API, `/*/raw`, Archive und git über HTTPS; opendata.ruhr
  verweist auf genau diese Wege). Viele Betreiber sperren ihre API gegen Suchmaschinen und bieten
  sie zugleich für Programme an – die Anfrage klärt, ob ein wöchentlicher Abruf bekannter Dateien
  gemeint ist. Entwürfe: Projekt-Dokument `claude/anfragen-robots-2026-11.md`; Empfänger und Stand
  je Ausnahme in `pipeline/config/robots.yaml` (`anfrage`).
- **Geofabrik** (Beschluss der Projektleitung, 14.11.2026): Geofabrik sperrt `*.osm.pbf` per
  robots.txt für alle Robots (ebenso openstreetmap.fr ganz und BBBike `*.pbf`). Der Abzug ist aber
  der übliche Weg zu den OSM-Daten einer Stadt; das OSM-Wiki rät für größere Datenmengen zu
  Extrakten statt Overpass (https://wiki.openstreetmap.org/wiki/Overpass_API), und Geofabrik
  bittet in seinem Blog vor allem darum, nicht dieselbe Datei immer wieder zu laden
  (https://blog.geofabrik.de/index.php/2025/09/10/download-responsibly/). Ausnahme für
  `download.geofabrik.de/europe/germany/`
  an Hamburg (Kfz, Rad) und Berlin („Berlin geokodieren“, nur von Hand). Beide Abzüge werden nur
  einmal geladen und im Actions-Cache behalten (Schlüssel `osm-hamburg-1`, `osm-berlin-1`);
  Hamburg lädt ohnehin nur, wenn neue Stellen ohne Namen auftauchen.
- **Erlaubt** laut Prüfung: MobiData BW (Dateien unter `/daten/`), Münster, Konstanz, Xanten
  (opendata.ruhr ohne Query), Berlin (Archiv, Rad-Datei), Hamburg (SensorThings), Ettlingen,
  Open.NRW (API; Essen und Düsseldorf laden von den Seiten der Städte), Leipzig, Bonn.

## Dauerzählstellen (November 2026)

- **Tageswerte der Quelle (seit November 2026, Vertrag 4):** Liefert eine Quelle für eine Stelle
  nur Tageswerte, legt der Adapter sie mit `modell.setze_tage` in `Messreihe.tageswerte` (Gruppe
  in `Messreihe.leer(…, tagesgruppen=…)`). `tagessummen` nimmt sie nur an Tagen vor der ersten
  gezählten Stunde der Stelle in der Gruppe – Quellen ganz ohne Stunden und die Zeit, bevor eine
  Quelle Stunden liefert; ab dann zählen allein die Stunden (ein Tag mit fehlender Stunde wird nie
  mit einem Tageswert gefüllt). In den Kartendaten `tageswerte_bis` je Gruppe und Stelle (bis zu
  diesem Tag ist ein Wert der Tageswert der Quelle), je Quelle `tageswerte`; die Karte schreibt
  „Tageswert der Quelle“ (Hover, Seitenleiste, Hinweis in der Legende), das CSV hat je Gruppe die
  Spalte `<gruppe>_tageswert_quelle` neben `<gruppe>_tagessumme`. Nie aus Wochen-, Monats- oder
  Jahreswerten. In der Karte: Augsburgs Radzählstationen (nur Tageswerte), Hamburg Kfz und Rad
  (Layer „1-Tag“ seit 2020 vor den Stunden des Gedächtnisses, unten), Leipzig (zwei Jahre,
  UTC-Tage; die Stelle Jahnallee hat nur sie), Würzburgs Passanten (Tagesdaten seit 2020 vor den
  Stunden ab 2024; `tage` im Adapter `ods_stunden`). Kandidat: Planegg (Excel je Jahr, ohne
  Lizenz). Weichen die Tageswerte einer Quelle von der Summe
  ihrer Stunden ab (Leipzig, Hamburg), steht das mit Zahlen als Hinweis an der Quelle – geprüft
  dort, wo es beides gibt (Tageswerte aus dem Werkzeug-Lauf gegen die Stunden des Gedächtnisses).
  **Den Tag der Quelle prüfen:** Ortstag (0–24 Uhr) oder UTC-Tag? Hamburg: Ortstag (phenomenonTime),
  Leipzig: UTC-Tag (jeder Tageswert genau die Summe der 24 Stunden des UTC-Tags). Ein anderer Tag
  als 0–24 Uhr steht im Verfahren und als Hinweis an der Quelle – nie umgerechnet.
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
    Tageswerte „für das aktuelle und das letzte Jahr“, Wochenwerte seit Beginn. Die Vollständigkeit
    eines Tags lässt sich nur an Stunden prüfen → die Zählkarte hebt die Stunden selbst auf
    (Gedächtnis, Monatsdateien im Release `dauerzaehlstellen`, `pipeline/werkzeuge/gedaechtnis.py`).
  - **Tageswerte (Layer „…_1-Tag“, seit #28 in der Karte):** entgegen der Beschreibung (Stand
    15.11.2026) seit 2020 – aus den alten Diensten übernommen (`resultTime` 02.03.2026), an
    denselben Things wie die Stunden: Kfz 829 Datastreams (569 Stellen ab 2020, 114 ab 2021),
    Rad 312 (145 ab 2020, 146 ab 2024), Schwerverkehr 341, aber erst ab 01.03.2026 – die Stunden im
    Gedächtnis beginnen schon am 28.02., daher ohne Schwerverkehr (`tageslayer` in der
    Quelldatei). Gedächtnis `tage_JJJJ.csv.gz` (je Stelle, Gruppe und Monat die Tage 1–31); der
    erste Abruf holt alles (Kfz 1,44 Mio., Rad 0,46 Mio. Tageswerte, zusammen rund 5 Minuten aus
    GitHub Actions; eine Seite mit 40 Datastreams ganz: 11 s, 4 MB), danach wie die Stunden ab
    dem jüngsten Tag minus `nachladen_tage`. phenomenonTime = Ortstag in UTC
    („2021-05-25T22:00:00Z/2021-05-26T21:59:59Z“, an den Tagen der Zeitumstellung 23 bzw. 25
    Stunden) – **außer 2026**: 29.03. und 25.10.2026 haben 24 Stunden → verworfen (`ortstag`),
    rund zwei je Datastream. Derselbe Tag zweimal kommt vor (gleicher Wert; verschiedene Werte:
    nicht übernommen, 17 Tage). In der Karte nur vor der ersten gezählten Stunde (Kfz 1,38 Mio.,
    Rad 0,44 Mio.); 31 Kfz-Stellen ohne Stunden (Datastreams leer, Tageswerte enden zwischen März
    und August 2026) sind nur mit Tageswerten in der Karte. Werkzeug: `tools/hamburg_tage.py`,
    Prüfung mit dem Gedächtnis aus dem Release `pruefe_hh` in `tools/lauf.sh` (werkzeug/dauer).
  - **Tageswert und Stunden** (Gedächtnis seit 29.08.2026, alle Stellen): An vollständig gezählten
    Tagen gleich der Summe der Stunden Kfz 72 %, Rad 79 %; sonst fast immer größer (Median der
    Abweichung Kfz +0,25 %, Rad +0,56 %; Kfz 97 %, Rad 94 % aller Tage innerhalb ±1 %). Tage mit
    fehlenden Stunden haben trotzdem einen Tageswert – meist größer als die gezählten Stunden
    (Ausfälle der Stunden-Ebene, ganze Tage ohne Stunden: Kfz 6.312, Rad 2.484), manchmal genau
    ihre Summe (Kfz 254, Rad 54 Tage: der Tageswert enthält nur einen Teil des Tags). Der
    Tageslayer entsteht also nicht aus dem Stundenlayer; beides steht als Hinweis an der Quelle.
  - **Ausreißer und Sprünge, nicht gekennzeichnet:** Knotenpunkt 0287 Ende Januar/Anfang Februar
    2021 Millionen Kfz am Tag (bis 10,2 Mio.), Knotenpunkt 0296 am 09.07.2024 bis 0,9 Mio.; Rad
    an Knotenpunkt 0286 am 11.07.2024 rund 40.000. Jahresmedian einer Stelle mindestens
    verdoppelt oder halbiert gegenüber dem Vorjahr: Kfz 125 von 720 Stellen, Rad 46 von 298
    (einzelne um das Hundertfache, etwa ganze Jahre fast ohne Zählung). Werte 0: Kfz 98, Rad
    1.646. Die Zählkarte übernimmt alles wie geliefert (Hinweis an der Quelle).
  - Ganze Tage fehlen bei allen Stellen zugleich (Ausfälle der Plattform); Werte können sich
    noch nach ein paar Tagen ändern → jeder Lauf holt 14 Tage erneut, in die Karte kommen nur
    Stunden, die sieben Tage alt sind.
  - UTC (laut Quelle). Die Rückstellung legt zwei UTC-Stunden auf 2 Uhr Ortszeit.
  - Keine Straßennamen, nur Kennung (`assetID` = Knotenpunkt, 9, Arm, Richtung) und Punkt →
    nächste benannte Straße aus dem Geofabrik-Abzug (OSM, ODbL; einmal geladen, Ausnahme zu
    robots.txt in robots.yaml), Kreuzungsname aus den übrigen Armen desselben Knotenpunkts.
  - Verschachteltes `$expand=Observations(…;$filter=phenomenonTime ge …;$top=10000)` über eine
    Seite Datastreams spart Abfragen; `$top` bis 20.000 geht.
  - Die alten Dienste `HH_STA_AutomatisierteVerkehrsmengenerfassung` und
    `HH_STA_HamburgerRadzaehlnetz` heißen „(veraltet)“, Tageswerte bis März 2026, Stundenwerte
    nur noch bei 5 Datastreams (2021–2023) – keine Hamburger Historie aus Stunden. Ihre Tageswerte
    stehen inzwischen in den neuen Diensten (oben).
  - Transparenzportal: Die CKAN-API (`/api/`) sperrt robots.txt; die Seite des Datensatzes
    (`/dataset/<name>`) ist erlaubt (Crawl-Delay 10 s, `tools/hamburg_portal.py`).
  - Lizenz dl-de/by-2-0 (beide Datensätze im Transparenzportal), Genauigkeit laut Quelle Kfz
    ±10 %, Schwerverkehrsanteil ±15 %, Rad ±10–20 %.
- **Ettlingen (in der Karte, `ettlingen`, Adapter `readi_urbanpulse`):** Datensatz
  „Automatisierte Verkehrszählung in Ettlingen“ auf re@di (CKAN `opendata.readi.de`),
  Ressource „Stundenwerte pro Fahrzeugtyp und Standort“ nur als Datastore; der ganze Bestand
  kommt über `/datastore/dump/<Ressource>` (CSV, rund 40 MB, aus GitHub Actions in Sekunden; aus
  manchen Entwicklungsumgebungen nicht erreichbar). `datastore_search_sql` ist abgeschaltet
  (400). Lizenz CC BY-NC 4.0 – aufgenommen, die Lizenz steht an der Quelle, in der Seitenleiste
  und in jeder CSV-Zeile. Erkundet im Werkzeug-Branch `werkzeug/dauer`
  (`tools/dauer_ettlingen.py`, `ergebnis/dauer/ettlingen/`). Fallen:
  - **Drei Arten Zeilen in einer Tabelle:** (1) Ströme der Plattform UrbanPulse
    (`source` = „UrbanPulse“, seit 20.08.2026) – je Fahrtrichtung ein Strom (`sid`, `lane_index`,
    `direction`), Lage je Sensor (`sensor_id`, `latitude`, `longitude`); nur die übernimmt die
    Karte. (2) Ältere Kennungen 46–54 (Mai 2025 bis 19.08.2026, ohne `source`, Richtung und
    Lage – nur ein `goo.gl`-Link): **laufende Tageszähler**, kein Stundenwert (der Wert steigt
    über den Tag, Neubeginn um Mitternacht Ortszeit; in der letzten Stunde des Tags bleibt er
    gleich, nach Mitternacht fehlen Stunden) → nicht übernommen. (3) Testimporte vom
    05.08.2026 (Zeitstempel minutengenau, Richtungen in `series_name`) und Übergangszeilen vom
    20.08.2026 (`label` „Straße | …“).
  - Klassen ohne Fahrzeug fehlen in der Stunde (keine Nullzeilen); eine Stunde ganz ohne Zeile
    ist nicht gezählt – auch tagsüber fehlen Stunden, eine Woche fehlt an allen Stellen
    (164 Stunden). Vollständige Tage je Richtung: 17–56 von rund 80; Schillerstraße („Zone1–3“)
    und Durlacher Straße Richtung Durlach haben keinen.
  - Alle Richtungen eines Sensors haben dieselbe Lage → in der Karte übereinander; die
    Seitenleiste schaltet um (`amSelbenPunkt` in `js/data/dauer.js`).
  - `timestamp` ohne Zonenangabe, laut Datenbeschreibung UTC (der Tagesgang passt dazu).
  - Namen uneinheitlich („Strasse“, „Pforzheimer-Str-14“, „Rcihtung“) → Straße und Abschnitt je
    Sensor in der Quelldatei (`stellen`), die Richtung ohne den vorangestellten Straßennamen.
  - `classification` und `amount` sind unbrauchbar (fast überall „LKW+Anhänger“ bzw. 0).
- **Baden-Württemberg, Dauerzählstellen des Landes (in der Karte seit November 2026,
  `bw_land_kfz`, Adapter `bw_land`):** MobiData BW, Datensatz `stundenwerte_dauerzaehlstellen`
  (Verkehrsministerium, dl-de/by-2-0): ein ZIP je Monat seit Januar 2025 (laut DCAT-Dokument,
  rund zwei Monate Verzug; ältere Monate ersetzt das Land gelegentlich, am 08.05.2026 etwa
  September bis Dezember 2025 und Februar 2026 – der Adapter lädt nach dem Datum der Ressource
  neu), je Jahr 2016–2024 ein ZIP `Stundenwerte_JJJJ.zip` (45–54 MB; nicht im DCAT-Dokument, nur
  in der Beschreibung des Datensatzes; 2024 ein ZIP aus Monats-ZIPs) und das Gesamtarchiv
  `Stundenwerte_Archiv.zip` (468 MB, nicht gebraucht). Erkundet im Werkzeug-Branch `werkzeug/bw`
  (`tools/bw_dauer.py` bis `bw_dauer4.py`, `pruefe.sh`). Fallen:
  - **Format:** abgeleitet aus den Lieferungen an die BASt. Die Beschreibung des
    [BASt-Bestandsbandformats](https://www.bast.de/DE/Publikationen/Daten/Verkehrstechnik/Downloads/DZ-Beschreibung.pdf)
    (Version 2004) erklärt Kopfzeilen, Prüfkennzeichen und Statuskennung – MobiData verweist nur
    allgemein auf „die Internetseite der BASt“. Je Stelle und Monat eine CSV mit drei Kopfzeilen
    (Blatt, Nummer, Land, Straße, Name; Fahrstreifen, Fernziele, Himmelsrichtungen; Gruppen und
    Arten) und einer Zeile Spaltennamen; die Fahrstreifen sind über die Fahrbahn durchnummeriert,
    erst Richtung I, dann II. Kodierung UTF-8 oder Windows-1252 (rund ein Fünftel der Dateien);
    einmal „BY_…“ statt „BW_…“ im Dateinamen (Juli 2018).
  - **Prüfkennzeichen:** „-“ korrekt, „u“ korrekt, aber unregelmäßig (Großveranstaltungen),
    „a“ Ausfall, „d“ fehlerhaft, „s“ Schätzwert wegen fehlender, „k“ wegen fehlerhafter Werte,
    „z“ Zeitumstellung; dazu „h“, „t“ (ab 2026, „t“ nur in eingefügten Zeilen) und „S“, die die
    Beschreibung nicht nennt. Schätzwerte stehen oft einen ganzen Monat an einer Stelle; an
    manchen Monatsgrenzen trägt die erste oder letzte Stunde an rund der Hälfte der Stellen „k“
    (01.06.2024, 30.11.2024, 31.12.2024, 01.01.2025 – Werkzeug-Branch, `tools/bw_rand.py`). In der
    Karte zählt eine Stunde nur mit „-“ oder „u“ auf allen Fahrstreifen der Richtung: je Monat
    55–94 % der Tage je Richtung vollständig (2016 um 90 %, seit 2022 meist 60–75 %). Die
    Statuskennung „i“ (eingefügte Zeile, am Datum) gibt es erst ab 2026, dann auch bei Ausfällen.
  - **Zeit:** Ortszeit, die Uhrzeit ist das Ende der Stunde (01:00 = 0–1 Uhr). Frühjahr: Zeile
    03:00 mit 0 und „z“ (die Stunde gibt es nicht; ab 2026 mit „i“). Herbst: 2–3 Uhr nur eine
    Zeile mit „z“ – bis 2022 im Median das Anderthalbfache eines Sonntags davor (wohl beide
    Stunden), seit 2023 etwa eine; nicht gezählt, der Tag ist nicht vollständig.
  - **Klassen:** 8+1-Geräte: Gruppen KFZ und SV (= LoA + LmA + Sat + Bus) -> `kfz`, `sv`. 41
    Autobahn-Stellen 2017–2025 unterscheiden nur zwei Klassen: KFZ und LK (Lkw-ähnliche, im
    Januar 2024 „LKW“ geschrieben) -> `lkw`. Sie enden im Dezember 2025 (2026: 160 statt 196
    Stellen); 36 Autobahn-Stellen mit 8+1 Klassen laufen weiter.
  - **Kennung:** die Zählstellennummer (vier Ziffern, Nummer der BASt). Das Kartenblatt davor
    wechselt (Kappelberg-Tunnel 2026: 7121 -> 7221; Reutlingen, Großbottwar), die Straße bei
    Umstufungen (Horb-Nord B 14 -> B 28, Lörrach-Stetten B 317 -> Gemeindestraße, Großbottwar
    L 1115 -> B 328), der Name bei Autobahn-Stellen 2016 („Ma-Sa_W_V“). Die Fernziele beider
    Richtungen stehen erst ab 2026 im Kopf, vorher nur eines – mal das der einen, mal das der
    anderen Richtung – , deshalb ohne Fernziel nur die Himmelsrichtung.
  - **Lage:** keine Koordinaten in den CSV. Die Dateinamen tragen meist die SVZ-Nummer eines
    Abschnitts in den Grunddaten der Zählstellenkarte (`karte_strassenverkehrszaehlung`, CSV
    `SVZ-Zaehlstellen_…_augmented_SVZ2024.csv`: svznr, zstart DZ/MZ/TM, Straße, Punkt,
    Abschnitt von–bis), aber nicht verlässlich: Zwischen den Jahren springt sie bei rund zehn
    Stellen auf Nachbarabschnitte, oft temporäre Messstellen (TM) oder andere Straßen (Riegel 2026:
    K 5135 statt L 113). Regel im Adapter: Abschnitt aus den Dateinamen, Straße passt, nie TM, DZ
    vor MZ, der häufigste; sonst der einzige freie DZ-Abschnitt der Straße auf dem Kartenblatt
    (Simonswald, Tübingen West, Westumgehung Aalen). Ohne Lage bleiben 13 von 206 Stellen, davon
    neun 2026 noch in Betrieb: A 5 Achern, B 27 Filderstadt und L.-E.-Stetten (ein freier
    MZ-Abschnitt für beide), B 462 Weisenbach-Au, B 3 Kippenheim, L 221 Wollmatingen, L 117
    Grenzübergang Sasbach, Hornberg und Lörrach-Stetten (Gemeindestraßen) – Lage beim Land
    erfragen. Eine Overpass-Abfrage nach Verkehrszählstellen in ganz BW lief in die Zeitgrenze
    (nicht weiter verfolgt).
  - **Doppelte Dateien:** 2024 steht eine Stelle (8961) von Januar bis September unter zwei
    Namen mit gleichem Inhalt (einmal gezählt); im Oktober 2024 drei Stellen (8928, 8935, 8936)
    mit verschiedenem Inhalt – der Monat gilt dort als nicht gezählt.
  - **Lauf:** der erste Abruf lädt 30 Dateien (550 MB) in gut fünf Minuten (Crawl-delay 10 s),
    Lesen und Bauen rund drei Minuten bei höchstens 1,1 GB Speicher; danach nur neue oder
    ersetzte ZIPs (Cache im Workflow). Kartendaten der Quelle: 56 MB, gepackt 15 MB.
  - Daneben „Ergebnisse und Ganglinien“: Monats- und Jahres-DTV seit 2002 als Excel (Kandidat
    für `vizsim/svz`) und Ganglinien nur als PDF-Grafik.
- **Geprüft, nicht aufgenommen (Stand 12.11.2026,** Werkzeug-Branch `werkzeug/dauer`,
  `tools/dauer_staedte1.py`, `dauer_staedte2.py`):
  - **Osnabrück:** SensorThings `https://daten-api.osnabrueck.de/v1.1` mit KI-Sensoren an
    rund zehn Kreuzungen (Things „Verkehrszaehlung …“ je Fahrstreifen bzw. Abbiegestrom; PKWs,
    LKWs, Busse, Motorräder, Fahrräder, Personen; 15-Minuten-Werte seit 2023, Zeitstempel
    unregelmäßig zum Zeitpunkt der Übertragung). Lizenz: laut Mobilithek dl-de/by-2-0,
    Herausgeber SWO Netz GmbH (Angebot `-6042365511594508563`, aus GovData übernommen; am
    12.11.2026 zeigte der GovData-Eintrag keine Lizenz). Nicht aufgenommen, weil die Meldungen
    kein festes Raster haben: Abstände von gut 15 Minuten (rund 15:23), die Zeitstempel wandern
    durch die Stunde – volle Stunden lassen sich daraus nicht sauber bilden (Werkzeug-Branch
    `werkzeug/erkundung`, Runde `holen3`, 14.11.2026).
  - **Ulm** (`vgv_ulm`, CKAN-Datastore `datenhub.ulm.de`): eine Zeile je erkanntem
    Verkehrsteilnehmer (Zeit, Klasse, Kamera-Kürzel, Richtung), Millionen Zeilen. Keine
    Standorte, und ohne Betriebszeiten ist eine Stunde ohne Zeile nicht von einem Ausfall zu
    unterscheiden → nicht aufnehmbar.
  - **Heidelberg:** Kameradaten (TrafficFlowObserved, CC0) im CKAN der Datenplattform, aber die
    CKAN-API antwortet mit 404 (Metadaten zuletzt 2023); die Verkehrsrechnerdaten gibt es nur
    über eine API mit Schlüssel (`api-key` im MobiData-Eintrag) → nicht keyless.
  - **Freiburg:** WFS `digit_verkehrszaehl` nur mit der Ebene `zaehl_co2_aktuell` (letzte
    Werte vom Mai 2024, keine Reihe) – weiter Testbetrieb.
  - **Leipzig:** Die 24 Kfz-Dauerzählstellen nur im Dashboard, nicht als Daten. Die
    Rad-Zählstellen (nur die Stundenwerte der letzten 31 Tage im WFS, dazu Tageswerte zweier
    Jahre) sind seit November 2026 mit einem Gedächtnis wie Hamburg in der Karte (siehe unten);
    ebenso die Rad-Zählstellen von Mannheim, Aachen und Ulm.
  - **Darmstadt:** „Verkehrsdaten im Rohformat“ 2022–2026 (ein Datensatz je Jahr,
    dl-de/by-2-0) aus dem Verkehrsleitrechner: je Kreuzung ein ZIP mit Monats-CSV im
    Minutentakt, je Detektor Belegungen und Verweilzeit (Schleifen `D…`, Taster `TBS…`), laut
    Quelle ungeprüft mit Lücken und Ausreißern. Ein Querschnitt ergäbe sich erst, wenn jede
    Schleife ihrer Zufahrt und ihrem Fahrstreifen zugeordnet ist (Datensatz „Kreuzungspläne Stadt
    Darmstadt“, je Kreuzung von Hand) – zurückgestellt. Die „Verkehrssensoren“ bei sensoto.io
    sind die BASt-Zählstellen.
  - **Wiesbaden, Kaiserslautern:** keine offenen kommunalen Zeitreihen gefunden (das Portal
    `opendata.cloud.wiesbaden.de` war aus dem Workflow nicht erreichbar).
  - **Kiel:** 87 Kfz-Dauerzählstellen (Menge, Art, Fahrtrichtung; Minuten- und Stundenwerte) im
    DatenDock der KielRegion (Civora-Plattform, Dashboards über eingebettete Superset-Ansichten,
    keine offene Schnittstelle gefunden). In der Mobilithek das Angebot 995318989663924224
    („[alt]“, CC BY 4.0, seit 24.05.2026) und seit 09.10.2026 1045322209798569984 mit
    „LICENSE_RESTRICTED_USE_FREE_OF_CHARGE“, Freigabe durch den Anbieter nötig und Abruf über die
    Vermittlung der Mobilithek (Konto) → nicht keyless, nicht offen. Die Metadaten liefert
    `https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/<id>`, die Suche
    `POST …/v2/offers/search` mit `{"searchString": "…"}`.
  - **Osnabrück, TEU-Datensatz der Mobilithek** (903287344194932736): 66 Sensoren paarweise je
    Richtung (Pkw, Lkw, Lkw mit Anhänger), 01.01.2022–11.09.2023, Lizenz „other-closed“ → nicht
    nutzbar. Ebenso **Berlin Müllerstraße** (VMZ, Tageswerte 2019–2022, „other-closed“).
  - **Köln, Rüsselsheim, Gelsenkirchen:** nur Echtzeit (DATEX II) – bräuchte ein eigenes
    Archiv; Kölns „KFZ Zählstellen und Werte“ sind DTVw (svz).
  - **Konstanz, Gelsenkirchen:** laut svz (AGENTS.md § 3) nur Echtzeit-Zähler (DATEX II) – nicht
    weiter geprüft.
- **Rad-Zählstellen (in der Karte seit November 2026,** Werkzeug-Branch `werkzeug/dauer2`,
  `tools/rad_erkunden*.py`, Ergebnisse `ergebnis/rad*/`):
  - **Was als gezählt gilt:** Eco-Counter führt je Wert einen Status – `0` (Rohwert) und
    `validated` (geprüft) gelten als gezählt, `4` (rekonstruiert: in Münster Läufe bis zu fünf
    Wochen, das Muster der Auffüllung bei Ausfällen) und `modified` (von Hand geändert) nicht.
    Berlins Excel markiert per Zellfarbe (Blatt „Legende“: orange 0/unplausibel, hellgelb keine
    Daten, Theme-Farbe 5 rekonstruiert; Theme-Farbe 7 an der fehlenden Stunde der Sommerzeit) –
    openpyxl nur ohne `read_only`, die Theme-Farben haben kein RGB. MobiData BW, Aachen und
    München liefern keinen Status: MobiData nachweislich mit rekonstruierten Werten (Abgleich mit
    dem eingefrorenen älteren Format, Juni 2025, Status 4 in `channels_all` enthalten) → Hinweis
    an der Quelle; Aachen und München lassen Ausfälle leer bzw. `NA`.
  - **Zeitumstellung je Quelle prüfen** (Verhältnis 2 Uhr / Mittel aus 1 und 3 Uhr am
    Rückstelltag gegen andere Sonntage): MobiData (1,3–1,7 gegen 0,8–0,9), Münster (1,8 gegen
    0,9) und Berlin (1,7 gegen 0,9) fassen beide Stunden unter einer Uhrzeit zusammen →
    `setze_lokal(rueck="zusammen")`; München nicht (1,0–1,2) – eine Stunde fehlt, der Tag ist
    nicht vollständig (`rueck="einfach"`). München führt die fehlende Stunde der Sommerzeit mit
    Nullen (verworfen). Aachen liefert UTC (`setze_utc`).
  - **Kanäle:** Münsters Gesamtspalte ist die Summe der Kanäle (bis auf 86 von 3,7 Mio.
    Viertelstunden – dann nicht gezählt); alte und neue Schleifen und Formel-Kanäle stehen
    nebeneinander, Pkw-Kanäle (Bohlweg) sind leer. MobiData zählt in `channels_all` nur
    Rad-Kanäle (Pkw- und Personen-Kanäle in Ludwigsburg, Reutlingen, Böblingen nicht). Aachen:
    eigene Kanäle für Falschfahrer (Hohenstaufenallee) – gehören zur Zählstelle. Zählstellen,
    deren Name Fuß- und Radverkehr nennt, und ein Gerät neben seinen eigenen Zählstellen
    („Hardware für …“, gleiche Seriennummer) stehen in `ohne`. Die Stelle des
    Regierungspräsidiums Stuttgart in Bad Wimpfen (Land) ist seit dem 14.11.2026 in der Karte
    (alle Zählungen, gleich, wer zählt). Offen: Tübingens Unterführung Steinlach hat dieselbe Kanalstruktur wie der
    Fuß- & Radtunnel („Fahrräder IN/OUT“ und „Richtung …“), der Name nennt aber keinen Fuß.
  - **Lage:** MobiData, Berlin (Blatt „Standortdaten“) und München (WFS) mit Koordinaten,
    Münster über das GeoJSON der Stadt (`fahrradzaehl-standorte_0.geojson`, gleiche Kennungen),
    Aachen nur im PDF „Standorte Radzählstellen“ (pdfplumber; Annuntiatenbach dort mit Länge
    6,80208 statt 6,080208 – korrigiert über `lage`). Berlin: sechs frühere Kennungen ohne
    Standortdaten (02-MI-AL-W, 02-PA-SE-N, 03-SP-NO-O/-W, 17-SZ-BRE-O/-W) fehlen in der Karte.
  - **Formate:** MobiData je Monat `fahrradzaehler_stundenwerten_JJJJMM.csv.gz` seit 2013-01
    (Verzeichnis `mobidata-bw.de/fahrradzaehldaten/v2/`), Zeitstempel mit Versatz, `na` = nicht
    gezählt. Münster: GitHub `od-ms/radverkehr-zaehlstellen`, je Zählstelle Monats-CSV seit 2019
    (Archiv über `codeload.github.com`). Aachen: CKAN, eine CSV je Jahr (laufendes und voriges),
    zwei Ressourcen für dasselbe Jahr möglich → die jüngste. Berlin: eine Excel-Datei, ein Blatt
    je Jahr (das Blatt 2012 reicht bis Ende 2013). München: Jahresdateien „15 Minuten Werte JJJJ“
    (2008–2025, Paket „…Jahreszahlen“), fürs laufende Jahr Monatsdateien; Datum als 2008-06-01,
    20230101 oder 2024.01.01, 2022 mit einer Spalte `t` vorn, bis 2024 `kommentar`.
  - **Zweite Runde (in der Karte seit November 2026,** Würzburg, Rhein-Kreis Neuss, Dortmund,
    Essen, Leipzig, Rostock, Bochum; `tools/rad_erkunden12–14.py`, Ergebnisse
    `ergebnis/rad12–14/`):
    - **Würzburg, Rhein-Kreis Neuss** (`ods_eco`): Opendatasoft-Export (`…/exports/csv?select=…
      &timezone=UTC`), Eco-Counter-Stunden in UTC. Status Würzburg als Liste (`["raw"]`,
      `["deleted"]` ohne Wert), Neuss als Text (`raw`, `modified`, leer). Würzburg: rund 1.000
      doppelte Stunden (45 mit verschiedenen Werten), eine Stelle ohne Standort (100020242,
      fast nur „deleted“), Hunderte ganzer Tage mit 0 in Heidingsfeld; die Radar-Sensoren
      (LoRaWAN, Datensatz `fahrradzaehlung`) melden ohne festes Raster – nicht aufnehmbar. Neuss:
      vier bis sechs Kanäle je Station über die ganze Laufzeit, der Datensatz der Zählstellen
      ist leer (Lage aus `coordinates` der Daten), seit dem 05.07.2026 nicht aktualisiert; am Tag
      der Sommerzeit eine leere Zeile zur selben UTC-Stunde wie eine gezählte (leere Zeilen
      zählen nicht mit).
    - **Rückstellung der Uhr:** In Würzburg, Neuss, Dortmund und Bochum fehlt die erste der
      beiden Stunden 2–3 Uhr (in UTC 0 Uhr), Essen und Düsseldorf (in der dritten Runde auch
      Bonn) führen 2 Uhr einmal. Ob diese eine Stunde beide enthält, ließ sich nicht klären
      (Verhältnis 2 Uhr / Mittel aus 1 und 3 Uhr am Rückstelltag streut zu stark,
      `ergebnis/rad14/rueckstellung.txt`) → der Tag ist nicht vollständig. Leipzig führt beide
      Stunden einzeln, Rostock unvollständig.
    - **Dortmund** (Schnettkerbrücke): `zeitpunkt_utc` ist trotz des Namens die Ortszeit mit
      Versatz, `zeitpunkt` dieselbe Ortszeit als UTC ausgewiesen; am Tag der Sommerzeit stehen
      leere Zeilen 2:00–2:45 Uhr (+01:00). Lage nicht im Datensatz und nicht auf dortmund.de –
      OSM-Knoten 5639350907 („Dauerzählstelle Radverkehr“, Verweis auf die Eco-Counter-Seite),
      gefunden über Overpass (`ergebnis/rad14/osm.txt`).
    - **Essen:** Quartals-CSV über Open.NRW (`radverkehrszahlungen-e`), Lizenz je Ressource:
      2018–2020 „other-closed“, ab 2021 dl-de/by-2-0. Spalten 1+2 Grugatrasse, 3+4 Huyssenallee
      (belegt durch die kumulierten Jahresdateien); 2026 heißt Spalte 2 fälschlich „Huyssenallee
      Stadtkern_Nord“, 2023 Q4 mit Tab. Lage als Gauß-Krüger in der Beschreibung (umgerechnet mit
      pyproj, EPSG:31466 → 4326, Werte in der Quelldatei).
    - **Leipzig:** WFS `radverkehr_dauerzaehlstelle_anzahl_stunde_zeitreihe` (31 Tage, Ortszeit
      ohne Versatz) → Gedächtnis wie Hamburg (`dauer/gedaechtnis.py`). Am Rückstelltag 2 Uhr
      zweimal (objectid folgt der Zeit); 0 Uhr des Folgetags kommt mit der nächsten Lieferung
      (`fme_tstamp`) erneut, oft mit anderem Wert → es gilt die jüngste Lieferung. Lage in UTM 33
      (`koordinaten.utm_zu_wgs84`).
      **Tageswerte** (`…_anzahl_tag_zeitreihe`, „pro Tag der letzten 2 Jahre bis einschließlich
      gestern“, seit #30 in der Karte): `phenomenontime` ein Datum, eine Lieferung je Tag mit dem
      ganzen Fenster (am 15.11.2026: 14.11.2024–14.11.2026, 14.794 Zeilen, 26 Stellen, keine
      Doppelten). Der Tag ist der **UTC-Tag**: An allen 927 Tagen, deren 24 UTC-Stunden im
      Gedächtnis stehen, ist der Tageswert genau deren Summe (die Stunden kommen in Ortszeit) –
      daher wichen sie von der Summe 0 bis 24 Uhr ab (61 % höchstens 1 %, 98 % höchstens 10 %).
      In der Karte als Tageswert der Quelle vor der ersten gezählten Stunde (bis 07.10.2026), mit
      dem UTC-Tag im Verfahren; Gedächtnis `tage_JJJJ.csv.gz`, weil das Fenster wandert. Jahnallee
      (300023813): keine Stunden, Tageswerte bis 20.09.2026, seit November 2025 fast nur 0 (213
      Nullen) – wie geliefert, Hinweis. Lizenz: die Seiten der Datensätze nennen keine, die
      Metadaten je Ressource beider Datensätze dl-de/by-2-0 (`ergebnis/rad12/leipzig.txt`,
      `werkzeug/dauer2`); die CKAN-API sperrt robots.txt inzwischen, die Seiten nicht
      (`tools/seiten.py`, `ergebnis/leipzig_tage/` in `werkzeug/dauer`).
    - **Rostock** (Radmonitore, CC0): eine CSV mit 5,4 Mio. Viertelstunden seit 2012, Zeit
      „2013/07/15 22:15:00+02“, keine Doppelten. Holbeinplatz und Lange Straße laut Quelle Summen
      zweier Querschnitte; Saarplatz Lindenpark („Steuergerät“) liegt täglich etwas über Saarplatz
      Nord (100 m entfernt) → `ohne`. Hinrichshagen, Markgrafenheide und Graal-Müritz liegen am
      selben Punkt (drei Wege), Graal-Müritz mit 174 ganzen Tagen 0.
    - **Bochum** (GitLab openCode, `StadtBochum/open-data/radverkehr-zaehlstellen-eco-counter`):
      Lizenz laut bochum.opendata.ruhr und README dl-de/by-2-0, in Open.NRW „other-closed“, die
      LICENSE-Datei CC0; dazu die Klausel „Nutzung … im direkten Wettbewerb zu Eco-Counter nicht
      gestattet“ → steht in `lizenz` (Seitenleiste, CSV). Die Stadt wählt je Richtung einen
      Kanalblock („pick best block“); an der Springorumtrasse Süd vermutet sie fehlende Kanäle →
      `ohne`. An einzelnen Tagen nur volle Stunden (Viertelstunden leer) – nicht gezählt.
  - **Dritte Runde (Bonn, Düsseldorf; Werkzeug-Branch `werkzeug/dauer`,
    `tools/rad_erkunden15–16.py`, Ergebnisse `ergebnis/rad15–16/`):**
    - **Bonn** (`bonn_rad`, CC0): Katalog `opendata.bonn.de/data.json`, je Jahr ein Datensatz
      „Fahrradmessstellen Ergebnisse Radzählungen JJJJ“ mit Stunden- und teils
      15-Minuten-Auswertung (Stunde = Summe der vier Viertelstunden, geprüft 2020, 2023, 2024).
      Zeit „01.01.2025 00:00“ oder „1. Jan. 2024 00:00“ (2021 „Febr.“). Spalten „N.NN BN - Name“,
      dahinter die Summen der Brücken (Kennedy-, Nord-, Südbrücke = ihre zwei Seiten, an jeder
      Stunde) und „Summe“. Sommerzeit: 3 Uhr zweimal, die erste Zeile leer; Rückstellung: 2 Uhr
      einmal. 2022: nur je Kanal, und alle Kanäle einer Stelle zählen gleichzeitig („Radfahrer
      Ri. …“ und „[Bike IN]/[Bike OUT]“, teils doppelt) – nicht übernommen. 2019: bei Open.NRW
      „other-closed“, Mac-Roman mit CR – nicht übernommen. Der Datensatz „Vortag“ (Stadtplan-CSV)
      ist nur ein Tag. Lage: Der Stadtplan (`stadtplan.bonn.de/geojson?Thema=22640`) antwortete in
      zwei Läufen nur mit 502; OSM hat alle Zählstellen der Stadt als `monitoring_station` mit
      `ref` = Kennung (5.12 Straßburger Weg ohne Werte, 5.16/5.17 noch ohne Jahresdatei). Auffällig:
      Mc Cloy Weg Juni–August 2025 mit 10.000–52.000 am Tag (sonst 1.500–4.000), Südbrücke 2020
      mit 125 bzw. 169 Nulltagen – Hinweis an der Quelle, Werte wie geliefert.
    - **Düsseldorf** (`duesseldorf_rad`, dl-de/by-2-0 ab 2020; 2012–2019 „other-closed“): Pakete
      `wetterabhangige-jahresubersicht-der-dauerzahlstellen-radverkehr-JJJJ-d` auf Open.NRW, kein
      Paket 2022; Lizenz je Ressource (2020 Koblenzer stadtauswärts und Koblenzer Straße
      geschlossen). Formate: 2020 `Zeit;Stunde;Anzahl`, 2021 `datum;stunde;anzahl` (Datum auch
      „1012021“) oder `Zeit;<Stelle>`, ab 2023 `Zeit;<IN>;<OUT>` mit „26-03-2023 01:00:00“; Werte
      vor der ersten Wetter-Spalte. Summen, aus den Tagessummen belegt: Fleher Deich Rampe = Ost +
      West, Oberkasseler Brücke = OKB Nord + Süd, Koblenzer Straße (2023) = die drei Koblenzer
      Stellen; 2024 steht bei Fleher Deich und OKB Süd vorn eine Summenspalte. 2021 ist „Koblenzer
      einwärts nach TLS“ eine Kopie von „vor TLS“. Sommerzeit 2020/2021: 3 Uhr zweimal, eine Zeile
      leer („weather_condition_null“); ab 2023 fehlt 2 Uhr; Rückstellung: 2 Uhr einmal. Luegallee
      2025 und Friedrichstraße 2023 nur mit 0 (Luegallee 2024 meist). Kaputte Zeilen (Fleher Deich,
      Mannesmannufer 2020) gelten als nicht gezählt; am Mannesmannufer 2020 stehen viele Stunden
      doppelt (rund 4.500) – nur 42 Tage vollständig. Lage: „Standorte der Dauerzählstellen
      Radverkehr“ (dl-de/zero-2-0, `Zählstellen_2.csv`), Hofgartenrampe und Luegallee aus OSM;
      Kölner Straße 186 und Pempelforter Straße 42 (ab 2025 mit Werten) ohne Lage. Der Server
      lehnt Abrufe zeitweise ab („Connection refused“) – Wiederholungen und Cache im Workflow.
  - **VMZ Niedersachsen** (`vmz_rad`, ohne Lizenz – nur „© VMZ Niedersachsen“ in der Fußzeile;
    Hinweis der Projektleitung 14.11.2026; Werkzeug-Branches `werkzeug/erkundung`, `tools/holen.py`
    Runden 4–6, und `werkzeug/dauer`, `tools/vmz_pruefen.py`, Ergebnis `ergebnis/vmz/`):
    - **Zählstellen:** Die Seite `/niedersachsen/radzaehler/` trägt die Karte als Startzustand
      (`JSON.parse('…')`, darin `reHydratedState.featureSources["niedersachsen-radzaehler"].data`,
      eine FeatureCollection mit `externalId`, `name`, `group`, `source`). Dieselbe Liste unter
      `/geojson/` sperrt robots.txt (dazu `/typo3`, `/nachricht`; kein Crawl-delay). 74 Zählstellen
      in Gruppen: die Regionen der Landesbehörde (NLStBV) `20_Nordwest` 12, `30_Nordost` 9,
      `40_West` 7, `50_Südost` 8 an Bundes- und Landesstraßen; `60_Region Hannover` (vier an
      Kreisstraßen, dazu B 217); `70_Stadt Hannover` (13 der Stadt, dazu B 6 Garbsen und L 389
      Wülfel; Schwarzer Bär Süd steht doppelt); `zzz_…` für Braunschweig 8, Verden 4, Gellersen 4,
      Rotenburg (Wümme) 1, Jemgum 1 (die letzten beiden NeoCount). `source` nennt den Lieferweg,
      nicht den Betreiber („NLSTBV“ auch bei Braunschweigs Stadtstraßen).
    - **Werte:** `https://www.vmz-niedersachsen.de/msp/public/count-aggregator/wheel-counter/`
      `values/<von>/<bis>/<hourly|daily|weekly|monthly|yearly>?stationIds=<id>,…` – JSON je
      `externalId` mit `values: [{datetime: "2025-10-25 00:00:00", value: "30"}]` (Ortszeit, Wert
      als Text); mit `format=csv` eine Tabelle `"Zeitpunkt ('Y-m-d H:i:s')";"<Name>";…`, leere
      Zelle = kein Wert. Vom Endtag kommt nur die Stunde ab 0 Uhr (`toDateTime` = Beginn des
      Endtags) – je Jahr bis zum 1.1. des Folgejahrs abrufen, sonst fehlt der 31.12. Ein Jahr für
      zehn Zählstellen sind rund 4 MB; alle Jahre seit 2017 für alle Stellen: 740 Dateien, 75 MB,
      knapp zwei Minuten. Daneben `problems/<von>/<bis>?stationIds=…` (bisher nur
      `missing_data`, ganze Tage), `last-values/`, `last-problems/`.
    - **Zeit:** Sommerzeit: 2 Uhr fehlt (drei Einträge um 2 Uhr in zehn Jahren); Rückstellung:
      2 Uhr steht einmal (`rueck: einfach`, der Tag gilt als nicht vollständig).
    - **Stand 14.11.2026:** 2,4 Mio. Stunden, alle 74 Zählstellen mit vollständigen Tagen; Hannover
      seit 2017, Region Hannover seit Juli 2018, die Landesbehörde seit Ende 2023 bzw. 2024,
      Braunschweig seit 2024. Seit dem 25.10.2026 keine neuen Werte außer Jemgum und Rotenburg.
      Lange Folgen von Tagen mit lauter Nullen, die die Quelle nicht als Störung führt (Kleefelder
      Straße 2024: 93 Tage, L 826 Rastede 2026: 81, K 139 Ilten 2024: 61) – Werte wie geliefert,
      Hinweis an der Quelle. Braunschweigs Datenportal hat dieselben Zählstellen nur als
      Tageswerte (CC BY 4.0).
  - **Dresden** (`dresden_rad`, ohne Lizenz – die Schnittstelle nennt keine, das Open-Data-Portal
    ist nicht geprüft; Entscheidung der Projektleitung 14.11.2026: erst einmal ohne Lizenz zeigen;
    Werkzeug-Branch `werkzeug/erkundung`, `tools/holen.py` Runden 4–8):
    - **Schnittstelle:** OGC API des Themenstadtplans (cardo,
      `https://kommisdd.dresden.de/net4/public/ogcapi/collections/`). Ebene `L1780` „Radverkehr –
      Dauerzählstellen – alle Zählwerte (veröffentlicht)“: eine Zeile je Zählstelle und Stunde mit
      `ids`, `fremd_id`, `bezeichnung`, `lage`, `status`, `r1`/`w1`, `r2`/`w2`, `messzeit`, Punkt.
      `L1781`: je aktiver Zählstelle der jüngste Wert mit Lage (Objekt-ID = `ids`). Der Pfad
      braucht `collections/` (`/ogcapi/L1780/items` antwortet „NotSupportedException“).
      robots.txt sperrt nur Spatineo; aus der Sandbox nicht erreichbar. Der Server braucht je
      Jahresabfrage ein bis zwei Minuten (alle 18 Jahre seit 2009: 27 Minuten, 48 MB; danach je
      Woche nur das laufende Jahr und das Vorjahr).
    - **Abfragen** (Doku: cardogis.com/WFS3Server): `limit` ohne Obergrenze, kein `offset`, keine
      Folgeseiten; `filter` in der Syntax des Servers (`ids==1077 and
      messzeit>="2025-01-01T00:00:00"`, `In(...)`, Zeichenketten in doppelten Anführungszeichen,
      Zeiten nur als ISO – „14.11.2026 12:00:00“ ergibt einen Fehler); `format=csv`,
      `delimiter=Semicolon`, `propertynames=…`. Leerzeichen als `%20` kodieren. Ein Jahr aller
      Stellen mit vier Spalten: 270.000 Zeilen, 8 MB. Die Zeilen-ID `id` vergibt der Server bei
      jedem Aufbau der Ebene neu (je Zählstelle ein Block, Lennéstraße 1–77.223) – kein Schlüssel,
      kein Weiterlesen ab der letzten ID.
    - **Zeit:** CSV und Filter in Ortszeit, 0 Uhr nur als Datum („2025-10-26“); GeoJSON zeigt
      dieselbe Zeile in UTC und deutscher Schreibweise (CSV „2017-10-10 12:00:00“ = GeoJSON
      „10.10.2017 10:00:00“). Sommerzeit: 2 Uhr fehlt; Rückstellung: 2 Uhr einmal (2018–2024).
      Seit 2025 an den Umstelltagen zusätzliche Zeilen mit krummer Minute (Lennéstraße
      „2025-10-26 02:13:00“, „2026-03-29 03:11:00“, Löbtauer Straße „2025-03-30 03:05:00“) und
      vereinzelt sonst („2026-05-19 04:09:00“; 2009–2026 zusammen 107) – keine Stundenwerte, ihre
      Stunde gilt als nicht gezählt. Ob die Uhrzeit Beginn oder Ende der Stunde ist, sagt die Quelle nicht: an Werktagen
      ist die Stunde ab 8 Uhr die stärkste am Morgen (126 gegen 49 ab 7 Uhr an der Lennéstraße) –
      das passte auch zu Endzeiten. Die Karte nimmt die Uhrzeit wie geliefert als Beginn.
    - **Stand 14.11.2026:** 38 Zählstellen, die ersten seit 25.09.2009 (2009 zwei, 2017–2023 rund
      neun, Mitte 2024 schon 23; vor dem 25.09.2009 keine Zeile), 35 in Betrieb; nicht mehr: St. Petersburger Straße („Historisch“), Carolabrücke (nur eine Richtung,
      „Inaktiv“), Rathenauplatz Ost („Inaktiv“). Keine leeren Werte, keine Doppelten; Lücken von
      Stunden bis Monaten (Lennéstraße Januar bis April 2023). Jüngster Wert rund eine Stunde alt.
    - Die Kfz-Dauerzählstellen der Stadt sind nur als Mittelwerte in der Verkehrsmengenkarte offen
      (Ebenen „Kfz/Tag HIN/RÜCK“) – Fall für `vizsim/svz`.
  - **Neuss, Radschnellweg RS5** (`neuss_rad`, Stadt Neuss, CC BY-SA 4.0 laut Portal – die
    Mobilithek, Angebot `-1611162702897177411`, führt den Datensatz ohne Lizenz; Hinweis und
    Beschluss der Projektleitung, 14.11.2026): Opendatasoft-Datensatz
    `stadt-neuss-radzaehlstelle-radschnellweg-hammer-landstrasse` im Portal des Rhein-Kreises
    Neuss (robots-Ausnahme wie `rhein_kreis_neuss_rad`), Adapter `ods_stunden` (Felder `date`,
    `counts`). Ein Wert je Stunde seit dem 03.07.2026, keine Doppelten, keine Richtung (die
    Beschreibung nennt „Querungen … nach Fahrtrichtung“); Rückstellung: eine der beiden Stunden
    2–3 Uhr fehlt. Median eines vollen Tags 787, höchster 1.255 (bis 13.11.2026). **Lage:** nicht
    im Datensatz (nur der Gemeindeschlüssel), keine Zählstelle in OSM (Overpass, Ausschnitt
    Hammer Landstraße, `ergebnis/ohne_lizenz/holen15–16/` auf `werkzeug/erkundung`). Der RS5 läuft
    in Neuss an der Hammer Landstraße zwischen den Einmündungen Industriestraße und
    Langemarck-/Danziger Straße (OSM-Knoten 266565345 und 1692302391, rund 500 m; Pressemitteilungen
    der Stadt 2022–2025) und biegt dort in die Langemarckstraße – in der Karte die Mitte dieses
    Abschnitts, mit Hinweis „Lage ungefähr“. Die genaue Lage weiß die Stadt (Funktionsadresse
    opendata@stadt.neuss.de laut Portal).
  - **Augsburg, Radzählstationen** (`augsburg_rad`, Stadt Augsburg, Radverkehrsbeauftragter, CC BY
    4.0 laut Mobilithek, Angebot `-4859503742463304999`; die erste Quelle nur mit Tageswerten):
    eine CSV auf augsburg.de (`…/Smart_City/opendata/fahrradzaehler_augsburg-seit-start.csv`).
    Zeile 1 „Zeitraum,16. September 2016 - 11. August 2026“, dann der Kopf – nicht gequotet, „Südlich
    A8-Unterführung, Ostseite“ zerfällt an seinem Komma: Die Quelldatei nennt die zwölf Stationen in
    der Reihenfolge der Spalten, der Kopf muss genau passen. Je Tag eine Zeile, leer = nicht
    gezählt. Der letzte Tag ist der Tag der Erstellung, nur zum Teil gezählt (11.08.2026: 3 bis 556)
    → nicht übernommen. Die Datei endet am 11.08.2026 (wie die Annastraße), obwohl die Mobilithek
    tägliche Aktualisierung nennt. Stand 14.11.2026 (`tools/quelle_pruefen.py`,
    `ergebnis/augsburg_rad/` auf `werkzeug/dauer`): 3.617 Zeilen, 30.308 Tageswerte, im Median 536
    (Postillionstraße) bis 2.450 (Konrad-Adenauer-Allee) am Tag, höchster 6.291; Tage mit 0 fast nur
    an der Dieselbrücke (19, vermutlich Ausfälle – Hinweis). Lage: keine Koordinaten in der Quelle und keine Zähler in OSM →
    Punkte nach der Beschreibung der Station über die OSM-Straßen (Overpass,
    `ergebnis/ohne_lizenz/holen17–22/` auf `werkzeug/erkundung`); „Südlich A8-Unterführung,
    Ostseite“ ist der Geh- und Radweg am Ostufer des Lechs (Radverkehrsmaßnahmen 2020 der Stadt):
    A8-Brücke bei 48,4142° N (OSM-Wege 27394066/27394069), der Weg am Ostufer (24859272) endet
    nördlich davon – Punkt rund 100 m südlich der Brücke, „Lage ungefähr“. Ebenso ungefähr die
    Friedrich-Ebert-Straße: „östlich Haltestelle Messe“ passt zu „Messe DB“ wie zu „Messe Süd“ –
    Punkt dazwischen. Die übrigen Punkte: Brückenmitte (Diesel-, Ulrichsbrücke), Einmündung
    (Färber-/Gollwitzerstraße), 60 m von der genannten Kreuzung in die genannte Richtung, Mitte
    der Fahrradstraße Konrad-Adenauer-Allee bzw. des Wegs Wagenhalsstraße (laut Stadt „hinter der
    City-Galerie“), Haunstetter Straße am nächsten zur Mitte des Protestantischen Friedhofs.
    Overpass antwortete abends oft nicht (Zeitgrenze, 504) – kleine Abfragen gingen eher durch.
  - **Fuß (seit November 2026, Entscheidung der Projektleitung):**
    - **Augsburg** (`augsburg_fuss`, CC BY 4.0, Mobilithek-Angebot `-1747083335311792689` der
      Wirtschaftsförderung): eine CSV auf augsburg.de
      (`…/Smart_City/opendata/240429/Annastraße_Frequenzdaten.csv` – das Datum im Pfad täuscht,
      die Datei wird fortgeschrieben, zuletzt 11.08.2026), `Standort;Jahr;Datum;Stunde;Passanten`
      („Annastraße;2020;Mi., 16.12.2020;13 Uhr;521“), UTF-8 mit BOM, Ortszeit, ein Standort.
      Keine Stunde hat 0, es fehlen Stunden fast nur nachts (2–4 Uhr, sonst Werte 1–3): vermutlich
      Stunden ohne Passanten – nicht aufgefüllt, 2021 ist so fast jeder zweite Tag nicht
      vollständig. Rückstellung: 2 Uhr einmal, mal mit beiden Stunden (2023, 2024: rund das
      Doppelte von 1 und 3 Uhr), mal nicht – `rueck: einfach`. Eine Stunde doppelt (09.10.2025, 13
      Uhr). Lage: Mitte der Fußgängerzone laut OSM (Weg 265870758; Overpass über kumi.systems mit
      Ausschnitt – die Abfrage über die Fläche „Augsburg“ lief bei allen drei Servern in die
      Zeitgrenze; Photon sperrt per robots.txt alles). Median eines vollen Tags 17.600, höchster
      50.495.
    - **Bochum** (`bochum_rad`): die Spalten `passanten_in`/`passanten_out` an fünf Stellen
      (Springorumtrasse, Erzbahntrasse, Hofsteder Bach, Lothringentrasse, Blücherstraße) als
      Gruppe `fuss`, je Richtung wie Rad. An der Springorumtrasse sind die Passanten-Spalten bis
      Oktober 2023 leer. Erzbahntrasse: seit Juni 2026 Tagessummen von 0 bis über 100.000 (sonst
      rund 250–300) – Hinweis an der Stelle, Werte wie geliefert.
    - **Würzburg** (`wuerzburg_fuss`, Passantenzählung von hystreet.com, dl-de/by-2-0, im Portal
      „hystreet.com GmbH“ als Quelle genannt → Quellenvermerk; robots-Ausnahme wie `wuerzburg_rad`,
      Beschluss der Projektleitung 14.11.2026): Opendatasoft-Datensatz
      `passantenzaehlung_stundendaten`, generischer Adapter `ods_stunden` (Felder `timestamp`,
      `pedestrians_count`, `location_id`; Lage aus `geo_point_2d`, als Zahlen in der Quelldatei).
      Drei Standorte (Schönbornstraße 135, Spiegelstraße 470, Kaiserstraße 476), 01.01.2024 bis
      17.05.2026 – seither nicht fortgeschrieben (`data_processed` 18.05.2026, Stand 14.11.2026).
      Keine Doppelten; am Rückstelltag fehlt eine der beiden Stunden 2–3 Uhr, um den Jahreswechsel
      2025/26 fehlen ganze Tage. Volle Tage: 1.765 (Stellen × Tage), im Median Schönbornstraße
      25.105, Kaiserstraße 21.822, Spiegelstraße 14.335, höchster 67.169. **`unverified`:** 79 %
      der Zeilen, nach Ortszeit 0–20 Uhr zu 92 %, 20–24 Uhr zu 0–7 %, an allen drei Standorten
      gleich – vermutlich übernimmt das Portal die Stunden eines Tages gegen 20 Uhr, solange
      hystreet sie noch nicht geprüft hat, und zieht sie nicht nach. Als „nicht gezählt“ blieben
      nur 180 volle Tage (Stellen × Tage), der jüngste im Januar 2025.
      Das Kennzeichen sagt also nicht, dass ein Wert falsch ist: gezählt wie Rohwerte (Münster,
      Würzburg Rad); Ausfälle stehen teils als 0 (Schönbornstraße 15.05.2026, 12 Uhr: 0 zwischen
      3.822 und 4.790) – Hinweis an der Quelle. Die Verteilung des Kennzeichens zeigt
      `tools/quelle_pruefen.py` (Abschnitt „Kennzeichen“, Branch `werkzeug/dauer`).
      **Tagesdaten** (`passantenzaehlung_tagesdaten`, seit #31 als Tageswerte der Quelle vor den
      Stunden): 4.912 Zeilen, Schönbornstraße 01.01.2020–17.05.2026, Spiegelstraße ab 07.09.2022,
      Kaiserstraße ab 29.09.2022, je 31 Tage Lücke, keine Doppelten; `timestamp` ein Datum, der
      Tag ist der **Ortstag** (gleich der Summe der Stunden 0–24 Uhr an 1.137 Tagen, des UTC-Tags an
      3); `unverified` durchweg 0 – die Tagesdaten sind geprüft, die Stunden großenteils nicht: an
      64 % der vollständig gezählten Tage 2024–2026 gleich der Summe der Stunden, 76 % innerhalb
      ±1 %, 89 % ±5 % (Ausreißer an Tagen mit Ausfall in den Stunden, etwa 0 am Mittag). In der
      Karte 2.401 Tageswerte (135: 1.461 aus 2020–2023, 470: 481, 476: 459). Die Datensätze je
      Standort (`passantenzaehlung_schoenbornstrasse`, `…_kaiserstrasse`, `…_spiegelstrasse`)
      halten nur die **letzten 24 Stunden** vor (Felder `timestamp`, `pedestrians_count`, Wetter;
      die Stunden des laufenden Tags nach der aktuellen stehen als 0 da) – mit dem wöchentlichen
      Lauf nicht zu sammeln. Monatsübersicht `passantenzaehlung_wuerzburg` seit April 2019 (nur
      Monatssummen). Erkundet mit `tools/ods_erkunden.py` (`werkzeug/dauer`,
      `ergebnis/ods_wuerzburg_fuss/`, Abrufe der App mit der robots-Ausnahme der Quelle).
    - Weitere Kandidaten: Freiburg (FR.ITZ, Rad und Fuß getrennt), die Personen-Kanäle im Bündel
      von MobiData BW (Ludwigsburg, Reutlingen, Böblingen).
  - **Nicht aufgenommen (zweite Runde):** Oldenburg (Tag,
    Monat, Jahr), Köln (nur Monatssummen 2009–2022, jüngere Werte nur bei Eco-Counter), Kiel (Rad:
    sechs Stationen, nur der Vortag und nur über die Vermittlung der Mobilithek mit Konto; das neue
    Angebot „LICENSE_RESTRICTED_USE_FREE_OF_CHARGE“), Jena (keine offene Schnittstelle gefunden),
    Nürnberg (nur die Eco-Counter-Seite). Dieselben Zähler wie im
    MobiData-Bündel, also doppelt: Konstanz (Jahres-CSV CC0 – Herosé, Bahnhaltepunkte Fürstenberg
    und Petershausen, Alte Rheinbrücke, Friedrichstraße), Heidelberg (CKAN-API 404), Ulm
    (Lupferbrücke, eingestellt), Mannheims Portal (ohne Lizenzangabe). Nicht offen als
    Stundenwerte: Hessen Mobil (Rad-Zählnetz des Landes, etwa die Hälfte der Stellen kommunal –
    siehe Sackgassen, Hessen; ohne Lizenzangabe; Export der Diagrammwerte je Stelle – Tage, Wochen,
    Monate;
    `hessen-mobil.eco-counter.com` sperrt Abruf-Werkzeuge per robots.txt) und Bielefeld – dort
    hilft eine Anfrage (Eco-Counter-Kunden haben in Eco-Visio einen Export). Nur Summen:
    Mannheims Portal (Summe je Zähler), Stuttgarts Portal (Saisons).
- **Nicht kommunal (dokumentiert, nicht in der Karte; seit 14.11.2026 Kandidaten):** Baden-
  Württembergs Landes-Dauerzählstellen sind seit November 2026 in der Karte (oben). An
  Autobahnen und Bundesstraßen sind es vermutlich dieselben Stellen wie bei der BASt (nicht
  geprüft) – vor einer BASt-Quelle abgleichen, sonst stehen sie doppelt in der Karte.
  - **BASt:** Stundenwerte 2003–2024 je Jahr und Straßenart, Rohdaten je Monat
    (`DZ_JJJJ_MM_Rohdaten.zip`, rund 80 MB) – ohne formale Lizenz, nur die Bitte um
    Quellenangabe.
  - **Länder:** Schleswig-Holstein (BASt-Dateien je Stelle und Jahr im Landesportal, etwa
    „Automatische Zählstelle Kiel-West“, dl-de/by-2-0), Bayern (BAYSIS), Nordrhein-Westfalen
    (`opendata.strassen.nrw.de/Verkehrsdaten/Dauerzaehlungen/`), Brandenburg
    (Verkehrsstärkedaten). Bielefeld: Rohdaten einer Verkehrszählstelle am Ostwestfalendamm im
    BASt-Format (Open.NRW) – eine Stelle; ob die Stadt sie betreibt oder sie zum Zählnetz von Bund
    und Land gehört, ist nicht geprüft.
