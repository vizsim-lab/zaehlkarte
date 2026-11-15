"""VG250 des BKG erkunden (15.11.2026, für die Gemeinde je Dauerzählstelle, Branch `gemeinden`):
robots.txt, Verzeichnisse, Download, Prüfsumme, Ebenen und Felder; dann die Stellen des aktuellen
Release-Assets (und die Kurzzeit-Stellen) mit `zaehlkarte.gemeinden` des App-Branches den Gemeinden
zuordnen und je Quelle mit der Datenlage vergleichen.

Aufruf aus app/pipeline: uv run python tools/vg250_erkunden.py <ziel> <dauer/index.json> <index.json>
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from zaehlkarte import abruf
from zaehlkarte import gemeinden as gm
from zaehlkarte.config import konfiguration

ziel = Path(sys.argv[1])
ziel.mkdir(parents=True, exist_ok=True)
dauer_index = Path(sys.argv[2])
kurz_index = Path(sys.argv[3])
zeilen: list[str] = []


def p(*teile) -> None:
    s = " ".join(str(t) for t in teile)
    print(s, flush=True)
    zeilen.append(s)


def sichern() -> None:
    (ziel / "bericht.txt").write_text("\n".join(zeilen) + "\n", encoding="utf-8")


BASIS = "https://daten.gdz.bkg.bund.de/produkte/vg/"
for host in ("https://daten.gdz.bkg.bund.de", "https://gdz.bkg.bund.de"):
    try:
        status, text = abruf._robots_text(host)
        p(f"robots.txt {host}: HTTP {status}, {len(text)} Zeichen")
        (ziel / f"robots_{host.split('//')[1]}.txt").write_text(text, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        p(f"robots.txt {host}: {e!r}")

listen: dict[str, list[str]] = {}
for pfad in ("", "vg250_ebenen_0101/", "vg250_ebenen_0101/aktuell/", "vg250_ebenen_0101/2026/",
             "vg250_ebenen_0101/2025/", "vg250_ebenen_1231/"):
    url = BASIS + pfad
    try:
        print("erlaubt" if abruf.regeln(url).erlaubt(url) else "GESPERRT", url)
        r = abruf.hole(url, timeout=60)
        namen = [n for n in re.findall(r'href="([^"?#]+)"', r.text) if not n.startswith("/")]
        listen[pfad] = namen
        p(f"{url}: HTTP {r.status_code}: {namen[:60]}")
        (ziel / f"liste_{pfad.strip('/').replace('/', '_') or 'vg'}.html").write_text(
            r.text, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        p(f"{url}: {e!r}")
sichern()

kandidaten = []
for ordner in ("vg250_ebenen_0101/2026/", "vg250_ebenen_0101/aktuell/", "vg250_ebenen_0101/2025/"):
    for n in listen.get(ordner, []):
        if "geo84" in n and "shape" in n and n.endswith(".zip"):
            kandidaten.append(BASIS + ordner + n)
p("Kandidaten:", kandidaten)
if not kandidaten:
    sichern()
    sys.exit(0)
url = kandidaten[0]
datei = Path("/tmp") / Path(url).name
t0 = time.time()
abruf.lade(url, datei)
summe = hashlib.sha256(datei.read_bytes()).hexdigest()
p(f"geladen {url}: {datei.stat().st_size / 1e6:.1f} MB in {time.time() - t0:.0f} s, sha256 {summe}")
with zipfile.ZipFile(datei) as z:
    namen = z.namelist()
    p(f"{len(namen)} Dateien im ZIP:", [n for n in namen if "GEM" in n.upper() or n.endswith(".txt")
                                        or n.endswith(".pdf")][:40])
    for n in namen:
        if n.upper().endswith(("VG250_GEM.PRJ", "VG250_GEM.CPG")) or n.endswith(
                ("aktualitaet.txt", "quellenvermerk.txt", "copyright.txt")):
            p(f"--- {n}:", z.read(n)[:600].decode("latin-1"))
        if n.upper().endswith("VG250_GEM.DBF"):
            d = z.read(n)
            felder, pos = [], 32
            while d[pos] != 0x0D:
                felder.append(d[pos:pos + 11].split(b"\0", 1)[0].decode("ascii"))
                pos += 32
            p("Felder VG250_GEM:", felder)
sichern()

t0 = time.time()
g = gm.lese_zip(datei, {"stand": "?"})
p(f"gelesen: {len(g.ags)} Flächen, {len(set(g.ags))} Schlüssel, Land {int(g.land.sum())}, "
  f"Punkte {sum(len(r) for ringe in g.ringe for r in ringe)}, {time.time() - t0:.1f} s")
for a in ("11000000", "02000000", "05515000", "08436064", "03355031", "14612000"):
    p(f"  {a}: {g.name(a)}")
sichern()

cfg = konfiguration()
kommunen = {e["ags"]: e for e in cfg["datenlage"]}
an: dict[str, list[str]] = defaultdict(list)  # Dauer-Quelle -> Kommunen
for e in cfg["datenlage"]:
    for q in (e.get("dauer") or {}).get("quellen") or []:
        an[q].append(e["ags"])
ebene = {c for c, q in cfg["dauer"].items() if q.get("ebene")}

d = json.loads(dauer_index.read_text())
f = d["stellen"]["felder"]
stellen = [dict(zip(f, w, strict=False)) for w in d["stellen"]["werte"]]
t0 = time.time()
for s in stellen:
    s["ags"], s["art"] = g.finde(s["lon"], s["lat"])
p(f"\nDauer: {len(stellen)} Stellen zugeordnet in {time.time() - t0:.1f} s: "
  f"{Counter(s['art'] for s in stellen)}")
(ziel / "zuordnung_dauer.json").write_text(json.dumps(
    {s["id"]: [s["ags"], s["art"]] for s in stellen}, ensure_ascii=False, indent=0))

je_quelle: dict[str, list[dict]] = defaultdict(list)
for s in stellen:
    je_quelle[s["quelle"]].append(s)
for code, ss in je_quelle.items():
    arten = Counter(s["art"] for s in ss)
    ks = an.get(code, [])
    art = "Land/Bund" if code in ebene else ("eine Kommune" if len(ks) == 1 else f"{len(ks)} Kommunen")
    p(f"\n{code} ({art}): {len(ss)} Stellen, {dict(arten)}")
    for s in ss:
        if s["art"] != "innen":
            p(f"    {s['art']}: {s['id']} {s['name']!r} -> {s['ags']} {g.name(s['ags']) if s['ags'] else ''}")
    if len(ks) == 1:
        k = ks[0]
        drin = [s for s in ss if s["ags"] and s["ags"].startswith(k)]
        p(f"  in {kommunen[k]['name']} ({k}): {len(drin)} von {len(ss)}")
        for s in ss:
            if not (s["ags"] and s["ags"].startswith(k)):
                p(f"    außerhalb: {s['id']} {s['name']!r} -> {s['ags']} "
                  f"{g.name(s['ags']) if s['ags'] else ''} ({s['art']})")
    elif ks:
        for k in ks:
            n = sum(1 for s in ss if s["ags"] and s["ags"].startswith(k))
            p(f"  {kommunen[k]['name']} ({k}): {n}")
        frei = [s for s in ss if not any(s["ags"] and s["ags"].startswith(k) for k in ks)]
        p(f"  in keiner verknüpften Kommune: {len(frei)} – Gemeinden: "
          f"{Counter(g.name(s['ags']) if s['ags'] else None for s in frei).most_common(15)}")
    else:
        treffer = Counter(k for s in ss for k in kommunen if s["ags"] and s["ags"].startswith(k))
        p(f"  in Kommunen der Datenlage: {[(kommunen[k]['name'], n) for k, n in treffer.most_common(20)]}")
sichern()

# Kurzzeit: liegen die Stellen in ihrer Kommune?
try:
    k = json.loads(kurz_index.read_text())
    kf = k["stellen"]["felder"]
    kq = k["quellen"]
    ks_an: dict[str, str] = {}
    for e in cfg["datenlage"]:
        for q in (e.get("kurzzeit") or {}).get("quellen") or []:
            ks_an[q] = e["ags"]
    t0 = time.time()
    zaehler: dict[str, Counter] = defaultdict(Counter)
    beispiele: dict[str, list] = defaultdict(list)
    for w in k["stellen"]["werte"]:
        s = dict(zip(kf, w, strict=False))
        if s.get("lon") is None:
            continue
        code = kq[s["quelle"]]
        a, art = g.finde(s["lon"], s["lat"])
        drin = bool(a and code in ks_an and a.startswith(ks_an[code]))
        zaehler[code]["drin" if drin else "außerhalb"] += 1
        if not drin and len(beispiele[code]) < 8:
            beispiele[code].append((s["id"], s["name"], a, g.name(a) if a else None, art))
    p(f"\nKurzzeit: {sum(sum(c.values()) for c in zaehler.values())} Stellen in "
      f"{time.time() - t0:.0f} s")
    for code, c in zaehler.items():
        p(f"  {code}: {dict(c)}")
        for b in beispiele[code]:
            p(f"    {b}")
except Exception as e:  # noqa: BLE001
    p(f"Kurzzeit: {e!r}")
sichern()
