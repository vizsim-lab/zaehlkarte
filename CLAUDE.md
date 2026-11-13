# CLAUDE.md — zaehlkarte

Karte kommunaler Verkehrszählungen aus mehreren Quellen in zwei Familien:
Kurzzeitzählungen (Knotenpunkte, Querschnitte) und Dauerzählstellen (Stunden- und Tageswerte
fest eingebauter Zähler) – nur Zählwerte, je Verkehrsart (Kfz, Schwerverkehr, Rad, Fuß; bei
Dauerzählstellen die Klassen der Detektoren: Kfz, Lkw bzw. Schwerverkehr laut Detektor, Rad).
Jahresmittel (DTV), Verkehrsmengenkarten und Modellwerte gehören nach `vizsim/svz`. Stil und
Aufbau des Frontends wie `vizsim/unfallkarte`,
ZDA-Leser aus `vizsim/berlin-traffic-counts_schulwege`, Quellenverwaltung wie `vizsim/svz`.
Auswertungen (etwa der Schulweg-Verdacht) gehören NICHT hierher, sondern in die Schulwege-Karte.
Überblick: `README.md`. Quellenfinden und Sackgassen: `AGENTS.md`.
Diese Datei = die Regeln, die in jeder Session gelten.

## Repo-Layout
- **`pipeline/`** — uv-Paket `zaehlkarte` (Code `src/`, Config `config/`, Tests `tests/`,
  Rohdaten gitignored in `pipeline/data/`). CLI aus `pipeline/`: `uv run zaehlkarte fetch|build|site`.
- **`public/data/`** — die Kartendaten (manifest, index, details/NN, datenlage), erzeugt von
  `zaehlkarte site`, im Git. Vite kopiert `public/` unverändert nach `dist/`.
- **`public/data/dauer/`** — Dauerzählstellen, erzeugt von `zaehlkarte dauer site`, NICHT im
  Git (gitignored): Workflow „Dauerzählstellen bauen“ legt sie als Release-Asset
  `dauerzaehlstellen/dauer.tar.gz` ab, die CI holt es vor dem Build. Im selben Release liegt
  das **Gedächtnis** der Quellen, die Stundenwerte nur kurz vorhalten (Hamburg: zwei Monate):
  Assets `<code>__<datei>` aus `pipeline/data/raw/<code>/gedaechtnis/`, geholt und abgelegt von
  `pipeline/werkzeuge/gedaechtnis.py` – nie löschen, nie mit weniger Werten ersetzen (sonst
  sind die Stunden verloren).
- **Repo-Wurzel** — das Frontend (Vite): `index.html`, `main.js`, `js/`, `style.css`,
  `vite.config.js`. Build -> `dist/` (gitignored). Ungebaut läuft es nicht (nackte Imports).
- **`tests/`** — `unit/` (node --test, browserlos), `web/` (Playwright gegen den Build).

## Harte Regeln
- **`pipeline/config/sources.yaml` ist die einzige Quellenliste** – Quellen, Lizenzen und die
  Datenlage-Einträge. Das Frontend bekommt alles über `manifest.json`/`datenlage.json`; nie im
  Frontend nachtragen. Rechtliche Aussagen in der Datenlage nur mit Beleg (Link).
- **Erzeugte Dateien nicht von Hand ändern:** `public/data/*`, `docs/DATENLAGE.md` (beide
  `uv run zaehlkarte site`; nur `datenlage.json` und `DATENLAGE.md` nach geänderten
  Datenlage-Texten: `uv run zaehlkarte datenlage`), `pipeline/geokodierung/berlin_ergaenzung.csv`
  (Workflow „Berlin geokodieren“), `pipeline/geokodierung/moers.csv`
  (`werkzeuge/geokodiere_moers.py`).
