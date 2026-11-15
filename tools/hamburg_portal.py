"""Hamburg: Datensatzbeschreibungen der Infrarot-Dienste im Transparenzportal – die HTML-Seite
des Datensatzes (die CKAN-API unter /api/ sperrt robots.txt; Crawl-Delay 10 s).

    python3 tools/hamburg_portal.py <zielordner>
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robots  # noqa: E402

ziel = Path(sys.argv[1])
ziel.mkdir(parents=True, exist_ok=True)
for name in ("verkehrsdaten-kfz-infrarotdetektoren-hamburg14",
             "verkehrsdaten-rad-infrarotdetektoren-hamburg20"):
    url = f"https://suche.transparenz.hamburg.de/dataset/{name}"
    try:
        inhalt, ende, _ = robots.oeffne(url, zeit=60)
        text = inhalt.decode("utf-8", "replace")
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?is)<br\s*/?>|</p>|</li>|</h\d>|</tr>|</div>", "\n", text)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        text = "\n".join(re.sub(r"[ \t]+", " ", z).strip() for z in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text)
        (ziel / f"portal_{name}.txt").write_text(f"{url} -> {ende}\n\n{text}", encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        (ziel / f"portal_{name}.txt").write_text(f"{url}: {e!r}\n", encoding="utf-8")
