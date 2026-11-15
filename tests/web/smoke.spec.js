import { expect, test } from "@playwright/test";
import { klappeDatenlageAuf, klickeStelle, oeffne, oeffneKommune, zahl } from "./helpers.js";

test("lädt ohne Fehler und zeigt Stellen", async ({ page }) => {
  const fehler = await oeffne(page);
  expect(fehler).toEqual([]);
  expect(await zahl(page.locator("#fc-stellen"))).toBeGreaterThan(1000);
  expect(await zahl(page.locator("#fc-zaehlungen"))).toBeGreaterThan(1000);
  await expect(page.locator('#thema-chips [data-thema="kfz"]')).toHaveClass(/is-active/);
  await expect(page.locator("#modus-chips")).toBeHidden(); // Kfz: nur Menge
  await expect(page.locator("body")).not.toContainText("Schulweg");
  await expect.poll(() => page.evaluate(() => window.__app.karte.querySourceFeatures("stellen").length))
    .toBeGreaterThan(0);
});

test("Kopfzeile trägt das Zeichen, Favicons und Logo liegen bereit", async ({ page }) => {
  await oeffne(page);
  await expect(page.locator(".legend-heading .legend-logo")).toBeVisible();
  await expect(page.locator(".legend-heading")).toHaveText("Zählkarte"); // Zeichen ohne eigenen Text
  const links = await page.locator('link[rel="icon"], link[rel="apple-touch-icon"]')
    .evaluateAll((ls) => ls.map((l) => l.href));
  expect(links).toHaveLength(3);
  for (const url of [...links, new URL("logo/zaehlkarte-logo.svg", page.url()).href]) {
    expect((await page.request.get(url)).ok(), url).toBe(true);
  }
});

