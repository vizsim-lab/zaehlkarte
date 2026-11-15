"""Erkundung (15.11.2026): Fuß und Landesstraßen – was lässt sich in die Karte holen?

Teile (Aufruf: python3 tools/bw_fl1.py <ziel> <teil> [<teil> …]):
- fritz: Freiburg FR.ITZ, Datensatz „Fahrrad-Zählstellen Zeitreihe“ (Rad und Fußgänger getrennt):
  Seite, verlinkte Dateien, content.csv (gz abgelegt) und eine Übersicht je Zählstelle, Art und
  Richtung.
- planegg: Gemeinde Planegg, Fahrradzählstelle Amtmannstraße – Seite und alle Excel-Dateien.
- mobidata: MobiData BW, Eco-Counter – Ressourcen des Datensatzes (älteres Format je Kanal?).
- mobilithek: Metadaten der Angebote der Länder (Dauerzählstellen Bayern, Rheinland-Pfalz,
  Schleswig-Holstein …) und, was sie als Zugang nennen.
- baysis: Bayerisches Straßeninformationssystem, Seiten zu den Dauerzählstellen.
Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py).
"""

from __future__ import annotations

import collections
import csv
import gzip
import html
import io
import json
import pathlib
import re
import sys
import time
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
LOG: list[str] = []


def log(*z):
    s = " ".join(str(x) for x in z)
    print(time.strftime("%H:%M:%S"), s, flush=True)
    LOG.append(s)


def hole(url, *, zeit=90, grenze=25_000_000, daten=None, kopf=None):
    for versuch in range(3):
        try:
            inhalt, ende, art = R.oeffne(url, zeit=zeit, grenze=grenze, daten=daten, kopf=kopf)
            log("ok", url, len(inhalt), art)
            return inhalt, ende, art
        except R.Gesperrt:
            log("gesperrt", url)
            raise
        except Exception as e:  # noqa: BLE001
            log("Fehler", versuch + 1, url, repr(e)[:160])
            if versuch == 2 or "HTTP Error 404" in repr(e) or "zu groß" in repr(e):
                raise
            time.sleep(5 + 10 * versuch)


def links(seite: bytes, basis: str) -> list[str]:
    text = seite.decode("utf-8", "replace")
    out = []
    for m in re.finditer(r"""(?:href|src|action)\s*=\s*["']([^"'#]+)""", text, re.I):
        u = urllib.parse.urljoin(basis, html.unescape(m.group(1)).strip())
        if u.startswith("http") and u not in out:
            out.append(u)
    return out


def name_fuer(url: str) -> str:
    t = urllib.parse.urlsplit(url)
    n = (t.path.rstrip("/").split("/")[-1] or "index") + (("_" + t.query) if t.query else "")
    return re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.unquote(n))[:120]


def ablegen(ordner: pathlib.Path, url: str, inhalt: bytes) -> pathlib.Path:
    ordner.mkdir(parents=True, exist_ok=True)
    p = ordner / name_fuer(url)
    p.write_bytes(inhalt)
    return p


# --- Freiburg -----------------------------------------------------------------------------

FRITZ = "https://fritz.freiburg.de/duva2dcat/dataset/de-bw-freiburg-fahrrad-zaehlstellen_zeitreihe"


