// Browserlos: Familie Dauerzählstellen – Tage, Werte am Tag, Klassen, Kartenpunkte, CSV.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  DAUER_STUFEN, DAUER_THEMEN, amSelbenPunkt, ansichtDauer, ansichtJuengster, csvDauer, csvDauerJuengster, entpackeDauer,
  featuresDauer, gruppeFuer, gruppenName, hatGruppe, hatThema, imJuengsten, klassenDerQuellen, plusTage, quellenOhneTag,
  stundenAm, stundenDesTags, tagAusDetail, tagDerStelle, tagImZeitraum, tageJeQuelle, tageZwischen, tagtyp, tagtypen,
  themaFuerKommune, themaIn, themaVon, wertAm, zaehleDauer,
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
  z.dthema = "sv"; // Lkw/Schwerverkehr: Berlin zeigt seine Klasse Lkw
  const lkw = ansichtDauer(d, z, JAHR, "2025-01-03");
  assert.deepEqual(lkw.map((e) => [e.stelle.id, e.gruppe, e.wert]), [["berlin_viz:TE001", "lkw", 3]]); // TE002 zählt kein Lkw
  assert.equal(DAUER_STUFEN.kfz.length, 4);
});

test("Lkw/Schwerverkehr: ein Thema, je Stelle die Klasse ihres Detektors, nie zusammengezählt", () => {
  assert.deepEqual(DAUER_THEMEN.sv.gruppen, ["lkw", "sv"]);
  assert.equal(DAUER_THEMEN.sv.name, "Lkw/Schwerverkehr");
  assert.equal(gruppenName("lkw"), "Lkw (Detektor)");
  assert.equal(gruppenName("sv"), "Schwerverkehr (Detektor)");
  assert.equal(themaVon("lkw"), "sv"); // alte Links mit t=lkw.menge
  assert.equal(themaVon("kfz"), "kfz");
  const berlin = { gruppen: ["kfz", "lkw"] };
  const hamburg = { gruppen: ["kfz", "sv"] };
  assert.equal(gruppeFuer(berlin, "sv"), "lkw");
  assert.equal(gruppeFuer(hamburg, "sv"), "sv");
  assert.equal(gruppeFuer({ gruppen: ["rad"] }, "sv"), null);
  assert.ok(hatThema(d, "sv") && !hatThema(d, "rad"));
  assert.equal(themaIn(d, "lkw"), "sv");
  // welche Stadt welche Klasse zählt (Ortsname ohne Zusatz in Klammern, jeder Ort einmal)
  const e = entpackeDauer({
    ...INDEX,
    gruppen: ["kfz", "lkw", "sv", "rad"],
    quellen: [
      { code: "berlin_viz", name: "Berlin (Verkehrsdetektion)", land: "BE", gruppen: ["kfz", "lkw"] },
      { code: "hamburg_kfz", name: "Hamburg (Kfz, Wärmebildkameras)", land: "HH", gruppen: ["kfz", "sv"] },
      { code: "hamburg_rad", name: "Hamburg (Rad, Wärmebildkameras)", land: "HH", gruppen: ["rad"] },
      { code: "ettlingen", name: "Ettlingen (automatische Zählstellen)", land: "BW", gruppen: ["kfz", "lkw"] },
    ],
  });
  assert.deepEqual(klassenDerQuellen(e, "sv"), [{ gruppe: "lkw", orte: ["Berlin", "Ettlingen"] }, { gruppe: "sv", orte: ["Hamburg"] }]);
  assert.deepEqual(klassenDerQuellen(e, "kfz"), []);
});

