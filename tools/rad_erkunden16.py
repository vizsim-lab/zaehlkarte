"""Erkundung (13.11.2026), Teil 16: Bonn und Düsseldorf für die Adapter – Zeitformate je Jahr,
Zeilen je Tag, Zeitumstellung (alle Spalten), Doppelte, Summenspalten, Stunden gegen Viertelstunden
(Bonn), Kanäle 2022 (Bonn), Dubletten und Summen zwischen Dateien (Düsseldorf), Standorte (Stadtplan
Bonn, Standort-CSV Düsseldorf, OpenStreetMap). Ergebnisse laufend nach ergebnis/rad16/<stadt>.txt."""
from __future__ import annotations

import collections
import json
import re
import time
import traceback
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ZIEL = Path("ergebnis/rad16")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str, versuche: int = 5, pause: float = 10, daten: bytes | None = None,
         kopf: dict | None = None, timeout: float = 90) -> bytes:
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, data=daten, headers={**UA, **(kopf or {})})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:  # noqa: BLE001
            if i == versuche - 1:
                raise
            time.sleep(pause * (i + 1))
    raise RuntimeError("unerreichbar")


def js(url: str, **kw):
    return json.loads(hole(url, **kw).decode("utf-8"))


def text(b: bytes) -> str:
    for kod in ("utf-8-sig", "cp1252"):
        try:
            t = b.decode(kod)
            break
        except UnicodeDecodeError:
            continue
    else:
        t = b.decode("mac_roman")
    return t.replace("\r\n", "\n").replace("\r", "\n")


class Protokoll:
    """Schreibt jede Zeile sofort – ein Abbruch (Zeitlimit) lässt das Bisherige stehen."""

    def __init__(self, name: str):
        self.pfad = ZIEL / f"{name}.txt"
        self.pfad.write_text("", encoding="utf-8")

    def __call__(self, *teile):
        with self.pfad.open("a", encoding="utf-8") as f:
            f.write(" ".join(str(t) for t in teile)[:20000] + "\n")


def lauf(name, f):
    p = Protokoll(name)
    try:
        f(p)
    except Exception:  # noqa: BLE001
        p("FEHLER:", traceback.format_exc()[-3000:])
    print(f"== {name} fertig", flush=True)


def letzter_sonntag(j: int, m: int) -> date:
    d = date(j, m, 31)
    return d - timedelta(days=(d.weekday() - 6) % 7)


def zahl(v: str):
    v = (v or "").strip()
    if not v:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return "x"


def osm(p, name: str, bbox: tuple[float, float, float, float]):
    s, w, n, o = bbox
    q = (f'[out:json][timeout:90];(node({s},{w},{n},{o})["man_made"="monitoring_station"]["monitoring:bicycle"];'
         f'node({s},{w},{n},{o})["monitoring:bicycle"="yes"];node({s},{w},{n},{o})["traffic_counter"];'
         f'node({s},{w},{n},{o})["man_made"="monitoring_station"]["name"~"[Zz]ähl|[Rr]ad|Eco"];);out;')
    for basis in ("https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"):
        try:
            d = js(basis, daten=urllib.parse.urlencode({"data": q}).encode(), versuche=3,
                   kopf={"Content-Type": "application/x-www-form-urlencoded"}, timeout=120)
            p(f"\nOSM {name}: {len(d.get('elements', []))} Knoten")
            for e in d.get("elements", []):
                p("   ", e.get("id"), e.get("lat"), e.get("lon"), json.dumps(e.get("tags", {}), ensure_ascii=False)[:500])
            return
        except Exception as e:  # noqa: BLE001
            p(f"! OSM {name} {basis}: {e!r}")


# ------------------------------------------------------------------ Bonn
MONATE = {"jan": 1, "feb": 2, "mär": 3, "märz": 3, "mrz": 3, "apr": 4, "mai": 5, "jun": 6, "juni": 6,
          "jul": 7, "juli": 7, "aug": 8, "sep": 9, "sept": 9, "okt": 10, "nov": 11, "dez": 12}
