// modell.js — Kartendaten, Filter, Kennwerte und Klassen je Verkehrsart.
//
// REIN halten (kein DOM, kein window): tests/unit/modell.test.js prüft es browserlos.
//
// Die Karte zeigt je Verkehrsart (Kfz, Schwerverkehr, Rad, Fuß) die gezählten Werte. Je Stelle
// steht EINE Zählung aus dem Filter: die jüngste mit Kennwert, sonst die jüngste (hohl
// gezeichnet). Werte aus verschiedenen Zählfenstern werden nie ineinander umgerechnet.
//
// Bezeichnungen kommen aus js/sprache/texte.js und folgen der gewählten Sprache (DE/EN).
import { prozent, t, zahl } from "../sprache/texte.js";

/** {schlüssel: Text} – der Text wird erst beim Lesen geholt, folgt also dem Sprachwechsel. */
function namen(schluessel, praefix) {
  return Object.defineProperties({}, Object.fromEntries(schluessel.map((k) => [
    k, { get: () => t(`${praefix}.${k}`), enumerable: true },
  ])));
}

export const GRUPPEN = ["kfz", "sv", "rad", "fuss", "kind"];
export const GRUPPEN_NAMEN = namen(GRUPPEN, "gruppe");
export const TAGE = namen(["s", "f", "h", "w", "u"], "tag");
export const ARTEN = namen(["w", "w24", "sp"], "art");
const BIT = Object.fromEntries(GRUPPEN.map((g, i) => [g, 1 << i]));

