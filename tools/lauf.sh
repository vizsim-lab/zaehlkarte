#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Erkundung 13.11.2026: Rad-Zählstellen und weitere Dauerzählstellen (Kataloge, MobiData BW,
# Stichproben) – tools/rad_erkunden.py, Ergebnisse in ergebnis/rad/
uv run --no-project --with openpyxl --with pdfplumber python tools/rad_erkunden.py 2>&1 | tail -50 > ergebnis/rad_lauf.txt || true
