"""Quellen ohne Lizenz in den Kartendaten beider Familien (CLAUDE.md, „Quellen ohne Lizenz“):
`lizenzen[].ohne_lizenz` nur dort, wo die Quelldatei es angibt – die Kartendaten der übrigen
Quellen bleiben gleich."""

from datetime import date

from zaehlkarte.config import Pfade
from zaehlkarte.dauer.site import _lizenzen as dauer_lizenzen
from zaehlkarte.lizenz import ohne_lizenz
from zaehlkarte.site import _lizenzen

OHNE = {"herausgegeben": "als PDF auf der\n  Website der Stadt", "geprueft": date(2026, 11, 14)}
ERWARTET = {"herausgegeben": "als PDF auf der Website der Stadt", "geprueft": "2026-11-14"}
LINK = "https://example.org/zaehlung.pdf"


def test_nur_wo_angegeben():
    assert ohne_lizenz({"lizenz": "CC0 1.0"}) == {}
    assert ohne_lizenz({"ohne_lizenz": OHNE}) == {"ohne_lizenz": ERWARTET}


def test_kurzzeit_quelle(tmp_path):
    q = {"code": "kevelaer", "name": "Kevelaer", "traeger": "Stadt Kevelaer", "portal": LINK,
         "ohne_lizenz": OHNE}
    (lz,) = _lizenzen(q, Pfade(pipeline=tmp_path, repo=tmp_path))
    assert lz["lizenz"] is None and lz["lizenz_url"] is None
    assert lz["herkunft_url"] == LINK and lz["ohne_lizenz"] == ERWARTET


def test_kurzzeit_lieferungen(tmp_path):
    q = {"code": "stadt", "name": "Stadt", "lieferungen": [
        {"code": "a", "titel": "offen", "lizenz": "CC0 1.0",
         "lizenz_url": "https://creativecommons.org/publicdomain/zero/1.0/deed.de"},
        {"code": "b", "titel": "auf Anfrage", "herkunft_url": LINK, "ohne_lizenz": OHNE},
    ]}
    offen, anfrage = _lizenzen(q, Pfade(pipeline=tmp_path, repo=tmp_path))
    assert "ohne_lizenz" not in offen and offen["lizenz"] == "CC0 1.0"
    assert anfrage["ohne_lizenz"] == ERWARTET and anfrage["herkunft_url"] == LINK


def test_dauer_quelle():
    (lz,) = dauer_lizenzen({"code": "neuss", "name": "Neuss", "portal": LINK, "ohne_lizenz": OHNE})
    assert lz["lizenz"] is None and lz["ohne_lizenz"] == ERWARTET
    (mit,) = dauer_lizenzen({"code": "bonn_rad", "name": "Bonn", "lizenz": "CC0 1.0"})
    assert "ohne_lizenz" not in mit
