# Datenlage: kommunale Verkehrszählungen

Erzeugt von `zaehlkarte site` am 2026-11-08 aus `pipeline/config/sources.yaml` –
nicht von Hand ändern. Dieselben Angaben zeigt die Karte unter „Datenlage je Kommune“.
Rechtliche Hinweise sind keine Rechtsberatung; Kontakte aus der Behördendatenbank von
FragDenStaat.

| Kommune | Land | Stand | Empfehlung |
|---|---|---|---|
| Dortmund | NW | nur Summen oder Mittelwerte offen | Anfrage nach den Ergebnissen der Zählungen im Zählstellenplan, nach IFG NRW |
| Dresden | SN | erhoben – Anfrage aussichtsreich | Anfrage über FragDenStaat an die Landeshauptstadt Dresden nach den Einzelzählungen seit 2015, mit Verweis auf AF0915/25 |
| Düsseldorf | NW | nur Summen oder Mittelwerte offen | Anfrage nach den Einzelzählungen, aus denen die Mittelwerte entstehen, an das Amt für Verkehrsmanagement |
| Frankfurt am Main | HE | nur Summen oder Mittelwerte offen | Anfrage nach den Einzelzählungen |
| Hamburg | HH | automatische Zählungen offen | Für die Zählkarte nur bedingt passend (Dauerzählung) |
| Heidelberg | BW | automatische Zählungen offen | Manuelle Knotenpunktzählungen anfragen |
| Köln | NW | nur Summen oder Mittelwerte offen | Anfrage nach den Einzelzählungen hinter den Mittelwerten, an das Amt für Verkehrsmanagement |
| Leipzig | SN | Anfrage gescheitert | Neu anfragen, aber gezielt nach den Zählauswertungen der Büros (Tabellen seit 2022) und den eigenen Zählungen – nicht nach einem Export der Karte |
| Magdeburg | ST | auf Anfrage herausgegeben | Die Zählungen seit 2012 digital (CSV/XLSX statt PDF auf CD) und mit offener Lizenz anfragen |
| München | BY | erhoben – Anfrage aussichtsreich | Anfrage nach einem DAVe-Export aller Zählungen |
| Nürnberg | BY | auf Anfrage herausgegeben | Anfrage nach allen Zählungen seit 2015 in dieser Form, an das Verkehrsplanungsamt |
| Paderborn | NW | auf Anfrage herausgegeben | Anfrage nach allen Zählungen seit 2015 an die Stadt Paderborn |
| Potsdam | BB | offen, noch nicht in der Karte | Zwei Wege: die PDFs auslesen (Adapter in Arbeit) oder dieselben Zählungen als Tabellen (CSV/XLSX) anfragen |
| Rostock | MV | auf Anfrage herausgegeben | Die Excel-Originale und die Zählungen seit 2020 nachfordern, dazu eine Lizenz |
| Stuttgart | BW | nur Summen oder Mittelwerte offen | Anfrage nach den Knotenpunkt- und Querschnittszählungen im Stadtgebiet |
| Wolfsburg | NI | erhoben – Anfrage aussichtsreich | Anfrage nach einem DAVe-Export und den älteren Zählungen |
| Xanten | NW | offen, noch nicht in der Karte | Keine Anfrage nötig: Adapter für die Übersicht bauen. |
| Baienfurt | BW | in der Karte | in der Karte |
| Baindt | BW | in der Karte | in der Karte |
| Berg | BW | in der Karte | in der Karte |
| Berlin | BE | in der Karte | in der Karte |
| Münster | NW | in der Karte | Die PDFs 2013–2020 lassen sich auslesen (nächster Schritt hier) |
| Ravensburg | BW | in der Karte | in der Karte |
| Weingarten | BW | in der Karte | in der Karte |

## Dortmund (NW) – nur Summen oder Mittelwerte offen

**Lage:** Offen ist nur der Zählstellenplan; Werte gibt die Stadt gegen Gebühr heraus.

**Empfehlung:** Anfrage nach den Ergebnissen der Zählungen im Zählstellenplan, nach IFG NRW. Gebühren vorab erfragen und gegebenenfalls auf einen Teil (etwa die letzten fünf Jahre) begrenzen.

**Weg:** FragDenStaat, IFG NRW

