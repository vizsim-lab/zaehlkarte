// Browserlos: Familie Dauerzählstellen – Tage, Werte am Tag, Klassen, Kartenpunkte, CSV.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DAUER_STUFEN, DAUER_THEMEN, ansichtDauer, csvDauer, entpackeDauer, featuresDauer, hatGruppe, plusTage,
  quellenOhneTag, stundenAm, stundenDesTags, tagAusDetail, tagImZeitraum, tageZwischen, tagtyp, tagtypen,
  themaIn, wertAm, zaehleDauer,
} from "../../js/data/dauer.js";
import { standardZustand } from "../../js/data/modell.js";

const INDEX = {
  version: 1,
  gruppen: ["kfz", "lkw"],
  dateien: { tage: "dauer/tage/{jahr}.json", details: "dauer/{n}.json" },
  von: "2024-12-30",
  bis: "2025-01-05",
  standardtag: "2025-01-03",
  kalender: { BE: "sshfffw" }, // 30.12. … 5.1. (nur zum Testen)
  quellen: [{ code: "berlin_viz", name: "Berlin", land: "BE", lizenzen: [{ lizenz: "dl-de/by-2-0" }] }],
  stellen: {
    felder: ["id", "quelle", "name", "abschnitt", "richtung", "lon", "lat", "von", "bis", "g", "chunk"],
    werte: [
      ["berlin_viz:TE001", "berlin_viz", "Clayallee", "in Höhe 343", "Richtung Süd", 13.26, 52.43, "2024-12-30", "2025-01-05", 3, 0],
      ["berlin_viz:TE002", "berlin_viz", "A115; „Brücke“", null, null, 13.19, 52.43, "2025-01-02", "2025-01-05", 1, 0],
    ],
  },
};
const JAHR = { jahr: 2025, tage: 365, werte: { kfz: [[100, 200, 30000, null, 5], [null, 7000, 8000, 9000, 10]], lkw: [[1, 2, 3, 4, 5], null] } };
const d = entpackeDauer(INDEX);
const zustand = () => ({ ...standardZustand([2000, 2025], []), familie: "d" });

test("Tage: Abstand, Schritt, Zeitraum und Standardtag", () => {
  assert.equal(tageZwischen("2024-12-30", "2025-01-02"), 3);
  assert.equal(plusTage("2025-02-28", 1), "2025-03-01");
  assert.equal(plusTage("2024-02-28", 1), "2024-02-29");
  assert.equal(tagImZeitraum(d, null), "2025-01-03");
  assert.equal(tagImZeitraum(d, "2025-02-30"), "2025-01-03"); // kein gültiges Datum
  assert.equal(tagImZeitraum(d, "2020-01-01"), "2024-12-30");
  assert.equal(tagImZeitraum(d, "2030-01-01"), "2025-01-05");
  assert.equal(tagtyp(d, "BE", "2025-01-01"), "h");
  assert.equal(tagtyp(d, "HH", "2025-01-01"), "u");
  assert.equal(stundenDesTags("2025-03-30"), 23);
  assert.equal(stundenDesTags("2025-03-31"), 24);
  assert.equal(stundenDesTags("2024-03-31"), 23);
});

test("Werte am Tag: null heißt nicht vollständig, Stellen außerhalb ihres Zeitraums fehlen", () => {
  assert.equal(wertAm(JAHR, d.stellen[0], "kfz", "2025-01-03"), 30000);
  assert.equal(wertAm(JAHR, d.stellen[0], "kfz", "2025-01-04"), null);
  assert.equal(wertAm(JAHR, d.stellen[1], "lkw", "2025-01-03"), null); // keine Reihe
  const z = zustand();
  const am1 = ansichtDauer(d, z, JAHR, "2025-01-01");
  assert.deepEqual(am1.map((e) => e.stelle.id), ["berlin_viz:TE001"]); // TE002 erst ab 2.1.
  const am3 = ansichtDauer(d, z, JAHR, "2025-01-03");
  assert.deepEqual(am3.map((e) => [e.wert, e.stufe]), [[30000, 4], [8000, 1]]);
  const am4 = ansichtDauer(d, z, JAHR, "2025-01-04");
  assert.equal(am4[0].stufe, -1);
  assert.deepEqual(zaehleDauer(am4), { stellen: 2, vollstaendig: 1, klassen: { "-1": 1, 1: 1 } });
  z.dthema = "lkw";
  assert.deepEqual(ansichtDauer(d, z, JAHR, "2025-01-03").map((e) => e.stelle.id), ["berlin_viz:TE001"]); // TE002 zählt kein Lkw
  assert.equal(DAUER_STUFEN.kfz.length, 4);
});

test("featuresDauer: hohl ohne vollständigen Tag, sonst Farbe und Größe der Stufe", () => {
  const fc = featuresDauer(ansichtDauer(d, zustand(), JAHR, "2025-01-04"));
  const [a, b] = fc.features.map((f) => f.properties);
  assert.equal(a.o, 0);
  assert.match(a.c, /^rgba/);
  assert.equal(b.o, 2);
  assert.ok(b.r > a.r);
});

