# CLAUDE.md — zaehlkarte

Karte kommunaler Verkehrszählungen aus mehreren Quellen in zwei Familien:
Kurzzeitzählungen (Knotenpunkte, Querschnitte) und Dauerzählstellen (Stunden- und Tageswerte
fest eingebauter Zähler: Detektoren, Kameras, Rad-Zählstellen) – nur Zählwerte, je Verkehrsart
(Kfz, Schwerverkehr, Rad, Fuß; bei Dauerzählstellen die Klassen der Detektoren: Kfz, Lkw bzw.
Schwerverkehr laut Detektor, Rad). Nur kommunale Zählstellen; die Dauerzählstellen von Bund und
Ländern (BASt, Landesstraßen) nicht – sie stehen dokumentiert in `AGENTS.md`.
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
  das **Gedächtnis** der Quellen, die Stundenwerte nur kurz vorhalten (Hamburg: zwei Monate,
  Leipzig: 31 Tage):
  Assets `<code>__<datei>` aus `pipeline/data/raw/<code>/gedaechtnis/`, geholt und abgelegt von
  `pipeline/werkzeuge/gedaechtnis.py` – nie löschen, nie mit weniger Werten ersetzen (sonst
  sind die Stunden verloren). Eine zweite Kopie jeder Fassung liegt je Jahr im Release
  `gedaechtnis-kopie-JJJJ` (ebenso nie löschen); `zaehlkarte dauer frische` macht den
  Wochenlauf rot, wenn das Gedächtnis einer Quelle seit 10 Tagen nicht gewachsen ist.
- **Repo-Wurzel** — das Frontend (Vite): `index.html`, `main.js`, `js/`, `style.css`,
  `vite.config.js`. Build -> `dist/` (gitignored). Ungebaut läuft es nicht (nackte Imports).
- **`tests/`** — `unit/` (node --test, browserlos), `web/` (Playwright gegen den Build).

## Harte Regeln
- **`pipeline/config/` ist die einzige Quellenliste** – je Quelle eine Datei
  (`quellen/kurzzeit|dauer/<code>.yaml`, der Dateiname ist der Code), die Datenlage je Land
  (`kommunen/<LAND>.yaml`), Rechtslage, Anfragevorlage, robots-Ausnahmen, Ferien
  (`kalender/ferien/<LAND>.csv`); Aufbau in `pipeline/config/README.md`. `nr` legt die
  Reihenfolge der Quellen in den Kartendaten fest: eine neue Quelle bekommt die nächste Nummer,
  nie umnummerieren. Das Frontend bekommt alles über `manifest.json`/`datenlage.json`; nie im
  Frontend nachtragen. Rechtliche Aussagen in der Datenlage nur mit Beleg (Link).
- **Erzeugte Dateien nicht von Hand ändern:** `public/data/*`, `docs/DATENLAGE.md` (beide
  `uv run zaehlkarte site`; nur `datenlage.json` und `DATENLAGE.md` nach geänderten
  Datenlage-Texten: `uv run zaehlkarte datenlage`), `pipeline/geokodierung/berlin_ergaenzung.csv`
  (Workflow „Berlin geokodieren“), `pipeline/geokodierung/moers.csv`
  (`werkzeuge/geokodiere_moers.py`).
- **Datenlage** (`config/kommunen/<LAND>.yaml`, Aufbau in `pipeline/config/README.md`): je
  Kommune `ags` (amtlicher Gemeindeschlüssel, bei Kreisen der Kreisschlüssel – der Schlüssel der
  Kommune, das Land steckt darin), `name`, `lage`, und je Familie ein Block `kurzzeit:` bzw.
  `dauer:` mit `stand`, `quellen` (die Quellen der Familie, die die Kommune in die Karte bringen –
  kein Abgleich über Namen), `was`, `situation`, `links`; bei den Kurzzeitzählungen dazu
  `empfehlung`, `weg`, `anfrage`. Eine Liste von Ständen für beide Familien (`datenlage.STAND`:
  in_karte, offen, geliefert, kandidat, ohne_lizenz, aggregiert, nur_karte, abgelehnt,
  nichts_offen). Die Karte zeigt je Familie nur Kommunen mit deren Block; Kommunen, von denen nur
  Dauerzählstellen bekannt sind, haben keinen Block `kurzzeit:`. Kontakte nur als
  Funktionsadressen (keine Namen einzelner Beschäftigter), aus der FragDenStaat-Behördendatenbank;
  die Anfragevorlage (`anfrage_vorlage.yaml`) ist für alle gleich – nur die angefragte Stelle ist
  „Stadt {kommune}“ oder `anfrage.an` (etwa „Gemeinde Mühltal“); einen Anfragetext gibt es nur
  bei den Kurzzeitzählungen.
