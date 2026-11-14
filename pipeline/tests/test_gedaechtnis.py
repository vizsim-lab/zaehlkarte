"""werkzeuge/gedaechtnis.py gegen nachgebaute Releases: holen, ablegen, nie mit weniger Werten,
abgebrochene Ablage (`.neu`) wird beim Holen übernommen, zweite Kopie je Jahr (jede Fassung
einmal, nie ersetzt); dazu `frische` (zaehlkarte dauer frische): Wächst das Gedächtnis noch?"""

from __future__ import annotations

import gzip
import importlib.util
import itertools
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zaehlkarte import cli
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bau
from zaehlkarte.dauer import gedaechtnis as modul_gedaechtnis

WERKZEUG = Path(__file__).resolve().parents[1] / "werkzeuge" / "gedaechtnis.py"


@pytest.fixture
def gd(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("gedaechtnis", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setattr(modul, "ROH", tmp_path / "raw")
    monkeypatch.setattr(modul, "VORHER", tmp_path / "raw" / "gedaechtnis_vorher.json")
    monkeypatch.setattr(modul, "repo", lambda: "o/r")
    github = FakeGitHub(tmp_path / "releases", "dauerzaehlstellen")
    monkeypatch.setattr(modul, "gh", github.gh)
    modul.github = github
    modul.release = github.releases["dauerzaehlstellen"]
    return modul


class FakeRelease:
    """Ein Release als Ordner (Name -> Datei); die IDs der Assets zählt FakeGitHub über alle."""

    def __init__(self, ordner: Path, ids: itertools.count):
        self.ordner = ordner
        ordner.mkdir(parents=True)
        self.ids: dict[str, int] = {}
        self._ids = ids

    def lege(self, name: str, daten: bytes) -> None:
        (self.ordner / name).write_bytes(daten)
        self.ids[name] = next(self._ids)


class FakeGitHub:
    """Die gh-Aufrufe des Werkzeugs auf Ordnern, ein Release je Tag."""

    def __init__(self, ordner: Path, *tags: str):
        self.ordner = ordner
        self._ids = itertools.count(1)
        self.releases: dict[str, FakeRelease] = {}
        self.notizen: dict[str, str] = {}
        self.aufrufe: list[tuple] = []
        for tag in tags:
            self.releases[tag] = FakeRelease(ordner / tag, self._ids)

    def _rid(self, tag: str) -> int:
        return 100 + list(self.releases).index(tag)

    def _asset(self, i: int) -> tuple[FakeRelease, str]:
        return next((r, n) for r in self.releases.values() for n, x in r.ids.items() if x == i)

    def gh(self, *args, ausgabe=False):
        self.aufrufe.append(args)
        if args[0] == "api" and args[1].startswith("repos/o/r/releases/tags/"):
            tag = args[1].rsplit("/", 1)[1]
            if tag not in self.releases:
                raise subprocess.CalledProcessError(1, ["gh", *args])
            return json.dumps({"id": self._rid(tag)})
        if args[0] == "api" and "--paginate" in args:
            rid = int(next(a for a in args if "/assets" in a).split("/")[4])
            r = self.releases[list(self.releases)[rid - 100]]
            return json.dumps([[{"name": n, "id": i} for n, i in r.ids.items()]])
        if args[:3] == ("api", "-X", "DELETE"):
            r, name = self._asset(int(args[3].rsplit("/", 1)[1]))
            (r.ordner / name).unlink()
            del r.ids[name]
            return ""
        if args[:3] == ("api", "-X", "PATCH"):
            r, alt = self._asset(int(args[3].rsplit("/", 1)[1]))
            neu = args[5].split("=", 1)[1]
            assert neu not in r.ids
            (r.ordner / alt).rename(r.ordner / neu)
            r.ids[neu] = r.ids.pop(alt)
            return ""
        if args[:2] == ("release", "view"):
            if args[2] not in self.releases:
                raise subprocess.CalledProcessError(1, ["gh", *args])
            return ""
        if args[:2] == ("release", "create"):
            assert args[2] not in self.releases and "--latest=false" in args
            self.releases[args[2]] = FakeRelease(self.ordner / args[2], self._ids)
            self.notizen[args[2]] = args[args.index("--notes") + 1]
            return ""
        if args[:2] == ("release", "upload"):
            r, pfad = self.releases[args[2]], Path(args[3])
            assert "--clobber" not in args and pfad.name not in r.ids, "Name schon da"
            r.lege(pfad.name, pfad.read_bytes())
            return ""
        if args[:2] == ("release", "download"):
            r = self.releases[args[2]]
            name, ziel = args[args.index("--pattern") + 1], Path(args[args.index("--dir") + 1])
            shutil.copyfile(r.ordner / name, ziel / name)
            return ""
        raise AssertionError(f"unerwarteter Aufruf: {args}")


def csv_gz(*zeilen: str) -> bytes:
    kopf = "stelle;gruppe;tag;" + ";".join(f"h{h:02d}" for h in range(24))
    return gzip.compress(("\n".join([kopf, *zeilen]) + "\n").encode(), mtime=0)


def zeile(stelle: str, tag: str, n: int) -> str:
    return f"{stelle};kfz;{tag};" + ";".join(["5"] * n + [""] * (24 - n))


def test_holen_ablegen_und_nie_weniger(gd, tmp_path):
    gd.holen("dauerzaehlstellen")  # leerer Release
    ordner = tmp_path / "raw" / "hamburg_kfz" / "gedaechtnis"
    ordner.mkdir(parents=True)
    (ordner / "stunden_2026-11.csv.gz").write_bytes(csv_gz(zeile("0248931", "2026-11-01", 24)))
    (ordner / "strassen.json").write_text(json.dumps({"stellen": {"0248931": {"name": "X"}}}))
    gd.ablegen("dauerzaehlstellen")
    namen = {"hamburg_kfz__stunden_2026-11.csv.gz", "hamburg_kfz__strassen.json"}
    assert set(gd.release.ids) == namen

    # nächster Lauf: holen, ein Monat wächst -> nur er wird ersetzt (über .neu, dann umbenannt)
    shutil.rmtree(tmp_path / "raw")
    gd.holen("dauerzaehlstellen")
    assert (ordner / "stunden_2026-11.csv.gz").exists()
    (ordner / "stunden_2026-11.csv.gz").write_bytes(csv_gz(zeile("0248931", "2026-11-01", 24),
                                                            zeile("0248931", "2026-11-02", 12)))
    gd.github.aufrufe.clear()
    gd.ablegen("dauerzaehlstellen")
    hochgeladen = [a[3] for a in gd.github.aufrufe if a[:2] == ("release", "upload")]
    assert [Path(p).name for p in hochgeladen] == ["hamburg_kfz__stunden_2026-11.csv.gz.neu"]
    assert set(gd.release.ids) == namen
    assert gzip.decompress((gd.release.ordner / "hamburg_kfz__stunden_2026-11.csv.gz").read_bytes()
                           ).count(b"\n") == 3

    # weniger Werte als beim Holen: nicht ablegen, der Release bleibt, wie er ist
    gd.holen("dauerzaehlstellen")
    (ordner / "stunden_2026-11.csv.gz").write_bytes(csv_gz(zeile("0248931", "2026-11-01", 24)))
    vorher = (gd.release.ordner / "hamburg_kfz__stunden_2026-11.csv.gz").read_bytes()
    with pytest.raises(SystemExit, match="weniger Werte"):
        gd.ablegen("dauerzaehlstellen")
    assert (gd.release.ordner / "hamburg_kfz__stunden_2026-11.csv.gz").read_bytes() == vorher


def test_abgebrochene_ablage_und_ohne_holen(gd, tmp_path):
    # Abbruch nach dem Hochladen der neuen Fassung: X und X.neu liegen beide im Release
    gd.release.lege("hamburg_rad__stunden_2026-10.csv.gz",
                    csv_gz(zeile("7433952", "2026-10-01", 24)))
    gd.release.lege("hamburg_rad__stunden_2026-10.csv.gz.neu", csv_gz(
        zeile("7433952", "2026-10-01", 24), zeile("7433952", "2026-10-02", 24)))
    gd.holen("dauerzaehlstellen")
    lokal = tmp_path / "raw" / "hamburg_rad" / "gedaechtnis" / "stunden_2026-10.csv.gz"
    assert gzip.decompress(lokal.read_bytes()).count(b"\n") == 3  # die vollständigere .neu-Fassung
    # ablegen ohne vorheriges holen verweigert (sonst könnte eine leere Fassung die alte ersetzen)
    (tmp_path / "raw" / "gedaechtnis_vorher.json").unlink()
    with pytest.raises(SystemExit, match="erst `holen`"):
        gd.ablegen("dauerzaehlstellen")


def test_zweite_kopie_jede_fassung_einmal_nie_ersetzt(gd, tmp_path):
    ordner = tmp_path / "raw" / "leipzig_rad" / "gedaechtnis"
    ordner.mkdir(parents=True)
    monat = ordner / "stunden_2026-11.csv.gz"
    monat.write_bytes(csv_gz(zeile("100", "2026-11-01", 24)))
    gd.kopieren(datetime(2026, 11, 16, 5, 41, 12, tzinfo=UTC))
    kopie = gd.github.releases["gedaechtnis-kopie-2026"]
    assert "Leipzig: dl-de/by-2-0" in gd.github.notizen["gedaechtnis-kopie-2026"]
    erste = f"2026-11-16T054112Z__{gd.sha(monat)[:12]}__leipzig_rad__stunden_2026-11.csv.gz"
    assert list(kopie.ids) == [erste]

    # unverändert: nichts Neues; geändert: eine weitere Fassung daneben, die erste bleibt
    gd.kopieren(datetime(2026, 11, 23, 5, 41, tzinfo=UTC))
    assert list(kopie.ids) == [erste]
    monat.write_bytes(csv_gz(zeile("100", "2026-11-01", 24), zeile("100", "2026-11-02", 24)))
    gd.kopieren(datetime(2026, 11, 30, 5, 41, tzinfo=UTC))
    assert len(kopie.ids) == 2 and erste in kopie.ids
    assert (kopie.ordner / erste).read_bytes() == csv_gz(zeile("100", "2026-11-01", 24))
    assert not any(a[:3] in (("api", "-X", "DELETE"), ("api", "-X", "PATCH"))
                   for a in gd.github.aufrufe)

    # neues Jahr, neues Release (höchstens 1000 Assets je Release): alles einmal hinein
    gd.kopieren(datetime(2027, 1, 4, 5, 41, tzinfo=UTC))
    assert len(gd.github.releases["gedaechtnis-kopie-2027"].ids) == 1
    assert len(kopie.ids) == 2


def test_kopie_ohne_gedaechtnis(gd):
    gd.kopieren(datetime(2026, 11, 16, tzinfo=UTC))
    assert set(gd.github.releases) == {"dauerzaehlstellen"}


def _gedaechtnis(roh: Path, code: str, *zeilen: str) -> None:
    ordner = roh / code / "gedaechtnis"
    ordner.mkdir(parents=True)
    for z in zeilen:
        monat = z.split(";")[2][:7]
        (ordner / f"stunden_{monat}.csv.gz").write_bytes(csv_gz(z))


def test_frische(tmp_path):
    roh = tmp_path / "raw"
    _gedaechtnis(roh, "frisch", zeile("1", "2026-10-31", 24), zeile("1", "2026-11-14", 6))
    _gedaechtnis(roh, "alt", zeile("2", "2026-11-02", 24))
    (roh / "leer" / "gedaechtnis").mkdir(parents=True)
    jetzt = datetime(2026, 11, 16, 6, tzinfo=UTC)
    assert modul_gedaechtnis.juengste_stunde(roh / "frisch" / "gedaechtnis") == datetime(
        2026, 11, 14, 5, tzinfo=UTC)
    zeilen, alt = modul_gedaechtnis.frische(roh, ["frisch", "alt", "leer", "fehlt"], jetzt, 10)
    assert alt == ["alt", "leer", "fehlt"]
    assert zeilen[0] == "Gedächtnis frisch: jüngste Stunde 14.11.2026, 05 Uhr UTC (vor 2,0 Tagen)"
    assert zeilen[1].startswith("Gedächtnis alt: jüngste Stunde 02.11.2026, 23 Uhr UTC (vor 13,3")
    assert "älter als 10 Tage" in zeilen[1]
    assert zeilen[2:] == ["Gedächtnis leer: keine Stunden", "Gedächtnis fehlt: keine Stunden"]


def test_frische_cli_und_quellen_mit_gedaechtnis(tmp_path, monkeypatch):
    assert bau.mit_gedaechtnis() == ["hamburg_kfz", "hamburg_rad", "leipzig_rad"]
    pfade = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    jetzt = datetime.now(UTC)
    _gedaechtnis(pfade.roh, "q", zeile("1", jetzt.date().isoformat(), 1))
    monkeypatch.setattr("zaehlkarte.config.Pfade", lambda: pfade)
    monkeypatch.setattr(bau, "mit_gedaechtnis", lambda pfade=None: ["q"])
    r = CliRunner().invoke(cli.app, ["dauer", "frische"])
    assert r.exit_code == 0 and r.output.startswith("Gedächtnis q: jüngste Stunde")
    r = CliRunner().invoke(cli.app, ["dauer", "frische", "--tage", "-1"])
    assert r.exit_code == 1