def fritz():
    ordner = ZIEL / "fritz"
    seiten = {}
    for url in [FRITZ + ".html", FRITZ + ".rdf", FRITZ + ".ttl", FRITZ + ".jsonld", FRITZ + ".json",
                "https://fritz.freiburg.de/duva2dcat/", "https://fritz.freiburg.de/duva2dcat/catalog.html",
                "https://fritz.freiburg.de/duva2dcat/catalog.rdf"]:
        try:
            inhalt, ende, _ = hole(url, zeit=60, grenze=20_000_000)
            ablegen(ordner, url, inhalt)
            seiten[url] = links(inhalt, ende)
        except Exception as e:  # noqa: BLE001
            seiten[url] = repr(e)[:200]
    (ordner / "links.json").write_text(json.dumps(seiten, ensure_ascii=False, indent=1))
    # verlinkte Dateien des Datensatzes (nicht content.csv – die kommt unten)
    folgen = []
    for v in seiten.values():
        if isinstance(v, list):
            folgen += [u for u in v if "fritz.freiburg.de" in u and "zaehl" in u.lower()
                       and not u.endswith("content.csv") and u not in seiten]
    andere = sorted({u for v in seiten.values() if isinstance(v, list) for u in v
                     if "fritz.freiburg.de/duva2dcat/dataset/" in u and "zaehl" in u.lower()})
    (ordner / "datensaetze_zaehl.json").write_text(json.dumps(andere, ensure_ascii=False, indent=1))
    for url in list(dict.fromkeys(folgen))[:30]:
        try:
            inhalt, _, _ = hole(url, zeit=90, grenze=40_000_000)
            p = ablegen(ordner / "verlinkt", url, inhalt)
            if len(inhalt) > 3_000_000:
                p.with_suffix(p.suffix + ".gz").write_bytes(gzip.compress(inhalt))
                p.unlink()
        except Exception:  # noqa: BLE001
            pass
    inhalt, _, _ = hole(FRITZ + "/content.csv", zeit=300, grenze=200_000_000)
    (ordner / "content.csv.gz").write_bytes(gzip.compress(inhalt, 9))
    fritz_uebersicht(inhalt.decode("utf-8-sig", "replace"), ordner)


