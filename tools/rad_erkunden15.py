"""Erkundung (13.11.2026), Teil 15: Bonn und Düsseldorf im Detail – Formate je Jahr, Spalten
(Einzelstellen gegen Summen), Kanäle 2022 (Bonn), Zeitumstellung, Standorte. Ergebnisse in
ergebnis/rad15/<stadt>.txt."""
from __future__ import annotations

import collections
import json
import re
import time
import traceback
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ZIEL = Path("ergebnis/rad15")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str, versuche: int = 5, pause: float = 6) -> bytes:
    for i in range(versuche):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r:
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
    if "\r" in t and "\n" not in t:
        t = t.replace("\r", "\n")
    return t.replace("\r\n", "\n")


class Protokoll:
    def __init__(self, name: str):
        self.name = name
        self.z: list[str] = []

    def __call__(self, *teile):
        self.z.append(" ".join(str(t) for t in teile))

    def schreibe(self):
        (ZIEL / f"{self.name}.txt").write_text("\n".join(self.z) + "\n", encoding="utf-8")
        print(f"== {self.name}: {len(self.z)} Zeilen", flush=True)


def lauf(name, f):
    p = Protokoll(name)
    try:
        f(p)
    except Exception:  # noqa: BLE001
        p("FEHLER:", traceback.format_exc()[-3000:])
    p.schreibe()


def letzter_sonntag(j: int, m: int) -> date:
    d = date(j, m, 31)
    return d - timedelta(days=(d.weekday() - 6) % 7)


# ------------------------------------------------------------------ Bonn
def bonn(p):
    d = js("https://opendata.bonn.de/data.json")
    for x in d.get("dataset", []):
        if "Fahrradmess" not in (x.get("title") or "") or "Standorte" in (x.get("title") or ""):
            continue
        p(f"\n# {x.get('title')} | {x.get('license')}")
        for y in x.get("distribution", []):
            url = y.get("downloadURL") or y.get("accessURL")
            if not url or "stadtplan" in url:
                continue
            try:
                b = hole(url)
            except Exception as e:  # noqa: BLE001
                p(f"  ! {url}: {e!r}")
                continue
            t = text(b)
            zz = [z for z in t.split("\n")]
            kopf_i = next((i for i, z in enumerate(zz[:6]) if z.startswith(("Time;", "Zählstellenname;", "Kanalname;"))), None)
            p(f"  - {y.get('title')} | {url} | {len(b)} Bytes, {len(zz)} Zeilen, Kopfzeile {kopf_i}")
            if kopf_i is None:
                p("    erste Zeilen:", [z[:200] for z in zz[:4]])
                continue
            kopf = zz[kopf_i].split(";")
            p(f"    Spalten ({len(kopf)}): {kopf}")
            if zz[kopf_i].startswith("Zählstellenname"):
                kanal = zz[kopf_i + 1].split(";")
                p(f"    Kanäle: {kanal}")
                daten = [z.split(";") for z in zz[kopf_i + 2:] if re.match(r"\d", z)]
                summen = collections.defaultdict(int)
                for z in daten:
                    for i, v in enumerate(z[1:], start=1):
                        if v.strip():
                            summen[i] += int(float(v.replace(",", ".")))
                je_stelle = collections.defaultdict(list)
                for i in range(1, len(kopf)):
                    je_stelle[kopf[i]].append((kanal[i] if i < len(kanal) else "?", summen.get(i, 0)))
                for st, ks in je_stelle.items():
                    p(f"    {st}: {ks}")
                tage = collections.Counter(z[0][:10] for z in daten)
            else:
                daten = [z.split(";") for z in zz[kopf_i + 1:] if re.match(r"\d", z)]
                tage = collections.Counter(z[0].split(" ")[0] if "." in z[0][:3] else z[0][:10] for z in daten)
                p("    Zeitbeispiele:", [z[0] for z in daten[:2]], "…", [z[0] for z in daten[-2:]],
                  "| letzte Zeilen:", [z[:200] for z in zz[-3:]])
                # Summenspalten: ohne „N.NN BN - “ vorn
                einzel = [k for k in kopf[1:] if re.match(r"\d+\.\d+ BN - ", k)]
                p(f"    Einzelstellen {len(einzel)}, übrige Spalten: {[k for k in kopf[1:] if k not in einzel]}")
            p(f"    Zeilen je Tag: {dict(collections.Counter(tage.values()).most_common(5))}")
            for k, n in tage.items():
                if n not in (24, 96):
                    p(f"    {k}: {n}")
            # Zeitumstellung
            for z in daten:
                if re.match(r"(2[5-9]|3[01])\.(0?3|0?10)\.20\d\d 0?[12]:|(2[5-9]|3[01])\. (März|Mär\.|Okt\.) 20\d\d 0?[12]:|20\d\d-(03|10)-(2[5-9]|3[01]) 0[12]:", z[0]):
                    p("    um 1–2 Uhr Ende März/Oktober:", z[:6])
    for url in ("https://stadtplan.bonn.de/geojson?Thema=22640", "https://stadtplan.bonn.de/csv?OD=4285"):
        try:
            t = text(hole(url, versuche=8, pause=15))
            p(f"\n{url}: {len(t)} Zeichen\n{t[:9000]}")
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")


