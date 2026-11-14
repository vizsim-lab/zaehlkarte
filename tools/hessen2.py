"""Werkzeug: Verkehrszählungen in Hessen (Teil 2: gezielt lesen).

- Seiten aus tools/hessen2_seiten.txt („Kommune | URL“) als Text samt Links; PDFs mit pdftotext;
  verlinkte Zähl-Dokumente (PDF, XLSX, CSV) eine Ebene tief,
- FragDenStaat: ausgewählte Anfragen mit Nachrichten und Anhängen,
- Eco-Counter-Portal des Landes (Liste der Zählstellen), wenn robots.txt es erlaubt,
- CKAN-Portale (Frankfurt, Darmstadt, FID move), Mobilithek-Angebote, Geoportal Hessen.

Webseiten nur mit ehrlicher Kennung und nur, was robots.txt erlaubt (auch für die Kennungen von
Claude). Nur Standardbibliothek (+ pdftotext). Aufruf: python3 tools/hessen2.py ergebnis/hessen2
"""

import concurrent.futures as cf
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from html.parser import HTMLParser

ZIEL = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "ergebnis/hessen2")
ZIEL.mkdir(parents=True, exist_ok=True)
(ZIEL / "dateien").mkdir(exist_ok=True)
UA = "zaehlkarte-werkzeug/0.2 (+https://github.com/vizsim-lab/zaehlkarte)"
ROBOT_KENNUNGEN = ("zaehlkarte-werkzeug", "ClaudeBot", "Claude-User", "Claude-SearchBot", "anthropic-ai", "*")
GRENZE = 25_000_000
protokoll: dict = {}
_ROBOTS: dict = {}
_SPERRE = threading.Lock()
ZAEHL = re.compile(
    r"z(?:ae|ä|a)hl|verkehrsmeng|verkehrsdaten|verkehrserheb|verkehrsbelast|verkehrsst(?:ae|ä|a)rk"
    r"|messung|messtafel|geschwindigkeit|auswertung|ergebnis|querschnitt|knotenpunkt", re.I)


class Gesperrt(Exception):
    pass


def roh(url, *, daten=None, kopf=None, zeit=90, grenze=GRENZE):
    k = {"User-Agent": UA, "Accept-Language": "de"} | (kopf or {})
    if daten is not None and not isinstance(daten, bytes):
        daten = json.dumps(daten).encode()
        k.setdefault("Content-Type", "application/json")
    with urllib.request.urlopen(urllib.request.Request(url, data=daten, headers=k), timeout=zeit) as a:
        inhalt = a.read(grenze + 1)
        if len(inhalt) > grenze:
            raise ValueError("zu groß")
        return inhalt, a.geturl(), a.headers.get("Content-Type", "")


def erlaubt(url):
    t = urllib.parse.urlsplit(url)
    basis = f"{t.scheme}://{t.netloc}"
    with _SPERRE:
        rp = _ROBOTS.get(basis)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        try:
            inhalt, _, _ = roh(basis + "/robots.txt", zeit=20)
            rp.parse(inhalt.decode("utf-8", "replace").splitlines())
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                rp.disallow_all = True
            else:
                rp.allow_all = True
        except Exception:  # noqa: BLE001
            rp.allow_all = True
        with _SPERRE:
            _ROBOTS[basis] = rp
    return all(rp.can_fetch(k, url) for k in ROBOT_KENNUNGEN)


def seite(url, **kw):
    if not erlaubt(url):
        raise Gesperrt(url)
    return roh(url, **kw)


def schreibe(name, obj):
    (ZIEL / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1))


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.teile, self.links, self._a, self._at, self._weg = [], [], None, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._weg += 1
        elif tag == "a":
            self._a, self._at = dict(attrs).get("href"), []
        elif tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "tr", "div", "td", "th"):
            self.teile.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._weg = max(0, self._weg - 1)
        elif tag == "a" and self._a is not None:
            self.links.append([self._a, " ".join("".join(self._at).split())[:200]])
            self._a = None

    def handle_data(self, d):
        if self._weg:
            return
        self.teile.append(d)
        if self._a is not None:
            self._at.append(d)

    def text(self):
        t = "".join(self.teile)
        t = re.sub(r"[ \t\r\f\v]+", " ", t)
        return re.sub(r"\n\s*\n+", "\n", t).strip()


def dateiname(url, endung):
    h = hashlib.sha1(url.encode()).hexdigest()[:10]
    stamm = re.sub(r"[^\w\-]+", "_", urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1]))[:60]
    return f"{stamm or 'datei'}_{h}{endung}"


def pdf_text(pfad):
    try:
        subprocess.run(["pdftotext", "-layout", "-l", "90", str(pfad), str(pfad) + ".txt"], check=False,
                       timeout=180, capture_output=True)
        return (pathlib.Path(str(pfad) + ".txt").read_text(errors="replace"))[:200000]
    except Exception as e:  # noqa: BLE001
        return f"(pdftotext: {e!r})"


