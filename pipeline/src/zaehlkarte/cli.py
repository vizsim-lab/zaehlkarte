"""Kommandozeile: `uv run zaehlkarte fetch | build | site` (aus pipeline/), für die
Dauerzählstellen `uv run zaehlkarte dauer fetch | site | frische` (Kartendaten unter
public/data/dauer/; `frische` prüft das Gedächtnis)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer

from zaehlkarte import build as build_
from zaehlkarte import fetch as fetch_
from zaehlkarte import site as site_

app = typer.Typer(add_completion=False, no_args_is_help=True)
Quellen = Annotated[list[str] | None, typer.Option(help="nur diese Quellen (Code)")]
Datum = Annotated[str | None, typer.Option(help="Erzeugungsdatum im Manifest (JJJJ-MM-TT)")]


@app.command()
def fetch(quelle: Quellen = None) -> None:
    """Rohdaten nach pipeline/data/raw/ holen (nur was robots.txt erlaubt, mit Crawl-delay). Eine
    Quelle, die scheitert, hält die anderen nicht auf; Exit-Code 1, wenn eine scheitert – ohne
    ihre Rohdaten fehlte sie im Bau."""
    from zaehlkarte import abruf

    log, fehler = fetch_.hole(nur=quelle)
    for zeile in [*log, *abruf.bericht()]:
        typer.echo(zeile)
    if fehler:
        typer.echo(f"Abruf gescheitert: {', '.join(fehler)}")
        raise typer.Exit(1)


@app.command()
def lade(url: str, ziel: str) -> None:
    """Eine Datei holen wie die Pipeline (robots.txt, Crawl-delay, Ausnahmen aus sources.yaml) –
    für Workflows, die sonst curl nähmen."""
    from pathlib import Path

    from zaehlkarte import abruf
    from zaehlkarte.config import dauerquellen, quellen

    abruf.ausnahmen_setzen(quellen() | dauerquellen())
    try:
        abruf.lade(url, Path(ziel))
    except abruf.Gesperrt as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(2) from None
    for zeile in abruf.bericht():
        typer.echo(zeile)


@app.command()
def build(quelle: Quellen = None) -> None:
    """Alle Quellen lesen und den Bericht ausgeben (schreibt nichts)."""
    gebaut = build_.baue(nur=quelle)
    for code, zeilen in gebaut.berichte.items():
        for z in zeilen:
            typer.echo(f"{code}: {z}")
    typer.echo(f"Stellen: {len(gebaut.stellen)}")


@app.command("geokodier-liste")
def geokodier_liste(ziel: str) -> None:
    """Berliner Zählungen ohne Lage als CSV (Eingabe für den Workflow „Berlin geokodieren“)."""
    import csv

    from zaehlkarte.adapters import berlin_zda
    from zaehlkarte.config import Pfade, quellen

    zeilen = berlin_zda.geokodier_liste(quellen()["berlin"], Pfade())
    with open(ziel, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["datei", "bez", "name", "arme", "plz", "ortsteil"])
        w.writeheader()
        w.writerows(zeilen)
    typer.echo(f"{len(zeilen)} Zählungen ohne Lage -> {ziel}")


@app.command()
def site(datum: Datum = None) -> None:
    """Kartendaten nach public/data/ schreiben."""
    gebaut = build_.baue()
    for code, zeilen in gebaut.berichte.items():
        for z in zeilen:
            typer.echo(f"{code}: {z}")
    erzeugt = date.fromisoformat(datum) if datum else None
    for pfad in site_.schreibe(gebaut, erzeugt=erzeugt):
        typer.echo(f"{pfad.relative_to(pfad.parents[2])}: {pfad.stat().st_size // 1024} KB")


@app.command()
def kalender(
    monate: Annotated[int, typer.Option(help="so weit voraus müssen die Ferien reichen")] = 3,
) -> None:
    """Ferienkalender je Land (erstes und letztes Schuljahr): Exit-Code 1, wenn der Kalender
    eines Landes vor dem Schuljahr endet, das in `--monate` Monaten läuft – sonst wäre danach
    jeder Werktag „unbekannt“."""
    from datetime import timedelta

    from zaehlkarte.config import Pfade
    from zaehlkarte.kalender import abdeckung

    zeilen, fehlt = abdeckung(Pfade().config, date.today() + timedelta(days=round(30.5 * monate)))
    for z in zeilen:
        typer.echo(z)
    if fehlt:
        raise typer.Exit(1)


@app.command()
def datenlage(datum: Datum = None) -> None:
    """Nur datenlage.json und docs/DATENLAGE.md erneuern (aus sources.yaml und der vorhandenen
    index.json) – für geänderte Datenlage-Texte ohne neuen Bau."""
    erzeugt = date.fromisoformat(datum) if datum else None
    for pfad in site_.schreibe_datenlage(erzeugt=erzeugt):
        typer.echo(f"{pfad}: {pfad.stat().st_size // 1024} KB")


dauer = typer.Typer(no_args_is_help=True,
                    help="Dauerzählstellen: eigene Familie, Kartendaten unter public/data/dauer/")
app.add_typer(dauer, name="dauer")


@dauer.command("fetch")
def dauer_fetch(quelle: Quellen = None) -> None:
    """Rohdaten der Dauerzählstellen nach pipeline/data/raw/ holen (eine Quelle, die scheitert,
    hält die anderen nicht auf; Exit-Code 1 nur, wenn alle scheitern)."""
    from zaehlkarte import abruf
    from zaehlkarte.config import Pfade, dauerquellen
    from zaehlkarte.dauer import bau

    log, fehler = bau.hole(nur=quelle)
    for zeile in [*log, *abruf.bericht()]:
        typer.echo(zeile)
    if fehler:
        typer.echo(f"Abruf gescheitert: {', '.join(fehler)}")
    versucht = [c for c in dauerquellen(Pfade()) if not quelle or c in quelle]
    if fehler and len(fehler) == len(versucht):
        raise typer.Exit(1)


@dauer.command("frische")
def dauer_frische(
    tage: Annotated[float, typer.Option(help="höchstes Alter der jüngsten Stunde")] = 10,
) -> None:
    """Gedächtnis prüfen (Quellen, die Stundenwerte nur kurz vorhalten): Exit-Code 1, wenn die
    jüngste Stunde einer Quelle älter als `--tage` ist – dann scheitert ihr Abruf seit mindestens
    einem Wochenlauf, und bald fehlen Stunden für immer (Leipzig hält 31 Tage vor)."""
    from datetime import UTC, datetime

    from zaehlkarte.config import Pfade
    from zaehlkarte.dauer import bau, gedaechtnis

    pfade = Pfade()
    zeilen, alt = gedaechtnis.frische(pfade.roh, bau.mit_gedaechtnis(pfade), datetime.now(UTC),
                                      tage)
    for z in zeilen:
        typer.echo(z)
    if alt:
        raise typer.Exit(1)


@dauer.command("site")
def dauer_site(datum: Datum = None) -> None:
    """Kartendaten der Dauerzählstellen nach public/data/dauer/ schreiben."""
    from zaehlkarte.dauer import bau

    erzeugt = date.fromisoformat(datum) if datum else None
    _, zeilen = bau.site(erzeugt=erzeugt)
    for z in zeilen:
        typer.echo(z)


if __name__ == "__main__":
    app()
