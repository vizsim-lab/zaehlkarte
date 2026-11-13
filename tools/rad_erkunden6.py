"""Erkundung (13.11.2026), Teil 6: Hat MobiData BW die Eco-Counter-Werte irgendwo mit Status?
Felder der Datastore-Ressourcen, Verzeichnis der historischen Daten, Ressourcen des Pakets."""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ZIEL = Path("ergebnis/rad6")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


aus = []
for rid in ("3efeb12d-b485-444a-a8a3-70e746baa334", "bbb274af-580d-4228-851e-c8daf32d3c6e"):
    try:
        d = json.loads(hole(f"https://mobidata-bw.de/api/3/action/datastore_search?resource_id={rid}&limit=3"))["result"]
        aus.append(f"## Datastore {rid}: Felder {[(f['id'], f['type']) for f in d['fields']]}; gesamt {d.get('total')}")
        aus.append("   " + json.dumps(d["records"], ensure_ascii=False)[:1200])
    except Exception as e:  # noqa: BLE001
        aus.append(f"## Datastore {rid}: {e!r}")
for url in ("https://mobidata-bw.de/fahrradzaehldaten/v2/", "https://mobidata-bw.de/fahrradzaehldaten/"):
    try:
        t = hole(url).decode("utf-8", "replace")
        links = re.findall(r'href="([^"]+)"', t)
        aus.append(f"## {url}: {len(links)} Links: {links[:60]}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## {url}: {e!r}")
try:
    p = json.loads(hole("https://mobidata-bw.de/api/3/action/package_show?id=eco-counter-fahrradzahler"))["result"]
    for r in p["resources"]:
        aus.append(f"- {r.get('name')} | {r.get('format')} | {r.get('url')} | {(r.get('description') or '')[:300]!r}")
except Exception as e:  # noqa: BLE001
    aus.append(f"## Paket: {e!r}")
(ZIEL / "mobidata.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
