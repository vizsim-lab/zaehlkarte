"""Moers, Fußgänger in der Steinstraße (MoersMarketing, Laser-Personenzählung seit Mai 2022):
die Datensätze auf offenesdatenportal.de finden, ihre Ressourcen aus dem DCAT-Dokument lesen
und alle Dateien „nach Stunden“ und „nach Tagen“ laden – gepackt nach ergebnis/moers_fuss/roh/,
mit Kopf und ersten Zeilen je Datei im Bericht.

Nur über tools/robots.py (RFC 9309 für die eigene Kennung, `*` und die Kennungen von Claude,
Crawl-delay je Host). Die CKAN-API (`/api/`) sperrt das Portal; erlaubt sind Suche, Seiten,
DCAT-Dokumente und Downloads (Stand AGENTS.md, „robots.txt und die Pipeline“).

    python3 tools/moers_fuss_erkunden.py <zielordner>
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
import traceback
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robots  # noqa: E402

BASIS = "https://www.offenesdatenportal.de"
BEGRIFFE = ["Steinstraße Moers", "Steinstrasse Moers", "Besucherzahlen Moers",
            "Fußgängerinnen Moers", "Frequenzmessung Moers", "Fußgänger Steinstraße"]
PASST = re.compile(r"steinstra|besucherzahl|fu(ss|ß|b)g(a|ä)nger", re.I)
DCAT = "http://www.w3.org/ns/dcat#"
DCT = "http://purl.org/dc/terms/"

ziel = Path(sys.argv[1])
(ziel / "roh").mkdir(parents=True, exist_ok=True)
out: list[str] = []


def schreib() -> None:
    (ziel / "bericht.txt").write_text("\n".join(out) + "\n", encoding="utf-8")


def hole(url: str, grenze: int = 25_000_000) -> bytes:
    inhalt, _, _ = robots.oeffne(url, zeit=120, grenze=grenze)
    return inhalt


# ---------------------------------------------------------------- DCAT (wie zaehlkarte.ckan)


def _iri(wert: str, ctx: dict) -> str:
    if ":" in wert:
        praefix, rest = wert.split(":", 1)
        if isinstance(ctx.get(praefix), str) and not rest.startswith("//"):
            return ctx[praefix] + rest
    return wert


def _knoten(dok) -> dict[str, dict[str, list[str]]]:
    ctx = dok.get("@context", {}) if isinstance(dok, dict) else {}
    ctx = ctx if isinstance(ctx, dict) else {}
    liste = (dok.get("@graph", [dok]) if isinstance(dok, dict) else dok) or []
    knoten: dict[str, dict[str, list[str]]] = {}
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
        knoten[k.get("@id", f"_:{len(knoten)}")] = n
    return knoten


def _erstes(n: dict, iri: str):
    return (n.get(iri) or [None])[0]


def paket(name: str) -> dict:
    dok = json.loads(hole(f"{BASIS}/dataset/{urllib.parse.quote(name)}.jsonld"))
    knoten = _knoten(dok)
    saetze = [n for n in knoten.values() if DCAT + "Dataset" in n.get("@type", [])]
    ds = saetze[0]
    res = []
    for rid in ds.get(DCAT + "distribution", []):
        v = knoten.get(rid, {})
        res.append({"id": rid.rstrip("/").rsplit("/", 1)[-1], "titel": _erstes(v, DCT + "title"),
                    "url": _erstes(v, DCAT + "downloadURL") or _erstes(v, DCAT + "accessURL"),
                    "format": _erstes(v, DCT + "format"), "lizenz": _erstes(v, DCT + "license"),
                    "geaendert": _erstes(v, DCT + "modified"),
                    "erstellt": _erstes(v, DCT + "issued")})
    return {"name": name, "titel": _erstes(ds, DCT + "title"),
            "lizenz": _erstes(ds, DCT + "license"),
            "beschreibung": (_erstes(ds, DCT + "description") or "")[:1500],
            "herausgeber": _erstes(ds, DCT + "publisher"),
            "geaendert": _erstes(ds, DCT + "modified"), "ressourcen": res}


# ---------------------------------------------------------------- Ablauf

try:
    out.append("== robots.txt")
    for basis in (BASIS,):
        robots.regeln(basis + "/")
        out.append(f"{basis}: {robots.TEXTE.get(basis, '')[:1500]}")
        for pfad in ("/dataset/?q=Steinstra%C3%9Fe", "/dataset/x.jsonld", "/api/3/action/package_search",
                     "/dataset/x/resource/y/download/z.csv"):
            out.append(f"  {pfad}: {'erlaubt' if robots.erlaubt(basis + pfad) else 'gesperrt'}")
    schreib()

    namen: list[str] = []
    out.append("== Suche")
    for begriff in BEGRIFFE:
        for seite in range(1, 15):
            q = {"q": begriff} | ({"page": str(seite)} if seite > 1 else {})
            url = f"{BASIS}/dataset/?{urllib.parse.urlencode(q)}"
            if not robots.erlaubt(url):
                out.append(f"  gesperrt: {url}")
                break
            text = hole(url).decode("utf-8", "replace")
            treffer = re.findall(r'<h[23][^>]*dataset-heading[^>]*>\s*<a[^>]*href="(?:/[a-z]{2})?/dataset/([^"/?#]+)"', text)
            treffer = [urllib.parse.unquote(t) for t in treffer]
            neu = [t for t in treffer if t not in namen]
            namen += neu
            out.append(f"  {begriff!r} Seite {seite}: {len(treffer)} Treffer, neu {len(neu)}")
            if not re.search(rf"[?&;]page={seite + 1}(?![0-9])", text):
                break
    passend = [n for n in namen if PASST.search(n)]
    out.append(f"alle Treffer: {len(namen)}; passend: {len(passend)}")
    out += [f"  {n}" for n in passend]
    out.append("nicht passend (erste 40): " + ", ".join(n for n in namen if n not in passend)[:3000])
    schreib()

    pakete = []
    for n in passend:
        try:
            p = paket(n)
        except Exception as e:  # noqa: BLE001
            out.append(f"  {n}: DCAT nicht lesbar: {e!r}")
            continue
        pakete.append(p)
        out.append(f"== {n}: {p['titel']} | Lizenz {p['lizenz']} | geändert {p['geaendert']} | "
                   f"{len(p['ressourcen'])} Ressourcen")
        out.append(f"   {p['beschreibung'][:600]!r}")
        for r in p["ressourcen"]:
            out.append(f"   - {r['titel']} | {r['format']} | {r['lizenz']} | {r['erstellt']} / "
                       f"{r['geaendert']} | {r['url']}")
    (ziel / "pakete.json").write_text(json.dumps(pakete, ensure_ascii=False, indent=1) + "\n",
                                      encoding="utf-8")
    schreib()

    out.append("== Downloads")
    liste = []
    for p in pakete:
        for r in p["ressourcen"]:
            if not r["url"]:
                continue
            titel = (r["titel"] or "") + " " + r["url"]
            if not re.search(r"stund|stündl|stundl|tag|täglich", titel, re.I):
                out.append(f"  übersprungen: {r['titel']} {r['url']}")
                continue
            datei = urllib.parse.unquote(r["url"].rstrip("/").rsplit("/", 1)[-1])
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", f"{p['name']}__{datei}")[:180]
            try:
                inhalt = hole(r["url"])
            except Exception as e:  # noqa: BLE001
                out.append(f"  {r['url']}: {e!r}")
                continue
            (ziel / "roh" / (name + ".gz")).write_bytes(gzip.compress(inhalt, mtime=0))
            text = inhalt.decode("utf-8-sig", "replace")
            zeilen = text.splitlines()
            liste.append({"paket": p["name"], "titel": r["titel"], "url": r["url"],
                          "datei": name + ".gz", "bytes": len(inhalt),
                          "sha256": hashlib.sha256(inhalt).hexdigest(), "zeilen": len(zeilen),
                          "bom": inhalt.startswith(b"\xef\xbb\xbf"), "erstellt": r["erstellt"],
                          "geaendert": r["geaendert"], "lizenz": r["lizenz"]})
            bom = inhalt.startswith(b"\xef\xbb\xbf")
            out.append(f"  {name}: {len(inhalt)} Bytes, {len(zeilen)} Zeilen, BOM {bom}")
            out += [f"     {z[:300]}" for z in zeilen[:4]]
            out += [f"     … {z[:300]}" for z in zeilen[-2:]]
            schreib()
    (ziel / "dateien.json").write_text(json.dumps(liste, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")
    out.append(f"geladen: {len(liste)} Dateien")
except Exception:  # noqa: BLE001
    out.append(traceback.format_exc())
schreib()
