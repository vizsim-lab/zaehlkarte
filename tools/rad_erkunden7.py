"""Erkundung (13.11.2026), Teil 7: München – Format und Zeitraum der Jahresdateien 2022–2025 und
der Monatsdateien 2025 (für den Adapter)."""
from __future__ import annotations

import csv
import io
import json
import urllib.request
from collections import Counter
from pathlib import Path

ZIEL = Path("ergebnis/rad7")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-erkundung/1.0 (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


pakete = json.loads(Path("ergebnis/rad4/daten/muenchen_pakete.json").read_text(encoding="utf-8"))
alle = {r["name"]: r["url"] for p in pakete for r in p["resources"] if r.get("url")}
ziele = {k: v for k, v in alle.items() if k.startswith("15 Minuten Werte 20") and int(k[-4:]) >= 2017}
ziele.update({k: v for k, v in alle.items() if "Dezember 2025" in k and "15 Minuten" in k})
ziele.update({k: v for k, v in alle.items() if "Januar 2025" in k and "15 Minuten" in k})
aus = []
for name, url in sorted(ziele.items()):
    try:
        d = hole(url)
        t = d.decode("utf-8-sig", "replace")
        erste = t.splitlines()[0]
        trenner = max([",", ";", "\t"], key=erste.count)
        zeilen = list(csv.reader(io.StringIO(t), delimiter=trenner))
        kopf = [k.strip() for k in zeilen[0]]
        i_d = next((i for i, k in enumerate(kopf) if k.lower().startswith("datum")), 0)
        i_z = next((i for i, k in enumerate(kopf) if "zaehlstelle" in k.lower()), 3)
        tage = sorted({z[i_d].strip() for z in zeilen[1:] if len(z) > i_d})
        stellen = Counter(z[i_z].strip() for z in zeilen[1:] if len(z) > i_z)
        kommentar = Counter(z[kopf.index("kommentar")].strip() for z in zeilen[1:] if "kommentar" in kopf and len(z) > kopf.index("kommentar"))
        aus.append(f"## {name}: {url.split('/')[-1]} {len(d)} B, Trenner {trenner!r}, Kopf {kopf}")
        aus.append(f"   Tage {tage[0]} … {tage[-1]} ({len(tage)}), Stellen {dict(stellen)}")
        aus.append(f"   kommentar: {kommentar.most_common(8)}")
        aus.append(f"   Beispiel: {zeilen[1][:9]} | {zeilen[len(zeilen) // 2][:9]}")
    except Exception as e:  # noqa: BLE001
        aus.append(f"## {name}: {e!r}")
(ZIEL / "muenchen.txt").write_text("\n".join(aus) + "\n", encoding="utf-8")
