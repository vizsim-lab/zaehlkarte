"""Dauerzählstellen Berlin (VIZ): synthetische Archive in beiden Qualitätssicherungen."""

from __future__ import annotations

import gzip
import io
import json
import shutil
import tarfile
from datetime import date

import numpy as np
import openpyxl

from zaehlkarte.config import PIPELINE, Pfade
from zaehlkarte.dauer import berlin_viz as b
from zaehlkarte.dauer import site
from zaehlkarte.dauer.modell import Messreihe, erwartete_stunden, tagessummen, umstellungen

QUELLE = {"code": "berlin_viz", "name": "Berlin (Verkehrsdetektion)", "land": "BE",
          "stammdaten": "Stammdaten_Test.xlsx", "neue_qs_ab": "2025-01",
          "vollstaendig_mindestens": 75, "ferien": "schulferien_berlin.csv",
          "lizenz": "dl-de/by-2-0", "titel": "Verkehrsdetektion Berlin (verändert)"}
KOPF = ["MQ_KURZNAME", "DET_NAME_ALT", "DET_NAME_NEU", "DET_ID15", "MQ_ID15", "STRASSE", "POSITION",
        "POS_DETAIL", "RICHTUNG", "SPUR", "annotation", "LÄNGE (WGS84)", "BREITE (WGS84)",
        "INBETRIEBNAHME", "ABBAUDATUM", "DEINSTALLIERT", "KOMMENTAR"]


def _stammdaten(pfad):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stammdaten_TEU_20220720"
    ws.append(KOPF)
    for det, spur in (("TEU00001_Det0", "HF_R"), ("TEU00001_Det1", "HF_2vR")):
        ws.append(["TE001", det, "", "1", "11", "Clayallee", "in Höhe Haus Nr. 343",
                   "Potsdamer Chaussee", "Süd", spur, f"Spur {spur}", 13.2613, 52.4366,
                   "2003-02-18", None, None, None])
    ws.append(["TE002", "TEU00002_Det0", "", "3", "12", "Clayallee", "in Höhe Haus Nr. 343",
               "Hüttenweg", "Nord", "HF_R", "Hauptfahrbahn rechte Spur", 13.2614, 52.4367,
               "2003-02-18", None, None, None])
    ws.append(["TE002", "TEU00002_Det1", "", "4", "12", "Clayallee", "in Höhe Haus Nr. 343",
               "Hüttenweg", "Nord", "HF_2vR", "Hauptfahrbahn, 2. Spur", 13.2614, 52.4367,
               "2003-02-18", None, "X", "Jetzt Radspur?"])
    pfad.parent.mkdir(parents=True, exist_ok=True)
    wb.save(pfad)


def _alte_qs(pfad, zeilen):
    text = ("mq_name;tag;stunde;qualitaet;q_kfz_mq_hr;v_kfz_mq_hr;q_pkw_mq_hr;v_pkw_mq_hr;"
            "q_lkw_mq_hr;v_lkw_mq_hr\n")
    text += "".join(f"{mq};{tag};{h};1.0;{kfz};50;{kfz - lkw};50;{lkw};40\n"
                    for mq, tag, h, kfz, lkw in zeilen)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(gzip.compress(text.encode()))


def _tgz(pfad, glieder: dict[str, str]):
    pfad.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(pfad, "w:gz") as tf:
        for name, text in glieder.items():
            daten = gzip.compress(text.encode()) if name.endswith(".gz") else text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(daten)
            tf.addfile(info, io.BytesIO(daten))


def _pfade(tmp_path) -> Pfade:
    pfade = Pfade(pipeline=tmp_path / "pipeline", repo=tmp_path)
    pfade.config.mkdir(parents=True)
    shutil.copy(PIPELINE / "config" / "schulferien_berlin.csv", pfade.config)
    return pfade


