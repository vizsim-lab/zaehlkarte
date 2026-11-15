// Familie Dauerzählstellen im Browser – mit kleinen Fixture-Dateien (tests/web/fixtures/dauer/)
// statt der echten Daten, damit der Test nicht vom Release-Asset „dauerzaehlstellen“ abhängt.
// Fixture: zwei Messquerschnitte in Berlin, Juni 2025 (am 3.6. fehlt bei TE001 eine Stunde; Kfz
// und Lkw), dazu Hamburg vom 15.6. bis 10.7.2025: eine Kfz-Zählstelle mit Schwerverkehr und eine
// Rad-Zählstelle, und Ettlingen vom 1.6. bis 10.7.2025: zwei Richtungen eines Sensors am selben
// Punkt (Kfz und Lkw, CC BY-NC). Jüngster Schultag: Berlin 30.6., Hamburg und Ettlingen 10.7.2025.
import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { oeffne, oeffneKommune, zahl } from "./helpers.js";

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
  // Gemeindegrenzen (VG250, Vertrag 5): Quelle, Lizenz, Quellenvermerk mit „BKG“ und Lizenz verlinkt
  const gem = page.locator("#quelle-gemeinden");
  await expect(gem).toContainText("Gemeindegrenzen");
  await expect(gem).toContainText("© BKG (2026) dl-de/by-2-0, Datenquellen:");
  await expect(gem.locator('a[href="https://www.bkg.bund.de"]')).toHaveText("BKG");
  await expect(gem.locator('li a[href="https://www.govdata.de/dl-de/by-2-0"]')).toHaveCount(2);
  await expect(gem.locator('a[href$="datenquellen_vg_nuts.pdf"]')).toHaveCount(1);
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
  expect(zeilen[0]).toBe("quelle;stelle;name;abschnitt;richtung;lon;lat;datum;tagtyp;kfz_tagessumme;kfz_tageswert_quelle;lkw_tagessumme;lkw_tageswert_quelle;sv_tagessumme;sv_tageswert_quelle;rad_tagessumme;rad_tageswert_quelle;lizenz");
  expect(zeilen).toHaveLength(5); // Hamburg beginnt erst am 15.6.
  expect(zeilen[1]).toMatch(/^berlin_viz;berlin_viz:TE001;.*;2025-06-03;Schultag;;;;;;;;;dl-de\/by-2-0$/);
  expect(zeilen[2]).toMatch(/;2025-06-03;Schultag;\d+;;\d+;;;;;;dl-de\/by-2-0$/);
  // die Lizenz steht in jeder Zeile – bei Ettlingen nur nicht kommerziell; Lkw in der Spalte der Klasse
  expect(zeilen[3]).toMatch(/^ettlingen;ettlingen:1263-2;Rastatter Straße;;Richtung Bruchhausen;.*;2025-06-03;Schultag;1142;;64;;;;;;CC BY-NC 4\.0$/);
});

