"""CKAN-Portale ohne API: DCAT-Dokument, HTML-Seite, Suche (synthetische Seiten im Aufbau von
CKAN 2.10/2.11 und ckanext-dcat, wie bei Moers, Olpe und Aachen im November 2026)."""

from __future__ import annotations

import json
from datetime import date

import pytest
import requests

from zaehlkarte import abruf, ckan

KONTEXT = {"dcat": "http://www.w3.org/ns/dcat#", "dct": "http://purl.org/dc/terms/",
           "xsd": "http://www.w3.org/2001/XMLSchema#"}
DS = "https://p.example/dataset/d487"


def dcat_kompakt() -> dict:
    zeit = {"@type": "xsd:dateTime"}
    return {"@context": KONTEXT, "@graph": [
        {"@id": f"{DS}/resource/b", "@type": "dcat:Distribution",
         "dcat:accessURL": {"@id": f"{DS}/resource/b/download/zweite.txt"},
         "dct:format": "TXT", "dct:title": "Zweite Messung",
         "dct:issued": zeit | {"@value": "2022-08-16T09:04:55"},
         "dct:modified": zeit | {"@value": "2022-08-16T09:04:55"},
         "dct:license": {"@id": "http://dcat-ap.de/def/licenses/dl-zero-de/2.0"}},
        {"@id": DS, "@type": "dcat:Dataset", "dct:title": "Verkehrszählungen 2021 (Stadt Moers)",
         "dcat:distribution": [{"@id": f"{DS}/resource/b"}, {"@id": f"{DS}/resource/a"}]},
        {"@id": f"{DS}/resource/a", "@type": "dcat:Distribution",
         "dcat:accessURL": {"@id": f"{DS}/resource/a"},
         "dcat:downloadURL": {"@id": f"{DS}/resource/a/download/erste.txt"},
         "dct:format": {"@id": "http://publications.europa.eu/resource/authority/file-type/CSV"},
         "dct:title": "Erste Messung", "dct:issued": zeit | {"@value": "2015-10-08T14:47:54"}},
        {"@id": "_:N1", "@type": "vcard:Organization"},
    ]}


def test_dcat_kompakt():
    p = ckan.aus_dcat(dcat_kompakt(), "verkehrszahlung-in-moers-2021")
    assert p["name"] == "verkehrszahlung-in-moers-2021"
    assert p["title"] == "Verkehrszählungen 2021 (Stadt Moers)"
    assert p["license_id"] == "http://dcat-ap.de/def/licenses/dl-zero-de/2.0"
    # nach Datum (wie die Reihenfolge im Portal); downloadURL vor accessURL; Format aus der IRI
    assert [(r["name"], r["url"].rsplit("/", 1)[-1], r["format"]) for r in p["resources"]] == [
        ("Erste Messung", "erste.txt", "CSV"), ("Zweite Messung", "zweite.txt", "TXT")]
    assert p["resources"][1]["last_modified"] == "2022-08-16T09:04:55"
    assert p["resources"][0]["seite"] == f"{DS}/resource/a" and p["resources"][0]["id"] == "a"


def test_dcat_expandiert_und_ohne_datensatz():
    dok = [{"@id": DS, "@type": ["http://www.w3.org/ns/dcat#Dataset"],
            "http://purl.org/dc/terms/title": [{"@value": "Verkehrsmessungen K18"}],
            "http://www.w3.org/ns/dcat#distribution": [{"@id": f"{DS}/resource/a"}]},
           {"@id": f"{DS}/resource/a", "@type": ["http://www.w3.org/ns/dcat#Distribution"],
            "http://www.w3.org/ns/dcat#accessURL": [{"@id": f"{DS}/resource/a/download/k18.json"}],
            "http://purl.org/dc/terms/title": [{"@value": "k18.json"}]}]
    p = ckan.aus_dcat(dok, "verkehrsmessungen-k18")
    assert p["title"] == "Verkehrsmessungen K18" and p["license_id"] is None
    assert [r["url"] for r in p["resources"]] == [f"{DS}/resource/a/download/k18.json"]
    with pytest.raises(ValueError):
        ckan.aus_dcat({"@context": KONTEXT, "@graph": []}, "leer")


