"""werkzeuge/gedaechtnis.py gegen einen nachgebauten Release: holen, ablegen, nie mit weniger
Werten, abgebrochene Ablage (`.neu`) wird beim Holen übernommen."""

from __future__ import annotations

import gzip
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

WERKZEUG = Path(__file__).resolve().parents[1] / "werkzeuge" / "gedaechtnis.py"


@pytest.fixture
def gd(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("gedaechtnis", WERKZEUG)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    monkeypatch.setattr(modul, "ROH", tmp_path / "raw")
    monkeypatch.setattr(modul, "VORHER", tmp_path / "raw" / "gedaechtnis_vorher.json")
    monkeypatch.setattr(modul, "repo", lambda: "o/r")
    release = FakeRelease(tmp_path / "release")
    monkeypatch.setattr(modul, "gh", release.gh)
    modul.release = release
    return modul


class FakeRelease:
    """Die gh-Aufrufe des Werkzeugs auf einem Ordner (Name -> Datei, fortlaufende IDs)."""

    def __init__(self, ordner: Path):
        self.ordner = ordner
        ordner.mkdir()
        self.ids: dict[str, int] = {}
        self.naechste = 1
        self.aufrufe: list[tuple] = []

    def lege(self, name: str, daten: bytes) -> None:
        (self.ordner / name).write_bytes(daten)
        self.ids[name] = self.naechste
        self.naechste += 1

    def gh(self, *args, ausgabe=False):
        self.aufrufe.append(args)
        if args[:2] == ("api", "repos/o/r/releases/tags/dauerzaehlstellen"):
            return json.dumps({"id": 7})
        if args[0] == "api" and "--paginate" in args:
            return json.dumps([[{"name": n, "id": i} for n, i in self.ids.items()]])
        if args[:3] == ("api", "-X", "DELETE"):
            i = int(args[3].rsplit("/", 1)[1])
            name = next(n for n, x in self.ids.items() if x == i)
            (self.ordner / name).unlink()
            del self.ids[name]
            return ""
        if args[:3] == ("api", "-X", "PATCH"):
            i = int(args[3].rsplit("/", 1)[1])
            alt = next(n for n, x in self.ids.items() if x == i)
            neu = args[5].split("=", 1)[1]
            assert neu not in self.ids
            (self.ordner / alt).rename(self.ordner / neu)
            self.ids[neu] = self.ids.pop(alt)
            return ""
        if args[:2] == ("release", "upload"):
            pfad = Path(args[3])
            assert pfad.name not in self.ids, "ohne --clobber: Name schon da"
            self.lege(pfad.name, pfad.read_bytes())
            return ""
        if args[:2] == ("release", "download"):
            name, ziel = args[args.index("--pattern") + 1], Path(args[args.index("--dir") + 1])
            shutil.copyfile(self.ordner / name, ziel / name)
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
    gd.release.aufrufe.clear()
    gd.ablegen("dauerzaehlstellen")
    hochgeladen = [a[3] for a in gd.release.aufrufe if a[:2] == ("release", "upload")]
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