# ------------------------------------------------------------------ Düsseldorf
def duesseldorf(p):
    pakete = {}
    for q in ("Wetterabhängige Jahresübersicht Dauerzählstellen Radverkehr", "Dauerzählstellen Radverkehr 2022 Düsseldorf"):
        r = js("https://open.nrw/api/3/action/package_search?q=" + urllib.parse.quote(q) + "&rows=50")["result"]
        for x in r["results"]:
            m = re.search(r"radverkehr-(\d{4})-d$", x["name"])
            if m:
                pakete[int(m.group(1))] = x
    p("Jahrespakete:", sorted(pakete))
    for url in ("https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_2.csv",
                "https://opendata.duesseldorf.de/sites/default/files/Z%C3%A4hlstellen_1.geojson"):
        try:
            t = text(hole(url, versuche=6, pause=10))
            p(f"\n{url}:\n{t[:12000]}")
        except Exception as e:  # noqa: BLE001
            p(f"! {url}: {e!r}")
    reihen = {}
    for jahr in sorted(pakete):
        csvs = [y for y in pakete[jahr]["resources"] if y["url"].lower().endswith(".csv")]
        p(f"\n## {jahr}: {len(csvs)} CSV")
        for y in csvs:
            p(f"  · {y.get('name')} | {y['url']} | {(y.get('license') or '')[-20:]}")
        if jahr not in (2025, 2024, 2021, 2020):
            csvs = csvs[:2]
        for y in csvs:
            try:
                t = text(hole(y["url"], versuche=4, pause=4))
            except Exception as e:  # noqa: BLE001
                p(f"  ! {y.get('name')}: {e!r}")
                continue
            zz = t.rstrip("\n").split("\n")
            reihen[(jahr, y.get("name") or y["url"])] = zz
            p(f"  > {y.get('name')}: {len(zz) - 1} Zeilen, Kopf {zz[0][:140]!r}, erste {zz[1][:40]!r}")
    # Zeitumstellung je Jahr (erste Datei des Jahres)
    erste = {}
    for (jahr, name), zz in reihen.items():
        erste.setdefault(jahr, (name, zz))
    for jahr, (name, zz) in erste.items():
        for d, was in ((letzter_sonntag(jahr, 3), "Sommerzeit"), (letzter_sonntag(jahr, 10), "Rückstellung")):
            s = d.strftime("%d.%m.%Y"), d.strftime("%d-%m-%Y")
            tag = [z for z in zz if z.startswith(s)]
            p(f"  {jahr} {name[:45]} {was} {d}: {len(tag)} Zeilen; 1–3 Uhr: {[z[:40] for z in tag[1:4]]}")
    # Tagesgang im Juni: Spitzenstunde je Jahr und Datei
    for (jahr, name), zz in reihen.items():
        je_h = collections.defaultdict(list)
        for z in zz[1:]:
            f = z.split(";")
            try:
                if re.match(r"\d{2}\.\d{2}\.\d{4}$", f[0]):
                    tag, h, w = f[0], int(f[1].split(":")[0]), f[2]
                else:
                    tag, h, w = f[0][:10], int(f[0][11:13]), f[1]
                tt = date(int(tag[6:10]), int(tag[3:5]), int(tag[0:2]))
            except (ValueError, IndexError):
                continue
            if tt.month == 6 and tt.weekday() < 5 and w.strip():
                je_h[h].append(float(w.replace(",", ".")))
        m = {h: round(sum(v) / len(v), 1) for h, v in sorted(je_h.items()) if v}
        if m:
            p(f"  Juni-Werktage {jahr} {name[:45]}: Spitze früh {max(range(5, 11), key=lambda h: m.get(h, 0))} Uhr, "
              f"spät {max(range(14, 21), key=lambda h: m.get(h, 0))} Uhr; 5–10 Uhr {[m.get(h) for h in range(5, 11)]}")
    # Summen: Tagessummen 2025 je Datei, Paare und Dreier
    tage = {}
    for (jahr, name), zz in reihen.items():
        if jahr != 2025:
            continue
        s = collections.Counter()
        for z in zz[1:]:
            f = z.split(";")
            try:
                s[f[0][:10]] += sum(int(v) for v in f[1:3] if v.strip())
            except ValueError:
                continue
        tage[name[:60]] = s
    namen = sorted(tage)
    p("\n2025:", {n: sum(tage[n].values()) for n in namen})
    for a in namen:
        for b in namen:
            if a >= b:
                continue
            for c in namen:
                if c in (a, b):
                    continue
                gemeinsam = [d for d in tage[c] if d in tage[a] and d in tage[b] and tage[c][d] > 50]
                if len(gemeinsam) > 30:
                    gleich = sum(abs(tage[a][d] + tage[b][d] - tage[c][d]) <= 3 for d in gemeinsam) / len(gemeinsam)
                    if gleich > 0.8:
                        p(f"  Summe: {a} + {b} = {c} an {gleich:.0%} von {len(gemeinsam)} Tagen")
            gemeinsam = [d for d in tage[a] if d in tage[b] and tage[a][d] > 50]
            if len(gemeinsam) > 30 and sum(tage[a][d] == tage[b][d] for d in gemeinsam) / len(gemeinsam) > 0.8:
                p(f"  gleich: {a} = {b}")


for name, f in [("bonn", bonn), ("duesseldorf", duesseldorf)]:
    lauf(name, f)
