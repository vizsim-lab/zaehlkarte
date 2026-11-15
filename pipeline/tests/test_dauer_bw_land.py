"""Baden-Württemberg, Dauerzählstellen des Landes (BASt-Bestandsband als CSV, MobiData BW): Abruf
nach Datum der Ressourcen, Köpfe beider Formate (bis 2025 und ab 2026), Fahrstreifen je Richtung,
Prüfkennzeichen und Statuskennung, Zeitumstellung, Kodierung, doppelte Dateien, Lage aus der
Zählstellenkarte und der Vertrag von dauer/."""

from __future__ import annotations

import csv
import io
import json
import shutil
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

import zaehlkarte.ckan
import zaehlkarte.fetch
from zaehlkarte.config import Pfade
from zaehlkarte.dauer import bw_land as bw
from zaehlkarte.dauer import site
from zaehlkarte.dauer.modell import tagessummen
from zaehlkarte.kalender import FERIEN

VM = "https://mobidata.example/vm/Stundenwerte_Dauerzaehlstellen_BW"
Q = {
    "code": "bw_land_kfz", "name": "Baden-Württemberg (Kfz, Dauerzählstellen des Landes)",
    "land": "BW", "adapter": "bw_land", "portal_basis": "https://mobidata.example",
    "datensatz": "stundenwerte_dauerzaehlstellen", "ab": "2025-01",
    "archiv": {"von": 2024, "bis": 2024, "url": VM + "/Stundenwerte_{jahr}.zip"},
    "karte": {"datensatz": "karte_strassenverkehrszaehlung",
              "muster": "SVZ-Zaehlstellen_.*\\.csv$"},
    "lizenz": "dl-de/by-2-0", "lizenz_url": "https://www.govdata.de/dl-de/by-2-0",
}
KARTE = "\n".join([
    "svznr,zstart,klasse,nummer,gpsx1,gpsy1,RI,RII,DTV2024,DTVSV",
    "78141201,DZ,L,173,8.03,48.11,B294/L 173/K5109 Gutach,K5105 Obersimonswald,5000,200",
    "78141209,TM,L,173,8.05,48.10,K5105 Obersimonswald,L 173 Kandel,3000,100",
    "62221200,TM,L,508,9.474958,49.742579,Einmündung K2830 in L 508,Einm. K 2829 in L 508,6626,253",
    "62221202,DZ,L,2310,9.508385000000004,49.772387000000016,"
    'Einm. K2879 in L2310 bei Wessental,"Einm. L 508 \\""Sägmühle\\""",3729,261',
    "64161001,MZ,A,6,8.47,49.55,AS Mannheim-Sandhofen (5),AS Viernheim (6),95000,14000",
    "79121102,DZ,B,31,7.80,48.02,B31A/L116 Umkirch,AS Freiburg-Mitte,30000,1500",
    "79121103,DZ,B,31,7.78,48.03,AS March West,B31A/L116 Umkirch,28000,1400",
]) + "\n"
KLASSEN = ["Mot", "Pkw", "Lfw", "PmA", "Bus", "LoA", "LmA", "Sat", "So"]


