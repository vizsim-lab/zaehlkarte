// Platz der Panels (js/utils/platzRechnung.js): freie Fläche, Nachrücken der Auswahl, Ränder für
// fitBounds und das Hover-Kärtchen – browserlos, mit Rechtecken wie aus getBoundingClientRect.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MIN_KARTE, MOBIL_BIS, freieFlaeche, genugPlatz, kartenRand, popupRand, verschiebung, versatz,
} from "../../js/utils/platzRechnung.js";

const rechteck = (left, top, right, bottom) => ({ left, top, right, bottom });
// Desktop 1440 × 900: Seitenleiste links (10–390), Legende rechts (1076–1430)
const PANEL = rechteck(10, 60, 390, 836);
const LEGENDE = rechteck(1076, 60, 1430, 816);
const SUCHE = rechteck(10, 10, 390, 52);
const DESKTOP = { breite: 1440, hoehe: 900, mobil: false };

test("Handy-Layout bis 760 px, 480 px Karte zwischen den Panels", () => {
  assert.equal(MOBIL_BIS, 760);
  assert.equal(MIN_KARTE, 480);
});

test("genug Platz: ab 1234 px Fensterbreite bleiben Seitenleiste und Legende nebeneinander", () => {
  // Legende 320 px + Innenabstand, 10 px vom Rand: ihr linker Rand liegt bei Breite − 364
  assert.equal(genugPlatz(390, 1440 - 364), true);
  assert.equal(genugPlatz(390, 1280 - 364), true);
  assert.equal(genugPlatz(390, 1234 - 364), true);
  assert.equal(genugPlatz(390, 1233 - 364), false);
  assert.equal(genugPlatz(390, 1024 - 364), false);
  assert.equal(genugPlatz(390, 870), true); // genau 480 px
  assert.equal(genugPlatz(390, 869), false);
});

test("freie Fläche am Desktop: zwischen Seitenleiste und aufgeklappter Legende", () => {
  assert.deepEqual(freieFlaeche({ ...DESKTOP, panel: PANEL, legende: LEGENDE }),
    { links: 390, rechts: 1076, oben: 0, unten: 900 });
  // zugeklappt deckt die Legende nur eine Ecke: rechts frei bis zum Rand
  assert.deepEqual(freieFlaeche({ ...DESKTOP, panel: PANEL, legende: LEGENDE, legendeZu: true }),
    { links: 390, rechts: 1440, oben: 0, unten: 900 });
  assert.deepEqual(freieFlaeche({ ...DESKTOP, legende: LEGENDE }), { links: 0, rechts: 1076, oben: 0, unten: 900 });
});

test("freie Fläche am Handy: über dem Sheet (Seitenleiste oder Legende)", () => {
  const handy = { breite: 390, hoehe: 844, mobil: true };
  const streifen = rechteck(0, 730, 390, 844);
  assert.deepEqual(freieFlaeche({ ...handy, legende: streifen, legendeZu: true }), { links: 0, rechts: 390, oben: 0, unten: 730 });
  const sheet = rechteck(0, 253, 390, 844);
  assert.deepEqual(freieFlaeche({ ...handy, panel: sheet, legende: streifen, legendeZu: true }), { links: 0, rechts: 390, oben: 0, unten: 253 });
});

test("verschiebung: nur, was unter einem Panel liegt, rückt in die Mitte des freien Teils", () => {
  const frei = { links: 390, rechts: 1076, oben: 0, unten: 900 };
  const fenster = { breite: 1440, hoehe: 900 };
  assert.equal(verschiebung({ x: 700, y: 450 }, frei, fenster), null); // frei
  assert.equal(verschiebung({ x: 410, y: 450 }, frei, fenster), null); // dicht am Panel, aber frei
  // unter der Seitenleiste: in die Mitte (733, 450)
  assert.deepEqual(verschiebung({ x: 200, y: 300 }, frei, fenster), [200 - 733, 300 - 450]);
  // unter der Legende
  assert.deepEqual(verschiebung({ x: 1200, y: 450 }, frei, fenster), [1200 - 733, 0]);
  // gar nicht im Fenster: die Karte bleibt
  assert.equal(verschiebung({ x: -300, y: 450 }, frei, fenster), null);
  // Handy: unter dem Sheet -> über das Sheet
  assert.deepEqual(verschiebung({ x: 195, y: 422 }, { links: 0, rechts: 390, oben: 0, unten: 253 }, { breite: 390, hoehe: 844 }),
    [0, Math.round(422 - 253 / 2)]);
  // keine freie Fläche: nichts zu tun
  assert.equal(verschiebung({ x: 10, y: 10 }, { links: 400, rechts: 400, oben: 0, unten: 900 }, fenster), null);
});

test("versatz: Mitte des freien Teils gegen die Fenstermitte (für flyTo)", () => {
  assert.deepEqual(versatz({ links: 390, rechts: 1024, oben: 0, unten: 768 }, 1024, 768), [195, 0]);
  assert.deepEqual(versatz({ links: 0, rechts: 390, oben: 0, unten: 253 }, 390, 844), [0, -295]);
  assert.deepEqual(versatz({ links: 0, rechts: 800, oben: 0, unten: 600 }, 800, 600), [0, 0]);
});

test("kartenRand: verdeckter Teil plus Luft, sonst der schlichte Rand", () => {
  assert.deepEqual(kartenRand({ links: 390, rechts: 1076, oben: 0, unten: 900 }, 1440, 900),
    { top: 70, bottom: 50, left: 420, right: 394 });
  // zugeklappte Legende oben rechts: oben mehr Rand
  assert.equal(kartenRand({ links: 390, rechts: 1024, oben: 0, unten: 768 }, 1024, 768, 232).top, 232);
  // zu schmal dazwischen: links und rechts schlicht
  const eng = kartenRand({ links: 390, rechts: 600, oben: 0, unten: 900 }, 1024, 900);
  assert.equal(eng.left, 50);
  assert.equal(eng.right, 50);
  // Handy: unten bis über den Streifen
  assert.equal(kartenRand({ links: 0, rechts: 390, oben: 0, unten: 730 }, 390, 844).bottom, 144);
});

test("popupRand: das Kärtchen weicht Seitenleiste, Legende und Suche aus", () => {
  const lage = { ...DESKTOP, panel: PANEL, legende: LEGENDE, suche: SUCHE };
  assert.deepEqual(popupRand({ x: 700, y: 450 }, lage), { top: 0, right: 364, bottom: 0, left: 390 });
  // unter der zugeklappten Legende (Kopfzeile bis 212): weit darunter zählt sie nicht
  const zu = { ...lage, legende: rechteck(1076, 60, 1430, 212) };
  assert.equal(popupRand({ x: 1000, y: 800 }, zu).right, 0);
  assert.equal(popupRand({ x: 1000, y: 300 }, zu).right, 364);
  // neben der Suche: oben Abstand
  assert.equal(popupRand({ x: 450, y: 80 }, lage).top, 52);
  assert.equal(popupRand({ x: 900, y: 80 }, lage).top, 0);
  // Handy: unten das Sheet
  const handy = { breite: 390, hoehe: 844, mobil: true, legende: rechteck(0, 730, 390, 844) };
  assert.equal(popupRand({ x: 200, y: 400 }, handy).bottom, 114);
});
