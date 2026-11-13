# Zählkarte – kommunale Verkehrszählungen

**Karte:** https://vizsim-lab.github.io/zaehlkarte/

Städte zählen ständig Verkehr: an Kreuzungen (Knotenstromzählung) und an Straßenabschnitten
(Querschnitt), von Hand oder per Video, für Planungen, Ampeln und Lärmkarten. Die Ergebnisse
liegen meist in Schubladen. Die Zählkarte sammelt, was offen ist oder per
Informationsfreiheitsanfrage herausgegeben wurde, und zeigt die Zählwerte je Verkehrsart:

- **Kfz**, **Schwerverkehr** (Menge und Anteil an Kfz), **Rad** (Menge und Radanteil
  Rad / (Rad + Kfz)) und **Fuß** (bei nach Alter getrennten Zählungen auch
  Kinder/Jugendliche im Tagesgang).
- Kennzahl wählbar: Summe 7–19 Uhr, Summe 24 Stunden oder die stärkste Stunde.
- Je Zählstelle alle Zählungen, der **Tagesgang** jeder Zählung, der Verlauf über die Jahre,
  die Rohdatei und die Lizenz; Download als CSV.
- **Datenlage**: je Kommune, ob es solche Zählungen offen gibt, ob sie auf Anfrage
  herausgegeben wurden oder wo eine Anfrage aussichtsreich ist – mit Belegen.
- **Dauerzählstellen** (Umschalter „Kurzzeitzählungen | Dauerzählstellen“ oben in der
  Legende): fest eingebaute Zähler in Berlin, Hamburg und Ettlingen – die Karte zeigt die
  Tagessumme an einem wählbaren Tag, je Stelle die Tagessummen der ganzen Reihe und den
  Tagesgang des Tags.
- **Deutsch oder Englisch**: Umschalter DE/EN oben in der Legende (Deutsch ist Standard,
  `?lang=en` öffnet englisch). Übersetzt ist die Oberfläche; Hinweise zu den Zählungen,
  Quellenbeschreibungen, Datenlage-Texte und Anfragetexte bleiben deutsch.