class Stelle:
    """Eine Zählstelle im Format der Quelle; `alt`: Kopf wie bis 2025 (Nullen vorn, ein
    Fernziel), sonst wie ab 2026."""

    def __init__(self, tk, nr, klasse, strasse, name, n1, n2, gruppen, ziele):
        self.tk, self.nr, self.klasse, self.strasse, self.name = tk, nr, klasse, strasse, name
        self.n1, self.n2, self.gruppen, self.ziele = n1, n2, gruppen, ziele

    def kopf(self, alt: bool) -> list[str]:
        z1, h1, z2, h2 = self.ziele
        acht = len(self.gruppen) == 2 and self.gruppen[1] == "SV"
        if alt:
            k1 = f"{self.tk};{self.nr};08;{self.klasse};{self.strasse};{self.name:<25};;;"
            k2 = f"{self.n1:02d};{self.n2:02d};{z2};{h1};;{h2};;;"  # nur ein Fernziel
            k3 = "02;09;KFZ;SV;" + ";".join(KLASSEN) if acht else "02;00;KFZ;LK;;;"
        else:
            k1 = f"{self.tk};{self.nr};8;{self.klasse};{self.strasse};{self.name:<25};;;"
            k2 = f"{self.n1};{self.n2};{z1};{h1};{z2};{h2};;;"
            k3 = "2;9;KFZ;SV;" + ";".join(KLASSEN) if acht else "2;0;KFZ;LK;;;"
        spuren = range(1, self.n1 + self.n2 + 1)
        spalten = ["Datum", "Uhrzeit"]
        spalten += [x for s in spuren for g in self.gruppen for x in (f"{g}FS{s}", f"K_{g}FS{s}")]
        if acht:
            spalten += [x for s in spuren for k in KLASSEN for x in (f"{k}FS{s}", f"K_{k}FS{s}")]
        return [k1, k2, k3, ";".join(spalten) + ";"]

    def zeile(self, tag: date, stunde: int, werte: list[int], kennung="-", status="",
              kennungen: dict[int, str] | None = None) -> str:
        """Eine Stundenzeile: `werte` je Fahrstreifen (Kfz; SV bzw. LK = ein Zehntel),
        `kennungen` je Fahrstreifen (Index ab 0) abweichend von `kennung`."""
        kennungen = kennungen or {}
        felder = [tag.strftime("%y%m%d") + status, f"{stunde:02d}:00"]
        for s, w in enumerate(werte):
            k = kennungen.get(s, kennung)
            felder += [str(w), k, str(w // 10), k]
        if self.gruppen[1] == "SV":
            felder += [x for _ in werte for _ in KLASSEN for x in ("0", "-")]
        return ";".join(felder)

    def monat(self, jahr: int, monat: int, wert, alt=True, besonders=None) -> str:
        """Ganzer Monat: `wert(tag, stunde)` -> Werte je Fahrstreifen; `besonders[(tag, stunde)]`
        -> fertige Zeile statt der normalen."""
        besonders = besonders or {}
        zeilen = self.kopf(alt)
        tag = date(jahr, monat, 1)
        while tag.month == monat:
            for h in range(1, 25):
                zeilen.append(besonders.get((tag, h)) or self.zeile(tag, h, wert(tag, h)))
            tag += timedelta(days=1)
        return "\r\n".join(zeilen) + "\r\n"


ROSEN = Stelle("6222", "8202", "L", "2310", "Rosenmühle", 1, 1, ["KFZ", "SV"],
               ("Wertheim", "N", "Miltenberg", "S"))
# 2026 mit anderem Kartenblatt (wie der Kappelberg-Tunnel): dieselbe Zählstelle
ROSEN26 = Stelle("6223", "8202", "L", "2310", "Rosenmühle", 1, 1, ["KFZ", "SV"],
                 ("Wertheim", "N", "Miltenberg", "S"))
A6 = Stelle("6416", "8161", "A", "6", "Mannheim-Sandhöfen", 2, 2, ["KFZ", "LK"],
            ("Kaiserslautern", "O", "Frankfurt", "W"))  # ö: Windows-1252 im ZIP
OHNE = Stelle("7216", "8491", "B", "462", "Weisenbach-Au", 1, 1, ["KFZ", "SV"],
              ("Rastatt", "N", "Freudenstadt", "S"))


def zip_bytes(dateien: dict[str, bytes]) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for name, inhalt in dateien.items():
            z.writestr(name, inhalt)
    return puffer.getvalue()


def quelle_bauen() -> dict[str, bytes]:
    """Die Dateien der Quelle: Archiv 2024 (ZIP aus Monats-ZIPs, Oktober mit Rückstellung),
    März 2025 (Sommerzeit, Kennzeichen, doppelte Datei, cp1252, Stelle ohne Lage) und März 2026
    (neues Format, eingefügte Zeilen, Kennzeichen h)."""
    def ros(tag, h):
        return [10, 10]  # je Richtung ein Fahrstreifen

    okt = ROSEN.monat(2024, 10, ros, besonders={
        (date(2024, 10, 27), 3): ROSEN.zeile(date(2024, 10, 27), 3, [10, 10], kennung="z")})
    archiv = zip_bytes({"Stundenwerte_202410.zip": zip_bytes(
        {"Stundenwerte_202410/BW_62221202_2410.csv": okt.encode()})})
    maerz = ROSEN.monat(2025, 3, ros, besonders={
        (date(2025, 3, 30), 3): ROSEN.zeile(date(2025, 3, 30), 3, [0, 0], kennung="z"),
        (date(2025, 3, 3), 8): ROSEN.zeile(date(2025, 3, 3), 8, [10, 10], kennungen={0: "s"}),
        (date(2025, 3, 4), 8): ROSEN.zeile(date(2025, 3, 4), 8, [50, 50], kennung="u"),
    })
    a6 = A6.monat(2025, 3, lambda tag, h: [100, 50, 70, 30], besonders={
        (date(2025, 3, 5), 12): A6.zeile(date(2025, 3, 5), 12, [100, 50, 70, 30],
                                         kennungen={3: "a"}),  # nur Richtung II ausgefallen
    })
    monat_2503 = zip_bytes({
        "Stundenwerte_202503/BW_62221202_2503.csv": maerz.encode(),
        "Stundenwerte_202503/BW_62228202_2503.csv": maerz.encode(),  # dieselbe, zweiter Name
        "Stundenwerte_202503/BW_64161001_2503.csv": a6.encode("cp1252"),
        "Stundenwerte_202503/BW_72161100_2503.csv": OHNE.monat(2025, 3, ros).encode(),
    })
    neu = ROSEN26.monat(2026, 3, ros, alt=False, besonders={
        (date(2026, 3, 29), 3): ROSEN.zeile(date(2026, 3, 29), 3, [0, 0], kennung="z",
                                            status="i"),
        (date(2026, 3, 10), 5): ROSEN.zeile(date(2026, 3, 10), 5, [10, 10], kennung="t",
                                            status="i"),
        (date(2026, 3, 11), 6): ROSEN.zeile(date(2026, 3, 11), 6, [10, 10], kennung="h"),
    })
    monat_2603 = zip_bytes({"Stundenwerte_202603/BW_62228202_2603.csv": neu.encode()})
    return {VM + "/Stundenwerte_2024.zip": archiv, VM + "/Stundenwerte_202503.zip": monat_2503,
            VM + "/Stundenwerte_202603.zip": monat_2603,
            "https://mobidata.example/vm/Karte/SVZ-Zaehlstellen_2026-06-26.csv": KARTE.encode()}


@pytest.fixture
def pfade(tmp_path: Path) -> Pfade:
    p = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    p.config.mkdir(parents=True, exist_ok=True)
    return p


def portal(monkeypatch, dateien: dict[str, bytes], stand: dict[str, str] | None = None
           ) -> list[str]:
    """DCAT-Dokumente und Downloads vortäuschen; -> Liste der geladenen URLs."""
    stand = stand or {}
    geladen: list[str] = []

    def paket(basis, name, wege=("dcat", "html")):
        assert basis == Q["portal_basis"] and wege == ("dcat",)
        res = [{"url": u, "last_modified": stand.get(u, "2026-10-19T12:57:10")} for u in dateien]
        res.append({"url": VM + "/Stundenwerte_Archiv.zip", "last_modified": "2026-07-01"})
        # vor `ab`: nicht geholt
        res.append({"url": VM + "/Stundenwerte_202412.zip", "last_modified": "2026-01-01"})
        if name == Q["datensatz"]:
            return {"resources": [r for r in res if "Karte" not in r["url"]]}
        assert name == Q["karte"]["datensatz"]
        return {"resources": [r for r in res if "Karte" in r["url"]]
                + [{"url": "https://mobidata.example/vm/Karte/Methodik.pdf"}]}

    def lade(url, ziel):
        geladen.append(url)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_bytes(dateien[url])
        return ziel

    monkeypatch.setattr(zaehlkarte.ckan, "paket", paket)
    monkeypatch.setattr(zaehlkarte.fetch, "lade", lade)
    return geladen


def test_hole_nach_datum_der_ressourcen(pfade, monkeypatch):
    dateien = quelle_bauen()
    geladen = portal(monkeypatch, dateien)
    log = bw.hole(Q, pfade)
    assert sorted(geladen) == sorted(dateien) and log[0].startswith("bw_land_kfz: 4 Dateien")
    ordner = pfade.roh / "bw_land_kfz"
    assert sorted(p.name for p in ordner.iterdir()) == [
        "abruf.json", "jahr_2024.zip", "karte.csv", "monat_202503.zip", "monat_202603.zip"]
    # unverändert: nichts neu; geändertes Datum eines Monats: nur der
    geladen.clear()
    assert bw.hole(Q, pfade)[0].startswith("bw_land_kfz: 0 Dateien geladen, 4 unverändert")
    geladen = portal(monkeypatch, dateien, {VM + "/Stundenwerte_202503.zip": "2026-11-01"})
    bw.hole(Q, pfade)
    assert geladen == [VM + "/Stundenwerte_202503.zip"]


def test_lese(pfade, monkeypatch):
    portal(monkeypatch, quelle_bauen())
    bw.hole(Q, pfade)
    b = bw.Bericht()
    r = bw.lese(Q, pfade, b)
    # Kennung: Zählstellennummer und Richtung (das Kartenblatt wechselt bei manchen Stellen)
    assert [s.id for s in r.stellen] == ["bw_land_kfz:8161-1", "bw_land_kfz:8161-2",
                                         "bw_land_kfz:8202-1", "bw_land_kfz:8202-2"]
    a61, a62, ros1, ros2 = r.stellen
    assert (ros1.name, ros1.lon, ros1.lat) == ("L 2310 Rosenmühle", 9.508385, 49.772387)
    assert ros1.abschnitt == 'Einm. K2879 in L2310 bei Wessental – Einm. L 508 "Sägmühle"'
    # Fernziele aus dem jüngsten Kopf (2026: beide), sonst nur die Himmelsrichtung
    assert (ros1.richtung, ros2.richtung) == ("Richtung Wertheim (Norden)",
                                              "Richtung Miltenberg (Süden)")
    assert (a61.name, a61.richtung, a62.richtung) == ("A 6 Mannheim-Sandhöfen", "Richtung Osten",
                                                      "Richtung Westen")
    assert (a61.lon, a61.lat) == (a62.lon, a62.lat) == (8.47, 49.55)
    assert set(r.werte) == {"kfz", "lkw", "sv"}
    assert b.ohne_lage == ["B 462 Weisenbach-Au (8491)"] and b.stellen == 3
    assert b.gleich == 1 and not b.doppelt and b.cp1252 == 1
    assert dict(b.lage) == {"DZ (Dateiname)": 1, "MZ (Dateiname)": 1}

    kfz, n = tagessummen(r, "kfz")
    sv, _ = tagessummen(r, "sv")
    lkw, _ = tagessummen(r, "lkw")
    t = r.index
    R1, R2 = 2, 3  # Rosenmühle, Richtung I und II
    assert r.von == date(2024, 10, 1) and r.tag(r.tage - 1) == date(2026, 3, 31)
    assert kfz[R1, t(date(2025, 3, 1))] == 240 and sv[R1, t(date(2025, 3, 1))] == 24
    assert kfz[R1, t(date(2025, 3, 3))] == -1 and n[R1, t(date(2025, 3, 3))] == 23  # „s“
    assert kfz[R2, t(date(2025, 3, 3))] == 240  # die andere Richtung ist gezählt
    assert kfz[R1, t(date(2025, 3, 4))] == 23 * 10 + 50  # „u“ zählt
    assert kfz[R1, t(date(2025, 3, 30))] == 230 and n[R1, t(date(2025, 3, 30))] == 23  # Sommerzeit
    assert b.sommerzeit > 0
    # Rückstellung: 2–3 Uhr nur einmal, mit „z“ -> nicht vollständig
    assert kfz[R1, t(date(2024, 10, 27))] == -1 and n[R1, t(date(2024, 10, 27))] == 23
    assert kfz[R1, t(date(2024, 10, 26))] == 240
    # 2026 (anderes Blatt, dieselbe Stelle): eingefügte Zeile („i“) und „h“ -> nicht gezählt;
    # die Sommerzeit-Zeile ab 2026 mit „i“
    assert kfz[R1, t(date(2026, 3, 10))] == -1 and kfz[R1, t(date(2026, 3, 11))] == -1
    assert kfz[R1, t(date(2026, 3, 29))] == 230 and kfz[R1, t(date(2026, 3, 12))] == 240
    # A 6: Richtung I = Fahrstreifen 1+2, II = 3+4; LK als lkw, kein SV; Ausfall nur in II
    assert kfz[0, t(date(2025, 3, 1))] == 24 * 150 and kfz[1, t(date(2025, 3, 1))] == 24 * 100
    assert lkw[0, t(date(2025, 3, 1))] == 24 * (10 + 5) and (sv[:2] == -1).all()
    assert kfz[0, t(date(2025, 3, 5))] == 24 * 150 and kfz[1, t(date(2025, 3, 5))] == -1
    assert (lkw[2:] == -1).all() and (kfz[:2, t(date(2026, 3, 1))] == -1).all()
    assert b.kennungen[("KFZ", "s")] == 1 and b.kennungen[("LK", "a")] == 1
    assert b.eingefuegt == 2
    assert any("Weisenbach" in z for z in b.zeilen())


def test_verschiedene_dateien_einer_stelle_im_monat(pfade, monkeypatch):
    dateien = quelle_bauen()
    with zipfile.ZipFile(io.BytesIO(dateien[VM + "/Stundenwerte_202503.zip"])) as z:
        inhalt = {n: z.read(n) for n in z.namelist()}
    zweite = "Stundenwerte_202503/BW_62228202_2503.csv"
    inhalt[zweite] = inhalt[zweite].replace(b";10;-;1;-;", b";11;-;1;-;", 1)
    dateien[VM + "/Stundenwerte_202503.zip"] = zip_bytes(inhalt)
    portal(monkeypatch, dateien)
    bw.hole(Q, pfade)
    b = bw.Bericht()
    r = bw.lese(Q, pfade, b)
    kfz, _ = tagessummen(r, "kfz")
    assert b.doppelt == ["8202 202503 (BW_62221202_2503.csv, BW_62228202_2503.csv)"]
    assert (kfz[2, r.index(date(2025, 3, 1)):r.index(date(2025, 3, 31)) + 1] == -1).all()
    assert kfz[2, r.index(date(2026, 3, 1))] == 240


def test_ordne_lage():
    """Abschnitte von Dauerzählstellen zuerst, dann der häufigste; jeder Abschnitt einmal; die
    Straße muss passen (Nummer ohne Buchstaben); nie TM. Ohne Kandidaten: der einzige freie
    DZ-Abschnitt der Straße auf dem Blatt der Stelle, den keine andere Stelle ebenso will."""
    karte = {z["svznr"]: z for z in csv.DictReader(io.StringIO(KARTE))}
    meta = {"8538": {"klasse": "B", "nummer": "31a", "blatt": "7912"},  # March-Umkirch Ost
            "8537": {"klasse": "B", "nummer": "31A", "blatt": "7912"},  # March-Umkirch West
            "8202": {"klasse": "L", "nummer": "2310", "blatt": "6222"},
            "8237": {"klasse": "L", "nummer": "173", "blatt": "7814"},  # Simonswald
            "8999": {"klasse": "L", "nummer": "508", "blatt": "6222"}}
    kandidaten = {
        "8538": {"79121102": (120, "202510"), "64161001": (5, "202608")},
        "8537": {"79121103": (120, "202510"), "79121102": (5, "202608")},
        "8202": {"62221200": (200, "202608")},  # TM an einer anderen Straße
        "8237": {"78141204": (128, "202608"), "78141209": (3, "202601")},  # fehlt bzw. TM
        "8999": {"62221200": (100, "202608")},  # TM derselben Straße: nie
    }
    assert bw.ordne_lage(kandidaten, meta, karte) == {
        "8538": ("79121102", "Dateiname"), "8537": ("79121103", "Dateiname"),
        "8237": ("78141201", "Straße und Kartenblatt"),
        "8202": ("62221202", "Straße und Kartenblatt")}  # einziger freier DZ der L 2310
    # zwei Stellen wollen denselben freien Abschnitt: keine bekommt ihn
    meta["8238"] = dict(meta["8237"])
    kandidaten["8238"] = {}
    lage = bw.ordne_lage(kandidaten, meta, karte)
    assert "8237" not in lage and "8238" not in lage


def test_strasse_und_richtung():
    assert bw.strasse("L", "2310") == "L 2310" and bw.strasse("B", "31A") == "B 31a"
    assert bw.strasse("G", "0") == "" and bw.strasse("A", "06") == "A 6"
    assert bw.richtung(["1", "1", "Wertheim", "N", "Miltenberg", "S"], 2) == \
        "Richtung Miltenberg (Süden)"
    assert bw.richtung(["01", "01", "Miltenberg", "N", "", "S"], 1) == "Richtung Norden"
    assert bw.richtung(["01", "01", "", "", "", ""], 1) is None


def test_site(pfade, monkeypatch):
    portal(monkeypatch, quelle_bauen())
    bw.hole(Q, pfade)
    r = bw.lese(Q, pfade, bw.Bericht())
    (pfade.config / FERIEN).mkdir(parents=True)
    shutil.copyfile(Pfade().config / FERIEN / "BW.csv", pfade.config / FERIEN / "BW.csv")
    site.schreibe([(Q, r)], pfade, date(2026, 11, 15))
    index = json.loads((pfade.karte / "dauer" / "index.json").read_text())
    assert index["gruppen"] == ["kfz", "lkw", "sv"]
    q = index["quellen"][0]
    assert q["gruppen"] == ["kfz", "lkw", "sv"] and q["lizenzen"][0]["lizenz"] == "dl-de/by-2-0"
    felder = index["stellen"]["felder"]
    stellen = [dict(zip(felder, w, strict=True)) for w in index["stellen"]["werte"]]
    assert [s["id"] for s in stellen] == ["bw_land_kfz:8161-1", "bw_land_kfz:8161-2",
                                          "bw_land_kfz:8202-1", "bw_land_kfz:8202-2"]
    assert stellen[2]["richtung"] == "Richtung Wertheim (Norden)"
    # Bits: kfz 1, lkw 2, sv 4 (Reihenfolge von `gruppen`)
    assert [s["g"] for s in stellen] == [3, 3, 5, 5]
