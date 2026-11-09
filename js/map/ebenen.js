// ebenen.js — Quellen und Layer der Zählkarte: Zählstellen, gewählte Stelle, Datenlage.
//
// Farbe, Rand, Radius und Zeichenreihenfolge jedes Punkts rechnet js/data/modell.js
// (features) – der Stil liest sie nur aus (["get", …]). So bleibt die Logik browserlos testbar.
import { Popup } from "../lib/maplibre.js";
import { TAGE, formatiere, kennzahlText } from "../data/modell.js";
import { datum, lokal, t, zahl } from "../sprache/texte.js";

const LEER = { type: "FeatureCollection", features: [] };
export const DATENLAGE_FARBEN = {
  in_karte: "#2a78d6",
  offen: "#1baf7a",
  geliefert: "#1baf7a",
  kandidat: "#eb6834",
};
export const DATENLAGE_GRAU = "#9ca3af";
const klasse = (id, farbe, stand) => ({ id, farbe, stand, get name() { return t(`datenlage.klasse.${id}`); } });
export const DATENLAGE_KLASSEN = [
  klasse("in_karte", "#2a78d6", ["in_karte"]),
  klasse("offen", "#1baf7a", ["offen", "geliefert"]),
  klasse("kandidat", "#eb6834", ["kandidat"]),
  klasse("sonst", DATENLAGE_GRAU, ["aggregiert", "nur_karte", "automatisch", "abgelehnt"]),
];

/** Bezeichnung eines Datenlage-Stands in der gewählten Sprache (manifest.stand bzw. stand_en). */
export const standText = (manifest, code) => lokal(manifest, "stand")?.[code] ?? manifest.stand?.[code] ?? code;

export function fuegeEbenenHinzu(map, datenlage) {
  map.addSource("stellen", { type: "geojson", data: LEER });
  map.addSource("auswahl", { type: "geojson", data: LEER });
  map.addSource("datenlage", { type: "geojson", data: datenlage });

  map.addLayer({
    id: "stellen-kreis",
    type: "circle",
    source: "stellen",
    layout: { "circle-sort-key": ["get", "o"] },
    paint: {
      "circle-color": ["get", "c"],
      "circle-radius": [
        "interpolate", ["exponential", 1.5], ["zoom"],
        5, ["*", ["get", "r"], 0.4],
        10, ["*", ["get", "r"], 0.9],
        13, ["*", ["get", "r"], 1.5],
        16, ["*", ["get", "r"], 2.6],
      ],
      "circle-stroke-color": ["get", "sc"],
      "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 5, 0.2, 11, 0.8, 14, 1.2],
    },
  });
  map.addLayer({
    id: "auswahl-ring",
    type: "circle",
    source: "auswahl",
    paint: {
      "circle-color": "rgba(0,0,0,0)",
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 5, 6, 14, 13],
      "circle-stroke-color": "#111827",
      "circle-stroke-width": 2.5,
    },
  });
  const farbe = ["match", ["get", "stand"],
    ...Object.entries(DATENLAGE_FARBEN).flat(), DATENLAGE_GRAU];
  map.addLayer({
    id: "datenlage-kreis",
    type: "circle",
    source: "datenlage",
    maxzoom: 10,
    paint: {
      "circle-color": farbe,
      "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 4.5, 9, 9],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 1.5,
      "circle-opacity": ["interpolate", ["linear"], ["zoom"], 8.5, 1, 10, 0],
      "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], 8.5, 1, 10, 0],
    },
  });
  map.addLayer({
    id: "datenlage-text",
    type: "symbol",
    source: "datenlage",
    minzoom: 5,
    maxzoom: 10,
    layout: {
      "text-field": ["get", "kommune"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 11,
      "text-anchor": "top",
      "text-offset": [0, 0.9],
      "text-optional": true,
    },
    paint: { "text-color": "#374151", "text-halo-color": "#ffffff", "text-halo-width": 1.3 },
  });
}

export function setzeStellen(map, featureCollection) {
  map.getSource("stellen")?.setData(featureCollection);
}

export function setzeAuswahl(map, stelle) {
  map.getSource("auswahl")?.setData(stelle
    ? { type: "FeatureCollection", features: [{ type: "Feature", geometry: { type: "Point", coordinates: [stelle.lon, stelle.lat] }, properties: {} }] }
    : LEER);
}

export function setzeDatenlage(map, sichtbar) {
  for (const id of ["datenlage-kreis", "datenlage-text"]) {
    if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", sichtbar ? "visible" : "none");
  }
}

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** EIN Hover-Popup für Zählstellen und Datenlage (wie in der Unfallkarte). */
export function bindeHover(map, { daten, manifest, gibZustand, gibEintrag }) {
  const popup = new Popup({ closeButton: false, closeOnClick: false, maxWidth: "280px", offset: 10 });
  const ebenen = ["stellen-kreis", "datenlage-kreis"];
  map.on("mousemove", (e) => {
    const f = map.queryRenderedFeatures(e.point, { layers: ebenen.filter((id) => map.getLayer(id)) })[0];
    if (!f) {
      popup.remove();
      map.getCanvas().style.cursor = "";
      return;
    }
    map.getCanvas().style.cursor = "pointer";
    let html;
    if (f.layer.id === "datenlage-kreis") {
      const p = f.properties;
      html = `<div class="pop-eyebrow">${esc(t("hover.datenlage", { land: p.land ?? "" }))}</div>
        <div class="pop-title">${esc(p.kommune)}</div>
        <div class="pop-meta">${esc(standText(manifest, p.stand))}</div>
        <div class="pinhint pop-pinhint">${esc(t("hover.belege"))}</div>`;
    } else {
      const z = gibZustand();
      const s = daten.stellen[f.properties.i];
      const eintrag = gibEintrag(s.index);
      const modus = z.modus[z.thema];
      const zeile = eintrag
        ? `<div class="pop-hero">${formatiere(eintrag.wert, modus)}</div>
          <div class="pop-meta">${esc(kennzahlText(z.thema, modus, z.art))}</div>`
        : "";
      const tag = eintrag?.z?.datum ? datum(eintrag.z.datum) : "";
      html = `<div class="pop-eyebrow">${esc(manifest.quellen.find((q) => q.code === s.quelle)?.name ?? s.quelle)}</div>
        <div class="pop-title">${esc(s.name)}</div>${zeile}
        <div class="pop-meta">${esc(tag)}${eintrag?.z ? ` · ${esc(TAGE[eintrag.z.tag ?? "u"])}` : ""}${s.zaehlungen.length > 1 ? ` · ${esc(t("hover.mehrere", { n: zahl(s.zaehlungen.length) }))}` : ""}</div>
        <div class="pop-pinhint">${esc(t("hover.details"))}</div>`;
    }
    popup.setLngLat(e.lngLat).setHTML(html).addTo(map);
  });
  map.getCanvas().addEventListener("mouseleave", () => popup.remove());
  return popup;
}
