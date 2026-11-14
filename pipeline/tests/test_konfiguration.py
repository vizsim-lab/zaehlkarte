"""Die echte Konfiguration (pipeline/config/, Aufbau in config/README.md) gegen die Regeln aus
CLAUDE.md: Ein Tippfehler oder eine vergessene Angabe fällt im PR auf – nicht erst beim Bau, in der
Karte oder gar nicht (ein unbekannter optionaler Schlüssel würde sonst still zu `None`, eine Datei
am falschen Ort still übergangen).

Neue Regeln kommen hierher. Noch nicht geprüft, weil es heute noch nicht gilt: die Verknüpfung
einer Kommune mit ihren Dauer-Quellen (die Karte sucht sie über den Namen und die Nähe).
"""

from __future__ import annotations

import re
import string
from datetime import date

import pytest
import yaml

from zaehlkarte import adapters, fetch, site
from zaehlkarte.config import Pfade, konfiguration
from zaehlkarte.dauer import bau
from zaehlkarte.kalender import FEIERTAGE_LAENDER, FERIEN, LAENDER, ferienkalender

CONFIG = Pfade().config
CFG = konfiguration()
KURZZEIT = CFG["quellen"]
DAUER = CFG["dauer"]
QUELLEN = [("quellen", c, q) for c, q in KURZZEIT.items()] + [("dauer", c, q)
                                                              for c, q in DAUER.items()]
LIVE = [(f, c, q) for f, c, q in QUELLEN if q["status"] == "live"]
DATENLAGE = CFG["datenlage"]

URL = re.compile(r"https?://\S+$")
# Codes stecken in Stellen-IDs, Permalinks und Asset-Namen (`<code>__<datei>`): kein „__“
CODE = re.compile(r"[a-z][a-z0-9]*(_[a-z0-9]+)*$")
DEUTSCHLAND = {"lon": (5.8, 15.1), "lat": (47.2, 55.1)}

EINTRAG = {"kommune", "land", "lon", "lat", "quelle", "stand", "was", "situation", "empfehlung",
           "weg", "links", "kontakt", "anfrage", "anfrage_zusatz", "anfrage_an", "dauer"}
DAUER_BLOCK = {"stand", "was", "situation", "links"}
KONTAKT = {"name", "email", "fds", "fds_suche"}  # Funktionsadressen aus FragDenStaat


def _id(x: tuple) -> str:
    return f"{x[0]}/{x[1]}"


# --- Quellen beider Familien ------------------------------------------------------------------


def test_ordner():
    """Nur, was der Lader liest – eine Datei am falschen Ort oder mit anderer Endung fiele sonst
    still weg: je Quelle `quellen/<familie>/<code>.yaml`, je Land `kommunen/<LAND>.yaml` und
    `kalender/ferien/<LAND>.csv`."""
    oben = {"README.md", "quellen", "kommunen", "kalender", "recht.yaml", "anfrage_vorlage.yaml",
            "robots.yaml"}
    oben |= {q["rohdatei_liste"] for q in KURZZEIT.values() if "rohdatei_liste" in q}
    assert {p.name for p in CONFIG.iterdir()} <= oben, {p.name for p in CONFIG.iterdir()} - oben

    def dateien(ordner: str) -> set[str]:
        return {p.relative_to(CONFIG / ordner).as_posix()
                for p in (CONFIG / ordner).rglob("*") if p.is_file()}

    assert dateien("quellen") == ({f"kurzzeit/{c}.yaml" for c in KURZZEIT}
                                  | {f"dauer/{c}.yaml" for c in DAUER})
    assert dateien("kommunen") <= {f"{land}.yaml" for land in LAENDER}
    assert dateien("kalender") == {f"ferien/{land}.csv" for land in LAENDER}


def test_codes_eindeutig_und_gueltig():
    assert not set(KURZZEIT) & set(DAUER), "derselbe Code in beiden Familien"
    for familie, code, q in QUELLEN:
        assert CODE.match(code), f"{familie}/{code}: Code nur aus a–z, 0–9 und einfachem _"
        assert "code" not in q, f"{familie}/{code}: der Code ist der Dateiname"
        assert q["status"] in ("live", "research", "blocked"), f"{familie}/{code}: Status"


