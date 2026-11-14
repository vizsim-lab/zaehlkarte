"""Datenlage je Kommune: was es gibt, auch außerhalb der Karte – je Familie (Kurzzeitzählungen,
Dauerzählstellen) ein Stand mit Text und Belegen, aus `config/kommunen/<LAND>.yaml`.

`schreibe()` (`zaehlkarte datenlage`, auch am Ende von `zaehlkarte site`) erzeugt
public/data/datenlage.json und docs/DATENLAGE.md. Aus den Kartendaten kommt nur die Zahl der
Zählungen der Kommunen in der Karte (index.json) – ein neuer Bau ist nicht nötig, wenn sich nur
Datenlage-Texte ändern.

Vertrag mit dem Frontend (js/data/laden.js, js/map/ebenen.js, main.js), datenlage.json Version 2:
eine FeatureCollection, je Kommune ein Punkt (`lage`), dazu `version` und `stand`/`stand_en`
(Name jedes Stands je Familie, deutsch und englisch). Eigenschaften je Kommune:
- `ags` (Gemeindeschlüssel, bei Kreisen der Kreisschlüssel), `name`, `land`, `recht`, `kontakt`
- `kurzzeit`: {stand, quellen, zaehlungen, was, situation, empfehlung, weg, links, anfrage} oder
  null; `dauer`: {stand, quellen, was, situation, links} oder null
- `stand_k`, `stand_d`: der Stand flach, nur wo die Familie einen Eintrag hat – die Ausdrücke der
  Karte lesen verschachtelte Werte nur als Text
Wer ihn ändert, erhöht VERSION und zieht das Frontend und tests/web im selben Schritt mit.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

from zaehlkarte.config import Pfade, konfiguration

VERSION = 2
FAMILIEN = ("kurzzeit", "dauer")

# Eine Liste von Ständen für beide Familien; die Namen weichen bei den Dauerzählstellen ab, wo sie
# dort etwas anderes meinen (keine Anfragevorlage für Dauerzählstellen)
STAND = {
    "in_karte": "in der Karte",
    "offen": "offen, noch nicht in der Karte",
    "geliefert": "auf Anfrage herausgegeben",
    "kandidat": "erhoben – Anfrage aussichtsreich",
    "ohne_lizenz": "vorhanden, aber ohne Lizenz",
    "aggregiert": "nur Summen oder Mittelwerte offen",
    "nur_karte": "nur als Karte",
    "abgelehnt": "Anfrage gescheitert",
    "nichts_offen": "nichts offen",
}
STAND_DAUER = STAND | {"offen": "offen, nicht in der Karte",
                       "kandidat": "vorhanden, Werte nicht offen"}
# Für den Sprachumschalter der Karte (DE/EN); die Datenlage-Texte selbst bleiben deutsch.
STAND_EN = {
    "in_karte": "on the map",
    "offen": "open, not yet on the map",
    "geliefert": "released on request",
    "kandidat": "collected – request promising",
    "ohne_lizenz": "available, but without a licence",
    "aggregiert": "only totals or averages open",
    "nur_karte": "only as a map",
    "abgelehnt": "request failed",
    "nichts_offen": "nothing open",
}
STAND_DAUER_EN = STAND_EN | {"offen": "open, not on the map", "kandidat": "exist, values not open"}
NAMEN = {"kurzzeit": STAND, "dauer": STAND_DAUER}

# Land aus den ersten beiden Ziffern des Gemeindeschlüssels
LAND = {"01": "SH", "02": "HH", "03": "NI", "04": "HB", "05": "NW", "06": "HE", "07": "RP",
        "08": "BW", "09": "BY", "10": "SL", "11": "BE", "12": "BB", "13": "MV", "14": "SN",
        "15": "ST", "16": "TH"}
FDS_SUCHE = "https://fragdenstaat.de/behoerden/?q="


def anfrage(vorlage: dict, kommune: str, zusatz: str | None, an: str | None = None) -> dict:
    """Anfragetext aus der Vorlage (config/anfrage_vorlage.yaml; Feld „Anfrage“ auf FragDenStaat).
    `an`: die angefragte Stelle, wo sie keine Stadt ist (etwa „Gemeinde Mühltal“)."""
    zusatz = " ".join((zusatz or "").split())
    text = vorlage["text"].format(kommune=kommune, stelle=an or f"Stadt {kommune}",
                                  zusatz=f"\n{zusatz}\n" if zusatz else "")
    return {"betreff": vorlage["betreff"], "text": text.strip()}


def kontakt(roh: dict | None) -> dict | None:
    """Kontakt aus der FragDenStaat-Behördendatenbank; ohne Behörde ein Link zur Suche dort."""
    if not roh:
        return None
    out = {k: roh[k] for k in ("name", "email", "fds") if roh.get(k)}
    if roh.get("fds_suche"):
        out["fds"] = FDS_SUCHE + quote_plus(roh["fds_suche"])
        out["fds_suche"] = True
    return out


def _text(x: str | None) -> str | None:
    return " ".join((x or "").split()) or None


def _links(roh: list | None) -> list[dict]:
    return [{"titel": t, "url": u} for t, u in roh or []]


def _block(e: dict, familie: str, vorlage: dict, zaehlungen: Counter | None) -> dict | None:
    roh = e.get(familie)
    if not roh:
        return None
    if roh.get("stand") not in STAND:
        raise ValueError(f"{e['name']}: {familie}.stand {roh.get('stand')!r} unbekannt")
    out = {"stand": roh["stand"], "quellen": list(roh.get("quellen") or [])}
    if familie == "kurzzeit":
        out["zaehlungen"] = (sum(zaehlungen[c] for c in out["quellen"])
                             if out["quellen"] and zaehlungen is not None else None)
    out |= {"was": _text(roh.get("was")), "situation": _text(roh.get("situation"))}
    if familie == "kurzzeit":
        out |= {"empfehlung": _text(roh.get("empfehlung")), "weg": roh.get("weg")}
        a = roh.get("anfrage")
        out["anfrage"] = (anfrage(vorlage, e["name"], a.get("zusatz"), a.get("an"))
                          if a is not None else None)
    out["links"] = _links(roh.get("links"))
    return out


def datenlage(pfade: Pfade | None = None, zaehlungen: Counter | None = None) -> dict:
    """datenlage.json (Version 2). `zaehlungen`: Zahl der Zählungen je Kurzzeit-Quelle."""
    cfg = konfiguration(pfade)
    features = []
    for e in cfg["datenlage"]:
        bloecke = {f: _block(e, f, cfg["anfrage_vorlage"], zaehlungen) for f in FAMILIEN}
        if not any(bloecke.values()):
            raise ValueError(f"{e['name']}: weder kurzzeit noch dauer")
        land = LAND[e["ags"][:2]]
        p = {"ags": e["ags"], "name": e["name"], "land": land, "recht": cfg["recht"].get(land),
             "kontakt": kontakt(e.get("kontakt")), **bloecke}
        for f, kurz in (("kurzzeit", "stand_k"), ("dauer", "stand_d")):
            if bloecke[f]:
                p[kurz] = bloecke[f]["stand"]
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": list(e["lage"])},
                         "properties": p})
    return {
        "version": VERSION,
        "stand": {"kurzzeit": STAND, "dauer": STAND_DAUER},
        "stand_en": {"kurzzeit": STAND_EN, "dauer": STAND_DAUER_EN},
        "type": "FeatureCollection",
        "features": features,
    }


def _belege(links: list[dict]) -> list[str]:
    return ["**Belege:** " + " · ".join(f"[{x['titel']}]({x['url']})" for x in links), ""]


def datenlage_md(fc: dict, erzeugt: str) -> str:
    """Übersicht für GitHub (docs/DATENLAGE.md) aus denselben Daten wie die Karte."""
    zeilen = [
        "# Datenlage: kommunale Verkehrszählungen",
        "",
        f"Erzeugt von `zaehlkarte site` bzw. `zaehlkarte datenlage` am {erzeugt} aus",
        "`pipeline/config/kommunen/` (je Land eine Datei) – nicht von Hand ändern. Dieselben",
        "Angaben zeigt die Karte unter „Datenlage je Kommune“ (Kurzzeitzählungen bzw.",
        "Dauerzählstellen). Kommunen, von denen nur Dauerzählstellen bekannt sind, haben keinen",
        "Stand der Kurzzeitzählungen („–“).",
        "Rechtliche Hinweise sind keine Rechtsberatung; Kontakte aus der Behördendatenbank von",
        "FragDenStaat.",
        "",
        "| Kommune | Land | Stand | Dauerzählstellen | Empfehlung |",
        "|---|---|---|---|---|",
    ]

    def in_karte(p: dict) -> bool:
        return bool(p["kurzzeit"] and p["kurzzeit"]["stand"] == "in_karte")

    eintraege = sorted(fc["features"], key=lambda f: (in_karte(f["properties"]),
                                                       f["properties"]["name"]))
    for f in eintraege:
        p = f["properties"]
        k, d = p["kurzzeit"], p["dauer"]
        emp = (k or {}).get("empfehlung") or ("in der Karte" if in_karte(p) else "")
        emp = emp.split(". ")[0]
        kurz = STAND[k["stand"]] if k else "–"
        dauer = STAND_DAUER[d["stand"]] if d else ""
        zeilen.append(f"| {p['name']} | {p['land']} | {kurz} | {dauer} | {emp} |")
    for f in eintraege:
        p = f["properties"]
        k, d = p["kurzzeit"], p["dauer"]
        if not k:  # nur Dauerzählstellen bekannt
            titel = f"{p['name']} ({p['land']}) – Dauerzählstellen {STAND_DAUER[d['stand']]}"
            zeilen += ["", f"## {titel}", "", f"**Lage:** {d['situation'] or d['was']}", ""]
            if d["links"]:
                zeilen += _belege(d["links"])
            continue
        if in_karte(p):
            if d:  # in der Karte (Kurzzeitzählungen): nur die Dauerzählstellen
                zeilen += ["", f"## {p['name']} – Dauerzählstellen {STAND_DAUER[d['stand']]}", "",
                           d["situation"] or d["was"] or "", ""]
                if d["links"]:
                    zeilen += _belege(d["links"])
            continue
        zeilen += ["", f"## {p['name']} ({p['land']}) – {STAND[k['stand']]}", ""]
        zeilen += [f"**Lage:** {k['situation'] or k['was']}", ""]
        if k["empfehlung"]:
            zeilen += [f"**Empfehlung:** {k['empfehlung']}", ""]
        if k["weg"]:
            zeilen += [f"**Weg:** {k['weg']}", ""]
        if d:
            zeilen += [f"**Dauerzählstellen ({STAND_DAUER[d['stand']]}):** "
                       f"{d['situation'] or d['was']}", ""]
        kt = p.get("kontakt") or {}
        if kt:
            teile = [kt.get("name"), f"<{kt['email']}>" if kt.get("email") else None,
                     f"[FragDenStaat]({kt['fds']})" if kt.get("fds") else None]
            zeilen += ["**Kontakt:** " + " · ".join(t for t in teile if t), ""]
        if k["anfrage"]:
            zeilen += [f"**Anfragetext** – Betreff: {k['anfrage']['betreff']}", "", "```text",
                       k["anfrage"]["text"], "```", ""]
        belege = k["links"] + [x for x in (d or {}).get("links", []) if x not in k["links"]]
        if belege:
            zeilen += _belege(belege)
    return "\n".join(zeilen).rstrip() + "\n"


def zaehlungen_je_quelle(index: dict) -> Counter:
    """Zahl der Zählungen je Kurzzeit-Quelle aus einer index.json."""
    f = index["stellen"]["felder"]
    iq = f.index("quelle")
    quelle = [index["quellen"][w[iq]] for w in index["stellen"]["werte"]]
    return Counter(quelle[z[0]] for z in index["zaehlungen"]["werte"])


def schreibe(pfade: Pfade | None = None, erzeugt: date | None = None,
             zaehlungen: Counter | None = None) -> list[Path]:
    """datenlage.json und docs/DATENLAGE.md schreiben. Ohne `zaehlungen` aus der vorhandenen
    index.json."""
    pfade = pfade or Pfade()
    if zaehlungen is None:
        index = json.loads((pfade.karte / "index.json").read_text(encoding="utf-8"))
        zaehlungen = zaehlungen_je_quelle(index)
    fc = datenlage(pfade, zaehlungen)
    ziel = pfade.karte / "datenlage.json"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(json.dumps(fc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    doku = pfade.repo / "docs" / "DATENLAGE.md"
    doku.parent.mkdir(exist_ok=True)
    doku.write_text(datenlage_md(fc, (erzeugt or date.today()).isoformat()), encoding="utf-8")
    return [ziel, doku]
