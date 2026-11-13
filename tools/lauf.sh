#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 2: Formate, Lizenzen und Vollständigkeit der Kandidaten
# (tools/rad_erkunden2.py, Ergebnisse in ergebnis/rad2/; Teil 1 in ergebnis/rad/)
mkdir -p ergebnis
uv run --no-project --with openpyxl python tools/rad_erkunden2.py 2>&1 | tail -50 > ergebnis/rad2_lauf.txt || true
