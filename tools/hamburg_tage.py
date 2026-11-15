"""Hamburg: Tageswerte (Layer „1-Tag“) der Infrarot-Dienste erkunden – für die Tageswerte der
Quelle vor den Stunden des Gedächtnisses (App-Branch hamburg-tageswerte).

Fragen:
1. Welche Datastreams gibt es je Gruppe (Kfz, Schwerverkehr, Rad), an denselben Things wie die
   Stunden? Seit wann, bis wann (phenomenonTime der Datastreams)?
2. Wie sehen die Tageswerte aus: Zeitstempel (Ortstag oder UTC-Tag? Zeitumstellung: 23/25 h),
   Werte (ganze Zahlen, null, negativ, doppelte Tage), Lücken, Werte je Jahr, resultTime
   (übernommen aus den alten Diensten?).
3. Passen sie zu den Stunden: Tageswert = Summe der Stunden des Ortstags? Was liefert die Quelle
   an Tagen, an denen Stunden fehlen?
4. Was sagt die Datensatzbeschreibung im Transparenzportal (CKAN-API, wenn robots.txt es erlaubt)?
5. Wie lange dauert der erste volle Abruf (verschachteltes $expand je Seite Datastreams)?

Nur Abrufe, die robots.txt für unsere Kennung, „*“ und die Kennungen von Claude erlaubt
(tools/robots.py, mit Crawl-delay). Aufruf: python3 tools/hamburg_tage.py <zielordner>
"""

from __future__ import annotations

import html
import json
import re
import statistics
import sys
import time
import traceback
import urllib.parse
from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import robots  # noqa: E402

BASIS = "https://iot.hamburg.de/v1.1"
BERLIN = ZoneInfo("Europe/Berlin")
GRUPPEN = {
    "kfz": ("HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren", "Anzahl_Kfz_Zaehlstelle"),
    "sv": ("HH_STA_Verkehrsdaten_Kfz_Infrarotdetektoren", "Anzahl_Schwerverkehr_Zaehlstelle"),
    "rad": ("HH_STA_Verkehrsdaten_Rad_Infrarotdetektoren", "Anzahl_Fahrraeder_Zaehlstelle"),
}
PORTAL = {"kfz": "verkehrsdaten-kfz-infrarotdetektoren-hamburg14",
          "rad": "verkehrsdaten-rad-infrarotdetektoren-hamburg20"}
JE_GRUPPE = 12  # Stichprobe je Gruppe

ziel = Path(sys.argv[1])
ziel.mkdir(parents=True, exist_ok=True)
out: list[str] = []
daten: dict = {}


