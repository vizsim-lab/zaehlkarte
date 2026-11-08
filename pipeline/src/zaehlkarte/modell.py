"""Das gemeinsame Zählungsschema: jeder Adapter liefert `Zaehlung`-Objekte.

Eine Zählung ist ein Zähltag an einer Stelle. Werte stehen je Gruppe als Stundenreihe ab
`h0` (Summe über alle Richtungen); `None` heißt „nicht gezählt“, nie 0. Hat eine Quelle nur
Tagessummen (MobiData-BW-Übersicht), stehen sie in `summen` und `stunden` bleibt leer. Nennt
sie nur Spitzenstunden, die nicht auf vollen Stunden liegen, und die Summe der gezählten
Stunden (Potsdam), stehen sie in `spitzen` und `fenstersummen`.

Gruppen:
- kfz   Kraftfahrzeuge (Kfz-Summe der Quelle oder Summe der Fahrzeugarten)
- sv    Schwerverkehr (Lkw über 3,5 t, Lastzüge, Busse) – nur, wo Kfz gezählt sind
- rad   Radfahrende
- fuss  zu Fuß Gehende (alle Altersgruppen)
- kind  Kinder/Jugendliche (Quellkategorien „Jugend“, „Kinder“, „Schüler“) – nur, wo nach
        Alter getrennt gezählt ist
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

GRUPPEN = ("kfz", "sv", "rad", "fuss", "kind")


@dataclass
class Zaehlung:
    quelle: str  # Code aus sources.yaml
    kennung: str  # eindeutig je Quelle, stabil (Dateiname ohne Endung, ID + Datum)
    stelle_roh: str | None  # Zählstellen-Kennung der Quelle („K10921“), None = unbekannt
    name: str
    typ: str  # "K" Knotenpunkt | "Q" Querschnitt | "" unbekannt
    lon: float | None
    lat: float | None
    lage: str | None  # gps | geokodiert | quelle | uebertragen | None (nicht verortet)
    datum: date | None
    fenster: list[tuple[int, int]]  # gezählte Zeit, Minuten ab Mitternacht, [von, bis)
    intervall: int | None  # Minuten
    h0: int | None = None  # Stunde des ersten Werts in `stunden`
    stunden: dict[str, list[int | None]] = field(default_factory=dict)
    summen: dict[str, int | None] = field(default_factory=dict)  # nur Tagessummen
    # Spitzenstunden laut Quelle: [{"von", "bis" (Minuten), "name", "nach" (Gruppe, nach der die
    # Stunde bestimmt ist), "werte": {Gruppe: Wert}}] – nur, wo es keine Stundenreihe gibt
    spitzen: list[dict] = field(default_factory=list)
    fenstersummen: dict[str, int | None] = field(default_factory=dict)  # Summe über `fenster`
    land: str = ""
    gebiet: str | None = None  # Feriengebiet, wo es mehrere gab (Berlin West/Ost bis 1991)
    richtungen: int | None = None
    kategorien: str = ""
    rohdatei: str | None = None  # Link auf die Rohdatei, wo es einen gibt
    lizenz: str | None = None  # wenn je Lieferung verschieden (Berlin: zwei Archive)
    lieferung: str | None = None
    bemerkung: str | None = None
    hinweise: list[str] = field(default_factory=list)
    tagtyp: str | None = None  # schule | ferien | feiertag | wochenende | None (unbekannt)
    tagname: str | None = None  # „Sommerferien“, „Pfingstmontag“, „Samstag“
    zusatz: dict = field(default_factory=dict)  # Rohangaben des Adapters (nicht in der Karte)

    def gruppen(self) -> list[str]:
        """Gruppen, für die die Zählung Werte hat (in der Reihenfolge von GRUPPEN)."""
        da = {g for g, r in self.stunden.items() if any(v is not None for v in r)}
        da |= {g for g, v in self.summen.items() if v is not None}
        da |= {g for g, v in self.fenstersummen.items() if v is not None}
        da |= {g for s in self.spitzen for g, v in s.get("werte", {}).items() if v is not None}
        return [g for g in GRUPPEN if g in da]
