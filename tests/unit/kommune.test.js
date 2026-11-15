// Steckbrief einer Kommune (js/data/kommune.js): Klasse über beide Zählarten, welche Zählungen
// zu einer Kommune gehören, Zeitachse – mit kleinen synthetischen Daten.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  anteil, dauerDerKommune, dauerQuellenJeKommune, dauerStellenDerKommune, klasseVon, kommuneDerDauerstelle,
  kommuneDerStelle, kurzzeitDerKommune, zeitachse,
} from "../../js/data/kommune.js";

const kommune = (ags, name, kurzzeit, dauer) => ({ type: "Feature", geometry: { type: "Point", coordinates: [9, 48] }, properties: { ags, name, kurzzeit, dauer } });
const block = (stand, quellen = []) => ({ stand, quellen });

// Kreis 08119 mit der Gemeinde 08119001 darin; Stadt 08111000 mit eigener Quelle; ein Bündel für beide
const DATENLAGE = {
  features: [
    kommune("08111000", "Stadt", block("in_karte", ["stadt_k"]), block("in_karte", ["stadt_rad", "buendel"])),
    kommune("08119", "Kreis", null, block("in_karte", ["buendel"])),
    kommune("08119001", "Gemeinde im Kreis", block("kandidat"), null),
    kommune("05315000", "Nur Summen", block("aggregiert"), block("aggregiert")),
  ],
};

test("Klasse über beide Zählarten: in der Karte vor offen vor aussichtsreich vor grau", () => {
  assert.equal(klasseVon({ kurzzeit: block("aggregiert"), dauer: block("in_karte", ["x"]) }), "in_karte");
  // ohne Lizenz, aber mit Werten in der Karte: in der Karte
  assert.equal(klasseVon({ kurzzeit: block("ohne_lizenz", ["tuebingen"]), dauer: null }), "in_karte");
  assert.equal(klasseVon({ kurzzeit: block("geliefert"), dauer: block("kandidat") }), "offen");
  assert.equal(klasseVon({ kurzzeit: null, dauer: block("ohne_lizenz") }), "kandidat");
  assert.equal(klasseVon({ kurzzeit: block("nichts_offen"), dauer: block("abgelehnt") }), "sonst");
});

test("Dauer-Quellen je Kommune: eigene (1), Bündel (2), Land/Bund (keine)", () => {
  const n = dauerQuellenJeKommune(DATENLAGE);
  assert.equal(n.get("stadt_rad"), 1);
  assert.equal(n.get("buendel"), 2);
  assert.equal(n.get("land"), undefined);
});

// Kurzzeit: Bits wie GRUPPEN in modell.js (kfz 1, sv 2, rad 4, fuss 8)
const zaehlung = (g, jahr) => ({ g, jahr });
const DATEN = {
  stellen: [
    { quelle: "stadt_k", lon: 9.1, lat: 48.7, zaehlungen: [zaehlung(1 | 2, 2010), zaehlung(1 | 2 | 4, 2012), zaehlung(1, 2012)] },
    { quelle: "stadt_k", lon: 9.3, lat: 48.8, zaehlungen: [zaehlung(4 | 8, 2020)] },
    { quelle: "andere", lon: 7, lat: 50, zaehlungen: [zaehlung(1, 2001)] },
  ],
};

test("Kurzzeitzählungen der Kommune: je Verkehrsart Zählungen, Stellen, Jahre und Umriss", () => {
  const k = kurzzeitDerKommune(DATEN, ["stadt_k"]);
  assert.equal(k.zaehlungen, 4);
  assert.equal(k.stellen, 2);
  assert.deepEqual(k.themen.map((x) => x.thema), ["kfz", "sv", "rad", "fuss"]);
  const [kfz, sv, rad, fuss] = k.themen;
  assert.deepEqual([kfz.zaehlungen, kfz.stellen, kfz.von, kfz.bis], [3, 1, 2010, 2012]);
  assert.deepEqual(kfz.jahre, { 2010: 1, 2012: 2 });
  assert.deepEqual([sv.zaehlungen, rad.zaehlungen, fuss.zaehlungen], [2, 2, 1]);
  assert.deepEqual(rad.umriss, [[9.1, 48.7], [9.3, 48.8]]);
  assert.deepEqual(kurzzeitDerKommune(DATEN, []).themen, []);
});