def schreib() -> None:
    (ziel / "bericht.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
    (ziel / "daten.json").write_text(json.dumps(daten, ensure_ascii=False, indent=1),
                                     encoding="utf-8")


def hole(url: str, versuche: int = 4) -> dict:
    for i in range(versuche):
        try:
            inhalt, _, _ = robots.oeffne(url, zeit=240, grenze=400_000_000)
            return json.loads(inhalt)
        except robots.Gesperrt:
            raise
        except Exception:  # noqa: BLE001
            if i == versuche - 1:
                raise
            time.sleep(10 * (i + 1))
    raise RuntimeError("unerreichbar")


def url(pfad: str, **p: str) -> str:
    return f"{BASIS}/{pfad}?" + urllib.parse.urlencode(p, safe="$(),;'/=:",
                                                       quote_via=urllib.parse.quote)


def alle(u: str) -> list[dict]:
    werte: list[dict] = []
    while u:
        d = hole(u)
        werte += d.get("value", [])
        u = d.get("@iot.nextLink")
    return werte


def zeit(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def kennung(ds: dict) -> str | None:
    t = ds.get("Thing") or {}
    return (t.get("properties") or {}).get("assetID") or t.get("name")


def datastreams(gruppe: str, intervall: str) -> list[dict]:
    dienst, praefix = GRUPPEN[gruppe]
    f = (f"properties/serviceName eq '{dienst}' and "
         f"properties/layerName eq '{praefix}_{intervall}'")
    return alle(url("Datastreams", **{
        "$filter": f, "$top": "500", "$select": "id,name,description,phenomenonTime,properties",
        "$expand": "Thing($select=id,name,properties)"}))


def lokal(t: datetime) -> datetime:
    return t.astimezone(BERLIN)


def tagesart(von: datetime, bis: datetime) -> str:
    """Ortstag (Mitternacht bis Mitternacht Ortszeit), UTC-Tag oder etwas anderes."""
    lv, lb = lokal(von), lokal(bis + timedelta(seconds=1))
    if (lv.hour, lv.minute, lv.second) == (0, 0, 0) and (lb.hour, lb.minute, lb.second) == (0, 0, 0) \
            and lb.date() == lv.date() + timedelta(days=1):
        return "ortstag"
    uv, ub = von.astimezone(UTC), (bis + timedelta(seconds=1)).astimezone(UTC)
    if (uv.hour, uv.minute) == (0, 0) and ub == uv + timedelta(days=1):
        return "utc_tag"
    return "sonst"


def umstellungen(jahr: int) -> tuple[date, date]:
    def letzter_sonntag(monat: int) -> date:
        d = date(jahr, monat, 31)
        return d - timedelta(days=(d.weekday() - 6) % 7)
    return letzter_sonntag(3), letzter_sonntag(10)


def beobachtungen(ds_id: int) -> list[dict]:
    return alle(url(f"Datastreams({ds_id})/Observations", **{
        "$select": "phenomenonTime,result,resultTime", "$orderby": "phenomenonTime asc",
        "$top": "10000"}))


def tage_auswerten(obs: list[dict]) -> tuple[dict, dict[date, int]]:
    """-> (Kennzahlen, {Ortstag: Wert}) aus den Tageswerten eines Datastreams."""
    arten, werte_art, result_tage = Counter(), Counter(), Counter()
    je_tag: dict[date, list] = defaultdict(list)
    dauer_umst: dict[str, float] = {}
    for o in obs:
        try:
            a, b = (zeit(x) for x in o["phenomenonTime"].split("/"))
        except Exception:  # noqa: BLE001
            arten["unlesbar"] += 1
            continue
        art = tagesart(a, b)
        arten[art] += 1
        w = o.get("result")
        if w is None:
            werte_art["null"] += 1
        elif isinstance(w, bool) or not isinstance(w, int):
            werte_art[f"typ {type(w).__name__}"] += 1
        elif w < 0:
            werte_art["negativ"] += 1
        elif w == 0:
            werte_art["null_wert_0"] += 1
        else:
            werte_art["positiv"] += 1
        tag = lokal(a).date()
        je_tag[tag].append(w)
        if o.get("resultTime"):
            result_tage[o["resultTime"][:10]] += 1
        for jahr in range(2019, 2028):
            for u in umstellungen(jahr):
                if tag == u:
                    dauer_umst[tag.isoformat()] = round((b - a).total_seconds() / 3600 + 1 / 3600, 2)
    doppelt = {t: v for t, v in je_tag.items() if len(v) > 1}
    tage = {t: v[0] for t, v in je_tag.items()
            if len(v) == 1 and isinstance(v[0], int) and not isinstance(v[0], bool) and v[0] >= 0}
    if je_tag:
        erster, letzter = min(je_tag), max(je_tag)
        spanne = (letzter - erster).days + 1
    else:
        erster = letzter = None
        spanne = 0
    je_jahr = Counter(t.year for t in tage)
    median_jahr = {j: int(statistics.median([w for t, w in tage.items() if t.year == j]))
                   for j in sorted(je_jahr)}
    k = {
        "anzahl": len(obs), "zeitstempel": dict(arten), "werte": dict(werte_art),
        "erster": erster.isoformat() if erster else None,
        "letzter": letzter.isoformat() if letzter else None,
        "fehlende_tage_in_spanne": spanne - len(je_tag),
        "doppelte_tage": {t.isoformat(): v for t, v in list(doppelt.items())[:5]},
        "anzahl_doppelt": len(doppelt),
        "je_jahr": dict(sorted(je_jahr.items())), "median_je_jahr": median_jahr,
        "resulttime_tage": dict(result_tage.most_common(6)),
        "dauer_umstellungstage_h": dauer_umst,
    }
    return k, tage


def stunden_je_tag(obs: list[dict]) -> tuple[dict[date, dict[int, int]], dict[date, dict[int, int]], Counter]:
    """Stundenwerte -> {Ortstag: {UTC-Stunde (als Index der Ortsstunde): Wert}} und
    {UTC-Tag: {UTC-Stunde: Wert}}; Schlüssel der Ortstage: Beginn der Stunde in UTC (Sekunden)."""
    orts: dict[date, dict[int, int]] = defaultdict(dict)
    utc: dict[date, dict[int, int]] = defaultdict(dict)
    arten = Counter()
    for o in obs:
        try:
            a, b = (zeit(x) for x in o["phenomenonTime"].split("/"))
        except Exception:  # noqa: BLE001
            arten["unlesbar"] += 1
            continue
        w = o.get("result")
        if not isinstance(w, int) or isinstance(w, bool) or w < 0:
            arten["kein_wert"] += 1
            continue
        if (b - a) != timedelta(minutes=59, seconds=59) or a.minute or a.second:
            arten["keine_volle_stunde"] += 1
            continue
        arten["ok"] += 1
        orts[lokal(a).date()][int(a.timestamp())] = w
        utc[a.astimezone(UTC).date()][a.astimezone(UTC).hour] = w
    return orts, utc, arten


def stunden_am_tag(tag: date) -> int:
    a = datetime(tag.year, tag.month, tag.day, tzinfo=BERLIN)
    n = tag + timedelta(days=1)
    b = datetime(n.year, n.month, n.day, tzinfo=BERLIN)
    return round((b.astimezone(UTC) - a.astimezone(UTC)).total_seconds() / 3600)


def vergleich(tage: dict[date, int], orts: dict, utc: dict) -> dict:
    if not orts:
        return {"stunden": 0}
    erster, letzter = min(orts), max(orts)
    voll_gleich = voll_anders = voll_ohne_tw = teil_mit_tw = leer_mit_tw = 0
    utc_gleich = 0
    beispiele_anders, beispiele_teil, quoten = [], [], []
    t = erster
    while t <= letzter:
        h = orts.get(t, {})
        soll = stunden_am_tag(t)
        tw = tage.get(t)
        if len(h) == soll:
            s = sum(h.values())
            if tw is None:
                voll_ohne_tw += 1
            elif tw == s:
                voll_gleich += 1
            else:
                voll_anders += 1
                if len(beispiele_anders) < 6:
                    beispiele_anders.append([t.isoformat(), tw, s])
            u = utc.get(t, {})
            if tw is not None and len(u) == 24 and sum(u.values()) == tw and sum(u.values()) != s:
                utc_gleich += 1
        elif h:
            if tw is not None:
                teil_mit_tw += 1
                s = sum(h.values())
                if s:
                    quoten.append(tw / s)
                if len(beispiele_teil) < 6:
                    beispiele_teil.append([t.isoformat(), len(h), soll, tw, s])
        elif tw is not None:
            leer_mit_tw += 1
        t += timedelta(days=1)
    return {
        "stunden_von": erster.isoformat(), "stunden_bis": letzter.isoformat(),
        "voll_gleich": voll_gleich, "voll_anders": voll_anders, "voll_ohne_tageswert": voll_ohne_tw,
        "gleich_utc_statt_ortstag": utc_gleich,
        "teil_mit_tageswert": teil_mit_tw, "ohne_stunden_mit_tageswert": leer_mit_tw,
        "quote_tageswert_zu_stunden_bei_teil": (round(statistics.median(quoten), 3)
                                               if quoten else None),
        "beispiele_anders [tag, tageswert, stundensumme]": beispiele_anders,
        "beispiele_teil [tag, stunden, soll, tageswert, summe]": beispiele_teil,
    }


def jahr_von(text: str | None) -> str:
    if not text:
        return "ohne"
    return str(lokal(zeit(text.split("/")[0])).year)


def main() -> None:
    t0 = time.time()
    # ------------------------------------------------------------------ 1. Datastreams
    listen: dict[str, dict[str, list[dict]]] = {}
    for gruppe in GRUPPEN:
        listen[gruppe] = {}
        for intervall in ("1-Tag", "1-Stunde"):
            try:
                listen[gruppe][intervall] = datastreams(gruppe, intervall)
            except Exception:  # noqa: BLE001
                listen[gruppe][intervall] = []
                out.append(f"FEHLER Datastreams {gruppe} {intervall}: "
                           + traceback.format_exc().splitlines()[-1])
        tag, std = listen[gruppe]["1-Tag"], listen[gruppe]["1-Stunde"]
        k_tag = Counter(kennung(d) for d in tag)
        k_std = Counter(kennung(d) for d in std)
        things_tag = {(d.get("Thing") or {}).get("@iot.id") for d in tag}
        things_std = {(d.get("Thing") or {}).get("@iot.id") for d in std}
        beginn = Counter(jahr_von(d.get("phenomenonTime")) for d in tag)
        ende = Counter((lokal(zeit(d["phenomenonTime"].split("/")[1])).date().isoformat()[:7]
                        if d.get("phenomenonTime") else "ohne") for d in tag)
        spanne = sum(((zeit(d["phenomenonTime"].split("/")[1]) -
                       zeit(d["phenomenonTime"].split("/")[0])).days + 1)
                     for d in tag if d.get("phenomenonTime"))
        out.extend([f"== {gruppe}: {len(tag)} Datastreams 1-Tag, {len(std)} Datastreams 1-Stunde",
                f"  Kennungen: Tag {len(k_tag)}, Stunde {len(k_std)}, beide {len(set(k_tag) & set(k_std))}, "
                f"nur Tag {len(set(k_tag) - set(k_std))} {sorted(map(str, set(k_tag) - set(k_std)))[:8]}, "
                f"nur Stunde {len(set(k_std) - set(k_tag))}; mehrere Tages-Datastreams je Kennung: "
                f"{[k for k, n in k_tag.items() if n > 1][:5]}",
                f"  Things: gleiche {len(things_tag & things_std)}, nur Tag {len(things_tag - things_std)}",
                f"  Beginn der Tagesreihen je Jahr (Ortszeit): {dict(sorted(beginn.items()))}",
                f"  Ende der Tagesreihen je Monat: {dict(sorted(ende.items()))}",
                f"  Tage in den Spannen zusammen (Obergrenze der Werte): {spanne}"])
        if tag:
            b = tag[0]
            out.append("  Beispiel: " + json.dumps({k: b.get(k) for k in ("name", "description", "properties")},
                                                    ensure_ascii=False)[:900])
        daten.setdefault("datastreams", {})[gruppe] = {
            "tag": [[d["@iot.id"], kennung(d), d.get("phenomenonTime")] for d in tag],
            "stunde": [[d["@iot.id"], kennung(d), d.get("phenomenonTime")] for d in std]}
        schreib()
    out.append(f"(Datastreams: {time.time() - t0:.0f} s)")

    # ------------------------------------------------------------------ 2./3. Stichprobe
    for gruppe in GRUPPEN:
        tag = sorted((d for d in listen[gruppe]["1-Tag"] if d.get("phenomenonTime")),
                     key=lambda d: str(kennung(d)))
        std = {kennung(d): d for d in listen[gruppe]["1-Stunde"]}
        if not tag:
            continue
        # gleichmäßig verteilt, dazu die mit dem frühesten Beginn
        schritt = max(1, len(tag) // JE_GRUPPE)
        auswahl = tag[::schritt][:JE_GRUPPE]
        frueh = min(tag, key=lambda d: d["phenomenonTime"])
        if frueh not in auswahl:
            auswahl.append(frueh)
        out.append(f"== Stichprobe {gruppe}: {len(auswahl)} Datastreams")
        summe = Counter()
        for d in auswahl:
            k = kennung(d)
            try:
                obs = beobachtungen(d["@iot.id"])
                kz, tage = tage_auswerten(obs)
                h = std.get(k)
                vg = {}
                if h is not None:
                    orts, utc, arten = stunden_je_tag(beobachtungen(h["@iot.id"]))
                    vg = vergleich(tage, orts, utc) | {"stunden_arten": dict(arten)}
                for f in ("voll_gleich", "voll_anders", "teil_mit_tageswert",
                          "ohne_stunden_mit_tageswert", "voll_ohne_tageswert",
                          "gleich_utc_statt_ortstag"):
                    summe[f] += vg.get(f, 0)
                summe["tageswerte"] += len(tage)
                out.append(f"  {k} (Tag {d['@iot.id']}, Stunde {h['@iot.id'] if h else '–'}): "
                           + json.dumps(kz, ensure_ascii=False))
                out.append("    Vergleich mit den Stunden: " + json.dumps(vg, ensure_ascii=False))
                daten.setdefault("stichprobe", {}).setdefault(gruppe, {})[k] = {
                    "kennzahlen": kz, "vergleich": vg,
                    "tage": {t.isoformat(): w for t, w in sorted(tage.items())}}
            except Exception:  # noqa: BLE001
                out.append(f"  {k}: FEHLER " + traceback.format_exc().splitlines()[-1])
            schreib()
        out.append(f"  Summe {gruppe}: {dict(summe)}")
    out.append(f"(Stichprobe: {time.time() - t0:.0f} s)")
    schreib()

    # ------------------------------------------------------------------ 5. erster voller Abruf
    for gruppe, je_seite in (("rad", 10), ("kfz", 40)):
        dienst, praefix = GRUPPEN[gruppe]
        f = f"properties/serviceName eq '{dienst}' and properties/layerName eq '{praefix}_1-Tag'"
        u = url("Datastreams", **{
            "$filter": f, "$select": "id", "$top": str(je_seite),
            "$expand": "Observations($select=phenomenonTime,result;$orderby=phenomenonTime asc;"
                       "$top=10000)"})
        t1 = time.time()
        try:
            inhalt, _, _ = robots.oeffne(u, zeit=600, grenze=800_000_000)
            d = json.loads(inhalt)
            n = sum(len(x.get("Observations", [])) for x in d.get("value", []))
            weiter = sum(1 for x in d.get("value", []) if x.get("Observations@iot.nextLink"))
            out.append(f"== Seite mit {je_seite} Datastreams ({gruppe}, 1-Tag, alle Werte): "
                       f"{time.time() - t1:.0f} s, {len(inhalt) / 1e6:.1f} MB, {n} Werte, "
                       f"{weiter} Reihen mit nextLink, nächste Seite: {bool(d.get('@iot.nextLink'))}")
        except Exception:  # noqa: BLE001
            out.append(f"== Seite mit {je_seite} Datastreams ({gruppe}): FEHLER nach "
                       f"{time.time() - t1:.0f} s: " + traceback.format_exc().splitlines()[-1])
        schreib()

    # ------------------------------------------------------------------ 4. Datensatzbeschreibung
    for gruppe, paket in PORTAL.items():
        u = f"https://suche.transparenz.hamburg.de/api/3/action/package_show?id={paket}"
        try:
            if not robots.erlaubt(u):
                out.append(f"== Transparenzportal {paket}: robots.txt sperrt die API")
                continue
            d = hole(u)["result"]
            text = html.unescape(re.sub(r"<[^>]+>", " ", d.get("notes") or ""))
            out.append(f"== Transparenzportal {paket}: {d.get('title')}")
            out.append("  Beschreibung: " + re.sub(r"\s+", " ", text).strip()[:5000])
            out.append(f"  Lizenz: {d.get('license_id')} {d.get('license_title')}; geändert "
                       f"{d.get('metadata_modified')}")
            for r in d.get("resources") or []:
                out.append(f"  Ressource: {r.get('name')} | {r.get('format')} | {r.get('url')}")
            for e in d.get("extras") or []:
                if any(s in str(e.get("key")) for s in ("temporal", "zeit", "update", "frequency")):
                    out.append(f"  {e.get('key')}: {str(e.get('value'))[:200]}")
        except Exception:  # noqa: BLE001
            out.append(f"== Transparenzportal {paket}: FEHLER "
                       + traceback.format_exc().splitlines()[-1])
        schreib()
    out.append("robots.txt: " + json.dumps({k: v[:400] for k, v in robots.TEXTE.items()},
                                            ensure_ascii=False))
    out.append(f"(gesamt: {time.time() - t0:.0f} s)")
    schreib()


if __name__ == "__main__":
    main()
