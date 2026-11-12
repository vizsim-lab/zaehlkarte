"""KMK-Ferienkalender (PDF -> Text) und die Hamburger Datensätze im Transparenzportal (CKAN)."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}


def hole(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def main(ziel: Path) -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    for jahr in ("2024_25", "2025_26", "2026_27", "2027_28"):
        url = f"https://www.kmk.org/fileadmin/Dateien/pdf/Ferienkalender/FER{jahr}.pdf"
        try:
            pdf = ziel / f"FER{jahr}.pdf"
            pdf.write_bytes(hole(url))
            subprocess.run(["pdftotext", "-layout", str(pdf), str(ziel / f"FER{jahr}.txt")], check=True)
            pdf.unlink()
            print("ok", url, flush=True)
        except Exception as e:  # noqa: BLE001
            print("fehler", url, repr(e), flush=True)
    out = {}
    for q in ("Infrarotdetektoren", "Verkehrsdaten Kfz", "Radzählnetz"):
        try:
            d = json.loads(hole("https://suche.transparenz.hamburg.de/api/3/action/package_search?"
                                + urllib.parse.urlencode({"q": q, "rows": 20})))["result"]
            out[q] = [{"name": p.get("name"), "titel": p.get("title"), "lizenz": p.get("license_id"),
                       "lizenz_titel": p.get("license_title"), "geaendert": p.get("metadata_modified"),
                       "notes": p.get("notes"), "extras": p.get("extras"),
                       "ressourcen": [{"name": r.get("name"), "url": r.get("url"), "format": r.get("format")}
                                      for r in p.get("resources", [])]} for p in d.get("results", [])]
            print("ok", q, len(out[q]), flush=True)
        except Exception as e:  # noqa: BLE001
            out[q] = repr(e)
            print("fehler", q, repr(e), flush=True)
    (ziel / "transparenz.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
