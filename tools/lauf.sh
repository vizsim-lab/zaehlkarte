#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 15: Bonn und Düsseldorf im Detail (tools/rad_erkunden15.py,
# ergebnis/rad15/)

mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden15.py 2>&1 | tail -80 > ergebnis/rad15_lauf.txt || true
