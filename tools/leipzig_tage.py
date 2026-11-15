"""Leipzig: Tageswerte der Rad-Dauerzählstellen („pro Tag der letzten 2 Jahre“, WFS-Ebene
`radverkehr_dauerzaehlstelle_anzahl_tag_zeitreihe`) erkunden – für die Tageswerte der Quelle vor
den Stunden des Gedächtnisses.

Fragen: Spalten und Zeitformat (Datum? Ortszeit? Beginn des Tags?), Werte, Zeitraum je Stelle,
doppelte Tage und Lieferungen (`fme_tstamp`), die Stelle Jahnallee, Lizenz und Beschreibung beider
Datensätze (CKAN). Rohdateien gepackt nach <ziel>/ (Tage, Stunden, Standorte) für den Vergleich mit
den Stunden des Gedächtnisses (lokal).

Nur Abrufe, die robots.txt für unsere Kennung, „*“ und die Kennungen von Claude erlaubt
(tools/robots.py, mit Crawl-delay). Aufruf: python3 tools/leipzig_tage.py <zielordner>
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import re
import sys
import traceback
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robots  # noqa: E402

WFS = "https://geodienste.leipzig.de/l3/OpenData/wfs"
EBENEN = {
    "tage": "OpenData:radverkehr_dauerzaehlstelle_anzahl_tag_zeitreihe",
    "stunden": "OpenData:radverkehr_dauerzaehlstelle_anzahl_stunde_zeitreihe",
    "standorte": "OpenData:radverkehr_dauerzaehlstelle_standort_statisch",
}
PAKETE = [
    "dauerzahlstellen-radverkehr-gesamtanzahl-der-fahrrader-pro-tag-der-letzten-2-jahre-stadt-leipzi",
    "dauerzahlstellen-radverkehr-gesamtanzahl-der-fahrrader-pro-stunde-der-letzten-31-tage-stadt-lei",
]

ziel = Path(sys.argv[1])
ziel.mkdir(parents=True, exist_ok=True)
out: list[str] = []


def schreib() -> None:
    (ziel / "bericht.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def wfs(ebene: str) -> str:
    url = WFS + "?" + urllib.parse.urlencode({
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeName": ebene,
        "outputFormat": "csv"})
    inhalt, _, _ = robots.oeffne(url, zeit=300, grenze=300_000_000)
    return inhalt.decode("utf-8-sig", "replace")


def main() -> None:
    texte: dict[str, str] = {}
    for name, ebene in EBENEN.items():
        try:
            texte[name] = wfs(ebene)
            (ziel / f"{name}.csv.gz").write_bytes(
                gzip.compress(texte[name].encode("utf-8"), mtime=0))
            zeilen = texte[name].splitlines()
            out.append(f"== {name} ({ebene}): {len(zeilen)} Zeilen, {len(texte[name]) / 1e6:.2f} MB")
            out.extend("  " + z[:400] for z in zeilen[:4])
        except Exception:  # noqa: BLE001
            out.append(f"== {name}: FEHLER " + traceback.format_exc().splitlines()[-1])
        schreib()

    if "tage" in texte:
        r = list(csv.DictReader(io.StringIO(texte["tage"])))
        out.append(f"== Tage: {len(r)} Zeilen, Spalten {list(r[0]) if r else []}")
        zeitformen = Counter(re.sub(r"\d", "9", (z.get("phenomenontime") or "")) for z in r)
        out.append(f"  Formen der Zeit: {zeitformen.most_common(8)}")
        werte = Counter("leer" if not (z.get("count") or "").strip() else
                        ("ganz" if re.fullmatch(r"\d+(?:\.0+)?", z["count"].strip()) else "sonst")
                        for z in r)
        out.append(f"  Werte: {dict(werte)}; Nullen: "
                   f"{sum(1 for z in r if (z.get('count') or '').strip() in ('0', '0.0'))}")
        lief = Counter((z.get("fme_tstamp") or "")[:10] for z in r)
        out.append(f"  Lieferungen (fme_tstamp, Tag): {len(lief)}, häufigste {lief.most_common(5)}, "
                   f"jüngste {sorted(lief)[-3:]}")
        je: dict[str, list[dict]] = defaultdict(list)
        for z in r:
            je[(z.get("stationid") or "").strip()].append(z)
        out.append(f"  Stellen: {len(je)}")
        for st, zs in sorted(je.items()):
            tage = Counter((z.get("phenomenontime") or "")[:10] for z in zs)
            doppelt = {t: n for t, n in tage.items() if n > 1}
            verschieden = sum(1 for t in doppelt
                              if len({z["count"] for z in zs if z["phenomenontime"][:10] == t}) > 1)
            name = (zs[0].get("stationname") or "").strip()
            beispiel = [(z["phenomenontime"], z["count"], z.get("fme_tstamp")) for z in zs[:2]]
            out.append(f"  {st} {name!r}: {len(zs)} Zeilen, {len(tage)} Tage "
                       f"{min(tage)}–{max(tage)}; doppelt {len(doppelt)} (verschieden "
                       f"{verschieden}), Beispiel {beispiel}")
        schreib()
    if "standorte" in texte:
        r = list(csv.DictReader(io.StringIO(texte["standorte"])))
        out.append(f"== Standorte: {len(r)}, Spalten {list(r[0]) if r else []}")
        for z in r:
            out.append("  " + json.dumps({k: v[:120] for k, v in z.items()}, ensure_ascii=False))
        schreib()

    for paket in PAKETE:
        url = f"https://opendata.leipzig.de/api/3/action/package_show?id={paket}"
        try:
            if not robots.erlaubt(url):
                out.append(f"== CKAN {paket}: robots.txt sperrt")
                continue
            inhalt, _, _ = robots.oeffne(url, zeit=60)
            d = json.loads(inhalt)["result"]
            out.append(f"== CKAN {paket}: {d.get('title')}")
            out.append(f"  Lizenz: {d.get('license_id')} | {d.get('license_title')} | "
                       f"{d.get('license_url')}")
            out.append("  Beschreibung: " + re.sub(r"\s+", " ", d.get("notes") or "")[:3000])
            for e in d.get("extras") or []:
                out.append(f"  extra {e.get('key')}: {str(e.get('value'))[:200]}")
            for res in d.get("resources") or []:
                out.append(f"  Ressource: {res.get('name')} | {res.get('format')} | "
                           f"{res.get('url')} | Lizenz {res.get('license')}")
        except Exception:  # noqa: BLE001
            out.append(f"== CKAN {paket}: FEHLER " + traceback.format_exc().splitlines()[-1])
        schreib()
    out.append("robots.txt: " + json.dumps({k: v[:300] for k, v in robots.TEXTE.items()},
                                            ensure_ascii=False))
    schreib()


if __name__ == "__main__":
    main()
