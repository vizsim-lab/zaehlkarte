# Zählkarte – kommunale Verkehrszählungen

**Karte:** https://vizsim-lab.github.io/zaehlkarte/

Städte zählen ständig Verkehr: an Kreuzungen (Knotenstromzählung) und an Straßenabschnitten
(Querschnitt), von Hand oder per Video, für Planungen, Ampeln und Lärmkarten. Die Ergebnisse
liegen meist in Schubladen. Die Zählkarte sammelt, was offen ist oder per
Informationsfreiheitsanfrage herausgegeben wurde, und zeigt die Zählwerte je Verkehrsart:

- **Kfz**, **Schwerverkehr** (Menge und Anteil an Kfz), **Rad** (Menge und Radanteil
  Rad / (Rad + Kfz)) und **Fuß** (bei nach Alter getrennten Zählungen auch
  Kinder/Jugendliche im Tagesgang).
- Kennzahl wählbar: Summe 7–19 Uhr, Summe 24 Stunden oder die stärkste Stunde.
- Je Zählstelle alle Zählungen, der **Tagesgang** jeder Zählung, der Verlauf über die Jahre,
  die Rohdatei und die Lizenz; Download als CSV.
- **Datenlage**: je Kommune, ob es solche Zählungen offen gibt, ob sie auf Anfrage
  herausgegeben wurden oder wo eine Anfrage aussichtsreich ist – mit Belegen.