unbekannte_monate: collections.Counter = collections.Counter()


def bonn_zeit(s: str) -> datetime | None:
    s = s.strip()
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{1,2}):(\d{2})", s)
    if m:
        return datetime(int(m[3]), int(m[2]), int(m[1]), int(m[4]), int(m[5]))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{1,2}):(\d{2})", s)
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]))
    m = re.match(r"^(\d{1,2})\.\s*([^\W\d_]+)\.?\s+(\d{4})\s+(\d{1,2}):(\d{2})", s)
    if m:
        mon = MONATE.get(m[2].lower())
        if mon is None:
            unbekannte_monate[m[2]] += 1
            return None
        return datetime(int(m[3]), mon, int(m[1]), int(m[4]), int(m[5]))
    return None


def bonn_tabelle(t: str):
    zz = t.split("\n")
    k = next((i for i, z in enumerate(zz[:8]) if z.startswith(("Time;", "Zählstellenname;"))), None)
    if k is None:
        return None
    kopf = zz[k].split(";")
    start = k + 2 if zz[k].startswith("Zählstellenname") else k + 1
    kanal = zz[k + 1].split(";") if zz[k].startswith("Zählstellenname") else None
    zeilen, rest = [], collections.Counter()
    for z in zz[start:]:
        if not z.strip():
            continue
        f = z.split(";")
        t0 = bonn_zeit(f[0])
        if t0 is None:
            rest[f[0][:20]] += 1
            continue
        zeilen.append((t0, [zahl(v) for v in f[1:len(kopf)]]))
    return kopf, kanal, zeilen, rest


def bonn_datei(p, titel: str, url: str, jahr: int):
    b = hole(url)
    t = text(b)
    tab = bonn_tabelle(t)
    p(f"\n  - {titel} | {url} | {len(b)} Bytes")
    if tab is None:
        p("    kein Kopf; erste Zeilen:", [z[:200] for z in t.split("\n")[:4]])
        return None
    kopf, kanal, zeilen, rest = tab
    p(f"    Spalten ({len(kopf) - 1}): {kopf[1:]}")
    p(f"    Zeilen mit Zeit: {len(zeilen)}; übrige: {dict(rest.most_common(5))}")
    if not zeilen:
        return None
    schritt = collections.Counter((b[0] - a[0]).total_seconds() / 60 for a, b in zip(zeilen, zeilen[1:]))
    p(f"    Abstände (Minuten): {dict(schritt.most_common(6))}; von {zeilen[0][0]} bis {zeilen[-1][0]}")
    je_tag = collections.Counter(z[0].date() for z in zeilen)
    p(f"    Zeilen je Tag: {dict(collections.Counter(je_tag.values()).most_common(6))}")
    soll = 24 if schritt.most_common(1)[0][0] == 60 else 96
    for d, n in sorted(je_tag.items()):
        if n != soll:
            p(f"    {d}: {n} Zeilen")
    doppelt = [t0 for t0, n in collections.Counter(z[0] for z in zeilen).items() if n > 1]
    p(f"    doppelte Zeitpunkte: {len(doppelt)} {[str(x) for x in doppelt[:12]]}")
    for d in (letzter_sonntag(jahr, 3), letzter_sonntag(jahr, 10)):
        for t0, w in zeilen:
            if t0.date() == d and t0.hour <= 4:
                p(f"    {t0:%d.%m.%Y %H:%M} {w}")
    # je Spalte: gezählt, leer, erste/letzte Zeit mit Wert, Summe
    for i, name in enumerate(kopf[1:]):
        werte = [(t0, w[i]) for t0, w in zeilen if i < len(w)]
        mit = [(t0, v) for t0, v in werte if isinstance(v, float)]
        x = sum(1 for _, v in werte if v == "x")
        p(f"    [{i}] {name}{(' / ' + kanal[i + 1]) if kanal and i + 1 < len(kanal) else ''}: {len(mit)} Werte, "
          f"{len(werte) - len(mit) - x} leer, {x} unlesbar"
          + (f", {mit[0][0]:%d.%m.%Y} – {mit[-1][0]:%d.%m.%Y}, Summe {sum(v for _, v in mit):.0f}"
             f", nicht ganzzahlig {sum(1 for _, v in mit if v != int(v))}" if mit else ""))
    # Summenspalten (ohne „N.NN BN - “ vorn): gleich der Summe zweier Stellen?
    stellen = [i for i, k in enumerate(kopf[1:]) if re.match(r"\d+\.\d+ BN - ", k)]
    andere = [i for i, k in enumerate(kopf[1:]) if i not in stellen and k.strip()] if kanal is None else []

    def wert(w, j):
        return w[j] if j < len(w) else None

    for c in andere:
        for a in stellen:
            for b2 in stellen:
                if a >= b2:
                    continue
                paare = [(wert(w, a), wert(w, b2), wert(w, c)) for _, w in zeilen
                         if all(isinstance(wert(w, j), float) for j in (a, b2, c))]
                if len(paare) > 100:
                    gleich = sum(abs(x + y - z) < 0.5 for x, y, z in paare) / len(paare)
                    if gleich > 0.9:
                        p(f"    Summe: [{c}] {kopf[c + 1]} = [{a}] {kopf[a + 1]} + [{b2}] {kopf[b2 + 1]} an {gleich:.1%} von {len(paare)}")
    return kopf, zeilen


