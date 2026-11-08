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
  expect(manifest.kriterien).toBeUndefined();
  for (const q of manifest.quellen) expect(q.lizenzen.length).toBeGreaterThan(0);
});
