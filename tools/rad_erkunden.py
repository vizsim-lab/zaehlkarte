"""Erkundung (13.11.2026): Rad-Zählstellen und weitere Dauerzählstellen.

1. Kataloge (CKAN): GovData, open.nrw, MobiData BW und einige Stadtportale – Datensätze zu Rad-
   Zählstellen und Kfz-Dauerzählstellen mit Organisation, Lizenz, Ressourcen und Änderungsdatum.
2. MobiData BW, Eco-Counter: Stundenwerte eines Monats (Spalten, Zählstellen, Kommunen),
   Stellenliste, historische Daten.
3. MobiData BW, Landes-Dauerzählstellen: Ergebnisse (Excel) und Wochen-/Tagesganglinien (PDF) –
   was steht drin (Jahreswerte, Mittel oder gezählte Tage)?
4. Stichproben: München (Raddauerzählstellen), Bonn (open.nrw), Köln, Berlin, Münster, Leipzig,
   Dresden, Düsseldorf, Bielefeld.
Ergebnisse nach ergebnis/rad/.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import traceback
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ZIEL = Path("ergebnis/rad")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def schreibe(name: str, text: str) -> None:
    (ZIEL / name).write_text(text, encoding="utf-8")


def schritt(name: str):
    def deko(f):
        def lauf():
            try:
                f()
            except Exception:  # noqa: BLE001 – Erkundung: Fehler aufschreiben, weiter
                schreibe(f"{name}.fehler.txt", traceback.format_exc())
        return lauf
    return deko


def ckan_suche(basis: str, q: str, rows: int = 200) -> list[dict]:
    url = f"{basis}/api/3/action/package_search?" + urllib.parse.urlencode({"q": q, "rows": rows})
    daten = json.loads(hole(url))
    return daten["result"]["results"]


def kurz(p: dict) -> dict:
    return {
        "name": p.get("name"), "titel": p.get("title"),
        "org": (p.get("organization") or {}).get("title"),
        "lizenz": p.get("license_id") or p.get("license_title"),
        "geaendert": p.get("metadata_modified"),
        "ressourcen": [{"name": r.get("name"), "format": r.get("format"), "url": r.get("url"),
                        "geaendert": r.get("last_modified") or r.get("metadata_modified")}
                       for r in (p.get("resources") or [])[:12]],
        "n_ressourcen": len(p.get("resources") or []),
    }


RAD = ["Fahrradzählstelle", "Fahrradzählstellen", "Radzählstelle", "Radzählstellen",
       "Raddauerzählstelle", "Raddauerzählstellen", "Fahrradzähler", "Radverkehrszählung",
       "Eco-Counter", "Fahrradmessstelle", "Radverkehr Zählstelle", "Zählstellen Radverkehr",
       "Fahrradzählung", "Radzählung"]
KFZ = ["Dauerzählstelle", "Dauerzählstellen", "Verkehrsdetektor", "Verkehrsdetektion",
       "Verkehrsstärke", "Verkehrsstärken", "Verkehrsmengenerfassung", "Induktionsschleife",
       "Zählschleife", "Wärmebildkamera", "Verkehrssensor", "Verkehrssensoren", "Kfz-Zählstelle",
       "Verkehrszählung Stundenwerte", "Detektordaten", "Zählkamera"]


def katalog(name: str, basis: str, begriffe: list[str]) -> None:
    gesehen: dict[str, dict] = {}
    fehler = []
    for q in begriffe:
        try:
            for p in ckan_suche(basis, q):
                gesehen.setdefault(p["name"], kurz(p) | {"treffer": []})["treffer"].append(q)
        except Exception as e:  # noqa: BLE001
            fehler.append(f"{q}: {e}")
    eintraege = sorted(gesehen.values(), key=lambda x: (x["org"] or "", x["titel"] or ""))
    schreibe(f"{name}.json", json.dumps({"fehler": fehler, "datensaetze": eintraege},
                                         ensure_ascii=False, indent=1))
    zeilen = [f"{len(eintraege)} Datensätze; Fehler: {fehler[:3]}"]
    for e in eintraege:
        formate = sorted({(r["format"] or "?") for r in e["ressourcen"]})
        zeilen.append(f"{e['org']} | {e['titel']} | {e['lizenz']} | {e['geaendert'][:10] if e['geaendert'] else ''} "
                      f"| {e['n_ressourcen']} Ress. {','.join(formate)} | {e['name']}")
    schreibe(f"{name}.txt", "\n".join(zeilen) + "\n")


@schritt("kataloge")
def kataloge() -> None:
    # GovData: Schnittstelle unter ckan.govdata.de, früher www.govdata.de/ckan
    gov = "https://ckan.govdata.de"
    try:
        ckan_suche(gov, "Fahrrad", 1)
    except Exception:  # noqa: BLE001
        gov = "https://www.govdata.de/ckan"
    for name, basis in [("govdata", gov), ("opennrw", "https://ckan.open.nrw"),
                        ("mobidata", "https://mobidata-bw.de")]:
        katalog(f"{name}_rad", basis, RAD)
        katalog(f"{name}_kfz", basis, KFZ)
    for name, basis in [("muenchen", "https://opendata.muenchen.de"),
                        ("berlin", "https://datenregister.berlin.de"),
                        ("koeln", "https://www.offenedaten-koeln.de"),
                        ("leipzig", "https://opendata.leipzig.de"),
                        ("duesseldorf", "https://opendata.duesseldorf.de"),
                        ("muenster", "https://opendata.stadt-muenster.de"),
                        ("bielefeld", "https://open-data.bielefeld.de"),
                        ("frankfurt", "https://offenedaten.frankfurt.de"),
                        ("hannover", "https://opendata.hannover.de"),
                        ("sh", "https://opendata.schleswig-holstein.de"),
                        ("rostock", "https://www.opendata-hro.de"),
                        ("bremen", "https://transparenz.bremen.de"),
                        ("karlsruhe", "https://transparenz.karlsruhe.de"),
                        ("aachen", "https://offenedaten.aachen.de"),
                        ("darmstadt", "https://opendata.darmstadt.de")]:
        katalog(f"stadt_{name}", basis, ["Fahrrad", "Rad Zählstelle", "Radverkehr", "Dauerzählstelle",
                                          "Verkehrszählung", "Verkehrsstärke", "Detektor"])


def zeige_csv(daten: bytes, n: int = 15, trenner: str | None = None) -> tuple[list[str], list[list[str]]]:
    text = daten.decode("utf-8-sig", errors="replace")
    if trenner is None:
        kopf = text.splitlines()[0]
        trenner = ";" if kopf.count(";") > kopf.count(",") else ","
    rd = csv.reader(io.StringIO(text), delimiter=trenner)
    zeilen = list(rd)
    return zeilen[0], zeilen[1:]


@schritt("eco_counter")
def eco_counter() -> None:
    meta = json.loads(hole("https://mobidata-bw.de/api/3/action/package_show?id=eco-counter-fahrradzahler"))
    p = meta["result"]
    aus = [f"Datensatz: {p['title']} | Lizenz {p.get('license_id')} | {p.get('metadata_modified')}",
           f"Beschreibung: {p.get('notes')}", ""]
    for r in p["resources"]:
        aus.append(f"- {r.get('name')} | {r.get('format')} | {r.get('url')} | {r.get('description')}")
    # ein Monat Stundenwerte
    for monat in ["202610", "202609"]:
        try:
            roh = gzip.decompress(hole(f"https://mobidata-bw.de/daten/eco-counter/v2/fahrradzaehler_stundenwerten_{monat}.csv.gz", 300))
        except Exception as e:  # noqa: BLE001
            aus.append(f"{monat}: {e}")
            continue
        kopf, zeilen = zeige_csv(roh)
        aus += ["", f"Monat {monat}: {len(roh) / 1e6:.1f} MB, {len(zeilen)} Zeilen", f"Kopf: {kopf}"]
        aus += [f"  {z}" for z in zeilen[:12]]
        for spalte in kopf:
            i = kopf.index(spalte)
            werte = {z[i] for z in zeilen if len(z) > i}
            if len(werte) < 400:
                aus.append(f"  Spalte {spalte}: {len(werte)} Werte, z. B. {sorted(werte)[:25]}")
            else:
                aus.append(f"  Spalte {spalte}: {len(werte)} Werte")
        break
    # Stellenliste
    for r in p["resources"]:
        if r.get("name", "").startswith("Fahrradzähldaten (CSV)"):
            try:
                kopf, zeilen = zeige_csv(hole(r["url"], 120))
                aus += ["", f"Stellenliste {r['url']}: {len(zeilen)} Zeilen", f"Kopf: {kopf}"]
                aus += [f"  {z}" for z in zeilen[:8]]
            except Exception as e:  # noqa: BLE001
                aus.append(f"Stellenliste: {e}")
    schreibe("eco_counter.txt", "\n".join(aus) + "\n")


@schritt("bw_dauerzaehlstellen")
def bw_dauerzaehlstellen() -> None:
    import openpyxl

    meta = json.loads(hole("https://mobidata-bw.de/api/3/action/package_show?id=ergebnisse_ganglinien_dauerzaehlstellen"))
    p = meta["result"]
    aus = [f"Datensatz: {p['title']} | Org {(p.get('organization') or {}).get('title')} | Lizenz {p.get('license_id')}",
           f"Beschreibung: {p.get('notes')}", ""]
    for r in p["resources"]:
        aus.append(f"- {r.get('name')} | {r.get('format')} | {r.get('url')} | {r.get('description')}")
    basis = "https://mobidata-bw.de/vm/Ergebnisse_Ganglinien_Dauerzaehlstellen_BW/"
    roh = hole(basis + "Ergebnisse_2025_Excel.zip", 300)
    z = zipfile.ZipFile(io.BytesIO(roh))
    aus += ["", f"Ergebnisse_2025_Excel.zip: {len(roh) / 1e6:.1f} MB", *[f"  {i.filename} {i.file_size}" for i in z.infolist()]]
    for i in z.infolist():
        if not i.filename.lower().endswith(".xlsx"):
            continue
        if not any(k in i.filename for k in ("_01.", "Jahr", "_10.")):
            continue
        wb = openpyxl.load_workbook(io.BytesIO(z.read(i)), read_only=True, data_only=True)
        aus.append(f"\n== {i.filename}: Blätter {wb.sheetnames}")
        for ws in wb.worksheets[:3]:
            aus.append(f"-- Blatt {ws.title} ({ws.max_row} Zeilen x {ws.max_column} Spalten)")
            for n, zeile in enumerate(ws.iter_rows(values_only=True)):
                if n >= 25:
                    break
                aus.append("   " + " | ".join("" if v is None else str(v) for v in zeile[:30]))
    # Wochen- und Tagesganglinien: Dateien und Text der ersten Seite einer PDF
    try:
        import pdfplumber

        roh = hole(basis + "Ganglinien_WochenUndTage.zip", 300)
        z = zipfile.ZipFile(io.BytesIO(roh))
        aus += ["", f"Ganglinien_WochenUndTage.zip: {len(roh) / 1e6:.1f} MB, {len(z.infolist())} Dateien",
                *[f"  {i.filename} {i.file_size}" for i in z.infolist()[:40]]]
        pdfs = [i for i in z.infolist() if i.filename.lower().endswith(".pdf")]
        for i in pdfs[:2]:
            with pdfplumber.open(io.BytesIO(z.read(i))) as pdf:
                aus.append(f"\n== {i.filename}: {len(pdf.pages)} Seiten")
                for s in pdf.pages[:2]:
                    aus.append((s.extract_text() or "")[:2500])
    except Exception:  # noqa: BLE001
        aus.append(traceback.format_exc())
    schreibe("bw_dauerzaehlstellen.txt", "\n".join(aus) + "\n")


@schritt("stichproben")
def stichproben() -> None:
    aus = []
    # München: Raddauerzählstellen (Ressourcen der jüngsten Datensätze, eine Datei ansehen)
    try:
        treffer = ckan_suche("https://opendata.muenchen.de", "raddauerzaehlstellen", 300)
        aus.append(f"München: {len(treffer)} Datensätze")
        treffer.sort(key=lambda p: p.get("metadata_modified") or "", reverse=True)
        for p in treffer[:6]:
            aus.append(f"- {p['title']} | {p.get('license_id')} | {p.get('metadata_modified')}")
            for r in p["resources"][:6]:
                aus.append(f"    {r.get('name')} | {r.get('format')} | {r.get('url')}")
        for p in treffer:
            for r in p["resources"]:
                if "15" in (r.get("name") or "") and (r.get("format") or "").lower() == "csv":
                    kopf, zeilen = zeige_csv(hole(r["url"], 300))
                    aus += [f"Datei {r['url']}: {len(zeilen)} Zeilen", f"Kopf: {kopf}", *[f"  {z}" for z in zeilen[:8]]]
                    raise StopIteration
    except StopIteration:
        pass
    except Exception as e:  # noqa: BLE001
        aus.append(f"München: {e}")
    # Bonn (open.nrw): Fahrradmessstellen
    try:
        treffer = ckan_suche("https://ckan.open.nrw", "fahrradmessstellen bonn", 100)
        aus.append(f"\nBonn: {len(treffer)} Datensätze")
        for p in sorted(treffer, key=lambda p: p.get("name")):
            aus.append(f"- {p['title']} | {p.get('license_id')} | {p.get('metadata_modified')}")
            for r in p["resources"][:4]:
                aus.append(f"    {r.get('name')} | {r.get('format')} | {r.get('url')}")
        jung = sorted([p for p in treffer if "ergebnisse" in p["name"]], key=lambda p: p["name"])[-1:]
        for p in jung:
            for r in p["resources"]:
                if (r.get("format") or "").lower() == "csv":
                    kopf, zeilen = zeige_csv(hole(r["url"], 300))
                    aus += [f"Datei {r['url']}: {len(zeilen)} Zeilen", f"Kopf: {kopf}", *[f"  {z}" for z in zeilen[:8]]]
                    break
    except Exception as e:  # noqa: BLE001
        aus.append(f"Bonn: {e}")
    schreibe("stichproben.txt", "\n".join(aus) + "\n")


if __name__ == "__main__":
    for f in (eco_counter, bw_dauerzaehlstellen, stichproben, kataloge):
        f()
