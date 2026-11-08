// Smoke-Tests für das Frontend (tests/web/). Getestet wird der BUILD, nicht der Dev-Server:
// webServer baut dist/ und liefert es mit `vite preview` aus – genau das Artefakt, das die CI
// danach nach GitHub Pages deployt (getestet = ausgeliefert). Muster aus vizsim/unfallkarte.
//
// Die Tests sperren alle Anfragen ins Netz (tests/web/helpers.js): Hintergrundkarte und Suche
// gehören nicht zum Prüfgegenstand, und die Karte muss auch ohne sie funktionieren.
import { defineConfig, devices } from "@playwright/test";

const PORT = Number(process.env.PW_PORT) || 4173;
const BASE_URL = `http://127.0.0.1:${PORT}`;

export default defineConfig({
  testDir: "tests/web",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  workers: process.env.CI ? 2 : undefined,
  retries: process.env.CI ? 1 : 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: BASE_URL,
    viewport: { width: 1400, height: 900 },
    trace: process.env.CI ? "on-first-retry" : "off",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1400, height: 900 } } }],
  webServer: {
    command: `npm run build && npx vite preview --host 127.0.0.1 --port ${PORT} --strictPort`,
    url: `${BASE_URL}/index.html`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
