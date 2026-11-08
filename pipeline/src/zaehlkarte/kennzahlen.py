"""Kennzahlen einer Zählung: Summen über ein Zeitfenster und die stärkste Stunde.

Nur Zählwerte, keine Einstufung: Werte aus verschiedenen Zählfenstern werden nie ineinander
umgerechnet; wo ein Fenster nicht vollständig gezählt ist, ist die Summe None.
"""

from __future__ import annotations

from zaehlkarte.modell import Zaehlung


def reihe(z: Zaehlung, gruppe: str) -> dict[int, int | None]:
    """{Stunde: Wert} der Gruppe (leer, wenn die Gruppe keine Stundenwerte hat)."""
    werte = z.stunden.get(gruppe) or []
    return {z.h0 + i: v for i, v in enumerate(werte)} if z.h0 is not None else {}


def summe(z: Zaehlung, gruppe: str, von: int, bis: int) -> int | None:
    """Summe der Stunden von..bis-1 – nur, wenn jede davon gezählt ist, sonst None.

    So sind 12- und 24-Stunden-Zählungen vergleichbar, und eine Zählung von 15 bis 18 Uhr
    bekommt keine scheinbar niedrige Tagessumme."""
    r = reihe(z, gruppe)
    if any(r.get(h) is None for h in range(von, bis)):
        return None
    return sum(r[h] for h in range(von, bis))


def tag24(z: Zaehlung, gruppe: str) -> int | None:
    """Summe über 24 Stunden: aus den Stundenwerten oder der gelieferten Tagessumme."""
    if gruppe in z.summen:
        return z.summen[gruppe]
    return summe(z, gruppe, 0, 24)


def spitzenstunde(z: Zaehlung, gruppe: str) -> tuple[int, int] | None:
    """(Stunde, Wert) der stärksten gezählten Stunde."""
    r = {h: v for h, v in reihe(z, gruppe).items() if v is not None}
    if not r:
        return None
    h = max(r, key=lambda k: (r[k], -k))
    return h, r[h]
