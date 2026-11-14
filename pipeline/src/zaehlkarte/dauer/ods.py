"""Opendatasoft-Portale (Würzburg, Rhein-Kreis Neuss, Dortmund): einen Datensatz als CSV über die
Explore-API v2.1 exportieren – nur wenn er sich laut Metadaten geändert hat.

Der Export (`…/exports/csv?select=…&timezone=UTC`) liefert alle Zeilen in einer Datei, Zeiten in
UTC; `abruf.json` im Rohdatenordner merkt sich den Stand der Metadaten (`modified`,
`data_processed`). Der Export ist der Download, den die Kataloge (etwa Open.NRW) als Verteilung
des Datensatzes nennen.
"""

from __future__ import annotations

import json
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path


def metadaten(basis: str, datensatz: str) -> dict:
    from zaehlkarte import abruf

    return abruf.hole(f"{basis}/api/explore/v2.1/catalog/datasets/{datensatz}").json()


def datensaetze(basis: str, datensatz: str, **params: str) -> list[dict]:
    """Einige Datensätze über die Records-API (höchstens 100)."""
    from zaehlkarte import abruf

    r = abruf.hole(f"{basis}/api/explore/v2.1/catalog/datasets/{datensatz}/records",
                   params={"limit": "100", **params})
    return r.json().get("results", [])


def export_url(basis: str, datensatz: str, select: str) -> str:
    return (f"{basis}/api/explore/v2.1/catalog/datasets/{datensatz}/exports/csv?"
            + urllib.parse.urlencode({"select": select, "delimiter": ";", "timezone": "UTC"}))


def hole_export(basis: str, datensatz: str, select: str, ordner: Path, name: str) -> str:
    """Export nach `ordner/name` laden, wenn sich der Datensatz geändert hat. -> Logzeile."""
    from zaehlkarte.fetch import lade

    ordner.mkdir(parents=True, exist_ok=True)
    meta = metadaten(basis, datensatz)
    m = (meta.get("metas") or {}).get("default") or {}
    stand = f"{m.get('modified')}|{m.get('data_processed')}"
    abruf = ordner / "abruf.json"
    alt = json.loads(abruf.read_text(encoding="utf-8")) if abruf.exists() else {}
    eintrag = alt.get(name) or {}
    url = export_url(basis, datensatz, select)
    if eintrag.get("stand") == stand and eintrag.get("url") == url and (ordner / name).exists():
        return f"{datensatz}: unverändert seit {m.get('data_processed')}"
    lade(url, ordner / name)
    alt[name] = {"url": url, "stand": stand, "datensaetze": m.get("records_count"),
                 "abgerufen": datetime.now(UTC).replace(microsecond=0).isoformat()
                 .replace("+00:00", "Z")}
    abruf.write_text(json.dumps(alt, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return f"{datensatz}: {m.get('records_count')} Zeilen geladen (Stand {m.get('data_processed')})"