test("CSV am jüngsten Schultag: je Gruppe Tag und Tagessumme jeder Stelle", async ({ page }) => {
  await dauer(page);
  await oeffne(page, "#f=d");
  await expect(page.locator("#export-csv")).toHaveAttribute("title", "Tagessummen am jüngsten Schultag als CSV (nur Quellen mit Lizenz)");
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  expect(download.suggestedFilename()).toBe("dauerzaehlstellen_juengster_schultag_2026-11-12.csv");
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.replace(/^﻿/, "").trim().split("\n");
  expect(zeilen[0]).toBe("quelle;stelle;name;abschnitt;richtung;lon;lat;kfz_juengster_schultag;kfz_tagessumme;kfz_tageswert_quelle;lkw_juengster_schultag;lkw_tagessumme;lkw_tageswert_quelle;sv_juengster_schultag;sv_tagessumme;sv_tageswert_quelle;rad_juengster_schultag;rad_tagessumme;rad_tageswert_quelle;lizenz");
  expect(zeilen).toHaveLength(7); // alle sechs Stellen
  expect(zeilen[1]).toMatch(/^berlin_viz;berlin_viz:TE001;.*;2025-06-30;16430;;2025-06-30;821;;;;;;;;dl-de\/by-2-0$/);
  expect(zeilen[3]).toMatch(/^hamburg_kfz;.*;2025-07-10;8730;;;;;2025-07-10;339;;;;;dl-de\/by-2-0$/);
  expect(zeilen[4]).toMatch(/^hamburg_rad;.*;;;;;;;;;;2025-07-10;2040;;dl-de\/by-2-0$/);
  expect(zeilen[5]).toMatch(/^ettlingen;ettlingen:1263-2;.*;2025-07-10;1142;;2025-07-10;64;;;;;;;;CC BY-NC 4\.0$/);
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

/** Wie `dauer`, aber die Gruppe Rad der Fixture heißt Fuß – so prüft der Test die Gruppe Fuß
 *  (Chip, Stufen, Seitenleiste) an denselben Werten, ohne eigene Fixture-Dateien. */
async function dauerMitFuss(page) {
  const umbenennen = (o) => (o && typeof o === "object" && !Array.isArray(o) && "rad" in o
    ? Object.fromEntries(Object.entries(o).map(([k, v]) => [k === "rad" ? "fuss" : k, v])) : o);
  await page.route(/\/data\/dauer\/.*\.json$/, (route) => {
    const pfad = new URL(route.request().url()).pathname.replace(/^.*\/data\//, "");
    let d;
    try {
      d = JSON.parse(readFileSync(new URL(pfad, FIXTURES), "utf8"));
    } catch {
      return route.fulfill({ status: 404, body: "" });
    }
    if (pfad.endsWith("dauer/index.json")) {
      d.gruppen = d.gruppen.map((g) => (g === "rad" ? "fuss" : g));
      d.gruppen_namen = umbenennen(d.gruppen_namen);
      d.juengster = umbenennen(d.juengster);
      for (const q of d.quellen) {
        q.gruppen = q.gruppen.map((g) => (g === "rad" ? "fuss" : g));
        q.zeitraeume = umbenennen(q.zeitraeume);
      }
    } else if (d.werte) {
      d.werte = umbenennen(d.werte);
    } else if (d.stellen) {
      for (const s of Object.values(d.stellen)) {
        for (const k of ["tage", "n", "stunden"]) s[k] = umbenennen(s[k]);
      }
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(d) });
  });
}

test("Fuß: eigener Chip, eigene Stufen, Seitenleiste mit Fuß", async ({ page }) => {
  await dauerMitFuss(page);
  const fehler = await oeffne(page, "#f=d&t=fuss.menge");
  const fuss = page.locator('#thema-chips [data-thema="fuss"]');
  await expect(fuss).toBeVisible();
  await expect(fuss).toHaveClass(/is-active/);
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toBeHidden(); // keine Quelle mit Rad
  const legende = page.locator("#klassen-legende");
  await expect(legende).toContainText("Fuß, Tagessumme am jüngsten Schultag je Stelle");
  // Stufen für Fuß: Rad- und Fußwege (Bochum) unten, Fußgängerzonen (Augsburg) oben
  await expect(legende).toContainText("5.000 bis unter 15.000");
  await expect(legende).toContainText("ab 15.000");
  expect(await zahl(page.locator("#fc-stellen"))).toBe(1);
  await klickeDauer(page, "hamburg_rad:7433952");
  const detail = page.locator("#dauer-detail");
  await expect(detail.locator(".detail-titel")).toHaveText("Alsterufer");
  await expect(detail).toContainText("Tagessummen Fuß");
  await expect(detail.locator(".detail-kennwerte")).toContainText("Fuß");
  expect(fehler).toEqual([]);
});

/**
 * Fixtures, in denen die Hamburger Rad-Zählstelle nur Tageswerte liefert (wie eine Quelle ohne
 * Stunden): `tageswerte_bis` im Index und in den Details, keine Stunden, 0 gezählte Stunden.
 */
async function dauerMitTageswerten(page) {
  const ID = "hamburg_rad:7433952";
  await page.route(/\/data\/dauer\/.*\.json$/, (route) => {
    const pfad = new URL(route.request().url()).pathname.replace(/^.*\/data\//, "");
    let d;
    try {
      d = JSON.parse(readFileSync(new URL(pfad, FIXTURES), "utf8"));
    } catch {
      return route.fulfill({ status: 404, body: "" });
    }
    if (pfad.endsWith("dauer/index.json")) {
      d.tageswerte_bis = { rad: d.stellen.werte.map((w) => (w[0] === ID ? w[8] : null)) };
      const q = d.quellen.find((x) => x.code === "hamburg_rad");
      q.tageswerte = { rad: [q.von, q.bis] };
    } else if (d.stellen?.[ID]) {
      const s = d.stellen[ID];
      s.tageswerte_bis = { rad: "2025-07-10" };
      s.n.rad = s.n.rad.map(() => 0);
      s.stunden.rad = s.stunden.rad.map(() => null);
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(d) });
  });
}

test("Tageswerte der Quelle: Hinweis in der Legende, im Hover und in der Seitenleiste, eigene CSV-Spalte", async ({ page }) => {
  await dauerMitTageswerten(page);
  const fehler = await oeffne(page, "#f=d&t=rad.menge");
  const legende = page.locator("#klassen-legende");
  await expect(legende).toContainText("Rad, Tagessumme am jüngsten Schultag je Stelle");
  await expect(legende.locator(".dauer-tw")).toContainText("Tageswerte der Quelle: Hamburg");
  const popup = await hoverDauer(page, "hamburg_rad:7433952");
  await expect(popup).toContainText("Rad, Tageswert der Quelle am");
  await expect(popup).toContainText("2.040");
  await klickeDauer(page, "hamburg_rad:7433952");
  const detail = page.locator("#dauer-detail");
  await expect(detail.locator(".detail-titel")).toHaveText("Alsterufer");
  await expect(detail.locator(".dd-tw")).toHaveText("Tageswerte der Quelle (ohne Stunden, Vollständigkeit nicht prüfbar).");
  await expect(detail).toContainText("Tageswerte Rad · 15.06.2025 – 10.07.2025");
  await expect(detail.locator(".dd-juengster")).toContainText("Jüngster Schultag der Stelle mit einem Tageswert der Quelle");
  await expect(detail.locator(".detail-kennwerte thead")).toContainText("Tageswert der Quelle");
  await expect(detail.locator(".detail-kennwerte")).toContainText("2.040");
  await expect(detail).toContainText("Für diesen Tag liefert die Quelle nur einen Tageswert, keine Stunden.");
  await expect(detail).toContainText("Ob jede Stunde gezählt ist, lässt sich nicht prüfen.");
  await expect(detail.locator(".detail-tag .tg-wrap")).toHaveCount(0); // kein Tagesgang ohne Stunden
  await expect(detail.locator("[data-csv-stunden]")).toHaveCount(0);
  // CSV der Tage: der Wert steht als Tageswert der Quelle, nicht als Tagessumme
  const [download] = await Promise.all([page.waitForEvent("download"), detail.locator("[data-csv-tage]").click()]);
  const csv = readFileSync(await download.path(), "utf8").replace(/^\ufeff/, "").split("\n");
  expect(csv[0]).toBe("datum;tagtyp;rad_tagessumme;rad_gezaehlte_stunden;rad_tageswert_quelle");
  expect(csv.find((z) => z.startsWith("2025-07-10;"))).toBe("2025-07-10;Schultag;;0;2040");
  // Kfz: keine Quelle mit Tageswerten – kein Hinweis
  await page.locator('#thema-chips [data-thema="kfz"]').click();
  await expect(legende).toContainText("Kfz, Tagessumme am jüngsten Schultag je Stelle");
  await expect(legende.locator(".dauer-tw")).toHaveCount(0);
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

test("Kommunen stehen in beiden Ansichten, gefärbt nach dem besten Stand beider Zählarten", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#dl=1");
  const gezeigt = () => page.evaluate(async () => {
    const k = window.__app.karte;
    await new Promise((ok) => { k.once("idle", ok); k.triggerRepaint(); setTimeout(ok, 5000); });
    return [...new Set(k.queryRenderedFeatures({ layers: ["datenlage-kreis"] }).map((f) => f.properties.ags))].sort();
  });
  const alle = await page.evaluate(() => window.__app.datenlage.features.map((f) => f.properties.ags).sort());
  const legende = page.locator("#datenlage-legende");
  const summe = async () => (await legende.locator(".count-badge").allTextContents()).map(Number).reduce((a, b) => a + b, 0);
  // Kurzzeitzählungen: alle Kommunen, auch die nur mit Dauerzählstellen (Gießen)
  await expect.poll(gezeigt, { timeout: 20000 }).toEqual(alle);
  expect(alle).toContain("06531005");
  expect(await summe()).toBe(alle.length);
  await expect(legende).toContainText("Zählungen in der Karte");
  expect(await page.locator("#datenlage-tip").getAttribute("data-tip")).toContain("beiden Zählarten");
  await expect(page.locator("#legend")).toContainText("Klick auf eine Kommune zeigt, was es dort gibt");
  // Klasse je Kommune über beide Zählarten: Hamburg und Rostock haben Dauerzählstellen in der Karte
  const klassen = await page.evaluate(() => Object.fromEntries(window.__app.datenlage.features.map((f) => [f.properties.name, f.properties.klasse])));
  expect(klassen).toMatchObject({
    Hamburg: "in_karte", Rostock: "in_karte", Ettlingen: "in_karte", Xanten: "in_karte",
    Kassel: "kandidat", "Gießen": "kandidat", Dresden: "kandidat", "Köln": "sonst",
  });
  const blau = await legende.locator(".legend-item").first().locator(".count-badge").textContent();
  expect(Number(blau)).toBe(Object.values(klassen).filter((k) => k === "in_karte").length);
  // Dauerzählstellen: dieselben Kommunen, dieselbe Legende
  await page.locator('[data-familie="d"]').click();
  await expect(page.locator('[data-familie="d"]')).toHaveClass(/is-active/);
  await expect.poll(gezeigt, { timeout: 20000 }).toEqual(alle);
  expect(await summe()).toBe(alle.length);
  expect(fehler).toEqual([]);
});

test("Steckbrief: beide Zählarten, je Verkehrsart Zeitstrahl und Umfang; eine Zeile zeigt sie in der Karte", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page);
  const el = await oeffneKommune(page, "02000000"); // Hamburg
  await expect(el).toBeVisible();
  await expect(el.locator(".detail-titel")).toHaveText("Hamburg");
  await expect(el.locator(".pop-eyebrow")).toHaveText("Kommune · HH");
  await expect(page).toHaveURL(/k=02000000/);
  // Kurzzeitzählungen: nur Summen offen – keine Zeile; Dauerzählstellen: Kfz, Lkw/Schwerverkehr, Rad
  const kurz = el.locator('[data-familie-block="k"]');
  await expect(kurz.locator(".kz-stand")).toHaveText("nur Summen oder Mittelwerte offen");
  await expect(kurz.locator(".kz-zeile")).toHaveCount(0);
  const lang = el.locator('[data-familie-block="d"]');
  await expect(lang.locator(".kz-stand")).toHaveText("in der Karte");
  await expect(lang.locator(".kz-umfang")).toHaveText("2 Stellen");
  await expect(lang.locator(".kz-zeile .kz-name")).toHaveText(["Kfz", "Lkw/Schwerverkehr", "Rad"]);
  await expect(lang.locator(".kz-zeile .kz-n")).toHaveText(["1", "1", "1"]);
  await expect(lang.locator('[data-thema="rad"]')).toHaveAttribute("title", "Rad: 1 Stellen, 15.06.2025 – 10.07.2025 – in der Karte zeigen");
  await expect(lang.locator(".kz-quellen")).toContainText("Hamburg (Kfz, Wärmebildkameras), Hamburg (Rad, Wärmebildkameras)");
  // eine Achse für alle Zeilen, der Balken liegt darauf
  await expect(el.locator(".kz-achse-skala span").first()).toHaveText("2024");
  await expect(lang.locator('[data-thema="rad"] .kz-balken')).toHaveCount(1);
  // Datenlage zugeklappt (es ist etwas in der Karte), aufgeklappt mit Kontakt und Belegen
  const dl = el.locator(".kz-datenlage");
  await expect(dl).not.toHaveAttribute("open");
  await dl.locator("summary").click();
  await expect(dl).toContainText("Kurzzeitzählungen · nur Summen oder Mittelwerte offen");
  await expect(dl).toContainText("Dauerzählstellen · in der Karte");
  await expect(dl.locator(".detail-abschnitt", { hasText: "Kontakt" })).toBeVisible();
  // Zeile anklicken: Familie und Verkehrsart wechseln, der Steckbrief bleibt und markiert die Zeile
  await lang.locator('[data-thema="rad"]').click();
  await expect(page.locator('[data-familie="d"]').first()).toHaveClass(/is-active/);
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toHaveClass(/is-active/);
  await expect(page).toHaveURL(/f=d&t=rad\.menge/);
  await expect(page).toHaveURL(/k=02000000/);
  await expect(lang.locator('[data-thema="rad"]')).toHaveClass(/is-aktiv/);
  await expect(el).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.__app.dauerEintraege().filter((e) => e.stelle.quelle === "hamburg_rad").length)).toBe(1);
  // ein gewählter Tag außerhalb des Zeitraums der Zeile gilt nicht mehr: je Stelle ihr jüngster Schultag
  await page.evaluate(() => window.__app.tagWechseln("2025-06-03"));
  await expect(page).toHaveURL(/z=2025-06-03/);
  await lang.locator('[data-thema="kfz"]').click();
  await expect(page.locator('#thema-chips [data-thema="kfz"]')).toHaveClass(/is-active/);
  await expect(page).not.toHaveURL(/z=/);
  await expect(lang.locator('[data-thema="kfz"]')).toHaveClass(/is-aktiv/);
  await expect(lang.locator('[data-thema="rad"]')).not.toHaveClass(/is-aktiv/);
  expect(fehler).toEqual([]);
});

