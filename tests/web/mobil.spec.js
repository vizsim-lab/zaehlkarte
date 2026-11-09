import { expect, test } from "@playwright/test";
import { oeffne } from "./helpers.js";

test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

test("Handy: Legende startet zugeklappt und klappt auf", async ({ page }) => {
  const fehler = await oeffne(page);
  expect(fehler).toEqual([]);
  const legende = page.locator("#legend");
  await expect(legende).toHaveClass(/collapsed/);
  await expect(page.locator("#fc-stellen")).toBeVisible();
  await expect(page.locator("#thema-chips")).toBeHidden();
  await page.locator(".legend-title").click();
  await expect(legende).not.toHaveClass(/collapsed/);
  await expect(page.locator("#thema-chips")).toBeVisible();
  const box = await legende.boundingBox();
  expect(box.width).toBeGreaterThan(380); // Bottom-Sheet über die volle Breite
});

test("Handy: DE/EN im zugeklappten Streifen schaltet um, ohne die Legende aufzuklappen", async ({ page }) => {
  await oeffne(page);
  const legende = page.locator("#legend");
  await expect(legende).toHaveClass(/collapsed/);
  await page.locator('#sprachwahl [data-sprache="en"]').tap();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(legende).toHaveClass(/collapsed/);
  await expect(page.locator(".legend-subtext")).toContainText("Municipal traffic counts");
  await expect(page.locator("#fc-stellen + span")).toHaveText("sites");
});
