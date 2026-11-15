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
# Hamburg, Layer „1-Tag“ (15.11.2026): erkundet (tools/hamburg_tage.py, ergebnis/hamburg_tage)
#
# Hamburg mit Tageswerten der Quelle (Branch hamburg-tageswerte): mit dem Gedächtnis der Stunden
# aus dem Release – wie der erste Lauf nach dem Merge (Stunden 14 Tage neu, Tageswerte ganz);
# Speicherbedarf mit /usr/bin/time; die Tagesdateien des Gedächtnisses nach ergebnis/<code>/.
pruefe_hh() {  # pruefe_hh <branch> <code>
  local ziel="$GITHUB_WORKSPACE/ergebnis/$2"
  mkdir -p "$ziel/gedaechtnis"
  rm -rf app && git clone -q --depth 1 -b "$1" https://github.com/vizsim-lab/zaehlkarte app
  git -C app rev-parse HEAD > "$ziel/stand.txt"
  local roh="app/pipeline/data/raw/$2/gedaechtnis"
  local tmp="$RUNNER_TEMP/gd_$2"
  mkdir -p "$roh" "$tmp"
  local rid
  rid=$(gh api repos/vizsim-lab/zaehlkarte/releases/tags/dauerzaehlstellen -q .id)
  for name in $(gh api --paginate "repos/vizsim-lab/zaehlkarte/releases/$rid/assets?per_page=100" -q '.[].name' | grep "^$2__"); do
    gh release download dauerzaehlstellen -R vizsim-lab/zaehlkarte -p "$name" -D "$tmp" --clobber
    mv "$tmp/$name" "$roh/${name#"$2"__}"
  done
  ls -la "$roh" > "$ziel/gedaechtnis_vorher.txt"
  local zeit=""
  [ -x /usr/bin/time ] && zeit="/usr/bin/time -v"
  ( cd app/pipeline && uv sync --locked -q && $zeit timeout 50m uv run python "$GITHUB_WORKSPACE/tools/quelle_pruefen.py" "$2" "$ziel" ) > "$ziel/lauf_ganz.txt" 2>&1 || true
  tail -c 20000 "$ziel/lauf_ganz.txt" > "$ziel/lauf.txt" && rm -f "$ziel/lauf_ganz.txt"
  cp "$roh"/tage_*.csv.gz "$ziel/gedaechtnis/" 2>/dev/null || true
  ls -la "$roh" > "$ziel/gedaechtnis_nachher.txt"
}
# Datensatzbeschreibungen: geholt (ergebnis/hamburg_tage/portal_*.txt); zweiter Lauf mit dem
# Stand von #28 geprüft (gemergt 15.11.).
#
# Leipzig, Tageswerte „pro Tag der letzten 2 Jahre“ (15.11.2026): Format, Zeitraum, Lieferungen,
# Jahnallee, Lizenz beider Datensätze; Rohdateien gepackt für den Vergleich mit dem Gedächtnis
mkdir -p ergebnis/leipzig_tage
timeout 30m python3 tools/leipzig_tage.py ergebnis/leipzig_tage > ergebnis/leipzig_tage/lauf.txt 2>&1 || true
