# pipeline/config – die Konfiguration der Zählkarte

Die einzige Quellenliste der Zählkarte (wie in vizsim/svz): Quellen, Lizenzen, die Datenlage je
Kommune, Rechtslage, Ausnahmen von robots.txt und die Ferien je Land. Das Frontend bekommt alles
über `public/data/manifest.json`, `datenlage.json` und `dauer/index.json` – nie im Frontend
nachtragen. Die YAML-Dateien liest nur `src/zaehlkarte/config.py` (`konfiguration()`,
`quellen()`, `dauerquellen()`), die Ferien `src/zaehlkarte/kalender.py`;
`tests/test_konfiguration.py` prüft den Ordner gegen die Regeln aus CLAUDE.md, auch dass keine
Datei am falschen Ort liegt.

| Pfad | Inhalt |
|---|---|
| `quellen/kurzzeit/<code>.yaml` | eine Quelle der Kurzzeitzählungen (Adapter in `src/zaehlkarte/adapters/`) |
| `quellen/dauer/<code>.yaml` | eine Quelle der Dauerzählstellen (Adapter in `src/zaehlkarte/dauer/`) |
| `kommunen/<LAND>.yaml` | Datenlage: je Kommune ein Eintrag, je Land eine Datei |
| `recht.yaml` | Rechtslage je Land (kurz, mit Belegen im Kopf) |
| `anfrage_vorlage.yaml` | Vorlage für Anfragen auf FragDenStaat, für alle Kommunen gleich |
| `robots.yaml` | Ausnahmen von robots.txt (Format im Kopf der Datei) |
| `kalender/ferien/<LAND>.csv` | Schulferien je Land aus den KMK-Ferienkalendern |
| `berlin_rohdateien_2019-2025.txt` | welche Berliner Rohdateien einzeln online liegen (`rohdatei_liste` der Quelle `berlin`) |

## Quellen

- **Der Dateiname ist der Code** (`a–z`, `0–9`, einfacher `_`), in beiden Familien eindeutig und
  unveränderlich: Er steckt in Stellen-IDs, geteilten Links und den Asset-Namen des Gedächtnisses.
- **`nr`** legt die Reihenfolge der Quellen in den Kartendaten fest (`index.json`,
  `dauer/index.json`) – je Familie eindeutig. Eine neue Quelle bekommt die nächste freie Nummer
  (höchste + 1); nie umnummerieren, sonst ändern sich die Kartendaten von Grund auf. Der Lader
  sortiert danach und gibt `nr` nicht weiter.
- **`status`:** `live` = in der Karte, `research` = bekannt, der Adapter fehlt noch, `blocked` =
  nicht nutzbar (Grund in `notiz`).
- **`land`** wählt Rechtslage, Ferien und Feiertage. Welche weiteren Schlüssel eine Quelle hat,
  bestimmt ihr Adapter (Kopfkommentar des Adapters); Lizenz und Lizenz-URL stehen an der Quelle oder
  je Lieferung, eine Einschränkung mit Hinweis (`hinweise`).
- **Dauerzählstellen:** fest eingebaute Zähler mit Stunden- oder Tageswerten über Jahre. Abgrenzung
  zu vizsim/svz: hier die gezählten Werte im Zeitverlauf (Stunden, Tage) – keine Jahresmittel, kein
  DTV. Eine Tagessumme nur aus allen Stunden des Tages. Bau `zaehlkarte dauer`, Kartendaten unter
  `public/data/dauer/` – nicht im Git, Workflow „Dauerzählstellen bauen“.
- **Rad-Zählstellen** (Zählschleifen und -säulen, meist Eco-Counter): nur gezählte Werte – was die
  Quelle als rekonstruiert, unplausibel oder geändert markiert (Berlin: Zellfarbe, Münster:
  Status), kommt nicht in die Karte. Stellen, die nicht in die Karte kommen, stehen mit Grund unter
  `ohne`.

## Kommunen (Datenlage)

Was es außerhalb der Karte gibt – je Kommune ein Punkt mit Stand und Belegen. Die Länder stehen in
`datenlage.json` nach Kürzel, darin die Kommunen in der Reihenfolge der Datei. Neue Hinweise kommen
über das Issue-Formular „Zählung melden“.

- `kommune`, dazu `quelle` (dann liegt sie in der Karte; Land und Punkt kommen aus der Quelle und
  ihren Zählstellen) oder `land`, `lon`, `lat`.
- `stand` der Kurzzeitzählungen: `in_karte` | `offen` | `geliefert` | `kandidat` | `aggregiert` |
  `nur_karte` | `automatisch` | `abgelehnt`. Kommunen, von denen nur Dauerzählstellen bekannt
  sind, haben keinen `stand` – die Karte zeigt sie nur bei den Dauerzählstellen.
- `was`, `situation`, `empfehlung`, `weg`, `links` (`[Titel, URL]`); rechtliche Aussagen nur mit
  Beleg.
- `kontakt` (nur Funktionsadressen aus der Behördendatenbank von FragDenStaat), `anfrage: true`,
  `anfrage_zusatz`, `anfrage_an` (die angefragte Stelle, wo es keine Stadt ist, etwa
  „Gemeinde Mühltal“).
- `dauer:` – Datenlage der Dauerzählstellen: `stand` (`in_karte` | `offen` | `kandidat`), `was`,
  `situation`, `links`.

## Ferien

`kalender/ferien/<LAND>.csv` mit den Spalten `von`, `bis`, `ferien`, `schuljahr`, `gebiet`,
`quelle`, erzeugt mit `werkzeuge/kmk_ferien.py` aus den KMK-Ferienkalendern (PDF). Ein Schuljahr
gilt als abgedeckt, wenn es in der Spalte `schuljahr` vorkommt. `zaehlkarte kalender` meldet (auch
im Wochenlauf), wenn die Ferien eines Landes bald enden.
