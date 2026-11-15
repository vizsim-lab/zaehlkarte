"""Prüfung: Querstraßen, die nur über die Ähnlichkeit der Namen gefunden wurden („Leißziger Str.“ ->
Leipziger Straße) – zum Durchsehen; Ortsteile („nördl. Kornburg“) gehören nicht dazu (eigene Regel)."""
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orte as O  # noqa: E402
from geo import norm  # noqa: E402
from pfade import ARBEIT  # noqa: E402

g = O.Geokodierer()
erg = json.load(open(ARBEIT / "geo_erg.json"))
gesehen = set()
for nr, es in erg.items():
    for e in es:
        if e.get("genauigkeit") not in ("kreuzung", "kreuzung_ohne_richtung"):
            continue
        haupt, hn, zus = O.zerlege(e["name"])
        for z in zus:
            z2 = re.sub(rf"^{O.RICHT}\s*", "", z, flags=re.I).strip()
            if not z2 or g.o.strasse(z2):
                continue
            q = g.querstrasse(g.o.strasse(haupt), z2)
            if q and (nr, z2, q) not in gesehen:
                gesehen.add((nr, z2, q))
                r = difflib.SequenceMatcher(None, norm(z2), norm(q)).ratio()
                print(f"{r:.2f}\t{nr}\t{haupt}\t{z2!r} -> {q!r}\t{e.get('regel')}")
