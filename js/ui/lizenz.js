// lizenz.js — die Lizenz einer Quelle in Seitenleiste und Detailansichten beider Familien.
//
// Quellen ohne Lizenz (CLAUDE.md, „Quellen ohne Lizenz“; `lizenzen[].ohne_lizenz` in manifest.json
// bzw. dauer/index.json): „ohne Lizenz“ mit Hinweis (ⓘ – data-tip nur dort), wie die Kommune die
// Werte herausgegeben hat, und der Link zum Formular „Daten entfernen lassen“. Den CSV-Export
// verhindert lizenzFuerCsv (js/data/modell.js).
import { datum, sprache, t } from "../sprache/texte.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Issue-Formular für Rechteinhaber (.github/ISSUE_TEMPLATE/daten-entfernen.yml). */
export const ENTFERNEN = "https://github.com/vizsim-lab/zaehlkarte/issues/new?template=daten-entfernen.yml";

/** Die Lizenz als HTML: ihr Name (verlinkt, wo es eine URL gibt) oder „ohne Lizenz“ mit Hinweis. */
export function lizenzHtml(l) {
  if (l?.ohne_lizenz) {
    return `<span class="ohne-lizenz" lang="${sprache()}">${esc(t("lizenz.ohne"))}</span> <span class="info-icon" data-tip="${esc(t("lizenz.ohne_tip"))}">i</span>`;
  }
  return l?.lizenz_url ? `<a href="${esc(l.lizenz_url)}" target="_blank" rel="noopener">${esc(l.lizenz)}</a>` : esc(l?.lizenz ?? "");
}

/** Nur bei einer Quelle ohne Lizenz: wie die Kommune die Werte herausgegeben hat (deutsch), der
 *  Tag der Prüfung und der Link „Entfernen lassen“; sonst leer. */
export function ohneLizenzHtml(l) {
  const o = l?.ohne_lizenz;
  if (!o) return "";
  return `<div class="pop-meta ohne-lizenz-text"><span lang="de">${esc(o.herausgegeben)}</span>`
    + ` <span lang="${sprache()}">(${esc(t("lizenz.geprueft", { datum: datum(o.geprueft) }))}) · `
    + `<a href="${ENTFERNEN}" target="_blank" rel="noopener" title="${esc(t("lizenz.entfernen_titel"))}">${esc(t("lizenz.entfernen"))}</a></span></div>`;
}
