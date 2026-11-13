#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 7: München, Jahresdateien (tools/rad_erkunden7.py, ergebnis/rad7/)

mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden7.py 2>&1 | tail -50 > ergebnis/rad7_lauf.txt || true