test("Steckbrief: Kommune ohne eigene Recherche einer Zählart, nichts in der Karte – Datenlage offen", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page);
  const el = await oeffneKommune(page, "06531005"); // Gießen: nur Dauerzählstellen bekannt, Werte nicht offen
  await expect(el.locator(".detail-kopf .pop-meta")).toHaveText("Noch keine Zählungen in der Karte");
  await expect(el.locator('[data-familie-block="k"] .kz-stand')).toHaveText("noch nicht recherchiert");
  await expect(el.locator('[data-familie-block="d"] .kz-stand')).toHaveText("vorhanden, Werte nicht offen");
  await expect(el.locator(".kz-zeile")).toHaveCount(0);
  await expect(el.locator(".kz-achse")).toHaveCount(0);
  await expect(el.locator(".kz-datenlage")).toHaveAttribute("open", "");
  await expect(el.locator(".anfrage-text")).toHaveCount(0); // einen Anfragetext gibt es nur bei Kurzzeitzählungen
  await expect(el.locator('.kz-datenlage a[href^="http"]').first()).toBeVisible();
  // Kassel: beide Zählarten recherchiert, Kurzzeit ohne Lizenz – Anfragetext, Kontakt, Rechtslage
  await oeffneKommune(page, "06611000");
  await expect(el.locator(".detail-titel")).toHaveText("Kassel");
  await expect(el.locator('[data-familie-block="k"] .kz-stand')).toHaveText("vorhanden, aber ohne Lizenz");
  await expect(el.locator(".anfrage-text")).toBeVisible();
  await expect(el.locator(".detail-abschnitt", { hasText: "Rechtslage im Land" })).toBeVisible();
  await expect(el).toContainText("Induktionsschleifen");
  expect(fehler).toEqual([]);
});

