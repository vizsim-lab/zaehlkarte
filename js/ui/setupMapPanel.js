// setupMapPanel.js — die Karten-Bedienelemente unten links (aus vizsim/unfallkarte).
//
// Zwei Dinge, die zusammengehören, weil sie dieselbe Ecke des Bildschirms bespielen:
// das einklappbare Panel (Basemap, Relief) und die Zoom-/Kompass-Steuerung darüber.

import { NavigationControl } from "../lib/maplibre.js";
import { setBasemap, setRelief } from "../map/basemapTerrain.js";
import { t } from "../sprache/texte.js";

// Knöpfe, die MapLibre selbst beschriftet (englisch): hier in der Sprache der Oberfläche.
const STEUERUNG = [
  [".maplibregl-ctrl-zoom-in", "steuerung.plus"],
  [".maplibregl-ctrl-zoom-out", "steuerung.minus"],
  [".maplibregl-ctrl-compass", "steuerung.norden"],
  [".maplibregl-ctrl-attrib-button", "steuerung.quellenangabe"],
];

/** Titel der MapLibre-Knöpfe setzen und für den Sprachwechsel markieren (data-i18n-attr). */
export function beschrifteSteuerung() {
  for (const [sel, schluessel] of STEUERUNG) {
    for (const b of document.querySelectorAll(sel)) {
      b.dataset.i18nAttr = `title:${schluessel};aria-label:${schluessel}`;
      b.title = t(schluessel);
      b.setAttribute("aria-label", t(schluessel));
    }
  }
}

/**
 * Bedienelemente unten links neben ein offenes Panel (Stelle, Datenlage) rücken – aber nur,
 * wenn das Panel so weit nach unten reicht, dass es sie verdecken würde; kurze Panels lassen
 * sie am linken Rand. Gemessen wird bei jeder Größenänderung der Panels, der Bedienelemente
 * (Karten-Panel auf/zu) und des Fensters. Die Knöpfe hängen unten fest, ihre Oberkante hängt
 * also nicht davon ab, ob sie gerade gerückt sind.
 */
export function rueckeNebenPanels() {
  const panels = [...document.querySelectorAll(".detail-panel")];
  const stapel = ["#bottom-left-ui-container", ".map-settings-toggle", ".map-settings-panel"]
    .map((sel) => document.querySelector(sel)).filter(Boolean);
  const LUFT = 8;
  const pruefe = () => {
    const knoepfe = stapel.map((el) => el.getBoundingClientRect()).filter((r) => r.height > 0);
    if (!knoepfe.length) return; // Handy mit offener Legende: Knöpfe ausgeblendet
    const oben = Math.min(...knoepfe.map((r) => r.top));
    const imWeg = panels.filter((p) => !p.hidden).map((p) => p.getBoundingClientRect())
      .find((r) => r.height > 0 && r.bottom + LUFT > oben);
    document.body.classList.toggle("steuerung-daneben", Boolean(imWeg));
    if (imWeg) document.documentElement.style.setProperty("--steuerung-links", `${Math.round(imWeg.right + 10)}px`);
  };
  const groesse = new ResizeObserver(pruefe);
  for (const el of [...panels, ...stapel]) groesse.observe(el);
  const sichtbar = new MutationObserver(pruefe);
  for (const p of panels) sichtbar.observe(p, { attributes: true, attributeFilter: ["hidden"] });
  window.addEventListener("resize", pruefe);
  pruefe();
}

/** Panel unten links: Basemap-Auswahl (Positron/OSM/Esri) und Relief. */
export function setupMapPanel(map) {
  const panel = document.getElementById("map-settings-panel");
  const panelToggle = document.getElementById("map-settings-toggle");
  if (panelToggle && panel) {
    panelToggle.addEventListener("click", () => {
      const collapsed = panel.classList.toggle("is-collapsed");
      panelToggle.setAttribute("aria-expanded", String(!collapsed));
    });
  }

  document.querySelectorAll(".basemap-btn[data-basemap]").forEach((btn) => {
    btn.addEventListener("click", () => {
      setBasemap(map, btn.dataset.basemap);
      document.querySelectorAll(".basemap-btn").forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
    });
  });

  document.getElementById("toggle-relief")
    ?.addEventListener("change", (e) => setRelief(map, e.target.checked));
}

/**
 * Zoom-/Kompass-Steuerung in den eigenen Container hängen.
 * Bewusst NICHT über map.addControl: die Steuerung soll in #bottom-left-ui-container
 * sitzen (über dem Panel-Button), nicht in MapLibres eigener Ecke. `nav.onAdd(map)`
 * ist dafür der API-konforme Weg.
 */
export function addNavigationControl(map) {
  const container = document.getElementById("custom-nav-control");
  if (!container) return;

  const nav = new NavigationControl();
  container.appendChild(nav.onAdd(map));

  // Klick auf den Kompass stellt zusätzlich die Neigung zurück (MapLibre setzt nur den
  // Bearing). Der Knopf entsteht erst beim Einhängen -> kurz warten.
  setTimeout(() => {
    container.querySelector(".maplibregl-ctrl-compass")?.addEventListener("click", () => {
      map.setPitch(0);
      map.easeTo({ bearing: 0 });
    });
  }, 100);
}
