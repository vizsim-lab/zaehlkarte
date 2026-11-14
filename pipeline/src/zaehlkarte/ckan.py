"""CKAN-Portale ohne ihre API: Metadaten aus dem DCAT-Dokument oder der HTML-Seite.

Moers (offenesdatenportal.de), Olpe, Aachen und München sperren die CKAN-API (`/api/`) per
robots.txt für alle Robots; erlaubt sind die Datensatzseiten, ihr DCAT-Dokument (ckanext-dcat,
`/dataset/<name>.jsonld`), die Suchseite und die Downloads – mit Crawl-delay 10 Sekunden (Prüfung
November 2026, AGENTS.md „robots.txt und die Pipeline“). Alle Abrufe über `zaehlkarte.abruf`.

`paket(basis, name, wege)` liefert das Gerüst von `package_show`, soweit die Adapter es brauchen:
{"name", "title", "license_id", "license_url", "license_title",
 "resources": [{"id", "name", "url", "format", "last_modified", "created", "seite"}]}
- `dcat`: Titel, alle Ressourcen samt Datum (dct:modified, dct:issued), die Lizenz nur, wenn das
  Portal sie im DCAT-Dokument nennt (`license_id`, Olpe tut es nicht). Ressourcen nach Datum.
- `html`: Titel, Lizenz (Link und Name aus der Seitenleiste: `license_url`, `license_title`) und
  die Ressourcen in der Reihenfolge der Seite, ohne Datum – das steht auf der Seite der Ressource
  (`seite`, siehe `ressource_stand`). Die HTML-Seite mancher Portale zeigt nicht alle Ressourcen
  (offenesdatenportal.de) – dort `dcat`.
`suche(basis, begriffe)` -> Namen der Datensätze aus der HTML-Suche (alle Seiten je Begriff).
"""

from __future__ import annotations

import json
import re
import urllib.parse
from datetime import date
from html.parser import HTMLParser

import requests

from zaehlkarte import abruf

DCAT = "http://www.w3.org/ns/dcat#"
DCT = "http://purl.org/dc/terms/"
_OHNE: set[tuple[str, str]] = set()  # (Portal, Weg), die 404 lieferten – nicht noch einmal
MONATE = {m: i + 1 for i, m in enumerate(
    ["januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
     "oktober", "november", "dezember"])} | {m: i + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september",
     "october", "november", "december"])}


# ---------------------------------------------------------------- DCAT (JSON-LD)


def _iri(wert: str, ctx: dict) -> str:
    if ":" in wert:
        praefix, rest = wert.split(":", 1)
        if isinstance(ctx.get(praefix), str) and not rest.startswith("//"):
            return ctx[praefix] + rest
    return wert


def _knoten(dok: dict | list) -> dict[str, dict[str, list[str]]]:
    """JSON-LD (kompakt mit @context/@graph oder expandiert) -> {@id: {IRI: [Werte]}}; Werte
    sind Zeichenketten (Literale oder IRIs), @type steht unter "@type"."""
    ctx = dok.get("@context", {}) if isinstance(dok, dict) else {}
    ctx = ctx if isinstance(ctx, dict) else {}
    liste = (dok.get("@graph", [dok]) if isinstance(dok, dict) else dok) or []
    out: dict[str, dict[str, list[str]]] = {}
    for k in liste:
        n: dict[str, list[str]] = {}
        for schluessel, wert in k.items():
            if schluessel in ("@id", "@context"):
                continue
            werte = wert if isinstance(wert, list) else [wert]
            iri = "@type" if schluessel == "@type" else _iri(schluessel, ctx)
            for w in werte:
                if isinstance(w, dict):
                    w = _iri(w["@id"], ctx) if "@id" in w else w.get("@value")
                elif schluessel == "@type":
                    w = _iri(w, ctx)
                if w is not None:
                    n.setdefault(iri, []).append(str(w))
        out[k.get("@id", f"_:{len(out)}")] = n
    return out


def _erstes(n: dict, iri: str) -> str | None:
    return (n.get(iri) or [None])[0]