test("Verkehrsart und Darstellung wechseln Legende und Link", async ({ page }) => {
  await oeffne(page);
  await page.locator('#thema-chips [data-thema="rad"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Rad, Summe 7–19 Uhr");
  await page.locator('#modus-chips [data-modus="anteil"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Radanteil");
  await page.locator('#art-chips [data-art="sp"]').click();
  await expect(page).toHaveURL(/t=rad\.anteil/);
  await expect(page).toHaveURL(/a=sp/);
  await page.locator('#thema-chips [data-thema="sv"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Schwerverkehr, stärkste Stunde");
  await page.locator('#thema-chips [data-thema="fuss"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Fuß, stärkste Stunde");
  // Legendenzähler = Stellen in der Karte
  const summe = await page.locator("#klassen-legende .count-badge").evaluateAll(
    (els) => els.reduce((s, e) => s + Number(e.textContent.replace(/\./g, "")), 0));
  expect(summe).toBe(await zahl(page.locator("#fc-stellen")));
});

test("Permalink stellt den Zustand her", async ({ page }) => {
  await oeffne(page, "#t=sv.anteil&a=w24&j=2010-2020&dl=0&d=sw");
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveClass(/is-active/);
  await expect(page.locator('#modus-chips [data-modus="anteil"]')).toHaveClass(/is-active/);
  await expect(page.locator('#art-chips [data-art="w24"]')).toHaveClass(/is-active/);
  await expect(page.locator("#jahre-wert")).toHaveText("2010–2020");
  await expect(page.locator("#toggle-datenlage")).not.toBeChecked();
  await expect(page.locator('[data-tag="f"]')).not.toBeChecked();
});

test("Klick auf eine Stelle zeigt Zählungen und Tagesgang", async ({ page }) => {
  await oeffne(page, "#t=fuss.menge");
  const s = await klickeStelle(page, (x) => x.quelle === "berlin" && x.zaehlungen.length >= 3
    && x.zaehlungen.some((z) => z.g & 16));
  const detail = page.locator("#detail");
  await expect(detail).toBeVisible();
  await expect(detail.locator(".dz-zeile")).toHaveCount(s.n);
  await expect(detail.locator("svg.tg")).toBeVisible();
  await expect(detail.locator(".tg-legende")).toContainText("Kinder/Jugendliche");
  await expect(detail).not.toContainText("Schulweg");
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

test("Stelle aus Münster: zwei Spitzenstunden, nur stärkste Stunde, Rad-Spalte als Hinweis", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=sp");
  await klickeStelle(page, (x) => x.quelle === "muenster"
    && x.zaehlungen.some((z) => z.fenster === "7–8, 16–17"));
  const detail = page.locator("#detail");
  await expect(detail).toContainText("7–8, 16–17");
  await expect(detail).toContainText("Stadt Münster");
  await expect(detail).toContainText("dl-de/by-2-0");
  await expect(detail.locator(".detail-hinweise")).toContainText("keine vollständige Radzählung");
  // keine Summe 7–19 Uhr aus zwei Stunden
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "muenster").flatMap((s) => s.zaehlungen));
  expect(z.every((x) => x.w == null && x.w24 == null && x.sp)).toBe(true);
});

test("Stelle aus Konstanz: Fußzählung aus dem Geräteprotokoll, Lizenz CC0", async ({ page }) => {
  await oeffne(page, "#t=fuss.menge");
  await klickeStelle(page, (x) => x.quelle === "konstanz" && x.name === "Gartenstraße/Schottenstraße");
  const detail = page.locator("#detail");
  await expect(detail).toContainText("Gartenstraße/Schottenstraße");
  await expect(detail).toContainText("CC0 1.0");
  await expect(detail.locator(".detail-hinweise")).toContainText("Ende des 5-Minuten-Intervalls");
  const kennwerte = detail.locator(".detail-kennwerte");
  await expect(kennwerte).toContainText("Fuß");
  await expect(kennwerte).not.toContainText("Kfz"); // nicht gezählt: keine Zeile, keine 0
});

test("Stelle aus Potsdam: Spitzenstunden laut Zählplan, Quellenangabe nach NB-16-OGD", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=sp");
  await klickeStelle(page, (x) => x.quelle === "potsdam" && x.zaehlungen.length >= 2
    && x.zaehlungen.some((z) => z.fenster === "7–10, 15–18"));
  const detail = page.locator("#detail");
  const plan = detail.locator(".detail-zaehlplan");
  await expect(plan).toContainText("Frühspitze");
  await expect(plan).toContainText("Nachmittagsspitze");
  await expect(plan).toContainText("Summe 7–10, 15–18 Uhr");
  await expect(detail).toContainText("Spitzenstunden nach Kfz bestimmt");
  await expect(detail).toContainText("© LHP/NB-16-OGD/");
  await expect(detail).toContainText("Nutzungsbedingungen der LHP");
  await expect(detail.locator(".detail-kennwerte")).toContainText(/\d Uhr/); // stärkste Stunde Kfz
  await expect(detail.locator("svg.tg")).toHaveCount(0); // keine Stundenwerte, kein Tagesgang
  // in der Karte nur „stärkste Stunde“ (Kfz), keine Summe 7–19 oder 24 h
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "potsdam").flatMap((s) => s.zaehlungen));
  expect(z.length).toBeGreaterThan(400);
  expect(z.every((x) => x.w == null && x.w24 == null)).toBe(true);
  expect(z.filter((x) => x.sp).length).toBeGreaterThan(400);
});

test("Stelle aus Xanten: 24-Stunden-Querschnitt aus dem Mobilitätskonzept, nur Kfz", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=w24");
  await klickeStelle(page, (x) => x.quelle === "xanten" && x.typ === "Q" && x.name.startsWith("Westwall"));
  const detail = page.locator("#detail");
  await expect(detail).toContainText("Querschnitt 2");
  await expect(detail.locator("svg.tg")).toBeVisible();
  await expect(detail).toContainText("dl-de/zero-2-0");
  await expect(detail.locator(".detail-hinweise")).toContainText("Zählstellenkarte im Bericht");
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "xanten").flatMap((s) => s.zaehlungen));
  expect(z.length).toBe(18);
  expect(z.filter((x) => x.w24).length).toBe(6); // 6 Querschnitte über 24 Stunden
  expect(z.filter((x) => x.fenster === "7–9, 15–18").length).toBe(12);
});