def _archiv(pfade: Pfade):
    o = pfade.roh / "berlin_viz"
    _stammdaten(o / QUELLE["stammdaten"])
    z = []
    for h in range(24):  # 1.10.: vollständig
        z.append(("TE001", "01.10.2024", h, 100 + h, 10))
    for h in range(24):  # 2.10.: Stunde 5 fehlt
        if h != 5:
            z.append(("TE001", "02.10.2024", h, 200, 20))
    for h in range(24):  # 3.10.: Stunde 7 doppelt mit verschiedenen Werten -> verworfen
        z.append(("TE001", "03.10.2024", h, 300, 30))
    z.append(("TE001", "03.10.2024", 7, 999, 30))
    for h in range(24):  # 4.10.: Stunde 7 doppelt, gleich -> einmal
        z.append(("TE001", "04.10.2024", h, 400, 40))
    z.append(("TE001", "04.10.2024", 7, 400, 40))
    for h in range(24):  # 27.10. (Rückstellung): Stunde 2 zweimal -> beide Stunden
        z.append(("TE001", "27.10.2024", h, 50, 5))
    z.append(("TE001", "27.10.2024", 2, 60, 6))
    z.append(("TE999", "01.10.2024", 8, 1, 0))  # ohne Stammdaten
    _alte_qs(o / "2024/alte_qualitaetssicherung/Messquerschnitte/mq_hr_2024_10.csv.gz", z)

    # neue QS März 2025: zwei Formate, NaN-Zeilen neben den gültigen, 30.3. ohne 2 Uhr
    kopf_a = ("Datum (Ortszeit);Stunde des Tages (Ortszeit);qkfz;qpkw;qlkw;vkfz;vpkw;vlkw;"
              "ZScore_Det0;ZScore_Det1;ZScore_Det2;Datapoints_Rel;hist_cor\n")
    kopf_b = ("datum;stunde;kfz;qpkw;qlkw;vkfz;vpkw;vlkw;zscore_det0;zscore_det1;zscore_det2;"
              "vollstaendigkeit;hist_korr\n")

    def zeilen(tag, stunden, kfz, lkw, voll, format_b=False, nan_davor=True):
        out = ""
        for h in stunden:
            hs = f"{h:02d}" if h % 2 else str(h)  # Stunden mal „7“, mal „07“
            if nan_davor:
                out += f"{tag};{hs};NaN;NaN;NaN;NaN;NaN;NaN;NaN;NaN;NaN;0.00;NaN\n"
            v = voll(h) if callable(voll) else voll
            out += f"{tag};{hs};{kfz};{kfz - lkw};{lkw};50;50;40;0;0;0;{v};0.9\n"
        return out

    det0 = kopf_a + zeilen("2025-03-03", range(24), 100, 10, "1.00") \
        + zeilen("2025-03-04", range(24), 100, 10, "1.00") \
        + zeilen("2025-03-30", [h for h in range(24) if h != 2], 100, 10, "1.00")
    det1 = kopf_b + zeilen("2025-03-03", range(24), 50, 5, "100.00", nan_davor=False) \
        + zeilen("2025-03-04", range(24), 50, 5, lambda h: "50.00" if h == 7 else "100.00",
                 nan_davor=False) \
        + zeilen("2025-03-30", [h for h in range(24) if h != 2], 50, 5, "100.00", nan_davor=False)
    det2 = kopf_a + zeilen("2025-03-03", range(24), 70, 7, "1.00")
    det3 = kopf_a + zeilen("2025-03-03", range(24), 45, 0, "1.00")  # deinstalliert (Radspur)
    _tgz(o / "2025/neue_qualitaetssicherung/Fahrstreifendetektoren/detektor_2025_03.tgz",
         {"2025_03/TEU00001_Det0.csv": det0, "2025_03/TEU00001_Det1.csv.gz": det1,
          "2025_03/TEU00002_Det0.csv": det2, "2025_03/TEU00002_Det1.csv": det3})
    # neue QS auch für Oktober 2024 (nur zum Vergleich): TE001 am 1.10. gleich
    vgl0 = kopf_a + "".join(f"2024-10-01;{h};{60 + h};0;6;50;50;40;0;0;0;1.00;0.9\n"
                            for h in range(24))
    vgl1 = kopf_a + "".join(f"2024-10-01;{h};40;0;4;50;50;40;0;0;0;1.00;0.9\n" for h in range(24))
    _tgz(o / "2024/neue_qualitaetssicherung/Fahrstreifendetektoren/detektoren_2024_10.tgz",
         {"TEU00001_Det0.csv": vgl0, "TEU00001_Det1.csv": vgl1})


def test_umstellungen_und_erwartete_stunden():
    assert umstellungen(2025) == (date(2025, 3, 30), date(2025, 10, 26))
    erwartet = erwartete_stunden(date(2025, 3, 29), 3)
    assert erwartet.sum(axis=1).tolist() == [24, 23, 24]
    assert not erwartet[1, 2]


def test_stammdaten(tmp_path):
    pfad = tmp_path / "s.xlsx"
    _stammdaten(pfad)
    sd = b.lies_stammdaten(pfad, QUELLE)
    assert [s.kennung for s in sd.stellen] == ["TE001", "TE002"]
    te2 = sd.stellen[1]
    assert te2.richtung == "Richtung Hüttenweg (Nord)"
    assert te2.fahrstreifen == ["Hauptfahrbahn rechte Spur"]
    assert any("deinstalliert" in h for h in te2.hinweise)
    assert sd.deinstalliert == {"TEU00002_Det1"}
    assert sd.stellen[0].id == "berlin_viz:TE001"


