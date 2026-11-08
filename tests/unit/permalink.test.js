import { test } from "node:test";
import assert from "node:assert/strict";
import { standardZustand } from "../../js/data/modell.js";
import { dekodiere, kodiere } from "../../js/utils/permalinkFormat.js";

const QUELLEN = ["berlin", "ravensburg"];
const std = () => standardZustand([1983, 2026], QUELLEN);

test("Standard ergibt einen leeren Link", () => {
  assert.equal(kodiere(std(), std(), null, null), "");
});

test("Hin und zurück", () => {
  const z = std();
  z.thema = "rad";
  z.modus.rad = "anteil";
  z.art = "sp";
  z.jahre = [2010, 2020];
  z.tage = new Set(["s"]);
  z.quellen = new Set(["berlin"]);
  z.uebertragen = false;
  z.datenlage = false;
  const hash = kodiere(z, std(), { zoom: 12, lat: 52.52, lon: 13.4 }, "berlin:K10921");
  assert.match(hash, /t=rad\.anteil/);
  const { zustand, karte, stelle } = dekodiere(`#${hash}`, std(), QUELLEN);
  assert.equal(zustand.thema, "rad");
  assert.equal(zustand.modus.rad, "anteil");
  assert.equal(zustand.art, "sp");
  assert.deepEqual(zustand.jahre, [2010, 2020]);
  assert.deepEqual([...zustand.tage], ["s"]);
  assert.deepEqual([...zustand.quellen], ["berlin"]);
  assert.equal(zustand.uebertragen, false);
  assert.equal(zustand.datenlage, false);
  assert.deepEqual(karte, { zoom: 12, lat: 52.52, lon: 13.4 });
  assert.equal(stelle, "berlin:K10921");
});

test("Ungültiges wird ignoriert, Standard bleibt unberührt", () => {
  const s = std();
  const { zustand, karte } = dekodiere("#t=kfz.anteil&a=x&j=2030-1990&q=atlantis&m=99/1/1", s, QUELLEN);
  assert.equal(zustand.thema, "kfz");
  assert.equal(zustand.art, "w");
  assert.deepEqual(zustand.jahre, [1983, 2026]);
  assert.equal(zustand.quellen.size, 0); // q gesetzt, aber unbekannt -> leer (bewusst geteilt)
  assert.equal(karte, null);
  assert.equal(s.quellen.size, 2);
});
