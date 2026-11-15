"""Opendatasoft-Datensätze einer Dauer-Quelle erkunden (Felder, Zahl der Zeilen, Lizenz,
Beschreibung, Beispiele, dazu der ganze Export gepackt) – über die Abrufe der App
(`zaehlkarte.abruf`, mit der robots-Ausnahme der Quelle aus config/robots.yaml).

Läuft im Ordner `app/pipeline` des geklonten App-Branches (siehe tools/lauf.sh):
    uv run python <pfad>/tools/ods_erkunden.py <code> <zielordner> <datensatz> [<datensatz> …]
"""

from __future__ import annotations

import gzip
import json
import re
import sys
import traceback
from pathlib import Path

from zaehlkarte import abruf
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bau

CODE = sys.argv[1]
ziel = Path(sys.argv[2])
ziel.mkdir(parents=True, exist_ok=True)
pfade = Pfade()
q = bau.dauerquellen(pfade)[CODE]
abruf.ausnahmen_setzen([CODE], pfade=pfade)
basis = q["basis"].rstrip("/")
out: list[str] = []


def schreib() -> None:
    (ziel / "bericht.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


for ds in sys.argv[3:]:
    try:
        meta = abruf.hole(f"{basis}/api/explore/v2.1/catalog/datasets/{ds}", timeout=120).json()
        m = (meta.get("metas") or {}).get("default") or {}
        felder = [(f.get("name"), f.get("type"), f.get("label")) for f in meta.get("fields", [])]
        out.append(f"== {ds}: {m.get('title')}")
        out.append(f"  Zeilen: {m.get('records_count')}; geändert {m.get('modified')}; "
                   f"verarbeitet {m.get('data_processed')}; Lizenz {m.get('license')} "
                   f"{m.get('license_url')}; Herausgeber {m.get('publisher')}")
        out.append("  Beschreibung: " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ",
                                                                   m.get("description") or ""))[:2500])
        out.append(f"  Felder: {felder}")
        zeit = next((n for n, t, _ in felder if t in ("datetime", "date")), None)
        probe = abruf.hole(f"{basis}/api/explore/v2.1/catalog/datasets/{ds}/records",
                           params={"limit": 5, **({"order_by": zeit} if zeit else {})},
                           timeout=120).json()
        for r in probe.get("results", []):
            out.append("  erste: " + json.dumps(r, ensure_ascii=False)[:600])
        if zeit:
            probe = abruf.hole(f"{basis}/api/explore/v2.1/catalog/datasets/{ds}/records",
                               params={"limit": 3, "order_by": f"{zeit} desc"}, timeout=120).json()
            for r in probe.get("results", []):
                out.append("  letzte: " + json.dumps(r, ensure_ascii=False)[:600])
        r = abruf.hole(f"{basis}/api/explore/v2.1/catalog/datasets/{ds}/exports/csv",
                       params={"delimiter": ";", "timezone": "UTC"}, timeout=600)
        (ziel / f"{ds}.csv.gz").write_bytes(gzip.compress(r.content, mtime=0))
        zeilen = r.content.count(b"\n")
        out.append(f"  Export: {len(r.content) / 1e6:.1f} MB, {zeilen} Zeilen")
    except Exception:  # noqa: BLE001
        out.append(f"== {ds}: FEHLER " + traceback.format_exc().splitlines()[-1])
    schreib()
out += abruf.bericht()
schreib()
