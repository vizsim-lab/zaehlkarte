#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 4: Stichproben für die Rad-Adapter und der Kieler Zugang
# (tools/rad_erkunden4.py, Ergebnisse in ergebnis/rad4/, Stichproben in ergebnis/rad4/daten/)
mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden4.py 2>&1 | tail -50 > ergebnis/rad4_lauf.txt || true
