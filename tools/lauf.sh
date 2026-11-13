#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 16: Bonn und Düsseldorf für die Adapter (tools/rad_erkunden16.py,
# ergebnis/rad16/ – schreibt laufend, ein Zeitlimit lässt das Bisherige stehen)

mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden16.py 2>&1 | tail -80 > ergebnis/rad16_lauf.txt || true
