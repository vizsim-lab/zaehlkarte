"""robots.txt nach RFC 9309 für die Werkzeuge – unabhängig von der Python-Version.

urllib.robotparser kennt die Platzhalter `*` und `$` erst in neueren Versionen (auf dem Runner
mit Python 3.12 nicht: „Disallow: /*?*“ sperrte dort nichts). Hier:
- Gruppen je User-agent (Groß-/Kleinschreibung egal); gilt keine Gruppe für eine Kennung, die
  Gruppe „*“. Mehrere Gruppen für dieselbe Kennung werden zusammengelegt.
- Allow/Disallow mit `*` (beliebig viele Zeichen) und `$` (Ende); die längste passende Regel
  gewinnt, bei Gleichstand Allow. Leeres Disallow erlaubt alles.
- Pfad samt Query; Prozent-Kodierung vor dem Vergleich vereinheitlicht.
- robots.txt mit 4xx (außer 401/403): alles erlaubt; 401/403, 5xx, Netzfehler: alles gesperrt.
- Crawl-delay: die größte Angabe der Gruppen unserer Kennungen, mindestens 1 Sekunde je Host.
- Weiterleitungen: das Ziel jeder Weiterleitung wird ebenfalls geprüft (Opener unten).
"""

from __future__ import annotations

import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

KENNUNGEN = ("zaehlkarte-werkzeug", "ClaudeBot", "Claude-User", "Claude-SearchBot", "anthropic-ai", "*")
UA = "zaehlkarte-werkzeug/0.3 (+https://github.com/vizsim-lab/zaehlkarte)"
MIN_ABSTAND = 1.0
MAX_ABSTAND = 60.0


class Gesperrt(Exception):
    """robots.txt verbietet den Abruf."""


def _norm(pfad: str) -> str:
    """Prozent-Kodierung vereinheitlichen (RFC 9309 2.2.2)."""
    return urllib.parse.quote(urllib.parse.unquote(pfad), safe="/?=&*$:@!,;+-._~%")


def _muster(regel: str):
    anker = regel.endswith("$")
    kern = regel[:-1] if anker else regel
    rx = "".join(".*" if c == "*" else re.escape(c) for c in _norm(kern))
    return re.compile(rx + ("$" if anker else ""))


class Regeln:
    def __init__(self, text: str | None = None, *, alles: bool | None = None):
        self.alles = alles  # True: alles erlaubt, False: alles gesperrt, None: Regeln
        self.gruppen: list[tuple[set[str], list[tuple[bool, str]], float | None]] = []
        if text is not None:
            self._lies(text)

    def _lies(self, text: str):
        agenten: set[str] = set()
        regeln: list[tuple[bool, str]] = []
        verz: float | None = None
        in_regeln = False

        def abschliessen():
            if agenten:
                self.gruppen.append((set(agenten), list(regeln), verz))

        for zeile in text.splitlines():
            zeile = zeile.split("#", 1)[0].strip()
            if ":" not in zeile:
                continue
            feld, wert = (x.strip() for x in zeile.split(":", 1))
            feld = feld.lower()
            if feld == "user-agent":
                if in_regeln:
                    abschliessen()
                    agenten, regeln, verz, in_regeln = set(), [], None, False
                agenten.add(wert.lower())
            elif feld in ("allow", "disallow"):
                in_regeln = True
                if feld == "disallow" and not wert:
                    continue  # leeres Disallow: nichts gesperrt
                regeln.append((feld == "allow", wert))
            elif feld == "crawl-delay":
                in_regeln = True
                try:
                    verz = float(wert)
                except ValueError:
                    pass
        abschliessen()

    def _gruppen_fuer(self, kennung: str):
        k = kennung.lower()
        treffer = [g for g in self.gruppen if k != "*" and k in g[0]]
        return treffer or [g for g in self.gruppen if "*" in g[0]]

    def erlaubt(self, kennung: str, url: str) -> bool:
        if self.alles is not None:
            return self.alles
        t = urllib.parse.urlsplit(url)
        pfad = _norm((t.path or "/") + (f"?{t.query}" if t.query else ""))
        if pfad == "/robots.txt":
            return True
        bestes: tuple[int, bool] | None = None
        for _, regeln, _ in self._gruppen_fuer(kennung):
            for erlaubt_, regel in regeln:
                if _muster(regel).match(pfad):
                    kandidat = (len(regel), erlaubt_)
                    if bestes is None or kandidat[0] > bestes[0] or (kandidat[0] == bestes[0] and erlaubt_):
                        bestes = kandidat
        return True if bestes is None else bestes[1]

    def verzoegerung(self, kennungen=KENNUNGEN) -> float:
        werte = [g[2] for k in kennungen for g in self._gruppen_fuer(k) if g[2] is not None]
        return min(MAX_ABSTAND, max([MIN_ABSTAND, *werte]))


_CACHE: dict[str, Regeln] = {}
TEXTE: dict[str, str] = {}  # robots.txt je Host (für Protokolle)
_ZULETZT: dict[str, float] = {}
_SPERRE = threading.Lock()
_HOST_SPERREN: dict[str, threading.Lock] = {}


def _basis(url: str) -> str:
    t = urllib.parse.urlsplit(url)
    return f"{t.scheme}://{t.netloc}"


def regeln(url: str) -> Regeln:
    basis = _basis(url)
    with _SPERRE:
        r = _CACHE.get(basis)
    if r is not None:
        return r
    try:
        req = urllib.request.Request(basis + "/robots.txt", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as a:
            text = a.read(500_000).decode("utf-8-sig", "replace")
            TEXTE[basis] = text
            r = Regeln(text)
    except urllib.error.HTTPError as e:
        TEXTE[basis] = f"(HTTP {e.code})"
        r = Regeln(alles=False) if e.code in (401, 403) or e.code >= 500 else Regeln(alles=True)
    except Exception as e:  # noqa: BLE001  (nicht erreichbar: gesperrt)
        TEXTE[basis] = f"(nicht erreichbar: {e!r})"[:200]
        r = Regeln(alles=False)
    with _SPERRE:
        _CACHE[basis] = r
    return r


def erlaubt(url: str, kennungen=KENNUNGEN) -> bool:
    r = regeln(url)
    return all(r.erlaubt(k, url) for k in kennungen)


def warte(url: str, kennungen=KENNUNGEN):
    """Abstand je Host einhalten (Crawl-delay, mindestens 1 s)."""
    basis = _basis(url)
    abstand = regeln(url).verzoegerung(kennungen)
    with _SPERRE:
        sperre = _HOST_SPERREN.setdefault(basis, threading.Lock())
    with sperre:
        jetzt = time.monotonic()
        frei = _ZULETZT.get(basis, 0.0) + abstand
        if frei > jetzt:
            time.sleep(frei - jetzt)
        _ZULETZT[basis] = time.monotonic()


class _Weiterleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not erlaubt(newurl):
            raise Gesperrt(newurl)
        warte(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(_Weiterleitung)


def oeffne(url: str, *, daten=None, kopf=None, zeit=60, grenze=25_000_000):
    """Abruf nur, wenn robots.txt ihn erlaubt; hält den Abstand je Host ein."""
    if not erlaubt(url):
        raise Gesperrt(url)
    warte(url)
    k = {"User-Agent": UA, "Accept-Language": "de"} | (kopf or {})
    with OPENER.open(urllib.request.Request(url, data=daten, headers=k), timeout=zeit) as a:
        inhalt = a.read(grenze + 1)
        if len(inhalt) > grenze:
            raise ValueError("zu groß")
        return inhalt, a.geturl(), a.headers.get("Content-Type", "")
