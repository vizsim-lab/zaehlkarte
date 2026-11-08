// mobileLayout.js — unter 640px wird die Legende zum Bottom-Sheet (CSS in style.css).
// Hier nur, was CSS nicht kann (vereinfacht aus vizsim/unfallkarte, ohne Zieh-Geste):
//   1. die Höhe des zugeklappten Sheets als `--legend-peek` melden – daran hängen die
//      Bedienelemente unten links und die Attribution;
//   2. die Suche auf dem Handy zum Lupen-Knopf falten.
const MOBIL = "(max-width: 640px)";

export function setupMobileLayout() {
  const legend = document.querySelector(".legend");
  if (!legend || !window.matchMedia) return;
  const mql = window.matchMedia(MOBIL);

  const meldePeek = () => {
    if (!mql.matches || !legend.classList.contains("collapsed")) return;
    const h = Math.round(legend.getBoundingClientRect().height);
    if (h > 0) document.documentElement.style.setProperty("--legend-peek", `${h}px`);
  };
  if (window.ResizeObserver) new ResizeObserver(meldePeek).observe(legend);
  new MutationObserver(meldePeek).observe(legend, { attributes: true, attributeFilter: ["class"] });
  meldePeek();

  const geocoder = document.querySelector(".geocoder");
  const wrapper = geocoder?.querySelector(".geocoder-input-wrapper");
  const input = geocoder?.querySelector("#search");
  if (!geocoder || !wrapper || !input) return;
  const falte = (zu) => {
    geocoder.classList.toggle("is-collapsed", zu);
    if (zu) {
      wrapper.setAttribute("role", "button");
      wrapper.setAttribute("tabindex", "0");
      wrapper.setAttribute("aria-label", "Adresse suchen");
    } else {
      wrapper.removeAttribute("role");
      wrapper.removeAttribute("tabindex");
      wrapper.removeAttribute("aria-label");
    }
  };
  const oeffne = () => {
    if (!geocoder.classList.contains("is-collapsed")) return;
    falte(false);
    input.focus();
  };
  wrapper.addEventListener("click", oeffne);
  wrapper.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); oeffne(); }
  });
  input.addEventListener("blur", () => setTimeout(() => {
    if (mql.matches && !input.value.trim()) falte(true);
  }, 150));
  falte(mql.matches);
  mql.addEventListener("change", (e) => falte(e.matches));
}
