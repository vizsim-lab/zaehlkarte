#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 8: MobiData-Kanäle (tools/rad_erkunden8.py, ergebnis/rad8/)

mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden8.py 2>&1 | tail -50 > ergebnis/rad8_lauf.txt || true
