"""Abrufe der Pipeline – nur, was robots.txt erlaubt, mit dem Abstand, den sie verlangt.

Jede Anfrage der Pipeline geht über `hole` (Dateien: `lade`). Vor dem ersten Abruf eines Hosts
liest sie dessen robots.txt (RFC 9309); es gilt die Gruppe ihrer Kennung `zaehlkarte-pipeline`,
sonst die Gruppe `*`:
- Allow/Disallow mit `*` (beliebig viele Zeichen) und `$` (Ende); die längste passende Regel
  gewinnt, bei Gleichstand Allow; geprüft wird der Pfad samt Query, die Prozent-Kodierung vorher
  vereinheitlicht. Mehrere Gruppen für dieselbe Kennung gelten zusammen.
- robots.txt mit 4xx (auch 401/403, wie RFC 9309 es vorsieht – etwa bei Objektspeichern ohne
  robots.txt): alles erlaubt; 429, 5xx oder nicht erreichbar (drei Versuche): alles gesperrt.
- Crawl-delay der Gruppe: so viele Sekunden Abstand zwischen zwei Abrufen desselben Hosts
  (höchstens 60); ohne Angabe kein zusätzlicher Abstand.
- Weiterleitungen: jedes Ziel wird ebenso geprüft.

Einen gesperrten Abruf macht die Pipeline nicht (`Gesperrt`) – außer eine Quelle nennt ihn in
sources.yaml als Ausnahme (`robots_ausnahme`: URL-Anfänge, Grund, seit wann, Stand der Anfrage
beim Betreiber). Solche Abrufe zählt `bericht()` für das Protokoll. Hintergrund: AGENTS.md,
„robots.txt und die Pipeline“.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import requests

KENNUNG = "zaehlkarte-pipeline"
UA = {"User-Agent": f"{KENNUNG} (+https://github.com/vizsim-lab/zaehlkarte)"}
MAX_ABSTAND = 60.0
MAX_WEITERLEITUNGEN = 10


class Gesperrt(Exception):
    """robots.txt verbietet den Abruf, und sources.yaml nennt dafür keine Ausnahme."""


def _norm(pfad: str) -> str:
    """Prozent-Kodierung vereinheitlichen (RFC 9309, 2.2.2)."""
    return urllib.parse.quote(urllib.parse.unquote(pfad), safe="/?=&*$:@!,;+-._~%")


def _muster(regel: str) -> re.Pattern:
    anker = regel.endswith("$")
    kern = regel[:-1] if anker else regel
    return re.compile("".join(".*" if c == "*" else re.escape(c) for c in _norm(kern))
                      + ("$" if anker else ""))


class Regeln:
    """Die Regeln einer robots.txt, die für die Kennung der Pipeline gelten."""

    def __init__(self, text: str = "", *, alles: bool | None = None, kennung: str = KENNUNG):
        self.alles = alles  # True: alles erlaubt, False: alles gesperrt, None: nach Regeln
        self.regeln: list[tuple[int, bool, re.Pattern]] = []
        self.abstand: float | None = None
        if alles is None:
            self._waehle(self._gruppen(text), kennung.lower())

    @staticmethod
    def _gruppen(text: str) -> list[tuple[set[str], list[tuple[bool, str]], float | None]]:
        gruppen = []
        agenten: set[str] = set()
        regeln: list[tuple[bool, str]] = []
        abstand: float | None = None
        in_regeln = False
        for zeile in text.splitlines():
            zeile = zeile.split("#", 1)[0].strip()
            if ":" not in zeile:
                continue
            feld, wert = (x.strip() for x in zeile.split(":", 1))
            feld = feld.lower()
            if feld == "user-agent":
                if in_regeln:  # eine neue Gruppe beginnt
                    if agenten:
                        gruppen.append((agenten, regeln, abstand))
                    agenten, regeln, abstand, in_regeln = set(), [], None, False
                agenten.add(wert.lower())
            elif feld in ("allow", "disallow"):
                in_regeln = True
                if wert:  # leeres Disallow sperrt nichts
                    regeln.append((feld == "allow", wert))
            elif feld == "crawl-delay":
                in_regeln = True
                try:
                    abstand = float(wert)
                except ValueError:
                    pass
        if agenten:
            gruppen.append((agenten, regeln, abstand))
        return gruppen

    def _waehle(self, gruppen, kennung: str) -> None:
        passend = [g for g in gruppen if kennung in g[0]] or [g for g in gruppen if "*" in g[0]]
        for _, regeln, abstand in passend:
            self.regeln += [(len(r), erlaubt, _muster(r)) for erlaubt, r in regeln]
            if abstand is not None:
                self.abstand = max(self.abstand or 0.0, abstand)

    def erlaubt(self, url: str) -> bool:
        if self.alles is not None:
            return self.alles
        t = urllib.parse.urlsplit(url)
        pfad = _norm((t.path or "/") + (f"?{t.query}" if t.query else ""))
        if pfad == "/robots.txt":
            return True
        bestes: tuple[int, bool] | None = None
        for laenge, erlaubt, muster in self.regeln:
            if muster.match(pfad) and (bestes is None or laenge > bestes[0]
                                       or (laenge == bestes[0] and erlaubt)):
                bestes = (laenge, erlaubt)
        return True if bestes is None else bestes[1]


@dataclass(frozen=True)
class Ausnahme:
    quelle: str
    praefix: str
    grund: str


_REGELN: dict[str, Regeln] = {}
_ZULETZT: dict[str, float] = {}
_AUSNAHMEN: list[Ausnahme] = []
GENUTZT: Counter[Ausnahme] = Counter()
GEWARTET: Counter[str] = Counter()  # Sekunden je Host (Crawl-delay)


def _basis(url: str) -> str:
    t = urllib.parse.urlsplit(url)
    return f"{t.scheme}://{t.netloc}"


def _robots_text(basis: str) -> tuple[int, str]:
    """(HTTP-Status, Text) der robots.txt eines Hosts; Status 0: nicht erreichbar."""
    for versuch in range(3):
        try:
            r = requests.get(basis + "/robots.txt", headers=UA, timeout=30)
            if r.status_code < 500 and r.status_code != 429:
                text = r.content[:500_000].decode("utf-8-sig", "replace") if r.ok else ""
                return r.status_code, text
        except requests.RequestException:
            pass
        if versuch < 2:
            time.sleep(5 * (versuch + 1))
    return 0, ""


def regeln(url: str) -> Regeln:
    basis = _basis(url)
    if basis not in _REGELN:
        status, text = _robots_text(basis)
        if 200 <= status < 300:
            _REGELN[basis] = Regeln(text)
        else:  # 4xx: keine robots.txt; 429, 5xx, nicht erreichbar: alles gesperrt
            _REGELN[basis] = Regeln(alles=400 <= status < 500 and status != 429)
    return _REGELN[basis]


def ausnahmen_setzen(quellen: dict[str, dict]) -> None:
    """Ausnahmen aus sources.yaml übernehmen (je Quelle `robots_ausnahme`)."""
    for code, q in quellen.items():
        if a := q.get("robots_ausnahme"):
            for praefix in a["urls"]:
                ausnahme = Ausnahme(code, praefix, " ".join(a["grund"].split()))
                if ausnahme not in _AUSNAHMEN:
                    _AUSNAHMEN.append(ausnahme)


def pruefe(url: str) -> None:
    """Gesperrt, wenn robots.txt den Abruf verbietet und keine Ausnahme ihn abdeckt."""
    if regeln(url).erlaubt(url):
        return
    for a in _AUSNAHMEN:
        if url.startswith(a.praefix):
            GENUTZT[a] += 1
            return
    raise Gesperrt(f"robots.txt sperrt {url} für {KENNUNG} (keine Ausnahme in sources.yaml)")


def _warte(url: str) -> None:
    abstand = min(regeln(url).abstand or 0.0, MAX_ABSTAND)
    if not abstand:
        return
    basis = _basis(url)
    jetzt = time.monotonic()
    frei = _ZULETZT.get(basis, jetzt - abstand) + abstand
    if frei > jetzt:
        time.sleep(frei - jetzt)
        GEWARTET[urllib.parse.urlsplit(url).netloc] += frei - jetzt
    _ZULETZT[basis] = time.monotonic()


def hole(url: str, *, params: dict | None = None, daten: dict | None = None,
         sitzung: requests.Session | None = None, stream: bool = False, timeout: float = 120,
         kopf: dict | None = None, status_pruefen: bool = True) -> requests.Response:
    """GET (mit `daten`: POST) – nur wenn robots.txt es erlaubt (auch jedes Weiterleitungsziel),
    mit Crawl-delay."""
    kopf = UA | (kopf or {})
    for _ in range(MAX_WEITERLEITUNGEN + 1):
        voll = requests.Request("GET", url, params=params).prepare().url if params else url
        pruefe(voll)
        _warte(voll)
        weg = sitzung or requests
        if daten is None:
            r = weg.get(url, params=params, headers=kopf, timeout=timeout, stream=stream,
                        allow_redirects=False)
        else:
            r = weg.post(url, params=params, data=daten, headers=kopf, timeout=timeout,
                         stream=stream, allow_redirects=False)
        if not getattr(r, "is_redirect", False):
            break
        url, params = urllib.parse.urljoin(voll, r.headers["Location"]), None
        if r.status_code not in (307, 308):
            daten = None  # 301/302/303: weiter mit GET
        r.close()
    else:
        raise requests.TooManyRedirects(f"mehr als {MAX_WEITERLEITUNGEN} Weiterleitungen: {url}")
    if status_pruefen:
        r.raise_for_status()
    return r


def lade(url: str, ziel: Path, *, timeout: float = 600) -> Path:
    """Datei nach `ziel` (erst als `.teil`, damit kein halber Download liegen bleibt)."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = ziel.with_suffix(ziel.suffix + ".teil")
    with hole(url, stream=True, timeout=timeout) as r, tmp.open("wb") as f:
        for block in r.iter_content(1 << 20):
            f.write(block)
    tmp.replace(ziel)
    return ziel


def bericht() -> list[str]:
    """Für das Protokoll: Abrufe, die nur dank einer Ausnahme gingen, und die Wartezeiten."""
    z = [f"robots.txt: {n} Abrufe für {a.quelle} trotz Sperre ({a.praefix}) – Ausnahme laut "
         f"sources.yaml: {a.grund}" for a, n in GENUTZT.items()]
    if GEWARTET:
        z.append("Crawl-delay eingehalten: " + ", ".join(
            f"{host} {s:.0f} s" if s < 120 else f"{host} {s / 60:.0f} min"
            for host, s in GEWARTET.most_common()))
    return z