test("Jüngster Schultag je Stelle: Standardansicht ohne gewählten Tag, Tag je Stelle, CSV", () => {
  const index = {
    ...INDEX,
    juengster: { kfz: [["2025-01-03", 30000], ["2025-01-03", 8000]], lkw: [["2025-01-02", 2], null] },
  };
  const e = entpackeDauer(index);
  const z = zustand();
  assert.ok(imJuengsten(e, z));
  assert.ok(!imJuengsten(d, z)); // ohne `juengster` (älterer Vertrag): Standardtag
  assert.ok(!imJuengsten(e, { ...z, tag: "2025-01-02" }));
  const kfz = ansichtJuengster(e, z);
  assert.deepEqual(kfz.map((x) => [x.stelle.id, x.gruppe, x.tag, x.wert, x.stufe]), [
    ["berlin_viz:TE001", "kfz", "2025-01-03", 30000, 4],
    ["berlin_viz:TE002", "kfz", "2025-01-03", 8000, 1],
  ]);
  // Lkw/Schwerverkehr: nur Stellen mit der Klasse; ohne vollständigen Schultag hohl, ohne Tag
  z.dthema = "sv";
  assert.deepEqual(ansichtJuengster(e, z).map((x) => [x.stelle.id, x.tag, x.wert, x.stufe]), [["berlin_viz:TE001", "2025-01-02", 2, 0]]);
  // Tag der Seitenleiste: der jüngste der gezeigten Gruppe, sonst einer anderen, sonst der letzte Tag
  assert.equal(tagDerStelle(e, z, e.stellen[0]), "2025-01-02");
  assert.equal(tagDerStelle(e, { ...z, dthema: "kfz" }, e.stellen[0]), "2025-01-03");
  assert.equal(tagDerStelle(e, z, e.stellen[1]), "2025-01-03"); // TE002 zählt kein Lkw -> Kfz
  assert.equal(tagDerStelle(entpackeDauer({ ...index, juengster: { kfz: [null, null], lkw: [null, null] } }), z, e.stellen[1]), "2025-01-05");
  assert.equal(tagDerStelle(e, { ...z, tag: "2025-01-04" }, e.stellen[0]), "2025-01-04");
  // je Quelle die gezeigten Tage (für den Hinweis in der Legende)
  const gemischt = [{ stelle: e.stellen[0], tag: "2025-01-03", wert: 1 }, { stelle: e.stellen[1], tag: "2024-12-30", wert: 2 },
    { stelle: e.stellen[1], tag: null, wert: null }];
  assert.deepEqual(tageJeQuelle(e, gemischt).map((x) => [x.quelle.code, x.von, x.bis]), [["berlin_viz", "2024-12-30", "2025-01-03"]]);
  // CSV: je Gruppe Tag und Tagessumme, leer statt 0, Lizenz in jeder Zeile
  const zeilen = csvDauerJuengster(e, () => "dl-de/by-2-0").replace(/^﻿/, "").trim().split("\n");
  assert.equal(zeilen[0], "quelle;stelle;name;abschnitt;richtung;lon;lat;kfz_juengster_schultag;kfz_tagessumme;lkw_juengster_schultag;lkw_tagessumme;lizenz");
  assert.match(zeilen[1], /^berlin_viz;berlin_viz:TE001;Clayallee;in Höhe 343;Richtung Süd;13\.26;52\.43;2025-01-03;30000;2025-01-02;2;dl-de\/by-2-0$/);
  assert.match(zeilen[2], /;2025-01-03;8000;;;dl-de\/by-2-0$/);
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
      { code: "hamburg_kfz", name: "Hamburg Kfz", land: "HH", gruppen: ["kfz", "sv"], von: "2025-01-02", bis: "2025-01-10", standardtag: "2025-01-09",
        zeitraeume: { kfz: ["2025-01-06", "2025-01-10"], sv: ["2025-01-02", "2025-01-10"] } },
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
  assert.equal(themaIn(e, "fuss"), "kfz"); // gibt es hier nicht -> Thema der ersten Gruppe
  assert.equal(themaIn(e, "rad"), "rad");
  assert.equal(themaIn(e, "lkw"), "sv"); // Lkw gibt es hier nicht, aber Schwerverkehr im selben Thema
  // am 8.1.: Berlin zählt Kfz, hat aber keine Werte mehr; beim Rad fehlt nichts
  assert.deepEqual(quellenOhneTag(e, "kfz", "2025-01-08").map((o) => o.quelle.code), ["berlin_viz"]);
  assert.deepEqual(quellenOhneTag(e, "kfz", "2025-01-08")[0].sprung, "2025-01-02");
  assert.deepEqual(quellenOhneTag(e, "rad", "2025-01-08"), []);
  assert.deepEqual(quellenOhneTag(e, "sv", "2024-12-31").map((o) => o.quelle.code), ["hamburg_kfz"]);
  // Tagtyp: gleich in allen Ländern -> einer; verschieden -> je Land; nur Länder mit Werten am Tag
  assert.deepEqual(tagtypen(e, "2025-01-01"), [{ land: null, typ: "h" }]);
  assert.deepEqual(tagtypen(e, "2025-01-03"), [{ land: "BE", typ: "f" }, { land: "HH", typ: "s" }]);
  assert.deepEqual(tagtypen(e, "2025-01-08"), [{ land: null, typ: "s" }]); // nur Hamburg
  const csv = csvDauer(e, { werte: { kfz: [null, null, null], sv: [null, null, null], rad: [null, null, null] } },
    "2025-01-03", () => "dl-de/by-2-0");
  assert.match(csv.split("\n")[0], /;tagtyp;kfz_tagessumme;sv_tagessumme;rad_tagessumme;lizenz$/);
});

