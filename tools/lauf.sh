#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026, Teil 6: MobiData BW – Eco-Counter-Werte mit Status?
# (tools/rad_erkunden6.py, Ergebnisse in ergebnis/rad6/)
mkdir -p ergebnis
uv run --no-project python tools/rad_erkunden6.py 2>&1 | tail -50 > ergebnis/rad6_lauf.txt || true
