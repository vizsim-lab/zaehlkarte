"""Die echte Konfiguration (pipeline/config/, Aufbau in config/README.md) gegen die Regeln aus
CLAUDE.md: Ein Tippfehler oder eine vergessene Angabe fällt im PR auf – nicht erst beim Bau, in der
Karte oder gar nicht (ein unbekannter optionaler Schlüssel würde sonst still zu `None`, eine Datei
am falschen Ort still übergangen).

Neue Regeln kommen hierher.
"""

from __future__ import annotations

import re
import string
from datetime import date

import pytest
import yaml

from zaehlkarte import adapters, datenlage, fetch
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

EINTRAG = {"ags", "name", "lage", "kontakt", "kurzzeit", "dauer"}
BLOCK = {"kurzzeit": {"stand", "quellen", "was", "situation", "empfehlung", "weg", "anfrage",
                      "links"},
         "dauer": {"stand", "quellen", "was", "situation", "links"}}
ANFRAGE = {"an", "zusatz"}
KONTAKT = {"name", "email", "fds", "fds_suche"}  # Funktionsadressen aus FragDenStaat
EBENEN = {"land", "bund"}  # `ebene` einer Quelle, die keine Kommune betreibt


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


def _ohne_lizenz_ok(x: dict, herkunft: str | None) -> bool:
    """Quelle bzw. Lieferung ohne Lizenz (CLAUDE.md, „Quellen ohne Lizenz“): wie die Kommune die
    Werte herausgegeben hat, der Tag der Prüfung (weder Lizenz noch Bedingungen) und der Link zum
    Original – und keine Lizenzangabe daneben."""
    o = x.get("ohne_lizenz")
    return (isinstance(o, dict) and set(o) == {"herausgegeben", "geprueft"}
            and bool(str(o["herausgegeben"] or "").strip()) and _datum_bis_heute(o["geprueft"])
            and "lizenz" not in x and "lizenz_url" not in x and bool(URL.match(herkunft or "")))


def ohne_lizenz(q: dict) -> bool:
    """Die Quelle oder eine ihrer Lieferungen hat keine Lizenz."""
    return "ohne_lizenz" in q or any("ohne_lizenz" in lf for lf in q.get("lieferungen", []))


@pytest.mark.parametrize("quelle", LIVE, ids=_id)
def test_lizenz_je_quelle(quelle):
    """Eine Lizenzangabe an der Quelle oder je Lieferung – oder, wo die Kommune keine Lizenz
    genannt hat, der Block `ohne_lizenz` mit Link zum Original (nie beides); dazu die Lizenz der
    Lage, wo sie aus OpenStreetMap kommt."""
    _, code, q = quelle
    if "lieferungen" in q:
        assert q["lieferungen"], f"{code}: keine Lieferung"
        for lf in q["lieferungen"]:
            assert _lizenz_ok(lf) or _ohne_lizenz_ok(lf, lf.get("herkunft_url")), (
                f"{code}/{lf.get('code')}: Lizenz und Lizenz-URL oder ohne_lizenz mit herkunft_url")
        assert "ohne_lizenz" not in q, f"{code}: ohne_lizenz je Lieferung"
    else:
        assert _lizenz_ok(q) or _ohne_lizenz_ok(q, q.get("portal")), (
            f"{code}: Lizenz und Lizenz-URL oder ohne_lizenz mit portal")
    if "geokodierung" in q:
        assert _lizenz_ok(q["geokodierung"]), f"{code}: Lizenz der Geokodierung"


def test_ohne_lizenz_pruefung():
    """Die Prüfung selbst an Beispielen: vollständig und mit Link zum Original, nie neben einer
    Lizenz, der Tag der Prüfung nicht in der Zukunft."""
    gut = {"ohne_lizenz": {"herausgegeben": "PDF auf der Website der Stadt",
                           "geprueft": date(2026, 11, 14)}}
    link = "https://example.org/zaehlung.pdf"
    assert _ohne_lizenz_ok(gut, link)
    assert not _ohne_lizenz_ok(gut, None), "ohne Link zum Original"
    assert not _ohne_lizenz_ok({**gut, "lizenz": "CC BY 4.0"}, link), "neben einer Lizenz"
    for o in ({"herausgegeben": " ", "geprueft": date(2026, 11, 14)},
              {"herausgegeben": "PDF", "geprueft": date(2999, 1, 1)},
              {"herausgegeben": "PDF"}):
        assert not _ohne_lizenz_ok({"ohne_lizenz": o}, link), o
    assert ohne_lizenz({"lieferungen": [{"lizenz": "CC0 1.0"}, gut]})
    assert not ohne_lizenz({"lizenz": "CC0 1.0"})


