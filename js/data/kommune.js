// kommune.js — Steckbrief einer Kommune: was es dort gibt, je Zählart und Verkehrsart mit Zeitraum
// und Umfang; dazu die Farbe der Kommune in der Karte (der beste Stand beider Zählarten).
//
// REIN halten (kein DOM, kein window): tests/unit/kommune.test.js prüft es browserlos.
//
// Welche Zählungen zu einer Kommune gehören:
// - Kurzzeitzählungen: die ihrer Quellen (`kurzzeit.quellen` in datenlage.json) – jede
//   Kurzzeit-Quelle gehört zu genau einer Kommune, auch Zählungen jenseits der Grenze.
// - Dauerzählstellen: die ihrer eigenen Quellen (`dauer.quellen`, die zu keiner anderen Kommune
//   gehören) ganz, auch Stellen jenseits der Grenze (Hamburg zählt auch in Norderstedt); dazu aus
//   Bündeln (eine Quelle für mehrere Kommunen, etwa MobiData BW) und aus Quellen des Landes oder
//   des Bundes (zu keiner Kommune) die Stellen, die in ihr liegen: Gemeindeschlüssel der Stelle
//   (`ags` in dauer/index.json, Vertrag 5) beginnt mit dem der Kommune (Kreise: fünf Ziffern).
import { THEMEN, hat } from "./modell.js";
import { DAUER_THEMEN } from "./dauer.js";

/** Klassen der Kommunen in der Karte, vom besten Stand an (Farbe und Reihenfolge der Legende). */
export const KOMMUNE_KLASSEN = ["in_karte", "offen", "kandidat", "sonst"];

const bloecke = (p) => [p.kurzzeit, p.dauer].filter(Boolean);

/**
 * Klasse einer Kommune über beide Zählarten: „in_karte“, sobald Zählungen einer Zählart in der
 * Karte sind (auch ohne Lizenz), sonst „offen“ (offen oder herausgegeben), „kandidat“ (erhoben
 * oder ohne Lizenz – eine Anfrage ist aussichtsreich) oder „sonst“ (nur Summen, Karten, nichts
 * offen, abgelehnt).
 */
export function klasseVon(p) {
  const bs = bloecke(p);
  if (bs.some((b) => b.quellen?.length)) return "in_karte";
  const staende = bs.map((b) => b.stand);
  if (staende.some((s) => s === "offen" || s === "geliefert")) return "offen";
  if (staende.some((s) => s === "kandidat" || s === "ohne_lizenz")) return "kandidat";
  return "sonst";
}

/** Je Dauer-Quelle die Zahl der Kommunen, die sie nennen (1: eigene Quelle, mehr: Bündel, 0: Land/Bund). */
export function dauerQuellenJeKommune(datenlage) {
  const n = new Map();
  for (const f of datenlage.features) {
    for (const q of f.properties.dauer?.quellen ?? []) n.set(q, (n.get(q) ?? 0) + 1);
  }
  return n;
}

/** Umriss [[West, Süd], [Ost, Nord]] von Punkten mit Lage (null ohne). */
function umriss(punkte) {
  let w = Infinity; let s = Infinity; let o = -Infinity; let n = -Infinity;
  for (const p of punkte) {
    if (p.lon == null || p.lat == null) continue;
    w = Math.min(w, p.lon); s = Math.min(s, p.lat); o = Math.max(o, p.lon); n = Math.max(n, p.lat);
  }
  return Number.isFinite(w) ? [[w, s], [o, n]] : null;
}

/**
 * Kurzzeitzählungen einer Kommune (ihre Quellen): je Verkehrsart (Themen der Karte) Zählungen,
 * Stellen, Zählungen je Jahr, erstes und letztes Jahr, Umriss der Stellen – nur Verkehrsarten mit
 * Zählungen, in der Reihenfolge der Themen. Dazu Zählungen und Stellen insgesamt.
 */
export function kurzzeitDerKommune(daten, quellen) {
  const codes = new Set(quellen ?? []);
  const stellen = daten.stellen.filter((s) => codes.has(s.quelle));
  const themen = [];
  for (const thema of Object.keys(THEMEN)) {
    const jahre = {};
    let zaehlungen = 0;
    const mit = [];
    for (const s of stellen) {
      const zs = s.zaehlungen.filter((z) => hat(z, thema));
      if (!zs.length) continue;
      mit.push(s);
      for (const z of zs) {
        zaehlungen += 1;
        if (z.jahr != null) jahre[z.jahr] = (jahre[z.jahr] ?? 0) + 1;
      }
    }
    if (!zaehlungen) continue;
    const js = Object.keys(jahre).map(Number);
    themen.push({ thema, zaehlungen, stellen: mit.length, jahre, von: Math.min(...js), bis: Math.max(...js), umriss: umriss(mit) });
  }
  return { themen, zaehlungen: stellen.reduce((n, s) => n + s.zaehlungen.length, 0), stellen: stellen.length };
}