def bonn(p):
    d = js("https://opendata.bonn.de/data.json")
    dateien = {}
    for x in d.get("dataset", []):
        titel = x.get("title") or ""
        m = re.search(r"Radzählungen (20\d\d)", titel)
        if "Fahrradmess" not in titel or not m:
            continue
        jahr = int(m.group(1))
        p(f"\n# {titel} | {x.get('license')} | geändert {x.get('modified')}")
        for y in x.get("distribution", []):
            url = y.get("downloadURL") or y.get("accessURL")
            if url and "opendata.bonn.de" in url and jahr >= 2020:
                try:
                    r = bonn_datei(p, y.get("title") or "", url, jahr)
                    if r:
                        dateien[(jahr, y.get("title") or url)] = r
                except Exception as e:  # noqa: BLE001
                    p(f"  ! {url}: {e!r}")
    p(f"\nunbekannte Monatsnamen: {dict(unbekannte_monate)}")
    # Stunden gegen Summe der Viertelstunden (gleiche Spalte, alle vier Viertelstunden mit Wert)
    for jahr in (2020, 2023, 2024):
        st = [v for (j, t), v in dateien.items() if j == jahr and re.search(r"Stunde|1h|stündlich", t, re.I)]
        vi = [v for (j, t), v in dateien.items() if j == jahr and re.search(r"15", t)]
        if not (st and vi):
            continue
        (k1, z1), (k2, z2) = st[0], vi[0]
        viertel = collections.defaultdict(list)
        for t0, w in z2:
            viertel[t0.replace(minute=0)].append(w)
        gleich = ungleich = 0
        beispiele = []
        for t0, w in z1:
            q = viertel.get(t0)
            if not q or len(q) != 4:
                continue
            for i, name in enumerate(k1[1:]):
                if name not in k2 or i >= len(w) or not isinstance(w[i], float):
                    continue
                j = k2.index(name) - 1
                vs = [x[j] for x in q if j < len(x)]
                if len(vs) == 4 and all(isinstance(v, float) for v in vs):
                    if abs(sum(vs) - w[i]) < 0.5:
                        gleich += 1
                    else:
                        ungleich += 1
                        if len(beispiele) < 8:
                            beispiele.append((str(t0), name[:30], w[i], vs))
        p(f"\n{jahr}: Stundenwert = Summe der vier Viertelstunden: {gleich} gleich, {ungleich} verschieden {beispiele}")
    # 2022: Kanäle je Stelle – nacheinander oder gleichzeitig?
    k22 = [v for (j, t), v in dateien.items() if j == 2022]
    if k22:
        url = next(t for (j, t) in dateien if j == 2022)
        p(f"\n2022 ({url}): Kanäle, die gleichzeitig zählen (Viertelstunden mit beiden Werten)")
    for x in d.get("dataset", []):
        if "Radzählungen 2022" in (x.get("title") or ""):
            for y in x.get("distribution", []):
                url = y.get("downloadURL") or y.get("accessURL")
                tab = bonn_tabelle(text(hole(url)))
                if not tab:
                    continue
                kopf, kanal, zeilen, _ = tab
                gruppen = collections.defaultdict(list)
                for i, st in enumerate(kopf[1:]):
                    gruppen[st].append(i)
                for st, idx in gruppen.items():
                    for a in idx:
                        for b2 in idx:
                            if a < b2:
                                beide = sum(1 for _, w in zeilen if max(a, b2) < len(w) and isinstance(w[a], float) and isinstance(w[b2], float))
                                if beide:
                                    p(f"   {st}: {kanal[a + 1][len(st):]} & {kanal[b2 + 1][len(st):]}: {beide}")
    # Standorte
    for url in ("https://stadtplan.bonn.de/geojson?Thema=22640",):
        try:
            t = text(hole(url, versuche=6, pause=20, timeout=60))
            p(f"\n{url}: {len(t)} Zeichen\n{t[:15000]}")
        except Exception as e:  # noqa: BLE001
            p(f"\n! {url}: {e!r}")
    osm(p, "Bonn", (50.63, 7.02, 50.78, 7.22))


