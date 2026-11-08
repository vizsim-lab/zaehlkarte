// Browserlos: Datenmodell, Kennwerte je Verkehrsart, Klassen, Zähler und CSV.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ansicht, csv, entpacke, features, kennwert, kennzahlText, standardZustand, stufe, stufenText, zaehlen,
} from "../../js/data/modell.js";

const INDEX = {
  version: 1,
  quellen: ["berlin", "ravensburg"],
  lagen: ["gps", "quelle", "geokodiert", "uebertragen"],
  gruppen: ["kfz", "sv", "rad", "fuss", "kind"],
  lieferungen: ["berlin:2019-2025", "berlin:1990-2019"],
  stellen: {
    felder: ["id", "quelle", "name", "typ", "lon", "lat", "lage", "chunk"],
    werte: [
      ["berlin:K1", 0, "A / B", "K", 13.4, 52.5, 0, 0],
      ["ravensburg:1000", 1, "C / D", "K", 9.6, 47.8, 1, 1],
      ["berlin:K2", 0, "E", "Q", 13.5, 52.4, 3, 0],
    ],
  },
  zaehlungen: {
    felder: ["stelle", "datum", "tag", "fenster", "g", "w", "w24", "sp", "l"],
    werte: [
      [0, "2010-05-05", "s", "7–19", 1 | 4 | 8 | 16, [20000, null, 800, 900, 120], null, [2500, null, 90, 100, 30], 1],
      [0, "2020-05-05", "s", "15–19", 1 | 4, null, null, [2600, null, 120, null, null], 0],
      [1, "2024-07-11", "f", "0–24", 1 | 2 | 4 | 8, [12000, 1500, 300, 200, null], [16000, 1900, 400, 250, null], [1600, 200, 40, 30, null], null],
      [2, "1995-03-01", null, "7–19", 1, [3000, null, null, null, null], null, [400, null, null, null, null], 1],
    ],
  },
};

const daten = entpacke(INDEX);
const basis = () => standardZustand(daten.jahre, daten.quellen);

test("entpacke: Stellen kennen ihre Zählungen, Jahre und Lieferungen", () => {
  assert.equal(daten.stellen.length, 3);
  assert.deepEqual(daten.jahre, [1995, 2024]);
  assert.equal(daten.stellen[0].zaehlungen.length, 2);
  assert.equal(daten.stellen[2].lage, "uebertragen");
  assert.equal(daten.zaehlungen[0].lieferung, "berlin:1990-2019");
});

test("Stufen: Grenze gehört zur oberen Stufe", () => {
  assert.equal(stufe(4999, [5000, 10000, 20000, 35000]), 0);
  assert.equal(stufe(5000, [5000, 10000, 20000, 35000]), 1);
  assert.equal(stufe(99999, [5000, 10000, 20000, 35000]), 4);
  const texte = stufenText([0.02, 0.05, 0.1, 0.2], "anteil").map((t) => t.replaceAll("\u00a0", " "));
  assert.deepEqual(texte.slice(0, 2), ["unter 2 %", "2 % bis unter 5 %"]);
});

test("Kennwerte je Verkehrsart: Menge, Schwerverkehrs- und Radanteil", () => {
  const z = daten.zaehlungen[2];
  assert.equal(kennwert(z, "kfz", "menge", "w24"), 16000);
  assert.equal(kennwert(z, "sv", "menge", "w"), 1500);
  assert.equal(kennwert(z, "sv", "anteil", "w"), 1500 / 12000);
  assert.equal(kennwert(z, "rad", "anteil", "w"), 300 / 12300);
  assert.equal(kennwert(daten.zaehlungen[1], "rad", "menge", "w"), null);
  assert.equal(kennzahlText("rad", "anteil", "w24"), "Radanteil (24 Stunden)");
  assert.equal(kennzahlText("fuss", "menge", "w"), "Fuß, Summe 7–19 Uhr");
});

test("Ansicht: jüngste Zählung mit Kennwert, sonst hohl", () => {
  const z = basis();
  z.thema = "rad";
  const e = ansicht(daten, z);
  const k1 = e.find((x) => x.stelle.id === "berlin:K1");
  assert.equal(k1.z.datum, "2010-05-05"); // 2020 hat keine 7–19-Summe
  assert.equal(k1.wert, 800);
  z.art = "sp";
  assert.equal(ansicht(daten, z).find((x) => x.stelle.id === "berlin:K1").z.datum, "2020-05-05");
  z.jahre = [2015, 2024];
  z.art = "w";
  const nur = ansicht(daten, z).find((x) => x.stelle.id === "berlin:K1");
  assert.equal(nur.stufe, -1); // nur die 15–19-Zählung im Zeitraum
});

test("Ansicht: Filter nach Zähltag, Quelle und übernommener Lage", () => {
  const z = basis();
  z.thema = "fuss";
  assert.deepEqual(ansicht(daten, z).map((e) => e.stelle.id).sort(), ["berlin:K1", "ravensburg:1000"]);
  z.tage.delete("s");
  assert.deepEqual(ansicht(daten, z).map((e) => e.stelle.id), ["ravensburg:1000"]);
  const k = basis();
  k.uebertragen = false;
  assert.equal(ansicht(daten, k).some((x) => x.stelle.id === "berlin:K2"), false);
  k.quellen.delete("ravensburg");
  assert.deepEqual(ansicht(daten, k).map((e) => e.stelle.id), ["berlin:K1"]);
  const sv = basis();
  sv.thema = "sv";
  assert.deepEqual(ansicht(daten, sv).map((e) => [e.stelle.id, e.wert]), [["ravensburg:1000", 1500]]);
  const fc = features(ansicht(daten, basis()));
  assert.equal(fc.features.length, 3);
  assert.ok(fc.features.every((f) => f.properties.c && f.properties.r > 0));
});

test("Zähler und CSV", () => {
  const z = basis();
  z.thema = "kfz";
  const e = ansicht(daten, z);
  const n = zaehlen(daten, z, e);
  assert.equal(n.stellen, 3);
  assert.equal(n.zaehlungen, 4);
  assert.deepEqual(n.quellen, { berlin: 2, ravensburg: 1 });
  const text = csv(daten, z, () => "dl-de/by-2-0");
  const zeilen = text.trim().split("\n");
  assert.equal(zeilen.length, 5);
  assert.ok(text.startsWith("\ufeffquelle;stelle;name"));
  assert.ok(!zeilen[0].includes("schulweg"));
});