K18 = "/dataset/verkehrsmessungen-k18/resource"
DATENSATZ_HTML = f"""<!DOCTYPE html><html lang="de">
<head><title>Verkehrsmessungen K18 - Datensatz</title></head>
<body><header><h1><a class="logo" href="/">Open Data Portal</a></h1></header>
<aside><h1 class="heading">Kreisstadt Olpe</h1>
 <section class="module module-narrow module-shallow license">
  <h2 class="module-heading">Lizenz</h2>
  <p class="module-content"><a href="https://www.govdata.de/dl-de/by-2-0"
   rel="dc:rights">Datenlizenz
   Deutschland Namensnennung 2.0</a></p></section></aside>
<article class="module"><h1>
  Verkehrsmessungen K18 &amp; Umgebung
</h1>
<ul class="resource-list">
 <li class="resource-item" data-id="459a">
  <a class="heading" href="{K18}/459a" title="verkehrsdaten_K18 &amp; mehr.json">
   verkehrsdaten_K18…<span class="format-label" property="dc:format"
   data-format="json">JSON</span></a>
  <p class="description">Verkehrsmessungen vom 06.08.2025 - 13.08.2025</p>
  <div class="dropdown btn-group"><ul class="dropdown-menu">
   <li><a class="dropdown-item" href="{K18}/459a">Vorschau</a></li>
   <li><a class="dropdown-item resource-url-analytics"
     href="https://p.example/dataset/d6ee/resource/459a/download/k18.json"
     target="_blank">Herunterladen</a></li>
  </ul></div>
 </li>
 <li class="resource-item" data-id="77">
  <a class="heading" href="{K18}/77" title="Nur eine Ansicht">Ansicht</a>
 </li>
 <li class="resource-item" data-id="88">
  <a class="heading" href="{K18}/88" title="Beschreibung">x<span class="format-label"
   data-format="pdf">PDF</span></a>
  <ul><li><a class="dropdown-item resource-url-analytics"
   href="https://p.example/b.pdf">Herunterladen</a></li></ul>
 </li>
</ul></article>
<section class="additional-info"><table><tr>
<th scope="row" class="dataset-label">Letzte Fortführung</th>
<td class="dataset-details">13.08.2025</td></tr></table></section></body></html>"""


def test_html_datensatz():
    p = ckan.aus_html(DATENSATZ_HTML, "verkehrsmessungen-k18", "https://p.example")
    assert p["title"] == "Verkehrsmessungen K18 & Umgebung"  # nicht der Name des Portals
    assert (p["license_url"], p["license_title"]) == (
        "https://www.govdata.de/dl-de/by-2-0", "Datenlizenz Deutschland Namensnennung 2.0")
    # in der Reihenfolge der Seite; Ressourcen ohne Download (nur Ansicht) fehlen
    assert [(r["id"], r["name"], r["format"], r["url"]) for r in p["resources"]] == [
        ("459a", "verkehrsdaten_K18 & mehr.json", "json",
         "https://p.example/dataset/d6ee/resource/459a/download/k18.json"),
        ("88", "Beschreibung", "pdf", "https://p.example/b.pdf")]
    assert p["resources"][0]["seite"] == f"https://p.example{K18}/459a"
    assert ckan.lies_seite(DATENSATZ_HTML).zeilen == {"Letzte Fortführung": "13.08.2025"}


def suchseite(namen: list[str], weiter: int | None = None) -> str:
    treffer = "".join(
        f'<li class="dataset-item"><div class="dataset-content"><h2 class="dataset-heading">'
        f'<a href="{n}" title="T">T</a></h2></div>'
        f'<ul class="dataset-resources"><li><a href="{n}" class="badge">JSON</a></li></ul></li>'
        for n in namen)
    seiten = (f'<ul class="pagination"><li><a href="/dataset/?q=Verkehrsmessung&amp;page={weiter}">'
              f'{weiter}</a></li></ul>' if weiter else "")
    return (f'<html><body><h1> {len(namen)} Datensätze gefunden </h1><a href="/dataset/">Alle</a>'
            f'<a href="/dataset/?tags=Verkehr">Verkehr</a><ul class="dataset-list">{treffer}</ul>'
            f'{seiten}</body></html>')


class Antwort:
    def __init__(self, inhalt: str | bytes = b"", status: int = 200):
        self.content = inhalt.encode() if isinstance(inhalt, str) else inhalt
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)

    def json(self):
        return json.loads(self.content)


