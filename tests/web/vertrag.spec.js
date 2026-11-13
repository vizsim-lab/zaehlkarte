// Vertrag Pipeline <-> Frontend: Felder in index.json und manifest.json, die js/ lesen.
import { expect, test } from "@playwright/test";

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
test("dauer/index.json, Jahres- und Detaildateien haben die erwarteten Felder", async ({ request }) => {
  const r = await request.get("/data/dauer/index.json");
  test.skip(!r.ok(), "keine Dauerzählstellen im Build (Release-Asset fehlt)");
  const d = await r.json();
  expect(d.version).toBe(1);
  expect(d.stellen.felder).toEqual(["id", "quelle", "name", "abschnitt", "richtung", "lon", "lat", "von", "bis", "g", "chunk"]);
  expect(Object.keys(d.dateien)).toEqual(["tage", "details"]);
  expect(d.gruppen).toEqual(["kfz", "lkw"]);
  expect(d.standardtag >= d.von && d.standardtag <= d.bis).toBe(true);
  for (const q of d.quellen) {
    expect(q.lizenzen.length).toBeGreaterThan(0);
    expect(d.kalender[q.land].length).toBe(Math.round((Date.parse(d.bis) - Date.parse(d.von)) / 86_400_000) + 1);
  }
  const jahr = await (await request.get(`/data/${d.dateien.tage.replace("{jahr}", d.bis.slice(0, 4))}`)).json();
  expect(jahr.werte.kfz.length).toBe(d.stellen.werte.length);
  const zeile = jahr.werte.kfz.find((x) => x);
  expect(zeile.length).toBe(jahr.tage);
  expect(zeile.every((v) => v == null || v > 0)).toBe(true); // nie 0 für „nicht vollständig“
  const [id, , , , , , , von, , , chunk] = d.stellen.werte[0];
  const details = await (await request.get(`/data/${d.dateien.details.replace("{n}", chunk)}`)).json();
  const s = details.stellen[id];
  expect(s.von).toBe(von);
  expect(s.tage.kfz.length).toBe(s.n.length);
  expect(s.stunden.kfz.every((t) => t === null || t.length === 24)).toBe(true);
  for (let n = 0; n < d.details_anzahl; n += 1) {
    expect((await request.get(`/data/${d.dateien.details.replace("{n}", n)}`)).ok()).toBe(true);
  }
});
