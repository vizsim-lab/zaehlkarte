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

test("Dauerzählstellen: f, t und z hin und zurück; Kurzzeit-Links bleiben gleich", () => {
  const z = std();
  z.familie = "d";
  z.dthema = "sv";
  z.tag = "2025-05-19";
  const hash = kodiere(z, std(), null, "berlin_viz:TE001");
  assert.equal(hash, "f=d&t=sv.menge&z=2025-05-19&s=berlin_viz:TE001");
  const { zustand, stelle } = dekodiere(`#${hash}`, std(), QUELLEN);
  assert.equal(zustand.familie, "d");
  assert.equal(zustand.dthema, "sv");
  assert.equal(zustand.tag, "2025-05-19");
  // alte Links: t=lkw.menge (bis November 2026 ein eigener Chip) gilt als Lkw/Schwerverkehr
  assert.equal(dekodiere("#f=d&t=lkw.menge", std(), QUELLEN).zustand.dthema, "sv");
  // ohne z: kein Tag gewählt – die Karte zeigt je Stelle ihren jüngsten Schultag
  assert.equal(dekodiere("#f=d", std(), QUELLEN).zustand.tag, null);
  assert.equal(kodiere({ ...z, tag: null }, std(), null, null), "f=d&t=sv.menge");
  assert.equal(zustand.thema, "kfz"); // die Verkehrsart der Kurzzeitzählungen bleibt
  assert.equal(stelle, "berlin_viz:TE001");
  // t=lkw.menge ohne f=d gilt nicht (kein Thema der Kurzzeitzählungen), z ohne f=d auch nicht
  const alt = dekodiere("#t=lkw.menge&z=2025-05-19", std(), QUELLEN).zustand;
  assert.equal(alt.familie, "k");
  assert.equal(alt.thema, "kfz");
  assert.equal(alt.tag, null);
  // bei f=d gelten nur die Verkehrsarten der Dauerzählstellen (Rad, Schwerverkehr laut Detektor …)
  assert.equal(dekodiere("#f=d&t=rad.menge", std(), QUELLEN).zustand.dthema, "rad");
  assert.equal(dekodiere("#f=d&t=sv.menge", std(), QUELLEN).zustand.dthema, "sv");
  assert.equal(dekodiere("#f=d&t=kind.menge&z=gestern", std(), QUELLEN).zustand.dthema, "kfz");
  assert.equal(dekodiere("#f=d&z=gestern", std(), QUELLEN).zustand.tag, null);
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