@pytest.fixture
def portal(monkeypatch):
    """abruf.hole durch Antworten je URL ersetzen (404 sonst); protokolliert die Abrufe."""
    seiten: dict[str, Antwort] = {}
    abrufe: list[str] = []

    def hole(url, params=None, **k):
        voll = requests.Request("GET", url, params=params).prepare().url
        abrufe.append(voll)
        r = seiten.get(voll, Antwort(status=404))
        r.raise_for_status()
        return r

    monkeypatch.setattr(abruf, "hole", hole)
    return seiten, abrufe


def test_suche_alle_seiten_und_begriffe(portal):
    seiten, abrufe = portal
    q = "https://p.example/dataset/?q=Verkehrsmessung"
    seiten[q] = Antwort(suchseite(["/dataset/verkehrsmessung-a", "/dataset/verkehrsmessung-b"], 2))
    seiten[q + "&page=2"] = Antwort(suchseite(["https://p.example/dataset/verkehrsmessung-%C3%A4"]))
    seiten[q + "en"] = Antwort(suchseite(["/dataset/verkehrsmessung-b",
                                          "/dataset/verkehrsmessungen-c"]))
    namen = ckan.suche("https://p.example/", ["Verkehrsmessung", "Verkehrsmessungen"])
    assert namen == ["verkehrsmessung-a", "verkehrsmessung-b", "verkehrsmessung-ä",
                     "verkehrsmessungen-c"]
    assert abrufe == [q, q + "&page=2", q + "en"]  # keine Seite 2 ohne Link darauf


def test_paket_dcat_sonst_html(portal):
    seiten, abrufe = portal
    seiten["https://p.example/dataset/mit.jsonld"] = Antwort(json.dumps(dcat_kompakt()))
    assert ckan.paket("https://p.example", "mit")["title"].startswith("Verkehrszählungen 2021")
    # Portal ohne DCAT-Dokument (Aachen): 404 -> HTML; beim nächsten Datensatz gleich HTML
    seiten["https://q.example/dataset/eins"] = Antwort(DATENSATZ_HTML)
    seiten["https://q.example/dataset/zwei"] = Antwort(DATENSATZ_HTML)
    assert ckan.paket("https://q.example", "eins")["license_url"].endswith("by-2-0")
    ckan.paket("https://q.example", "zwei")
    assert abrufe[1:] == ["https://q.example/dataset/eins.jsonld", "https://q.example/dataset/eins",
                          "https://q.example/dataset/zwei"]
    with pytest.raises(requests.HTTPError):  # gibt es den Datensatz gar nicht: Fehler
        ckan.paket("https://q.example", "fehlt", wege=("html",))


def test_paket_gesperrter_weg(monkeypatch, portal):
    seiten, _ = portal

    def hole(url, **k):
        if url.endswith(".jsonld"):
            raise abruf.Gesperrt(url)
        return seiten[url]

    seiten["https://r.example/dataset/x"] = Antwort(DATENSATZ_HTML)
    monkeypatch.setattr(abruf, "hole", hole)
    assert ckan.paket("https://r.example", "x")["resources"][0]["id"] == "459a"


def test_ressource_stand_und_datum(portal):
    seiten, _ = portal
    tabelle = ("<table><tr><th scope=\"row\">Daten wurden zuletzt aktualisiert</th>"
               "<td>14. November 2026</td></tr><tr><th scope=\"row\">Erstellt</th>"
               "<td>13. November 2026</td></tr></table>")
    seiten["https://p.example/r/1"] = Antwort(f"<html><body>{tabelle}</body></html>")
    seiten["https://p.example/r/2"] = Antwort('<table><tr><th scope="row">Created</th>'
                                              '<td>March 3, 2026</td></tr></table>')
    seiten["https://p.example/r/3"] = Antwort("<p>nichts</p>")
    assert ckan.ressource_stand("https://p.example/r/1") == date(2026, 11, 14)
    assert ckan.ressource_stand("https://p.example/r/2") == date(2026, 3, 3)
    assert ckan.ressource_stand("https://p.example/r/3") is None
    assert ckan.datum("1. März 2026") == date(2026, 3, 1)
    assert ckan.datum("2026-11-14T08:42:20.091446") == date(2026, 11, 14)
    assert ckan.datum("irgendwann") is None