// Eine Blau-Stufung (hell -> dunkel), gegen den Positron-Hintergrund #f2f3f0 geprüft.
export const STUFENFARBEN = ["#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];

// Klassengrenzen (4 Grenzen -> 5 Stufen), an den Quartilen der Berliner Daten ausgerichtet.
export const STUFEN = {
  kfz: { w: [5000, 10000, 20000, 35000], w24: [6000, 12000, 25000, 40000], sp: [500, 1000, 2000, 3500] },
  sv: { w: [250, 500, 1000, 2000], w24: [250, 500, 1000, 2000], sp: [25, 50, 100, 200] },
  rad: { w: [250, 500, 1000, 2500], w24: [250, 500, 1000, 2500], sp: [25, 50, 100, 250] },
  fuss: { w: [100, 300, 1000, 3000], w24: [100, 300, 1000, 3000], sp: [15, 30, 100, 300] },
  anteil: { sv: [0.03, 0.05, 0.08, 0.12], rad: [0.02, 0.05, 0.1, 0.2] },
};

// Verkehrsarten (Themen heißen wie ihre Gruppe) und ihre Darstellungen.
// `braucht` = Gruppen, die eine Zählung haben muss, um in der Darstellung zu erscheinen.
const darstellung = (schluessel, braucht) => ({ get name() { return t(schluessel); }, braucht });
export const THEMEN = {
  kfz: { get name() { return t("gruppe.kfz"); }, modi: { menge: darstellung("modus.menge", ["kfz"]) } },
  sv: {
    get name() { return t("gruppe.sv"); },
    modi: {
      menge: darstellung("modus.menge", ["sv"]),
      anteil: darstellung("modus.sv.anteil", ["kfz", "sv"]),
    },
  },
  rad: {
    get name() { return t("gruppe.rad"); },
    modi: {
      menge: darstellung("modus.menge", ["rad"]),
      anteil: darstellung("modus.rad.anteil", ["rad", "kfz"]),
    },
  },
  fuss: { get name() { return t("gruppe.fuss"); }, modi: { menge: darstellung("modus.menge", ["fuss"]) } },
};

export function standardZustand(jahre, quellen) {
  return {
    thema: "kfz",
    modus: Object.fromEntries(Object.keys(THEMEN).map((t) => [t, "menge"])),
    art: "w",
    jahre: [...jahre],
    tage: new Set(Object.keys(TAGE)),
    quellen: new Set(quellen),
    uebertragen: true,
    datenlage: true,
  };
}

/** index.json -> { stellen, zaehlungen } als Objekte; Stellen kennen ihre Zählungen. */
export function entpacke(index) {
  const sf = index.stellen.felder;
  const zf = index.zaehlungen.felder;
  const stellen = index.stellen.werte.map((r, i) => {
    const o = Object.fromEntries(sf.map((f, j) => [f, r[j]]));
    return { ...o, index: i, quelle: index.quellen[o.quelle], lage: index.lagen[o.lage], zaehlungen: [] };
  });
  const zaehlungen = index.zaehlungen.werte.map((r, i) => {
    const o = Object.fromEntries(zf.map((f, j) => [f, r[j]]));
    o.index = i;
    o.jahr = o.datum ? Number(o.datum.slice(0, 4)) : null;
    o.lieferung = o.l == null ? null : index.lieferungen[o.l];
    stellen[o.stelle].zaehlungen.push(o);
    return o;
  });
  for (const s of stellen) s.zaehlungen.sort((a, b) => (a.datum ?? "").localeCompare(b.datum ?? ""));
  const jahre = zaehlungen.map((z) => z.jahr).filter((j) => j != null);
  return {
    stellen,
    zaehlungen,
    quellen: index.quellen,
    jahre: [Math.min(...jahre), Math.max(...jahre)],
  };
}

export const hat = (z, g) => (z.g & BIT[g]) !== 0;

/** Wert einer Gruppe in einer Kennzahl-Art ("w" 7–19 Uhr, "w24", "sp" stärkste Stunde). */
export function wert(z, g, art) {
  const liste = z[art];
  return liste ? (liste[GRUPPEN.indexOf(g)] ?? null) : null;
}

/**
 * Kennwert einer Zählung: die Menge der Verkehrsart oder ihr Anteil (0..1) –
 * Schwerverkehr an allen Kfz, Rad an Rad + Kfz. null = in dieser Art nicht gezählt.
 */
export function kennwert(z, thema, modus, art) {
  if (modus !== "anteil") return wert(z, thema, art);
  const kfz = wert(z, "kfz", art);
  const teil = wert(z, thema, art);
  if (teil == null || kfz == null) return null;
  const ganz = thema === "sv" ? kfz : teil + kfz;
  return ganz > 0 ? teil / ganz : null;
}

export function stufenFuer(thema, modus, art) {
  return modus === "anteil" ? STUFEN.anteil[thema] : STUFEN[thema][art];
}

/** Stufe 0..4 eines Werts zu 4 Grenzen (Grenze gehört zur oberen Stufe). */
export function stufe(v, grenzen) {
  let k = 0;
  while (k < grenzen.length && v >= grenzen[k]) k += 1;
  return k;
}

function imFilter(z, zustand, braucht) {
  if (z.jahr == null || z.jahr < zustand.jahre[0] || z.jahr > zustand.jahre[1]) return false;
  if (!zustand.tage.has(z.tag ?? "u")) return false;
  return braucht.every((g) => hat(z, g));
}

export function stelleSichtbar(s, zustand) {
  return zustand.quellen.has(s.quelle) && (zustand.uebertragen || s.lage !== "uebertragen");
}

/** Je sichtbare Stelle die gezeigte Zählung mit Kennwert und Stufe (-1 = kein Kennwert). */
export function ansicht(daten, zustand) {
  const { thema } = zustand;
  const modus = zustand.modus[thema];
  const braucht = THEMEN[thema].modi[modus].braucht;
  const grenzen = stufenFuer(thema, modus, zustand.art);
  const out = [];
  for (const s of daten.stellen) {
    if (!stelleSichtbar(s, zustand)) continue;
    const zs = s.zaehlungen.filter((z) => imFilter(z, zustand, braucht));
    if (!zs.length) continue;
    let gewaehlt = null;
    let v = null;
    for (let i = zs.length - 1; i >= 0; i -= 1) {
      v = kennwert(zs[i], thema, modus, zustand.art);
      if (v != null) { gewaehlt = zs[i]; break; }
    }
    if (!gewaehlt) { gewaehlt = zs[zs.length - 1]; v = null; }
    out.push({ stelle: s, z: gewaehlt, wert: v, stufe: v == null ? -1 : stufe(v, grenzen), n: zs.length });
  }
  return out;
}

/** Zähler für Fußzeile und Filter: Zählungen im Filter, je Zähltag, Stellen je Quelle. */
export function zaehlen(daten, zustand, eintraege) {
  const { thema } = zustand;
  const braucht = THEMEN[thema].modi[zustand.modus[thema]].braucht;
  const tage = Object.fromEntries(Object.keys(TAGE).map((t) => [t, 0]));
  let zaehlungen = 0;
  for (const s of daten.stellen) {
    if (!stelleSichtbar(s, zustand)) continue;
    for (const z of s.zaehlungen) {
      if (z.jahr == null || z.jahr < zustand.jahre[0] || z.jahr > zustand.jahre[1]) continue;
      if (!braucht.every((g) => hat(z, g))) continue;
      tage[z.tag ?? "u"] += 1;
      if (zustand.tage.has(z.tag ?? "u")) zaehlungen += 1;
    }
  }
  const quellen = Object.fromEntries(daten.quellen.map((q) => [q, 0]));
  for (const e of eintraege) quellen[e.stelle.quelle] += 1;
  return { stellen: eintraege.length, zaehlungen, tage, quellen };
}

/** Anzahl je Legendenzeile: Stufen 0..4 und -1 (kein Kennwert). */
export function zaehleKlassen(eintraege) {
  const n = {};
  for (const e of eintraege) n[String(e.stufe)] = (n[String(e.stufe)] ?? 0) + 1;
  return n;
}

/** GeoJSON für die Kartenquelle: Farbe, Rand, Radius und Zeichenreihenfolge je Punkt. */
export function features(eintraege) {
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
          z: e.z.index,
          c: mit ? STUFENFARBEN[e.stufe] : "rgba(255, 255, 255, 0.85)",
          sc: mit ? "rgba(17, 24, 39, 0.45)" : "#8b929c",
          r: mit ? 2.4 + e.stufe * 0.7 : 2.4,
          o: mit ? e.stufe + 1 : 0,
        },
      };
    }),
  };
}

