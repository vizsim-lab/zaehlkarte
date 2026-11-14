"""Werkzeug: alle Angebote der Mobilithek zu Zählungen, Detektoren und Radverkehr (bundesweit).

Die Suche der Mobilithek liefert je Begriff bis zu 2.000 Angebote samt Herausgeber, Beschreibung
und Lizenz. Ergebnis: ein Eintrag je Angebot mit den Begriffen, die es gefunden haben.
Jeder Abruf nur, wenn robots.txt ihn erlaubt (tools/robots.py).
Aufruf: python3 tools/mobilithek_alle.py ergebnis/runde3
"""

import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import robots as R  # noqa: E402

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/runde3")
ZIEL.mkdir(parents=True, exist_ok=True)
SUCHE = "https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/search"
BEGRIFFE = ["Verkehrszählung", "Verkehrszählungen", "Zählstelle", "Zählstellen", "Zähldaten", "Zählung",
            "Verkehrsmengen", "Verkehrsstärke", "Verkehrsdaten", "Detektor", "Detektordaten",
            "Induktionsschleife", "Radverkehr", "Radzählung", "Fahrradzählung", "Fahrradzählstellen",
            "Radzählstelle", "Dauerzählstelle", "Messquerschnitt", "Verkehrsfluss", "Kamera", "Sensor",
            "Fußverkehr", "Passanten", "Verkehrserhebung", "Knotenpunkt", "Verkehrsaufkommen",
            "Verkehrsbelastung", "Eco-Counter", "Seitenradar", "Verkehrsmessung"]


def main():
    angebote, protokoll = {}, {}
    for b in BEGRIFFE:
        try:
            inhalt, _, _ = R.oeffne(SUCHE, daten=json.dumps({"searchString": b}).encode(),
                                    kopf={"Content-Type": "application/json"}, zeit=120, grenze=80_000_000)
            r = json.loads(inhalt)
        except R.Gesperrt:
            protokoll[b] = "robots.txt"
            break
        except Exception as e:  # noqa: BLE001
            protokoll[b] = repr(e)[:200]
            continue
        liste = (r.get("dataOffers") or {}).get("content") or []
        protokoll[b] = {"treffer": (r.get("dataOffers") or {}).get("totalElements"), "gelesen": len(liste)}
        for o in liste:
            i = o.get("publicationId")
            a = angebote.setdefault(i, {
                "id": i, "titel": o.get("title"),
                "herausgeber": ((o.get("agents") or {}).get("publisher") or {}).get("name"),
                "lizenz": (o.get("rights") or "").rsplit("#", 1)[-1],
                "zugang": (o.get("accessRights") or "").rsplit("/", 1)[-1],
                "vermittlung": o.get("mdpBrokering"), "erstellt": (o.get("created") or "")[:10],
                "kategorie": (o.get("dataCategory") or "").rsplit("#", 1)[-1],
                "beschreibung": " ".join((o.get("description") or "").split())[:700],
                "begriffe": []})
            a["begriffe"].append(b)
        time.sleep(1)
    (ZIEL / "mobilithek.json").write_text(json.dumps(sorted(angebote.values(), key=lambda a: a["herausgeber"] or ""),
                                                     ensure_ascii=False, indent=0))
    (ZIEL / "mobilithek_protokoll.json").write_text(json.dumps(protokoll, ensure_ascii=False, indent=1))
    print(len(angebote), "Angebote", json.dumps(protokoll, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
