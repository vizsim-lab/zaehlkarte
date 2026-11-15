# Was die Karte zeigt

Zwei Familien, beide nur mit gezählten Werten im Zeitverlauf: **Kurzzeitzählungen** (Werte je
Zählung) und **Dauerzählstellen** (Stunden- und Tageswerte) – gleich, wer zählt: gesucht sind
Werte je Stunde oder je Tag an einer bestimmten Stelle.
Nicht gemeint sind Jahresmittel (DTV/DTVw), Verkehrsmengenkarten und Modellwerte – dafür gibt
es [vizsim/svz](https://github.com/vizsim/svz). Liefert eine Quelle beides, nimmt jedes Repo
seinen Teil: Hamburgs DTV-Tabelle gehört nach svz, die Stundenwerte der Wärmebildkameras hierher.
Auswertungen wie der Schulweg-Verdacht aus den Berliner Fußgängerzählungen stehen in
[vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege).

## Überblick

- **Kfz**, **Schwerverkehr** (Menge und Anteil an Kfz), **Rad** (Menge und Radanteil
  Rad / (Rad + Kfz)) und **Fuß** (bei nach Alter getrennten Zählungen auch
  Kinder/Jugendliche im Tagesgang).
- Kennzahl wählbar: Summe 7–19 Uhr, Summe 6–22 Uhr, Summe 24 Stunden oder die stärkste Stunde.
- Je Zählstelle alle Zählungen, der **Tagesgang** jeder Zählung, der Verlauf über die Jahre,
  die Rohdatei und die Lizenz; Download als CSV (nur Quellen mit Lizenz, siehe
  [Quellen ohne Lizenz](QUELLEN.md#quellen-ohne-lizenz)).
- **Kommunen und ihr Steckbrief**: Die Punkte der Kommunen zeigen in beiden Ansichten, wie es
  dort steht – blau, sobald Zählungen einer Familie in der Karte sind, sonst grün (offen oder auf
  Anfrage herausgegeben), orange (eine Anfrage ist aussichtsreich) oder grau. Ein Klick öffnet
  den **Steckbrief**: für beide Familien je Verkehrsart eine Zeile mit Zeitstrahl und Umfang –
  Kurzzeitzählungen als Kästchen je Jahr (je dunkler, desto mehr Zählungen; Lücken bleiben leer),
  Dauerzählstellen als Balken vom ersten bis zum letzten vollständig gezählten Tag (hell, solange
  es nur Tageswerte der Quelle gibt). Ein Klick auf eine Zeile stellt Familie und Verkehrsart um
  und zeigt die Stellen. Darunter die Datenlage beider Familien mit Belegen, Kontakt und
  Anfragetext, die Kurzzeitzählungen der Kommune als CSV und ein Permalink (`k=`, der
  Gemeinde- oder Kreisschlüssel). Aus der Seitenleiste einer Stelle führt ein Link zum Steckbrief
  ihrer Kommune.
- **Dauerzählstellen** (Umschalter „Kurzzeitzählungen | Dauerzählstellen“ oben in der
  Legende): fest eingebaute Zähler in Berlin, Hamburg und Ettlingen, die Dauerzählstellen des
  Landes Baden-Württemberg an Autobahnen, Bundes- und Landesstraßen und die Rad-Zählstellen von
  Berlin, Münster, Aachen, München, Würzburg, Dortmund, Essen, Bochum, Bonn, Düsseldorf,
  Leipzig, Rostock, Dresden, dem Rhein-Kreis Neuss, 27 Städten und Landkreisen und dem Land in
  Baden-Württemberg und in Niedersachsen die der VMZ Niedersachsen (Landesbehörde für Straßenbau
  und Verkehr, Hannover, Region Hannover, Braunschweig und vier weitere Kommunen), dazu der
  Radschnellweg RS5 in Neuss und Augsburgs Radzählstationen (nur Tageswerte); Fuß in Augsburg
  (Passantenzählung Annastraße), Würzburg (Passantenzählung an drei Standorten der Innenstadt)
  und Bochum (fünf Rad- und Fuß-Zählstellen).
  Die Karte zeigt je Stelle die Tagessumme ihres jüngsten vollständig gezählten Schultags oder
  eines wählbaren Tags (Kfz zuerst, Rad, Fuß und Lkw/Schwerverkehr über die Chips), die
  Seitenleiste die Tagessummen der ganzen Reihe und den Tagesgang des Tags.
- **Deutsch oder Englisch**: Umschalter DE/EN oben in der Legende (Deutsch ist Standard,
  `?lang=en` öffnet englisch). Übersetzt ist die Oberfläche; Hinweise zu den Zählungen,
  Quellenbeschreibungen, Datenlage-Texte und Anfragetexte bleiben deutsch.

## Kurzzeitzählungen: Kennzahlen

- Werte sind Summen über alle Richtungen. „7–19 Uhr“ nur, wo jede dieser Stunden gezählt ist;
  „6–22 Uhr“ ebenso, oder wo die Quelle genau diese Summe nennt (Nürnberg); „24 h“ nur bei
  24-Stunden-Zählungen; „stärkste Stunde“ vergleicht auch kurze Zählfenster.
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
  lassen, der größere Wert (mit Hinweis). Schwerverkehr = Bus + Lkw + Lastzug. Die Spalte
  „Rad“ der Kfz-Zählung ist keine vollständige Radzählung (wo es eine eigene Radzählung gibt,
  liegt sie deutlich darunter oder steht auf 0); sie fehlt in der Karte und steht im Hinweis
  der Zählung.
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
- Nürnberg: Die Berichte der jährlichen Querschnittszählung nennen je Zählstelle nur die Summe
  Kfz 6–22 Uhr – in der Karte erscheint Nürnberg nur unter „6–22 Uhr“ Kfz. Gezählt wird in
  vier Schichten an zwei Tagen (Dienstag 10–14 und 18–22 Uhr, Mittwoch 6–10 und 14–18 Uhr); die
  Zählung trägt das Datum des Dienstags. Lkw und Lastzüge (ab 2023) fehlen: ohne Busse ist das
  nicht der Schwerverkehr der Karte. Fehlt der Wert einer Zählstelle im Bericht seines Jahres,
  gilt der Wert für dieses Jahr aus dem frühesten späteren Bericht; Fußnoten der Berichte und
  Abweichungen zwischen ihnen stehen als Hinweis an der Zählung. Die Lage stammt aus
  OpenStreetMap (nach dem Namen der Zählstelle) und den Zählstellenplänen der Berichte; die
  Genauigkeit steht im Hinweis.
- Kevelaer: Die Knotenpunkte sind 6–10 und 15–19 Uhr gezählt (in der Karte unter „stärkste
  Stunde“), die Querschnitte 24 Stunden. Kfz = Pkw, Krad, Lieferwagen und Lkw; Schwerverkehr =
  die Art „Lkw“ (Lieferwagen nicht; Busse und Lastzüge sind keine eigenen Arten). Seiten, die im
  PDF nur Bilder sind, sind abgeschrieben; ein Zählfenster kommt nur in die Karte, wenn es die
  Summen des Berichts trifft. Der Bericht nennt für die meisten Knotenpunkte „Do. 17.09.2019“ –
  der 17.09.2019 war ein Dienstag; es gilt das Datum (Hinweis an der Zählung).

## Dauerzählstellen

- Eine **Tagessumme** (0–24 Uhr, je Zählstelle – je nach Quelle eine Fahrtrichtung oder beide
  zusammen) gibt es nur, wenn jede Stunde des Tages gezählt ist; sonst ist der Tag „nicht
  vollständig gezählt“ (hohler Punkt) – nie aufgefüllt, nie hochgerechnet, keine Mittelwerte.
  Am Tag der Umstellung auf Sommerzeit hat der Tag 23 Stunden, bei der Rückstellung 25 (Stunde
  2–3 Uhr zweimal, mit Hinweis); führt eine Quelle dann nur eine dieser Stunden, ist der Tag
  nicht vollständig gezählt.
- **Tageswerte der Quelle:** Liefert eine Quelle für eine Stelle nur Tageswerte (Augsburgs
  Radzählstationen; Hamburg und Leipzig vor den Stunden, die die Zählkarte seit August bzw.
  Oktober 2026 aufhebt; Würzburgs Passanten vor 2024), zeigt die Karte deren Tageswert wie
  geliefert – „Tageswert der Quelle“ im
  Hover, in der Seitenleiste und als Hinweis in der Legende, ohne Tagesgang; ob jede Stunde
  gezählt ist, lässt sich dort nicht prüfen. Tageswerte gelten nur vor der ersten gezählten
  Stunde einer Stelle, nie als Ersatz fehlender Stunden, und nie aus Wochen-, Monats- oder
  Jahreswerten. Der Tag der Quelle kann vom Kalendertag 0–24 Uhr abweichen (Leipzig: UTC-Tag,
  1 bis 1 Uhr, im Sommer 2 bis 2 Uhr) – das steht im Verfahren der Seitenleiste und als Hinweis
  an der Quelle, umgerechnet wird nichts. Im CSV stehen sie in einer eigenen Spalte
  (`<gruppe>_tageswert_quelle`).
- Standard: je Stelle die Tagessumme ihres **jüngsten vollständig gezählten Schultags** – so
  stehen alle Quellen zugleich in der Karte, auch wenn ihre Zeiträume sich nicht überschneiden
  (Berlins Detektoren enden im Juni 2025, der Rhein-Kreis Neuss im Juli 2026; Berlins
  Rad-Zählstellen, Bonn und Düsseldorf liefern einmal im Jahr und enden im Dezember 2025, Essen
  liefert vierteljährlich, München monatlich, die übrigen Quellen laufend). Der Tag steht bei
  jedem Wert (Hover, Seitenleiste, CSV), die Legende nennt die Tage je Quelle – Stellen, die
  nicht mehr zählen, zeigen ihren letzten Schultag, in Berlin auch Jahre zurück. Schultag und
  Ferien gelten je Land.
- „Tag wählen“ zeigt alle Stellen am selben Tag (zuerst der jüngste Schultag, an dem die meisten
  Stellen vollständig sind); Pfeile, Datum und Regler wählen einen anderen. Hat eine Quelle an
  dem Tag keine Werte, nennt die Legende ihren Zeitraum und springt auf Wunsch zu ihrem
  Standardtag. Die Seitenleiste zeigt die Tagessummen über alle Jahre (gefärbt nach Schultag,
  Ferien, Wochenende/Feiertag) und den Tagesgang des Tags – Stundenwerte für die jüngsten 12
  Monate der Quelle; ein Klick in die Tagesreihe wählt den Tag.
- **Lkw/Schwerverkehr:** Berlin und Ettlingen zählen „Lkw“, Hamburg „Schwerverkehr“, die
  Dauerzählstellen des Landes Baden-Württemberg „Schwerverkehr“ (an 41 Autobahn-Stellen mit nur
  zwei Klassen bis 2025 die Lkw-ähnlichen als „Lkw“) – jeweils
  die Klasse, die der Detektor bzw. die Kamera von Pkw unterscheidet, je Quelle anders
  abgegrenzt und nicht dasselbe wie der Schwerverkehr der Kurzzeitzählungen. Ein Chip zeigt
  beide: jede Stelle in ihrer Klasse und mit deren Namen, nie zusammengezählt; die Legende nennt,
  welche Stadt welche Klasse zählt. Welche Verkehrsarten es gibt, richtet sich nach den Quellen
  (Kfz, Lkw/Schwerverkehr, Rad, Fuß); die Karte öffnet mit Kfz. Die Stufen für Fuß trennen Rad-
  und Fußwege (Bochum: meist 100 bis 500 am Tag) von Fußgängerzonen (Augsburg: rund 17.600,
  Würzburg: im Median 14.000 bis 25.000 je Standort).
- **Datenlage und Steckbrief:** Je Kommune hat jede Familie ihren eigenen Stand und ihre
  Belege; beide nutzen dieselben Stände (in der Karte, offen, herausgegeben, aussichtsreich, ohne
  Lizenz, nur Summen, nichts offen …). Der Steckbrief zählt zu einer Kommune die Stellen ihrer
  eigenen Quellen ganz – auch jenseits der Grenze (Hamburg zählt auch in Norderstedt) –, aus
  Bündeln (MobiData BW, VMZ Niedersachsen) und von Quellen des Landes die Stellen, die in ihr
  liegen (Gemeinde der Stelle aus VG250; ein Kreis umfasst seine Gemeinden). So zeigt etwa
  Stuttgart neben den Rad-Zählstellen der Stadt die Kfz-Zählstellen des Landes.
- Berlin: bis 2024 die Werte je Messquerschnitt der alten Qualitätssicherung, wie geliefert
  (eine Stunde nur bei mindestens 75 % gültigen Messintervallen und nur, wenn alle Fahrstreifen
  gültig sind). Ab 2025 gibt es nur die neue Qualitätssicherung je Fahrstreifen; die Zählkarte
  summiert dann nach derselben Regel. Für 2023–2024 liegen beide vor: 81 % der Stunden stimmen
  auf ±2 % überein (Median-Abweichung 0 %). Ab 2021 sind deutlich weniger Tage vollständig
  gezählt als davor. Messquerschnitte, die in den Stammdaten (Stand Juli 2022) fehlen – vor
  allem neue mit „n“ am Ende der Kennung –, haben keine Lage und fehlen in der Karte.
- Hamburg: Stundenwerte je Zählstelle wie geliefert (UTC, in Ortszeit umgerechnet; bei der
  Rückstellung liegen zwei Stunden in 2–3 Uhr). Die Quelle hält Stundenwerte nur zwei Monate
  vor; die Zählkarte hebt sie selbst auf (Gedächtnis, siehe
  [Entwicklung](ENTWICKLUNG.md#gedächtnis)) und übernimmt eine Stunde
  erst, wenn sie sieben Tage alt ist (Lücken werden laut Quelle noch nachgeliefert). Ganze Tage
  fehlen gelegentlich an allen Stellen zugleich. Vor der ersten gezählten Stunde einer Stelle
  (meist bis 28.08.2026) stehen für Kfz und Rad die Tageswerte der Quelle (seit 2020; auch sie
  hebt die Zählkarte auf, die Quelle hält sie nur für das laufende und das letzte Jahr vor). Sie
  entstehen nicht aus den Stunden: Wo es beides gibt, ist der Tageswert an rund drei von vier
  vollständig gezählten Tagen gleich der Summe der Stunden, sonst meist knapp darüber, und auch
  Tage mit fehlenden Stunden haben einen Tageswert (manchmal nur für den gezählten Teil). Die
  Quelle kennzeichnet keine unplausiblen Werte (es gibt Tage mit Millionen Kfz); die Zählkarte
  übernimmt sie wie geliefert. Die Quelle nennt keine Straßen: Der Name ist die nächste benannte
  Straße aus OpenStreetMap, die Kreuzung ergibt sich aus den übrigen Armen desselben
  Knotenpunkts.
- Ettlingen: Stundenwerte je Fahrtrichtung und Fahrzeugklasse (UTC, in Ortszeit umgerechnet);
  Kfz ist die Summe der Klassen (Pkw, leichte Nutzfahrzeuge, Lkw, Lkw mit Anhänger, Motorrad),
  Lkw die von Lkw und Lkw mit Anhänger.
  Klassen ohne Fahrzeug liefert die Quelle nicht; eine Stunde ganz ohne Werte gilt als nicht
  gezählt. Alle Richtungen eines Sensors haben dieselbe Lage – die Seitenleiste schaltet
  zwischen ihnen um. Die Werte vor dem 20.08.2026 (laufende Tageszähler ohne Fahrtrichtung)
  sind nicht übernommen. Lizenz CC BY-NC 4.0: Weiterverwendung nur nicht kommerziell; die
  Lizenz steht an der Quelle, in der Seitenleiste und in jeder Zeile des CSV-Exports.
- Baden-Württemberg, Dauerzählstellen des Landes: Stundenwerte je Fahrstreifen, abgeleitet aus
  den Lieferungen an die BASt; in der Karte je Fahrtrichtung die Summe ihrer Fahrstreifen (beide
  Richtungen am selben Punkt, die Seitenleiste schaltet um). Eine Stunde zählt nur, wenn die
  Quelle sie auf allen Fahrstreifen der Richtung als korrekt kennzeichnet – Ausfälle,
  fehlerhafte Werte, Schätzwerte (oft einen ganzen Monat an einer Stelle) und eingefügte Stunden
  nicht; je Monat sind 55–94 % der Tage je Richtung vollständig. Am Tag der Rückstellung der Uhr
  steht 2–3 Uhr nur einmal da (gekennzeichnet) – der Tag ist nicht vollständig. Die Dateien nennen
  keine Koordinaten: Die Lage ist die des passenden Abschnitts in der Zählstellenkarte des
  Landes; 13 von 206 Zählstellen ohne passenden Abschnitt fehlen.
- Rad-Zählstellen (Berlin, Münster, Aachen, München, Baden-Württemberg über MobiData BW,
  Würzburg, Rhein-Kreis Neuss, Neuss, Dortmund, Essen, Bochum, Bonn, Düsseldorf, Leipzig,
  Rostock):
  Zählschleifen oder -säulen, meist von Eco-Counter; in der Karte je Zählstelle die Summe ihrer
  Richtungen – wo die Quelle jede Richtung als eigene Zählstelle führt (Berlin meist, Würzburg
  am Greinberg), steht jede für sich. Gezählt ist nur, was die Quelle als Rohwert oder geprüften
  Wert führt – Werte, die sie als rekonstruiert (Ausfall rechnerisch aufgefüllt), unplausibel,
  gelöscht oder von Hand geändert kennzeichnet, gelten als nicht gezählt (Münster und Würzburg:
  Status je Wert, Rhein-Kreis Neuss: „modified“, Berlin: Zellfarbe). Die übrigen Quellen führen
  keinen Status: Aachen und München lassen Ausfälle leer; bei MobiData BW stecken nachweislich
  rekonstruierte Werte in den Stundenwerten, bei Dortmund, Essen, Bochum, Bonn, Düsseldorf,
  Leipzig, Rostock und am RS5 in Neuss lässt es sich nicht prüfen. Wo die Quelle einen Ausfall als 0 führt
  (Würzburg-Heidingsfeld, Rhein-Kreis Neuss, Rostock, Bonn, Düsseldorf), erscheint der Tag als
  gezählt (Hinweis an der Quelle).
- Nicht in der Karte (Gründe in der Quelldatei und an der Quelle): Zählstellen, die Rad und Fuß
  zusammen zählen, und Stellen, die nur die Summe anderer sind oder deren Gerät schon unter
  anderen Stellen zählt (sonst doppelt: die Brücken-Summen in Bonn, drei
  Stellen in Düsseldorf, je eine in Stuttgart und Rostock). Bochum zählt Fuß getrennt – in der
  Karte stehen Rad und Fuß als eigene Verkehrsarten, ohne die Springorumtrasse Süd, an der laut
  Stadt Rad-Kanäle fehlen.
- Zeitumstellung bei den Rad-Zählstellen: Bei der Rückstellung der Uhr fassen MobiData BW,
  Münster und Berlin beide Stunden 2–3 Uhr unter einer Uhrzeit zusammen; in München, Würzburg,
  Dortmund, Essen, Bochum, Bonn, Düsseldorf, Rostock, im Rhein-Kreis Neuss und am RS5 in Neuss
  fehlt eine davon
  oder ist unvollständig – der Tag gilt als nicht vollständig gezählt. Leipzig führt beide
  Stunden, Aachen liefert UTC.
