// main.js — Start der Zählkarte: Daten laden, Karte und Legende aufbauen, Zustand <-> Karte.
//
// Ablauf: manifest.json + index.json + datenlage.json laden (parallel zur Karte), Zustand aus
// dem Permalink (#…) lesen, Layer anlegen, bei jeder Änderung `zeichne()`. Details einer
// Stelle lädt detail.js erst beim Klick. Test-Hook: window.__app (tests/web/).
import { Map as Karte } from "./js/lib/maplibre.js";
import { ladeStart } from "./js/data/laden.js";
import { ansicht, csv, entpacke, features, standardZustand, zaehleKlassen, zaehlen } from "./js/data/modell.js";
import { addBasemapTerrain } from "./js/map/basemapTerrain.js";
import { bindeHover, fuegeEbenenHinzu, setzeAuswahl, setzeDatenlage, setzeStellen } from "./js/map/ebenen.js";
import { erstelleDetail } from "./js/ui/detail.js";
import { erstelleLegende } from "./js/ui/legende.js";
import { setupMobileLayout } from "./js/ui/mobileLayout.js";
import { addNavigationControl, setupMapPanel } from "./js/ui/setupMapPanel.js";
import { setupTooltips } from "./js/ui/tooltip.js";
import { setupPhotonGeocoder } from "./js/utils/geocoder.js";
import { dekodiere, kodiere } from "./js/utils/permalinkFormat.js";

const START = { center: [10.45, 51.16], zoom: 5.3 };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

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
  const standard = standardZustand(manifest.kriterien, daten.jahre, daten.quellen);
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
      history.replaceState(null, "", `#${hash}`);
    }, 250);
  }
  karte.on("moveend", merkeLink);

  function oeffneStelle(s, zaehlung = null) {
    detail.zeige(s, zaehlung ?? jeStelle.get(s.index)?.z.index ?? null);
    setzeAuswahl(karte, s);
    document.getElementById("datenlage-detail").hidden = true;
    merkeLink();
  }

  function zeigeDatenlage(kommune) {
    const f = datenlage.features.find((x) => x.properties.kommune === kommune);
    if (!f) return;
    const p = f.properties;
    const el = document.getElementById("datenlage-detail");
    const links = p.links.map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.titel)}</a></li>`).join("");
    el.innerHTML = `
      <header class="detail-kopf">
        <div><div class="pop-eyebrow">Datenlage · ${esc(p.land ?? "")}</div>
        <h2 class="detail-titel">${esc(p.kommune)}</h2>
        <div class="pop-meta">${esc(manifest.stand[p.stand] ?? p.stand)}</div></div>
        <button class="detail-zu" type="button" data-schliessen aria-label="Schließen">×</button>
      </header>
      <p class="detail-text">${esc(p.was ?? "")}</p>
      ${p.zaehlungen ? `<p class="detail-text"><button type="button" class="link-knopf" data-hinzoomen>${p.zaehlungen.toLocaleString("de-DE")} Zählungen in der Karte – hinzoomen</button></p>` : ""}
      ${p.recht ? `<div class="detail-abschnitt">Rechtsgrundlage für Anfragen</div><p class="detail-text">${esc(p.recht)}; das Umweltinformationsgesetz gilt überall (keine Rechtsberatung).</p>` : ""}
      ${links ? `<div class="detail-abschnitt">Belege</div><ul class="detail-hinweise">${links}</ul>` : ""}
      <div class="pop-foot"><a href="https://github.com/vizsim-lab/zaehlkarte/issues/new?template=zaehlung-melden.yml" target="_blank" rel="noopener">Neues zu ${esc(p.kommune)} melden →</a></div>`;
    el.hidden = false;
    el.querySelector("[data-schliessen]").onclick = () => { el.hidden = true; };
    el.querySelector("[data-hinzoomen]")?.addEventListener("click", () => {
      karte.flyTo({ center: f.geometry.coordinates, zoom: 11 });
      el.hidden = true;
    });
    detail.schliesse();
  }

  bindeHover(karte, { daten, manifest, gibZustand: () => zustand, gibEintrag: (i) => jeStelle.get(i) });
  karte.on("click", (e) => {
    const treffer = karte.queryRenderedFeatures(e.point, { layers: ["stellen-kreis", "datenlage-kreis"] });
    const s = treffer.find((f) => f.layer.id === "stellen-kreis");
    if (s) { oeffneStelle(daten.stellen[s.properties.i]); return; }
    const d = treffer.find((f) => f.layer.id === "datenlage-kreis");
    if (d) { zeigeDatenlage(d.properties.kommune); return; }
    detail.schliesse();
    document.getElementById("datenlage-detail").hidden = true;
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
  setupMobileLayout();
  zeichne();

  if (aufruf.stelle) {
    const s = daten.stellen.find((x) => x.id === aufruf.stelle);
    if (s) {
      oeffneStelle(s);
      if (!aufruf.karte) karte.jumpTo({ center: [s.lon, s.lat], zoom: 14 });
    }
  }
  window.__app = { karte, daten, zustand, manifest, zeichne, oeffneStelle, detail, eintraege: () => eintraege };
  document.documentElement.dataset.bereit = "1";
}

start().catch((err) => {
  console.error(err);
  zeigeFehler(`Die Karte konnte nicht geladen werden: ${err.message}`);
});