test("Zeitraum: über Jahre als Jahre, sonst als Tage", async () => {
  const { zeitraumText } = await import("../../js/data/dauer.js");
  assert.equal(zeitraumText("2015-01-01", "2025-06-30"), "2015–2025");
  assert.equal(zeitraumText("2026-08-29", "2026-11-05"), "29.08.2026 – 05.11.2026");
});

test("Spanne gezeigter Tage: kurz, im selben Jahr ohne doppeltes Jahr, über Jahre als Jahre", async () => {
  const { tageSpanne } = await import("../../js/data/dauer.js");
  const { setzeSprache } = await import("../../js/sprache/texte.js");
  assert.equal(tageSpanne("2026-11-05", "2026-11-05"), "05.11.2026");
  assert.equal(tageSpanne("2026-09-11", "2026-11-05"), "11.09.–05.11.2026");
  assert.equal(tageSpanne("2025-12-30", "2026-01-05"), "30.12.2025–05.01.2026");
  assert.equal(tageSpanne("2020-12-03", "2025-06-30"), "2020–2025");
  setzeSprache("en");
  try {
    assert.equal(tageSpanne("2026-09-11", "2026-11-05"), "11 Sep – 5 Nov 2026");
  } finally {
    setzeSprache("de");
  }
});

test("Zeitraum je Gruppe: vor dem Kfz-Beginn fehlt die Stelle beim Kfz, beim Schwerverkehr nicht", () => {
  const index = {
    ...INDEX,
    gruppen: ["kfz", "sv"],
    bis: "2025-01-10",
    kalender: { HH: "sshssswwssss" },
    quellen: [{ code: "hamburg_kfz", name: "Hamburg Kfz", land: "HH", gruppen: ["kfz", "sv"], von: "2024-12-30", bis: "2025-01-10",
      standardtag: "2025-01-02", zeitraeume: { kfz: ["2025-01-06", "2025-01-10"], sv: ["2024-12-30", "2025-01-10"] } }],
    stellen: {
      felder: INDEX.stellen.felder,
      werte: [["hamburg_kfz:0248931", "hamburg_kfz", "Bramfelder Straße", null, null, 10.05, 53.6, "2024-12-30", "2025-01-10", 3, 0]],
    },
  };
  const e = entpackeDauer(index);
  const jahr = { werte: { kfz: [[null, null, null, null, null, 9000]], sv: [[300, 310, 320, 330, 340, 350]] } };
  const z = { ...zustand(), dthema: "kfz" };
  assert.deepEqual(ansichtDauer(e, z, jahr, "2025-01-03"), []); // kein Kfz vor dem 6.1. – nicht „nicht vollständig“
  assert.equal(ansichtDauer(e, z, jahr, "2025-01-06")[0].wert, 9000);
  z.dthema = "sv";
  assert.equal(ansichtDauer(e, z, jahr, "2025-01-03")[0].wert, 320);
  // Hinweis: Kfz am 3.1. ohne Werte, Sprung ans Ende des Kfz-Zeitraums (Standardtag liegt davor)
  const [o] = quellenOhneTag(e, "kfz", "2025-01-03");
  assert.deepEqual([o.von, o.bis, o.sprung], ["2025-01-06", "2025-01-10", "2025-01-10"]);
});

