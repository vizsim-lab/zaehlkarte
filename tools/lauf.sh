#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 5: Rekonstruktion im MobiData-Bündel, Münsters Standorte, Kiels
# neues Angebot, KMK-Ferienkalender BW/BY (tools/rad_erkunden5.py, Ergebnisse in ergebnis/rad5/)
mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden5.py 2>&1 | tail -50 > ergebnis/rad5_lauf.txt || true
