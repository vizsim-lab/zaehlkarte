#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# 13.11.2026, Teil 17: Bonn und Düsseldorf (dritte Runde) mit dem Code von dauer-rad3 bauen
# (tools/rad_bau.py, ergebnis/rad17/: Bericht und dauer_rad3.tar.gz)

ziel="$GITHUB_WORKSPACE/ergebnis/rad17"
neu="bonn_rad,duesseldorf_rad"
mkdir -p "$ziel"
rm -rf app && git clone -q --depth 1 -b dauer-rad3 https://github.com/vizsim-lab/zaehlkarte app
git -C app rev-parse HEAD > "$ziel/stand.txt"
quellen=""
for q in ${neu//,/ }; do quellen="$quellen --quelle $q"; done
( cd app/pipeline && uv sync --locked \
  && /usr/bin/time -v uv run zaehlkarte dauer fetch $quellen \
  && /usr/bin/time -v uv run python "$GITHUB_WORKSPACE/tools/rad_bau.py" "$GITHUB_WORKSPACE/app_aus" "$neu" ) 2>&1 | tail -250 > "$ziel/bericht.txt" || true
if [ -d app_aus/public/data/dauer ]; then
  tar -czf "$ziel/dauer_rad3.tar.gz" -C app_aus/public/data dauer
  du -sh app_aus/public/data/dauer >> "$ziel/bericht.txt"
fi
cat app/pipeline/data/raw/duesseldorf_rad/abruf.json >> "$ziel/bericht.txt" 2>/dev/null || true
cat app/pipeline/data/raw/bonn_rad/abruf.json >> "$ziel/bericht.txt" 2>/dev/null || true