# ------------------------------------------------------------------ Düsseldorf
def dd_zeit(datum: str, uhr: str | None) -> datetime | None:
    s = (datum.strip() + (" " + uhr.strip() if uhr is not None else "")).strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d.%m.%y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def dd_datei(p, name: str, url: str, lizenz: str, jahr: int):
    t = text(hole(url, versuche=6, pause=8, timeout=60))
    zz = [z for z in t.split("\n") if z.strip()]
    kopf = zz[0].split(";")
    stunde_extra = len(kopf) > 2 and kopf[1].strip().lower() == "stunde"
    ende = next((i for i, k in enumerate(kopf) if "wetter" in k.lower()), len(kopf))
    wspalten = list(range(2 if stunde_extra else 1, ende))
    zeilen, unlesbar = [], []
    for z in zz[1:]:
        f = z.split(";")
        t0 = dd_zeit(f[0], f[1] if stunde_extra and len(f) > 1 else None)
        if t0 is None:
            unlesbar.append(z[:60])
            continue
        zeilen.append((t0, [zahl(f[i]) if i < len(f) else None for i in wspalten], z[:90]))
    p(f"\n  - {name} | {lizenz[-22:]} | {url}")
    p(f"    Kopf {kopf[:ende + 1]}; Wertespalten {[kopf[i] for i in wspalten]}; {len(zeilen)} Zeilen, unlesbar {len(unlesbar)} {unlesbar[:3]}")
    p(f"    erste {[z[2] for z in zeilen[:2]]}, letzte {zeilen[-1][2] if zeilen else None}")
    je_tag = collections.Counter(z[0].date() for z in zeilen)
    p(f"    Zeilen je Tag: {dict(collections.Counter(je_tag.values()).most_common(5))}; "
      f"abweichend: {[(str(d), n) for d, n in sorted(je_tag.items()) if n != 24][:12]}")
    doppelt = [(str(t0), n) for t0, n in collections.Counter(z[0] for z in zeilen).items() if n > 1]
    p(f"    doppelte Zeitpunkte: {doppelt[:10]}")
    for d in (letzter_sonntag(jahr, 3), letzter_sonntag(jahr, 10)):
        p(f"    {d}: {[z[2] for z in zeilen if z[0].date() == d and z[0].hour <= 4]}")
    for j, i in enumerate(wspalten):
        werte = [z[1][j] for z in zeilen]
        mit = [v for v in werte if isinstance(v, float)]
        p(f"    {kopf[i]}: {len(mit)} Werte, {sum(1 for v in werte if v is None)} leer, "
          f"{sum(1 for v in werte if v == 'x')} unlesbar, Summe {sum(mit):.0f}")
    return [kopf[i] for i in wspalten], zeilen


