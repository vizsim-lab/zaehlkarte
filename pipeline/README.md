# Pipeline der Zählkarte

uv-Paket `zaehlkarte`: liest jede Quelle aus `config/sources.yaml` mit ihrem Adapter, bringt
alle Zählungen in ein Schema (`src/zaehlkarte/modell.py`) und schreibt die Kartendaten nach
`../public/data/`.

```
fetch  Rohdaten -> data/raw/           Berlin-Archive + Geokodierung (sha256 geprüft),
                                         MobiData BW: Übersicht + Excel aus den ZIPs,
                                         Münster: Positionen + XLS aus dem ZIP (sha256)
build  Adapter -> Zählungen             Zähltag (Ferienkalender je Land), Lage übertragen,
                                         Stellen bilden (je Kennung, 150 m)
site   -> public/data/                  manifest.json, index.json, details/NN.json, datenlage.json
```

| Modul | Aufgabe |
|---|---|
| `adapters/berlin_zda.py`, `zda.py`, `kategorien.py`, `berlin_bezeichnung.py` | Berliner ZDA-Dateien (aus dem Schulwege-Projekt) |
| `adapters/mobidata_bw.py` | MobiData BW (Ravensburg & Co.) |
| `adapters/muenster_xls.py` | Münster: Knotenstrompläne als XLS (2000–2012) |
| `koordinaten.py` | UTM -> Länge/Breite, örtliche Anpassung Gauß-Krüger -> UTM |
| `kalender.py` | Schultag, Ferien, Feiertag, Wochenende je Land |
| `kennzahlen.py` | Summen je Zeitfenster, stärkste Stunde |
| `build.py` | Lage übertragen, Stellen bilden |
| `site.py` | Kartendaten (Vertrag mit dem Frontend, Kopfkommentar) |

Konfiguration: `config/sources.yaml` (Quellen, Datenlage, Rechtslage je Land),
`config/schulferien_*.csv` (KMK-Ferienkalender für die Einordnung des Zähltags),
`config/berlin_rohdateien_2019-2025.txt` (welche Berliner Rohdateien einzeln online liegen).
`geokodierung/berlin_ergaenzung.csv`: Lage der Berliner Zählungen, die weder GPS noch einen
Eintrag im Schulwege-Cache haben – erzeugt vom Workflow „Berlin geokodieren“
(`zaehlkarte geokodier-liste` + `werkzeuge/geokodiere_berlin.py` mit dem Schulwege-Geocoder).

```bash
uv sync
uv run zaehlkarte fetch            # ~450 MB Download (MobiData-ZIPs samt PDFs)
uv run zaehlkarte build            # Bericht ohne zu schreiben
uv run zaehlkarte site             # Kartendaten schreiben (~1,5 min)
uv run pytest && uvx ruff check
```
