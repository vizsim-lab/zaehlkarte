# Pipeline der Zählkarte

uv-Paket `zaehlkarte`: liest jede Quelle aus `config/sources.yaml` mit ihrem Adapter, bringt
alle Zählungen in ein Schema (`src/zaehlkarte/modell.py`) und schreibt die Kartendaten nach
`../public/data/`.

```
fetch  Rohdaten -> data/raw/           Berlin-Archive + Geokodierung (sha256 geprüft),
                                         MobiData BW: Übersicht + Excel aus den ZIPs,
                                         Münster: Positionen + XLS/PDF aus dem ZIP (sha256),
                                         Moers: Datensätze 2010–2022 (CKAN-API),
                                         Olpe: alle Verkehrsmessungen (CKAN-Suche), JSON,
                                         Konstanz: eine CSV je Standort (sha256),
                                         Potsdam: Knotenliste (API) + Zählpläne aus den ZIPs,
                                         Xanten: zwei PDFs (sha256)
build  Adapter -> Zählungen             Zähltag (Ferienkalender je Land), Lage übertragen,
                                         Stellen bilden (je Kennung, 150 m)
site   -> public/data/                  manifest.json, index.json, details/NN.json, datenlage.json

dauer fetch  -> data/raw/berlin_viz/     Berlin: Monatsarchive der Verkehrsdetektion (Content-MD5)
             -> data/raw/hamburg_*/      Hamburg: Stellen (stellen.json) und gedaechtnis/ (Stunden
                                         je UTC-Monat, Straßennamen aus OSM)
             -> data/raw/ettlingen/      Ettlingen: Datastore von re@di
             -> data/raw/*_rad/          Rad-Zählstellen: MobiData BW (Monatsdateien, fehlende und
                                         die jüngsten zwei), Münster (Archiv des GitHub-Repositorys,
                                         sha256), Aachen (Jahres-CSV, PDF der Standorte), Berlin
                                         (Excel, sha256), München (Jahres- und Monatsdateien, WFS),
                                         Würzburg, Rhein-Kreis Neuss, Dortmund (Opendatasoft-Export,
                                         nur bei Änderung), Essen (Quartale über Open.NRW), Leipzig
                                         (WFS -> gedaechtnis/), Rostock (CSV, GeoJSON), Bochum
                                         (GitLab, eine CSV je Zählstelle)
dauer site   -> public/data/dauer/       index.json, tage/JJJJ.json, NN.json (nicht im Git)
```