@pytest.mark.parametrize("quelle", [x for x in LIVE if x[0] == "dauer"], ids=_id)
def test_lizenz_mit_einschraenkung_nur_mit_hinweis(quelle):
    """Lizenzen mit Einschränkung (nicht kommerziell, Nutzungsbeschränkung) stehen mit einem
    Hinweis an der Quelle, der die Lizenz erklärt (Seitenleiste der Dauerzählstellen)."""
    _, code, q = quelle
    lizenz = q.get("lizenz") or ""
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


# --- Datenlage ---------------------------------------------------------------------------------


def _name(e: dict) -> str:
    return e.get("name", "?")


def _bloecke(e: dict):
    return [(f, e[f]) for f in ("kurzzeit", "dauer") if e.get(f)]


def test_datenlage_schluessel():
    for e in DATENLAGE:
        assert set(e) <= EINTRAG, f"{_name(e)}: unbekannt {set(e) - EINTRAG}"
        assert _bloecke(e), f"{_name(e)}: weder kurzzeit noch dauer"
        for f, b in _bloecke(e):
            assert set(b) <= BLOCK[f], f"{_name(e)}: {f} {set(b) - BLOCK[f]}"
        assert set(e.get("kontakt") or {}) <= KONTAKT, f"{_name(e)}: kontakt {set(e['kontakt'])}"


def test_gemeindeschluessel():
    """Schlüssel der Kommune: der amtliche Gemeindeschlüssel (8 Ziffern), bei Kreisen der
    Kreisschlüssel (5 Ziffern) – eindeutig; das Land steckt in den ersten beiden Ziffern."""
    schluessel = [e["ags"] for e in DATENLAGE]
    for e in DATENLAGE:
        assert isinstance(e["ags"], str) and re.fullmatch(r"\d{5}|\d{8}", e["ags"]), _name(e)
        assert e["ags"][:2] in datenlage.LAND, f"{_name(e)}: Land {e['ags'][:2]}"
    assert len(schluessel) == len(set(schluessel)), {a for a in schluessel
                                                     if schluessel.count(a) > 1}


def test_kommune_in_der_datei_ihres_landes():
    """Je Land eine Datei: jede Kommune steht in der ihres Landes (laut Gemeindeschlüssel)."""
    for pfad in sorted((CONFIG / "kommunen").glob("*.yaml")):
        for e in yaml.safe_load(pfad.read_text(encoding="utf-8")):
            land = datenlage.LAND[e["ags"][:2]]
            assert land == pfad.stem, f"{_name(e)}: Land {land}, aber in {pfad.name}"


def test_datenlage_kommunen_eindeutig():
    namen = [e["name"] for e in DATENLAGE]
    assert len(namen) == len(set(namen)), {n for n in namen if namen.count(n) > 1}


def test_datenlage_staende():
    """Eine Liste von Ständen für beide Familien (datenlage.STAND)."""
    for e in DATENLAGE:
        for f, b in _bloecke(e):
            assert b.get("stand") in datenlage.STAND, f"{_name(e)}: {f}.stand {b.get('stand')!r}"


def test_datenlage_lage():
    for e in DATENLAGE:
        lage = e.get("lage")
        assert isinstance(lage, list) and len(lage) == 2, f"{_name(e)}: lage [Länge, Breite]"
        for wert, (lo, hi) in zip(lage, DEUTSCHLAND.values(), strict=True):
            assert lo <= wert <= hi, f"{_name(e)}: lage {lage}"


