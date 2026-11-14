// Familie Dauerzählstellen im Browser – mit kleinen Fixture-Dateien (tests/web/fixtures/dauer/)
// statt der echten Daten, damit der Test nicht vom Release-Asset „dauerzaehlstellen“ abhängt.
// Fixture: zwei Messquerschnitte in Berlin, Juni 2025 (am 3.6. fehlt bei TE001 eine Stunde; Kfz
// und Lkw), dazu Hamburg vom 15.6. bis 10.7.2025: eine Kfz-Zählstelle mit Schwerverkehr und eine
// Rad-Zählstelle, und Ettlingen vom 1.6. bis 10.7.2025: zwei Richtungen eines Sensors am selben
// Punkt (Kfz und Lkw, CC BY-NC). Jüngster Schultag: Berlin 30.6., Hamburg und Ettlingen 10.7.2025.
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

/** Bildschirmpunkt einer Dauerzählstelle (Karte dorthin, bis sie steht). */
async function punktVon(page, id) {
  return page.evaluate(async (sid) => {
    const app = window.__app;
    const s = app.dauer().jeId.get(sid);
    app.karte.jumpTo({ center: [s.lon, s.lat], zoom: 18 });
    await new Promise((ok) => app.karte.once("idle", ok));
    return app.karte.project([s.lon, s.lat]);
  }, id);
}

async function klickeDauer(page, id) {
  const p = await punktVon(page, id);
  await page.mouse.click(p.x, p.y);
}

/** Hover-Popup über einer Dauerzählstelle. */
async function hoverDauer(page, id) {
  const p = await punktVon(page, id);
  await page.mouse.move(p.x + 1, p.y + 1);
  await page.mouse.move(p.x, p.y);
  const popup = page.locator(".maplibregl-popup");
  await expect(popup).toBeVisible();
  return popup;
}

