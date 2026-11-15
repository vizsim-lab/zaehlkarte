// Gemeinsame Schritte der Browser-Tests.
import { readFileSync } from "node:fs";
import { expect } from "@playwright/test";

// Datenlage aus einer kleinen Fixture (tests/web/fixtures/datenlage.json: zehn Kommunen mit echten
// Texten, Stand 14.11.2026) statt der echten Datei – die Tests hängen so nicht an der Recherche.
// Den Vertrag der echten datenlage.json prüft tests/web/vertrag.spec.js.
const DATENLAGE = readFileSync(new URL("./fixtures/datenlage.json", import.meta.url));

/** Seite öffnen, Netz außer dem Testserver sperren, warten bis die Karte bereit ist.
 *  `datenlage`: Funktion, die die Fixture vor dem Laden ändert (bekommt das geparste JSON). */
export async function oeffne(page, hash = "", { datenlage = null } = {}) {
  const fehler = [];
  page.on("pageerror", (e) => fehler.push(e.message));
  await page.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, (route) => route.abort());
  const body = datenlage ? JSON.stringify(datenlage(JSON.parse(DATENLAGE))) : DATENLAGE;
  await page.route(/\/data\/datenlage\.json$/, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body }));
  await page.goto(`/index.html${hash}`);
  await page.waitForFunction(() => document.documentElement.dataset.bereit === "1");
  return fehler;
}

/** Zahl aus einem Element mit deutscher Tausendertrennung. */
export async function zahl(locator) {
  return Number((await locator.textContent()).replace(/\./g, ""));
}

/** Eine Stelle per Klick auf die Karte öffnen (Bildschirmpunkt aus MapLibre). */
export async function klickeStelle(page, auswahl) {
  const punkt = await page.evaluate(async (fn) => {
    const app = window.__app;
    const s = app.daten.stellen.find(new Function(`return ${fn}`)());
    app.karte.jumpTo({ center: [s.lon, s.lat], zoom: 16 });
    await new Promise((ok) => app.karte.once("idle", ok));
    const p = app.karte.project([s.lon, s.lat]);
    return { x: p.x, y: p.y, id: s.id, n: s.zaehlungen.length };
  }, auswahl.toString());
  await page.mouse.click(punkt.x, punkt.y);
  return punkt;
}

/** Steckbrief einer Kommune öffnen (wie ein Klick auf ihren Punkt) und warten, bis die
 *  Dauerzählstellen darin geladen sind. */
export async function oeffneKommune(page, ags) {
  await page.evaluate((a) => window.__app.oeffneKommune(a), ags);
  const el = page.locator("#kommune-detail");
  await page.waitForFunction(() => !document.querySelector("#kommune-detail [data-laedt]"));
  return el;
}

/** Datenlage im Steckbrief aufklappen, falls sie zu ist (zu ist sie, sobald etwas in der Karte
 *  ist – das hängt in den Smoke-Tests auch am Release-Asset der Dauerzählstellen im Build). */
export async function klappeDatenlageAuf(el) {
  const zu = el.locator(".kz-datenlage:not([open]) > summary");
  if (await zu.count()) await zu.click();
  await expect(el.locator(".kz-datenlage")).toHaveAttribute("open", "");
}
