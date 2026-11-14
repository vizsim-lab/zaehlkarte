"""Kommandozeile: `uv run zaehlkarte fetch | build | site` (aus pipeline/), für die
Dauerzählstellen `uv run zaehlkarte dauer fetch | site` (Kartendaten unter public/data/dauer/)."""

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
    """Rohdaten nach pipeline/data/raw/ holen (nur was robots.txt erlaubt, mit Crawl-delay)."""
    from zaehlkarte import abruf

    for zeile in [*fetch_.hole(nur=quelle), *abruf.bericht()]:
        typer.echo(zeile)


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
    versucht = [c for c in dauerquellen(Pfade()) if not quelle or c in quelle]
    if fehler and len(fehler) == len(versucht):
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