test("csvDauer: deutsche Spalten, leer statt 0, Lizenz", () => {
  const text = csvDauer(d, JAHR, "2025-01-04", () => "dl-de/by-2-0");
  assert.ok(text.startsWith("\ufeff")); // BOM für Excel
  const zeilen = text.trim().split("\n");
  assert.equal(zeilen[0], "quelle;stelle;name;abschnitt;richtung;lon;lat;datum;tagtyp;kfz_tagessumme;lkw_tagessumme;lizenz");
  assert.equal(zeilen.length, 3);
  assert.match(zeilen[1], /;2025-01-04;Ferien;;4;dl-de\/by-2-0$/);
  assert.match(zeilen[2], /"A115; „Brücke“"/); // Semikolon im Namen -> in Anführungszeichen
});

test("Details: Tagessumme, gezählte Stunden und Stundenwerte am Tag", () => {
  const detail = {
    von: "2025-01-01", tage: { kfz: [10, null, 30] }, n: { kfz: [24, 20, 24] },
    stunden_von: "2025-01-02", stunden: { kfz: [Array(24).fill(1), null] },
  };
  assert.deepEqual(tagAusDetail(detail, "kfz", "2025-01-02"), { wert: null, stunden: 20 });
  assert.deepEqual(tagAusDetail(detail, "kfz", "2024-12-31"), { wert: null, stunden: 0 });
  assert.equal(stundenAm(detail, "kfz", "2025-01-01"), null); // vor stunden_von
  assert.equal(stundenAm(detail, "kfz", "2025-01-02").length, 24);
  assert.equal(stundenAm(detail, "kfz", "2025-01-03"), null);
  assert.equal(stundenAm(detail, "lkw", "2025-01-02"), null);
});

test("Gruppen aus den Daten: Bits je Stelle, Thema, Quellen ohne Werte am Tag, Tagtyp je Land", () => {
  const index = {
    ...INDEX,
    gruppen: ["kfz", "sv", "rad"],
    bis: "2025-01-10",
    kalender: { BE: "sshfffwwssss", HH: "sshssswwssss" },
    quellen: [
      { code: "berlin_viz", name: "Berlin", land: "BE", gruppen: ["kfz"], von: "2024-12-30", bis: "2025-01-05", standardtag: "2025-01-02" },
      { code: "hamburg_kfz", name: "Hamburg Kfz", land: "HH", gruppen: ["kfz", "sv"], von: "2025-01-02", bis: "2025-01-10", standardtag: "2025-01-09" },
      { code: "hamburg_rad", name: "Hamburg Rad", land: "HH", gruppen: ["rad"], von: "2025-01-02", bis: "2025-01-10", standardtag: "2025-01-09" },
    ],
    stellen: {
      felder: INDEX.stellen.felder,
      werte: [
        ["berlin_viz:TE001", "berlin_viz", "Clayallee", null, null, 13.26, 52.43, "2024-12-30", "2025-01-05", 1, 0],
        ["hamburg_kfz:0248931", "hamburg_kfz", "Bramfelder Straße", null, null, 10.05, 53.6, "2025-01-02", "2025-01-10", 3, 0],
        ["hamburg_rad:7433952", "hamburg_rad", "Alsterufer", null, null, 10.0, 53.56, "2025-01-02", "2025-01-10", 4, 0],
      ],
    },
  };
  const e = entpackeDauer(index);
  assert.deepEqual(e.stellen.map((s) => s.gruppen), [["kfz"], ["kfz", "sv"], ["rad"]]);
  assert.ok(hatGruppe(e.stellen[1], "sv") && !hatGruppe(e.stellen[0], "sv"));
  assert.equal(themaIn(e, "lkw"), "kfz"); // gibt es hier nicht -> erste Gruppe
  assert.equal(themaIn(e, "rad"), "rad");
  assert.equal(DAUER_THEMEN.sv.name, "Schwerverkehr (Detektor)");
  // am 8.1.: Berlin zählt Kfz, hat aber keine Werte mehr; beim Rad fehlt nichts
  assert.deepEqual(quellenOhneTag(e, "kfz", "2025-01-08").map((q) => q.code), ["berlin_viz"]);
  assert.deepEqual(quellenOhneTag(e, "rad", "2025-01-08"), []);
  assert.deepEqual(quellenOhneTag(e, "sv", "2024-12-31").map((q) => q.code), ["hamburg_kfz"]);
  // Tagtyp: gleich in allen Ländern -> einer; verschieden -> je Land; nur Länder mit Werten am Tag
  assert.deepEqual(tagtypen(e, "2025-01-01"), [{ land: null, typ: "h" }]);
  assert.deepEqual(tagtypen(e, "2025-01-03"), [{ land: "BE", typ: "f" }, { land: "HH", typ: "s" }]);
  assert.deepEqual(tagtypen(e, "2025-01-08"), [{ land: null, typ: "s" }]); // nur Hamburg
  const csv = csvDauer(e, { werte: { kfz: [null, null, null], sv: [null, null, null], rad: [null, null, null] } },
    "2025-01-03", () => "dl-de/by-2-0");
  assert.match(csv.split("\n")[0], /;tagtyp;kfz_tagessumme;sv_tagessumme;rad_tagessumme;lizenz$/);
});
