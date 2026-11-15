"""Letzter Schritt: den Block `orte:` der Quelldatei durch ARBEIT/orte_block.yaml ersetzen.

Aufruf: python ersetze_orte.py <Checkout von main>/pipeline/config/quellen/kurzzeit/nuernberg.yaml
Alles nach der Zeile „orte:“ wird ersetzt (der Block steht am Ende der Datei).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pfade import ARBEIT  # noqa: E402

p = Path(sys.argv[1])
zeilen = p.read_text().splitlines(keepends=True)
i = zeilen.index("orte:\n")
p.write_text("".join(zeilen[: i + 1]) + (ARBEIT / "orte_block.yaml").read_text())
print(p, len(zeilen), "->", len(p.read_text().splitlines()), "Zeilen")
