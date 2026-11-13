// Familie Dauerzählstellen im Browser – mit kleinen Fixture-Dateien (tests/web/fixtures/dauer/)
// statt der echten Daten, damit der Test nicht vom Release-Asset „dauerzaehlstellen“ abhängt.
// Fixture: zwei Messquerschnitte in Berlin, Juni 2025 (am 3.6. fehlt bei TE001 eine Stunde), dazu
// Hamburg vom 15.6. bis 10.7.2025: eine Kfz-Zählstelle mit Schwerverkehr und eine Rad-Zählstelle,
// und Ettlingen vom 1.6. bis 10.7.2025: zwei Richtungen eines Sensors am selben Punkt (CC BY-NC).
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { oeffne, zahl } from "./helpers.js";

const FIXTURES = new URL("./fixtures/", import.meta.url);

/** Anfragen an data/dauer/ aus den Fixtures beantworten (oder ohne Dauerzählstellen: 404). */
async function dauer(page, { da = true } = {}) {
  await page.route(/\/data\/dauer\/.*\.json$/, (route) => {
    const pfad = new URL(route.request().url()).pathname.replace(/^.*\/data\//, "");
    let body = null;
    try {
      if (da) body = readFileSync(new URL(pfad, FIXTURES));
    } catch {
      body = null;
    }
    return body ? route.fulfill({ status: 200, contentType: "application/json", body }) : route.fulfill({ status: 404, body: "" });
  });
}

async function klickeDauer(page, id) {
  const p = await page.evaluate(async (sid) => {
    const app = window.__app;
    const s = app.dauer().jeId.get(sid);
    app.karte.jumpTo({ center: [s.lon, s.lat], zoom: 18 });
    await new Promise((ok) => app.karte.once("idle", ok));
    return app.karte.project([s.lon, s.lat]);
  }, id);
  await page.mouse.click(p.x, p.y);
}

test("Umschalter lädt die Dauerzählstellen: Tag, Klassen, Zähler und Link", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page);
  const knopf = page.locator('[data-familie="d"]');
  await expect(knopf).toBeEnabled();
  await knopf.click();
  await expect(knopf).toHaveClass(/is-active/);
  await expect(page).toHaveURL(/f=d/);
  await expect(page.locator("#dauer-tag")).toBeVisible();
  await expect(page.locator("#dauer-tag-wert")).toHaveText(/^Do\.? 26\.06\.2025 · Schultag$/);
  await expect(page.locator("#klassen-legende")).toContainText("Kfz, Tagessumme am 26.06.2025");
  await expect(page.locator('[data-section="filter"]')).toBeHidden();
  await expect(page.locator("#art-wahl")).toBeHidden();
  await expect(page.locator('#thema-chips [data-thema="lkw"]')).toBeVisible();
  // Schwerverkehr gibt es hier nur als Klasse der Kamera – anders beschriftet als bei den Kurzzeitzählungen
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveText("Schwerverkehr (Detektor)");
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toBeVisible();
  await expect(page.locator('#thema-chips [data-thema="fuss"]')).toBeHidden();
  await expect(page.locator("#fc-zaehlungen-name")).toHaveText("vollständig");
  expect(await zahl(page.locator("#fc-stellen"))).toBe(5); // Berlin zwei, Hamburg eine (Kfz), Ettlingen zwei
  // querySourceFeatures liefert je Kachel – Stellen zählen, nicht Treffer
  await expect.poll(() => page.evaluate(() => new Set(window.__app.karte.querySourceFeatures("dauer").map((f) => f.properties.i)).size)).toBe(5);
  expect(await page.evaluate(() => window.__app.karte.getLayoutProperty("stellen-kreis", "visibility"))).toBe("none");

  // ein Tag zurück, dann der 3.6.: TE001 dort nicht vollständig gezählt -> hohl, kein Wert
  await page.locator('[data-schritt="-1"]').click();
  await expect(page).toHaveURL(/z=2025-06-25/);
  await page.locator("#dauer-datum").fill("2025-06-03");
  await expect(page).toHaveURL(/z=2025-06-03/);
  await expect(page.locator("#fc-zaehlungen")).toHaveText("3"); // TE002 und die beiden in Ettlingen
  const nicht = page.locator("#klassen-legende .legend-item").last();
  await expect(nicht).toContainText("an dem Tag nicht vollständig gezählt");
  await expect(nicht.locator(".count-badge")).toHaveText("1");

  // zurück zu den Kurzzeitzählungen: Filter und Kennzahl wieder da, f=d weg
  await page.locator('[data-familie="k"]').click();
  await expect(page.locator('[data-section="filter"]')).toBeVisible();
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveText("Schwerverkehr");
  await expect(page).not.toHaveURL(/f=d/);
  expect(await zahl(page.locator("#fc-stellen"))).toBeGreaterThan(1000);
  expect(fehler).toEqual([]);
});

