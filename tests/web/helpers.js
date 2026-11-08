// Gemeinsame Schritte der Browser-Tests.

/** Seite öffnen, Netz außer dem Testserver sperren, warten bis die Karte bereit ist. */
export async function oeffne(page, hash = "") {
  const fehler = [];
  page.on("pageerror", (e) => fehler.push(e.message));
  await page.route(/^https?:\/\/(?!127\.0\.0\.1[:/])/, (route) => route.abort());
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
