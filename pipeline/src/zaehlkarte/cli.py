"""Kommandozeile: `uv run zaehlkarte fetch | build | site` (aus pipeline/)."""

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
    """Rohdaten nach pipeline/data/raw/ holen."""
    for zeile in fetch_.hole(nur=quelle):
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


if __name__ == "__main__":
    app()
