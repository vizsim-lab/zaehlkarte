#!/usr/bin/env bash
# Eine Dauer-Quelle mit dem Adapter eines App-Branches holen, lesen und die Kartendaten nur dieser
# Quelle bauen (tools/quelle_pruefen.py, aus werkzeug/dauer übernommen) – mit Zeit und Speicher.
# Aufruf (im Wurzelordner dieses Branches): tools/pruefe.sh <branch> <code>
set -u
ziel="$GITHUB_WORKSPACE/ergebnis/bw/pruefe_$2"
mkdir -p "$ziel"
rm -rf app && git clone -q --depth 1 -b "$1" "https://github.com/vizsim-lab/zaehlkarte" app
git -C app rev-parse HEAD > "$ziel/stand.txt"
zeit=""
[ -x /usr/bin/time ] && zeit="/usr/bin/time -v"
( cd app/pipeline && uv sync --locked -q && $zeit timeout 70m uv run python "$GITHUB_WORKSPACE/tools/quelle_pruefen.py" "$2" "$ziel" ) > "$ziel/lauf_ganz.txt" 2>&1 || true
tail -c 30000 "$ziel/lauf_ganz.txt" > "$ziel/lauf.txt" && rm -f "$ziel/lauf_ganz.txt"
# kleine Zustandsdateien des Adapters (etwa der Abrufplan von BAYSIS) mit ablegen
for f in stand.json abruf.json; do
  [ -f "app/pipeline/data/raw/$2/$f" ] && cp "app/pipeline/data/raw/$2/$f" "$ziel/"
done
true
