"""Entwicklungswerkzeug: gezielt einzelne Pakete holen (Paketliste + Suchen), alle Ressourcen
herunterladen (bis 30 MB), ZIP-Inhalte (Tabellen, TXT, je 2 PDF) entpacken. Nur Stdlib."""

import io
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
import zipfile

UA = {"User-Agent": "zaehlkarte-erkundung (+https://github.com/vizsim-lab/zaehlkarte)"}
GOVDATA = "https://www.govdata.de/ckan/api/3/action/"
PORTALE = {
    "govdata": GOVDATA,
    "muenster": "https://opendata.stadt-muenster.de/api/3/action/",
    "opennrw": "https://ckan.open.nrw.de/api/3/action/",
    "hamburg": "https://suche.transparenz.hamburg.de/api/3/action/",
}
PAKETE = {
    "govdata": ["verkehrszahlung-manuelle-verkehrserhebung", "verkehrszahlungen-2021", "verkehrszahlungen-2020",
                "verkehrszahlungen-2018", "verkehrszahlung-osnabruckd277a", "verkehrszahlungen-konstanzdc68b",
                "verkehrszahlung-boschheidewegbd80e"],
    "hamburg": ["verkehrsstaerken-bedarfszaehlstellen-hamburg10"],
}
SUCHEN = {
    "govdata": ["Verkehrszählung Münster", "Knotenpunkt Münster", "Verkehrszählungen Moers", "Verkehrserhebung"],
    "muenster": ["Verkehrszählung", "Knotenpunkt", "Kfz"],
    "opennrw": ["Verkehrszählung Münster"],
}
ziel = pathlib.Path(sys.argv[1])
log: dict = {"pakete": {}, "suchen": {}, "fehler": {}}


def hole(url: str, limit: int = 30_000_000, timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        daten = r.read(limit + 1)
    if len(daten) > limit:
        raise ValueError("zu groß")
    return daten


def api(portal: str, action: str, **params) -> dict:
    url = PORTALE[portal] + action + "?" + urllib.parse.urlencode(params)
    return json.loads(hole(url))["result"]


def sicher(name: str) -> str:
    return re.sub(r"[^\w.\-äöüÄÖÜß]+", "_", name)[:120]


def speichere(portal: str, paket: dict, laden: bool) -> None:
    ordner = ziel / portal / sicher(paket["name"])
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "paket.json").write_text(json.dumps(paket, ensure_ascii=False, indent=1))
    if not laden:
        return
    for r in paket.get("resources", [])[:60]:
        url = r.get("url") or ""
        if not url.startswith("http"):
            continue
        datei = sicher(urllib.parse.unquote(url.split("?")[0].rsplit("/", 1)[-1]) or r.get("id", "x"))
        try:
            daten = hole(url)
        except Exception as e:  # noqa: BLE001
            log["fehler"][url] = str(e)
            continue
        if daten[:2] == b"PK" and not datei.lower().endswith((".xlsx", ".xlsm", ".ods", ".docx")):
            try:
                with zipfile.ZipFile(io.BytesIO(daten)) as zf:
                    pdfs = 0
                    liste = []
                    for info in zf.infolist():
                        liste.append([info.filename, info.file_size])
                        n = info.filename.lower()
                        if n.endswith((".xls", ".xlsx", ".csv", ".txt", ".json", ".zda")) or (n.endswith(".pdf") and pdfs < 2):
                            pdfs += n.endswith(".pdf")
                            p = ordner / "zip" / sicher(datei) / sicher(info.filename.replace("/", "__"))
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_bytes(zf.read(info))
                    (ordner / f"{sicher(datei)}.inhalt.json").write_text(json.dumps(liste, ensure_ascii=False))
            except Exception as e:  # noqa: BLE001
                log["fehler"][url] = f"ZIP: {e}"
        else:
            (ordner / datei).write_bytes(daten)


def main() -> None:
    ziel.mkdir(parents=True, exist_ok=True)
    for portal, namen in PAKETE.items():
        for n in namen:
            try:
                speichere(portal, api(portal, "package_show", id=n), True)
                log["pakete"][n] = "ok"
            except Exception as e:  # noqa: BLE001
                log["fehler"][f"{portal}/{n}"] = str(e)
    for portal, suchen in SUCHEN.items():
        for q in suchen:
            try:
                res = api(portal, "package_search", q=q, rows=100)["results"]
                log["suchen"][f"{portal}:{q}"] = [[p["name"], p.get("title"), (p.get("organization") or {}).get("title")] for p in res]
                for p in res:
                    t = (p.get("title") or "").lower()
                    if portal == "muenster" or "münster" in t or "moers" in t:
                        if any(w in t for w in ("zähl", "zaehl", "knoten", "verkehrsmeng")):
                            speichere(portal, p, "rad" not in t)
            except Exception as e:  # noqa: BLE001
                log["fehler"][f"{portal}:{q}"] = str(e)
    (ziel / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