def test_lese_beide_verfahren(tmp_path):
    pfade = _pfade(tmp_path)
    _archiv(pfade)
    bericht = b.Bericht()
    r = b.lese(QUELLE, pfade, bericht)
    assert r.von == date(2024, 10, 1) and r.tag(r.tage - 1) == date(2025, 3, 31)
    kfz, n = tagessummen(r, "kfz")
    lkw, _ = tagessummen(r, "lkw")
    t = r.index
    assert kfz[0, t(date(2024, 10, 1))] == sum(100 + h for h in range(24))
    assert lkw[0, t(date(2024, 10, 1))] == 240
    assert kfz[0, t(date(2024, 10, 2))] == -1 and n[0, t(date(2024, 10, 2))] == 23
    assert kfz[0, t(date(2024, 10, 3))] == -1  # widersprüchliche Stunde verworfen
    assert kfz[0, t(date(2024, 10, 4))] == 24 * 400
    assert kfz[0, t(date(2024, 10, 27))] == 24 * 50 + 60  # 25 Stunden
    assert r.doppelt[0, t(date(2024, 10, 27))]
    assert bericht.widerspruch == 1
    assert bericht.unbekannt == {"TE999": 1}
    # neue QS: Fahrstreifen summiert, 50 %-Stunde macht den Tag unvollständig
    assert kfz[0, t(date(2025, 3, 3))] == 24 * 150
    assert lkw[0, t(date(2025, 3, 3))] == 24 * 15
    assert kfz[0, t(date(2025, 3, 4))] == -1 and n[0, t(date(2025, 3, 4))] == 23
    assert kfz[0, t(date(2025, 3, 30))] == 23 * 150  # Sommerzeit-Beginn: 23 Stunden
    # TE002: der deinstallierte Detektor zählt nicht mit, auch wenn er Werte liefert
    assert kfz[1, t(date(2025, 3, 3))] == 24 * 70
    assert bericht.deinstalliert_neu == 24
    assert bericht.unvollstaendig_neu == 1
    # Vergleich Oktober 2024: TE001 am 1.10. in beiden gleich (24 Stunden)
    assert bericht.vergleich["beide"] == 24 and bericht.vergleich["gleich"] == 24
    assert [v[2][:4] for v in r.verfahren] == ["alte", "neue"]
    assert any("Vergleich alte/neue QS" in z for z in bericht.zeilen())


def test_site_schreibt_vertrag(tmp_path):
    pfade = _pfade(tmp_path)
    _archiv(pfade)
    r = b.lese(QUELLE, pfade, b.Bericht())
    dateien, bericht = site.schreibe([(QUELLE, r)], pfade, erzeugt=date(2026, 11, 12))
    ziel = pfade.karte / "dauer"
    index = json.loads((ziel / "index.json").read_text())
    assert index["stellen"]["felder"] == site.STELLEN_FELDER
    assert index["dateien"] == {"tage": "dauer/tage/{jahr}.json", "details": "dauer/{n}.json"}
    assert index["von"] == "2024-10-01" and index["bis"] == "2025-03-31"
    assert len(index["kalender"]["BE"]) == (date(2025, 3, 31) - date(2024, 10, 1)).days + 1
    assert index["kalender"]["BE"][2] == "h"  # 3.10. Tag der Deutschen Einheit
    # Standardtag: jüngster Schultag mit fast so vielen vollständigen Stellen wie am besten Tag
    assert index["standardtag"] == "2025-03-03"
    assert index["quellen"][0]["verfahren"][-1]["von"] == "2025-03-01"
    felder = index["stellen"]["felder"]
    werte = {w[0]: dict(zip(felder, w, strict=True)) for w in index["stellen"]["werte"]}
    assert set(werte) == {"berlin_viz:TE001", "berlin_viz:TE002"}
    assert werte["berlin_viz:TE001"]["von"] == "2024-10-01"
    assert werte["berlin_viz:TE002"]["g"] == 3  # kfz und lkw
    jahr = json.loads((ziel / "tage" / "2024.json").read_text())
    assert jahr["tage"] == 366 and len(jahr["werte"]["kfz"][0]) == 366
    i = [w[0] for w in index["stellen"]["werte"]].index("berlin_viz:TE001")
    tag = (date(2024, 10, 1) - date(2024, 1, 1)).days
    assert jahr["werte"]["kfz"][i][tag] == sum(100 + h for h in range(24))
    assert jahr["werte"]["kfz"][i][tag + 1] is None  # unvollständig, nie 0
    chunk = json.loads((ziel / f"{werte['berlin_viz:TE001']['chunk']}.json").read_text())
    d = chunk["stellen"]["berlin_viz:TE001"]
    assert d["von"] == "2024-10-01" and d["n"][1] == 23
    assert d["doppelt"] == ["2024-10-27"]
    assert d["stunden_von"] == "2024-10-01"  # weniger als 12 Monate: alles
    assert d["stunden"]["kfz"][0][:3] == [100, 101, 102]
    assert d["stunden"]["kfz"][1][5] is None
    assert any("Stellen mit vollständigen Tagen" in z for z in bericht)
    assert np.all([p.exists() for p in dateien])


def test_messreihe_leer():
    r = Messreihe.leer("x", date(2025, 1, 1), date(2025, 1, 31), [])
    assert r.werte["kfz"].shape == (0, 31, 24)
