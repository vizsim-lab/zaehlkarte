"""Kennzahlen einer Zählung: Summen über ein Zeitfenster, Spitzenstunde, Schulweg-Kriterium.

Die Einordnung (`status`) und das Kriterium (`verdacht`) rechnet die Karte mit denselben
Regeln im Browser nach (js/data/modell.js: bewerte) – wer eine Seite ändert, ändert beide;
tests/unit/modell.test.js prüft das Frontend gegen die Fälle aus pipeline/tests.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class Kriterien:
    schulstunden: tuple[int, ...] = (7, 8, 13, 14, 15)
    schwelle_stunde: int = 50
    schwelle_tag: int = 300
    tag_von: int = 7
    tag_bis: int = 19

    @classmethod
    def aus_config(cls, cfg: dict) -> Kriterien:
        return cls(
            schulstunden=tuple(cfg["schulstunden"]),
            schwelle_stunde=int(cfg["schwelle_stunde"]),
            schwelle_tag=int(cfg["schwelle_tag"]),
            tag_von=int(cfg["tag_von"]),
            tag_bis=int(cfg["tag_bis"]),
        )


def verdacht(z: Zaehlung, k: Kriterien) -> tuple[bool | None, list[str]]:
    """Schulweg-Kriterium nach den Zahlen: (True/False, Gründe); None = nicht beurteilbar.

    Verdacht, wenn in einer Schulstunde mehr als `schwelle_stunde` Kinder/Jugendliche
    gezählt sind ODER von `tag_von` bis `tag_bis` Uhr mehr als `schwelle_tag`."""
    kind = {h: v for h, v in reihe(z, "kind").items() if v is not None}
    if not kind:
        return None, ["Kinder/Jugendliche nicht gezählt"]
    gruende = [f"{h} Uhr: {kind[h]}" for h in k.schulstunden if kind.get(h, -1) > k.schwelle_stunde]
    tag = summe(z, "kind", k.tag_von, k.tag_bis)
    if tag is not None and tag > k.schwelle_tag:
        gruende.append(f"{k.tag_von}–{k.tag_bis} Uhr: {tag}")
    if tag is None and not any(h in kind for h in k.schulstunden):
        return None, ["zu Schulzeiten nicht gezählt"]
    return bool(gruende), gruende


SCHULFREI = ("ferien", "feiertag", "wochenende")


def status(kriterium: bool | None, tagtyp: str | None) -> str:
    """verdacht | kein | schulfrei | unbekannt – an schulfreien Tagen nie Verdacht."""
    if kriterium is None:
        return "unbekannt"
    if tagtyp in SCHULFREI:
        return "schulfrei"
    return "verdacht" if kriterium else "kein"