test("Steckbrief aus der Seitenleiste einer Dauerzählstelle; Permalink k= öffnet ihn", async ({ page }) => {
  await dauer(page);
  const fehler = await oeffne(page, "#f=d");
  await klickeDauer(page, "ettlingen:1263-2");
  const detail = page.locator("#dauer-detail");
  const link = detail.locator("[data-kommune]");
  await expect(link).toHaveText("Ettlingen: was es dort gibt ›");
  await link.click();
  await expect(detail).toBeHidden();
  const el = page.locator("#kommune-detail");
  await expect(el.locator(".detail-titel")).toHaveText("Ettlingen");
  await expect(el.locator('[data-familie-block="d"] .kz-zeile .kz-name')).toHaveText(["Kfz", "Lkw/Schwerverkehr"]);
  await expect(el.locator('[data-familie-block="k"] .kz-stand')).toHaveText("nichts offen");
  // Berliner Stellen: keine Kommune der Datenlage in der Fixture – kein Link
  await klickeDauer(page, "berlin_viz:TE001");
  await expect(el).toBeHidden();
  await expect(detail.locator("[data-kommune]")).toHaveCount(0);
  // Permalink: k= öffnet den Steckbrief (eine Stelle hätte Vorrang)
  const neu = await page.context().newPage();
  await dauer(neu);
  const fehler2 = await oeffne(neu, "#k=13003000");
  await expect(neu.locator("#kommune-detail .detail-titel")).toHaveText("Rostock");
  expect([...fehler, ...fehler2]).toEqual([]);
});