def lies(kommune, url, tiefe=0):
    erg = {"kommune": kommune, "url": url}
    try:
        inhalt, end, typ = seite(url)
    except Gesperrt:
        return erg | {"fehler": "robots.txt"}
    except Exception as e:  # noqa: BLE001
        return erg | {"fehler": repr(e)[:200]}
    erg |= {"end": end, "typ": typ, "bytes": len(inhalt)}
    if inhalt[:4] == b"%PDF" or "pdf" in typ:
        p = ZIEL / "dateien" / dateiname(url, ".pdf")
        p.write_bytes(inhalt)
        return erg | {"datei": p.name, "text": pdf_text(p)}
    if any(x in typ for x in ("spreadsheet", "excel", "csv", "zip", "octet-stream")) or re.search(
            r"\.(xlsx?|csv|zip)(\?|$)", url, re.I):
        endung = (re.search(r"\.(xlsx?|csv|zip)", url, re.I) or re.search(r"(csv|zip)", typ) or [None, "bin"])[1]
        p = ZIEL / "dateien" / dateiname(url, "." + endung.lower())
        p.write_bytes(inhalt)
        return erg | {"datei": p.name}
    t = Text()
    try:
        t.feed(inhalt.decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        pass
    links = [[urllib.parse.urljoin(end, h), x] for h, x in t.links if h and not h.startswith(("mailto:", "tel:", "#"))]
    erg |= {"text": t.text()[:30000], "links": [lk for lk in links if ZAEHL.search(lk[0] + " " + lk[1])
                                                 or re.search(r"\.(pdf|xlsx?|csv|zip)(\?|$)", lk[0], re.I)][:120]}
    if tiefe == 0:
        unter = [lk[0] for lk in erg["links"] if re.search(r"\.(pdf|xlsx?|csv)(\?|$)", lk[0], re.I)
                 and ZAEHL.search(urllib.parse.unquote(lk[0]) + " " + lk[1])][:6]
        erg["unter"] = [lies(kommune, u, 1) for u in unter]
    return erg


def seiten():
    ziele = []
    liste = sys.argv[2] if len(sys.argv) > 2 else str(pathlib.Path(__file__).parent / "hessen2_seiten.txt")
    for z in pathlib.Path(liste).read_text().splitlines():
        if " | " in z and not z.startswith("#"):
            k, u = z.split(" | ", 1)
            ziele.append((k.strip(), u.strip()))
    with cf.ThreadPoolExecutor(max_workers=12) as pool:
        aus = list(pool.map(lambda kv: lies(*kv), ziele))
    schreibe("seiten.json", aus)
    protokoll["seiten"] = {"ziele": len(ziele), "gelesen": sum(1 for e in aus if "fehler" not in e),
                           "robots": sum(1 for e in aus if e.get("fehler") == "robots.txt")}


FDS_IDS = [29243, 31660, 33668, 132306, 187707, 242705, 267811, 314657, 321119, 370827, 371577]


def fds():
    aus = {}
    for i in FDS_IDS:
        try:
            d = json.loads(roh(f"https://fragdenstaat.de/api/v1/request/{i}/")[0])
        except Exception as e:  # noqa: BLE001
            aus[i] = {"fehler": repr(e)[:200]}
            continue
        nachrichten = []
        for m in d.get("messages", []):
            if isinstance(m, str):
                try:
                    m = json.loads(roh(m)[0])
                except Exception:  # noqa: BLE001
                    continue
            anh = []
            for a in m.get("attachments", []) or []:
                if isinstance(a, str):
                    try:
                        a = json.loads(roh(a)[0])
                    except Exception:  # noqa: BLE001
                        continue
                eintrag = {k: a.get(k) for k in ("name", "filetype", "size", "file_url", "site_url", "approved",
                                                 "is_redacted", "is_converted")}
                url = a.get("file_url")
                if url and (a.get("size") or 0) < 15_000_000 and re.search(r"\.(pdf|xlsx?|csv|zip|ods)$", a.get("name") or "", re.I):
                    try:
                        inhalt = roh(url)[0]
                        endung = "." + (a.get("name") or "x.bin").rsplit(".", 1)[-1].lower()
                        p = ZIEL / "dateien" / f"fds_{i}_{hashlib.sha1(url.encode()).hexdigest()[:8]}{endung}"
                        p.write_bytes(inhalt)
                        eintrag["datei"] = p.name
                        if endung == ".pdf":
                            eintrag["text"] = pdf_text(p)[:20000]
                    except Exception as e:  # noqa: BLE001
                        eintrag["fehler"] = repr(e)[:150]
                anh.append(eintrag)
            nachrichten.append({"von": m.get("sender_public_body") or m.get("sender_name"),
                                "datum": (m.get("timestamp") or "")[:10], "betreff": m.get("subject"),
                                "text": re.sub(r"\s+", " ", m.get("content") or m.get("plaintext") or "")[:6000],
                                "anhaenge": anh, "ist_antwort": m.get("is_response")})
            time.sleep(0.3)
        aus[i] = {"titel": d.get("title"), "status": d.get("status"), "ergebnis": d.get("resolution"),
                  "behoerde": (d.get("public_body") or {}).get("name") if isinstance(d.get("public_body"), dict)
                  else d.get("public_body"), "gesetz": d.get("law"), "kosten": d.get("costs"),
                  "beschreibung": d.get("description"), "nachrichten": nachrichten,
                  "schluessel": sorted(d.keys())}
        time.sleep(0.5)
    schreibe("fds.json", aus)
    protokoll["fds"] = {"anfragen": len(aus)}


def eco_counter():
    aus = {}
    for url in ("https://www.eco-visio.net/api/aladdin/1.0.0/pbl/publicwebpageplus/8080?withNull=true",
                "https://data.eco-counter.com/ParcPublic/?id=8080",
                "https://hessen-mobil.eco-counter.com/"):
        try:
            inhalt, end, typ = seite(url, zeit=90)
            aus[url] = json.loads(inhalt) if "json" in typ else inhalt[:20000].decode("utf-8", "replace")
        except Gesperrt:
            aus[url] = "robots.txt"
        except Exception as e:  # noqa: BLE001
            aus[url] = repr(e)[:200]
    schreibe("eco_counter.json", aus)
    protokoll["eco_counter"] = {u: (len(v) if isinstance(v, list) else str(v)[:60]) for u, v in aus.items()}


def portale():
    aus = {}
    ckan = {"frankfurt": "https://offenedaten.frankfurt.de/api/3/action/",
            "darmstadt": "https://opendata.darmstadt.de/api/3/action/"}
    for name, api in ckan.items():
        for q in ("Zählung", "Zählstelle", "Verkehr", "Radverkehr", "Verkehrsmengen", "Detektor", "Fußverkehr"):
            try:
                r = json.loads(roh(api + "package_search?" + urllib.parse.urlencode({"q": q, "rows": 100}))[0])["result"]
                for p in r["results"]:
                    aus.setdefault(name, {})[p["name"]] = {
                        "titel": p.get("title"), "lizenz": p.get("license_id"), "geaendert": p.get("metadata_modified"),
                        "notiz": re.sub(r"\s+", " ", p.get("notes") or "")[:500],
                        "ressourcen": [[r.get("name"), r.get("format"), r.get("url")] for r in p.get("resources", [])][:15]}
            except Exception as e:  # noqa: BLE001
                aus.setdefault(name + "_fehler", {})[q] = repr(e)[:200]
            time.sleep(0.4)
    try:
        aus["fid_move_r3"] = json.loads(roh("https://data.fid-move.de/api/3/action/package_show?id=9b2b839e-441b-44a5-9dc1-64c0408f2b91")[0])["result"]
    except Exception as e:  # noqa: BLE001
        aus["fid_move_r3"] = repr(e)[:200]
    for oid in ("842371963004272640", "110000000003182000", "110000000003181000", "-8060510244121701904",
                "-2949871930131753119"):
        try:
            aus.setdefault("mobilithek", {})[oid] = json.loads(roh(
                f"https://mobilithek.info/mdp-api/mdp-msa-metadata/v2/offers/{oid}")[0])
        except Exception as e:  # noqa: BLE001
            aus.setdefault("mobilithek", {})[oid] = repr(e)[:200]
    for b in ("Verkehrszählung", "Verkehrsmengen", "Zählstelle", "Verkehrsstärke", "Radverkehr", "DTV",
              "Verkehrsbelastung"):
        for res in ("dataset", "wms", "wfs"):
            url = ("https://www.geoportal.hessen.de/mapbender/php/mod_callMetadata.php?"
                   + urllib.parse.urlencode({"searchText": b, "searchResources": res, "outputFormat": "json",
                                             "resultTarget": "web", "maxResults": 50, "searchPages": 1}))
            try:
                inhalt = roh(url)[0]
                aus.setdefault("geoportal", {})[f"{b}|{res}"] = json.loads(inhalt)
            except Exception as e:  # noqa: BLE001
                aus.setdefault("geoportal", {})[f"{b}|{res}"] = repr(e)[:200]
    schreibe("portale.json", aus)
    protokoll["portale"] = {k: (len(v) if isinstance(v, dict) else str(v)[:80]) for k, v in aus.items()}


if __name__ == "__main__":
    nur_seiten = len(sys.argv) > 3 and sys.argv[3] == "nur_seiten"
    for f in (seiten,) if nur_seiten else (seiten, fds, eco_counter, portale):
        t0 = time.time()
        try:
            f()
        except Exception as e:  # noqa: BLE001
            protokoll[f.__name__ + "_fehler"] = repr(e)[:300]
        protokoll[f.__name__ + "_sekunden"] = round(time.time() - t0)
        schreibe("protokoll.json", protokoll)
        print(f.__name__, json.dumps(protokoll.get(f.__name__), ensure_ascii=False)[:400], flush=True)
