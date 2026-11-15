"""Webseiten als Text ablegen (etwa die Seite eines Datensatzes, wenn robots.txt die CKAN-API
sperrt) – nur, was robots.txt erlaubt (tools/robots.py, mit Crawl-delay).

    python3 tools/seiten.py <zielordner> <url> [<url> …]
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
for url in sys.argv[2:]:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:150] + ".txt"
    try:
        inhalt, ende, _ = robots.oeffne(url, zeit=60)
        text = inhalt.decode("utf-8", "replace")
        text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
        text = re.sub(r"(?is)<br\s*/?>|</p>|</li>|</h\d>|</tr>|</div>|</dt>|</dd>", "\n", text)
        links = re.findall(r'(?is)<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', inhalt.decode("utf-8", "replace"))
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        text = "\n".join(re.sub(r"[ \t]+", " ", z).strip() for z in text.splitlines())
        text = re.sub(r"\n{3,}", "\n\n", text)
        verweise = "\n".join(f"{html.unescape(re.sub(r'<[^>]+>', ' ', t)).strip()[:80]} -> {h}"
                             for h, t in links if "licen" in h.lower() or "lizenz" in h.lower()
                             or "govdata" in h.lower() or "creativecommons" in h.lower())
        (ziel / name).write_text(f"{url} -> {ende}\n\n{text}\n\n== Lizenz-Verweise\n{verweise}\n",
                                 encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        (ziel / name).write_text(f"{url}: {e!r}\n", encoding="utf-8")