/** Dauerzählstellen einer Kommune (Regel oben). `anzahl`: dauerQuellenJeKommune. */
export function dauerStellenDerKommune(d, p, anzahl) {
  const eigene = new Set(p.dauer?.quellen ?? []);
  return d.stellen.filter((s) => {
    const n = anzahl.get(s.quelle) ?? 0;
    if (n === 1) return eigene.has(s.quelle);
    return s.ags != null && s.ags.startsWith(p.ags);
  });
}

const spaeter = (a, b) => (a > b ? a : b);
const frueher = (a, b) => (a < b ? a : b);

/**
 * Dauerzählstellen einer Kommune: je Verkehrsart (Themen der Dauerzählstellen) Stellen, erster und
 * letzter vollständig gezählter Tag (Zeitraum der Stelle, beschnitten auf den der Gruppe in ihrer
 * Quelle), bis wann es nur Tageswerte der Quelle gibt (`twBis`, null ohne), die Quellen und der
 * Umriss der Stellen. Dazu die Stellen insgesamt und die Quellen.
 */
export function dauerDerKommune(d, p, anzahl) {
  const stellen = dauerStellenDerKommune(d, p, anzahl);
  const meta = new Map(d.quellenMeta.map((q) => [q.code, q]));
  const themen = [];
  for (const [thema, def] of Object.entries(DAUER_THEMEN)) {
    let von = null; let bis = null; let twBis = null;
    const mit = [];
    const quellen = new Set();
    for (const s of stellen) {
      const g = def.gruppen.find((x) => s.gruppen.includes(x));
      if (!g) continue;
      const q = meta.get(s.quelle);
      const [zVon, zBis] = q?.zeitraeume?.[g] ?? [s.von, s.bis];
      const a = spaeter(s.von, zVon);
      const b = frueher(s.bis, zBis);
      if (a > b) continue;
      mit.push(s);
      quellen.add(s.quelle);
      von = von == null ? a : frueher(von, a);
      bis = bis == null ? b : spaeter(bis, b);
      const tw = d.tageswerte_bis?.[g]?.[s.index];
      if (tw) twBis = twBis == null ? tw : spaeter(twBis, tw);
    }
    if (!mit.length) continue;
    themen.push({ thema, stellen: mit.length, von, bis, twBis, quellen: [...quellen], umriss: umriss(mit) });
  }
  const codes = new Set(stellen.map((s) => s.quelle));
  return { themen, stellen: stellen.length, quellen: d.quellenMeta.filter((q) => codes.has(q.code)) };
}

/**
 * Zeitachse des Steckbriefs: erstes und letztes Jahr über alle Zeilen ([von, bis], mindestens
 * drei Jahre breit, damit ein einzelnes Jahr nicht die ganze Breite füllt); null ohne Zeilen.
 */
export function zeitachse(kurzzeit, dauer) {
  const jahre = [
    ...(kurzzeit?.themen ?? []).flatMap((x) => [x.von, x.bis]),
    ...(dauer?.themen ?? []).flatMap((x) => [Number(x.von.slice(0, 4)), Number(x.bis.slice(0, 4))]),
  ];
  if (!jahre.length) return null;
  let von = Math.min(...jahre);
  let bis = Math.max(...jahre);
  while (bis - von < 2) {
    von -= 1;
    if (bis - von < 2) bis += 1;
  }
  return [von, bis];
}

/** Lage eines Tages auf der Zeitachse (0 = 1. Januar des ersten Jahres, 1 = 31. Dezember des letzten). */
export function anteil(iso, achse) {
  const t0 = Date.UTC(achse[0], 0, 1);
  const t1 = Date.UTC(achse[1] + 1, 0, 1);
  const t = Date.UTC(Number(iso.slice(0, 4)), Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10)));
  return Math.min(1, Math.max(0, (t - t0) / (t1 - t0)));
}

/** Kommune einer Kurzzeit-Stelle: die mit ihrer Quelle (Eigenschaften aus datenlage.json) oder null. */
export function kommuneDerStelle(datenlage, s) {
  return datenlage.features.find((f) => f.properties.kurzzeit?.quellen?.includes(s.quelle))?.properties ?? null;
}

/**
 * Kommune einer Dauerzählstelle: bei einer eigenen Quelle deren Kommune, sonst die Kommune, in der
 * sie liegt (die genaueste: Gemeinde vor Kreis); null, wenn keine Kommune der Datenlage passt.
 */
export function kommuneDerDauerstelle(datenlage, s, anzahl) {
  const ps = datenlage.features.map((f) => f.properties);
  if ((anzahl.get(s.quelle) ?? 0) === 1) return ps.find((p) => p.dauer?.quellen?.includes(s.quelle)) ?? null;
  if (!s.ags) return null;
  return ps.filter((p) => s.ags.startsWith(p.ags)).sort((a, b) => b.ags.length - a.ags.length)[0] ?? null;
}