def duesseldorf(p):
    pakete = {}
    for q in ("Wetterabhängige Jahresübersicht Dauerzählstelle", "Dauerzählstellen Radverkehr Düsseldorf",
              "Radverkehr 2022 Düsseldorf Dauerzählstelle", "Zählstellen Radverkehr Standorte Düsseldorf"):
        try:
            r = js("https://open.nrw/api/3/action/package_search?rows=100&q=" + urllib.parse.quote(q))["result"]
        except Exception as e:  # noqa: BLE001
            p(f"! Suche {q}: {e!r}")
            continue
        for x in r["results"]:
            org = (x.get("organization") or {}).get("title") or ""
            if "sseldorf" not in org and not x["name"].endswith("-d"):
                continue
            if x["name"] not in pakete:
                pakete[x["name"]] = x
                p(f"  {x['name']} | {x.get('title')} | {org} | {x.get('license_id')} | {x.get('num_resources')} Ressourcen")
    jahre = {}
    for name, x in pakete.items():
        m = re.search(r"(20\d\d)", x.get("title") or "")
        if m and ("Radverkehr" in (x.get("title") or "") or "Dauerzähl" in (x.get("title") or "")):
            jahre.setdefault(int(m.group(1)), []).append(x)
    p("Jahre:", {j: [x["name"] for x in v] for j, v in sorted(jahre.items())})
    alle = {}
    for jahr in sorted(j for j in jahre if j >= 2020):
        p(f"\n## {jahr}")
        for x in jahre[jahr]:
            for y in x.get("resources", []):
                if not (y.get("url") or "").lower().endswith(".csv"):
                    continue
                try:
                    alle[(jahr, y.get("name") or y["url"])] = dd_datei(p, y.get("name") or "", y["url"], y.get("license") or x.get("license_id") or "", jahr)
                except Exception as e:  # noqa: BLE001
                    p(f"  ! {y.get('name')}: {e!r}")
                time.sleep(2)
        # Tagessummen je Datei und Spalte; Dubletten und Summen
        tage = {}
        for (j, name), (spalten, zeilen) in alle.items():
            if j != jahr:
                continue
            for k, sp in enumerate(spalten):
                s = collections.Counter()
                n = collections.Counter()
                for t0, w, _ in zeilen:
                    if isinstance(w[k], float):
                        s[t0.date()] += w[k]
                        n[t0.date()] += 1
                tage[f"{name[:40]} | {sp[:40]}"] = {d: v for d, v in s.items() if n[d] >= 23}
        namen = sorted(tage)
        for a in namen:
            for b2 in namen:
                if a >= b2:
                    continue
                gem = [d for d in tage[a] if d in tage[b2] and tage[a][d] > 20]
                if len(gem) > 30 and sum(abs(tage[a][d] - tage[b2][d]) < 0.5 for d in gem) / len(gem) > 0.8:
                    p(f"  gleich: {a} = {b2} ({len(gem)} Tage)")
                for c in namen:
                    if c in (a, b2):
                        continue
                    gem = [d for d in tage[c] if d in tage[a] and d in tage[b2] and tage[c][d] > 20]
                    if len(gem) > 30:
                        g = sum(abs(tage[a][d] + tage[b2][d] - tage[c][d]) < 0.5 for d in gem) / len(gem)
                        if g > 0.8:
                            p(f"  Summe: {c} = {a} + {b2} an {g:.0%} von {len(gem)} Tagen")
    for url in ("https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_2.csv",):
        try:
            p(f"\n{url}:\n{text(hole(url, versuche=6, pause=10))[:6000]}")
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")
    for name, x in pakete.items():
        if "Standort" in (x.get("title") or "") or "Zählstellen" == (x.get("title") or "")[:11]:
            p(f"\nStandort-Paket {name}: {[(y.get('name'), y.get('url')) for y in x.get('resources', [])]}")
    osm(p, "Düsseldorf", (51.12, 6.68, 51.36, 6.94))


for name, f in [("bonn", bonn), ("duesseldorf", duesseldorf)]:
    lauf(name, f)
