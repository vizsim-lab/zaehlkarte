"""Erkundung (13.11.2026), Teil 3: Lizenzen und Formate der letzten offenen Kandidaten.
Darmstadt (Verkehrsdaten im Rohformat), Osnabrück (TEU-Datensatz der Mobilithek), Kiel (MIV-
Dauerzählstellen), Berlin (Hinweise der Rad-Gesamtdatei), dazu die GovData-Einträge mit Lizenz.
Ergebnisse nach ergebnis/rad3/.
"""

from __future__ import annotations

import io
import json
import traceback
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ZIEL = Path("ergebnis/rad3")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str, timeout: int = 90) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def teil(name, f):
    aus: list[str] = []
    try:
        f(aus)
    except Exception:  # noqa: BLE001
        aus.append(traceback.format_exc())
    (ZIEL / f"{name}.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")


def zipkopf(aus, url: str, n: int = 8) -> None:
    z = zipfile.ZipFile(io.BytesIO(hole(url, 300)))
    dateien = [i for i in z.infolist() if not i.is_dir()]
    aus.append(f"{url}: {len(dateien)} Dateien: " + ", ".join(i.filename for i in dateien[:80]))
    for i in dateien[:2]:
        aus.append(f"== {i.filename} ({i.file_size})")
        aus += ["   " + s for s in z.read(i).decode("utf-8", "replace").splitlines()[:n]]
    andere = [i for i in dateien if not i.filename.startswith("dynamicData/")]
    for i in andere[:3]:
        aus.append(f"== {i.filename} ({i.file_size})")
        aus += ["   " + s for s in z.read(i).decode("utf-8", "replace").splitlines()[:n]]


def govdata(aus):
    basis = "https://ckan.govdata.de/api/3/action/"
    namen = ["verkehrsdaten-im-rohformat-2025", "verkehrszahlungsdatensatz-osnabruck-01-01-2022-09-11-2023",
             "miv-verkehrsdaten-dauerzahlstellen-kiel-langzeitdaten-stundlich-mit-abfragemoglichkeit-historis",
             "radzahldaten-in-berlin3fcda", "stundenwerte-der-dauerzahlstellen-in-baden-wurttembergba12b",
             "hochfein-verkehrsstarken-mullerstrasse", "nuerlast-fahrradverkehr-in-munster-schleifendetektor-zahlungen-mit-zeitstempeln"]
    for n in namen:
        try:
            p = json.loads(hole(basis + "package_show?id=" + urllib.parse.quote(n)))["result"]
        except Exception as e:  # noqa: BLE001
            aus.append(f"## {n}: {e}")
            continue
        extras = {x["key"]: x["value"] for x in p.get("extras", [])}
        aus.append(f"## {p['title']} | license_id {p.get('license_id')} | {p.get('license_title')}")
        aus.append(f"   Herausgeber {(p.get('organization') or {}).get('title')} | {extras.get('publisher_name')} | {extras.get('contributorID')}")
        aus.append(f"   {(p.get('notes') or '')[:900]}")
        for k in ("licenseAttributionByText", "spatial", "temporal_start", "temporal_end", "frequency", "landingpage", "url", "originator_name"):
            if extras.get(k):
                aus.append(f"   {k}: {extras[k][:300]}")
        for r in p.get("resources", [])[:4]:
            aus.append(f"   - {r.get('name')} | lizenz {r.get('license')} | {r.get('url')}")
    for q in ("Kiel Dauerzählstellen", "KielRegion Verkehr", "Darmstadt Verkehrsdaten Rohformat"):
        try:
            res = json.loads(hole(basis + "package_search?" + urllib.parse.urlencode({"q": q, "rows": 15})))["result"]["results"]
            aus.append(f"## Suche {q!r}: " + " | ".join(f"{x['title']} ({x['name']}, {x.get('license_id')})" for x in res))
        except Exception as e:  # noqa: BLE001
            aus.append(f"## Suche {q}: {e}")


def darmstadt(aus):
    zipkopf(aus, "https://opendata.darmstadt.de/sites/default/files/A126_4.zip", n=10)
    for url in ["https://opendata.darmstadt.de/dataset/verkehrsdaten-im-rohformat-2025",
                "https://opendata.darmstadt.de/dataset/verkehrsdaten-im-rohformat-2026"]:
        try:
            t = hole(url, 60).decode("utf-8", "replace")
            import re
            lic = re.findall(r'(?i)(lizenz[^<]{0,200}|license[^<]{0,200}|dl-de[^<"]{0,60}|cc[- ]by[^<"]{0,40}|Datenlizenz[^<]{0,80})', t)
            aus.append(f"## {url}: Lizenz-Treffer {lic[:8]}")
            k = t.find("field-name-body")
            aus.append("   Beschreibung: " + re.sub(r"<[^>]+>", " ", t[k:k + 3000])[:1500])
        except Exception as e:  # noqa: BLE001
            aus.append(f"## {url}: {e}")


def osnabrueck(aus):
    zipkopf(aus, "https://mobilithek.info/mdp-api/files/aux/903287344194932736/teu_dataset.zip", n=6)
    t = hole("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/903287344194932736", 60).decode("utf-8", "replace")
    try:
        d = json.loads(t)
        aus.append("Angebot: " + json.dumps({k: v for k, v in d.items() if k not in ("description",)}, ensure_ascii=False)[:4000])
    except Exception:  # noqa: BLE001
        aus.append("Angebot (roh): " + t[:4000])


def kiel(aus):
    t = hole("https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/995318989663924224", 60).decode("utf-8", "replace")
    aus.append("Angebot (roh): " + t[:5000])


def berlin(aus):
    import openpyxl

    url = ("https://www.berlin.de/sen/uvk/_assets/verkehr/verkehrsplanung/radverkehr/weitere-radinfrastruktur/"
           "zaehlstellen-und-fahrradbarometer/gesamtdatei-stundenwerte.xlsx")
    wb = openpyxl.load_workbook(io.BytesIO(hole(url, 300)), data_only=True)
    ws = wb["Hinweise"]
    for z in ws.iter_rows(values_only=True):
        if any(z):
            aus.append(" | ".join("" if v is None else str(v) for v in z))
    j = wb["Jahresdatei 2025"]
    kopf = [c.value for c in j[1]]
    aus.append(f"Jahresdatei 2025 Kopf: {kopf[:12]} … ({len(kopf)} Spalten)")
    # markierte (rekonstruierte) Zellen zählen: Füllfarbe ungleich Standard
    farben = {}
    for zeile in j.iter_rows(min_row=2, max_row=j.max_row):
        for c in zeile[1:]:
            f = c.fill.fgColor.rgb if c.fill and c.fill.fill_type else None
            if f and f not in ("00000000", "FFFFFFFF"):
                farben[f] = farben.get(f, 0) + 1
    aus.append(f"Füllfarben in Jahresdatei 2025 (markierte Zellen): {farben}")
    leg = wb["Legende"]
    for z in leg.iter_rows():
        for c in z:
            if c.fill and c.fill.fill_type:
                aus.append(f"Legende {c.coordinate}: Farbe {c.fill.fgColor.rgb} Wert {c.value!r}")


if __name__ == "__main__":
    for name, f in [("govdata", govdata), ("darmstadt", darmstadt), ("osnabrueck", osnabrueck),
                    ("kiel", kiel), ("berlin", berlin)]:
        teil(name, f)