// Dauer: Stellen mit Quelle, Gemeinde (ags), Zeitraum und Gruppen
const stelle = (index, quelle, ags, gruppen, von = "2020-01-01", bis = "2026-11-01") => ({
  index, id: `${quelle}:${index}`, quelle, ags, gruppen, von, bis, lon: 9 + index / 10, lat: 48,
});
const DAUER = {
  stellen: [
    stelle(0, "stadt_rad", "08111000", ["rad"]),
    stelle(1, "stadt_rad", "08115001", ["rad"], "2024-01-01"), // eigene Quelle, jenseits der Grenze
    stelle(2, "buendel", "08111000", ["rad"], "2015-06-01", "2025-12-31"),
    stelle(3, "buendel", "08119001", ["rad"]), // im Kreis, in der Gemeinde 08119001
    stelle(4, "buendel", "09162000", ["rad"]), // in keiner Kommune der Datenlage
    stelle(5, "land", "08119001", ["kfz", "lkw", "sv"]), // Quelle des Landes, im Kreis
    stelle(6, "land", "08111000", ["kfz", "sv"]),
    stelle(7, "fremd_eigen", "08111000", ["rad"]), // eigene Quelle einer anderen Kommune, liegt hier
  ],
  quellenMeta: [
    { code: "stadt_rad", name: "Stadt (Rad)", zeitraeume: { rad: ["2019-01-01", "2026-11-01"] } },
    { code: "buendel", name: "Bündel (Rad)", zeitraeume: { rad: ["2013-01-01", "2026-11-01"] } },
    { code: "land", name: "Land (Kfz)", zeitraeume: { kfz: ["2016-01-01", "2026-08-31"], lkw: ["2017-01-01", "2025-12-31"], sv: ["2016-01-01", "2026-08-31"] } },
    { code: "fremd_eigen", name: "Fremd", zeitraeume: { rad: ["2020-01-01", "2026-11-01"] } },
  ],
  tageswerte_bis: { rad: [null, null, "2019-12-31", null, null, null, null, null] },
};
const ANZAHL = new Map([...dauerQuellenJeKommune(DATENLAGE), ["fremd_eigen", 1]]);
const p = (ags) => DATENLAGE.features.find((f) => f.properties.ags === ags).properties;

test("Dauerzählstellen der Kommune: eigene Quellen ganz, Bündel und Land nach Lage", () => {
  const ids = (ags) => dauerStellenDerKommune(DAUER, p(ags), ANZAHL).map((s) => s.index);
  assert.deepEqual(ids("08111000"), [0, 1, 2, 6]); // nicht 7: eigene Quelle einer anderen Kommune
  assert.deepEqual(ids("08119"), [3, 5]); // Kreis: Bündel und Land in seinen Gemeinden
  assert.deepEqual(ids("08119001"), [3, 5]);
  assert.deepEqual(ids("05315000"), []);
});

test("Dauerzählstellen je Verkehrsart: Stellen, Zeitraum (je Gruppe beschnitten), Tageswerte, Quellen", () => {
  const d = dauerDerKommune(DAUER, p("08111000"), ANZAHL);
  assert.equal(d.stellen, 4);
  assert.deepEqual(d.themen.map((x) => x.thema), ["kfz", "sv", "rad"]);
  const [kfz, sv, rad] = d.themen;
  assert.deepEqual([kfz.stellen, kfz.von, kfz.bis], [1, "2020-01-01", "2026-08-31"]);
  assert.deepEqual([sv.stellen, sv.quellen], [1, ["land"]]);
  assert.deepEqual([rad.stellen, rad.von, rad.bis, rad.twBis], [3, "2015-06-01", "2026-11-01", "2019-12-31"]);
  assert.deepEqual(rad.quellen.sort(), ["buendel", "stadt_rad"]);
  assert.deepEqual(d.quellen.map((q) => q.code), ["stadt_rad", "buendel", "land"]);
  // Lkw und Schwerverkehr unter einem Thema: die Stelle zählt einmal
  assert.equal(dauerDerKommune(DAUER, p("08119"), ANZAHL).themen.find((x) => x.thema === "sv").stellen, 1);
});

test("Zeitachse über beide Zählarten, mindestens drei Jahre; Lage eines Tages darauf", () => {
  const k = kurzzeitDerKommune(DATEN, ["stadt_k"]);
  const d = dauerDerKommune(DAUER, p("08111000"), ANZAHL);
  assert.deepEqual(zeitachse(k, d), [2010, 2026]);
  assert.deepEqual(zeitachse({ themen: [{ von: 2020, bis: 2020 }] }, null), [2019, 2021]);
  assert.equal(zeitachse(null, null), null);
  assert.equal(anteil("2010-01-01", [2010, 2019]), 0);
  assert.equal(anteil("2020-01-01", [2010, 2019]), 1);
  assert.ok(Math.abs(anteil("2015-01-01", [2010, 2019]) - 0.5) < 0.01);
});

test("Kommune einer Stelle: Kurzzeit über die Quelle, Dauer über eigene Quelle oder Lage (Gemeinde vor Kreis)", () => {
  assert.equal(kommuneDerStelle(DATENLAGE, { quelle: "stadt_k" }).ags, "08111000");
  assert.equal(kommuneDerStelle(DATENLAGE, { quelle: "andere" }), null);
  assert.equal(kommuneDerDauerstelle(DATENLAGE, DAUER.stellen[1], ANZAHL).ags, "08111000"); // eigene Quelle
  assert.equal(kommuneDerDauerstelle(DATENLAGE, DAUER.stellen[3], ANZAHL).ags, "08119001"); // Gemeinde vor Kreis
  assert.equal(kommuneDerDauerstelle(DATENLAGE, DAUER.stellen[4], ANZAHL), null);
  assert.equal(kommuneDerDauerstelle(DATENLAGE, { ...DAUER.stellen[5], ags: null }, ANZAHL), null);
});