test("Stelle aus Tübingen: Tageswerte ohne Lizenz, Richtungen summiert, nicht im CSV", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=w24");
  await klickeStelle(page, (x) => x.quelle === "tuebingen" && x.name.startsWith("Stuttgarter Straße"));
  const detail = page.locator("#detail");
  await expect(detail.locator(".ohne-lizenz")).toHaveText("ohne Lizenz");
  await expect(detail).toContainText("Ratsinformationssystem");
  await expect(detail.getByRole("link", { name: "Entfernen lassen" })).toBeVisible();
  await expect(detail).toContainText("Richtung Norden");
  await expect(detail).toContainText("Summe beider Richtungen");
  await expect(detail).toContainText("Nur Tagessummen geliefert");
  await expect(detail.locator("[data-csv]")).toHaveCount(0);
  await expect(detail.locator(".detail-hinweise")).toContainText("Adler-Kreuzung");
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "tuebingen").flatMap((s) => s.zaehlungen));
  expect(z.length).toBe(47);
  expect(z.every((x) => x.w24 && x.fenster === "0–24" && x.w == null)).toBe(true); // nur 24-Stunden-Werte
});

test("Stelle aus Neubulach: Knoten mit Summe 15–19 Uhr, ohne Spitzenstunden", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=w24");
  await klickeStelle(page, (x) => x.quelle === "neubulach" && x.name.startsWith("Calwer Straße"));
  const detail = page.locator("#detail");
  await expect(detail.locator(".ohne-lizenz")).toHaveText("ohne Lizenz");
  await expect(detail).toContainText("die Quelle nennt nur die Summe der gezählten Stunden");
  await expect(detail).toContainText("Laut Quelle");
  await expect(detail.locator(".detail-zaehlplan")).toContainText("Summe 15–19 Uhr");
  await expect(detail.locator(".detail-zaehlplan")).toContainText("3.644");
  await expect(detail.locator(".detail-hinweise")).toContainText("Summe der Zufahrten");
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "neubulach").flatMap((s) => s.zaehlungen));
  expect(z.length).toBe(8);
  expect(z.filter((x) => x.w24).length).toBe(1); // nur Knoten 1 über 24 Stunden
  expect(z.filter((x) => x.fenster === "15–19").length).toBe(7);
});

test("Stelle aus Nürnberg: Kfz 6–22 Uhr laut Bericht, ohne Lizenz, nur unter 6–22 Uhr", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=w16");
  await expect(page.locator('#art-chips [data-art="w16"]')).toHaveClass(/is-active/);
  await expect(page.locator("#klassen-legende")).toContainText("Kfz, Summe 6–22 Uhr");
  await klickeStelle(page, (x) => x.quelle === "nuernberg" && x.name === "Hallertorbrücke");
  const detail = page.locator("#detail");
  await expect(detail.locator(".ohne-lizenz")).toHaveText("ohne Lizenz");
  await expect(detail).toContainText("die Quelle nennt nur die Summe der gezählten Stunden");
  await expect(detail.locator(".detail-kennwerte thead")).toContainText("6–22 Uhr");
  await expect(detail.locator(".detail-kennwerte")).toContainText("21.629"); // Bericht 2025
  await expect(detail.locator(".detail-zaehlplan")).toContainText("Summe 6–22 Uhr");
  await expect(detail).toContainText("Zählstelle 65 (Bericht 2025");
  await expect(detail.locator("[data-csv]")).toHaveCount(0);
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "nuernberg").flatMap((s) => s.zaehlungen));
  expect(z.length).toBe(1650);
  // nur die Summe 6–22 Uhr: keine Stunden, also weder 7–19 Uhr noch 24 Stunden
  expect(z.every((x) => x.w16 && x.fenster === "6–22" && x.w == null && x.w24 == null)).toBe(true);
});

