// platzRechnung.js — wie viel Karte die schwebenden Panels frei lassen: die reinen Rechnungen für
// js/ui/platz.js. REIN (kein DOM, kein window), browserlos getestet (tests/unit/platz.test.js).
// Rechtecke kommen als einfache Objekte {left, top, right, bottom} in Bildschirm-px herein
// (wie getBoundingClientRect), die freie Fläche geht als {links, rechts, oben, unten} hinaus.

/** Bis zu dieser Fensterbreite (px) gilt das Handy-Layout: Legende und Seitenleisten als Sheets
 *  unten. Darüber stehen Seitenleiste (links, 380 px) und Legende (rechts, 320 px) nebeneinander –
 *  unter etwa 730 px lägen sie aufeinander. Steht auch in index.html und style.css (@media). */
export const MOBIL_BIS = 760;

/** So viel Karte (px) soll zwischen einer offenen Seitenleiste und der Legende frei bleiben;
 *  sonst klappt die Legende auf ihre Kopfzeile zu. Seitenleiste bis 390 px, Legende ab
 *  Fensterbreite − 364 px: das trifft Fenster unter 1234 px. */
export const MIN_KARTE = 480;

/** Bleibt zwischen Seitenleiste (rechter Rand) und Legende (linker Rand) genug Karte? */
export function genugPlatz(panelRechts, legendeLinks) {
  return legendeLinks - panelRechts >= MIN_KARTE;
}

/**
 * Der Teil der Karte, den kein Panel verdeckt.
 * Desktop: links bis zur offenen Seitenleiste, rechts bis zur aufgeklappten Legende – zugeklappt
 * deckt sie nur die Ecke oben rechts, die zählt hier nicht. Handy: oben bis zum Sheet (offene
 * Seitenleiste oder Legende, aufgeklappt oder als Streifen).
 */
export function freieFlaeche({ breite, hoehe, mobil, panel = null, legende = null, legendeZu = false }) {
  const f = { links: 0, rechts: breite, oben: 0, unten: hoehe };
  if (mobil) {
    const kanten = [panel?.top, legende?.top].filter((x) => x != null);
    if (kanten.length) f.unten = Math.max(0, Math.min(hoehe, ...kanten));
    return f;
  }
  if (panel) f.links = Math.max(0, panel.right);
  if (legende && !legendeZu) f.rechts = Math.max(f.links, Math.min(breite, legende.left));
  return f;
}

const mitte = (f) => ({ x: (f.links + f.rechts) / 2, y: (f.oben + f.unten) / 2 });

/**
 * Wie weit die Karte rücken muss (für panBy), damit ein Punkt aus einem Panel heraus in die Mitte
 * des freien Teils kommt – null, wenn er schon frei liegt (mindestens `rand` px vom Rand des
 * freien Teils: Punkt samt Ring) oder gar nicht im Fenster: dann hat man woanders hingesehen,
 * und die Karte bleibt, wo sie ist. Was frei liegt, bleibt liegen – auch dicht an einem Panel.
 */
export function verschiebung(punkt, frei, { breite, hoehe, rand = 16 } = {}) {
  const w = frei.rechts - frei.links;
  const h = frei.unten - frei.oben;
  if (w < 1 || h < 1) return null;
  if (breite != null && (punkt.x < 0 || punkt.x > breite || punkt.y < 0 || punkt.y > hoehe)) return null;
  const r = Math.min(rand, w / 4, h / 4);
  if (punkt.x >= frei.links + r && punkt.x <= frei.rechts - r && punkt.y >= frei.oben + r && punkt.y <= frei.unten - r) return null;
  const m = mitte(frei);
  return [Math.round(punkt.x - m.x), Math.round(punkt.y - m.y)];
}

/** Versatz der Mitte des freien Teils gegen die Fenstermitte (offset für flyTo/easeTo). */
export function versatz(frei, breite, hoehe) {
  const m = mitte(frei);
  return [Math.round(m.x - breite / 2), Math.round(m.y - hoehe / 2)];
}

/**
 * Rand für fitBounds: der verdeckte Teil plus Luft. `obenMin`: oben mindestens so viel (Suche,
 * zugeklappte Legende). Bleibt dazwischen zu wenig, gilt der schlichte Rand.
 */
export function kartenRand(frei, breite, hoehe, obenMin = 70) {
  const r = {
    top: Math.max(obenMin, frei.oben + 30),
    bottom: Math.max(50, hoehe - frei.unten + 30),
    left: Math.max(50, frei.links + 30),
    right: Math.max(50, breite - frei.rechts + 30),
  };
  if (breite - r.left - r.right < 220) Object.assign(r, { left: 50, right: 50 });
  if (hoehe - r.top - r.bottom < 160) Object.assign(r, { top: 70, bottom: 50 });
  return r;
}

/**
 * Rand für das Hover-Kärtchen (Popup.setPadding): MapLibre verankert es dann so, dass es nicht
 * unter die Panels rutscht – neben der Seitenleiste nach rechts, neben der Legende nach links,
 * unter der Suche nach unten. Die Legende zählt nur, wo das Kärtchen ihre Höhe erreichen kann.
 */
export function popupRand(punkt, { breite, hoehe, mobil, panel = null, legende = null, suche = null }, groesse = { breite: 300, hoehe: 200 }) {
  const r = { top: 0, right: 0, bottom: 0, left: 0 };
  if (mobil) {
    const kanten = [panel?.top, legende?.top].filter((x) => x != null);
    if (kanten.length) r.bottom = Math.max(0, hoehe - Math.min(...kanten));
  } else {
    if (panel) r.left = Math.max(0, panel.right);
    if (legende && punkt.y <= legende.bottom + groesse.hoehe) r.right = Math.max(0, breite - legende.left);
  }
  if (suche && punkt.x <= suche.right + groesse.breite / 2) r.top = Math.max(0, suche.bottom);
  return r;
}
