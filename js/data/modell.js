// modell.js — Kartendaten, Filter, Kennzahlen, Klassen und das Schulweg-Kriterium.
//
// REIN halten (kein DOM, kein window): tests/unit/modell.test.js prüft es browserlos. Das
// Kriterium (`verdacht`, `status`) rechnet die Pipeline gleich (pipeline/src/zaehlkarte/
// kennzahlen.py); beide Seiten lesen dieselben Fälle aus tests/fixtures/kriterium.json.
//
// Je Stelle zeigt die Karte EINE Zählung aus dem Filter: bei Mengen und Anteilen die jüngste
// mit Kennwert (sonst die jüngste, hohl gezeichnet), beim Schulweg-Verdacht die stärkste
// Einstufung (Verdacht vor kein Verdacht vor schulfrei vor nicht beurteilbar).

export const GRUPPEN = ["kfz", "sv", "rad", "fuss", "kind"];
export const GRUPPEN_NAMEN = { kfz: "Kfz", sv: "Schwerverkehr", rad: "Rad", fuss: "Fuß", kind: "Kinder/Jugendliche" };
export const TAGE = { s: "Schultag", f: "Ferien", h: "Feiertag", w: "Wochenende", u: "unbekannt" };
export const ARTEN = { w: "7–19 Uhr", w24: "24 Stunden", sp: "stärkste Stunde" };
const BIT = Object.fromEntries(GRUPPEN.map((g, i) => [g, 1 << i]));

