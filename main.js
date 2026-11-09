// main.js — Start der Zählkarte: Daten laden, Karte und Legende aufbauen, Zustand <-> Karte.
//
// Ablauf: manifest.json + index.json + datenlage.json laden (parallel zur Karte), Zustand aus
// dem Permalink (#…) lesen, Layer anlegen, bei jeder Änderung `zeichne()`. Details einer
// Stelle lädt detail.js erst beim Klick. Test-Hook: window.__app (tests/web/).
// Sprache (DE Standard, EN wählbar): js/sprache/ – nach einem Wechsel wird neu gezeichnet.
import { Map as Karte } from "./js/lib/maplibre.js";
import { ladeStart } from "./js/data/laden.js";
import { ansicht, csv, entpacke, features, standardZustand, zaehleKlassen, zaehlen } from "./js/data/modell.js";
import { addBasemapTerrain } from "./js/map/basemapTerrain.js";
import { bindeHover, fuegeEbenenHinzu, setzeAuswahl, setzeDatenlage, setzeStellen, standText } from "./js/map/ebenen.js";
import { t, zahl } from "./js/sprache/texte.js";
import { bindeUmschalter, ersteSprache, wendeAn } from "./js/sprache/umschalter.js";
import { erstelleDetail } from "./js/ui/detail.js";
import { erstelleLegende } from "./js/ui/legende.js";
import { setupMobileLayout } from "./js/ui/mobileLayout.js";
import { addNavigationControl, beschrifteSteuerung, setupMapPanel } from "./js/ui/setupMapPanel.js";
import { setupTooltips } from "./js/ui/tooltip.js";
import { setupPhotonGeocoder } from "./js/utils/geocoder.js";
import { dekodiere, kodiere } from "./js/utils/permalinkFormat.js";

const START = { center: [10.45, 51.16], zoom: 5.3 };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// Sprache sofort anwenden – vor dem Laden der Daten, damit die Legende nicht erst deutsch steht
ersteSprache();
wendeAn();

function zeigeFehler(text) {
  const el = document.getElementById("fehler");
  el.textContent = text;
  el.hidden = false;
}