test("amSelbenPunkt: Stellen derselben Quelle mit gleicher Lage (Richtungen eines Sensors)", () => {
  const felder = INDEX.stellen.felder;
  const zeile = (id, quelle, richtung, lon, lat) => [id, quelle, "Rastatter Straße", null, richtung, lon, lat, "2025-01-01", "2025-01-05", 1, 0];
  const e = entpackeDauer({
    ...INDEX,
    quellen: [...INDEX.quellen, { code: "ettlingen", name: "Ettlingen", land: "BW", lizenzen: [{ lizenz: "CC BY-NC 4.0" }] }],
    stellen: {
      felder,
      werte: [
        ...INDEX.stellen.werte,
        zeile("ettlingen:1263-1", "ettlingen", "Richtung Schloßgartenstraße", 8.403476, 48.940203),
        zeile("ettlingen:1263-2", "ettlingen", "Richtung Bruchhausen", 8.403476, 48.940203),
        zeile("ettlingen:395842-1", "ettlingen", "Karlsruhe Richtung Ettlingen", 8.406437, 48.956261),
        zeile("berlin_viz:X", "berlin_viz", "gleiche Lage, andere Quelle", 8.403476, 48.940203),
      ],
    },
  });
  const ids = (s) => amSelbenPunkt(e, e.jeId.get(s)).map((x) => x.id);
  assert.deepEqual(ids("ettlingen:1263-2"), ["ettlingen:1263-1", "ettlingen:1263-2"]);
  assert.deepEqual(ids("ettlingen:395842-1"), ["ettlingen:395842-1"]);
  assert.deepEqual(ids("berlin_viz:TE001"), ["berlin_viz:TE001"]);
});

test("Verkehrsart für eine Kommune: was sie zählt, ohne eigene Quelle die nächste Stelle", () => {
  const e = entpackeDauer({
    ...INDEX,
    gruppen: ["kfz", "lkw", "rad"],
    quellen: [
      { code: "ettlingen", name: "Ettlingen (automatische Zählstellen)", land: "BW", gruppen: ["kfz", "lkw"] },
      { code: "leipzig_rad", name: "Leipzig (Rad-Zählstellen)", land: "SN", gruppen: ["rad"] },
      { code: "mobidata_rad", name: "Baden-Württemberg (Rad-Zählstellen, MobiData BW)", land: "BW", gruppen: ["rad"] },
    ],
    stellen: {
      felder: INDEX.stellen.felder,
      werte: [
        ["ettlingen:1", "ettlingen", "Karlsruher Straße", null, null, 8.4, 48.94, "2025-01-01", "2025-01-05", 3, 0],
        ["leipzig_rad:1", "leipzig_rad", "Manetstraße", null, null, 12.37, 51.34, "2025-01-01", "2025-01-05", 4, 0],
        ["mobidata_rad:1", "mobidata_rad", "Erbprinzenstraße", null, null, 8.4, 49.01, "2025-01-01", "2025-01-05", 4, 0],
      ],
    },
  });
  assert.equal(themaFuerKommune(e, "Leipzig", 12.373, 51.34, "kfz"), "rad"); // zählt nur Rad
  assert.equal(themaFuerKommune(e, "Leipzig", 12.373, 51.34, "rad"), "rad");
  assert.equal(themaFuerKommune(e, "Ettlingen", 8.408, 48.941, "rad"), "kfz"); // Rad aus Karlsruhe zählt nicht
  assert.equal(themaFuerKommune(e, "Ettlingen", 8.408, 48.941, "sv"), "sv"); // Lkw: im Thema Lkw/Schwerverkehr
  assert.equal(themaFuerKommune(e, "Karlsruhe", 8.404, 49.009, "kfz"), "rad"); // nächste Stelle: MobiData
  assert.equal(themaFuerKommune(e, "Kiel", 10.13, 54.32, "kfz"), "kfz"); // nichts im Umkreis: bleibt
});
