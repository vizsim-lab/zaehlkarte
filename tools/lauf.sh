#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 12: übrige Quellen des Artefakts „Offene Radzähldaten“
# (tools/rad_erkunden12.py, ergebnis/rad12/)

mkdir -p ergebnis
uv run --no-project --with openpyxl python tools/rad_erkunden12.py 2>&1 | tail -80 > ergebnis/rad12_lauf.txt || true
