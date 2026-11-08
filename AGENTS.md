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
- **Zählsoftware:** München und Wolfsburg nutzen DAVe (Open Source, Export in offene Formate)
  – dort lohnt eine Anfrage nach dem Export statt nach PDFs.

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
- **Münster PDF** (`muenster_pdf`): Ausdrucke derselben Excel-Vorlagen. Senkrechte Tabellen
  stehen gedreht im PDF – pdfplumber liest sie rückwärts („zfK“, „0301“), solange man die
  Zeichen nicht je Drehrichtung mit `char_dir_rotated="btt"` bzw. `"ttb"` zusammensetzt.
  Spalten über die Tabellenrahmen (dünne Rechtecke), nicht über Textmitten: Beschriftungen
  stehen linksbündig, Zahlen rechtsbündig. 2017 gibt es eine Vorlage nur mit Kfz, Pkw, SV;
  Radar-Berichte („Class/Volume Report“, 48 h, ohne Knotennummer) und Scans liest der
  Adapter nicht.
- **PDF je Knoten** (Potsdam, Rostock-Lieferung, Magdeburg-Angebot): braucht einen
  PDF-Tabellen-Leser; noch kein Adapter (Ansatz wie `muenster_pdf`).

## Fallstricke (gemessen)
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
  dl-de/by-2-0. Immer beim Portal der Kommune nachsehen.

## Sackgassen
- mobidata-bw.de, GovData, opendata.potsdam.de, opendata.stadt-muenster.de und kmk.org sind
  aus manchen Entwicklungsumgebungen nicht erreichbar (Proxy). Abruf dann über GitHub Actions (`zaehlkarte fetch` im Workflow
  „Kartendaten neu bauen“). Braucht man die Rohdateien selbst in der Sandbox: der Workflow aus
  Commit e6f7280 (`tools/mobidata_holen.py`, früher Branch `werkzeug/mobidata`) legt sie auf
  einen Branch, den man dann per `git fetch` holt.
- Leipzig 2023: Ablehnung, weil die Karte keinen Export hat – nicht nach „den Daten der
  Karte“ fragen, sondern nach den gelieferten Zählauswertungen der Büros.
- Dortmund gibt Werte nur gegen Gebühr heraus; offen ist nur der Zählstellenplan.

## Rechtliches (Stand 2026, keine Rechtsberatung)
Bayern und Niedersachsen haben kein Landes-IFG; in Sachsen und Hessen gilt es für Kommunen
nur per Satzung. Das UIG gilt überall – Zählungen gehen in die Lärmkartierung ein, darum mit
anführen. Sachsen: LfULG-Handlungsempfehlung (Mai 2026) verlangt Intervallwerte als CSV/XLSX
von beauftragten Büros. Kurzfassung je Land: `recht:` in `pipeline/config/sources.yaml`.
