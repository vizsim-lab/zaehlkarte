// dauer.js — Familie Dauerzählstellen: Stellen, Tagessumme am gewählten Tag, Klassen, CSV.
//
// REIN halten (kein DOM, kein window): tests/unit/dauer.test.js prüft es browserlos.
// Daten aus public/data/dauer/ (pipeline/src/zaehlkarte/dauer/site.py): index.json beim
// Umschalten, tage/JJJJ.json für das Jahr des gewählten Tags, NN.json erst beim Klick.
//
// Eine Tagessumme gibt es nur, wenn jede Stunde des Tages gezählt ist – null heißt „nicht
// vollständig gezählt“, nie 0. Keine Mittelwerte, keine Hochrechnung: gezeigt wird der Tag.
import { datum, t } from "../sprache/texte.js";
import { STUFENFARBEN, stufe } from "./modell.js";

// Gruppen, wie die Quellen sie zählen – nie ineinander gemischt: Berlins „Lkw“ und Hamburgs
// „Schwerverkehr“ sind je eine Klasse des Detektors, keiner der Schwerverkehr der
// Kurzzeitzählungen. Welche es gibt, steht in dauer/index.json (`gruppen`, Bits der Stellen).
export const DAUER_GRUPPEN = ["kfz", "lkw", "sv", "rad", "fuss"];
export const DAUER_THEMEN = {
  kfz: { get name() { return t("gruppe.kfz"); } },
  lkw: { get name() { return t("gruppe.lkw"); } },
  sv: { get name() { return t("gruppe.sv_detektor"); } },
  rad: { get name() { return t("gruppe.rad"); } },
  fuss: { get name() { return t("gruppe.fuss"); } },
};

// Klassengrenzen der Tagessummen je Zählstelle (4 Grenzen -> 5 Stufen), an den Quintilen der
// Quellen ausgerichtet (Bericht von `zaehlkarte dauer site`, November 2026):
// Kfz Berlin 6.350 / 9.760 / 12.820 / 16.820, Hamburg 5.000 / 8.140 / 11.950 / 18.190;
// Lkw Berlin 190 / 360 / 590 / 990; Schwerverkehr Hamburg 170 / 350 / 600 / 990;
// Rad Hamburg 360 / 660 / 1.100 / 1.950. Fuß: noch keine Quelle (Platzhalter).
export const DAUER_STUFEN = {
  kfz: [6000, 10000, 13000, 17000],
  lkw: [200, 350, 600, 1000],
  sv: [200, 350, 600, 1000],
  rad: [350, 700, 1100, 2000],
  fuss: [500, 1000, 2500, 5000],
};

const TAG_MS = 86_400_000;
/** "2025-06-26" -> Tage seit 1970-01-01 (UTC, ohne Zeitzone). */
export const tagNr = (iso) => Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))) / TAG_MS;
export const isoAus = (nr) => new Date(nr * TAG_MS).toISOString().slice(0, 10);
export const tageZwischen = (von, bis) => tagNr(bis) - tagNr(von);
export const plusTage = (iso, n) => isoAus(tagNr(iso) + n);
const gueltigesDatum = (iso) => /^\d{4}-\d{2}-\d{2}$/.test(iso ?? "") && isoAus(tagNr(iso)) === iso;

/** index.json -> { stellen (Objekte), quellen (Codes), quellenMeta, … } */
export function entpackeDauer(index) {
  const f = index.stellen.felder;
  const gruppen = index.gruppen ?? ["kfz"];
  const stellen = index.stellen.werte.map((r, i) => {
    const s = Object.fromEntries(f.map((k, j) => [k, r[j]]));
    return { ...s, index: i, gruppen: gruppen.filter((_, b) => (s.g & (1 << b)) !== 0) };
  });
  return {
    ...index,
    stellen,
    quellen: index.quellen.map((q) => q.code),
    quellenMeta: index.quellen,
    // Zeitraum je Quelle und Gruppe: Hamburg zählt Schwerverkehr länger als Kfz (Stunden der
    // Quelle verfallen nach zwei Monaten) – außerhalb fehlt die Gruppe, statt „nicht vollständig“
    zeitraeume: new Map(index.quellen.map((q) => [q.code, q.zeitraeume ?? {}])),
    jeId: new Map(stellen.map((s) => [s.id, s])),
  };
}

