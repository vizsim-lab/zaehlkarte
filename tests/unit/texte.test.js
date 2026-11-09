// Browserlos: Texte der Oberfläche in beiden Sprachen, Formate, Wechsel der Bezeichnungen.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  SPRACHEN, TEXTE, datum, lokal, name, prozent, setzeSprache, sprache, t, uhr, wochentag, zahl,
} from "../../js/sprache/texte.js";
import { ARTEN, GRUPPEN_NAMEN, TAGE, THEMEN, kennzahlText, stufenText } from "../../js/data/modell.js";

const platzhalter = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

/** Test in einer Sprache, danach wieder Deutsch (der Zustand gilt modulweit). */
function inSprache(s, fn) {
  setzeSprache(s);
  try { fn(); } finally { setzeSprache("de"); }
}

test("beide Sprachen haben dieselben Schlüssel und Platzhalter", () => {
  assert.deepEqual(SPRACHEN, ["de", "en"]);
  assert.deepEqual(Object.keys(TEXTE.en).sort(), Object.keys(TEXTE.de).sort());
  for (const [k, de] of Object.entries(TEXTE.de)) {
    assert.deepEqual(platzhalter(TEXTE.en[k]), platzhalter(de), k);
    if (de) assert.notEqual(TEXTE.en[k], "", `${k}: englischer Text fehlt`);
  }
});

test("Deutsch ist Standard; t() ersetzt Platzhalter und fällt auf Deutsch, dann den Schlüssel zurück", () => {
  assert.equal(sprache(), "de");
  assert.equal(t("detail.n", { n: 3 }), "3 Zählungen");
  assert.equal(t("detail.n", { n: 3 }, "en"), "3 counts");
  assert.equal(t("gibt.es.nicht"), "gibt.es.nicht");
  assert.equal(setzeSprache("fr"), "de"); // Unbekanntes bleibt beim Alten
});

test("Zahlen, Anteile, Daten und Uhrzeiten je Sprache", () => {
  assert.equal(zahl(12345), "12.345");
  assert.equal(zahl(12345, "en"), "12,345");
  assert.equal(prozent(0.053), "5,3 %"); // geschütztes Leerzeichen wie bisher
  assert.equal(prozent(0.053, "en"), "5.3%");
  assert.equal(datum("2025-06-20"), "20.06.2025");
  assert.equal(datum("2025-06-20", "en"), "20 Jun 2025");
  assert.equal(datum("2020-09-03", "en"), "3 Sep 2020"); // nicht „Sept“
  assert.equal(datum(null, "en"), "no date");
  assert.equal(wochentag("2025-06-20", "en"), "Fri");
  assert.equal(uhr("7–19"), "7–19 Uhr");
  assert.equal(uhr("7–19", "en"), "7–19 h");
});

test("feste Namen aus den Daten und Felder mit _en", () => {
  assert.equal(name("Sommerferien"), "Sommerferien");
  assert.equal(name("Sommerferien", "en"), "summer holidays");
  assert.equal(name("Frühspitze", "en"), "Morning peak");
  assert.equal(name("Neuer Feiertag", "en"), "Neuer Feiertag"); // unbekannt: wie geliefert
  const manifest = { stand: { offen: "offen" }, stand_en: { offen: "open" } };
  assert.equal(lokal(manifest, "stand").offen, "offen");
  assert.equal(lokal(manifest, "stand", "en").offen, "open");
  assert.equal(lokal({ stand: { offen: "offen" } }, "stand", "en").offen, "offen");
});

test("Bezeichnungen des Modells folgen dem Sprachwechsel", () => {
  assert.equal(GRUPPEN_NAMEN.sv, "Schwerverkehr");
  assert.equal(kennzahlText("rad", "menge", "w"), "Rad, Summe 7–19 Uhr");
  inSprache("en", () => {
    assert.equal(GRUPPEN_NAMEN.sv, "Heavy vehicles");
    assert.equal(TAGE.f, "School holidays");
    assert.deepEqual(Object.keys(TAGE), ["s", "f", "h", "w", "u"]);
    assert.equal(ARTEN.w24, "24 hours");
    assert.equal(THEMEN.rad.modi.anteil.name, "Cycling share");
    assert.equal(kennzahlText("rad", "menge", "w"), "Cyclists, total 7–19 h");
    assert.equal(kennzahlText("sv", "anteil", "w24"), "Heavy vehicle share (24 hours)");
    assert.equal(kennzahlText("kfz", "menge", "sp"), "Motor vehicles, peak hour");
    assert.deepEqual(stufenText([5000, 10000, 20000, 35000], "menge"),
      ["under 5,000", "5,000 to under 10,000", "10,000 to under 20,000", "20,000 to under 35,000", "35,000 and more"]);
  });
  assert.equal(TAGE.f, "Ferien");
});

test("jeder Datenlage-Stand der Kartendaten hat eine englische Bezeichnung", () => {
  const manifest = JSON.parse(readFileSync(new URL("../../public/data/manifest.json", import.meta.url), "utf-8"));
  assert.deepEqual(Object.keys(manifest.stand_en).sort(), Object.keys(manifest.stand).sort());
});