// Farben: sequentiell eine Blau-Stufung (hell -> dunkel, gegen den Positron-Hintergrund
// #f2f3f0 geprüft), Einstufungen in den ersten beiden Kategorienfarben + neutralem Grau.
export const STUFENFARBEN = ["#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
export const STATUSFARBEN = { verdacht: "#eb6834", kein: "#2a78d6", schulfrei: "#9ca3af", unbekannt: null };
export const STATUS_NAMEN = {
  verdacht: "Schulweg-Verdacht",
  kein: "kein Verdacht",
  schulfrei: "schulfreier Tag",
  unbekannt: "nicht beurteilbar",
};
const STATUS_RANG = { verdacht: 3, kein: 2, schulfrei: 1, unbekannt: 0 };

// Klassengrenzen (4 Grenzen -> 5 Stufen), an den Quartilen der Berliner Daten ausgerichtet.
export const STUFEN = {
  kfz: { w: [5000, 10000, 20000, 35000], w24: [6000, 12000, 25000, 40000], sp: [500, 1000, 2000, 3500] },
  rad: { w: [250, 500, 1000, 2500], w24: [250, 500, 1000, 2500], sp: [25, 50, 100, 250] },
  fuss: { w: [100, 300, 1000, 3000], w24: [100, 300, 1000, 3000], sp: [15, 30, 100, 300] },
  svanteil: [0.03, 0.05, 0.08, 0.12],
  radanteil: [0.02, 0.05, 0.1, 0.2],
};

// Themen und ihre Modi. `braucht` = Gruppen, die eine Zählung haben muss, um zu erscheinen.
export const THEMEN = {
  kfz: {
    name: "Kfz",
    modi: {
      menge: { name: "Menge", braucht: ["kfz"] },
      svanteil: { name: "Schwerverkehrsanteil", braucht: ["kfz", "sv"] },
    },
  },
  rad: {
    name: "Rad",
    modi: {
      menge: { name: "Menge", braucht: ["rad"] },
      radanteil: { name: "Radanteil", braucht: ["rad", "kfz"] },
    },
  },
  fuss: {
    name: "Fuß & Schulweg",
    modi: {
      verdacht: { name: "Schulweg-Verdacht", braucht: ["fuss"] },
      menge: { name: "Menge", braucht: ["fuss"] },
    },
  },
};

export function standardZustand(kriterien, jahre, quellen) {
  return {
    thema: "fuss",
    modus: { kfz: "menge", rad: "menge", fuss: "verdacht" },
    art: "w",
    jahre: [...jahre],
    tage: new Set(Object.keys(TAGE)),
    quellen: new Set(quellen),
    uebertragen: true,
    kriterien: {
      schulstunden: [...kriterien.schulstunden],
      schwelle_stunde: kriterien.schwelle_stunde,
      schwelle_tag: kriterien.schwelle_tag,
      tag_von: kriterien.tag_von,
      tag_bis: kriterien.tag_bis,
    },
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

/** Kennwert für Thema/Modus: Menge oder Anteil (0..1); null = in dieser Art nicht gezählt. */
export function kennwert(z, thema, modus, art) {
  if (modus === "svanteil") {
    const sv = wert(z, "sv", art);
    const kfz = wert(z, "kfz", art);
    return sv != null && kfz ? sv / kfz : null;
  }
  if (modus === "radanteil") {
    const rad = wert(z, "rad", art);
    const kfz = wert(z, "kfz", art);
    return rad != null && kfz != null && rad + kfz > 0 ? rad / (rad + kfz) : null;
  }
  return wert(z, thema, art); // Themen heißen wie ihre Gruppe (kfz, rad, fuss)
}

export function stufenFuer(thema, modus, art) {
  if (modus === "svanteil" || modus === "radanteil") return STUFEN[modus];
  return STUFEN[thema][art];
}

/** Stufe 0..4 eines Werts zu 4 Grenzen (Grenze gehört zur oberen Stufe). */
export function stufe(v, grenzen) {
  let k = 0;
  while (k < grenzen.length && v >= grenzen[k]) k += 1;
  return k;
}

/** Schulweg-Kriterium wie kennzahlen.verdacht: { wert: true|false|null, gruende }. */
export function verdacht(kh0, kh, k) {
  const kind = new Map();
  (kh ?? []).forEach((v, i) => { if (v != null) kind.set(kh0 + i, v); });
  if (!kind.size) return { wert: null, gruende: ["Kinder/Jugendliche nicht gezählt"] };
  const gruende = k.schulstunden
    .filter((h) => (kind.get(h) ?? -1) > k.schwelle_stunde)
    .map((h) => `${h} Uhr: ${kind.get(h)}`);
  let tag = 0;
  for (let h = k.tag_von; h < k.tag_bis; h += 1) {
    if (!kind.has(h)) { tag = null; break; }
    tag += kind.get(h);
  }
  if (tag != null && tag > k.schwelle_tag) gruende.push(`${k.tag_von}–${k.tag_bis} Uhr: ${tag}`);
  if (tag == null && !k.schulstunden.some((h) => kind.has(h))) {
    return { wert: null, gruende: ["zu Schulzeiten nicht gezählt"] };
  }
  return { wert: gruende.length > 0, gruende };
}

/** Einordnung wie kennzahlen.status: an schulfreien Tagen nie Verdacht. */
export function status(kriterium, tag) {
  if (kriterium == null) return "unbekannt";
  if (tag === "f" || tag === "h" || tag === "w") return "schulfrei";
  return kriterium ? "verdacht" : "kein";
}

export function bewerte(z, k) {
  const v = verdacht(z.kh0, z.kh, k);
  return { ...v, status: status(v.wert, z.tag) };
}

function imFilter(z, zustand, braucht) {
  if (z.jahr == null || z.jahr < zustand.jahre[0] || z.jahr > zustand.jahre[1]) return false;
  if (!zustand.tage.has(z.tag ?? "u")) return false;
  return braucht.every((g) => hat(z, g));
}

export function stelleSichtbar(s, zustand) {
  return zustand.quellen.has(s.quelle) && (zustand.uebertragen || s.lage !== "uebertragen");
}

/** Je sichtbare Stelle die gezeigte Zählung samt Einordnung. */
export function ansicht(daten, zustand) {
  const { thema } = zustand;
  const modus = zustand.modus[thema];
  const braucht = THEMEN[thema].modi[modus].braucht;
  const grenzen = modus === "verdacht" ? null : stufenFuer(thema, modus, zustand.art);
  const out = [];
  for (const s of daten.stellen) {
    if (!stelleSichtbar(s, zustand)) continue;
    const zs = s.zaehlungen.filter((z) => imFilter(z, zustand, braucht));
    if (!zs.length) continue;
    if (modus === "verdacht") {
      let best = null;
      for (const z of zs) {
        const b = bewerte(z, zustand.kriterien);
        if (!best || STATUS_RANG[b.status] >= STATUS_RANG[best.b.status]) best = { z, b };
      }
      const n = zs.filter((z) => bewerte(z, zustand.kriterien).status === "verdacht").length;
      out.push({ stelle: s, z: best.z, status: best.b.status, stufe: null, wert: null, n: zs.length, nVerdacht: n });
      continue;
    }
    let gewaehlt = null;
    let v = null;
    for (let i = zs.length - 1; i >= 0; i -= 1) {
      v = kennwert(zs[i], thema, modus, zustand.art);
      if (v != null) { gewaehlt = zs[i]; break; }
    }
    if (!gewaehlt) { gewaehlt = zs[zs.length - 1]; v = null; }
    out.push({
      stelle: s,
      z: gewaehlt,
      status: null,
      wert: v,
      stufe: v == null ? -1 : stufe(v, grenzen),
      n: zs.length,
    });
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

/** Anzahl je Legendenzeile: Stufen 0..4 und -1 (kein Kennwert) bzw. je Status. */
export function zaehleKlassen(eintraege) {
  const n = {};
  for (const e of eintraege) {
    const k = e.status ?? String(e.stufe);
    n[k] = (n[k] ?? 0) + 1;
  }
  return n;
}

/** GeoJSON für die Kartenquelle: Farbe, Rand, Radius und Zeichenreihenfolge je Punkt. */
export function features(eintraege) {
  return {
    type: "FeatureCollection",
    features: eintraege.map((e) => {
      let farbe;
      let rand = "rgba(17, 24, 39, 0.45)";
      let r = 3.2;
      let ordnung = 0;
      if (e.status) {
        farbe = STATUSFARBEN[e.status];
        ordnung = STATUS_RANG[e.status];
        if (!farbe) { farbe = "rgba(255, 255, 255, 0.85)"; rand = "#8b929c"; r = 2.6; }
        if (e.status === "schulfrei") r = 2.8;
      } else if (e.stufe >= 0) {
        farbe = STUFENFARBEN[e.stufe];
        r = 2.4 + e.stufe * 0.7;
        ordnung = e.stufe + 1;
      } else {
        farbe = "rgba(255, 255, 255, 0.85)";
        rand = "#8b929c";
        r = 2.4;
      }
      return {
        type: "Feature",
        id: e.stelle.index,
        geometry: { type: "Point", coordinates: [e.stelle.lon, e.stelle.lat] },
        properties: { i: e.stelle.index, z: e.z.index, c: farbe, sc: rand, r, o: ordnung },
      };
    }),
  };
}

const zahl = new Intl.NumberFormat("de-DE");
const prozent = new Intl.NumberFormat("de-DE", { style: "percent", maximumFractionDigits: 1 });

export function formatiere(v, modus) {
  if (v == null) return "–";
  return modus === "svanteil" || modus === "radanteil" ? prozent.format(v) : zahl.format(v);
}

/** Legendenzeilen zu Grenzen: ["unter 5.000", "5.000–10.000", …, "ab 35.000"]. */
export function stufenText(grenzen, modus) {
  const f = (v) => formatiere(v, modus);
  return [
    `unter ${f(grenzen[0])}`,
    ...grenzen.slice(0, -1).map((g, i) => `${f(g)} bis unter ${f(grenzen[i + 1])}`),
    `ab ${f(grenzen[grenzen.length - 1])}`,
  ];
}

function csvFeld(v) {
  if (v == null) return "";
  const s = String(v);
  return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** CSV (Semikolon, UTF-8) aller Zählungen im Filter – nicht nur der gezeigten je Stelle. */
export function csv(daten, zustand, lizenzVon) {
  const kopf = [
    "quelle", "stelle", "name", "typ", "lon", "lat", "lage", "datum", "zaehltag", "fenster",
    ...GRUPPEN.map((g) => `${g}_7_19`), ...GRUPPEN.map((g) => `${g}_24h`),
    ...GRUPPEN.map((g) => `${g}_spitzenstunde`), "schulweg", "lizenz",
  ];
  const zeilen = [kopf.join(";")];
  for (const s of daten.stellen) {
    if (!stelleSichtbar(s, zustand)) continue;
    for (const z of s.zaehlungen) {
      if (!imFilter(z, zustand, [])) continue;
      const b = hat(z, "kind") ? bewerte(z, zustand.kriterien).status : "";
      zeilen.push([
        s.quelle, s.id, s.name, s.typ, s.lon, s.lat, s.lage, z.datum, TAGE[z.tag ?? "u"], z.fenster,
        ...GRUPPEN.map((g) => wert(z, g, "w")), ...GRUPPEN.map((g) => wert(z, g, "w24")),
        ...GRUPPEN.map((g) => wert(z, g, "sp")), b, lizenzVon(s.quelle, z.lieferung),
      ].map(csvFeld).join(";"));
    }
  }
  return `﻿${zeilen.join("\n")}\n`;
}