test("Quelle ohne Lizenz: Hinweis, „Entfernen lassen“, nicht im CSV-Export", async ({ page }) => {
  await dauer(page);
  // Hamburg (Rad) so, wie eine Quelldatei mit `ohne_lizenz` in dauer/index.json ankäme
  await page.route(/\/data\/dauer\/index\.json$/, (route) => {
    const index = JSON.parse(readFileSync(new URL("dauer/index.json", FIXTURES)));
    const q = index.quellen.find((x) => x.code === "hamburg_rad");
    q.lizenzen = [{
      ...q.lizenzen[0], lizenz: null, lizenz_url: null,
      ohne_lizenz: { herausgegeben: "auf Anfrage herausgegeben, ohne Lizenzangabe", geprueft: "2026-11-14" },
    }];
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(index) });
  });
  const fehler = await oeffne(page, "#f=d&s=hamburg_rad:7433952");
  const detail = page.locator("#dauer-detail");
  await expect(detail.locator(".detail-titel")).toHaveText("Alsterufer");
  await expect(detail.locator(".ohne-lizenz")).toHaveText("ohne Lizenz");
  await expect(detail).toContainText("auf Anfrage herausgegeben, ohne Lizenzangabe (geprüft am 14.11.2026)");
  await expect(detail.getByRole("link", { name: "Entfernen lassen" })).toHaveAttribute("href", /template=daten-entfernen\.yml$/);
  await expect(detail.locator("[data-csv-tage], [data-csv-stunden]")).toHaveCount(0);
  await expect(detail).toContainText("ohne Lizenz – kein CSV");
  // „Quellen & Lizenzen“: nur Hamburg (Rad) ohne Lizenz, Ettlingen weiter mit seiner
  await expect(page.locator("#quellen-dauer .ohne-lizenz")).toHaveCount(1);
  await expect(page.locator('#quellen-dauer a[href*="by-nc/4.0"]')).toHaveCount(1);
  // CSV am jüngsten Schultag: ohne die Stelle aus Hamburg (Rad)
  const [download] = await Promise.all([page.waitForEvent("download"), page.locator("#export-csv").click()]);
  const text = await (await download.createReadStream()).toArray().then((b) => Buffer.concat(b).toString("utf8"));
  const zeilen = text.replace(/^﻿/, "").trim().split("\n");
  expect(zeilen).toHaveLength(6); // fünf von sechs Stellen
  expect(zeilen.some((z) => z.startsWith("hamburg_rad;"))).toBe(false);
  expect(fehler).toEqual([]);
});

