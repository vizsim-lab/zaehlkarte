#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 11: nur die Rad-Quellen mit dem Code von dauer-rad bauen
# (tools/rad_bau.py, ergebnis/rad11/: Bericht und dauer_rad.tar.gz)

ziel="$GITHUB_WORKSPACE/ergebnis/rad11"
mkdir -p "$ziel"
rm -rf app && git clone -q --depth 1 -b dauer-rad https://github.com/vizsim-lab/zaehlkarte app
git -C app rev-parse HEAD > "$ziel/stand.txt"
( cd app/pipeline && uv sync --locked \
  && uv run zaehlkarte dauer fetch --quelle mobidata_rad --quelle muenster_rad --quelle aachen_rad --quelle berlin_rad --quelle muenchen_rad \
  && uv run python "$GITHUB_WORKSPACE/tools/rad_bau.py" "$GITHUB_WORKSPACE/app_aus" ) 2>&1 | tail -150 > "$ziel/bericht.txt" || true
if [ -d app_aus/public/data/dauer ]; then
  tar -czf "$ziel/dauer_rad.tar.gz" -C app_aus/public/data dauer
  du -sh app_aus/public/data/dauer >> "$ziel/bericht.txt"
fi