test("Stelle aus Olpe: Radarmessung je Fahrzeug, Lizenz je Datensatz", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&a=w24");
  await klickeStelle(page, (x) => x.quelle === "olpe" && x.name === "Zum Honigsack 35");
  const detail = page.locator("#detail");
  await expect(detail).toContainText("Zum Honigsack 35");
  await expect(detail).toContainText("CC BY 4.0"); // diese Messung hat eine eigene Lizenz
  await expect(detail.locator(".detail-hinweise")).toContainText("Radargerät");
  await expect(detail.locator("svg.tg")).toBeVisible();
  const z = await page.evaluate(() => window.__app.daten.stellen
    .filter((s) => s.quelle === "olpe").flatMap((s) => s.zaehlungen));
  expect(z.length).toBeGreaterThan(100);
  expect(z.filter((x) => x.w24).length).toBeGreaterThan(50); // volle Tage
  expect(z.filter((x) => x.lieferung === "olpe:dl-de-by").length).toBeGreaterThan(100);
});

test("Bedienelemente unten links rücken nur neben ein Panel, das sie verdecken würde", async ({ page }) => {
  await page.setViewportSize({ width: 1400, height: 1200 });
  await oeffne(page);
  const knoepfe = page.locator("#bottom-left-ui-container");
  const links = async () => (await knoepfe.boundingBox()).x;
  await page.evaluate(() => {
    const a = window.__app;
    a.oeffneStelle(a.daten.stellen.find((x) => x.quelle === "ravensburg" && x.zaehlungen.length === 1));
  });
  await expect(page.locator("#detail svg.tg")).toBeVisible();
  await expect.poll(links).toBeLessThan(20); // kurzes Panel: Knöpfe bleiben am Rand
  await page.setViewportSize({ width: 1400, height: 700 });
  await expect.poll(links).toBeGreaterThan(380); // Panel reicht bis unten: Knöpfe daneben
  await expect.poll(async () => (await page.locator(".map-settings-toggle").boundingBox()).x).toBeGreaterThan(380);
  await page.locator("#detail [data-schliessen]").click();
  await expect.poll(links).toBeLessThan(20);
});

test("CSV-Export der Zählungen im Filter", async ({ page }) => {
  await oeffne(page, "#t=rad.menge&j=2024-2026");
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  expect(download.suggestedFilename()).toMatch(/^zaehlungen_\d{4}-\d{2}-\d{2}\.csv$/);
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.trim().split("\n");
  expect(zeilen[0]).toContain("quelle;stelle;name");
  expect(zeilen.length).toBeGreaterThan(50);
  const datum = zeilen[0].replace(/^\uFEFF/, "").split(";").indexOf("datum");
  expect(zeilen.slice(1).every((z) => /^202[4-6]-/.test(z.split(";")[datum]))).toBe(true);
});

test("Keine Auswahl der Quellen mehr: alter Link mit q= zeigt alle Quellen", async ({ page }) => {
  await oeffne(page, "#t=kfz.menge&q=ravensburg");
  await expect(page.locator("#quellen-liste")).toHaveCount(0);
  await expect(page.locator("[data-quelle]")).toHaveCount(0);
  const quellen = await page.evaluate(() => [...new Set(window.__app.eintraege().map((e) => e.stelle.quelle))]);
  expect(quellen.length).toBeGreaterThan(5);
  await expect(page).not.toHaveURL(/q=/);
});

