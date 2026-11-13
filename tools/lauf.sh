#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 10: MobiData – Zeitstempel ohne Versatz (tools/rad_erkunden10.py,
# ergebnis/rad10/)

mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden10.py 2>&1 | tail -80 > ergebnis/rad10_lauf.txt || true
