#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 14: offene Punkte der Rad-Quellen
# (tools/rad_erkunden14.py, ergebnis/rad14/)

mkdir -p ergebnis
uv run --no-project --with pandas --with openpyxl python tools/rad_erkunden14.py 2>&1 | tail -80 > ergebnis/rad14_lauf.txt || true