test("Umschalter lädt die Dauerzählstellen: alle Quellen am jüngsten Schultag, dann ein Tag für alle", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page);
  const knopf = page.locator('[data-familie="d"]');
  await expect(knopf).toBeEnabled();
  await knopf.click();
  await expect(knopf).toHaveClass(/is-active/);
  await expect(page).toHaveURL(/f=d/);
  await expect(page).not.toHaveURL(/z=/);
  // Standard: je Stelle ihr jüngster vollständig gezählter Schultag – Berlin, Hamburg und Ettlingen zugleich
  await expect(page.locator("#dauer-tag")).toBeVisible();
  await expect(page.locator('#dauer-modus [data-dmodus="j"]')).toHaveClass(/is-active/);
  await expect(page.locator("#dauer-tag-einzeln")).toBeHidden();
  await expect(page.locator("#klassen-legende")).toContainText("Kfz, Tagessumme am jüngsten Schultag je Stelle");
  const quellen = page.locator("#dauer-quellen");
  await expect(quellen).toContainText("Gezeigte Tage je Quelle");
  await expect(quellen).toContainText("Berlin: 30.06.2025");
  await expect(quellen).toContainText("Hamburg: 10.07.2025");
  await expect(quellen).toContainText("Ettlingen: 10.07.2025");
  // Quellen & Lizenzen: jede Familie mit ihrem eigenen Stand (die Fixture ist vom 12.11.2026)
  await expect(page.locator("#quellen-dauer")).toContainText("Stand: 12.11.2026 (jede Woche neu gebaut)");
  await expect(page.locator("#quellen-text")).toContainText(/Stand der Kurzzeitzählungen: \d\d\.\d\d\.\d{4}\./);
  await expect(page.locator('[data-section="filter"]')).toBeHidden();
  await expect(page.locator("#art-wahl")).toBeHidden();
  // Lkw (Berlin, Ettlingen) und Schwerverkehr (Hamburg) unter einem Chip, kein eigener Lkw-Chip
  await expect(page.locator('#thema-chips [data-thema="lkw"]')).toHaveCount(0);
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveText("Lkw/Schwerverkehr");
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toBeVisible();
  await expect(page.locator('#thema-chips [data-thema="fuss"]')).toBeHidden();
  await expect(page.locator("#fc-zaehlungen-name")).toHaveText("vollständig");
  expect(await zahl(page.locator("#fc-stellen"))).toBe(5); // Berlin zwei, Hamburg eine (Kfz), Ettlingen zwei
  expect(await zahl(page.locator("#fc-zaehlungen"))).toBe(5);
  // querySourceFeatures liefert je Kachel – Stellen zählen, nicht Treffer
  await expect.poll(() => page.evaluate(() => new Set(window.__app.karte.querySourceFeatures("dauer").map((f) => f.properties.i)).size)).toBe(5);
  expect(await page.evaluate(() => window.__app.karte.getLayoutProperty("stellen-kreis", "visibility"))).toBe("none");

  // Tag wählen: alle am Standardtag der Daten
  await page.locator('#dauer-modus [data-dmodus="t"]').click();
  await expect(page).toHaveURL(/z=2025-06-26/);
  await expect(page.locator("#dauer-tag-einzeln")).toBeVisible();
  await expect(page.locator("#dauer-tag-wert")).toHaveText(/^Do\.? 26\.06\.2025 · Schultag$/);
  await expect(page.locator("#klassen-legende")).toContainText("Kfz, Tagessumme am 26.06.2025");

  // ein Tag zurück, dann der 3.6.: TE001 dort nicht vollständig gezählt -> hohl, kein Wert
  await page.locator('[data-schritt="-1"]').click();
  await expect(page).toHaveURL(/z=2025-06-25/);
  await page.locator("#dauer-datum").fill("2025-06-03");
  await expect(page).toHaveURL(/z=2025-06-03/);
  await expect(page.locator("#fc-zaehlungen")).toHaveText("3"); // TE002 und die beiden in Ettlingen
  const nicht = page.locator("#klassen-legende .legend-item").last();
  await expect(nicht).toContainText("an dem Tag nicht vollständig gezählt");
  await expect(nicht.locator(".count-badge")).toHaveText("1");

  // zurück zum jüngsten Schultag: z weg, wieder alle fünf
  await page.locator('#dauer-modus [data-dmodus="j"]').click();
  await expect(page).not.toHaveURL(/z=/);
  await expect(page.locator("#dauer-tag-einzeln")).toBeHidden();
  await expect(page.locator("#fc-zaehlungen")).toHaveText("5");

  // zurück zu den Kurzzeitzählungen: Filter und Kennzahl wieder da, f=d weg
  await page.locator('[data-familie="k"]').click();
  await expect(page.locator('[data-section="filter"]')).toBeVisible();
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveText("Schwerverkehr");
  await expect(page).not.toHaveURL(/f=d/);
  expect(await zahl(page.locator("#fc-stellen"))).toBeGreaterThan(1000);
  expect(fehler).toEqual([]);
});