def aus_dcat(dok: dict | list, name: str) -> dict:
    """DCAT-Dokument eines Datensatzes -> Gerüst wie package_show (siehe oben)."""
    knoten = _knoten(dok)
    saetze = [n for n in knoten.values() if DCAT + "Dataset" in n.get("@type", [])]
    if len(saetze) != 1:
        raise ValueError(f"{name}: {len(saetze)} Datensätze im DCAT-Dokument")
    ds = saetze[0]
    ressourcen, lizenzen = [], [_erstes(ds, DCT + "license")]
    for rid in ds.get(DCAT + "distribution", []):
        v = knoten.get(rid, {})
        fmt = _erstes(v, DCT + "format") or ""
        if fmt.startswith("http"):  # Vokabular der EU: …/file-type/CSV
            fmt = fmt.rstrip("/").rsplit("/", 1)[-1]
        ressourcen.append({
            "id": rid.rstrip("/").rsplit("/", 1)[-1], "name": _erstes(v, DCT + "title"),
            "url": _erstes(v, DCAT + "downloadURL") or _erstes(v, DCAT + "accessURL"),
            "format": fmt or _erstes(v, DCAT + "mediaType") or "",
            "last_modified": _erstes(v, DCT + "modified"), "created": _erstes(v, DCT + "issued"),
            "seite": rid,
        })
        lizenzen.append(_erstes(v, DCT + "license"))
    ressourcen.sort(key=lambda r: (r["created"] or "", r["url"] or ""))
    return {"name": name, "title": _erstes(ds, DCT + "title"),
            "license_id": next((x for x in lizenzen if x), None), "license_url": None,
            "license_title": None, "resources": ressourcen}


# ---------------------------------------------------------------- HTML


