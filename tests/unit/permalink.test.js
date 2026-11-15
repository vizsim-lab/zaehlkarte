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
  z.uebertragen = false;
  z.datenlage = false;
  const hash = kodiere(z, std(), { zoom: 12, lat: 52.52, lon: 13.4 }, "berlin:K10921");
  assert.match(hash, /t=rad\.anteil/);
  const { zustand, karte, stelle } = dekodiere(`#${hash}`, std());
  assert.equal(zustand.thema, "rad");
  assert.equal(zustand.modus.rad, "anteil");
  assert.equal(zustand.art, "sp");
  assert.deepEqual(zustand.jahre, [2010, 2020]);
  assert.deepEqual([...zustand.tage], ["s"]);
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
  const { zustand, stelle } = dekodiere(`#${hash}`, std());
  assert.equal(zustand.familie, "d");
  assert.equal(zustand.dthema, "sv");
  assert.equal(zustand.tag, "2025-05-19");
  // alte Links: t=lkw.menge (bis November 2026 ein eigener Chip) gilt als Lkw/Schwerverkehr
  assert.equal(dekodiere("#f=d&t=lkw.menge", std()).zustand.dthema, "sv");
  // ohne z: kein Tag gewählt – die Karte zeigt je Stelle ihren jüngsten Schultag
  assert.equal(dekodiere("#f=d", std()).zustand.tag, null);
  assert.equal(kodiere({ ...z, tag: null }, std(), null, null), "f=d&t=sv.menge");
  assert.equal(zustand.thema, "kfz"); // die Verkehrsart der Kurzzeitzählungen bleibt
  assert.equal(stelle, "berlin_viz:TE001");
  // t=lkw.menge ohne f=d gilt nicht (kein Thema der Kurzzeitzählungen), z ohne f=d auch nicht
  const alt = dekodiere("#t=lkw.menge&z=2025-05-19", std()).zustand;
  assert.equal(alt.familie, "k");
  assert.equal(alt.thema, "kfz");
  assert.equal(alt.tag, null);
  // bei f=d gelten nur die Verkehrsarten der Dauerzählstellen (Rad, Schwerverkehr laut Detektor …)
  assert.equal(dekodiere("#f=d&t=rad.menge", std()).zustand.dthema, "rad");
  assert.equal(dekodiere("#f=d&t=sv.menge", std()).zustand.dthema, "sv");
  assert.equal(dekodiere("#f=d&t=kind.menge&z=gestern", std()).zustand.dthema, "kfz");
  assert.equal(dekodiere("#f=d&z=gestern", std()).zustand.tag, null);
});

test("Ungültiges wird ignoriert, Standard bleibt unberührt", () => {
  const s = std();
  const { zustand, karte, kommune } = dekodiere("#t=kfz.anteil&a=x&j=2030-1990&m=99/1/1&k=Berlin", s);
  assert.equal(zustand.thema, "kfz");
  assert.equal(zustand.art, "w");
  assert.deepEqual(zustand.jahre, [1983, 2026]);
  assert.equal(karte, null);
  assert.equal(kommune, null);
});

test("q (Auswahl der Quellen bis November 2026) gilt nicht mehr: alle Quellen, kein q im Link", () => {
  const { zustand } = dekodiere("#t=rad.menge&q=ravensburg", std());
  assert.deepEqual([...zustand.quellen], QUELLEN);
  assert.equal(zustand.thema, "rad");
  assert.equal(kodiere(zustand, std(), null, null), "t=rad.menge");
});

test("k: Steckbrief einer Kommune (Gemeinde- oder Kreisschlüssel); eine Stelle geht vor", () => {
  assert.equal(kodiere(std(), std(), null, null, "05515000"), "k=05515000");
  assert.equal(kodiere(std(), std(), null, "berlin:K1", "05515000"), "s=berlin:K1");
  assert.equal(dekodiere("#k=05515000", std()).kommune, "05515000");
  assert.equal(dekodiere("#k=08119", std()).kommune, "08119");
  assert.equal(dekodiere("#k=0551", std()).kommune, null);
});

test("Kennzahl 6–22 Uhr (a=w16) hin und zurück", () => {
  const z = std();
  z.art = "w16";
  const hash = kodiere(z, std(), null, null);
  assert.equal(hash, "a=w16");
  assert.equal(dekodiere(`#${hash}`, std(), QUELLEN).zustand.art, "w16");
});