test("Steckbrief: Kurzzeitzählungen je Verkehrsart mit Jahren, Zeile stellt Verkehrsart und Zeitraum um, CSV der Kommune", async ({ page }) => {
  const fehler = await oeffne(page, "#j=2010-2015");
  const el = await oeffneKommune(page, "08436064"); // Ravensburg: Kurzzeitzählungen 2023–2026
  const kurz = el.locator('[data-familie-block="k"]');
  await expect(kurz.locator(".kz-stand")).toHaveText("in der Karte");
  await expect(kurz.locator(".kz-zeile .kz-name")).toHaveText(["Kfz", "Schwerverkehr", "Rad", "Fuß"]);
  await expect(kurz.locator(".kz-umfang")).toHaveText(/^\d+ Zählungen an \d+ Stellen$/);
  await expect(kurz.locator('[data-thema="fuss"]')).toHaveAttribute("title", /^Fuß: \d+ Zählungen, 2023–2026 – in der Karte zeigen$/);
  await expect(kurz.locator(".kz-quellen")).toHaveText("Quelle: Ravensburg");
  // ein Kästchen je Jahr der Achse, gefüllt nur in Jahren mit Zählungen
  const kaestchen = await kurz.locator('[data-thema="fuss"] .kz-jahr').evaluateAll((els) => els.map((x) => Boolean(x.getAttribute("style"))));
  expect(kaestchen.slice(-4)).toEqual([true, true, true, true]);
  // Zeile anklicken: Fuß; der Zeitraum 2010–2015 enthält keine Zählung aus Ravensburg – wieder alle Jahre
  await kurz.locator('[data-thema="fuss"]').click();
  await expect(page.locator('#thema-chips [data-thema="fuss"]')).toHaveClass(/is-active/);
  await expect(page).toHaveURL(/t=fuss\.menge/);
  await expect(page).not.toHaveURL(/j=/);
  await expect(kurz.locator('[data-thema="fuss"]')).toHaveClass(/is-aktiv/);
  await expect.poll(() => page.evaluate(() => window.__app.eintraege().filter((e) => e.stelle.quelle === "ravensburg").length)).toBeGreaterThan(50);
  // CSV der Kommune: alle ihre Zählungen (alle Jahre), nur ihre Quelle
  const [download] = await Promise.all([page.waitForEvent("download"), el.locator("[data-csv]").click()]);
  expect(download.suggestedFilename()).toMatch(/^zaehlungen_08436064_\d{4}-\d{2}-\d{2}\.csv$/);
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.trim().split("\n");
  expect(zeilen.length).toBeGreaterThan(100);
  expect(zeilen.slice(1).every((z) => z.startsWith("ravensburg;"))).toBe(true);
  expect(fehler).toEqual([]);
});

test("Steckbrief aus der Seitenleiste einer Zählstelle", async ({ page }) => {
  const fehler = await oeffne(page);
  await klickeStelle(page, (x) => x.quelle === "xanten");
  const link = page.locator("#detail [data-kommune]");
  await expect(link).toHaveText("Xanten: was es dort gibt ›");
  await link.click();
  await expect(page.locator("#detail")).toBeHidden();
  const el = page.locator("#kommune-detail");
  await expect(el.locator(".detail-titel")).toHaveText("Xanten");
  await expect(el.locator('[data-familie-block="k"] .kz-zeile .kz-name')).toHaveText(["Kfz", "Schwerverkehr"]);
  await expect(el.locator('[data-familie-block="d"] .kz-stand')).toHaveText("noch nicht recherchiert");
  await expect(page).toHaveURL(/k=05170052/);
  // Klick in die leere Karte schließt den Steckbrief
  await page.mouse.click(700, 880);
  await expect(el).toBeHidden();
  await expect(page).not.toHaveURL(/k=/);
  expect(fehler).toEqual([]);
});

test("Klick auf eine Kommune öffnet ihren Steckbrief mit Stand und Belegen", async ({ page }) => {
  await oeffne(page);
  const p = await page.evaluate(async () => {
    const k = window.__app.karte;
    await new Promise((ok) => { k.once("idle", ok); k.triggerRepaint(); setTimeout(ok, 5000); });
    const f = k.queryRenderedFeatures({ layers: ["datenlage-kreis"] }).find((x) => x.properties.name === "Rostock");
    return k.project(f.geometry.coordinates);
  });
  await page.mouse.click(p.x, p.y);
  const el = page.locator("#kommune-detail");
  await expect(el).toBeVisible();
  await expect(el.locator(".detail-titel")).toHaveText("Rostock");
  await expect(el.locator('[data-familie-block="k"] .kz-stand')).toHaveText("auf Anfrage herausgegeben");
  // Datenlage, Belege und Anfragetext stehen darunter (zugeklappt, sobald etwas in der Karte ist)
  await klappeDatenlageAuf(el);
  await expect(el.locator('a[href$="fragdenstaat.de/anfrage/verkehrszahlung-14/"]')).toHaveCount(1);
  await expect(el.locator(".anfrage-text")).toHaveValue(/50 jüngsten Knotenpunktzählungen/);
});

