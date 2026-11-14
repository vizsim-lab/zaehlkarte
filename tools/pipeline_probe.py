"""Die umgestellte Pipeline (Branch robots-pipeline) gegen die echten Portale prüfen – nur Quellen,
die robots.txt auch den Werkzeugen erlaubt (Kennungen samt Claude, tools/robots.py): Olpe (ganz),
Moers (zwei Datensätze), Aachen (Rad), Hamburg (Straßennamen über Overpass, zwei Punkte).

Jeder Abruf der Pipeline wird zusätzlich gegen die Werkzeug-Kennungen geprüft (sonst Abbruch).
Aufruf aus dem Ordner pipeline/ des Branches:
    uv run python /pfad/tools/pipeline_probe.py ZIEL
"""

import json
import pathlib
import sys
import time
import traceback

WERKZEUGE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(WERKZEUGE))
import robots as R  # noqa: E402

from zaehlkarte import abruf, build, fetch  # noqa: E402
from zaehlkarte.config import Pfade, dauerquellen, quellen  # noqa: E402
from zaehlkarte.dauer import bau  # noqa: E402
from zaehlkarte.dauer.strassen import naechste_strassen_overpass  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1]).resolve()
ZIEL.mkdir(parents=True, exist_ok=True)
LOG = []
ABRUFE = []


def log(*z):
    zeile = " ".join(str(x) for x in z)
    print(zeile, flush=True)
    LOG.append(zeile)


_pruefe = abruf.pruefe


def pruefe(url):
    if not R.erlaubt(url):
        raise abruf.Gesperrt(f"für die Werkzeuge gesperrt: {url}")
    R.warte(url)
    _pruefe(url)
    ABRUFE.append(url)


abruf.pruefe = pruefe


def schritt(name, f):
    t0 = time.time()
    try:
        for z in f() or []:
            log(f"[{name}]", z)
    except Exception as e:  # noqa: BLE001
        log(f"[{name}] FEHLER", repr(e))
        log(traceback.format_exc()[-1500:])
    log(f"[{name}] {time.time() - t0:.0f} s")


def kurz():
    q = quellen()
    q["moers"] = {**q["moers"], "pakete": ["verkehrszahlung-kirschenallee",
                                           "verkehrszahlung-in-moers-2021"]}
    return {k: q[k] for k in ("moers", "olpe")}


def kurzzeit():
    fetch.quellen = lambda pfade: kurz()
    zeilen = fetch.hole(Pfade(), ["moers", "olpe"])
    roh = Pfade().roh
    for p in sorted(roh.glob("*/*/paket.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        zeilen.append(f"{p.parent.parent.name}/{p.parent.name}: {d.get('title')!r} "
                      f"Lizenz {d.get('license_url') or d.get('license_id')} "
                      f"{len(d['resources'])} Ressourcen")
        (ZIEL / "pakete").mkdir(exist_ok=True)
        (ZIEL / "pakete" / f"{p.parent.parent.name}__{p.parent.name}.json").write_text(
            p.read_text(encoding="utf-8"))
    return zeilen


def bauen():
    build.quellen = lambda pfade=None, nur_live=True: kurz()
    g = build.baue(nur=["moers", "olpe"])
    z = [f"{c}: {x}" for c, zs in g.berichte.items() for x in zs]
    return z + [f"Stellen: {len(g.stellen)}"]


def aachen():
    log_, fehler = bau.hole(nur=["aachen_rad"])
    roh = Pfade().roh / "aachen_rad"
    return log_ + [f"Fehler: {fehler}", (roh / "abruf.json").read_text(encoding="utf-8")]


def hamburg():
    server = dauerquellen()["hamburg_kfz"]["overpass"]
    treffer, genutzt = naechste_strassen_overpass(server, {
        "a": (10.0050, 53.6004), "b": (9.9937, 53.5511)})
    return [f"Server {genutzt}", json.dumps(treffer, ensure_ascii=False)]


if __name__ == "__main__":
    schritt("kurzzeit", kurzzeit)
    schritt("bauen", bauen)
    schritt("aachen", aachen)
    schritt("hamburg", hamburg)
    for z in abruf.bericht():
        log("[bericht]", z)
    (ZIEL / "log.txt").write_text("\n".join(LOG) + "\n")
    (ZIEL / "abrufe.txt").write_text("\n".join(ABRUFE) + "\n")
    (ZIEL / "robots_texte.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
