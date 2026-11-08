import { expect, test } from "@playwright/test";
import { klickeStelle, oeffne, zahl } from "./helpers.js";

test("lädt ohne Fehler und zeigt Stellen", async ({ page }) => {
  const fehler = await oeffne(page);
  expect(fehler).toEqual([]);
  expect(await zahl(page.locator("#fc-stellen"))).toBeGreaterThan(1000);
  expect(await zahl(page.locator("#fc-zaehlungen"))).toBeGreaterThan(1000);
  await expect(page.locator('#thema-chips [data-thema="fuss"]')).toHaveClass(/is-active/);
  await expect(page.locator("#kriterium")).toBeVisible();
  const n = await page.evaluate(() => window.__app.karte.querySourceFeatures("stellen").length);
  expect(n).toBeGreaterThan(0);
});

test("Thema und Darstellung wechseln Legende und Link", async ({ page }) => {
  await oeffne(page);
  await page.locator('#thema-chips [data-thema="rad"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Rad, Summe 7–19 Uhr");
  await expect(page.locator("#art-wahl")).toBeVisible();
  await page.locator('#modus-chips [data-modus="radanteil"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Radanteil");
  await page.locator('#art-chips [data-art="sp"]').click();
  await expect(page).toHaveURL(/t=rad\.radanteil/);
  await expect(page).toHaveURL(/a=sp/);
  // Legendenzähler = Stellen in der Karte
  const summe = await page.locator("#klassen-legende .count-badge").evaluateAll(
    (els) => els.reduce((s, e) => s + Number(e.textContent.replace(/\./g, "")), 0));
  expect(summe).toBe(await zahl(page.locator("#fc-stellen")));
});

test("Permalink stellt den Zustand her", async ({ page }) => {
  await oeffne(page, "#t=kfz.svanteil&a=w24&j=2010-2020&dl=0&d=sw");
  await expect(page.locator('#thema-chips [data-thema="kfz"]')).toHaveClass(/is-active/);
  await expect(page.locator('#modus-chips [data-modus="svanteil"]')).toHaveClass(/is-active/);
  await expect(page.locator('#art-chips [data-art="w24"]')).toHaveClass(/is-active/);
  await expect(page.locator("#jahre-wert")).toHaveText("2010–2020");
  await expect(page.locator("#toggle-datenlage")).not.toBeChecked();
  await expect(page.locator('[data-tag="f"]')).not.toBeChecked();
});

test("Klick auf eine Stelle zeigt Zählungen und Tagesgang", async ({ page }) => {
  await oeffne(page);
  const s = await klickeStelle(page, (x) => x.quelle === "berlin" && x.zaehlungen.length >= 3
    && x.zaehlungen.some((z) => z.kh));
  const detail = page.locator("#detail");
  await expect(detail).toBeVisible();
  await expect(detail.locator(".dz-zeile")).toHaveCount(s.n);
  await expect(detail.locator("svg.tg")).toBeVisible();
  await expect(detail).toContainText("Schulweg-Kriterium");
  await expect(page).toHaveURL(new RegExp(`s=${s.id.replace(":", ":")}`));
  // andere Zählung wählen -> Tagesgang wird neu gezeichnet
  await detail.locator(".dz-zeile").last().click();
  await expect(detail.locator(".dz-zeile.is-aktiv")).toHaveCount(1);
  await expect(detail.locator("svg.tg, .detail-zaehlung .pop-meta").first()).toBeVisible();
  await detail.locator("[data-schliessen]").click();
  await expect(detail).toBeHidden();
});

test("Stelle aus MobiData BW: 24-Stunden-Tagesgang mit Kfz und Schwerverkehr", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge");
  await klickeStelle(page, (x) => x.quelle === "ravensburg" && x.zaehlungen.some((z) => z.fenster === "0–24"));
  const detail = page.locator("#detail");
  await expect(detail).toContainText("Ravensburg");
  await expect(detail.locator(".tg-legende")).toContainText("Schwerverkehr");
  await expect(detail).toContainText("dl-de/by-2-0");
});

test("Schulweg-Regler ändern die Einstufung", async ({ page }) => {
  await oeffne(page);
  const verdacht = () => page.locator("#klassen-legende .legend-item").first().locator(".count-badge");
  const vorher = await zahl(verdacht());
  await page.locator("#schwelle-stunde").fill("10");
  await expect.poll(async () => zahl(verdacht())).toBeGreaterThan(vorher);
  await expect(page).toHaveURL(/k=10,300/);
});

test("CSV-Export der Zählungen im Filter", async ({ page }) => {
  await oeffne(page, "#t=rad.menge&q=ravensburg");
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  expect(download.suggestedFilename()).toMatch(/^zaehlungen_\d{4}-\d{2}-\d{2}\.csv$/);
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.trim().split("\n");
  expect(zeilen[0]).toContain("quelle;stelle;name");
  expect(zeilen.length).toBeGreaterThan(50);
  expect(zeilen.slice(1).every((z) => z.startsWith("ravensburg;"))).toBe(true);
});

test("Datenlage: Klick auf eine Kommune zeigt Stand und Belege", async ({ page }) => {
  await oeffne(page);
  const p = await page.evaluate(async () => {
    const k = window.__app.karte;
    await new Promise((ok) => { k.once("idle", ok); k.triggerRepaint(); setTimeout(ok, 5000); });
    const f = k.queryRenderedFeatures({ layers: ["datenlage-kreis"] }).find((x) => x.properties.kommune === "Rostock");
    return k.project(f.geometry.coordinates);
  });
  await page.mouse.click(p.x, p.y);
  const el = page.locator("#datenlage-detail");
  await expect(el).toBeVisible();
  await expect(el).toContainText("Rostock");
  await expect(el.locator('a[href*="fragdenstaat.de"]')).toHaveCount(1);
});
