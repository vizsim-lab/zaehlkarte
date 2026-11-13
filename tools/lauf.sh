#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# 13.11.2026, Teil 15: die neuen Rad-Quellen der zweiten Runde mit dem Code von dauer-rad2 bauen
# (tools/rad_bau.py, ergebnis/rad15/: Bericht und dauer_rad2.tar.gz)

ziel="$GITHUB_WORKSPACE/ergebnis/rad15"
neu="wuerzburg_rad,rhein_kreis_neuss_rad,dortmund_rad,essen_rad,leipzig_rad,rostock_rad,bochum_rad"
mkdir -p "$ziel"
rm -rf app && git clone -q --depth 1 -b dauer-rad2 https://github.com/vizsim-lab/zaehlkarte app
git -C app rev-parse HEAD > "$ziel/stand.txt"
quellen=""
for q in ${neu//,/ }; do quellen="$quellen --quelle $q"; done
( cd app/pipeline && uv sync --locked \
  && /usr/bin/time -v uv run zaehlkarte dauer fetch $quellen \
  && /usr/bin/time -v uv run python "$GITHUB_WORKSPACE/tools/rad_bau.py" "$GITHUB_WORKSPACE/app_aus" "$neu" ) 2>&1 | tail -250 > "$ziel/bericht.txt" || true
if [ -d app_aus/public/data/dauer ]; then
  tar -czf "$ziel/dauer_rad2.tar.gz" -C app_aus/public/data dauer
  du -sh app_aus/public/data/dauer >> "$ziel/bericht.txt"
fi
ls -la app/pipeline/data/raw/*/ 2>/dev/null | head -80 >> "$ziel/bericht.txt" || true