- **Frontend-Vertrag:** Feldnamen in `index.json` (`stellen.felder`, `zaehlungen.felder`,
  `gruppen`, `quellen`, `lieferungen`), Aufbau von `details/NN.json`, Dateinamen in
  `manifest.dateien`. Wer sie ändert, zieht `js/data/modell.js`, `js/ui/detail.js` und
  `tests/web/vertrag.spec.js` im selben Schritt mit. Datenlage: `datenlage.json` Version 2 (Kopf
  von `pipeline/src/zaehlkarte/datenlage.py`) – mitziehen: `js/map/ebenen.js`, `main.js`,
  `tests/web/vertrag.spec.js` und die Fixture `tests/web/fixtures/datenlage.json` (die
  Browser-Tests lesen nur sie). Dauerzählstellen: Felder in
  `dauer/index.json` (`stellen.felder`, `gruppen` = Bits von `g`, `dateien`, `kalender`,
  `standardtag`, `juengster`, `quellen[].gruppen`/`zeitraeume`/`standardtag`/`lizenzen`), Aufbau von
  `dauer/tage/JJJJ.json` und `dauer/NN.json` (Kopf von `pipeline/src/zaehlkarte/dauer/site.py`)
  – mitziehen: `js/data/dauer.js`, `js/ui/dauerdetail.js`, `tests/web/vertrag.spec.js` und die
  Fixtures `tests/web/fixtures/dauer/`, und die Vertragsversion erhöhen (`VERSION` in
  `dauer/site.py` = `DAUER_VERSION` in `js/data/dauer.js`): Bis „Dauerzählstellen bauen“ nach dem
  Merge neu gebaut hat, überspringt der Vertragstest das alte Asset im PR; auf `main` hält er die
  Auslieferung so lange an.
- **Nur Zählwerte, keine Einstufungen.** Je Verkehrsart Menge (und bei Schwerverkehr/Rad der
  Anteil). Kinder/Jugendliche nur als Zählkategorie (Tagesgang Fuß), keine Schwellen.
  Dauerzählstellen: eine Tagessumme nur aus allen Stunden des Tages (Zeitumstellung beachten),
  sonst „nicht vollständig gezählt“ – nie auffüllen, keine Mittel über Tage, kein DTV. Was die
  Quelle als rekonstruiert, unplausibel oder geändert kennzeichnet (Berlins Rad-Datei: Zellfarbe;
  Eco-Counter: Status 4, „modified“), gilt als nicht gezählt; kennzeichnet sie es nicht (MobiData
  BW), steht das als Hinweis an der Quelle. Zählt eine Stelle Rad und Fuß oder Pkw gemeinsam,
  kommt sie nicht als Rad in die Karte (`ohne` in der Quelldatei). Klassen
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
  (sha256 in der Quelldatei). Offenbare Tippfehler einer Quelle (etwa eine Koordinate) korrigiert
  die Quelldatei mit Vermerk (`lage`, Hinweis an der Quelle), nie die Rohdatei.
- **Abrufe der Pipeline nur über `zaehlkarte.abruf`** (robots.txt nach RFC 9309 für die Kennung
  `zaehlkarte-pipeline`, Crawl-delay, Weiterleitungen), nie `requests` direkt; CKAN-Portale ohne
  ihre API über `zaehlkarte.ckan`. Was robots.txt sperrt, holt die Pipeline nur mit einer
  Ausnahme in `pipeline/config/robots.yaml` (URL-Anfänge, Quellen, Grund, seit, Anfrage beim
  Betreiber) – eine neue Ausnahme beschließt die Projektleitung (AGENTS.md, „robots.txt und die
  Pipeline“).
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
- **Lizenzen mit Einschränkung** (Ettlingen: CC BY-NC 4.0, nur nicht kommerziell; Bochum:
  dl-de/by-2-0, aber nicht für Produkte im Wettbewerb zu Eco-Counter) nur mit Hinweis an der
  Quelle (`hinweise` in der Quelldatei); die Lizenz – samt Einschränkung – steht in der
  Seitenleiste und in jeder Zeile des CSV-Exports.
- **Quellen ohne Lizenz** (Beschluss der Projektleitung, 14.11.2026; Abwägung in AGENTS.md,
  „Rechtliches“): Zählwerte, die eine Kommune ohne Lizenz veröffentlicht oder auf Anfrage
  herausgegeben hat, kommen nur so in die Karte: Block `ohne_lizenz` statt `lizenz` in der
  Quelldatei (wie herausgegeben, Tag der Prüfung), Link zum Original (`portal` bzw.
  `herkunft_url`), in der Karte „ohne Lizenz“ mit Hinweis und Link „Entfernen lassen“, nie im
  CSV-Export; die Kommune steht in der Datenlage auf `ohne_lizenz`. Nur die Zahlen übernehmen,
  keine Berichte, Grafiken oder Karten spiegeln. Nie, wenn die Kommune Bedingungen gestellt hat
  (Nutzungserklärung wie Amberg, Entgelt für die Weitergabe wie Magdeburg) oder die
  Veröffentlichung untersagt; auf Bitte der Rechteinhaber sofort entfernen. Jede andere Quelle
  braucht eine Lizenzangabe.
