// Vertrag Pipeline <-> Frontend: Felder in index.json und manifest.json, die js/ lesen.
import { expect, test } from "@playwright/test";
import { DAUER_VERSION } from "../../js/data/dauer.js";

test("index.json und manifest.json haben die erwarteten Felder", async ({ request }) => {
  const manifest = await (await request.get("/data/manifest.json")).json();
  expect(manifest.version).toBe(1);
  expect(Object.keys(manifest.dateien)).toEqual(["index", "details", "datenlage"]);
  const index = await (await request.get(`/data/${manifest.dateien.index}`)).json();
  expect(index.stellen.felder).toEqual(["id", "quelle", "name", "typ", "lon", "lat", "lage", "chunk"]);
  expect(index.zaehlungen.felder).toEqual(["stelle", "datum", "tag", "fenster", "g", "w", "w24", "sp", "l"]);
  expect(index.gruppen).toEqual(["kfz", "sv", "rad", "fuss", "kind"]);
  expect(index.quellen).toEqual(manifest.quellen.map((q) => q.code));
  const chunk = index.stellen.werte[0][7];
  const details = await (await request.get(`/data/${manifest.dateien.details.replace("{n}", chunk)}`)).json();
  expect(Object.keys(details.zaehlungen).length).toBeGreaterThan(0);
  for (let n = 0; n < manifest.details_anzahl; n += 1) {
    expect((await request.get(`/data/details/${n}.json`)).ok()).toBe(true);
  }
  // Spitzenstunden ohne Stundenreihe (Potsdam): von/bis in Minuten, Werte je Gruppe
  const potsdam = index.quellen.indexOf("potsdam");
  const stelle = index.stellen.werte.find((s) => s[1] === potsdam);
  if (stelle) {
    const d = await (await request.get(`/data/${manifest.dateien.details.replace("{n}", stelle[7])}`)).json();
    const mitSpitzen = Object.values(d.zaehlungen).find((z) => z.spitzen);
    expect(mitSpitzen.stunden).toBeUndefined();
    for (const s of mitSpitzen.spitzen) {
      expect(typeof s.von).toBe("number");
      expect(s.bis - s.von).toBe(60);
      expect(Object.keys(s.werte).length).toBeGreaterThan(0);
      expect(index.gruppen).toContain(s.nach);
    }
  }
  expect(manifest.kriterien).toBeUndefined();
  for (const q of manifest.quellen) expect(q.lizenzen.length).toBeGreaterThan(0);
});

