#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Prüfung 14.11.2026: eine Dauer-Quelle mit dem Adapter eines App-Branches holen und lesen –
# Kennzahlen je Zählstelle, Jahresgrenzen, Zeitumstellung, Kartendaten nur dieser Quelle
# (tools/quelle_pruefen.py, ergebnis/<code>/). Erst VMZ Niedersachsen (vmz-rad), jetzt Dresden.
pruefe() {  # pruefe <branch> <code>
  local ziel="$GITHUB_WORKSPACE/ergebnis/$2"
  mkdir -p "$ziel"
  rm -rf app && git clone -q --depth 1 -b "$1" https://github.com/vizsim-lab/zaehlkarte app
  git -C app rev-parse HEAD > "$ziel/stand.txt"
  ( cd app/pipeline && uv sync --locked -q && timeout 40m uv run python "$GITHUB_WORKSPACE/tools/quelle_pruefen.py" "$2" "$ziel" ) 2>&1 | tail -80 > "$ziel/lauf.txt" || true
}
pruefe dresden-rad dresden_rad  # zweiter Lauf: ab 2009