- **Datenlage-Texte** (Lage, Empfehlung, Anfragezusatz, Kontakt) stehen in `sources.yaml`.
  Kontakte nur als Funktionsadressen (keine Namen einzelner Beschäftigter), aus der
  FragDenStaat-Behördendatenbank; die Anfragevorlage (`anfrage_vorlage`) ist für alle gleich.
  Die Datenlage folgt der Familie: je Kommune `stand` für die Kurzzeitzählungen und, wo
  recherchiert, ein Block `dauer:` (`stand` in_karte | offen | kandidat, `was`, `links`) für die
  Dauerzählstellen – die Karte zeigt bei ihnen nur Kommunen mit diesem Block, ohne Anfragetext.
- **Frontend-Vertrag:** Feldnamen in `index.json` (`stellen.felder`, `zaehlungen.felder`,
  `gruppen`, `quellen`, `lieferungen`), Aufbau von `details/NN.json`, Dateinamen in
  `manifest.dateien`. Wer sie ändert, zieht `js/data/modell.js`, `js/ui/detail.js` und
  `tests/web/vertrag.spec.js` im selben Schritt mit. Dauerzählstellen: Felder in
  `dauer/index.json` (`stellen.felder`, `gruppen` = Bits von `g`, `dateien`, `kalender`,
  `standardtag`, `juengster`, `quellen[].gruppen`/`zeitraeume`/`standardtag`), Aufbau von
  `dauer/tage/JJJJ.json` und `dauer/NN.json` (Kopf von `pipeline/src/zaehlkarte/dauer/site.py`)
  – mitziehen: `js/data/dauer.js`, `js/ui/dauerdetail.js`, `tests/web/vertrag.spec.js` und die
  Fixtures `tests/web/fixtures/dauer/`, und die Vertragsversion erhöhen (`VERSION` in
  `dauer/site.py` = `DAUER_VERSION` in `js/data/dauer.js`): Bis „Dauerzählstellen bauen“ nach dem
  Merge neu gebaut hat, überspringt der Vertragstest das alte Asset im PR; auf `main` hält er die
  Auslieferung so lange an.
- **Nur Zählwerte, keine Einstufungen.** Je Verkehrsart Menge (und bei Schwerverkehr/Rad der
  Anteil). Kinder/Jugendliche nur als Zählkategorie (Tagesgang Fuß), keine Schwellen.
  Dauerzählstellen: eine Tagessumme nur aus allen Stunden des Tages (Zeitumstellung beachten),
  sonst „nicht vollständig gezählt“ – nie auffüllen, keine Mittel über Tage, kein DTV. Klassen
  der Detektoren nie zusammenzählen oder ineinander umrechnen: Berlins und Ettlingens „Lkw“ und
  Hamburgs „Schwerverkehr“ bleiben eigene Gruppen der Daten, keine ist der Schwerverkehr der
  Kurzzeitzählungen. Die Karte zeigt sie unter einem Chip „Lkw/Schwerverkehr“ – jede Stelle in
  ihrer Klasse und mit deren Namen, die Legende nennt, welche Stadt welche Klasse zählt.
  Standardansicht: je Stelle der jüngste vollständig gezählte Schultag (so stehen alle Quellen
  zugleich in der Karte; der Tag steht bei jedem Wert), ein gewählter Tag gilt für alle.
- **Wording:** Quellkategorien Jugend, Kinder, Schüler heißen „Kinder/Jugendliche“.
  `-1`/fehlend heißt „nicht gezählt“, nie 0. Werte aus verschiedenen Zählfenstern nie
  ineinander umrechnen (keine Hochrechnung 7–19 -> 24 h); die Kennzahl-Art steht immer dabei.
- **Rohdaten bleiben unverändert**; Berlin-Archive und Geokodierung sind auf Commits gepinnt,
  Münster-ZIP und -Positionen, die Konstanzer CSVs und die Xantener PDFs über ihre Prüfsumme
  (sha256 in sources.yaml).
- **Keyless:** Hintergrund OpenFreeMap (Positron, lokale `public/style.json` ohne Sprite),
  Relief Mapterhorn, Suche Photon. Keine API-Keys, keine Secrets im Repo.
- **MapLibre (ESM, v6):** nur über `js/lib/maplibre.js` importieren; wird NICHT gebündelt
  (versionierte Kopie + Importmap, `vite.config.js`). `appType: "mpa"` nicht entfernen.
  Die Karte wartet auf `style.load`, nicht auf `load` – sonst bliebe sie leer, wenn
  OpenFreeMap nicht erreichbar ist.
