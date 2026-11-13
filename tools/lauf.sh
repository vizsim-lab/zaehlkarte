#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 3: Lizenzen und Formate der letzten Kandidaten
# (tools/rad_erkunden3.py, Ergebnisse in ergebnis/rad3/)
mkdir -p ergebnis
uv run --no-project --with openpyxl python tools/rad_erkunden3.py 2>&1 | tail -50 > ergebnis/rad3_lauf.txt || true
