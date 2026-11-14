"""Werkzeug: einzelne Dateien holen (Quellen ohne Lizenz, November 2026) – PDF, Excel, JSON, HTML.

Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py: eigene Kennung, `*` und die
Kennungen von Claude), mit dem Abstand je Host. Je Eintrag ein Ordner mit der Datei, bei PDF der
Text (pdftotext -layout) daneben, und ein Protokoll (URL, Ziel, Typ, Größe, sha256 oder Fehler).

Aufruf: python3 tools/holen.py <ziel> <liste>
Liste: je Zeile „name | url“ (# Kommentar); name = Ordner im Ziel.
"""

import hashlib
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1])
LISTE = pathlib.Path(sys.argv[2])
ENDUNG = {"application/pdf": ".pdf", "application/json": ".json", "text/html": ".html",
          "text/csv": ".csv", "application/zip": ".zip", "text/plain": ".txt",
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
          "application/vnd.ms-excel": ".xls"}


def dateiname(url: str, typ: str, n: int) -> str:
    pfad = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", pfad.rsplit("/", 1)[-1]).strip("_") or "datei"
    endung = ENDUNG.get(typ.split(";")[0].strip().lower(), "")
    if endung and not name.lower().endswith(endung):
        name = f"{name}{endung}"
    return f"{n:02d}_{name}"


def main():
    protokoll: dict[str, list] = {}
    for n, zeile in enumerate(LISTE.read_text(encoding="utf-8").splitlines()):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        name, url = (t.strip() for t in zeile.split("|", 1))
        ordner = ZIEL / name
        ordner.mkdir(parents=True, exist_ok=True)
        eintrag = {"url": url}
        try:
            if not R.erlaubt(url):
                raise R.Gesperrt(url)
            inhalt, ende, typ = R.oeffne(url, zeit=120, grenze=80_000_000)
            datei = ordner / dateiname(ende, typ, n)
            datei.write_bytes(inhalt)
            eintrag |= {"ende": ende, "typ": typ, "bytes": len(inhalt), "datei": datei.name,
                        "sha256": hashlib.sha256(inhalt).hexdigest()}
            if inhalt[:5] == b"%PDF-":
                subprocess.run(["pdftotext", "-layout", str(datei), str(datei) + ".txt"],
                               check=False, timeout=300)
            print(name, url, "ok", len(inhalt))
        except Exception as e:  # noqa: BLE001
            eintrag["fehler"] = repr(e)[:300]
            print(name, url, "FEHLER", repr(e)[:200])
        protokoll.setdefault(name, []).append(eintrag)
    for name, eintraege in protokoll.items():
        (ZIEL / name / "protokoll.json").write_text(
            json.dumps(eintraege, ensure_ascii=False, indent=1), encoding="utf-8")
    (ZIEL / "robots.json").write_text(json.dumps(R.TEXTE, ensure_ascii=False, indent=1),
                                      encoding="utf-8")


if __name__ == "__main__":
    main()
