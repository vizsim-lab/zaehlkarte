// Sprachumschalter DE/EN: Deutsch ist Standard, EN wählbar, Wahl in ?lang= und gemerkt.
// Die Oberfläche folgt der Sprache; Inhalte aus den Daten (Hinweise, Datenlage-Texte,
// Anfragetexte) bleiben deutsch und tragen lang="de".
import { expect, test } from "@playwright/test";
import { klickeStelle, oeffne } from "./helpers.js";

test("Sprache: Deutsch ist Standard, EN schaltet um und bleibt gemerkt", async ({ page }) => {
  const fehler = await oeffne(page, "#t=kfz.menge");
  expect(fehler).toEqual([]);
  await expect(page.locator("html")).toHaveAttribute("lang", "de");
  await expect(page.locator('#sprachwahl [data-sprache="de"]')).toHaveAttribute("aria-pressed", "true");

  await page.locator('#sprachwahl [data-sprache="en"]').click();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator('#sprachwahl [data-sprache="en"]')).toHaveAttribute("aria-pressed", "true");
  await expect(page).toHaveURL(/\?lang=en/);
  await expect(page).toHaveTitle(/municipal traffic counts/);
  await expect(page.locator('[data-section="thema"] .legend-section-title')).toHaveText("Mode");
  await expect(page.locator('#thema-chips [data-thema="kfz"]')).toHaveText("Motor vehicles");
  await expect(page.locator("#klassen-legende")).toContainText("Motor vehicles, total 7–19 h");
  await expect(page.locator("#klassen-legende")).toContainText("35,000 and more");
  await expect(page.locator("#tage-liste")).toContainText("School holidays");
  await expect(page.locator("#datenlage-legende")).toContainText("collected – request promising");
  await expect(page.locator("#fc-stellen")).toHaveText(/^\d{1,3}(,\d{3})*$/);
  await expect(page.locator("#search")).toHaveAttribute("placeholder", "Search address...");
  await expect(page.locator(".maplibregl-ctrl-zoom-in")).toHaveAttribute("title", "Zoom in");

  // Der Zustand der Karte bleibt im #-Teil, die Sprache steht davor
  await page.locator('#thema-chips [data-thema="rad"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Cyclists, total 7–19 h");
  await expect(page).toHaveURL(/\?lang=en#.*t=rad\.menge/);

  // gemerkte Wahl: ohne ?lang= wieder Englisch
  await page.goto("/index.html");
  await page.waitForFunction(() => document.documentElement.dataset.bereit === "1");
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await expect(page.locator('#thema-chips [data-thema="fuss"]')).toHaveText("Pedestrians");

  // und zurück
  await page.locator('#sprachwahl [data-sprache="de"]').click();
  await expect(page.locator('#thema-chips [data-thema="kfz"]')).toHaveText("Kfz");
  await expect(page.locator("#klassen-legende")).toContainText("ab 35.000");
  await expect(page.locator(".maplibregl-ctrl-zoom-in")).toHaveAttribute("title", "Vergrößern");
  await expect(page).toHaveURL(/\?lang=de/);
});

test("Sprache EN: Stelle englisch, Hinweise aus den Daten deutsch; Wechsel zeichnet sie neu", async ({ page }) => {
  await oeffne(page, "?lang=en");
  await klickeStelle(page, (x) => x.quelle === "olpe" && x.name === "Zum Honigsack 35");
  const detail = page.locator("#detail");
  await expect(detail).toBeVisible();
  await expect(detail).toContainText("Provenance");
  await expect(detail).toContainText("Licence");
  await expect(detail.locator("thead").first()).toContainText("Date");
  await expect(detail.locator(".detail-hinweise")).toHaveAttribute("lang", "de");
  await expect(detail.locator(".detail-hinweise")).toContainText("Radargerät");

  await page.locator('#sprachwahl [data-sprache="de"]').click();
  await expect(detail).toContainText("Herkunft");
  await expect(detail.locator("thead").first()).toContainText("Datum");
});

test("Sprache EN: Datenlage mit englischer Oberfläche, Anfragetext deutsch", async ({ page }) => {
  await oeffne(page, "?lang=en");
  await page.evaluate(() => window.__app.zeigeDatenlage("Dresden"));
  const el = page.locator("#datenlage-detail");
  await expect(el).toBeVisible();
  await expect(el).toContainText("Recommendation");
  await expect(el).toContainText("Request text");
  await expect(el).toContainText("The research notes are in German.");
  await expect(el.locator(".anfrage-text")).toHaveAttribute("lang", "de");
  await expect(el.locator(".anfrage-text")).toHaveValue(/Stadt Dresden/);
  await expect(el.locator("[data-kopieren]")).toHaveText("Copy text");

  // Wechsel bei offenem Panel: bleibt offen, jetzt deutsch
  await page.locator('#sprachwahl [data-sprache="de"]').click();
  await expect(el).toBeVisible();
  await expect(el).toContainText("Empfehlung");
  await expect(el).not.toContainText("The research notes are in German.");
});