Gemeint sind Kurzzeitzählungen der Kommunen, keine Dauerzählstellen und keine
Verkehrsmengenkarten (dafür: [vizsim/svz](https://github.com/vizsim/svz)). Auswertungen wie
der Schulweg-Verdacht aus den Berliner Fußgängerzählungen stehen in
[vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege).

## Daten

| Quelle | Was | Zeitraum | Weg | Lizenz |
|---|---|---|---|---|
| Berlin (SenMVKU) | rund 26.600 verortete Knoten- und Querschnittszählungen, 15/60-Minuten-Werte, Kfz nach Fahrzeugart, Rad, Fuß nach Alter | 1983–2025 | IFG-Anfragen [2019](https://fragdenstaat.de/anfrage/kfz-verkehrszahldaten-aus-berlin/) und [2025](https://fragdenstaat.de/anfrage/stundengenaue-ergebnisse-manueller-verkehrszaehlungen-in-berlin/) | CC BY-SA 3.0 DE (bis 2019), dl-de/by-2-0 (ab 2019) |
| Ravensburg, Weingarten, Berg, Baienfurt, Baindt | 24-Stunden-Videozählungen an Kreuzungen, 15-Minuten-Werte, Pkw, Lkw, Rad, Fuß | 2023–2026 | offen auf [MobiData BW](https://mobidata-bw.de/dataset/zaehldaten-ravensburg) | dl-de/by-2-0 |
| Moers (Stadt Moers) | rund 540 Tageszählungen an 140 Stellen mit Seitenradar-Messgeräten (meist zwei Tage am Stück), Kfz je Stunde, Schwerverkehr über die Länge | 2010–2022 | offen auf [offenesdatenportal.de](https://www.offenesdatenportal.de/dataset/verkehrszahlung-in-moers-2021) | dl-de/zero-2-0 |
| Münster (Stadt Münster) | rund 1.160 Kfz-Knotenpunktzählungen von Hand, je meist zwei Stunden (7–8 und 16–17 Uhr), nach Fahrzeugart | 2000–2020 | offen auf dem [Open-Data-Portal der Stadt](https://opendata.stadt-muenster.de/dataset/verkehrsz%C3%A4hlung-manuelle-verkehrserhebung) (XLS und PDF) | dl-de/by-2-0, „Datenquelle: Stadt Münster“ |

Die Zahlen je Quelle (Stellen, Zählungen, Jahre) stehen in der Karte unter „Quellen &
Lizenzen“ und in `public/data/manifest.json`. Rund 1.500 Berliner Zählungen haben noch keine
Lage (Straßennamen ohne eindeutige Kreuzung in OpenStreetMap); sie fehlen in der Karte.

**Lage in Berlin:** Koordinaten aus der Zähldatei (ab 2021), sonst die Geokodierung der Fuß-
und Radzählungen aus [vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege)
(Straßenkreuzungen aus OpenStreetMap), für die übrigen Zählungen derselbe Geocoder im Workflow
„Berlin geokodieren“ (`pipeline/geokodierung/berlin_ergaenzung.csv`), sonst übernommen von
Zählungen derselben Zählstellen-Kennung, wenn die eindeutig an einem Ort liegen (in der Karte
abschaltbar).

**Datenlage:** Recherche Stand November 2026, unvollständig. Hinweise auf weitere Zählungen
gern über das Formular [„Zählungen melden“](https://github.com/vizsim-lab/zaehlkarte/issues/new?template=zaehlung-melden.yml).

## Kennzahlen – was die Karte zeigt

- Werte sind Summen über alle Richtungen. „7–19 Uhr“ nur, wo jede dieser Stunden gezählt ist;
  „24 h“ nur bei 24-Stunden-Zählungen; „stärkste Stunde“ vergleicht auch kurze Zählfenster.
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
- Münster: Je Zählung liegen nur die Spitzenstunden vor (meist 7–8 und 16–17 Uhr) – in der
  Karte erscheinen die Zählungen deshalb nur unter „stärkste Stunde“. Kfz = Summe der
  Fahrzeugarten; wo Formelfehler im Zählblatt Kfz-Zelle und Fahrzeugarten auseinanderlaufen
  lassen, der größere Wert (mit Hinweis). Schwerverkehr = Bus + Lkw + Lastzug. Die Spalte „Rad“ der Kfz-Zählung ist keine vollständige Radzählung
  (wo es eine eigene Radzählung gibt, liegt sie deutlich darunter oder steht auf 0); sie
  fehlt in der Karte und steht im Hinweis der Zählung.

## Aufbau

```
pipeline/            uv-Paket `zaehlkarte`: Rohdaten -> ein Zählungsschema -> Kartendaten
  config/sources.yaml   die einzige Quellenliste (Quellen, Lizenzen, Datenlage)
  src/zaehlkarte/adapters/  ein Adapter je Format (berlin_zda, mobidata_bw, muenster, moers_radar)
public/data/         die Kartendaten (erzeugt, im Git): manifest, index, details/NN, datenlage
index.html, main.js, js/, style.css   die Karte (Vite, MapLibre, Positron von OpenFreeMap)
tests/               unit/ (node --test), web/ (Playwright gegen den Build)
```

```bash
# Pipeline (aus pipeline/)
uv sync
uv run zaehlkarte fetch      # Rohdaten nach pipeline/data/raw/
uv run zaehlkarte site       # Kartendaten nach public/data/
uv run pytest && uvx ruff check

# Karte (aus der Wurzel)
npm ci
npm run dev                  # http://localhost:5173
npm run test:unit && npm run test:web
```

Eine neue Quelle: Eintrag in `pipeline/config/sources.yaml`, Adapter in
`src/zaehlkarte/adapters/` (liefert `Zaehlung`-Objekte, siehe `modell.py`), Test mit einer
kleinen synthetischen Datei in `pipeline/tests/`. Wie man Quellen findet und was nicht
funktioniert hat: [AGENTS.md](AGENTS.md).

Die Daten erneuert der Workflow „Kartendaten neu bauen“ (monatlich und von Hand) als Pull
Request. Jeder Push auf `main` wird nach grünen Tests nach GitHub Pages ausgeliefert.

## Lizenz

- **Code:** AGPL-3.0-or-later. ZDA-Leser und Namensbereinigung stammen aus
  [vizsim/berlin-traffic-counts_schulwege](https://github.com/vizsim/berlin-traffic-counts_schulwege) (MIT).
- **Daten:** die Lizenz der jeweiligen Quelle (Tabelle oben, in der Karte je Zählung);
  Namensnennung erforderlich. Hintergrundkarte © OpenStreetMap-Mitwirkende, OpenFreeMap.