export function formatiere(v, modus) {
  if (v == null) return "–";
  return modus === "anteil" ? prozent(v) : zahl(v);
}

/** Bezeichnung der gezeigten Kennzahl, etwa „Rad, Summe 7–19 Uhr“ oder „Radanteil (24 Stunden)“. */
export function kennzahlText(thema, modus, art) {
  if (modus === "anteil") return t("kennzahl.anteil", { anteil: t(`anteil.${thema}`), art: ARTEN[art] });
  return art === "sp"
    ? t("kennzahl.spitze", { gruppe: GRUPPEN_NAMEN[thema] })
    : t("kennzahl.summe", { gruppe: GRUPPEN_NAMEN[thema], art: ARTEN[art] });
}

/** Legendenzeilen zu Grenzen: ["unter 5.000", "5.000 bis unter 10.000", …, "ab 35.000"]. */
export function stufenText(grenzen, modus) {
  const f = (v) => formatiere(v, modus);
  return [
    t("stufe.unter", { wert: f(grenzen[0]) }),
    ...grenzen.slice(0, -1).map((g, i) => t("stufe.bis", { von: f(g), bis: f(grenzen[i + 1]) })),
    t("stufe.ab", { wert: f(grenzen[grenzen.length - 1]) }),
  ];
}

function csvFeld(v) {
  if (v == null) return "";
  const s = String(v);
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/**
 * CSV (Semikolon, UTF-8) aller Zählungen im Filter – nicht nur der gezeigten je Stelle.
 * Spalten und Werte bleiben in jeder Sprache gleich (deutsch), damit Auswertungen nicht brechen.
 */
export function csv(daten, zustand, lizenzVon) {
  const kopf = [
    "quelle", "stelle", "name", "typ", "lon", "lat", "lage", "datum", "zaehltag", "fenster",
    ...GRUPPEN.map((g) => `${g}_7_19`), ...GRUPPEN.map((g) => `${g}_24h`),
    ...GRUPPEN.map((g) => `${g}_spitzenstunde`), "lizenz",
  ];
  const zeilen = [kopf.join(";")];
  for (const s of daten.stellen) {
    if (!stelleSichtbar(s, zustand)) continue;
    for (const z of s.zaehlungen) {
      if (!imFilter(z, zustand, [])) continue;
      zeilen.push([
        s.quelle, s.id, s.name, s.typ, s.lon, s.lat, s.lage, z.datum, t(`tag.${z.tag ?? "u"}`, {}, "de"), z.fenster,
        ...GRUPPEN.map((g) => wert(z, g, "w")), ...GRUPPEN.map((g) => wert(z, g, "w24")),
        ...GRUPPEN.map((g) => wert(z, g, "sp")), lizenzVon(s.quelle, z.lieferung),
      ].map(csvFeld).join(";"));
    }
  }
  return `﻿${zeilen.join("\n")}\n`;
}