test("Steckbrief: Kommune ohne Lizenz mit Werten in der Karte – Zeile, Kontakt bleibt", async ({ page }) => {
  await dauer(page);
  // Osnabrück (Stand ohne_lizenz) so, als stünden seine Werte schon in der Karte (hier: Hamburg Rad)
  const fehler = await oeffne(page, "", {
    datenlage: (dl) => {
      for (const f of dl.features) {
        if (f.properties.ags === "03404000") f.properties.dauer.quellen = ["hamburg_rad"];
        if (f.properties.ags === "02000000") f.properties.dauer.quellen = ["hamburg_kfz"];
      }
      return dl;
    },
  });
  const el = await oeffneKommune(page, "03404000");
  const lang = el.locator('[data-familie-block="d"]');
  await expect(lang.locator(".kz-stand")).toHaveText("vorhanden, aber ohne Lizenz");
  await expect(lang.locator(".kz-stand")).toHaveClass(/kz-stand--karte/);
  await expect(lang.locator(".kz-zeile .kz-name")).toHaveText(["Rad"]);
  // eine Anfrage nach einer Lizenz lohnt weiter: Kontakt und Rechtslage bleiben
  await el.locator(".kz-datenlage summary").click();
  await expect(el.locator(".detail-abschnitt", { hasText: "Kontakt" })).toBeVisible();
  await expect(el.locator(".detail-abschnitt", { hasText: "Rechtslage im Land" })).toBeVisible();
  await lang.locator(".kz-zeile").click();
  await expect(page.locator('#thema-chips [data-thema="rad"]')).toHaveClass(/is-active/);
  expect(fehler).toEqual([]);
});