async function start() {
  setupTooltips();
  const karte = new Karte({
    container: "map",
    style: "./style.json",
    ...START,
    attributionControl: { compact: true },
    dragRotate: false,
  });
  // Auf den STIL warten, nicht auf "load": "load" kommt erst, wenn auch die Hintergrund-
  // Kacheln da sind – ist OpenFreeMap nicht erreichbar, bliebe die Karte sonst ganz leer.
  const [{ manifest, index, datenlage }] = await Promise.all([
    ladeStart(),
    new Promise((ok) => (karte.isStyleLoaded() ? ok() : karte.once("style.load", ok))),
  ]);

  const daten = entpacke(index);
  const standard = standardZustand(daten.jahre, daten.quellen);
  const aufruf = dekodiere(location.hash, standard, daten.quellen);
  const zustand = aufruf.zustand;
  if (aufruf.karte) karte.jumpTo({ center: [aufruf.karte.lon, aufruf.karte.lat], zoom: aufruf.karte.zoom });

  addBasemapTerrain(karte);
  fuegeEbenenHinzu(karte, datenlage);

  let eintraege = [];
  let jeStelle = new Map();
  const detail = erstelleDetail({
    manifest,
    daten,
    gibZustand: () => zustand,
    beiSchliessen: () => { setzeAuswahl(karte, null); merkeLink(); },
    beiWechsel: () => merkeLink(),
  });
  const legende = erstelleLegende({ manifest, daten, zustand, datenlage, geaendert: () => zeichne() });

  function zeichne() {
    eintraege = ansicht(daten, zustand);
    jeStelle = new Map(eintraege.map((e) => [e.stelle.index, e]));
    setzeStellen(karte, features(eintraege));
    setzeDatenlage(karte, zustand.datenlage);
    legende.zeichneKlassen(zaehleKlassen(eintraege), zaehlen(daten, zustand, eintraege));
    detail.aktualisiere();
    merkeLink();
  }

  let linkTimer = null;
  function merkeLink() {
    clearTimeout(linkTimer);
    linkTimer = setTimeout(() => {
      const c = karte.getCenter();
      const hash = kodiere(zustand, standard, { zoom: karte.getZoom(), lat: c.lat, lon: c.lng }, detail.stelle?.id ?? null);
      history.replaceState(null, "", `#${hash}`); // ?lang= bleibt stehen
    }, 250);
  }
  karte.on("moveend", merkeLink);

  const dlPanel = document.getElementById("datenlage-detail");
  function schliesseDatenlage() {
    dlPanel.hidden = true;
    document.body.classList.remove("detail-offen");
  }

  function oeffneStelle(s, zaehlung = null) {
    detail.zeige(s, zaehlung ?? jeStelle.get(s.index)?.z.index ?? null);
    setzeAuswahl(karte, s);
    dlPanel.hidden = true;
    merkeLink();
  }

  // Datenlage einer Kommune: Oberfläche in der gewählten Sprache, die Recherche-Texte deutsch
  function zeigeDatenlage(kommune, { behalteScroll = false } = {}) {
    const f = datenlage.features.find((x) => x.properties.kommune === kommune);
    if (!f) return;
    const p = f.properties;
    const el = dlPanel;
    const scroll = el.scrollTop;
    const links = p.links.map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.titel)}</a></li>`).join("");
    const k = p.kontakt;
    const kontakt = k ? `<div class="detail-abschnitt">${esc(t("dl.kontakt"))}</div><p class="detail-text">
        ${k.name ? `<span lang="de">${esc(k.name)}</span><br>` : ""}${k.email ? `<a href="mailto:${esc(k.email)}">${esc(k.email)}</a><br>` : ""}
        ${k.fds ? `<a href="${esc(k.fds)}" target="_blank" rel="noopener">${esc(t(k.fds_suche ? "dl.fds_suche" : "dl.fds"))} →</a>` : ""}</p>` : "";
    const a = p.anfrage;
    const deutsch = t("dl.deutsch");
    el.innerHTML = `
      <header class="detail-kopf">
        <div><div class="pop-eyebrow">${esc(t("hover.datenlage", { land: p.land ?? "" }))}</div>
        <h2 class="detail-titel">${esc(p.kommune)}</h2>
        <div class="pop-meta">${esc(standText(manifest, p.stand))}</div></div>
        <button class="detail-zu" type="button" data-schliessen aria-label="${esc(t("schliessen"))}">×</button>
      </header>
      ${deutsch ? `<p class="pop-meta dl-sprache">${esc(deutsch)}</p>` : ""}
      ${p.zaehlungen ? `<p class="detail-text" lang="de">${esc(p.was ?? "")}</p><p class="detail-text"><button type="button" class="link-knopf" data-hinzoomen>${esc(t("dl.in_karte", { n: zahl(p.zaehlungen) }))}</button></p>` : ""}
      ${p.situation ? `<div class="detail-abschnitt">${esc(t("dl.lage"))}</div><p class="detail-text" lang="de">${esc(p.situation)}</p>` : (p.zaehlungen ? "" : `<p class="detail-text" lang="de">${esc(p.was ?? "")}</p>`)}
      ${p.empfehlung ? `<div class="detail-abschnitt">${esc(t("dl.empfehlung"))}</div><p class="detail-text" lang="de">${esc(p.empfehlung)}</p>` : ""}
      ${p.weg ? `<p class="detail-text"><span class="pop-chip" lang="de">${esc(p.weg)}</span></p>` : ""}
      ${kontakt}
      ${a ? `<div class="detail-abschnitt">${esc(t("dl.anfrage"))}</div>
        <p class="pop-meta">${esc(t("dl.anfrage_hinweis", { betreff: a.betreff }))}</p>
        <textarea class="anfrage-text" readonly rows="9" lang="de" aria-label="${esc(t("dl.anfrage"))}">${esc(a.text)}</textarea>
        <p class="detail-links"><button type="button" class="link-knopf" data-kopieren>${esc(t("dl.kopieren"))}</button>
        ${k?.fds ? `<a href="${esc(k.fds)}" target="_blank" rel="noopener">${esc(t("dl.stellen"))}</a>` : ""}</p>` : ""}
      ${p.recht ? `<div class="detail-abschnitt">${esc(t("dl.recht"))}</div><p class="detail-text"><span lang="de">${esc(p.recht)}.</span> ${esc(t("dl.keine_beratung"))}</p>` : ""}
      ${links ? `<div class="detail-abschnitt">${esc(t("dl.belege"))}</div><ul class="detail-hinweise" lang="de">${links}</ul>` : ""}
      <div class="pop-foot"><a href="https://github.com/vizsim-lab/zaehlkarte/issues/new?template=zaehlung-melden.yml" target="_blank" rel="noopener">${esc(t("dl.melden", { kommune: p.kommune }))}</a></div>`;
    el.hidden = false;
    el.scrollTop = behalteScroll ? scroll : 0;
    el.querySelector("[data-schliessen]").onclick = schliesseDatenlage;
    el.querySelector("[data-hinzoomen]")?.addEventListener("click", () => {
      karte.flyTo({ center: f.geometry.coordinates, zoom: 11 });
      el.hidden = true;
    });
    el.querySelector("[data-kopieren]")?.addEventListener("click", async (e) => {
      const feld = el.querySelector(".anfrage-text");
      try {
        await navigator.clipboard.writeText(feld.value);
      } catch {
        feld.select();
        document.execCommand("copy");
      }
      e.target.textContent = t("dl.kopiert");
    });
    detail.schliesse();
    document.body.classList.add("detail-offen"); // Bedienelemente unten links rücken daneben
    el.dataset.kommune = kommune;
  }

  const popup = bindeHover(karte, { daten, manifest, gibZustand: () => zustand, gibEintrag: (i) => jeStelle.get(i) });
  karte.on("click", (e) => {
    const treffer = karte.queryRenderedFeatures(e.point, { layers: ["stellen-kreis", "datenlage-kreis"] });
    const s = treffer.find((f) => f.layer.id === "stellen-kreis");
    if (s) { oeffneStelle(daten.stellen[s.properties.i]); return; }
    const d = treffer.find((f) => f.layer.id === "datenlage-kreis");
    if (d) { zeigeDatenlage(d.properties.kommune); return; }
    detail.schliesse();
    schliesseDatenlage();
  });

  document.getElementById("export-csv").addEventListener("click", () => {
    const lizenzVon = (quelle, lieferung) => {
      const q = manifest.quellen.find((x) => x.code === quelle);
      const code = lieferung ? lieferung.split(":")[1] : quelle;
      return (q.lizenzen.find((l) => l.code === code) ?? q.lizenzen[0])?.lizenz ?? "";
    };
    const blob = new Blob([csv(daten, zustand, lizenzVon)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `zaehlungen_${manifest.erzeugt}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  setupPhotonGeocoder(karte);
  setupMapPanel(karte);
  addNavigationControl(karte);
  beschrifteSteuerung();
  setupMobileLayout();
  zeichne();

  // Sprachwechsel: statische Texte setzt der Umschalter, hier alles Erzeugte neu zeichnen
  bindeUmschalter(() => {
    popup.remove();
    beschrifteSteuerung(); // Kompass entsteht erst kurz nach dem Einhängen
    legende.uebersetze();
    zeichne();
    if (!dlPanel.hidden && dlPanel.dataset.kommune) zeigeDatenlage(dlPanel.dataset.kommune, { behalteScroll: true });
  });

  if (aufruf.stelle) {
    const s = daten.stellen.find((x) => x.id === aufruf.stelle);
    if (s) {
      oeffneStelle(s);
      if (!aufruf.karte) karte.jumpTo({ center: [s.lon, s.lat], zoom: 14 });
    }
  }
  window.__app = { karte, daten, zustand, manifest, zeichne, oeffneStelle, zeigeDatenlage, detail, eintraege: () => eintraege };
  document.documentElement.dataset.bereit = "1";
}

start().catch((err) => {
  console.error(err);
  zeigeFehler(t("fehler.laden", { fehler: err.message }));
});