@pytest.mark.parametrize("quelle", LIVE, ids=_id)
def test_adapter_bekannt(quelle):
    familie, code, q = quelle
    if familie == "quellen":
        assert q["adapter"] in adapters.ADAPTER, f"{code}: Adapter zum Lesen fehlt"
        assert q["adapter"] in fetch.ABRUF, f"{code}: Abruf für den Adapter fehlt (fetch.py)"
    else:
        assert q["adapter"] in bau.ADAPTER, f"{code}: Adapter fehlt (dauer/bau.py)"


def _lizenz_ok(x: dict) -> bool:
    return bool(x.get("lizenz")) and bool(URL.match(x.get("lizenz_url") or ""))


@pytest.mark.parametrize("quelle", LIVE, ids=_id)
def test_lizenz_je_quelle(quelle):
    """Nie eine Quelle ohne Lizenzangabe: an der Quelle oder je Lieferung, dazu die Lizenz der
    Lage, wo sie aus OpenStreetMap kommt."""
    _, code, q = quelle
    if "lieferungen" in q:
        assert q["lieferungen"], f"{code}: keine Lieferung"
        for lf in q["lieferungen"]:
            assert _lizenz_ok(lf), f"{code}/{lf.get('code')}: Lizenz und Lizenz-URL"
    else:
        assert _lizenz_ok(q), f"{code}: Lizenz und Lizenz-URL"
    if "geokodierung" in q:
        assert _lizenz_ok(q["geokodierung"]), f"{code}: Lizenz der Geokodierung"


@pytest.mark.parametrize("quelle", [x for x in LIVE if x[0] == "dauer"], ids=_id)
def test_lizenz_mit_einschraenkung_nur_mit_hinweis(quelle):
    """Lizenzen mit Einschränkung (nicht kommerziell, Nutzungsbeschränkung) stehen mit einem
    Hinweis an der Quelle, der die Lizenz erklärt (Seitenleiste der Dauerzählstellen)."""
    _, code, q = quelle
    lizenz = q["lizenz"]
    if re.search(r"\bNC\b|beschränk|nicht kommerziell|nicht für", lizenz, re.IGNORECASE):
        assert any("Lizenz" in h for h in q.get("hinweise", [])), f"{code}: Hinweis zur Lizenz"


@pytest.mark.parametrize("quelle", QUELLEN, ids=_id)
def test_land_jeder_quelle(quelle):
    """Das Land wählt Rechtslage, Ferien (config/kalender/ferien/<LAND>.csv) und Feiertage – ein
    eigenes `ferien:` an der Quelle gibt es nicht mehr."""
    _, code, q = quelle
    assert q["land"] in LAENDER, f"{code}: Land {q['land']!r}"
    assert "ferien" not in q, f"{code}: `ferien:` entfällt, das Land wählt den Kalender"


@pytest.mark.parametrize("land", LAENDER)
def test_kalender_je_land(land):
    """Ohne Ferien oder Feiertage wäre jeder Werktag „unbekannt“ bzw. ein Feiertag ein Schultag –
    ohne Warnung. Alle 16 Länder haben Rechtslage, Feiertage und Ferien bis mindestens 2027/28;
    dass sie rechtzeitig fortgeschrieben werden, prüft `zaehlkarte kalender` im Wochenlauf."""
    assert land in CFG["recht"], f"Rechtslage für {land} fehlt"
    assert land in FEIERTAGE_LAENDER, f"Feiertage für {land} fehlen"
    kal = ferienkalender(land, CONFIG)
    assert kal is not None, f"{FERIEN / land}.csv fehlt"
    assert (kal.letztes_schuljahr() or "") >= "2027/2028", f"{land}: {kal.letztes_schuljahr()}"


def _datum_bis_heute(x) -> bool:
    return isinstance(x, date) and x <= date.today()


