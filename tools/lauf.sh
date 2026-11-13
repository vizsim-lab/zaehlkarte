#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Dauerzählstellen mit dem Code eines App-Branches bauen: baue <branch>
baue() {
  local ziel="$GITHUB_WORKSPACE/ergebnis/dauer/bau"
  mkdir -p "$ziel"
  rm -rf app && git clone -q --depth 1 -b "$1" https://github.com/vizsim-lab/zaehlkarte app
  ( cd app/pipeline && uv sync --locked && uv run zaehlkarte dauer fetch && uv run zaehlkarte dauer site ) 2>&1 | tail -300 > "$ziel/bericht.txt" || true
  git -C app rev-parse HEAD > "$ziel/stand.txt"
  if [ -d app/public/data/dauer ]; then
    tar -czf "$ziel/dauer.tar.gz" -C app/public/data dauer
    du -sh app/public/data/dauer >> "$ziel/bericht.txt"
  fi
}

# Dauerzählstellen mit dem Branch dauer-rad bauen (Rad-Zählstellen: MobiData BW, Münster, Aachen,
# Berlin, München; 13.11.2026)
baue dauer-rad