def test_quellen_der_kommunen():
    """Kommune und Quelle sind ausdrücklich verknüpft (`quellen` je Familie), nur Quellen der
    Familie, die in der Karte sind: „in der Karte“ immer mit Quellen, und nur mit solchen mit
    Lizenz; „ohne Lizenz“ mit Quellen, sobald die Werte in der Karte sind, und nur mit solchen ohne
    Lizenz; jeder andere Stand ohne Quellen. Jede Kurzzeit-Quelle gehört zu genau einer Kommune,
    jede Dauer-Quelle zu mindestens einer (Bündel wie MobiData BW zu mehreren) – außer Quellen
    des Landes oder des Bundes (`ebene` in der Quelldatei): Sie gehören zu keiner Kommune."""
    alle = {"kurzzeit": KURZZEIT, "dauer": DAUER}
    live = {f: {c for c, q in qs.items() if q["status"] == "live"} for f, qs in alle.items()}
    verknuepft: dict[str, list[str]] = {"kurzzeit": [], "dauer": []}
    for e in DATENLAGE:
        for f, b in _bloecke(e):
            qs = b.get("quellen") or []
            assert set(qs) <= live[f], f"{_name(e)}: {f}.quellen {set(qs) - live[f]}"
            ohne = [c for c in qs if ohne_lizenz(alle[f][c])]
            if b["stand"] == "in_karte":
                assert qs, f"{_name(e)}: {f} in_karte ohne quellen"
                assert not ohne, f"{_name(e)}: {f} in_karte, aber ohne Lizenz: {ohne} (ohne_lizenz)"
            elif b["stand"] == "ohne_lizenz":
                mit = set(qs) - set(ohne)
                assert not mit, f"{_name(e)}: {f} ohne_lizenz, aber mit Lizenz: {mit}"
            else:
                assert not qs, f"{_name(e)}: {f}.quellen nur bei in_karte oder ohne_lizenz"
            verknuepft[f] += qs
    k = verknuepft["kurzzeit"]
    assert len(k) == len(set(k)), "eine Kurzzeit-Quelle an mehreren Kommunen"
    assert set(k) == live["kurzzeit"], f"ohne Kommune: {live['kurzzeit'] - set(k)}"
    ohne_kommune = {c for c, q in DAUER.items() if q.get("ebene") in EBENEN}
    assert not set(verknuepft["dauer"]) & ohne_kommune, "Quelle des Landes/Bundes an einer Kommune"
    assert set(verknuepft["dauer"]) == live["dauer"] - ohne_kommune, (
        f"ohne Kommune: {live['dauer'] - ohne_kommune - set(verknuepft['dauer'])}")


@pytest.mark.parametrize("quelle", LIVE, ids=_id)
def test_ebene(quelle):
    """`ebene` nur bei Dauerzählstellen, die keine Kommune betreibt: Land oder Bund."""
    familie, code, q = quelle
    if "ebene" in q:
        assert familie == "dauer" and q["ebene"] in EBENEN, f"{code}: ebene {q['ebene']!r}"


def _links_ok(links) -> bool:
    return isinstance(links, list) and bool(links) and all(
        isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and x[0].strip()
        and isinstance(x[1], str) and URL.match(x[1]) for x in links)


def test_datenlage_texte_und_links():
    """Rechtliche Aussagen nur mit Beleg: jeder Stand mit Text und Links als [Titel, URL]; bei
    Kurzzeitzählungen außerhalb der Karte dazu Lage, Empfehlung und Weg."""
    for e in DATENLAGE:
        for f, b in _bloecke(e):
            assert (b.get("was") or "").strip(), f"{_name(e)}: {f}.was"
            assert _links_ok(b.get("links")), f"{_name(e)}: {f}.links"
        k = e.get("kurzzeit")
        if k and k["stand"] != "in_karte":
            for x in ("situation", "empfehlung", "weg"):
                assert (k.get(x) or "").strip(), f"{_name(e)}: kurzzeit.{x}"


def test_datenlage_anfrage_und_kontakt():
    """Eine Anfrage nur bei den Kurzzeitzählungen und nur mit Kontakt (Behörde aus FragDenStaat
    oder Suche dort); `an` ist die angefragte Stelle, wo es keine Stadt ist."""
    for e in DATENLAGE:
        k = e.get("kontakt")
        if k:
            assert k.get("fds") or k.get("fds_suche"), f"{_name(e)}: Kontakt ohne FragDenStaat"
            if k.get("fds"):
                assert URL.match(k["fds"]) and k.get("name"), f"{_name(e)}: Kontakt"
        a = (e.get("kurzzeit") or {}).get("anfrage")
        if a is not None:
            assert isinstance(a, dict) and set(a) <= ANFRAGE, f"{_name(e)}: anfrage {a!r}"
            assert k, f"{_name(e)}: Anfrage ohne Kontakt"
