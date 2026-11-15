# Entwicklung

Aufbau des Repositorys, Befehle für Pipeline und Karte, die Workflows. Die Regeln für jede
Änderung stehen in [CLAUDE.md](../CLAUDE.md), wie man Quellen findet in [AGENTS.md](../AGENTS.md).

## Aufbau

```
pipeline/            uv-Paket `zaehlkarte`: Rohdaten -> ein Zählungsschema -> Kartendaten
  config/              die einzige Quellenliste: je Quelle eine Datei, Datenlage je Land,
                       Rechtslage, robots-Ausnahmen, Ferien (Aufbau: config/README.md)
  src/zaehlkarte/adapters/  ein Adapter je Format (berlin_zda, mobidata_bw, muenster, moers_radar,
                            olpe_radar, konstanz_mobil, potsdam_pdf, xanten_pdf,
                            tuebingen_pdf, neubulach_pdf)
  src/zaehlkarte/dauer/     Familie Dauerzählstellen (berlin_viz, hamburg_sta, readi_urbanpulse;
                            Rad: mobidata_eco, muenster_rad, aachen_rad, berlin_rad,
                            muenchen_rad, ods_eco, dortmund_rad, essen_rad, bochum_rad,
                            bonn_rad, duesseldorf_rad, leipzig_rad, rostock_rad), eigener Bau
public/data/         die Kartendaten (erzeugt, im Git): manifest, index, details/NN, datenlage
public/data/dauer/   Dauerzählstellen (erzeugt, NICHT im Git – Release-Asset, siehe unten)
public/logo/         Logo, Signet und kleines Zeichen (SVG); Favicons und App-Icon in public/
docs/                Quellen, was die Karte zeigt, Entwicklung, Logo; DATENLAGE.md (erzeugt)
index.html, main.js, js/, style.css   die Karte (Vite, MapLibre, Positron von OpenFreeMap)
  js/sprache/          Texte der Oberfläche DE/EN (texte.js) und der Umschalter
tests/               unit/ (node --test), web/ (Playwright gegen den Build)
```

```bash
# Pipeline (aus pipeline/)
uv sync
uv run zaehlkarte fetch      # Rohdaten nach pipeline/data/raw/
uv run zaehlkarte site       # Kartendaten nach public/data/
uv run zaehlkarte datenlage  # nur datenlage.json und docs/DATENLAGE.md (geänderte Datenlage-Texte)
uv run zaehlkarte dauer fetch && uv run zaehlkarte dauer site   # Dauerzählstellen
uv run pytest && uvx ruff check

# Karte (aus der Wurzel)
npm ci
npm run dev                  # http://localhost:5173
npm run test:unit && npm run test:web
```

Eine neue Quelle: eine Datei in `pipeline/config/quellen/<familie>/` (Aufbau:
[pipeline/config/README.md](../pipeline/config/README.md)), Adapter in
`src/zaehlkarte/adapters/` (liefert `Zaehlung`-Objekte, siehe `modell.py`), Test mit einer
kleinen synthetischen Datei in `pipeline/tests/`. Wie man Quellen findet und was nicht
funktioniert hat: [AGENTS.md](../AGENTS.md).

## Daten erneuern

Die Daten erneuert der Workflow „Kartendaten neu bauen“ (monatlich und von Hand) als Pull
Request; scheitert der Abruf einer Quelle, endet er rot ohne PR und nennt sie. Die
Dauerzählstellen baut der Workflow „Dauerzählstellen bauen“ (wöchentlich, von Hand und bei
Änderungen an `pipeline/src/zaehlkarte/dauer/` oder der Konfiguration) und legt sie als
Release-Asset `dauerzaehlstellen/dauer.tar.gz` ab – Daten, die sich laufend ändern, gehören
nicht ins Git. Eine Quelle, die scheitert, hält die anderen nicht auf; sie steht als Warnung am
Lauf. Die CI holt das Asset vor dem Build; fehlt es, zeigt die Karte nur die Kurzzeitzählungen.

## Gedächtnis

Hamburg hält Stundenwerte nur zwei Monate vor, Leipzig 31 Tage (Tageswerte:
Hamburg laut Beschreibung das laufende und das letzte Jahr, Leipzig zwei Jahre). Was die
Zählkarte davon aufhebt (Monatsdateien je Quelle, `<code>__stunden_JJJJ-MM.csv.gz`, die
Tageswerte je Jahr `<code>__tage_JJJJ.csv.gz` und für Hamburg die Straßennamen
`<code>__strassen.json`), liegt im selben Release. Der Workflow holt es
vor dem Abruf und legt danach ab, was sich geändert hat – nie mit weniger Werten
(`pipeline/werkzeuge/gedaechtnis.py`). Wer diese Assets löscht, verliert die Stunden, die die
Quelle nicht mehr hat. Darum liegt jede Fassung zusätzlich im Release
`gedaechtnis-kopie-JJJJ` (eins je Jahr, nie überschrieben). Ist die jüngste Stunde einer Quelle
älter als 10 Tage, wird der Wochenlauf rot (`zaehlkarte dauer frische`): Dann scheitert ihr Abruf
seit mindestens einer Woche, und Leipzig etwa bleiben noch gut zwei Wochen bis zum Verlust.
Ebenso, wenn die Schulferien eines Landes in drei Monaten enden (`zaehlkarte kalender`): Ferien
und Feiertage gibt es für alle 16 Länder, aus den KMK-Ferienkalendern bis 2027/28.

## Auslieferung

Jeder Push auf `main` wird nach grünen Tests nach GitHub Pages ausgeliefert.
