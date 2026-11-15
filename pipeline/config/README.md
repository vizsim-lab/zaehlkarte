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
| `gemeinden.yaml` | Gemeindegrenzen (VG250 des BKG, URL und sha256): die Gemeinde je Dauerzählstelle (`ags`, `src/zaehlkarte/gemeinden.py`) |
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
- **`ebene`** (nur Dauerzählstellen): `land` oder `bund`, wenn keine Kommune die Zählstellen
  betreibt (etwa die Dauerzählstellen des Landes Baden-Württemberg). Solche Quellen gehören zu
  keiner Kommune der Datenlage; ohne `ebene` gehört jede Dauer-Quelle zu mindestens einer.
- **`land`** wählt Rechtslage, Ferien und Feiertage. Welche weiteren Schlüssel eine Quelle hat,
  bestimmt ihr Adapter (Kopfkommentar des Adapters); Lizenz und Lizenz-URL stehen an der Quelle oder
  je Lieferung, eine Einschränkung mit Hinweis (`hinweise`) – oder, wo es keine Lizenz gibt, der
  Block `ohne_lizenz` (unten).
- **Ohne Lizenz** (CLAUDE.md, „Quellen ohne Lizenz“): Hat die Kommune die Werte ohne Lizenz
  veröffentlicht oder auf Anfrage herausgegeben und keine Bedingungen gestellt, steht statt
  `lizenz`/`lizenz_url` (an der Quelle oder je Lieferung):

  ```yaml
  ohne_lizenz:
    herausgegeben: >-          # wie die Werte öffentlich wurden – erscheint in der Karte
      als Anlage zur Vorlage 242/2022 im Ratsinformationssystem, ohne Lizenzangabe
    geprueft: 2026-11-14       # an dem Tag weder Lizenz noch Bedingungen gefunden
  ```

  Dazu der Link zum Original (`portal`, je Lieferung `herkunft_url`). Die Karte zeigt die Werte mit
  „ohne Lizenz“ und dem Link „Entfernen lassen“, der CSV-Export lässt sie weg; die Kommune steht in
  der Datenlage auf `ohne_lizenz`.
- **Dauerzählstellen:** fest eingebaute Zähler mit Stunden- oder Tageswerten über Jahre. Abgrenzung
  zu vizsim/svz: hier die gezählten Werte im Zeitverlauf (Stunden, Tage) – keine Jahresmittel, kein
  DTV. Eine Tagessumme nur aus allen Stunden des Tages. Bau `zaehlkarte dauer`, Kartendaten unter
  `public/data/dauer/` – nicht im Git, Workflow „Dauerzählstellen bauen“.
- **Rad-Zählstellen** (Zählschleifen und -säulen, meist Eco-Counter): nur gezählte Werte – was die
  Quelle als rekonstruiert, unplausibel oder geändert markiert (Berlin: Zellfarbe, Münster:
  Status), kommt nicht in die Karte. Stellen, die nicht in die Karte kommen, stehen mit Grund unter
  `ohne`.

## Kommunen (Datenlage)

Was es gibt, auch außerhalb der Karte – je Kommune ein Punkt, je Familie ein Stand mit Text und
Belegen. Gelesen von `src/zaehlkarte/datenlage.py` (datenlage.json, docs/DATENLAGE.md). Die Länder
stehen in `datenlage.json` nach Kürzel, darin die Kommunen in der Reihenfolge der Datei. Neue
Hinweise kommen über das Issue-Formular „Zählung melden“.

```yaml
- ags: "05913000"              # amtlicher Gemeindeschlüssel, bei Kreisen der Kreisschlüssel (5 Ziffern)
  name: Dortmund
  lage: [7.4653, 51.5136]      # [Länge, Breite] – der Punkt in der Karte
  kontakt: {fds_suche: "Stadt Dortmund"}
  kurzzeit:                    # Kurzzeitzählungen (Knotenpunkte, Querschnitte)
    stand: aggregiert
    was: >-
      …
    situation: >-
      …
    empfehlung: >-
      …
    weg: "FragDenStaat, IFG NRW"
    anfrage: {zusatz: …}       # Anfragetext aus der Vorlage; `an`, wo es keine Stadt ist
    links:
      - [Titel, URL]
  dauer:                       # Dauerzählstellen
    stand: in_karte
    quellen: [dortmund_rad]
    was: >-
      …
    links:
      - [Titel, URL]
```

- **`ags`:** der Schlüssel der Kommune – eindeutig, aus dem Gemeindeverzeichnis des Statistischen
  Bundesamts (GV-ISys); die ersten beiden Ziffern sind das Land, die Datei muss dazu passen. Namen
  sind bundesweit nicht eindeutig. Regionale Feiertage ließen sich später über ihn zuordnen.
- **Blöcke je Familie:** `kurzzeit` und `dauer` sind beide optional, mindestens einer ist da. Die
  Karte zeigt je Familie nur Kommunen mit deren Block – Kommunen, von denen nur Dauerzählstellen
  bekannt sind, haben keinen Block `kurzzeit`.
- **`stand`:** eine Liste für beide Familien (`datenlage.STAND`): `in_karte` | `offen` |
  `geliefert` | `kandidat` | `ohne_lizenz` (Werte da, aber ohne Lizenz) | `aggregiert` (nur
  Summen oder Mittelwerte) | `nur_karte` | `abgelehnt` | `nichts_offen`. Die Karte fasst sie in
  vier Farben zusammen.
- **`quellen`:** die Quellen der Familie, die die Kommune in die Karte bringen – bei
  `stand: in_karte` immer (nur Quellen mit Lizenz), bei `ohne_lizenz`, sobald die Werte in der
  Karte sind (nur Quellen ohne Lizenz), sonst nie. Jede Kurzzeit-Quelle gehört zu genau einer
  Kommune, eine Dauer-Quelle zu mindestens einer (Bündel wie MobiData BW zu mehreren) – außer
  Quellen des Landes oder Bundes (`ebene`), die zu keiner gehören. Die Karte findet so die
  Quellen einer Kommune („hinzoomen“) ohne Abgleich über den Namen.
- **Texte:** `was` (kurz), `situation` (die Lage ausführlich), `links` (`[Titel, URL]`);
  rechtliche Aussagen nur mit Beleg. Bei den Kurzzeitzählungen außerhalb der Karte dazu
  `empfehlung` und `weg`.
- **`kontakt`:** nur Funktionsadressen aus der Behördendatenbank von FragDenStaat (`name`,
  `email`, `fds`) oder `fds_suche` (Link zur Suche dort).
- **`anfrage`:** nur bei den Kurzzeitzählungen; der Text kommt aus `anfrage_vorlage.yaml`, mit
  `zusatz` (eigener Absatz) und `an` (die angefragte Stelle, wo es keine Stadt ist, etwa
  „Gemeinde Mühltal“). Eine Anfrage braucht einen Kontakt.

## Ferien

`kalender/ferien/<LAND>.csv` mit den Spalten `von`, `bis`, `ferien`, `schuljahr`, `gebiet`,
`quelle`, erzeugt mit `werkzeuge/kmk_ferien.py` aus den KMK-Ferienkalendern (PDF). Ein Schuljahr
gilt als abgedeckt, wenn es in der Spalte `schuljahr` vorkommt. `zaehlkarte kalender` meldet (auch
im Wochenlauf), wenn die Ferien eines Landes bald enden.
