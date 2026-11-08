// diagramme.js — Tagesgang und Verlauf an einer Stelle als SVG-Text. REIN (kein DOM): die
// Geometrie wird hier gerechnet und browserlos getestet (tests/unit/diagramme.test.js);
// Hover und Einfügen übernimmt detail.js.
//
// Gestaltung nach den Regeln der Karte: eine y-Achse, 2-px-Linien, zurückhaltendes Raster,
// Werte in Textfarbe; mehr als eine Reihe nur mit derselben Einheit (Fahrzeuge oder Personen
// je Stunde) – Kfz und Schwerverkehr, Fuß und Kinder/Jugendliche.

export const TG = { breite: 340, hoehe: 156, l: 42, r: 10, o: 12, u: 24 };

/** Runde Obergrenze und Schritt für 3–5 Rasterlinien. */
export function achse(max) {
  if (!(max > 0)) return { max: 10, schritt: 5 };
  const roh = max / 4;
  const p = 10 ** Math.floor(Math.log10(roh));
  const schritt = [1, 2, 2.5, 5, 10].map((f) => f * p).find((s) => s >= roh);
  return { max: Math.ceil(max / schritt) * schritt, schritt };
}

const zahl = new Intl.NumberFormat("de-DE");
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

/** Werte je Stunde 0..23 aus einer Reihe ab h0 (fehlende Stunden = null). */
export function proStunde(h0, werte) {
  const out = Array(24).fill(null);
  (werte ?? []).forEach((v, i) => {
    const h = h0 + i;
    if (h >= 0 && h < 24) out[h] = v;
  });
  return out;
}

/** Pfad-Befehle je zusammenhängendem Abschnitt gezählter Stunden. */
export function pfad(stunden, x, y) {
  let d = "";
  let offen = false;
  stunden.forEach((v, h) => {
    if (v == null) { offen = false; return; }
    d += `${offen ? "L" : "M"}${x(h + 0.5).toFixed(1)},${y(v).toFixed(1)}`;
    offen = true;
  });
  return d;
}

/**
 * reihen: [{ id, name, farbe, stunden: [24 Werte|null] }]
 * -> { svg, max } – mit Raster, Achsen, Band der gezählten Stunden und den Linien.
 */
export function tagesgang(reihen, opt = TG) {
  const { breite, hoehe, l, r, o, u } = opt;
  const w = breite - l - r;
  const h = hoehe - o - u;
  const alle = reihen.flatMap((s) => s.stunden.filter((v) => v != null));
  const { max, schritt } = achse(Math.max(0, ...alle));
  const x = (stunde) => l + (stunde / 24) * w;
  const y = (v) => o + h - (v / max) * h;
  const teile = [];
  // gezählte Stunden als helles Band (Lücken = nicht gezählt, nicht null)
  const gezaehlt = Array.from({ length: 24 }, (_, s) => reihen.some((rr) => rr.stunden[s] != null));
  gezaehlt.forEach((g, s) => {
    if (g) teile.push(`<rect class="tg-band" x="${x(s).toFixed(1)}" y="${o}" width="${(w / 24).toFixed(2)}" height="${h}"/>`);
  });
  for (let v = 0; v <= max + 1e-9; v += schritt) {
    teile.push(`<line class="tg-raster" x1="${l}" x2="${l + w}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/>`);
    teile.push(`<text class="tg-tick" x="${l - 6}" y="${(y(v) + 3.5).toFixed(1)}" text-anchor="end">${zahl.format(v)}</text>`);
  }
  for (const s of [0, 6, 12, 18, 24]) {
    teile.push(`<text class="tg-tick" x="${x(s).toFixed(1)}" y="${hoehe - 6}" text-anchor="middle">${s}</text>`);
  }
  teile.push(`<line class="tg-basis" x1="${l}" x2="${l + w}" y1="${o + h}" y2="${o + h}"/>`);
  for (const s of reihen) {
    teile.push(`<path class="tg-linie" stroke="${esc(s.farbe)}" d="${pfad(s.stunden, x, y)}"/>`);
    // einzelne gezählte Stunden ohne Nachbarn wären als Linie unsichtbar -> Punkt
    s.stunden.forEach((v, st) => {
      if (v != null && s.stunden[st - 1] == null && s.stunden[st + 1] == null) {
        teile.push(`<circle class="tg-punkt" fill="${esc(s.farbe)}" cx="${x(st + 0.5).toFixed(1)}" cy="${y(v).toFixed(1)}" r="3"/>`);
      }
    });
  }
  teile.push(`<line class="tg-kreuz" x1="0" x2="0" y1="${o}" y2="${o + h}" visibility="hidden"/>`);
  teile.push(`<rect class="tg-treffer" x="${l}" y="${o}" width="${w}" height="${h}"/>`);
  const svg = `<svg class="tg" viewBox="0 0 ${breite} ${hoehe}" width="100%" role="img">${teile.join("")}</svg>`;
  return { svg, max, x, y };
}

/**
 * Verlauf eines Kennwerts über die Zählungen einer Stelle (Säulen nach Datum).
 * punkte: [{ datum, wert, text, aktiv }], format: Zahl -> Text der Achse
 * -> SVG-Text (leer, wenn weniger als zwei Werte).
 */
export function verlauf(punkte, format = (v) => zahl.format(v), opt = { breite: 340, hoehe: 96, l: 42, r: 10, o: 8, u: 20 }) {
  const mit = punkte.filter((p) => p.wert != null);
  if (mit.length < 2) return "";
  const { breite, hoehe, l, r, o, u } = opt;
  const w = breite - l - r;
  const h = hoehe - o - u;
  const { max, schritt } = achse(Math.max(...mit.map((p) => p.wert)));
  const n = mit.length;
  const spalte = w / n;
  const saeule = Math.max(2, Math.min(18, spalte - 2));
  const teile = [];
  for (let v = 0; v <= max + 1e-9; v += schritt * 2) {
    const yy = o + h - (v / max) * h;
    teile.push(`<line class="tg-raster" x1="${l}" x2="${l + w}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}"/>`);
    teile.push(`<text class="tg-tick" x="${l - 6}" y="${(yy + 3.5).toFixed(1)}" text-anchor="end">${esc(format(v))}</text>`);
  }
  mit.forEach((p, i) => {
    const hh = Math.max(1, (p.wert / max) * h);
    const xx = l + i * spalte + (spalte - saeule) / 2;
    teile.push(`<rect class="vl-saeule${p.aktiv ? " is-aktiv" : ""}" x="${xx.toFixed(1)}" y="${(o + h - hh).toFixed(1)}" width="${saeule.toFixed(1)}" height="${hh.toFixed(1)}" rx="2" data-tip="${esc(p.text)}"/>`);
  });
  teile.push(`<line class="tg-basis" x1="${l}" x2="${l + w}" y1="${o + h}" y2="${o + h}"/>`);
  teile.push(`<text class="tg-tick" x="${l}" y="${hoehe - 5}">${esc(mit[0].datum.slice(0, 4))}</text>`);
  teile.push(`<text class="tg-tick" x="${l + w}" y="${hoehe - 5}" text-anchor="end">${esc(mit[n - 1].datum.slice(0, 4))}</text>`);
  return `<svg class="vl" viewBox="0 0 ${breite} ${hoehe}" width="100%" role="img">${teile.join("")}</svg>`;
}
