// vite.config.js — Dev-Server + Build des Frontends (Muster aus vizsim/unfallkarte).
//
// Zwei Abweichungen vom Vite-Standard, beide wie in der Unfallkarte:
//  1. MapLibre wird NICHT gebündelt (maplibreExternal). Es sucht seinen Worker zur Laufzeit
//     neben der eigenen Datei (import.meta.url). Gebündelt bleibt die Karte leer, ohne jeden
//     Fehler. Die drei .mjs werden versioniert nach dist/lib/ kopiert, eine Importmap löst den
//     nackten Import "maplibre-gl" auf.
//  2. appType "mpa": Vites SPA-Fallback beantwortete jeden unbekannten Pfad mit index.html und
//     Status 200 – ein fehlender Daten-Chunk sähe dann aus wie ein kaputtes JSON statt wie 404.
// Die Kartendaten liegen in public/data/ (erzeugt von der Pipeline) und gehen unverändert nach
// dist/data/.
import { defineConfig } from "vite";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";

const require = createRequire(import.meta.url);
const ML_PKG = require.resolve("maplibre-gl/package.json");
const ML_DIR = `lib/maplibre-gl@${require(ML_PKG).version}`;
const ML_FILES = ["maplibre-gl.mjs", "maplibre-gl-shared.mjs", "maplibre-gl-worker.mjs"];

function maplibreExternal() {
  return {
    name: "zaehlkarte:maplibre-external",
    apply: "build",
    config: () => ({ build: { rolldownOptions: { external: ["maplibre-gl"] } } }),
    transformIndexHtml: () => [
      // Die Importmap muss vor dem ersten Modul stehen.
      { tag: "script", attrs: { type: "importmap" }, injectTo: "head-prepend",
        children: JSON.stringify({ imports: { "maplibre-gl": `./${ML_DIR}/maplibre-gl.mjs` } }) },
      // Ohne Preload entdeckt der Browser MapLibre erst nach dem Parsen des Bündels.
      ...ML_FILES.slice(0, 2).map((f) => ({
        tag: "link", attrs: { rel: "modulepreload", href: `./${ML_DIR}/${f}` }, injectTo: "head-prepend",
      })),
    ],
    writeBundle({ dir }) {
      mkdirSync(join(dir, ML_DIR), { recursive: true });
      for (const f of ML_FILES) {
        // .map-Dateien liefern wir nicht aus -> Verweis weg, sonst 404 in den DevTools.
        const code = readFileSync(join(dirname(ML_PKG), "dist", f), "utf8")
          .replace(/\/\/# sourceMappingURL=\S+\s*$/, "");
        writeFileSync(join(dir, ML_DIR, f), code);
      }
    },
  };
}

export default defineConfig({
  base: "./",        // Pages liefert unter vizsim-lab.github.io/zaehlkarte/ aus; relativ passt überall
  appType: "mpa",    // siehe 2. oben
  server: { watch: { ignored: ["**/pipeline/**", "**/test-results/**", "**/playwright-report/**"] } },
  // Dev: MapLibre direkt aus node_modules laden statt vorgebündelt (Worker liegt daneben).
  optimizeDeps: { exclude: ["maplibre-gl"] },
  plugins: [maplibreExternal()],
});