def test_robots_ausnahmen():
    """Eine Ausnahme von robots.txt (config/robots.yaml) nur mit URL-Anfängen, den Quellen, die
    sie brauchen, Grund, Datum und dem Stand der Anfrage beim Betreiber – je URL-Anfang eine
    (CLAUDE.md, AGENTS.md „robots.txt und die Pipeline“)."""
    codes = set(KURZZEIT) | set(DAUER)
    praefixe = []
    for e in CFG["robots"]:
        name = e.get("urls")
        assert set(e) == {"urls", "quellen", "grund", "seit", "anfrage"}, f"{name}: {set(e)}"
        assert e["urls"] and e["quellen"], name
        for u in e["urls"]:
            assert u.startswith("https://") and u.endswith("/"), u
        praefixe += e["urls"]
        assert set(e["quellen"]) <= codes, f"{name}: unbekannt {set(e['quellen']) - codes}"
        assert e["grund"].strip() and _datum_bis_heute(e["seit"]), name
        a = e["anfrage"]
        assert {"an", "gestellt", "antwort"} <= set(a) <= {"an", "gestellt", "antwort",
                                                           "verzicht"}, f"{name}: {set(a)}"
        assert a["an"].strip(), name
        assert a["gestellt"] is None or _datum_bis_heute(a["gestellt"]), f"{name}: gestellt"
        assert a["antwort"] is None or (str(a["antwort"]).strip() and a["gestellt"]), name
        assert not (a.get("verzicht") and a["gestellt"]), f"{name}: Verzicht, aber gestellt"
    assert len(praefixe) == len(set(praefixe)), "derselbe URL-Anfang in zwei Ausnahmen"
    for familie, code, q in QUELLEN:
        assert "robots_ausnahme" not in q, f"{familie}/{code}: Ausnahmen stehen in robots.yaml"