| Modul | Aufgabe |
|---|---|
| `adapters/berlin_zda.py`, `zda.py`, `kategorien.py`, `berlin_bezeichnung.py` | Berliner ZDA-Dateien (aus dem Schulwege-Projekt) |
| `adapters/mobidata_bw.py` | MobiData BW (Ravensburg & Co.) |
| `adapters/moers_radar.py` | Moers: Seitenradar-Messungen (eine Zeile je Fahrzeug) |
| `adapters/olpe_radar.py` | Olpe: Radar-Messungen als JSON (je Fahrzeug, UTC, GPS je Tag) |
| `adapters/konstanz_mobil.py` | Konstanz: mobile Zählgeräte, 5- und 15-Minuten-Werte je Richtung |
| `adapters/potsdam_pdf.py` | Potsdam: Zählpläne (PDF) mit Spitzenstunden und 6-Stunden-Summen |
| `adapters/xanten_pdf.py` | Xanten: Viertelstundenwerte aus den PDFs des Mobilitätskonzepts |
| `adapters/muenster.py`, `muenster_xls.py`, `muenster_pdf.py` | Münster: Knotenstrompläne als XLS (2000–2012) und PDF (2010–2020) |
| `koordinaten.py` | UTM -> Länge/Breite, örtliche Anpassung Gauß-Krüger -> UTM |
| `kalender.py` | Schultag, Ferien, Feiertag, Wochenende je Land |
| `kennzahlen.py` | Summen je Zeitfenster, stärkste Stunde |
| `build.py` | Lage übertragen, Stellen bilden |
| `site.py` | Kartendaten (Vertrag mit dem Frontend, Kopfkommentar) |
| `dauer/modell.py` | Dauerzählstellen: Messreihe (Stelle × Tag × Stunde), Tagessummen, Zeitumstellung |
| `dauer/berlin_viz.py` | Berlin: Verkehrsdetektion, alte und neue Qualitätssicherung, Stammdaten |
| `dauer/hamburg_sta.py` | Hamburg: Wärmebildkameras über SensorThings, Gedächtnis (Monatsdateien), UTC -> Ortszeit |
| `dauer/readi_urbanpulse.py` | Ettlingen: Datastore von re@di (UrbanPulse-Ströme je Fahrtrichtung), Kfz als Summe der Klassen |
| `dauer/mobidata_eco.py` | Rad-Zählstellen in Baden-Württemberg (Eco-Counter, gebündelt von MobiData BW), Stundenwerte in Ortszeit |
| `dauer/muenster_rad.py` | Münster: Rad-Zählstellen (Eco-Counter) aus dem GitHub-Repository der Stadt, Status je Viertelstunde |
| `dauer/aachen_rad.py` | Aachen: Radzählstellen je Kanal (UTC), Standorte aus dem PDF |
| `dauer/berlin_rad.py` | Berlin: Rad-Zählstellen aus der Excel-Datei der Senatsverwaltung, Markierungen per Zellfarbe |
| `dauer/muenchen_rad.py` | München: Raddauerzählstellen, 15-Minuten-Werte (drei Datumsformate), Lage aus dem WFS |
| `dauer/ods.py`, `dauer/ods_eco.py` | Opendatasoft-Export (nur bei Änderung); Würzburg und Rhein-Kreis Neuss: Eco-Counter-Stunden (UTC) mit Status, in Neuss je Kanal |
| `dauer/dortmund_rad.py` | Dortmund: Schnettkerbrücke, 15-Minuten-Werte in Ortszeit mit Versatz |
| `dauer/essen_rad.py` | Essen: Quartalsdateien (Lizenz je Ressource), Spalten nach Reihenfolge |
| `dauer/leipzig_rad.py` | Leipzig: WFS mit 31 Tagen, Gedächtnis; doppelte 2 Uhr nach objectid, jüngste Lieferung gilt |
| `dauer/rostock_rad.py` | Rostock: Radmonitore, 15-Minuten-Werte mit Versatz, Standorte als GeoJSON |
| `dauer/bochum_rad.py` | Bochum: Gesamtdatei je Zählstelle aus dem GitLab der Stadt, nur Rad |
| `dauer/gedaechtnis.py` | Gedächtnis der Quellen mit kurzer Vorhaltezeit (Hamburg, Leipzig): Monatsdateien je UTC-Tag |
| `dauer/strassen.py` | nächste benannte Straße aus einem OSM-Abzug (für Quellen ohne Straßennamen) |
| `werkzeuge/gedaechtnis.py` | Gedächtnis im Release `dauerzaehlstellen` holen und ablegen (Workflow) |
| `werkzeuge/kmk_ferien.py` | Schulferien eines Landes aus den KMK-Ferienkalendern (Text von `pdftotext -layout`), mit Abgleich gegen eine vorhandene CSV |
| `dauer/site.py`, `dauer/bau.py` | Dauerzählstellen schreiben (Vertrag im Kopfkommentar) bzw. holen und bauen |

Konfiguration: `config/sources.yaml` (Quellen, Datenlage, Rechtslage je Land),
`config/schulferien_*.csv` (KMK-Ferienkalender für die Einordnung des Zähltags),
`config/berlin_rohdateien_2019-2025.txt` (welche Berliner Rohdateien einzeln online liegen).
`geokodierung/berlin_ergaenzung.csv`: Lage der Berliner Zählungen, die weder GPS noch einen
Eintrag im Schulwege-Cache haben – erzeugt vom Workflow „Berlin geokodieren“
(`zaehlkarte geokodier-liste` + `werkzeuge/geokodiere_berlin.py` mit dem Schulwege-Geocoder).
`geokodierung/moers.csv`: Lage der Moerser Messstellen aus ihren Adressen – erzeugt von
`werkzeuge/geokodiere_moers.py` (Nominatim, Overpass, Photon; braucht Netz, z. B. GitHub Actions).

```bash
uv sync
uv run zaehlkarte fetch            # ~450 MB Download (MobiData-ZIPs samt PDFs)
uv run zaehlkarte build            # Bericht ohne zu schreiben
uv run zaehlkarte site             # Kartendaten schreiben (~1,5 min)
uv run zaehlkarte datenlage        # nur datenlage.json und docs/DATENLAGE.md (aus sources.yaml
                                   # und der vorhandenen index.json, ohne neuen Bau)
uv run zaehlkarte dauer fetch      # Dauerzählstellen: ~330 MB (Berliner Monatsarchive), Hamburg
                                   # über SensorThings (erster Abruf ohne Gedächtnis: einige Minuten)
uv run zaehlkarte dauer site       # public/data/dauer/ schreiben (~30 MB, ~5 min)
uv run pytest && uvx ruff check
```
