#!/usr/bin/env bash
# Was ein Lauf des Werkzeug-Workflows tut – vor jedem Push anpassen. Läuft im Wurzelordner
# dieses Branches; Ergebnisse nach ergebnis/ (werden danach committet).
set -u

# Prüfung 14.11.2026: VMZ Niedersachsen (vmz_rad) mit dem Adapter des Branches vmz-rad holen und
# lesen – Kennzahlen je Zählstelle, Jahresgrenzen, Zeitumstellung, Kartendaten nur dieser Quelle
# (tools/vmz_pruefen.py, ergebnis/vmz/). vmz-niedersachsen.de ist aus der Sandbox nicht erreichbar.
mkdir -p ergebnis/vmz
rm -rf app && git clone -q --depth 1 -b vmz-rad https://github.com/vizsim-lab/zaehlkarte app
git -C app rev-parse HEAD > ergebnis/vmz/stand.txt
( cd app/pipeline && uv sync --locked -q && timeout 40m uv run python "$GITHUB_WORKSPACE/tools/vmz_pruefen.py" "$GITHUB_WORKSPACE/ergebnis/vmz" ) 2>&1 | tail -80 > ergebnis/vmz/lauf.txt || true
