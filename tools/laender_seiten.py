"""Werkzeug: Seiten, die nur im Browser oder nur aus GitHub Actions lesbar sind (Playwright).

Je Seite: Text, Links und die Anfragen der Seite; dazu Dateien (PDF -> Text) und WMS/WFS-
Capabilities. Liste der Seiten: tools/laender_seiten.json ({name: url}).
"""

import json
import pathlib
import re
import subprocess
import sys
import urllib.request

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/seiten")
ZIEL.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "zaehlkarte-werkzeug/0.1 (+https://github.com/vizsim-lab/zaehlkarte)"}
SEITEN = json.loads(pathlib.Path(__file__).with_name("laender_seiten.json").read_text(encoding="utf-8"))
protokoll = {}


def hole(url, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as a:
        return a.read()


dateien = {n: u for n, u in SEITEN.items() if re.search(r"\.(pdf|xlsx?|csv|zip)$|GetCapabilities", u, re.I)}
for name, url in dateien.items():
    try:
        daten = hole(url)
        endung = ".xml" if "GetCapabilities" in url else "." + url.rsplit(".", 1)[-1].lower()[:4]
        pfad = ZIEL / (name + endung)
        pfad.write_bytes(daten[:60_000_000])
        if daten.startswith(b"%PDF"):
            subprocess.run(["pdftotext", "-layout", str(pfad), str(pfad) + ".txt"], check=False)
        protokoll[name] = len(daten)
    except Exception as e:  # noqa: BLE001
        protokoll[name] = repr(e)[:200]

try:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(locale="de-DE", user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36 zaehlkarte-werkzeug"))
        anfragen = []
        seite.on("request", lambda r: anfragen.append(r.url))
        for name, url in SEITEN.items():
            if name in dateien:
                continue
            anfragen.clear()
            try:
                seite.goto(url, wait_until="networkidle", timeout=60_000)
                seite.wait_for_timeout(1500)
                (ZIEL / f"{name}.txt").write_text(seite.inner_text("body"), encoding="utf-8")
                links = seite.eval_on_selector_all(
                    "a", "els => els.map(e => [e.innerText.trim().slice(0, 160), e.href])")
                (ZIEL / f"{name}_links.json").write_text(json.dumps(
                    {"links": links, "anfragen": [a for a in anfragen if "/api" in a or "json" in a][:80]},
                    ensure_ascii=False, indent=1), encoding="utf-8")
                protokoll[name] = "ok"
            except Exception as e:  # noqa: BLE001
                protokoll[name] = repr(e)[:200]
        browser.close()
except Exception as e:  # noqa: BLE001
    protokoll["playwright"] = repr(e)[:300]

(ZIEL / "protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(protokoll, ensure_ascii=False, indent=1))
