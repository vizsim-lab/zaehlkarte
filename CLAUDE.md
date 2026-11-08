# CLAUDE.md — zaehlkarte

Karte kommunaler Verkehrszählungen (Kurzzeitzählungen: Knotenpunkte, Querschnitte; Kfz, Rad,
Fuß nach Alter) aus mehreren Quellen in einem Schema. Stil und Aufbau des Frontends wie
`vizsim/unfallkarte`, Inhalte wie `vizsim/berlin-traffic-counts_schulwege`, Quellenverwaltung
wie `vizsim/svz`. Überblick: `README.md`. Quellenfinden und Sackgassen: `AGENTS.md`.
Diese Datei = die Regeln, die in jeder Session gelten.

## Repo-Layout
- **`pipeline/`** — uv-Paket `zaehlkarte` (Code `src/`, Config `config/`, Tests `tests/`,
  Rohdaten gitignored in `pipeline/data/`). CLI aus `pipeline/`: `uv run zaehlkarte fetch|build|site`.
- **`public/data/`** — die Kartendaten (manifest, index, details/NN, datenlage), erzeugt von
  `zaehlkarte site`, im Git. Vite kopiert `public/` unverändert nach `dist/`.
- **Repo-Wurzel** — das Frontend (Vite): `index.html`, `main.js`, `js/`, `style.css`,
  `vite.config.js`. Build -> `dist/` (gitignored). Ungebaut läuft es nicht (nackte Imports).
- **`tests/`** — `unit/` (node --test, browserlos), `web/` (Playwright gegen den Build),
  `fixtures/` (gemeinsam mit den Pipeline-Tests).

## Harte Regeln
- **`pipeline/config/sources.yaml` ist die einzige Quellenliste** – Quellen, Lizenzen und die
  Datenlage-Einträge. Das Frontend bekommt alles über `manifest.json`/`datenlage.json`; nie im
  Frontend nachtragen. Rechtliche Aussagen in der Datenlage nur mit Beleg (Link).
- **Erzeugte Dateien nicht von Hand ändern:** `public/data/*`. Immer `uv run zaehlkarte site`.
- **Frontend-Vertrag:** Feldnamen in `index.json` (`stellen.felder`, `zaehlungen.felder`,
  `gruppen`, `quellen`, `lieferungen`), Aufbau von `details/NN.json`, Dateinamen in
  `manifest.dateien`. Wer sie ändert, zieht `js/data/modell.js`, `js/ui/detail.js` und
  `tests/web/vertrag.spec.js` im selben Schritt mit.
- **Kriterium an zwei Stellen, gleich:** `kennzahlen.verdacht/status` (Pipeline) und
  `verdacht/status` in `js/data/modell.js`. Beide prüfen dieselben Fälle aus
  `tests/fixtures/kriterium.json` – neuer Fall dort, nicht nur in einem Test.
- **Wording:** „Schulweg-Verdacht“, nie „Schulweg“ als Tatsache; Quellkategorien Jugend,
  Kinder, Schüler heißen „Kinder/Jugendliche“. `-1`/fehlend heißt „nicht gezählt“, nie 0. An
  schulfreien Tagen kein Verdacht. Werte aus verschiedenen Zählfenstern nie ineinander
  umrechnen (keine Hochrechnung 7–19 -> 24 h); die Kennzahl-Art steht immer dabei.
- **Rohdaten bleiben unverändert**; Berlin-Archive und Geokodierung sind auf Commits gepinnt
  (sha256 in sources.yaml).
- **Keyless:** Hintergrund OpenFreeMap (Positron, lokale `public/style.json` ohne Sprite),
  Relief Mapterhorn, Suche Photon. Keine API-Keys, keine Secrets im Repo.
- **MapLibre (ESM, v6):** nur über `js/lib/maplibre.js` importieren; wird NICHT gebündelt
  (versionierte Kopie + Importmap, `vite.config.js`). `appType: "mpa"` nicht entfernen.
  Die Karte wartet auf `style.load`, nicht auf `load` – sonst bliebe sie leer, wenn
  OpenFreeMap nicht erreichbar ist.
- **`data-tip` nur an Hinweis-Zeichen (ⓘ), nie an Knöpfen oder Links:** der Tooltip fängt
  Klicks darauf ab (Touch). Bedienelemente bekommen `title`/`aria-label`.
- **REIN halten** (kein DOM, kein window): `js/data/modell.js`, `js/ui/diagramme.js`,
  `js/utils/permalinkFormat.js` – browserlos getestet. Permalink-Kürzel sind Vertrag mit
  geteilten Links: nie umdeuten, nur ergänzen.
- **Fremde Texte** (Namen, Bemerkungen aus den Daten) nur escaped ins HTML (`esc()`).
- **Lizenz:** AGPL-3.0-or-later. Aus dem Schulwege-Projekt (MIT) übernommene Dateien tragen
  einen Herkunftsvermerk.

## Konventionen
- **uv**, nie `pip install`. Lint `uvx ruff check`, Tests `uv run pytest` (aus `pipeline/`).
- **Sprache:** Deutsch in UI, Doku, Kommentaren und Bezeichnern.
- **Neue Quelle:** Eintrag in `sources.yaml` (`status: research` bis der Adapter steht),
  Adapter mit `lese(quelle, pfade, bericht)` und `Bericht`, Test mit synthetischer Datei.
  Mehrere Kommunen mit gleichem Format teilen sich einen Adapter (`adapter:`).
- **Frontend:** `npm run dev`; vor jedem Push `npm run test:unit` und `npm run test:web`
  (Playwright sperrt das Netz außer dem Testserver – die Karte muss ohne Hintergrund laufen).
  Neues Verhalten = neuer Test in `tests/web/`.
- **Daten neu bauen:** Workflow „Kartendaten neu bauen“ (`.github/workflows/daten.yml`) oder
  lokal `fetch` + `site`. Das Ergebnis kommt als PR. MobiData BW ist aus manchen
  Entwicklungsumgebungen nicht erreichbar – dann den Workflow nutzen.
- Push auf `main` = Produktiv-Deploy nach GitHub Pages (nach grünen Frontend-Tests). Größere
  Umbauten auf einem Branch mit PR.