/** Gewählter Tag innerhalb des Zeitraums; ungültig oder außerhalb -> Standardtag der Daten. */
export function tagImZeitraum(d, iso) {
  if (!gueltigesDatum(iso)) return d.standardtag ?? d.bis;
  if (iso < d.von) return d.von;
  if (iso > d.bis) return d.bis;
  return iso;
}

/** Tagtyp am Tag (s Schultag, f Ferien, h Feiertag, w Wochenende, u unbekannt). */
export function tagtyp(d, land, iso) {
  const k = d.kalender?.[land];
  return (k && k[tageZwischen(d.von, iso)]) || "u";
}

export const hatGruppe = (s, g) => s.gruppen.includes(g);

/**
 * Stellen derselben Quelle am selben Punkt, die Stelle selbst eingeschlossen (Ettlingen: alle
 * Fahrtrichtungen eines Sensors haben eine Lage). In der Karte liegen sie übereinander – die
 * Seitenleiste schaltet zwischen ihnen um. Nur eine Stelle -> [stelle].
 */
export function amSelbenPunkt(d, stelle) {
  return d.stellen.filter((s) => s.quelle === stelle.quelle && s.lon === stelle.lon && s.lat === stelle.lat);
}

/** Gruppe, die die Karte zeigt: die gewählte, wenn es sie gibt, sonst die erste der Daten. */
export const themaIn = (d, g) => (d.gruppen.includes(g) ? g : d.gruppen[0]);

/**
 * Quellen, die die Gruppe zählen, aber am Tag keine Werte haben (ihr Zeitraum für die Gruppe
 * endet vorher oder beginnt später): [{ quelle, von, bis, sprung }] – `sprung` ist der
 * Standardtag der Quelle, liegt er außerhalb, das Ende ihres Zeitraums.
 */
export function quellenOhneTag(d, g, iso) {
  const out = [];
  for (const q of d.quellenMeta) {
    if (!(q.gruppen ?? d.gruppen).includes(g)) continue;
    const [von, bis] = q.zeitraeume?.[g] ?? [q.von, q.bis];
    if (iso >= von && iso <= bis) continue;
    const sprung = q.standardtag && q.standardtag >= von && q.standardtag <= bis ? q.standardtag : bis;
    out.push({ quelle: q, von, bis, sprung });
  }
  return out;
}

/** Tagtyp je Land der Quellen, die den Tag abdecken: [{ land, typ }] (gleiche Typen zusammen). */
export function tagtypen(d, iso) {
  const laender = [...new Set(d.quellenMeta.filter((q) => q.von <= iso && iso <= q.bis).map((q) => q.land))];
  const liste = (laender.length ? laender : [d.quellenMeta[0]?.land]).map((land) => ({ land, typ: tagtyp(d, land, iso) }));
  return new Set(liste.map((x) => x.typ)).size === 1 ? [{ land: null, typ: liste[0].typ }] : liste;
}

/** Tagessumme einer Stelle am Tag aus der Jahresdatei (null = nicht vollständig gezählt). */
export function wertAm(jahr, stelle, g, iso) {
  const reihe = jahr?.werte?.[g]?.[stelle.index];
  if (!reihe) return null;
  return reihe[tageZwischen(`${iso.slice(0, 4)}-01-01`, iso)] ?? null;
}

/** Je Stelle, die an dem Tag besteht und die Gruppe zählt: Wert und Stufe (-1 = nicht vollständig). */
export function ansichtDauer(d, zustand, jahr, iso) {
  const g = zustand.dthema;
  const grenzen = DAUER_STUFEN[g];
  const out = [];
  for (const s of d.stellen) {
    if (iso < s.von || iso > s.bis || !hatGruppe(s, g)) continue;
    const z = d.zeitraeume?.get(s.quelle)?.[g];
    if (z && (iso < z[0] || iso > z[1])) continue;
    const v = wertAm(jahr, s, g, iso);
    out.push({ stelle: s, wert: v, stufe: v == null ? -1 : stufe(v, grenzen) });
  }
  return out;
}