test("Jüngster Schultag: Hover und Seitenleiste nennen den Tag der Stelle, Klick in die Reihe wählt einen Tag", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&s=berlin_viz:TE001");
  const detail = page.locator("#dauer-detail");
  await expect(detail.locator(".detail-titel")).toHaveText("Clayallee");
  await expect(detail.locator(".detail-tag .detail-abschnitt")).toHaveText(/^Mo\.? 30\.06\.2025 · Schultag$/);
  await expect(detail.locator(".dd-juengster")).toContainText("Jüngster vollständig gezählter Schultag");
  await expect(detail.locator(".detail-kennwerte")).toContainText("16.430");
  await detail.locator("[data-schliessen]").click();

  // Hamburg: anderer Tag als Berlin – das Popup nennt ihn
  const popup = await hoverDauer(page, "hamburg_kfz:0248931");
  await expect(popup).toContainText("8.730");
  await expect(popup).toContainText(/Kfz, Tagessumme am Do\.? 10\.07\.2025/);

  // Sprung aus der Liste je Quelle: Berlins jüngster Schultag für alle
  await page.locator('#dauer-quellen [data-sprung="2025-06-30"]').click();
  await expect(page).toHaveURL(/z=2025-06-30/);
  await expect(page.locator('#dauer-modus [data-dmodus="t"]')).toHaveClass(/is-active/);
  await expect(page.locator("#dauer-tag-wert")).toHaveText(/^Mo\.? 30\.06\.2025 · Schultag$/);
  await expect(page.locator("#dauer-quellen")).toBeHidden(); // an dem Tag zählen alle drei
  await expect(page.locator("#fc-zaehlungen")).toHaveText("5");

  // zurück zum Standard, Stelle öffnen und in die Tagesreihe klicken: ein Tag für alle
  await page.locator('#dauer-modus [data-dmodus="j"]').click();
  await klickeDauer(page, "ettlingen:1263-3");
  await expect(detail.locator(".detail-tag .detail-abschnitt")).toHaveText(/^Do\.? 10\.07\.2025 · Schultag$/);
  const reihe = detail.locator("svg.tr");
  const box = await reihe.boundingBox();
  await reihe.click({ position: { x: box.width * 0.3, y: box.height / 2 } });
  await expect(page).toHaveURL(/z=2025-06-\d\d/);
  await expect(detail.locator(".dd-juengster")).toHaveCount(0);
  expect(fehler).toEqual([]);
});

test("Permalink und Klick: Detail mit Tagesreihe, Tagesgang und unvollständigem Tag", async ({ page }) => {
  await dauer(page);
  // alter Link mit dem früheren Lkw-Chip: gilt als Lkw/Schwerverkehr
  const fehler = await oeffne(page, "#f=d&t=lkw.menge&z=2025-06-02&s=berlin_viz:TE001");
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveClass(/is-active/);
  await expect(page).toHaveURL(/t=sv\.menge/);
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
  // die Lizenz steht in jeder Zeile – bei Ettlingen nur nicht kommerziell; Lkw in der Spalte der Klasse
  expect(zeilen[3]).toMatch(/^ettlingen;ettlingen:1263-2;Rastatter Straße;;Richtung Bruchhausen;.*;2025-06-03;Schultag;1142;64;;;CC BY-NC 4\.0$/);
});

test("CSV am jüngsten Schultag: je Gruppe Tag und Tagessumme jeder Stelle", async ({ page }) => {
  await dauer(page);
  await oeffne(page, "#f=d");
  await expect(page.locator("#export-csv")).toHaveAttribute("title", "Tagessummen am jüngsten Schultag als CSV");
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  expect(download.suggestedFilename()).toBe("dauerzaehlstellen_juengster_schultag_2026-11-12.csv");
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.replace(/^﻿/, "").trim().split("\n");
  expect(zeilen[0]).toBe("quelle;stelle;name;abschnitt;richtung;lon;lat;kfz_juengster_schultag;kfz_tagessumme;lkw_juengster_schultag;lkw_tagessumme;sv_juengster_schultag;sv_tagessumme;rad_juengster_schultag;rad_tagessumme;lizenz");
  expect(zeilen).toHaveLength(7); // alle sechs Stellen
  expect(zeilen[1]).toMatch(/^berlin_viz;berlin_viz:TE001;.*;2025-06-30;16430;2025-06-30;821;;;;;dl-de\/by-2-0$/);
  expect(zeilen[3]).toMatch(/^hamburg_kfz;.*;2025-07-10;8730;;;2025-07-10;339;;;dl-de\/by-2-0$/);
  expect(zeilen[4]).toMatch(/^hamburg_rad;.*;;;;;;;2025-07-10;2040;dl-de\/by-2-0$/);
  expect(zeilen[5]).toMatch(/^ettlingen;ettlingen:1263-2;.*;2025-07-10;1142;2025-07-10;64;;;;;CC BY-NC 4\.0$/);
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
  await expect(page.locator('#dauer-modus [data-dmodus="j"]')).toHaveText("latest school day");
  await expect(page.locator("#klassen-legende")).toContainText("Motor vehicles, daily total on each site's latest school day");
  await expect(page.locator("#dauer-quellen")).toContainText("Days shown per source");
  await expect(page.locator("#quellen-dauer")).toContainText("As of 12 Nov 2026 (rebuilt every week)");
  await expect(page.locator("#fc-zaehlungen-name")).toHaveText("complete");
  await page.locator('#dauer-modus [data-dmodus="t"]').click();
  await expect(page.locator("#klassen-legende")).toContainText("Motor vehicles, daily total on 26 Jun 2025");
  await expect(page.locator("#dauer-tag-wert")).toHaveText("Thu 26 Jun 2025 · School day");
  await page.locator('#thema-chips [data-thema="sv"]').click();
  await expect(page.locator('#thema-chips [data-thema="sv"]')).toHaveText("Trucks/heavy vehicles");
  await expect(page.locator("#klassen-legende")).toContainText("Trucks (detector): Berlin, Ettlingen · Heavy vehicles (detector): Hamburg");
});

