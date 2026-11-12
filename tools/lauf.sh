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

# Bau mit dem App-Branch, dazu das Gedächtnis als Saat für den Release sichern
baue dauer-staedte
mkdir -p ergebnis/dauer/gedaechtnis
for d in app/pipeline/data/raw/*/gedaechtnis; do
  [ -d "$d" ] || continue
  code=$(basename "$(dirname "$d")")
  for f in "$d"/*; do cp "$f" "ergebnis/dauer/gedaechtnis/${code}__$(basename "$f")"; done
done
ls -la ergebnis/dauer/gedaechtnis >> ergebnis/dauer/bau/bericht.txt
for u in https://suche.transparenz.hamburg.de/dataset/verkehrsdaten-kfz-infrarotdetektoren-hamburg \
         https://suche.transparenz.hamburg.de/dataset/verkehrsdaten-kfz-infrarotdetektoren-hamburg14 \
         https://suche.transparenz.hamburg.de/dataset/verkehrsdaten-rad-infrarotdetektoren-hamburg \
         https://suche.transparenz.hamburg.de/dataset/verkehrsdaten-rad-infrarotdetektoren-hamburg20; do
  curl -s -o /dev/null -L -w "%{http_code} %{url_effective} $u\n" "$u"
done > ergebnis/dauer/links.txt 2>&1