def test_pruefsummen():
    """Gepinnte Rohdaten (Berlin, Münster, Konstanz, Xanten): sha256 als 64 Hex-Zeichen."""

    def felder(x, pfad):
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).startswith("sha256"):
                    yield f"{pfad}.{k}", v
                yield from felder(v, f"{pfad}.{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                yield from felder(v, f"{pfad}[{i}]")

    alle = list(felder({"kurzzeit": KURZZEIT, "dauer": DAUER}, "quellen"))
    assert alle
    for pfad, wert in alle:
        assert isinstance(wert, str) and re.fullmatch(r"[0-9a-f]{64}", wert), pfad


# --- Rechtslage und Anfragevorlage -----------------------------------------------------------


def test_recht_fuer_alle_laender():
    assert set(CFG["recht"]) == set(LAENDER)
    assert all(isinstance(v, str) and v.strip() for v in CFG["recht"].values())


def test_anfrage_vorlage():
    v = CFG["anfrage_vorlage"]
    assert v["betreff"].strip()
    platzhalter = {f for _, f, _, _ in string.Formatter().parse(v["text"]) if f}
    assert platzhalter <= {"kommune", "stelle", "zusatz"}, platzhalter
    assert {"stelle", "zusatz"} <= platzhalter


# --- Datenlage --------------------------------------------------------------------------------


def _name(e: dict) -> str:
    return e.get("kommune", "?")


def test_datenlage_schluessel():
    for e in DATENLAGE:
        assert set(e) <= EINTRAG, f"{_name(e)}: unbekannt {set(e) - EINTRAG}"
        assert set(e.get("dauer") or {}) <= DAUER_BLOCK, f"{_name(e)}: dauer {set(e['dauer'])}"
        assert set(e.get("kontakt") or {}) <= KONTAKT, f"{_name(e)}: kontakt {set(e['kontakt'])}"


def test_kommune_in_der_datei_ihres_landes():
    """Je Land eine Datei: Jede Kommune steht in der ihres Landes (am Eintrag oder, mit `quelle`,
    das der Quelle)."""
    for pfad in sorted((CONFIG / "kommunen").glob("*.yaml")):
        for e in yaml.safe_load(pfad.read_text(encoding="utf-8")):
            land = e.get("land") or KURZZEIT[e["quelle"]]["land"]
            assert land == pfad.stem, f"{_name(e)}: Land {land}, aber in {pfad.name}"


def test_datenlage_kommunen_eindeutig():
    namen = [e["kommune"] for e in DATENLAGE]
    assert len(namen) == len(set(namen)), {n for n in namen if namen.count(n) > 1}


def test_datenlage_staende():
    for e in DATENLAGE:
        assert e.get("stand") is not None or e.get("dauer"), f"{_name(e)}: weder stand noch dauer"
        if e.get("stand") is not None:
            assert e["stand"] in site.STAND, f"{_name(e)}: stand {e['stand']!r}"
        if e.get("dauer"):
            assert e["dauer"].get("stand") in site.DAUER_STAND, f"{_name(e)}: dauer.stand"


def test_datenlage_lage_und_quelle():
    """Mit `quelle` liegt die Kommune in der Karte (Lage und Land aus der Quelle), sonst stehen
    Land und Lage am Eintrag."""
    for e in DATENLAGE:
        if e.get("quelle"):
            q = KURZZEIT.get(e["quelle"])
            assert q and q["status"] == "live", f"{_name(e)}: Quelle {e['quelle']!r}"
            assert e.get("stand") == "in_karte", f"{_name(e)}: mit Quelle in_karte"
            assert not {"land", "lon", "lat"} & set(e), f"{_name(e)}: Lage kommt aus der Quelle"
        else:
            assert e.get("stand") != "in_karte", f"{_name(e)}: in_karte ohne Quelle"
            assert e.get("land") in CFG["recht"], f"{_name(e)}: Land {e.get('land')!r}"
            for achse, (lo, hi) in DEUTSCHLAND.items():
                assert lo <= e[achse] <= hi, f"{_name(e)}: {achse} {e[achse]}"


def test_jede_kurzzeit_quelle_hat_eine_kommune():
    verknuepft = [e["quelle"] for e in DATENLAGE if e.get("quelle")]
    assert len(verknuepft) == len(set(verknuepft)), "eine Quelle an mehreren Kommunen"
    live = {c for c, q in KURZZEIT.items() if q["status"] == "live"}
    assert live <= set(verknuepft), f"ohne Datenlage-Eintrag: {live - set(verknuepft)}"


def _links_ok(links) -> bool:
    return isinstance(links, list) and bool(links) and all(
        isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and x[0].strip()
        and isinstance(x[1], str) and URL.match(x[1]) for x in links)


def test_datenlage_texte_und_links():
    """Rechtliche Aussagen nur mit Beleg: jeder Stand mit Text und Links als [Titel, URL]."""
    for e in DATENLAGE:
        if e.get("stand") is not None:
            assert (e.get("was") or "").strip(), f"{_name(e)}: was"
            assert _links_ok(e.get("links")), f"{_name(e)}: links"
            if not e.get("quelle"):
                for k in ("situation", "empfehlung", "weg"):
                    assert (e.get(k) or "").strip(), f"{_name(e)}: {k}"
        if e.get("dauer"):
            assert (e["dauer"].get("was") or "").strip(), f"{_name(e)}: dauer.was"
            assert _links_ok(e["dauer"].get("links")), f"{_name(e)}: dauer.links"


def test_datenlage_anfrage_und_kontakt():
    """Eine Anfrage nur mit Kontakt (Behörde aus FragDenStaat oder Suche dort); Zusatz und
    angefragte Stelle nur mit Anfrage."""
    for e in DATENLAGE:
        k = e.get("kontakt")
        if k:
            assert k.get("fds") or k.get("fds_suche"), f"{_name(e)}: Kontakt ohne FragDenStaat"
            if k.get("fds"):
                assert URL.match(k["fds"]) and k.get("name"), f"{_name(e)}: Kontakt"
        if "anfrage" in e:
            assert isinstance(e["anfrage"], bool), f"{_name(e)}: anfrage ja/nein"
        if e.get("anfrage"):
            assert k, f"{_name(e)}: Anfrage ohne Kontakt"
        if e.get("anfrage_zusatz") or e.get("anfrage_an"):
            assert e.get("anfrage"), f"{_name(e)}: Zusatz oder Stelle ohne Anfrage"