test("Mehrere Quellen: Lkw/Schwerverkehr je Stelle in ihrer Klasse, Rad aus Hamburg, Sprung zu Berlin", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&z=2025-07-05");
  await expect(page.locator("#dauer-tag-wert")).toHaveText(/^Sa\.? 05\.07\.2025 · Wochenende$/);
  // Berlin zählt Kfz, hat am 5.7. aber keine Werte mehr: Hinweis mit Sprung zu seinem Standardtag
  const hinweis = page.locator("#dauer-quellen");
  await expect(hinweis).toBeVisible();
  await expect(hinweis).toContainText("Berlin (Verkehrsdetektion): Werte vom 01.06.2025 bis 30.06.2025");
  expect(await zahl(page.locator("#fc-stellen"))).toBe(3); // Hamburg eine, Ettlingen zwei

  // ein Chip für beide Klassen: Hamburg zeigt Schwerverkehr, Ettlingen Lkw – nie zusammengezählt
  await page.locator('#thema-chips [data-thema="sv"]').click();
  await expect(page).toHaveURL(/t=sv\.menge/);
  const legende = page.locator("#klassen-legende");
  await expect(legende).toContainText("Lkw/Schwerverkehr, Tagessumme am 05.07.2025");
  await expect(legende.locator(".dauer-klassen")).toHaveText(/Je Stelle die Klasse ihres Detektors – Lkw \(Detektor\): Berlin, Ettlingen · Schwerverkehr \(Detektor\): Hamburg/);
  await expect(hinweis).toContainText("Berlin (Verkehrsdetektion)"); // Berlins Lkw enden am 30.6.
  expect(await zahl(page.locator("#fc-stellen"))).toBe(3); // Hamburg (Schwerverkehr), Ettlingen zwei (Lkw)
  const hh = await hoverDauer(page, "hamburg_kfz:0248931");
  await expect(hh).toContainText("Schwerverkehr (Detektor), Tagessumme am Sa");
  await expect(hh).toContainText("339");
  const ett = await hoverDauer(page, "ettlingen:1263-3"); // beide Richtungen am selben Punkt
  await expect(ett).toContainText("Lkw (Detektor), Tagessumme am Sa");
  await expect(ett.locator(".pop-hero")).toHaveText(/^(64|118)$/);
  await klickeDauer(page, "hamburg_kfz:0248931");
  await expect(page.locator("#dauer-detail")).toContainText("Tagessummen Schwerverkehr (Detektor)");
  await page.locator("#dauer-detail [data-schliessen]").click();

  await page.locator('#thema-chips [data-thema="rad"]').click();
  await expect(page).toHaveURL(/t=rad\.menge/);
  // Rad-Klassen nach den Quintilen aller Rad-Stellen (Hamburg, Berlin, Münster, Aachen, München, BW)
  await expect(legende).toContainText("1.300 bis unter 2.500");
  await expect(legende).toContainText("ab 2.500");
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

test("Datenlage: Kommunen nur mit Dauerzählstellen stehen nur bei den Dauerzählstellen", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#dl=1");
  const gezeigt = () => page.evaluate(async () => {
    const k = window.__app.karte;
    await new Promise((ok) => { k.once("idle", ok); k.triggerRepaint(); setTimeout(ok, 5000); });
    return [...new Set(k.queryRenderedFeatures({ layers: ["datenlage-kreis"] }).map((f) => f.properties.kommune))].sort();
  });
  const { mitStand, nurDauer } = await page.evaluate(() => {
    const fs = window.__app.datenlage.features.map((f) => f.properties);
    return {
      mitStand: fs.filter((p) => p.stand).map((p) => p.kommune).sort(),
      nurDauer: fs.filter((p) => !p.stand).map((p) => ({ kommune: p.kommune, land: p.land, dauer: !!p.dauer })),
    };
  });
  expect(nurDauer.length).toBeGreaterThan(0);
  expect(nurDauer.every((x) => x.dauer)).toBe(true);
  // Kurzzeitzählungen: nur Kommunen mit deren Stand, die Zähler der Legende passen dazu
  expect(await gezeigt()).toEqual(mitStand);
  const zaehler = async () => (await page.locator("#datenlage-legende .count-badge").allTextContents()).map(Number).reduce((a, b) => a + b, 0);
  expect(await zaehler()).toBe(mitStand.length);
  // Dauerzählstellen: dort stehen sie, mit ihrem Stand und ohne Anfragetext
  await page.locator('[data-familie="d"]').click();
  const { kommune, land } = nurDauer[0];
  expect(await gezeigt()).toContain(kommune);
  await page.evaluate((k) => window.__app.zeigeDatenlage(k), kommune);
  const el = page.locator("#datenlage-detail");
  await expect(el.locator(".pop-eyebrow")).toHaveText(`Datenlage Dauerzählstellen · ${land}`);
  await expect(el.locator(".anfrage-text")).toHaveCount(0);
  // zurück zu den Kurzzeitzählungen: dort hat die Kommune keinen Eintrag – die Seitenleiste schließt
  await page.locator('[data-familie="k"]').click();
  await expect(el).toBeHidden();
  expect(fehler).toEqual([]);
});