Zwei Familien, beide nur mit gezählten Werten im Zeitverlauf: **Kurzzeitzählungen** der
Kommunen (Werte je Zählung) und **Dauerzählstellen** der Kommunen (Stunden- und Tageswerte).
Nicht gemeint sind Jahresmittel (DTV/DTVw), Verkehrsmengenkarten und Modellwerte – dafür gibt
es [vizsim/svz](https://github.com/vizsim/svz). Liefert eine Quelle beides, nimmt jedes Repo
seinen Teil: Hamburgs DTV-Tabelle gehört nach svz, die Stundenwerte der Wärmebildkameras hierher.
Auswertungen wie der Schulweg-Verdacht aus den Berliner Fußgängerzählungen stehen in
[vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege).

## Daten

| Quelle | Was | Zeitraum | Weg | Lizenz |
|---|---|---|---|---|
| Berlin (SenMVKU) | rund 26.600 verortete Knoten- und Querschnittszählungen, 15/60-Minuten-Werte, Kfz nach Fahrzeugart, Rad, Fuß nach Alter | 1983–2025 | IFG-Anfragen [2019](https://fragdenstaat.de/anfrage/kfz-verkehrszahldaten-aus-berlin/) und [2025](https://fragdenstaat.de/anfrage/stundengenaue-ergebnisse-manueller-verkehrszaehlungen-in-berlin/) | CC BY-SA 3.0 DE (bis 2019), dl-de/by-2-0 (ab 2019) |
| Ravensburg, Weingarten, Berg, Baienfurt, Baindt | 24-Stunden-Videozählungen an Kreuzungen, 15-Minuten-Werte, Pkw, Lkw, Rad, Fuß | 2023–2026 | offen auf [MobiData BW](https://mobidata-bw.de/dataset/zaehldaten-ravensburg) | dl-de/by-2-0 |
| Moers (Stadt Moers) | rund 540 Tageszählungen an 140 Stellen mit Seitenradar-Messgeräten (meist zwei Tage am Stück), Kfz je Stunde, Schwerverkehr über die Länge | 2010–2022 | offen auf [offenesdatenportal.de](https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021) | dl-de/zero-2-0 |
| Olpe (Kreisstadt Olpe, Ordnungsamt) | 13 Messungen an zwölf Stellen mit Radar-Messgeräten (ein bis zwei Wochen am Stück), je Fahrzeug Zeit, Richtung und Klasse – Kfz, Schwerverkehr, Rad je Stunde | 2025–2026 | offen auf dem [Open-Data-Portal der Stadt](https://opendata.olpe.de/dataset/?q=Verkehrsmessung) (JSON) | dl-de/by-2-0, eine Messung CC BY 4.0 |
| Münster (Stadt Münster) | rund 1.160 Kfz-Knotenpunktzählungen von Hand, je meist zwei Stunden (7–8 und 16–17 Uhr), nach Fahrzeugart | 2000–2020 | offen auf dem [Open-Data-Portal der Stadt](https://opendata.stadt-muenster.de/dataset/verkehrsz%C3%A4hlung-manuelle-verkehrserhebung) (XLS und PDF) | dl-de/by-2-0, „Datenquelle: Stadt Münster“ |
| Potsdam (Bereich Verkehrsentwicklung) | rund 470 Knotenpunktzählungen von Hand (7–10 und 15–18 Uhr), je Zählung Früh- und Nachmittagsspitzenstunde und Summe der sechs Stunden, Kfz, Schwerverkehr, Rad | 2010–2023 | offen auf dem [Open-Data-Portal der Stadt](https://opendata.potsdam.de/explore/dataset/verkehrszahlungen/) (ein PDF je Zählung) | [Nutzungsbedingungen der LHP](https://opendata.potsdam.de/terms/terms-of-use/), „© LHP/NB-16-OGD/Datum der Entnahme“ |
| Xanten (Mobilitätskonzept, büro stadtVerkehr) | 18 Zählungen vom 25.08.2020 per Video: 12 Knotenpunkte (7–9 und 15–18 Uhr) und 6 Querschnitte (24 h), Viertelstunden nach Fahrzeugart, nur Kfz | 2020 | offen auf [opendata.ruhr](https://opendata.ruhr/dataset/mobilitatskonzept) (PDF) | dl-de/zero-2-0 |
| Konstanz (Amt für Stadtplanung und Umwelt) | 83 Tageszählungen an sechs Stellen mit mobilen Zählgeräten (ein bis sechs Wochen am Stück), 5- oder 15-Minuten-Werte, Rad, Fuß, an zwei Stellen Kfz | 2020 | offen auf [Offene Daten Konstanz](https://offenedaten-konstanz.de/dataset/mobile-verkehrsz-hlungen-rad-und-fu-verkehr) | CC0 1.0 |

**Dauerzählstellen:**

| Quelle | Was | Zeitraum | Weg | Lizenz |
|---|---|---|---|---|
| Berlin (Verkehrsinformationszentrale) | Infrarot-Detektoren (TEU) an rund 250 Standorten; Stundenwerte je Richtung (Messquerschnitt) für Kfz und Lkw (Detektorklasse), in der Karte rund 290 Messquerschnitte | 2015 – Juni 2025 | offen im [Archiv der Digitalen Plattform Stadtverkehr](https://api.viz.berlin.de/daten/verkehrsdetektion) ([Datensatz](https://daten.berlin.de/datensaetze/verkehrsdetektion-berlin)) | dl-de/by-2-0, „Digitale Plattform Stadtverkehr Berlin / Verkehrsdetektion Berlin“ |
| Hamburg (Behörde für Verkehr und Mobilitätswende) | Wärmebildkameras an Kreuzungen: Stundenwerte je Zählstelle (eine Richtung an einem Knotenarm) für Kfz, an 341 Stellen auch Schwerverkehr (Klasse der Kamera), dazu 312 Rad-Zählstellen; in der Karte rund 1.120 Zählstellen, Straßennamen aus OpenStreetMap | vollständig gezählte Tage: Kfz und Rad ab 09.09.2026, Schwerverkehr ab 01.03.2026; wöchentlich ergänzt | offen über die [SensorThings API](https://iot.hamburg.de/v1.1) ([Kfz](https://suche.transparenz.hamburg.de/dataset/verkehrsdaten-kfz-infrarotdetektoren-hamburg14), [Rad](https://suche.transparenz.hamburg.de/dataset/verkehrsdaten-rad-infrarotdetektoren-hamburg20)) | dl-de/by-2-0, „Freie und Hansestadt Hamburg, Behörde für Verkehr und Mobilitätswende“ |
| Ettlingen (Stadt Ettlingen) | automatische Zählstellen an sechs Straßen: Stundenwerte je Fahrtrichtung und Fahrzeugklasse, in der Karte als Kfz (Summe der Klassen); 10 Richtungen an 5 Stellen mit vollständigen Tagen | ab 20.08.2026 (ältere Werte ab Mai 2025 nicht übernommen); wöchentlich ergänzt | offen im [Open-Data-Portal re@di](https://opendata.readi.de/dataset/automatisierte-verkehrszahlung-in-ettlingen) (Datastore) | [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.de) – nur nicht kommerziell, „Stadt Ettlingen“ |

Die Zahlen je Quelle (Stellen, Zählungen, Jahre) stehen in der Karte unter „Quellen &
Lizenzen“ und in `public/data/manifest.json`. Rund 1.500 Berliner Zählungen haben noch keine
Lage (Straßennamen ohne eindeutige Kreuzung in OpenStreetMap); sie fehlen in der Karte.

**Lage in Berlin:** Koordinaten aus der Zähldatei (ab 2021), sonst die Geokodierung der Fuß-
und Radzählungen aus [vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege)
(Straßenkreuzungen aus OpenStreetMap), für die übrigen Zählungen derselbe Geocoder im Workflow
„Berlin geokodieren“ (`pipeline/geokodierung/berlin_ergaenzung.csv`), sonst übernommen von
Zählungen derselben Zählstellen-Kennung, wenn die eindeutig an einem Ort liegen (in der Karte
abschaltbar).

**Datenlage:** Recherche Stand November 2026, unvollständig. Hinweise auf weitere Zählungen
gern über das Formular [„Zählungen melden“](https://github.com/vizsim-lab/zaehlkarte/issues/new?template=zaehlung-melden.yml).

## Kennzahlen – was die Karte zeigt

- Werte sind Summen über alle Richtungen. „7–19 Uhr“ nur, wo jede dieser Stunden gezählt ist;
  „24 h“ nur bei 24-Stunden-Zählungen; „stärkste Stunde“ vergleicht auch kurze Zählfenster.
- Je Stelle zeigt die Karte die jüngste Zählung im Filter, die die gewählte Kennzahl hat.
  Alle Zählungen einer Stelle stehen in der Seitenleiste.
- `-1` in den Rohdaten heißt „nicht gezählt“ und wird nie als 0 gerechnet. Eine Richtung, die
  für eine Verkehrsart gar nicht gezählt wurde, fällt aus der Summe – die Seitenleiste nennt das.
- Werte aus verschiedenen Zählfenstern werden nie ineinander umgerechnet (keine Hochrechnung).
- Der Zähltag ist eingeordnet (Schultag, Ferien, Feiertag, Wochenende – KMK-Ferienkalender),
  weil Ferienzählungen deutlich niedriger liegen können; filterbar.
- MobiData BW: Die Übersichtstabelle nennt in `KFZ_n` nur die Pkw (nachgerechnet an allen
  Zählungen mit Excel); die Karte rechnet Kfz = Pkw + Lkw aus den Stundenwerten.
- Moers: Seitenradar-Geräte zählen jedes Fahrzeug, das sie erfassen (auch Radfahrende lassen
  sich nicht abtrennen); Schwerverkehr = Fahrzeuglänge ab 8 m. Die Lage ist aus der Adresse
  der Messung geokodiert (OpenStreetMap), wo nur die Straße bekannt ist, liegt der Punkt in der
  Straßenmitte.
- Olpe: Die Geräte-Dateien haben UTC-Zeiten (die Karte rechnet in Ortszeit um) und je Tag einen
  GPS-Punkt – auch für Tage nach der Messung; es zählen nur die Punkte aus der Zeit der
  Fahrzeuge. Kfz = alle Klassen außer Radfahrern; Schwerverkehr = Lkw, Lkw mit Anhänger,
  Sattelzüge, Busse; Rad = vom Gerät als Radfahrer erkannt (nur auf der Fahrbahn). Drei oder
  mehr Stunden ohne jedes Fahrzeug, wo nach den übrigen Tagen Verkehr zu erwarten wäre, gelten
  als Ausfall des Geräts („nicht gezählt“, mit Hinweis).
- Münster: Je Zählung liegen nur die Spitzenstunden vor (meist 7–8 und 16–17 Uhr) – in der
  Karte erscheinen die Zählungen deshalb nur unter „stärkste Stunde“. Kfz = Summe der
  Fahrzeugarten; wo Formelfehler im Zählblatt Kfz-Zelle und Fahrzeugarten auseinanderlaufen
  lassen, der größere Wert (mit Hinweis). Schwerverkehr = Bus + Lkw + Lastzug. Die Spalte „Rad“ der Kfz-Zählung ist keine vollständige Radzählung
  (wo es eine eigene Radzählung gibt, liegt sie deutlich darunter oder steht auf 0); sie
  fehlt in der Karte und steht im Hinweis der Zählung.
- Potsdam: Die Zählpläne (PDF) nennen je Zählung nur die Früh- und die Nachmittagsspitzenstunde
  (nach Kfz bestimmt, im Halbstundenraster, z. B. 7:30–8:30 Uhr) und die Summe der sechs
  gezählten Stunden – keine Stundenwerte. In der Karte erscheint Potsdam nur unter „stärkste
  Stunde“ Kfz; Rad und Schwerverkehr in den Spitzenstunden und die 6-Stunden-Summen stehen in
  der Seitenleiste. Weichen im Plan Spalte SUMME und Summe der Zufahrten voneinander ab, gilt
  der größere Wert (mit Hinweis); Pläne mit errechneten Werten (Nachkommastellen) fehlen.
- Konstanz: Je Kalendertag eine Zählung; eine Stunde zählt nur, wenn alle ihre 5- oder
  15-Minuten-Werte da sind (die Geräte fielen öfter für Stunden oder Tage aus). Die
  5-Minuten-Dateien sind Geräteprotokolle: Jede Zeile steht kurz nach dem Ende ihres
  Intervalls und wird so zugeordnet. Die Lage nennt die Stadt nur als Straße, Brücke oder
  Hausnummer; die Punkte stammen aus OpenStreetMap, die Genauigkeit steht im Hinweis.

## Dauerzählstellen – was die Karte zeigt

- Eine **Tagessumme** (0–24 Uhr, je Richtung) gibt es nur, wenn jede Stunde des Tages gezählt
  ist; sonst ist der Tag „nicht vollständig gezählt“ (hohler Punkt) – nie aufgefüllt, nie
  hochgerechnet, keine Mittelwerte. Am Tag der Umstellung auf Sommerzeit hat der Tag 23
  Stunden, bei der Rückstellung 25 (Stunde 2–3 Uhr zweimal, mit Hinweis).
- Gezeigt wird ein Tag (Standard: der jüngste Schultag, an dem die meisten Stellen
  vollständig sind); Pfeile, Datum und Regler wählen einen anderen. Die Seitenleiste zeigt die
  Tagessummen über alle Jahre (gefärbt nach Schultag, Ferien, Wochenende/Feiertag) und den
  Tagesgang des Tags – Stundenwerte für die jüngsten 12 Monate der Quelle.
- **Lkw (Detektor)** (Berlin) und **Schwerverkehr (Detektor)** (Hamburg) sind die Klassen, die
  der Detektor bzw. die Kamera von Pkw unterscheidet – nicht dasselbe wie der Schwerverkehr der
  Kurzzeitzählungen und nicht dasselbe wie einander, darum je eine eigene Verkehrsart. Welche
  Verkehrsarten es gibt, richtet sich nach den Quellen (Kfz, Lkw, Schwerverkehr, Rad).
- Mehrere Quellen, verschiedene Zeiträume: Berlin endet im Juni 2025, Hamburg und Ettlingen
  sind aktuell.
  Hat eine Quelle am gewählten Tag keine Werte, nennt die Legende ihren Zeitraum und springt auf
  Wunsch zu ihrem Standardtag. Schultag und Ferien gelten je Land.
- Berlin: bis 2024 die Werte je Messquerschnitt der alten Qualitätssicherung, wie geliefert
  (eine Stunde nur bei mindestens 75 % gültigen Messintervallen und nur, wenn alle Fahrstreifen
  gültig sind). Ab 2025 gibt es nur die neue Qualitätssicherung je Fahrstreifen; die Zählkarte
  summiert dann nach derselben Regel. Für 2023–2024 liegen beide vor: 81 % der Stunden stimmen
  auf ±2 % überein (Median-Abweichung 0 %). Ab 2021 sind deutlich weniger Tage vollständig
  gezählt als davor. Messquerschnitte, die in den Stammdaten (Stand Juli 2022) fehlen – vor
  allem neue mit „n“ am Ende der Kennung –, haben keine Lage und fehlen in der Karte.
- Hamburg: Stundenwerte je Zählstelle wie geliefert (UTC, in Ortszeit umgerechnet; bei der
  Rückstellung liegen zwei Stunden in 2–3 Uhr). Die Quelle hält Stundenwerte nur zwei Monate
  vor; die Zählkarte hebt sie selbst auf (Gedächtnis, siehe unten) und übernimmt eine Stunde
  erst, wenn sie sieben Tage alt ist (Lücken werden laut Quelle noch nachgeliefert). Ganze Tage
  fehlen gelegentlich an allen Stellen zugleich. Die Quelle nennt keine Straßen: Der Name ist die
  nächste benannte Straße aus OpenStreetMap, die Kreuzung ergibt sich aus den übrigen Armen
  desselben Knotenpunkts.
- Ettlingen: Stundenwerte je Fahrtrichtung und Fahrzeugklasse (UTC, in Ortszeit umgerechnet);
  Kfz ist die Summe der Klassen (Pkw, leichte Nutzfahrzeuge, Lkw, Lkw mit Anhänger, Motorrad).
  Klassen ohne Fahrzeug liefert die Quelle nicht; eine Stunde ganz ohne Werte gilt als nicht
  gezählt. Alle Richtungen eines Sensors haben dieselbe Lage – die Seitenleiste schaltet
  zwischen ihnen um. Die Werte vor dem 20.08.2026 (laufende Tageszähler ohne Fahrtrichtung)
  sind nicht übernommen. Lizenz CC BY-NC 4.0: Weiterverwendung nur nicht kommerziell; die
  Lizenz steht an der Quelle, in der Seitenleiste und in jeder Zeile des CSV-Exports.

## Aufbau

```
pipeline/            uv-Paket `zaehlkarte`: Rohdaten -> ein Zählungsschema -> Kartendaten
  config/sources.yaml   die einzige Quellenliste (Quellen, Lizenzen, Datenlage)
  src/zaehlkarte/adapters/  ein Adapter je Format (berlin_zda, mobidata_bw, muenster, moers_radar,
                            olpe_radar, konstanz_mobil, potsdam_pdf, xanten_pdf)
  src/zaehlkarte/dauer/     Familie Dauerzählstellen (berlin_viz, hamburg_sta, readi_urbanpulse),
                            eigener Bau
public/data/         die Kartendaten (erzeugt, im Git): manifest, index, details/NN, datenlage
public/data/dauer/   Dauerzählstellen (erzeugt, NICHT im Git – Release-Asset, siehe unten)
index.html, main.js, js/, style.css   die Karte (Vite, MapLibre, Positron von OpenFreeMap)
  js/sprache/          Texte der Oberfläche DE/EN (texte.js) und der Umschalter
tests/               unit/ (node --test), web/ (Playwright gegen den Build)
```

```bash
# Pipeline (aus pipeline/)
uv sync
uv run zaehlkarte fetch      # Rohdaten nach pipeline/data/raw/
uv run zaehlkarte site       # Kartendaten nach public/data/
uv run zaehlkarte dauer fetch && uv run zaehlkarte dauer site   # Dauerzählstellen
uv run pytest && uvx ruff check

# Karte (aus der Wurzel)
npm ci
npm run dev                  # http://localhost:5173
npm run test:unit && npm run test:web
```

Eine neue Quelle: Eintrag in `pipeline/config/sources.yaml`, Adapter in
`src/zaehlkarte/adapters/` (liefert `Zaehlung`-Objekte, siehe `modell.py`), Test mit einer
kleinen synthetischen Datei in `pipeline/tests/`. Wie man Quellen findet und was nicht
funktioniert hat: [AGENTS.md](AGENTS.md).

Die Daten erneuert der Workflow „Kartendaten neu bauen“ (monatlich und von Hand) als Pull
Request. Die Dauerzählstellen baut der Workflow „Dauerzählstellen bauen“ (wöchentlich, von
Hand und bei Änderungen an `pipeline/src/zaehlkarte/dauer/`) und legt sie als Release-Asset
`dauerzaehlstellen/dauer.tar.gz` ab – Daten, die sich laufend ändern, gehören nicht ins Git.
Die CI holt das Asset vor dem Build; fehlt es, zeigt die Karte nur die Kurzzeitzählungen.

**Gedächtnis:** Hamburg hält Stundenwerte nur zwei Monate vor. Was die Zählkarte davon
aufhebt (Monatsdateien je Quelle, `<code>__stunden_JJJJ-MM.csv.gz`, und die Straßennamen
`<code>__strassen.json`), liegt im selben Release. Der Workflow holt es vor dem Abruf und legt
danach ab, was sich geändert hat – nie mit weniger Werten (`pipeline/werkzeuge/gedaechtnis.py`).
Wer diese Assets löscht, verliert die Stunden, die die Quelle nicht mehr hat.

Jeder Push auf `main` wird nach grünen Tests nach GitHub Pages ausgeliefert.

## Lizenz

- **Code:** AGPL-3.0-or-later. ZDA-Leser und Namensbereinigung stammen aus
  [vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege) (MIT).
- **Daten:** die Lizenz der jeweiligen Quelle (Tabelle oben, in der Karte je Zählung);
  Namensnennung erforderlich. Hintergrundkarte © OpenStreetMap-Mitwirkende, OpenFreeMap.
