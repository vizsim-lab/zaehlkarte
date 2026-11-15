#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Prüfung 14.11.2026: eine Dauer-Quelle mit dem Adapter eines App-Branches holen und lesen –
# Kennzahlen je Zählstelle, Jahresgrenzen, Zeitumstellung, Kartendaten nur dieser Quelle
# (tools/quelle_pruefen.py, ergebnis/<code>/). Erst VMZ Niedersachsen (vmz-rad), dann Dresden,
# dann Fuß (Augsburg, Bochum), dann Neuss RS5 und Würzburg Passanten (Branch neuss-wuerzburg), dann Augsburgs
# Radzählstationen mit Tageswerten der Quelle (Branch tageswerte), jetzt Hamburgs Tageswerte.
pruefe() {  # pruefe <branch> <code>
  local ziel="$GITHUB_WORKSPACE/ergebnis/$2"
  mkdir -p "$ziel"
  rm -rf app && git clone -q --depth 1 -b "$1" https://github.com/vizsim-lab/zaehlkarte app
  git -C app rev-parse HEAD > "$ziel/stand.txt"
  ( cd app/pipeline && uv sync --locked -q && timeout 40m uv run python "$GITHUB_WORKSPACE/tools/quelle_pruefen.py" "$2" "$ziel" ) 2>&1 | tail -80 > "$ziel/lauf.txt" || true
}
# Neuss RS5: geprüft (ergebnis/neuss_rad)
# Würzburg Passanten: geprüft (ergebnis/wuerzburg_fuss)
# Augsburgs Radzählstationen: geprüft (ergebnis/augsburg_rad)
# Hamburg, Layer „1-Tag“ (15.11.2026): Umfang, Zeitstempel, Vergleich mit den Stunden,
# Datensatzbeschreibung, Dauer des ersten vollen Abrufs (tools/hamburg_tage.py, ohne App-Code)
mkdir -p ergebnis/hamburg_tage
timeout 60m python3 tools/hamburg_tage.py ergebnis/hamburg_tage 2>&1 | tail -40 > ergebnis/hamburg_tage/lauf.txt || true