// Dauerzählstellen (eigener Bau, Release-Asset): Vertrag prüfen, wenn sie im Build liegen.
// Ändert ein Branch den Vertrag (VERSION in dauer/site.py, DAUER_VERSION in js/data/dauer.js), hat
// das Release-Asset bis nach dem Merge noch den alten: im PR und lokal wird der Test dann
// übersprungen; auf main hält er die Auslieferung an, bis „Dauerzählstellen bauen“ das Asset neu
// gebaut und die CI neu gestartet hat (der Workflow läuft nach jedem Push auf src/zaehlkarte/dauer/).
test("dauer/index.json, Jahres- und Detaildateien haben die erwarteten Felder", async ({ request }) => {
  const r = await request.get("/data/dauer/index.json");
  test.skip(!r.ok(), "keine Dauerzählstellen im Build (Release-Asset fehlt)");
  const d = await r.json();
  const vorMerge = process.env.GITHUB_EVENT_NAME === "pull_request" || !process.env.CI;
  test.skip(vorMerge && d.version < DAUER_VERSION,
    `Release-Asset mit Vertrag ${d.version}, dieser Stand erwartet ${DAUER_VERSION} – nach dem Merge baut „Dauerzählstellen bauen“ es neu`);
  expect(d.version, "Vertrag des Release-Assets (neu bauen: Workflow „Dauerzählstellen bauen“)").toBe(DAUER_VERSION);
  expect(d.stellen.felder).toEqual(["id", "quelle", "name", "abschnitt", "richtung", "lon", "lat", "von", "bis", "g", "chunk"]);
  expect(Object.keys(d.dateien)).toEqual(["tage", "details"]);
  const bekannt = ["kfz", "lkw", "sv", "rad", "fuss"];
  expect(d.gruppen.length).toBeGreaterThan(0);
  expect(d.gruppen.every((g) => bekannt.includes(g))).toBe(true);
  expect(d.standardtag >= d.von && d.standardtag <= d.bis).toBe(true);
  for (const q of d.quellen) {
    expect(q.lizenzen.length).toBeGreaterThan(0);
    expect(d.kalender[q.land].length).toBe(Math.round((Date.parse(d.bis) - Date.parse(d.von)) / 86_400_000) + 1);
    expect(q.gruppen.length).toBeGreaterThan(0);
    expect(q.gruppen.every((g) => d.gruppen.includes(g))).toBe(true);
    expect(q.standardtag >= q.von && q.standardtag <= q.bis).toBe(true);
    for (const [g, [von, bis]] of Object.entries(q.zeitraeume)) {
      expect(q.gruppen).toContain(g);
      expect(von >= q.von && von <= bis && bis <= q.bis).toBe(true);
    }
  }
  const jahr = await (await request.get(`/data/${d.dateien.tage.replace("{jahr}", d.bis.slice(0, 4))}`)).json();
  expect(Object.keys(jahr.werte).sort()).toEqual([...d.gruppen].sort());
  for (const g of d.gruppen) expect(jahr.werte[g].length).toBe(d.stellen.werte.length);
  const zeile = d.gruppen.map((g) => jahr.werte[g].find((x) => x)).find((x) => x);
  expect(zeile.length).toBe(jahr.tage);
  expect(zeile.every((v) => v == null || v > 0)).toBe(true); // nie 0 für „nicht vollständig“

  // jüngster vollständig gezählter Schultag je Gruppe und Stelle: [Tag, Tagessumme] oder null –
  // im Zeitraum der Stelle, ein Schultag im Land ihrer Quelle, die Gruppe im Bit der Stelle
  expect(Object.keys(d.juengster).sort()).toEqual([...d.gruppen].sort());
  const felder = d.stellen.felder;
  const land = Object.fromEntries(d.quellen.map((q) => [q.code, q.land]));
  const tagIndex = (iso) => Math.round((Date.parse(iso) - Date.parse(d.von)) / 86_400_000);
  const falsch = [];
  let gefunden = null;
  d.gruppen.forEach((g, b) => {
    expect(d.juengster[g].length).toBe(d.stellen.werte.length);
    d.juengster[g].forEach((x, i) => {
      if (x === null) return;
      const s = Object.fromEntries(felder.map((k, j) => [k, d.stellen.werte[i][j]]));
      const [tag, wert] = x;
      const ok = Number.isInteger(wert) && wert >= 0 && tag >= s.von && tag <= s.bis && (s.g & (1 << b)) !== 0
        && d.kalender[land[s.quelle]][tagIndex(tag)] === "s";
      if (!ok) falsch.push(`${g} ${s.id}: ${JSON.stringify(x)}`);
      if (!gefunden && tag.slice(0, 4) === d.bis.slice(0, 4)) gefunden = { g, i, tag, wert };
    });
  });
  expect(falsch.slice(0, 5)).toEqual([]);
  // dieselbe Tagessumme wie in der Jahresdatei
  if (gefunden) {
    const { g, i, tag, wert } = gefunden;
    expect(jahr.werte[g][i][Math.round((Date.parse(tag) - Date.parse(`${tag.slice(0, 4)}-01-01`)) / 86_400_000)]).toBe(wert);
  }
  const [id, , , , , , , von, , maske, chunk] = d.stellen.werte[0];
  const gruppe = d.gruppen.find((_, i) => (maske & (1 << i)) !== 0);
  const details = await (await request.get(`/data/${d.dateien.details.replace("{n}", chunk)}`)).json();
  const s = details.stellen[id];
  expect(s.von).toBe(von);
  expect(s.tage[gruppe].length).toBe(s.n[gruppe].length); // gezählte Stunden je Gruppe und Tag
  expect(s.stunden[gruppe].every((t) => t === null || t.length === 24)).toBe(true);
  for (let n = 0; n < d.details_anzahl; n += 1) {
    expect((await request.get(`/data/${d.dateien.details.replace("{n}", n)}`)).ok()).toBe(true);
  }
});