test("Steckbrief: Empfehlung und Anfragetext für Dresden", async ({ page }) => {
  await oeffne(page);
  const p = await page.evaluate(async () => {
    const k = window.__app.karte;
    await new Promise((ok) => { k.once("idle", ok); k.triggerRepaint(); setTimeout(ok, 5000); });
    const f = k.queryRenderedFeatures({ layers: ["datenlage-kreis"] }).find((x) => x.properties.name === "Dresden");
    return k.project(f.geometry.coordinates);
  });
  await page.mouse.click(p.x, p.y);
  const el = page.locator("#kommune-detail");
  await expect(el.locator(".detail-titel")).toHaveText("Dresden");
  await klappeDatenlageAuf(el);
  await expect(el).toContainText("Empfehlung");
  await expect(el.locator(".anfrage-text")).toHaveValue(/AF0915\/25/);
  await expect(el.locator(".anfrage-text")).toHaveValue(/Stadt Dresden/);
  await expect(el.locator('a[href^="https://fragdenstaat.de/"]').first()).toBeVisible();
  await expect(el.locator("[data-kopieren]")).toBeVisible();
});

test("Quelle ohne Lizenz: Hinweis, „Entfernen lassen“, nicht im CSV-Export", async ({ page }) => {
  // Ravensburg so, wie eine Quelldatei mit `ohne_lizenz` in manifest.json ankäme
  let ohne = 0; // Lizenzangaben ohne Lizenz im Manifest (Ravensburg und die echten, etwa Tübingen)
  await page.route(/\/data\/manifest\.json$/, async (route) => {
    const antwort = await route.fetch();
    const m = await antwort.json();
    const q = m.quellen.find((x) => x.code === "ravensburg");
    q.lizenzen = q.lizenzen.map((l) => ({
      ...l, lizenz: null, lizenz_url: null,
      ohne_lizenz: { herausgegeben: "als PDF auf der Website der Stadt, ohne Lizenzangabe", geprueft: "2026-11-14" },
    }));
    ohne = m.quellen.flatMap((x) => x.lizenzen).filter((l) => l.ohne_lizenz).length;
    await route.fulfill({ response: antwort, json: m });
  });
  const fehler = await oeffne(page, "#t=kfz.menge");
  await klickeStelle(page, (x) => x.quelle === "ravensburg" && x.zaehlungen.some((z) => z.fenster === "0–24"));
  const detail = page.locator("#detail");
  await expect(detail.locator(".ohne-lizenz")).toHaveText("ohne Lizenz");
  await expect(detail).toContainText("als PDF auf der Website der Stadt, ohne Lizenzangabe (geprüft am 14.11.2026)");
  await expect(detail.getByRole("link", { name: "Entfernen lassen" })).toHaveAttribute("href", /template=daten-entfernen\.yml$/);
  await expect(detail.locator("[data-csv]")).toHaveCount(0);
  await expect(detail).toContainText("ohne Lizenz – kein CSV");
  // „Quellen & Lizenzen“: Ravensburg gekennzeichnet wie die echten Quellen ohne Lizenz, die übrigen
  // mit ihrer Lizenz
  expect(ohne).toBeGreaterThan(0);
  await expect(page.locator("#quellen-text .ohne-lizenz")).toHaveCount(ohne);
  await expect(page.locator("#quellen-text li", { hasText: "Ravensburg" }).locator(".ohne-lizenz")).toHaveCount(1);
  await expect(page.locator('#quellen-text a[href*="dl-de/by-2-0"]').first()).toBeAttached();
  // CSV der Zählungen im Filter: ohne Ravensburg, mit den übrigen Quellen
  await expect(page.locator("#export-csv")).toHaveAttribute("title", "Zählungen im Filter als CSV (nur Quellen mit Lizenz)");
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.replace(/^\ufeff/, "").trim().split("\n");
  expect(zeilen.length).toBeGreaterThan(100);
  expect(zeilen.some((z) => z.startsWith("ravensburg;"))).toBe(false);
  // Steckbrief von Ravensburg: kein CSV der Kommune (ihre einzige Quelle hat keine Lizenz)
  const el = await oeffneKommune(page, "08436064");
  await expect(el.locator('[data-familie-block="k"] .kz-zeile')).toHaveCount(4);
  await expect(el.locator("[data-csv]")).toHaveCount(0);
  expect(fehler).toEqual([]);
});