**Kontakt:** [FragDenStaat](https://fragdenstaat.de/behoerden/?q=Stadt+Dortmund)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Dortmund seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Ihr Zählstellenplan ist offen; ich bitte um die Ergebnisse der dort verzeichneten Zählungen.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [opendata.ruhr](https://opendata.ruhr/dataset/verkehrszahlung-zahlstellenplan1)


## Dresden (SN) – erhoben – Anfrage aussichtsreich

**Lage:** Dresden zählt an Knotenpunkten und im Nebennetz, meist per Video oder Radar durch eigene Mitarbeitende. Offen sind nur Mittelwerte der Dauerzählstellen (Verkehrsmengenkarte). Laut Antwort AF0915/25 vom 18.11.2025 bereitet die Stadt Verkehrsdaten auf Anfrage auf, je nach Kapazität.

**Empfehlung:** Anfrage über FragDenStaat an die Landeshauptstadt Dresden nach den Einzelzählungen seit 2015, mit Verweis auf AF0915/25. Grundlage: Sächsisches Umweltinformationsgesetz – das Transparenzgesetz gilt für Kommunen nur, wenn sie es per Satzung einführen.

**Weg:** FragDenStaat, Sächsisches Umweltinformationsgesetz

**Kontakt:** [FragDenStaat](https://fragdenstaat.de/behoerden/?q=Landeshauptstadt+Dresden)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Dresden seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

In Ihrer Antwort auf die Anfrage AF0915/25 vom 18. November 2025 schreiben Sie, dass Verkehrsdaten auf Anfrage aufbereitet und bereitgestellt werden. Gemeint sind hier die Knotenpunkt- und Querschnittszählungen, nicht die Mittelwerte der Dauerzählstellen.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [Antwort AF0915/25 (18.11.2025)](https://team-zastrow.de/wp-content/uploads/2025/11/AF0915_25-Verkehrszaehlung.pdf)


## Düsseldorf (NW) – nur Summen oder Mittelwerte offen

**Lage:** Offen sind Jahresmittelwerte (DTV) je Abschnitt als WFS.

**Empfehlung:** Anfrage nach den Einzelzählungen, aus denen die Mittelwerte entstehen, an das Amt für Verkehrsmanagement. Grundlage: IFG NRW.

**Weg:** FragDenStaat, IFG NRW

**Kontakt:** Amt für Verkehrsmanagement Düsseldorf · <verkehrsmanagement@duesseldorf.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/16786/amt-fur-verkehrsmanagement-der-landeshauptstadt-dusseldorf/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Düsseldorf seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Offen sind Jahresmittelwerte je Abschnitt; ich bitte um die Einzelzählungen, aus denen sie entstehen.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```


## Frankfurt am Main (HE) – nur Summen oder Mittelwerte offen

**Lage:** Offen sind 24-Stunden-Mittelwerte 2019–2023 als WFS, auch für Rad.

**Empfehlung:** Anfrage nach den Einzelzählungen. Das hessische Informationsfreiheitsrecht gilt für Kommunen nur per Satzung – das Hessische Umweltinformationsgesetz gilt immer.

**Weg:** FragDenStaat, Hessisches UIG

**Kontakt:** [FragDenStaat](https://fragdenstaat.de/behoerden/?q=Frankfurt+am+Main+Verkehr)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Frankfurt am Main seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Offen sind 24-Stunden-Mittelwerte je Zählstelle; ich bitte um die Einzelzählungen dahinter.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```


## Hamburg (HH) – automatische Zählungen offen

**Lage:** Offen sind automatische Zählungen: Wärmebildkameras an über 400 Kreuzungen mit 15-Minuten- Werten.

**Empfehlung:** Für die Zählkarte nur bedingt passend (Dauerzählung). Manuelle Kurzzeitzählungen bei Bedarf nach dem Hamburgischen Transparenzgesetz anfragen.

**Weg:** offen (automatisch)

**Belege:** [BMV](https://www.bmv.de/SharedDocs/DE/Artikel/G/DKV/dkv-aVME-HH.html)


## Heidelberg (BW) – automatische Zählungen offen

**Lage:** Offen sind die Werte von 12 automatischen Zählkameras.

**Empfehlung:** Manuelle Knotenpunktzählungen anfragen. Grundlage: Landesinformationsfreiheitsgesetz Baden- Württemberg; die Stadt hat dafür eine eigene Koordinierungsstelle.

**Weg:** FragDenStaat, LIFG BW

**Kontakt:** Stadt Heidelberg · <Koordinierungsstelle-LIFG@Heidelberg.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/9232/stadt-heidelberg/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Heidelberg seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```


## Köln (NW) – nur Summen oder Mittelwerte offen

**Lage:** Offen sind Mittelwerte je Zählstelle. Einzelzählungen gibt die Stadt auf Anfrage heraus, 2024 etwa für die Kitschburger Straße.

**Empfehlung:** Anfrage nach den Einzelzählungen hinter den Mittelwerten, an das Amt für Verkehrsmanagement. Grundlage: IFG NRW.

**Weg:** FragDenStaat, IFG NRW

**Kontakt:** Amt für Verkehrsmanagement Köln · <verkehrsmanagement@stadt-koeln.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/15906/amt-fur-straen-und-verkehrsentwicklung/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Köln seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Offen sind Mittelwerte je Zählstelle. Ich bitte um die zugrundeliegenden Einzelzählungen; 2024 haben Sie solche Zählungen für die Kitschburger Straße herausgegeben.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [Open.NRW](https://ckan.open.nrw.de/dataset/kfz-zaehlstellen-und-werte-koeln-k) · [FragDenStaat 2024](https://fragdenstaat.de/anfrage/verkehrszaehlungen-auf-der-kitschburger-str-in-koeln-lindenthal/)


## Leipzig (SN) – Anfrage gescheitert

**Lage:** Leipzig zählt 50–100-mal im Jahr; seit 2022 liefern die beauftragten Büros Tabellen. Online gibt es nur die Verkehrsmengenkarte. Eine Anfrage 2023 nach den Daten der Karte wurde abgelehnt, weil es keinen Export gibt; eine Anfrage 2020 wurde wegen Kosten zurückgezogen.

**Empfehlung:** Neu anfragen, aber gezielt nach den Zählauswertungen der Büros (Tabellen seit 2022) und den eigenen Zählungen – nicht nach einem Export der Karte. An das Verkehrs- und Tiefbauamt. Grundlage: Informationsfreiheitssatzung der Stadt Leipzig und Sächsisches Umweltinformationsgesetz.

**Weg:** FragDenStaat, Informationsfreiheitssatzung Leipzig / Sächsisches UIG

**Kontakt:** Verkehrs- und Tiefbauamt Leipzig · <vta@leipzig.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/49250/verkehrs-und-tiefbauamt-leipzig/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Leipzig seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Gemeint sind die Zählauswertungen, die Ihnen die beauftragten Büros liefern (seit 2022 als Tabellen), und Ihre eigenen Zählungen – nicht ein Export aus der Verkehrsmengenkarte.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [FragDenStaat 2023](https://fragdenstaat.de/anfrage/datengrundlage-verkehrsmengenkarten-der-stadt-leipzig/) · [Informationsfreiheitssatzung (L-IZ 2021)](https://www.l-iz.de/politik/leipzig/2021/10/evaluierungsbericht-zur-informationsfreiheitssatzung-warten-auf-das-saechsische-transparenzgesetz-417215)


## Magdeburg (ST) – auf Anfrage herausgegeben

**Lage:** Hat 2022 alle Zählunterlagen 2012–2020 angeboten: Viertelstundenwerte je Richtung, nach Rad, Pkw, Lieferwagen, Lkw, Lastzug und Bus – als PDF-Listen auf CD, gebührenfrei. Für die Weitergabe war ein Entgelt nach dem Weiterverwendungsgesetz im Gespräch.

**Empfehlung:** Die Zählungen seit 2012 digital (CSV/XLSX statt PDF auf CD) und mit offener Lizenz anfragen. Grundlage: Informationszugangsgesetz Sachsen-Anhalt.

**Weg:** FragDenStaat, IZG LSA

**Kontakt:** Landeshauptstadt Magdeburg · <info@magdeburg.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/7460/landeshauptstadt-magdeburg/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Magdeburg seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

2022 haben Sie die Zählunterlagen 2012–2020 als PDF-Listen auf CD angeboten. Ich bitte um die Zählungen seit 2012 in digitaler, maschinenlesbarer Form per E-Mail oder Download.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [FragDenStaat 2022](https://fragdenstaat.de/anfrage/rohdaten-von-verkehrszahlungen-2012-bis-2021/)


## München (BY) – erhoben – Anfrage aussichtsreich

**Lage:** Über 5.000 von Hand gezählte Kfz- und Radzählungen in der stadteigenen Software DAVe, in Viertelstunden; Fußzählungen kommen dazu. DAVe kann offene Formate exportieren. Online gibt es nur Karten.

**Empfehlung:** Anfrage nach einem DAVe-Export aller Zählungen. Bayern hat kein Landes-IFG: Grundlage sind das Bayerische Umweltinformationsgesetz und die Informationsfreiheitssatzung der Stadt.

**Weg:** FragDenStaat, Bayerisches UIG / Informationsfreiheitssatzung München

**Kontakt:** [FragDenStaat](https://fragdenstaat.de/behoerden/?q=Landeshauptstadt+M%C3%BCnchen+Mobilit%C3%A4tsreferat)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt München seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Die Zählungen liegen in Ihrer Software DAVe vor, die Exporte in offene Formate erlaubt. Ein solcher Export aller Zählungen genügt.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [stadt.muenchen.de](https://stadt.muenchen.de/infos/verkehrsdaten.html) · [DAVe](https://stadt.muenchen.de/news/open-source-anwendung-dave.html)


## Nürnberg (BY) – auf Anfrage herausgegeben

**Lage:** Zählt seit 1967 jedes Jahr von Hand. Eine Anfrage 2025/26 bekam eine Zählung in Halbstundenwerten; abgelehnt wurden nur Geschwindigkeitsdaten der Verkehrsüberwachung.

**Empfehlung:** Anfrage nach allen Zählungen seit 2015 in dieser Form, an das Verkehrsplanungsamt. Grundlage: Bayerisches Umweltinformationsgesetz.

**Weg:** FragDenStaat, Bayerisches UIG

**Kontakt:** Verkehrsplanungsamt Nürnberg · [FragDenStaat](https://fragdenstaat.de/behoerde/52086/verkehrsplanungsamt-nuernberg/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Nürnberg seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Auf eine Anfrage 2025/26 haben Sie eine Zählung in Halbstundenwerten herausgegeben. Ich bitte um alle Zählungen seit 2015 in dieser Form; Geschwindigkeitsdaten der Verkehrsüberwachung sind nicht gemeint.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [FragDenStaat 2025/26](https://fragdenstaat.de/anfrage/anfrage-daten-verkehrszaehlung-und-geschwindigkeitsmessung/) · [Bericht Verkehrszählung 2018](https://www.nuernberg.de/imperia/md/verkehrsplanung/dokumente/bericht_verkehrszahlung_2018.pdf)


## Paderborn (NW) – auf Anfrage herausgegeben

**Lage:** Hat Zählungen einzelner Straßen auf Anfrage herausgegeben.

**Empfehlung:** Anfrage nach allen Zählungen seit 2015 an die Stadt Paderborn. Grundlage: IFG NRW.

**Weg:** FragDenStaat, IFG NRW

**Kontakt:** Stadt Paderborn · <info@paderborn.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/34204/stadt-paderborn/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Paderborn seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [FragDenStaat](https://fragdenstaat.de/anfrage/verkehrszahlungen-bahnhofstrae-neuhauser-strae-rathenaustrae-detmolder-strae/)


## Potsdam (BB) – offen, noch nicht in der Karte

**Lage:** Offen sind die Lage der gezählten Kreuzungen und ein PDF je Kreuzung (von Hand, April bis Oktober, 7–10 und 15–18 Uhr).

**Empfehlung:** Zwei Wege: die PDFs auslesen (Adapter in Arbeit) oder dieselben Zählungen als Tabellen (CSV/XLSX) anfragen. Grundlage: Akteneinsichts- und Informationszugangsgesetz Brandenburg.

**Weg:** FragDenStaat, AIG Brandenburg

**Kontakt:** Stadtverwaltung Potsdam · <Poststelle@Rathaus.Potsdam.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/4046/stadtverwaltung-potsdam/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Potsdam seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Auf Ihrem Open-Data-Portal stehen die Ergebnisse der Knotenpunktzählungen als PDF je Kreuzung. Ich bitte um dieselben Zählungen in maschinenlesbarer Form (CSV oder XLSX) und um die Zählungen, die dort nicht veröffentlicht sind.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [Open Data Potsdam](https://opendata.potsdam.de/explore/dataset/verkehrszahlungen/) · [potsdam.de](https://www.potsdam.de/de/verkehrszaehlungen-der-landeshauptstadt-potsdam)


## Rostock (MV) – auf Anfrage herausgegeben

**Lage:** Zählt an rund 100 Kreuzungen im Jahr; Jahresübersichten als Excel, auch mit Rad- und Fußzählungen. Bis 50 Zählungen kostenlos. 2020 geliefert – auf FragDenStaat liegen aber nur PDF-Umwandlungen.

**Empfehlung:** Die Excel-Originale und die Zählungen seit 2020 nachfordern, dazu eine Lizenz. Beim Amt für Verkehrsanlagen, Grundlage: Informationsfreiheitsgesetz M-V.

**Weg:** FragDenStaat, IFG M-V

**Kontakt:** Amt für Verkehrsanlagen Rostock · [FragDenStaat](https://fragdenstaat.de/behoerde/15967/amt-fur-verkehrsanlagen-hro/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Rostock seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

2020 haben Sie Jahresübersichten Ihrer Verkehrszählungen herausgegeben (FragDenStaat, „Verkehrszählung“); dort liegen nur PDF-Umwandlungen. Ich bitte um die Excel-Originale und die Zählungen seither.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [FragDenStaat 2020](https://fragdenstaat.de/anfrage/verkehrszahlung-14/)


## Stuttgart (BW) – nur Summen oder Mittelwerte offen

**Lage:** Offen sind Kordonzählungen am Stadtrand 1980–2024 als Summen (CSV, CC BY 4.0).

**Empfehlung:** Anfrage nach den Knotenpunkt- und Querschnittszählungen im Stadtgebiet. Grundlage: Landesinformationsfreiheitsgesetz Baden-Württemberg.

**Weg:** FragDenStaat, LIFG BW

**Kontakt:** Landeshauptstadt Stuttgart · <post@stuttgart.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/9384/stadt-stuttgart/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Stuttgart seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Offen sind die Kordonzählungen am Stadtrand; gemeint sind die Zählungen im Stadtgebiet.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [Open Data Stuttgart](https://opendata.stuttgart.de/en/dataset/ergebnisse-der-verkehrszaehlungen/resource/8345d864-0173-483f-adc7-8ded2d7c7855)


## Wolfsburg (NI) – erhoben – Anfrage aussichtsreich

**Lage:** Nutzt seit April 2026 dieselbe Zählsoftware wie München (DAVe). Wie viele Zählungen es gibt, ist nicht bekannt.

**Empfehlung:** Anfrage nach einem DAVe-Export und den älteren Zählungen. Niedersachsen hat kein Landes-IFG: Grundlage ist das Niedersächsische Umweltinformationsgesetz.

**Weg:** FragDenStaat, Niedersächsisches UIG

**Kontakt:** Stadtverwaltung Wolfsburg · <servicecenter@stadt.wolfsburg.de> · [FragDenStaat](https://fragdenstaat.de/behoerde/15210/wolfsburg/)

**Anfragetext** – Betreff: Ergebnisse von Verkehrszählungen (Knotenpunkte und Querschnitte) seit 2015

```text
Bitte übermitteln Sie mir die Ergebnisse aller Verkehrszählungen, die die Stadt Wolfsburg seit dem 1. Januar 2015 an Knotenpunkten und Straßenquerschnitten durchgeführt hat oder hat durchführen lassen – von Hand, per Video oder Radar; Dauerzählstellen ausgenommen. Je Zählung bitte:

1. Bezeichnung und Lage der Zählstelle (Koordinaten oder die beteiligten Straßen, gegebenenfalls Knotennummer),
2. Datum und gezählte Uhrzeiten,
3. die Zählwerte je Intervall (z. B. 15 oder 60 Minuten) und je Fahrtrichtung bzw. Verkehrsstrom, getrennt nach den erhobenen Verkehrsarten (Kfz nach Fahrzeugart, Rad, zu Fuß).

Bitte schicken Sie die Daten in dem maschinenlesbaren Format, in dem sie bei Ihnen vorliegen (z. B. CSV, XLSX oder Export der Zählsoftware); PDF-Berichte nur dort, wo es nichts anderes gibt. Eine Aufbereitung ist nicht nötig.

Sie nutzen seit April 2026 die Zählsoftware DAVe, die Exporte in offene Formate erlaubt. Ein solcher Export genügt; ältere Zählungen bitte in dem Format, in dem sie vorliegen.

Bitte nennen Sie mir außerdem, unter welchen Bedingungen ich die Daten weiterverwenden und veröffentlichen darf – am liebsten unter einer offenen Lizenz wie der Datenlizenz Deutschland – Namensnennung 2.0.

Verkehrsmengen sind Umweltinformationen: Sie bestimmen die Belastung durch Lärm und Luftschadstoffe und gehen in Lärmkartierung und Luftreinhalteplanung ein.
```

**Belege:** [DAVe](https://stadt.muenchen.de/news/open-source-anwendung-dave.html)


## Xanten (NW) – offen, noch nicht in der Karte

**Lage:** Offen ist eine Übersicht der Kreuzungszählungen aus dem Mobilitätskonzept.

**Empfehlung:** Keine Anfrage nötig: Adapter für die Übersicht bauen.

**Weg:** offen – Adapter bauen

**Belege:** [opendata.ruhr](https://opendata.ruhr/en/dataset/mobilitatskonzept/resource/fea95307-56ea-425c-9a77-535b88d10598)
