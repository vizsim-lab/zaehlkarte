"""Abrufe der Pipeline: robots.txt nach RFC 9309, Crawl-delay, Ausnahmen (ohne Netz)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import requests

from zaehlkarte import abruf

ROBOTS_TEXT = abruf._robots_text  # das echte (conftest ersetzt es je Test)

# wie opendata.muenchen.de (gekürzt): API gesperrt, Crawl-delay, eigene Gruppe für KI-Crawler
MUENCHEN = """User-agent: *

# Bisherige Regeln
Disallow: /dataset/rate/
Disallow: /api/
Crawl-delay: 10

# Historische Ansichten
Disallow: /*?activity_id=
Disallow: /*?*&activity_id=

User-agent: ClaudeBot
User-agent: GPTBot
Disallow: /
"""


def test_gruppe_platzhalter_und_crawl_delay():
    r = abruf.Regeln(MUENCHEN)
    assert not r.erlaubt("https://m.example/api/3/action/package_search?q=rad")
    assert r.erlaubt("https://m.example/dataset/raddauerzaehlstellen.jsonld")
    assert r.erlaubt("https://m.example/dataset/?q=rad&page=2")
    assert not r.erlaubt("https://m.example/dataset/x?activity_id=5")
    assert not r.erlaubt("https://m.example/dataset/x?a=1&activity_id=5")
    assert r.erlaubt("https://m.example/robots.txt")
    assert r.abstand == 10
    # die Gruppe der KI-Crawler gilt nicht für die Pipeline (Kennung zaehlkarte-pipeline)
    assert not abruf.Regeln(MUENCHEN, kennung="ClaudeBot").erlaubt("https://m.example/dataset/x")


def test_laengste_regel_gewinnt_gleichstand_erlaubt():
    r = abruf.Regeln("User-agent: *\nDisallow: /api/\nAllow: /api/3/action/package_show\n"
                     "Disallow: /a\nAllow: /a\n")
    assert r.erlaubt("https://x.example/api/3/action/package_show?id=1")
    assert not r.erlaubt("https://x.example/api/3/action/package_search")
    assert r.erlaubt("https://x.example/a/b")  # gleich lang: Allow


def test_stern_am_anfang_und_dollar():
    # wie download.geofabrik.de: Regeln ohne führenden Schrägstrich
    r = abruf.Regeln("User-agent: *\nDisallow: *.osm.pbf\nDisallow: /*.gz$\n")
    assert not r.erlaubt("https://g.example/europe/germany/hamburg-latest.osm.pbf")
    assert not r.erlaubt("https://g.example/x.gz")
    assert r.erlaubt("https://g.example/x.gz.html")
    assert r.erlaubt("https://g.example/europe/germany.html")


def test_eigene_gruppe_gross_klein_und_leeres_disallow():
    text = "User-agent: *\nDisallow: /\n\nUser-Agent: Zaehlkarte-Pipeline\nDisallow:\n"
    assert abruf.Regeln(text).erlaubt("https://x.example/alles")
    assert not abruf.Regeln(text, kennung="anderer-bot").erlaubt("https://x.example/alles")


def test_gruppen_derselben_kennung_gelten_zusammen():
    r = abruf.Regeln("User-agent: *\nDisallow: /a/\nCrawl-delay: 2\n\n"
                     "User-agent: *\nDisallow: /b/\nCrawl-delay: 5\n")
    assert not r.erlaubt("https://x.example/a/1") and not r.erlaubt("https://x.example/b/1")
    assert r.abstand == 5


def test_prozent_kodierung_vereinheitlicht():
    r = abruf.Regeln("User-agent: *\nDisallow: /dataset/%C3%A4\n")
    assert not r.erlaubt("https://x.example/dataset/ä-zählung")
    assert r.erlaubt("https://x.example/dataset/a")


class Antwort:
    def __init__(self, status=200, inhalt=b"", ort=None):
        self.status_code, self.content = status, inhalt
        self.ok = status < 400
        self.headers = {"Location": ort} if ort else {}
        self.is_redirect = ort is not None

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code), response=self)

    def iter_content(self, n):
        yield self.content

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


@pytest.fixture
def netz(monkeypatch):
    """Antworten je URL; protokolliert jede Anfrage (Methode, URL samt Parametern)."""
    antworten: dict[str, Antwort] = {}
    anfragen: list[tuple[str, str]] = []

    def anfrage(methode):
        def f(url, params=None, **k):
            voll = requests.Request("GET", url, params=params).prepare().url
            anfragen.append((methode, voll))
            return antworten.get(voll, Antwort(404))
        return f

    monkeypatch.setattr(requests, "get", anfrage("GET"))
    monkeypatch.setattr(requests, "post", anfrage("POST"))
    return antworten, anfragen


def test_robots_txt_status(monkeypatch, netz):
    antworten, _ = netz
    monkeypatch.setattr(abruf, "_robots_text", ROBOTS_TEXT)
    monkeypatch.setattr(abruf.time, "sleep", lambda s: None)
    antworten["https://bom.example/robots.txt"] = Antwort(
        200, "﻿User-agent: *\nDisallow: /".encode())
    antworten["https://zu.example/robots.txt"] = Antwort(403)
    antworten["https://voll.example/robots.txt"] = Antwort(429)
    antworten["https://kaputt.example/robots.txt"] = Antwort(503)
    assert not abruf.regeln("https://bom.example/x").erlaubt("https://bom.example/x")
    assert abruf.regeln("https://ohne.example/x").alles is True  # 404: keine robots.txt
    assert abruf.regeln("https://zu.example/x").alles is True  # 4xx laut RFC 9309: erlaubt
    assert abruf.regeln("https://voll.example/x").alles is False
    assert abruf.regeln("https://kaputt.example/x").alles is False


def robots(monkeypatch, **texte: str):
    """robots.txt je Host (ohne Angabe: keine)."""
    monkeypatch.setattr(abruf, "_robots_text", lambda basis: (
        (200, texte[basis.split("//")[1].split(".")[0]])
        if basis.split("//")[1].split(".")[0] in texte else (404, "")))


def test_gesperrt_ohne_anfrage(monkeypatch, netz):
    _, anfragen = netz
    robots(monkeypatch, portal="User-agent: *\nDisallow: /api/\n")
    with pytest.raises(abruf.Gesperrt):
        abruf.hole("https://portal.example/api/3/action/package_show", params={"id": "x"})
    assert anfragen == []


def test_ausnahme_aus_sources_yaml(monkeypatch, netz):
    antworten, anfragen = netz
    robots(monkeypatch, portal="User-agent: *\nDisallow: /api/\n")
    antworten["https://portal.example/api/explore/x?limit=1"] = Antwort(200, b"[]")
    abruf.ausnahmen_setzen({"potsdam": {"robots_ausnahme": {
        "urls": ["https://portal.example/api/explore/"],
        "grund": "kein anderer\n  Weg zu den Daten"}}, "andere": {}})
    assert abruf.hole("https://portal.example/api/explore/x", params={"limit": 1}).content == b"[]"
    with pytest.raises(abruf.Gesperrt):  # nur die genannten URL-Anfänge
        abruf.hole("https://portal.example/api/3/action/package_show")
    assert abruf.bericht() == [
        "robots.txt: 1 Abrufe für potsdam trotz Sperre (https://portal.example/api/explore/) – "
        "Ausnahme laut sources.yaml: kein anderer Weg zu den Daten"]


def test_weiterleitung_wird_geprueft(monkeypatch, netz):
    antworten, anfragen = netz
    robots(monkeypatch, ziel="User-agent: *\nDisallow: /privat/\n")
    antworten["https://start.example/a"] = Antwort(302, ort="https://ziel.example/privat/a")
    antworten["https://start.example/b"] = Antwort(301, ort="/c")
    antworten["https://start.example/c"] = Antwort(200, b"c")
    with pytest.raises(abruf.Gesperrt):
        abruf.hole("https://start.example/a")
    assert abruf.hole("https://start.example/b").content == b"c"
    assert anfragen == [("GET", "https://start.example/a"), ("GET", "https://start.example/b"),
                        ("GET", "https://start.example/c")]


def test_crawl_delay_je_host(monkeypatch, netz):
    antworten, _ = netz
    robots(monkeypatch, langsam="User-agent: *\nCrawl-delay: 10\n")
    uhr = [100.0]
    schlaf = []

    def sleep(s):
        schlaf.append(round(s, 3))
        uhr[0] += s

    monkeypatch.setattr(abruf.time, "monotonic", lambda: uhr[0])
    monkeypatch.setattr(abruf.time, "sleep", sleep)
    for url in ("https://langsam.example/1", "https://langsam.example/2",
                "https://schnell.example/1", "https://schnell.example/2"):
        antworten[url] = Antwort(200, b"x")
        abruf.hole(url)
        uhr[0] += 1.5  # die Anfrage selbst dauert
    assert schlaf == [8.5]  # nur der zweite Abruf desselben Hosts, nur die Restzeit
    assert abruf.bericht() == ["Crawl-delay eingehalten: langsam.example 8 s"]


def test_post_und_lade(tmp_path, netz):
    antworten, anfragen = netz
    antworten["https://overpass.example/api/interpreter"] = Antwort(200, b'{"elements": []}')
    antworten["https://daten.example/x.csv"] = Antwort(200, b"a;b\n1;2\n")
    r = abruf.hole("https://overpass.example/api/interpreter", daten={"data": "[out:json];"})
    assert r.content == b'{"elements": []}' and anfragen[0][0] == "POST"
    ziel = abruf.lade("https://daten.example/x.csv", tmp_path / "roh" / "x.csv")
    assert ziel.read_bytes() == b"a;b\n1;2\n" and not (tmp_path / "roh" / "x.csv.teil").exists()
    with pytest.raises(requests.HTTPError):
        abruf.lade("https://daten.example/fehlt.csv", tmp_path / "fehlt.csv")


# Netz nur über `abruf` (CLAUDE.md: nie `requests` direkt). Geprüft am Quelltext der Pipeline
# und ihrer Werkzeuge: keine Aufrufe von requests.get/post/… oder einer Sitzung an `abruf.hole`
# vorbei, keine anderen HTTP-Bibliotheken, kein curl/wget, keine URL direkt an pandas.
PIPELINE = Path(__file__).resolve().parents[1]
HTTP_VERBEN = {"get", "post", "put", "patch", "delete", "head", "options", "request"}
ANDERE_NETZMODULE = {"urllib.request", "http.client", "httpx", "aiohttp", "urllib3", "socket",
                     "pycurl", "ftplib"}
LESER = {"read_csv", "read_excel", "read_json", "read_html", "read_xml", "read_parquet",
         "ExcelFile", "urlretrieve"}


def _verstoesse(pfad: Path, basis: Path = PIPELINE) -> list[str]:
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    out = []
    for k in ast.walk(baum):
        if isinstance(k, ast.Import):
            out += [a.name for a in k.names if a.name in ANDERE_NETZMODULE]
        elif isinstance(k, ast.ImportFrom) and k.module in ANDERE_NETZMODULE:
            out.append(k.module)
        elif isinstance(k, ast.Constant) and isinstance(k.value, str):
            if re.match(r"(curl|wget)\b", k.value):
                out.append(k.value[:20])
        elif isinstance(k, ast.Call):
            f = k.func
            name = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value,
                                                                            ast.Name) else ""
            attr = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if attr in HTTP_VERBEN and (name == "requests" or "sitzung" in name
                                        or "session" in name.lower()):
                out.append(f"{name}.{attr}()")
            if (attr in LESER and k.args and isinstance(k.args[0], ast.Constant)
                    and str(k.args[0].value).startswith(("http://", "https://"))):
                out.append(f"{attr}(URL)")
    return [f"{pfad.relative_to(basis)}: {v}" for v in out]


def test_netz_nur_ueber_abruf():
    dateien = [p for p in sorted((PIPELINE / "src" / "zaehlkarte").rglob("*.py"))
               if p.name != "abruf.py"] + sorted((PIPELINE / "werkzeuge").glob("*.py"))
    assert len(dateien) > 30
    assert [v for p in dateien for v in _verstoesse(p)] == []


def test_netz_pruefung_erkennt_umwege(tmp_path):
    p = tmp_path / "x.py"
    p.write_text("import urllib.request\nimport requests\nimport pandas as pd\n"
                 "requests.get('https://a.example')\ns = requests.Session()\n"
                 "sitzung.post('https://a.example')\n"
                 "pd.read_csv('https://a.example/x.csv')\n"
                 "subprocess.run(['curl', '-O', 'https://a.example'])\n", encoding="utf-8")
    befunde = sorted(v.split(": ", 1)[1] for v in _verstoesse(p, tmp_path))
    assert befunde == sorted(["urllib.request", "requests.get()", "sitzung.post()",
                              "read_csv(URL)", "curl"])
