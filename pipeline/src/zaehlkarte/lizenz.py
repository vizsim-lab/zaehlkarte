"""Lizenzangaben der Quellen für die Kartendaten beider Familien (site.py, dauer/site.py)."""

from __future__ import annotations


def ohne_lizenz(x: dict) -> dict:
    """Quelle oder Lieferung ohne Lizenz (CLAUDE.md, „Quellen ohne Lizenz“): `ohne_lizenz` mit
    dem Weg, auf dem die Kommune die Werte herausgegeben hat, und dem Tag der Prüfung – die Karte
    zeigt dann „ohne Lizenz“ und lässt die Werte im CSV-Export weg. Leer bei einer Lizenz, damit
    sich die Kartendaten der übrigen Quellen nicht ändern."""
    o = x.get("ohne_lizenz")
    if not o:
        return {}
    geprueft = o["geprueft"]
    return {"ohne_lizenz": {
        "herausgegeben": " ".join(str(o["herausgegeben"]).split()),
        "geprueft": geprueft.isoformat() if hasattr(geprueft, "isoformat") else str(geprueft),
    }}
