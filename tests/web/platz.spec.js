// Platz der Panels (js/ui/platz.js): nie zwei Panels übereinander, die Knopfleiste rückt nie,
// die gewählte Stelle bleibt sichtbar, das Hover-Kärtchen öffnet zur freien Seite.
import { expect, test } from "@playwright/test";
import { oeffne, oeffneKommune } from "./helpers.js";

const RAVENSBURG = "08436064"; // Kommune aus der Fixture der Datenlage

/** Bildschirmpunkt einer Stelle, nachdem die Karte sie an den Punkt (x, Mitte) gelegt hat. */
async function legeStelleAn(page, auswahl, x = null) {
  return page.evaluate(async ({ fn, x }) => {
    const a = window.__app;
    const s = a.daten.stellen.find(new Function(`return ${fn}`)());
    a.karte.jumpTo({ center: [s.lon, s.lat], zoom: 17 });
    if (x != null) a.karte.panBy([a.karte.getContainer().clientWidth / 2 - x, 0], { duration: 0 });
    await new Promise((ok) => a.karte.once("idle", ok));
    const p = a.karte.project([s.lon, s.lat]);
    return { x: p.x, y: p.y, lon: s.lon, lat: s.lat };
  }, { fn: auswahl.toString(), x });
}

/** Liegt die Stelle frei über dem offenen Sheet (Handy)? */
const ueberDemSheet = (page, { lon, lat }) => page.evaluate(({ lon, lat }) => {
  const y = window.__app.karte.project([lon, lat]).y;
  return y > 0 && y < document.getElementById("detail").getBoundingClientRect().top - 10;
}, { lon, lat });

test.describe("Laptop", () => {
  test("Knopfleiste bleibt unten links, Seitenleisten enden darüber", async ({ page }) => {
    await page.setViewportSize({ width: 1400, height: 700 });
    await oeffne(page);
    const leiste = await page.locator("#bottom-left-ui-container").boundingBox();
    const knopf = await page.locator(".map-settings-toggle").boundingBox();
    expect(Math.abs(leiste.y + leiste.height - (knopf.y + knopf.height))).toBeLessThan(2); // eine Zeile
    expect(leiste.x).toBeGreaterThan(knopf.x + knopf.width); // Plus, Minus, Kompass rechts daneben
    await page.evaluate(() => {
      const a = window.__app;
      a.oeffneStelle(a.daten.stellen.find((x) => x.quelle === "berlin" && x.zaehlungen.length > 5));
    });
    const panel = page.locator("#detail");
    await expect(panel.locator("svg.tg")).toBeVisible();
    // lang genug, um bis unten zu reichen: endet trotzdem über der Leiste
    expect(await panel.evaluate((el) => el.scrollHeight > el.clientHeight)).toBe(true);
    const p = await panel.boundingBox();
    expect(p.y + p.height).toBeLessThanOrEqual(knopf.y - 8);
    expect(await page.locator("#bottom-left-ui-container").boundingBox()).toEqual(leiste); // rückt nicht
    expect(await page.locator(".map-settings-toggle").boundingBox()).toEqual(knopf);
  });

  test("Breiter Bildschirm: die Legende bleibt neben dem Steckbrief offen", async ({ page }) => {
    await oeffne(page); // 1400 × 900
    await oeffneKommune(page, RAVENSBURG);
    await expect(page.locator("#legend")).not.toHaveClass(/collapsed/);
  });

  test("Schmaler Laptop: die Legende klappt für eine Seitenleiste zu und danach wieder auf", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await oeffne(page);
    const legende = page.locator("#legend");
    const schliesse = () => page.locator("#kommune-detail [data-schliessen]").click();
    await expect(legende).not.toHaveClass(/collapsed/);
    await oeffneKommune(page, RAVENSBURG);
    await expect(legende).toHaveClass(/collapsed/);
    await schliesse();
    await expect(legende).not.toHaveClass(/collapsed/);
    // von Hand wieder aufgeklappt: liegt neben dem Steckbrief, nicht darauf, und bleibt offen
    await oeffneKommune(page, RAVENSBURG);
    await expect(legende).toHaveClass(/collapsed/);
    await page.locator(".legend-heading").click();
    await expect(legende).not.toHaveClass(/collapsed/);
    const k = await page.locator("#kommune-detail").boundingBox();
    expect(k.x + k.width).toBeLessThan((await legende.boundingBox()).x);
    await schliesse();
    await expect(legende).not.toHaveClass(/collapsed/);
    // von Hand zugeklappt: bleibt zu
    await page.locator(".legend-heading").click();
    await expect(legende).toHaveClass(/collapsed/);
    await oeffneKommune(page, RAVENSBURG);
    await schliesse();
    await expect(legende).toHaveClass(/collapsed/);
  });

  test("Hover-Kärtchen öffnet zur freien Seite und geht beim Klick weg", async ({ page }) => {
    await oeffne(page);
    await page.evaluate(() => {
      const a = window.__app;
      a.oeffneStelle(a.daten.stellen.find((x) => x.quelle === "ravensburg"));
    });
    await expect(page.locator("#detail")).toBeVisible();
    const panel = await page.locator("#detail").boundingBox();
    const legende = await page.locator("#legend").boundingBox();
    const popup = page.locator(".maplibregl-popup");
    const ueber = async (x) => {
      const p = await legeStelleAn(page, (s) => s.quelle === "olpe", x);
      await page.mouse.move(p.x + 1, p.y + 1);
      await page.mouse.move(p.x, p.y);
      await expect(popup).toBeVisible();
      return p;
    };
    await ueber(panel.x + panel.width + 25); // dicht neben der Seitenleiste: Kärtchen nach rechts
    expect((await popup.boundingBox()).x).toBeGreaterThanOrEqual(panel.x + panel.width);
    const p = await ueber(legende.x - 25); // dicht vor der Legende: Kärtchen nach links
    const b = await popup.boundingBox();
    expect(b.x + b.width).toBeLessThanOrEqual(legende.x);
    await page.mouse.click(p.x, p.y);
    await expect(page.locator("#detail")).toContainText("Olpe");
    await expect(popup).toHaveCount(0); // was es zeigte, steht jetzt in der Seitenleiste
  });

  test("Suche: der Treffer landet im freien Teil der Karte", async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 768 });
    await oeffne(page);
    await oeffneKommune(page, RAVENSBURG);
    await page.route(/photon\.komoot\.io/, (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ features: [{ type: "Feature", geometry: { type: "Point", coordinates: [9.4797, 51.3127] }, properties: { name: "Kassel", country: "Deutschland" } }] }),
    }));
    await page.locator("#search").fill("Kassel");
    await page.locator(".geocoder-result-item").first().click();
    const k = await page.locator("#kommune-detail").boundingBox();
    const mitte = (k.x + k.width + 1024) / 2; // Legende zugeklappt: frei bis zum rechten Rand
    await expect.poll(() => page.evaluate(() => Math.round(window.__app.karte.project([9.4797, 51.3127]).x)), { timeout: 10_000 })
      .toBeGreaterThan(mitte - 4);
    expect(await page.evaluate(() => window.__app.karte.project([9.4797, 51.3127]).x)).toBeLessThan(mitte + 4);
  });
});