- **Lizenz:** AGPL-3.0-or-later. Aus dem Schulwege-Projekt (MIT) übernommene Dateien tragen
  einen Herkunftsvermerk.

## Konventionen
- **uv**, nie `pip install`. Lint `uvx ruff check`, Tests `uv run pytest` (aus `pipeline/`).
  Die harten Regeln zur Konfiguration prüft `tests/test_konfiguration.py` an der echten
  Konfiguration (Ordner, Lizenzen, Land mit Ferien und Feiertagen, robots-Ausnahmen,
  Datenlage-Felder, jede Kommune in der Datei ihres Landes),
  `tests/test_abruf.py`, dass kein Modul das Netz an `abruf` vorbei ruft – eine neue Regel
  bekommt dort ihre Prüfung.
- **Sprache:** Deutsch in Doku, Kommentaren und Bezeichnern. Die UI ist zweisprachig
  (Deutsch Standard, Englisch per Umschalter): jeder neue UI-Text als Schlüssel in
  `js/sprache/texte.js`, in beiden Sprachen (Unit-Test prüft gleiche Schlüssel und
  Platzhalter); statisches HTML über `data-i18n`/`data-i18n-attr`. Inhalte aus den Daten
  (Hinweise, Quellenbeschreibungen, Datenlage- und Anfragetexte) bleiben deutsch und tragen
  `lang="de"`; die Namen der Stände (DE/EN, je Familie) kommen mit `datenlage.json` aus
  `datenlage.py`. CSV-Exporte bleiben in beiden Sprachen gleich (deutsche Spalten und Werte).
- **Neue Quelle:** eine Datei `pipeline/config/quellen/<familie>/<code>.yaml` mit der nächsten
  `nr` (`status: research` bis der Adapter steht),
  Adapter mit `lese(quelle, pfade, bericht)` und `Bericht`, Test mit synthetischer Datei.
  Mehrere Kommunen mit gleichem Format teilen sich einen Adapter (`adapter:`). Kurzzeit: der
  Abruf des Formats steht in `fetch.ABRUF`. Ferien und Feiertage gibt es für alle 16 Länder;
  das Land der Quelle wählt den Kalender (`config/kalender/ferien/<LAND>.csv`). Meldet
  `zaehlkarte kalender`, dass Ferien bald enden: nächsten KMK-Kalender mit
  `werkzeuge/kmk_ferien.py` aus dem PDF nachtragen.
- **Frontend:** `npm run dev`; vor jedem Push `npm run test:unit` und `npm run test:web`
  (Playwright sperrt das Netz außer dem Testserver – die Karte muss ohne Hintergrund laufen).
  Neues Verhalten = neuer Test in `tests/web/`.
- **Abrufe der Werkzeuge** (Branches `werkzeug/*`): nur, was robots.txt erlaubt – für die eigene
  Kennung, für `*` und für die Kennungen von Claude; prüfen mit `tools/robots.py` (RFC 9309 samt
  `*` und `$`, Crawl-delay), nicht mit `urllib.robotparser`. FragDenStaat und GovData sperren
  Werkzeuge ganz (AGENTS.md, „Wo suchen“).
- **Daten neu bauen:** Workflow „Kartendaten neu bauen“ (`.github/workflows/daten.yml`) oder
  lokal `fetch` + `site`. Das Ergebnis kommt als PR. MobiData BW und die Portale von Münster,
  Konstanz, Potsdam und Olpe sind aus manchen Entwicklungsumgebungen nicht erreichbar – dann den
  Workflow nutzen. Dauerzählstellen: Workflow „Dauerzählstellen bauen“
  (`.github/workflows/dauer.yml`, wöchentlich) – Ergebnis als Release-Asset, kein PR; danach
  startet er die CI auf `main` neu. Das Berliner Archiv, `iot.hamburg.de`,
  `opendata.readi.de` (Ettlingen) und die Rad-Quellen (MobiData BW, berlin.de, Open.NRW, die
  Portale von Münster, Aachen, München, Würzburg, Neuss, Dortmund, Leipzig, Rostock, Bonn und
  Düsseldorf und Bochums GitLab) sind aus der Sandbox ebenfalls nicht erreichbar (Werkzeug-Branch
  `werkzeug/dauer`, `tools/lauf.sh`); GitHub geht (Münsters Repository).
- Push auf `main` = Produktiv-Deploy nach GitHub Pages (nach grünen Frontend-Tests). Größere
  Umbauten auf einem Branch mit PR.