class _Seite(HTMLParser):
    """Liest aus einer CKAN-Seite: Überschrift, Lizenz, Ressourcen, Suchtreffer, Tabellenzeilen."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titel: str | None = None
        self.lizenz: dict[str, str | None] = {}
        self.ressourcen: list[dict] = []
        self.treffer: list[str] = []
        self.zeilen: dict[str, str] = {}
        self._text: list[str] | None = None  # sammelt Text bis zum Ende von self._ziel
        self._ziel: str | None = None
        self._li = 0  # Tiefe der <li> in einer Ressource
        self._h2 = False
        self._th: str | None = None

    def _sammle(self, ziel: str):
        self._ziel, self._text = ziel, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        klasse = (a.get("class") or "").split()
        if tag == "li" and self._li:
            self._li += 1
        elif tag == "li" and "resource-item" in klasse:
            self._li = 1
            self.ressourcen.append({"id": a.get("data-id"), "name": None, "url": None,
                                    "format": "", "last_modified": None, "created": None,
                                    "seite": None})
        if tag == "h1" and not attrs:  # Titel: das letzte <h1> ohne Klasse (davor steht oft
            self._sammle("titel")      # der Name des Portals)
        elif tag == "a" and a.get("rel") == "dc:rights":
            self.lizenz["url"] = a.get("href")
            self._sammle("lizenz")
        elif tag == "span" and a.get("property") == "dc:rights":
            self._sammle("lizenz")
        elif tag == "h2" and "dataset-heading" in klasse:
            self._h2 = True
        elif tag == "a" and self._h2 and a.get("href"):
            pfad = urllib.parse.urlsplit(a["href"]).path
            if m := re.match(r"^/dataset/([^/]+)/?$", pfad):
                self.treffer.append(urllib.parse.unquote(m.group(1)))
            self._h2 = False
        elif tag == "th" and a.get("scope") == "row":
            self._sammle("th")
        elif tag == "td" and self._th is not None:
            self._sammle("td")
        elif self._li and self.ressourcen:
            r = self.ressourcen[-1]
            if tag == "a" and "heading" in klasse:
                r["name"], r["seite"] = a.get("title"), a.get("href")
            elif tag == "span" and "format-label" in klasse:
                r["format"] = a.get("data-format") or r["format"]
            elif tag == "a" and "resource-url-analytics" in klasse:
                r["url"] = a.get("href")

    def handle_endtag(self, tag):
        if tag == "li" and self._li:
            self._li -= 1
        if self._text is None:
            return
        text = " ".join("".join(self._text).split())
        if self._ziel == "titel" and tag == "h1":
            self.titel = text or self.titel
        elif self._ziel == "lizenz" and tag in ("a", "span"):
            self.lizenz["titel"] = text or None
        elif self._ziel == "th" and tag == "th":
            self._th = text
        elif self._ziel == "td" and tag == "td":
            self.zeilen[self._th or ""] = text
            self._th = None
        else:
            return
        self._text = self._ziel = None

    def handle_data(self, data):
        if self._text is not None:
            self._text.append(data)


def lies_seite(text: str) -> _Seite:
    s = _Seite()
    s.feed(text)
    s.close()
    return s


def aus_html(text: str, name: str, basis: str) -> dict:
    """HTML-Seite eines Datensatzes -> Gerüst wie package_show (siehe oben)."""
    s = lies_seite(text)
    for r in s.ressourcen:
        if r["seite"]:
            r["seite"] = urllib.parse.urljoin(basis + "/", r["seite"])
    return {"name": name, "title": s.titel, "license_id": None,
            "license_url": s.lizenz.get("url"), "license_title": s.lizenz.get("titel"),
            "resources": [r for r in s.ressourcen if r["url"]]}


def datum(text: str) -> date | None:
    """„14. November 2026“, „November 14, 2026“ oder „2026-11-14…“ -> Datum."""
    t = text.strip().lower()
    if m := re.match(r"(\d{4})-(\d{2})-(\d{2})", t):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if (m := re.match(r"(\d{1,2})\.\s*([a-zä]+)\s+(\d{4})", t)) and m[2] in MONATE:
        return date(int(m[3]), MONATE[m[2]], int(m[1]))
    if (m := re.match(r"([a-z]+)\s+(\d{1,2}),\s*(\d{4})", t)) and m[1] in MONATE:
        return date(int(m[3]), MONATE[m[1]], int(m[2]))
    return None


# ---------------------------------------------------------------- Abrufe


def paket(basis: str, name: str, wege: tuple[str, ...] = ("dcat", "html")) -> dict:
    """Metadaten eines Datensatzes – der erste Weg, den das Portal anbietet (404: der nächste)."""
    basis = basis.rstrip("/")
    pfad = urllib.parse.quote(name)
    fehler: Exception = ValueError(f"{name}: kein Weg angegeben")
    for weg in wege:
        if (basis, weg) in _OHNE and weg != wege[-1]:
            continue
        try:
            if weg == "dcat":
                r = abruf.hole(f"{basis}/dataset/{pfad}.jsonld")
                return aus_dcat(json.loads(r.content), name)
            r = abruf.hole(f"{basis}/dataset/{pfad}")
            return aus_html(r.content.decode("utf-8", "replace"), name, basis)
        except abruf.Gesperrt as e:  # robots.txt: der nächste Weg
            fehler = e
        except requests.HTTPError as e:  # 404: das Portal bietet diesen Weg nicht an
            if e.response is None or e.response.status_code != 404:
                raise
            _OHNE.add((basis, weg))
            fehler = e
    raise fehler


def suche(basis: str, begriffe: list[str], seiten: int = 50) -> list[str]:
    """Namen der Datensätze, die die HTML-Suche des Portals für die Begriffe findet."""
    basis = basis.rstrip("/")
    namen: list[str] = []
    for begriff in begriffe:
        for seite in range(1, seiten + 1):
            params = {"q": begriff} | ({"page": str(seite)} if seite > 1 else {})
            text = abruf.hole(f"{basis}/dataset/", params=params).content.decode("utf-8", "replace")
            namen += [n for n in lies_seite(text).treffer if n not in namen]
            if not re.search(rf"[?&;]page={seite + 1}(?![0-9])", text):
                break  # kein Link auf die nächste Seite
    return namen


def ressource_stand(seite: str) -> date | None:
    """Datum der Ressource von ihrer Seite (Daten zuletzt aktualisiert, sonst Erstellt)."""
    zeilen = lies_seite(abruf.hole(seite).content.decode("utf-8", "replace")).zeilen
    for schluessel in ("Daten wurden zuletzt aktualisiert", "Data last updated", "Erstellt",
                       "Created"):
        if schluessel in zeilen and (d := datum(zeilen[schluessel])):
            return d
    return None