- **`data-tip` nur an Hinweis-Zeichen (ⓘ), nie an Knöpfen oder Links:** der Tooltip fängt
  Klicks darauf ab (Touch). Bedienelemente bekommen `title`/`aria-label`.
- **REIN halten** (kein DOM, kein window): `js/data/modell.js`, `js/data/dauer.js`,
  `js/ui/diagramme.js`, `js/utils/permalinkFormat.js`, `js/sprache/texte.js` – browserlos
  getestet.
  Permalink-Kürzel sind Vertrag mit geteilten Links: nie umdeuten, nur ergänzen (die Sprache
  steht nicht im #-Teil, sondern in `?lang=`).
- **Fremde Texte** (Namen, Bemerkungen aus den Daten) nur escaped ins HTML (`esc()`).
- **Lizenzen mit Einschränkung** (Ettlingen: CC BY-NC 4.0, nur nicht kommerziell) nur mit
  Hinweis an der Quelle (`hinweise` in sources.yaml); die Lizenz steht in der Seitenleiste und in
  jeder Zeile des CSV-Exports – nie eine Quelle ohne Lizenzangabe aufnehmen.
- **Lizenz:** AGPL-3.0-or-later. Aus dem Schulwege-Projekt (MIT) übernommene Dateien tragen
  einen Herkunftsvermerk.

## Konventionen
- **uv**, nie `pip install`. Lint `uvx ruff check`, Tests `uv run pytest` (aus `pipeline/`).
- **Sprache:** Deutsch in Doku, Kommentaren und Bezeichnern. Die UI ist zweisprachig
  (Deutsch Standard, Englisch per Umschalter): jeder neue UI-Text als Schlüssel in
  `js/sprache/texte.js`, in beiden Sprachen (Unit-Test prüft gleiche Schlüssel und
  Platzhalter); statisches HTML über `data-i18n`/`data-i18n-attr`. Inhalte aus den Daten
  (Hinweise, Quellenbeschreibungen, Datenlage- und Anfragetexte) bleiben deutsch und tragen
  `lang="de"`; englische Stand-Namen kommen als `manifest.stand_en` aus `site.py`. CSV-Exporte
  bleiben in beiden Sprachen gleich (deutsche Spalten und Werte).
- **Neue Quelle:** Eintrag in `sources.yaml` (`status: research` bis der Adapter steht),
  Adapter mit `lese(quelle, pfade, bericht)` und `Bericht`, Test mit synthetischer Datei.
  Mehrere Kommunen mit gleichem Format teilen sich einen Adapter (`adapter:`).
- **Frontend:** `npm run dev`; vor jedem Push `npm run test:unit` und `npm run test:web`
  (Playwright sperrt das Netz außer dem Testserver – die Karte muss ohne Hintergrund laufen).
  Neues Verhalten = neuer Test in `tests/web/`.
- **Daten neu bauen:** Workflow „Kartendaten neu bauen“ (`.github/workflows/daten.yml`) oder
  lokal `fetch` + `site`. Das Ergebnis kommt als PR. MobiData BW und die Portale von Münster,
  Konstanz, Potsdam und Olpe sind aus manchen Entwicklungsumgebungen nicht erreichbar – dann den
  Workflow nutzen. Dauerzählstellen: Workflow „Dauerzählstellen bauen“
  (`.github/workflows/dauer.yml`, wöchentlich) – Ergebnis als Release-Asset, kein PR; danach
  startet er die CI auf `main` neu. Das Berliner Archiv, `iot.hamburg.de` und
  `opendata.readi.de` (Ettlingen) sind aus der Sandbox ebenfalls nicht erreichbar
  (Werkzeug-Branch `werkzeug/dauer`, `tools/lauf.sh`).
- Push auf `main` = Produktiv-Deploy nach GitHub Pages (nach grünen Frontend-Tests). Größere
  Umbauten auf einem Branch mit PR.