test("Permalink und Klick: Detail mit Tagesreihe, Tagesgang und unvollständigem Tag", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&t=lkw.menge&z=2025-06-02&s=berlin_viz:TE001");
  await expect(page.locator('#thema-chips [data-thema="lkw"]')).toHaveClass(/is-active/);
  const detail = page.locator("#dauer-detail");
  await expect(detail).toBeVisible();
  await expect(detail.locator(".detail-titel")).toHaveText("Clayallee");
  await expect(detail).toContainText("Richtung Potsdamer Chaussee (Süd)");
  await expect(detail.locator("svg.tr")).toBeVisible();
  await expect(detail.locator("svg.tg")).toBeVisible();
  await expect(detail.locator(".detail-kennwerte")).toContainText("Lkw (Detektor)");
  await expect(detail).toContainText("dl-de/by-2-0");
  await expect(detail).toContainText("Radspur (Stammdaten 2022)");
  await expect(detail.locator(".detail-hinweise")).toContainText("vereinzelt Messfehler");

  // am 3.6. fehlt eine Stunde: keine Tagessumme, sondern der Hinweis
  await page.evaluate(() => window.__app.tagWechseln("2025-06-03"));
  await expect(detail.locator(".detail-kennwerte")).toContainText("nicht vollständig gezählt (23 von 24 Stunden)");

  // andere Stelle per Klick auf die Karte
  await klickeDauer(page, "berlin_viz:TE002");
  await expect(detail).toContainText("Richtung Hüttenweg (Nord)");
  await expect(page).toHaveURL(/s=berlin_viz:TE002/);
  await detail.locator("[data-schliessen]").click();
  await expect(detail).toBeHidden();
  expect(fehler).toEqual([]);
});

test("CSV der Dauerzählstellen: Tagessummen des Tags, leer statt 0", async ({ page }) => {
  await dauer(page);
  await oeffne(page, "#f=d&z=2025-06-03");
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  expect(download.suggestedFilename()).toBe("dauerzaehlstellen_2025-06-03.csv");
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.replace(/^﻿/, "").trim().split("\n");
  expect(zeilen[0]).toBe("quelle;stelle;name;abschnitt;richtung;lon;lat;datum;tagtyp;kfz_tagessumme;lkw_tagessumme;sv_tagessumme;rad_tagessumme;lizenz");
  expect(zeilen).toHaveLength(5); // Hamburg beginnt erst am 15.6.
  expect(zeilen[1]).toMatch(/^berlin_viz;berlin_viz:TE001;.*;2025-06-03;Schultag;;;;;dl-de\/by-2-0$/);
  expect(zeilen[2]).toMatch(/;2025-06-03;Schultag;\d+;\d+;;;dl-de\/by-2-0$/);
  // die Lizenz steht in jeder Zeile – bei Ettlingen nur nicht kommerziell
  expect(zeilen[3]).toMatch(/^ettlingen;ettlingen:1263-2;Rastatter Straße;;Richtung Bruchhausen;.*;2025-06-03;Schultag;1142;;;;CC BY-NC 4\.0$/);
});

test("Ohne Dauerzählstellen bleibt der Umschalter aus, die Karte läuft wie bisher", async ({ page }) => {
  await dauer(page, { da: false });
  const fehler = await oeffne(page, "#f=d");
  await expect(page.locator('[data-familie="d"]')).toBeDisabled();
  await expect(page.locator('[data-familie="k"]')).toHaveClass(/is-active/);
  await expect(page.locator("#familie-hinweis")).toContainText("nicht verfügbar");
  expect(await zahl(page.locator("#fc-stellen"))).toBeGreaterThan(1000);
  expect(fehler).toEqual([]);
});