test.describe("Fenster 700 px", () => {
  test.use({ viewport: { width: 700, height: 900 } });

  test("Handy-Layout: der Steckbrief ist ein Sheet und liegt nie auf der Legende", async ({ page }) => {
    await oeffne(page);
    const legende = page.locator("#legend");
    await expect(legende).toHaveClass(/collapsed/);
    await oeffneKommune(page, RAVENSBURG);
    const k = await page.locator("#kommune-detail").boundingBox();
    expect(k.width).toBeGreaterThan(690); // über die volle Breite
    expect(k.y + k.height).toBeGreaterThan(895); // unten angedockt
    await expect(legende).toHaveClass(/collapsed/);
    await expect(page.locator(".map-settings-toggle")).toBeHidden();
  });
});

test.describe("Handy", () => {
  test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });

  test("nie zwei Sheets: der Steckbrief klappt die Legende zu, die Knöpfe weichen", async ({ page }) => {
    await oeffne(page);
    const legende = page.locator("#legend");
    await page.locator(".legend-heading").click();
    await expect(legende).not.toHaveClass(/collapsed/);
    await oeffneKommune(page, RAVENSBURG);
    await expect(legende).toHaveClass(/collapsed/);
    await expect(page.locator("#bottom-left-ui-container")).toBeHidden();
    await expect(page.locator(".map-settings-toggle")).toBeHidden();
    await page.locator("#kommune-detail [data-schliessen]").tap();
    await expect(page.locator("#kommune-detail")).toBeHidden();
    await expect(legende).toHaveClass(/collapsed/); // bleibt zu: wer schließt, will die Karte sehen
    await expect(page.locator(".map-settings-toggle")).toBeVisible();
  });

  test("Antippen einer Stelle: kein Hover-Kärtchen, die Stelle rückt über das Sheet", async ({ page }) => {
    await oeffne(page);
    // eine Stelle mit vielen Zählungen: das Sheet wird hoch und deckt die Mitte, wo sie liegt
    const p = await legeStelleAn(page, (s) => s.zaehlungen.length > 5);
    await page.touchscreen.tap(p.x, p.y);
    await expect(page.locator("#detail")).toBeVisible();
    await expect(page.locator(".maplibregl-popup")).toHaveCount(0);
    await expect.poll(() => ueberDemSheet(page, p)).toBe(true);
  });

  test("Link auf eine Stelle: sie liegt über dem Sheet", async ({ page, context }) => {
    await oeffne(page);
    const s = await page.evaluate(() => {
      const x = window.__app.daten.stellen.find((s) => s.zaehlungen.length > 5);
      return { id: x.id, lon: x.lon, lat: x.lat };
    });
    const neu = await context.newPage();
    await oeffne(neu, `#s=${s.id}`);
    await expect(neu.locator("#detail")).toBeVisible();
    await expect.poll(() => ueberDemSheet(neu, s)).toBe(true);
  });
});
