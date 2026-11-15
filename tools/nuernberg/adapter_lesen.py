"""Schritt 1: die Berichte mit dem Adapter der Pipeline lesen (src/zaehlkarte/adapters/nuernberg_pdf.py).

Schreibt nach ARBEIT: adapter_out.json (je Zählung Nummer, Name, Jahr, Wert, Hinweise, Zusatz) und
gruppen.json (Nummern der Tabellen „Außenkordon“ und „Pegnitzbrücken“ – dort gelten eigene Regeln).
Aufruf aus pipeline/ eines Checkouts von main: `uv run python <dieser Ordner>/adapter_lesen.py`.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pfade import ARBEIT, BERICHTE  # noqa: E402

from zaehlkarte.adapters import nuernberg_pdf as n  # noqa: E402
from zaehlkarte.config import quellen  # noqa: E402

q = quellen(nur_live=False)["nuernberg"]
bericht = n.Bericht()
berichte = {d["jahr"]: n.lese_pdf(BERICHTE / d["datei"]) for d in q["dateien"]}
zs = list(n.zaehlungen(berichte, q, bericht))
print(len(zs), "Zählungen;", "\n".join(bericht.zeilen()[:3]))
json.dump([{"nummer": z.stelle_roh, "name": z.name, "jahr": z.datum.year, "wert": z.fenstersummen["kfz"],
            "hinweise": z.hinweise, "zusatz": z.zusatz} for z in zs],
          open(ARBEIT / "adapter_out.json", "w"), ensure_ascii=False)
gruppen = {art: sorted({nr for b in berichte.values() for nr in b[art]}) for art in ("kordon", "bruecken")}
json.dump(gruppen, open(ARBEIT / "gruppen.json", "w"), ensure_ascii=False, indent=1)
print("Außenkordon:", len(gruppen["kordon"]), "Pegnitzbrücken:", len(gruppen["bruecken"]))