def fritz_uebersicht(text: str, ordner: pathlib.Path):
    zeilen = list(csv.reader(io.StringIO(text), delimiter=text[:2000].count(";") > text[:2000].count(",") and ";" or ","))
    kopf, daten = zeilen[0], zeilen[1:]
    aus = [f"Kopf: {kopf}", f"Zeilen: {len(daten)}"]
    i = {k: n for n, k in enumerate(kopf)}
    st, wert, ri, art, dt = (kopf[3], kopf[4], kopf[5], kopf[6], kopf[2])
    gruppen = collections.defaultdict(lambda: {"n": 0, "tage": collections.Counter(), "summe": 0,
                                               "von": "9999", "bis": "0000", "leer": 0})
    doppelt = collections.Counter()
    je_stunde = collections.defaultdict(dict)
    for z in daten:
        if len(z) < len(kopf):
            continue
        k = (z[i[st]], z[i[art]], z[i[ri]])
        g = gruppen[k]
        g["n"] += 1
        g["tage"][z[i[dt]][:10]] += 1
        w = z[i[wert]].strip()
        if w in ("", "-", "NA", "na"):
            g["leer"] += 1
        else:
            try:
                g["summe"] += float(w.replace(",", "."))
            except ValueError:
                g["leer"] += 1
        g["von"] = min(g["von"], z[i[dt]])
        g["bis"] = max(g["bis"], z[i[dt]])
        doppelt[(k, z[i[dt]])] += 1
        je_stunde[(z[i[st]], z[i[art]], z[i[dt]])][z[i[ri]]] = w
    aus.append("Zählstelle | Art | Richtung | Zeilen | Tage | Tage mit 24 Zeilen | von | bis | Summe | leer")
    for k in sorted(gruppen, key=lambda x: (int(x[0]) if x[0].isdigit() else 999, x[1], x[2])):
        g = gruppen[k]
        aus.append(f"{k[0]} | {k[1]} | {k[2]} | {g['n']} | {len(g['tage'])} | "
                   f"{sum(1 for n in g['tage'].values() if n == 24)} | {g['von']} | {g['bis']} | "
                   f"{g['summe']:.0f} | {g['leer']}")
    aus.append(f"doppelte Stunden: {sum(1 for n in doppelt.values() if n > 1)}")
    # Richtung 3 (all) = 1 + 2?
    v = collections.Counter()
    for (s, a, _), werte in je_stunde.items():
        if "3" in werte and ("1" in werte or "2" in werte):
            try:
                summe = sum(float(werte.get(r, "0") or 0) for r in ("1", "2"))
                v["gleich" if abs(summe - float(werte["3"] or 0)) < 0.5 else "anders"] += 1
            except ValueError:
                v["unlesbar"] += 1
        elif "3" in werte:
            v["nur 3"] += 1
        else:
            v["nur 1/2"] += 1
    aus.append(f"Richtung 3 gegen 1+2: {dict(v)}")
    # Zeitumstellung: Zeilen um 2 Uhr an den Umstelltagen
    um = collections.Counter()
    for z in daten:
        d = z[i[dt]]
        if d[5:7] in ("03", "10") and d[11:13] in ("01", "02", "03") and int(d[8:10]) >= 25:
            um[(d[:10], d[11:13])] += 1
    aus.append("Zeilen 1–3 Uhr an Tagen 25.–31. März/Oktober (Auszug): "
               + "; ".join(f"{k[0]} {k[1]}h: {n}" for k, n in sorted(um.items())[:60]))
    aus.append("erste Zeilen: " + " || ".join(";".join(z) for z in daten[:5]))
    (ordner / "uebersicht.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


# --- Planegg ------------------------------------------------------------------------------

PLANEGG = "https://www.planegg.de/umwelt/mobilitaet/radverkehr/fahrradzaehlstelle-amtmannstrasse"


def planegg():
    ordner = ZIEL / "planegg"
    inhalt, ende, _ = hole(PLANEGG, zeit=60)
    ablegen(ordner, PLANEGG + ".html", inhalt)
    alle = links(inhalt, ende)
    (ordner / "links.json").write_text(json.dumps(alle, ensure_ascii=False, indent=1))
    dateien = [u for u in alle if re.search(r"(?i)\.(xlsx?|csv|ods|pdf)(\?|$)", u)
               or "download" in u.lower() or "fileadmin" in u.lower()]
    for url in dateien[:25]:
        try:
            d, _, art = hole(url, zeit=90, grenze=30_000_000)
            ablegen(ordner / "dateien", url, d)
        except Exception:  # noqa: BLE001
            pass


# --- MobiData BW (älteres Eco-Counter-Format) ----------------------------------------------

def mobidata():
    ordner = ZIEL / "mobidata"
    for name in ["eco-counter-fahrradzahler", "eco-counter-fahrradzaehler"]:
        url = f"https://mobidata-bw.de/api/3/action/package_show?id={name}"
        try:
            inhalt, _, _ = hole(url, zeit=60)
            ablegen(ordner, url, inhalt)
            d = json.loads(inhalt)["result"]
            aus = [f"{d['title']} | {d.get('license_id')} | {d.get('metadata_modified')}"]
            for r in d["resources"]:
                aus.append(f"- {r.get('name')} | {r.get('format')} | {r.get('url')} | "
                           f"{r.get('last_modified') or r.get('created')} | {r.get('size')}")
            (ordner / "ressourcen.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
            break
        except Exception:  # noqa: BLE001
            continue
    for url in ["https://mobidata-bw.de/daten/eco-counter/", "https://mobidata-bw.de/daten/eco-counter/v2/"]:
        try:
            inhalt, _, _ = hole(url, zeit=60)
            ablegen(ordner, url + "index.html", inhalt)
        except Exception:  # noqa: BLE001
            pass


# --- Mobilithek ----------------------------------------------------------------------------

ANGEBOTE = {
    "798871611185745920": "Daten der Dauerzählstellen (DAUZ) in Bayern (ZVM)",
    "-4266012713253267478": "Dauerzählstellen (StMB Bayern)",
    "-6470273619834216294": "Zählstellen 2021 (StMB Bayern)",
    "-8628280793063448106": "Langzeitzählstellen (LBM Rheinland-Pfalz)",
    "748506312813203456": "Verkehrsdaten Messquerschnitte dynamisch (LBV.SH)",
    "748508537744674816": "Verkehrsdaten Messquerschnitte statisch (LBV.SH)",
    "983406200238284800": "Straßenverkehrszählungsdaten der Lausitz (IPG)",
    "-489044378979458875": "Fußgängerzählstellen Hamburg",
    "-1595922270408040459": "Verkehrszählstellen Hamburg",
    "-781197459961221857": "Digitale Personenzählung Kiel (ODALA)",
}


def mobilithek():
    ordner = ZIEL / "mobilithek"
    aus = []
    zugaenge = []
    for oid, titel in ANGEBOTE.items():
        url = f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{oid}"
        try:
            inhalt, _, _ = hole(url, zeit=60)
            d = json.loads(inhalt)
            (ordner / f"{oid}.json").parent.mkdir(parents=True, exist_ok=True)
            (ordner / f"{oid}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1))
            aus.append(f"## {oid} {titel}")
            aus.append(f"  Lizenz {d.get('rights')} | Vermittlung {d.get('mdpBrokering')} | Freigabe "
                       f"{(d.get('contractOffer') or {}).get('providerApprovalRequired')} | Zeitraum "
                       f"{d.get('temporalCoverage')} | {d.get('accrualPeriodicity')}")
            for c in d.get("contentData") or []:
                aus.append(f"  - {c.get('accessUrl')} | {c.get('mediaType')} | {c.get('dataModel')} | "
                           f"{c.get('fileName')} | {c.get('byteSize')} | {c.get('description')}")
                if c.get("accessUrl"):
                    zugaenge.append((oid, c["accessUrl"]))
            for s in d.get("samples") or []:
                aus.append(f"  Probe: {json.dumps(s, ensure_ascii=False)[:300]}")
                for v in (s.values() if isinstance(s, dict) else []):
                    if isinstance(v, str) and v.startswith("http"):
                        zugaenge.append((oid, v))
            aus.append("  " + (d.get("description") or "")[:1500].replace("\n", " "))
        except Exception as e:  # noqa: BLE001
            aus.append(f"## {oid} {titel}: {e!r}"[:300])
    for oid, url in zugaenge:
        try:
            inhalt, ende, art = hole(url, zeit=120, grenze=60_000_000)
            p = ablegen(ordner / "zugang" / oid, url, inhalt)
            aus.append(f"Zugang {oid}: {url} -> {ende} | {art} | {len(inhalt)} Byte | {p.name}")
            if len(inhalt) > 5_000_000:
                p.with_suffix(p.suffix + ".gz").write_bytes(gzip.compress(inhalt))
                p.unlink()
            if b"<html" in inhalt[:2000].lower():
                for u in links(inhalt, ende)[:80]:
                    aus.append(f"    link {u}")
        except Exception as e:  # noqa: BLE001
            aus.append(f"Zugang {oid}: {url}: {e!r}"[:300])
    (ordner / "angebote.txt").parent.mkdir(parents=True, exist_ok=True)
    (ordner / "angebote.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


# --- BAYSIS --------------------------------------------------------------------------------

def baysis():
    ordner = ZIEL / "baysis"
    start = ["https://www.baysis.bayern.de/internet/verdat/dauz/index.html",
             "https://www.baysis.bayern.de/internet/verdat/statistik/index.html",
             "https://www.baysis.bayern.de/internet/veroeffentlichung/index.html"]
    gesehen, aus = set(), []
    warte = list(start)
    while warte and len(gesehen) < 30:
        url = warte.pop(0)
        if url in gesehen:
            continue
        gesehen.add(url)
        try:
            inhalt, ende, art = hole(url, zeit=60, grenze=15_000_000)
        except Exception as e:  # noqa: BLE001
            aus.append(f"{url}: {e!r}"[:200])
            continue
        ablegen(ordner, url, inhalt)
        if "html" not in art:
            continue
        for u in links(inhalt, ende):
            if "baysis.bayern.de" in u and re.search(r"(?i)dauz|dauer|stunde|ganglin|csv|zip|xls", u):
                aus.append(f"{url} -> {u}")
                if u not in gesehen and len(warte) < 40:
                    warte.append(u)
    (ordner / "links.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


TEILE = {"fritz": fritz, "planegg": planegg, "mobidata": mobidata, "mobilithek": mobilithek,
         "baysis": baysis}

if __name__ == "__main__":
    ZIEL.mkdir(parents=True, exist_ok=True)
    for t in sys.argv[2:]:
        try:
            TEILE[t]()
        except Exception as e:  # noqa: BLE001
            log("Teil", t, "abgebrochen:", repr(e)[:300])
    (ZIEL / f"robots_{'_'.join(sys.argv[2:])}.json").write_text(
        json.dumps(R.TEXTE, ensure_ascii=False, indent=1))
    with open(ZIEL / "log.txt", "a") as f:
        f.write("\n".join(LOG) + "\n")
