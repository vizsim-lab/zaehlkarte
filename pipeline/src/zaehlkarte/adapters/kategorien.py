"""Kategorien der Berliner ZDA-Dateien (`art=`) -> Gruppen des Zählungsschemas.

Die Mengen beruhen auf allen 28.742 Dateien beider Archive (83 verschiedene Kategorien).
Häufigste Kopfzeilen: „Pkw+Lfw, Lkw, Bus, Krad, Radf“, „Erw, Jugend“, „Radf“,
„Pkw+Lfw, Lkw(>3.5t), Bus, Krad, Radf“, „Pkw+Kr, LiefWg, Lkw, Bus, Radf“.

- kfz: die Kfz-Summe der Quelle, sonst die Summe der Fahrzeugarten – aber nur, wo Pkw (oder
  „übrige Kfz“) gezählt sind. Busspur-Zählungen (Bus, Taxi, Radf) ergäben sonst Kfz-Werte,
  die mit Straßen nicht vergleichbar sind (Regel aus dem Schulwege-Projekt).
- sv: Lkw (wo Lieferwagen bei den Pkw oder extra stehen, ist „Lkw“ der schwere Lkw),
  Lastzüge und Busse – nur zusammen mit kfz.
- rad: Radfahrende.
- fuss: alle zu Fuß Gehenden (mit und ohne Altersangabe).
- kind: Kinder/Jugendliche – nur, wo auch Erwachsene getrennt gezählt sind (sonst ist die
  Altersgruppe kein Anteil, sondern eine Teilzählung). „Erw, Azubi“ zählt nicht dazu.
E-Tretroller, Tram und unklare Kürzel („5“, „ü“) gehören zu keiner Gruppe.
"""

from __future__ import annotations

FUSS_ERW = {"erw", "erw.", "erw-g", "erw-rot", "erw<65", "erw>65", "senioren", "fußgäng", "azubi"}
FUSS_KIND = {"jugend", "jugend-g", "jug-rot", "kinder", "schuel", "schül", "schüler"}
FUSS_OHNE_ALTER = {"fussg", "fußg", "mobfuß", "kiwafuß", "behindr", "behind"}
RAD = {"radf", "radfahrer", "rad", "radf-erw", "radf-jug", "radf-f", "radg"}
KFZ_SUMME = {"kfz"}
KFZ_UEBRIGE = {"ükfz", "übrkfz"}  # „übrige Kfz“ neben extra gezählten Lkw
SV = {
    "lkw", "lkw(1)", "lkw(2)", "lkw(>3.5t)", "lkw(l)", "lkw(s)", "lkw(leicht)", "lkw(schwer)",
    "lkw+bus", "lkw+", "g-lkw", "lk<7", "lk>7", "lzug", "lz",
    "bus", "bvg-bus", "reisebus", "bus-lv", "bus-gv",
}  # fmt: skip
KFZ_TEILE = SV | KFZ_UEBRIGE | {
    "pkw", "pkw+", "pkw+lfw", "pkw+kr", "pkw+lfw+kr", "pkw+lw+k", "pkw+l+kr", "pklfwg",
    "liefwg", "liefw", "liefer", "lfw", "krad", "m+krad", "taxi", "taxen", "kfzs",
    "einsfz", "rettfz", "krk-fz", "bsr", "sonst", "sonstg", "falsch",
}  # fmt: skip


def spalten(kategorien: list[str]) -> dict[str, list[int]]:
    """{'kfz': [0, 1, 2, 3], 'sv': [1, 2], 'rad': [4]} – Spalten je Gruppe."""
    ks = [k.strip().lower() for k in kategorien]

    def idx(menge: set[str]) -> list[int]:
        return [i for i, k in enumerate(ks) if k in menge]

    out: dict[str, list[int]] = {}
    if idx(KFZ_SUMME):
        out["kfz"] = idx(KFZ_SUMME)
    elif any(k.startswith(("pkw", "pklfw")) for k in ks) or idx(KFZ_UEBRIGE):
        out["kfz"] = idx(KFZ_TEILE)
    if "kfz" in out and idx(SV):
        out["sv"] = idx(SV)
    if idx(RAD):
        out["rad"] = idx(RAD)
    erw, kind, ohne = idx(FUSS_ERW), idx(FUSS_KIND), idx(FUSS_OHNE_ALTER)
    if erw or kind or ohne:
        out["fuss"] = sorted(erw + kind + ohne)
    if erw and kind:
        out["kind"] = kind
    return out