test("Datenlage: „hinzoomen“ wechselt auf die Verkehrsart, die die Kommune zählt", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&t=rad.menge&dl=1");
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toHaveClass(/is-active/);
  // Ettlingen zählt Kfz und Lkw, kein Rad: die Karte wechselt auf Kfz (Standard, ohne t= im Link)
  await page.evaluate(() => window.__app.zeigeDatenlage("Ettlingen"));
  await page.locator("#datenlage-detail [data-hinzoomen]").click();
  await expect(page.locator('#thema-chips [data-thema="kfz"]')).toHaveClass(/is-active/);
  await expect(page).not.toHaveURL(/t=rad/);
  await expect.poll(() => page.evaluate(() => window.__app.dauerEintraege().filter((e) => e.stelle.quelle === "ettlingen").length)).toBeGreaterThan(0);
  // Hamburg zählt beides: die gewählte Verkehrsart bleibt
  await page.locator('#thema-chips [data-thema="rad"]').click();
  await page.evaluate(() => window.__app.zeigeDatenlage("Hamburg"));
  await page.locator("#datenlage-detail [data-hinzoomen]").click();
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toHaveClass(/is-active/);
  await expect(page).toHaveURL(/t=rad\.menge/);
  expect(fehler).toEqual([]);
});

test("Datenlage folgt der Familie: eigener Stand je Kommune für Dauerzählstellen", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d&dl=1");
  await expect(page.locator("#toggle-datenlage")).toBeChecked();
  const legende = page.locator("#datenlage-legende");
  await expect(legende).toContainText("vorhanden, Werte nicht offen");
  await expect(legende).not.toContainText("nur Summen, Karten, automatisch oder abgelehnt");
  expect(await page.locator("#datenlage-tip").getAttribute("data-tip")).toContain("Dauerzählstellen");
  // die Ebene zeigt nur Kommunen mit einem Stand der Dauerzählstellen, die Zähler passen dazu
  const n = await page.evaluate(async () => {
    const k = window.__app.karte;
    await new Promise((ok) => { k.once("idle", ok); k.triggerRepaint(); setTimeout(ok, 5000); });
    const gezeigt = new Set(k.queryRenderedFeatures({ layers: ["datenlage-kreis"] }).map((f) => f.properties.kommune));
    const mit = window.__app.datenlage.features.filter((f) => f.properties.dauer).map((f) => f.properties.kommune);
    return { gezeigt: [...gezeigt].sort(), mit: mit.sort() };
  });
  expect(n.gezeigt).toEqual(n.mit);
  expect(n.mit).toContain("Ettlingen");
  const summe = (await legende.locator(".count-badge").allTextContents()).map(Number).reduce((a, b) => a + b, 0);
  expect(summe).toBe(n.mit.length);

  // Ettlingen: in der Karte (Kurzzeitzählungen: nur automatische Zählungen offen)
  await page.evaluate(() => window.__app.zeigeDatenlage("Ettlingen"));
  const el = page.locator("#datenlage-detail");
  await expect(el.locator(".pop-eyebrow")).toHaveText("Datenlage Dauerzählstellen · BW");
  await expect(el.locator(".pop-meta").first()).toHaveText("in der Karte");
  await expect(el).toContainText("automatische Zählstellen an sechs Straßen");
  await expect(el.locator("[data-hinzoomen]")).toHaveText("Dauerzählstellen in der Karte – hinzoomen");
  await expect(el.locator('a[href*="opendata.readi.de"]')).toHaveCount(1);
  await expect(el.locator(".anfrage-text")).toHaveCount(0);
  // Familie wechseln: dieselbe Kommune mit dem Stand der Kurzzeitzählungen
  await page.locator('[data-familie="k"]').click();
  await expect(el).toBeVisible();
  await expect(el.locator(".pop-eyebrow")).toHaveText("Datenlage · BW");
  await expect(el.locator(".pop-meta").first()).toHaveText("automatische Zählungen offen");
  await expect(page.locator("#datenlage-legende")).toContainText("nur Summen, Karten, automatisch oder abgelehnt");

  // Kassel bei den Dauerzählstellen: Werte nicht offen – Kontakt und Belege, aber kein Anfragetext
  await page.locator('[data-familie="d"]').click();
  await page.evaluate(() => window.__app.zeigeDatenlage("Kassel"));
  await expect(el.locator(".pop-meta").first()).toHaveText("vorhanden, Werte nicht offen");
  await expect(el).toContainText("Induktionsschleifen");
  await expect(el.locator('a[href^="https://fragdenstaat.de/"]').first()).toBeVisible();
  await expect(el.locator(".anfrage-text")).toHaveCount(0);
  // eine Kommune ohne Stand der Dauerzählstellen schließt sich beim Wechsel zu ihnen
  // (Xanten: nur Kurzzeitzählungen; Rostock hat seit den Radmonitoren einen Stand)
  await page.locator('[data-familie="k"]').click();
  await page.evaluate(() => window.__app.zeigeDatenlage("Xanten"));
  await page.locator('[data-familie="d"]').click();
  await expect(el).toBeHidden();
  expect(fehler).toEqual([]);
});