test("Dauerzählstellen auf Englisch", async ({ page }) => {
  await dauer(page);
  await oeffne(page, "?lang=en#f=d");
  await expect(page.locator('[data-familie="d"]')).toHaveText("Permanent counters");
  await expect(page.locator("#klassen-legende")).toContainText("Motor vehicles, daily total on 26 Jun 2025");
  await expect(page.locator("#dauer-tag-wert")).toHaveText("Thu 26 Jun 2025 · School day");
  await expect(page.locator("#fc-zaehlungen-name")).toHaveText("complete");
});

test("Mehrere Quellen: Schwerverkehr und Rad aus Hamburg, Sprung zu Berlin außerhalb seines Zeitraums", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&z=2025-07-05");
  await expect(page.locator("#dauer-tag-wert")).toHaveText(/^Sa\.? 05\.07\.2025 · Wochenende$/);
  // Berlin zählt Kfz, hat am 5.7. aber keine Werte mehr: Hinweis mit Sprung zu seinem Standardtag
  const hinweis = page.locator("#dauer-quellen");
  await expect(hinweis).toBeVisible();
  await expect(hinweis).toContainText("Berlin (Verkehrsdetektion): Werte vom 01.06.2025 bis 30.06.2025");
  expect(await zahl(page.locator("#fc-stellen"))).toBe(3); // Hamburg eine, Ettlingen zwei

  await page.locator('#thema-chips [data-thema="sv"]').click();
  await expect(page).toHaveURL(/t=sv\.menge/);
  await expect(page.locator("#klassen-legende")).toContainText("Schwerverkehr (Detektor), Tagessumme am 05.07.2025");
  await expect(hinweis).toBeHidden(); // Schwerverkehr zählt nur Hamburg
  expect(await zahl(page.locator("#fc-stellen"))).toBe(1);

  await page.locator('#thema-chips [data-thema="rad"]').click();
  await expect(page).toHaveURL(/t=rad\.menge/);
  await klickeDauer(page, "hamburg_rad:7433952");
  const detail = page.locator("#dauer-detail");
  await expect(detail.locator(".detail-titel")).toHaveText("Alsterufer");
  await expect(detail).toContainText("ohne Richtung (Querschnitt)");
  await expect(detail.locator(".detail-kennwerte")).toContainText("Rad");

  // zurück zu Kfz und per Sprung zu Berlin
  await page.locator('#thema-chips [data-thema="kfz"]').click();
  await hinweis.locator("[data-sprung]").click();
  await expect(page).toHaveURL(/z=2025-06-26/);
  await expect(hinweis).toBeHidden();
  expect(await zahl(page.locator("#fc-stellen"))).toBe(5);
  expect(fehler).toEqual([]);
});

test("Stellen am selben Punkt: Umschalter in der Seitenleiste, Lizenz CC BY-NC", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&z=2025-06-26&s=ettlingen:1263-2");
  const detail = page.locator("#dauer-detail");
  await expect(detail.locator(".detail-titel")).toHaveText("Rastatter Straße");
  const punkt = detail.locator(".dd-punkt");
  await expect(punkt).toContainText("Am selben Punkt");
  await expect(punkt.locator("button")).toHaveCount(2);
  await expect(punkt.locator('[aria-pressed="true"]')).toHaveText("Richtung Bruchhausen");
  await expect(detail.locator(".detail-kennwerte")).toContainText("1.142");
  await expect(detail.getByRole("link", { name: "CC BY-NC 4.0" })).toHaveAttribute("href", /licenses\/by-nc\/4\.0/);
  await expect(detail.locator(".detail-hinweise")).toContainText("nur nicht kommerziell");

  // zur anderen Richtung: Seitenleiste und Link wechseln, der Tag bleibt
  await punkt.locator("button", { hasText: "Richtung Innenstadt" }).click();
  await expect(page).toHaveURL(/s=ettlingen:1263-3/);
  await expect(page).toHaveURL(/z=2025-06-26/);
  await expect(detail.locator('.dd-punkt [aria-pressed="true"]')).toHaveText("Richtung Innenstadt");
  await expect(detail.locator(".detail-kennwerte")).toContainText("2.092");

  // Stellen ohne Nachbarn am selben Punkt haben keinen Umschalter
  await klickeDauer(page, "berlin_viz:TE001");
  await expect(detail.locator(".detail-titel")).toHaveText("Clayallee");
  await expect(detail.locator(".dd-punkt")).toHaveCount(0);
  expect(fehler).toEqual([]);
});