export function zaehleDauer(eintraege) {
  const klassen = {};
  for (const e of eintraege) klassen[String(e.stufe)] = (klassen[String(e.stufe)] ?? 0) + 1;
  return { stellen: eintraege.length, vollstaendig: eintraege.filter((e) => e.stufe >= 0).length, klassen };
}

/** GeoJSON für die Kartenquelle „dauer“: Farbe, Rand, Radius, Reihenfolge wie bei den Kurzzeitzählungen. */
export function featuresDauer(eintraege) {
  return {
    type: "FeatureCollection",
    features: eintraege.map((e) => {
      const mit = e.stufe >= 0;
      return {
        type: "Feature",
        id: e.stelle.index,
        geometry: { type: "Point", coordinates: [e.stelle.lon, e.stelle.lat] },
        properties: {
          i: e.stelle.index,
          c: mit ? STUFENFARBEN[e.stufe] : "rgba(255, 255, 255, 0.85)",
          sc: mit ? "rgba(17, 24, 39, 0.55)" : "#8b929c",
          r: mit ? 2.6 + e.stufe * 0.7 : 2.6,
          o: mit ? e.stufe + 1 : 0,
        },
      };
    }),
  };
}

/** Zeitraum einer Quelle oder Stelle: über Jahre „2015–2025“, sonst die Tage. */
export function zeitraumText(von, bis) {
  if (Number(bis.slice(0, 4)) - Number(von.slice(0, 4)) >= 2) return `${von.slice(0, 4)}–${bis.slice(0, 4)}`;
  return `${datum(von)} – ${datum(bis)}`;
}

/** Bezeichnung der gezeigten Kennzahl: „Kfz, Tagessumme am 26.06.2025“. */
export function kennzahlTextDauer(g, datumText) {
  return t("dauer.kennzahl", { gruppe: DAUER_THEMEN[g].name, datum: datumText });
}

function csvFeld(v) {
  if (v == null) return "";
  const s = String(v);
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * CSV (Semikolon, UTF-8) aller Stellen, die am Tag bestehen: Tagessummen je Gruppe, leer =
 * nicht vollständig gezählt. Spalten und Werte deutsch, in jeder Sprache gleich.
 */
export function csvDauer(d, jahr, iso, lizenzVon) {
  const kopf = ["quelle", "stelle", "name", "abschnitt", "richtung", "lon", "lat", "datum", "tagtyp",
    ...d.gruppen.map((g) => `${g}_tagessumme`), "lizenz"];
  const zeilen = [kopf.join(";")];
  for (const s of d.stellen) {
    if (iso < s.von || iso > s.bis) continue;
    const q = d.quellenMeta.find((x) => x.code === s.quelle);
    zeilen.push([
      s.quelle, s.id, s.name, s.abschnitt, s.richtung, s.lon, s.lat, iso,
      t(`tag.${tagtyp(d, q?.land, iso)}`, {}, "de"),
      ...d.gruppen.map((g) => (hatGruppe(s, g) ? wertAm(jahr, s, g, iso) : null)),
      lizenzVon(s.quelle),
    ].map(csvFeld).join(";"));
  }
  return `﻿${zeilen.join("\n")}\n`;
}

/** Stundenwerte einer Stelle am Tag aus den Details (null außerhalb der jüngsten 12 Monate). */
export function stundenAm(detail, g, iso) {
  if (!detail?.stunden?.[g] || iso < detail.stunden_von) return null;
  return detail.stunden[g][tageZwischen(detail.stunden_von, iso)] ?? null;
}

/** Tagessumme und gezählte Stunden einer Gruppe am Tag aus den Details. */
export function tagAusDetail(detail, g, iso) {
  const i = tageZwischen(detail.von, iso);
  if (i < 0) return { wert: null, stunden: 0 };
  return { wert: detail.tage?.[g]?.[i] ?? null, stunden: detail.n?.[g]?.[i] ?? 0 };
}

/** Stunden, die es am Tag gibt: 23 am Tag der Umstellung auf Sommerzeit, sonst 24. */
export function stundenDesTags(iso) {
  const j = Number(iso.slice(0, 4));
  const maerz = tagNr(`${j}-03-31`);
  const sonntag = maerz - ((new Date(maerz * TAG_MS).getUTCDay() + 7) % 7);
  return tagNr(iso) === sonntag ? 23 : 24;
}
