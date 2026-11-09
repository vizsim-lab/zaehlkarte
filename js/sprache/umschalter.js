// umschalter.js — Sprache der Oberfläche wählen und anwenden (DE Standard, EN wählbar).
//
// Wahl: ?lang=de|en > gespeicherte Wahl > Deutsch. Der Wechsel schreibt ?lang= in die Adresse,
// damit geteilte Links in derselben Sprache öffnen (der Zustand der Karte steht im #-Teil und
// bleibt unberührt). Statische Texte stehen im HTML als data-i18n (Textinhalt) und
// data-i18n-attr ("title:schlüssel;aria-label:schlüssel"); dynamische holen sich ihre Texte
// über t() und werden nach dem Wechsel neu gezeichnet (main.js).
// Muster aus vizsim/osm_hashtag_analyse (analysen/cw_miss/viz/i18n.js).
import { SPRACHEN, setzeSprache, sprache, t } from "./texte.js";

const SPEICHER = "zaehlkarte:sprache";

export function ersteSprache() {
  const ausUrl = new URLSearchParams(location.search).get("lang");
  if (SPRACHEN.includes(ausUrl)) return setzeSprache(ausUrl);
  try {
    const gemerkt = localStorage.getItem(SPEICHER);
    if (SPRACHEN.includes(gemerkt)) return setzeSprache(gemerkt);
  } catch {
    // Speicher gesperrt (privates Fenster o. Ä.) -> Standard
  }
  return setzeSprache("de");
}

/** Sprache wechseln; false, wenn sie schon gilt. */
export function wechsleSprache(s) {
  if (!SPRACHEN.includes(s) || s === sprache()) return false;
  setzeSprache(s);
  try {
    localStorage.setItem(SPEICHER, s);
  } catch {
    // dann gilt die Wahl nur, solange ?lang= in der Adresse steht
  }
  const url = new URL(location.href);
  url.searchParams.set("lang", s);
  history.replaceState(null, "", url);
  return true;
}

/** Statische Texte, <html lang>, Titel und Knöpfe des Umschalters in der aktuellen Sprache. */
export function wendeAn(wurzel = document) {
  document.documentElement.lang = sprache();
  document.title = t("dokument.titel");
  document.querySelector('meta[name="description"]')?.setAttribute("content", t("dokument.beschreibung"));
  for (const el of wurzel.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of wurzel.querySelectorAll("[data-i18n-attr]")) {
    for (const paar of el.dataset.i18nAttr.split(";")) {
      const [attr, schluessel] = paar.split(":").map((x) => x.trim());
      if (attr && schluessel) el.setAttribute(attr, t(schluessel));
    }
  }
  for (const b of document.querySelectorAll("#sprachwahl [data-sprache]")) {
    const an = b.dataset.sprache === sprache();
    b.classList.toggle("is-active", an);
    b.setAttribute("aria-pressed", String(an));
  }
}

/** Klick auf DE/EN: Sprache wechseln, Texte anwenden, dann `beiWechsel()` (neu zeichnen). */
export function bindeUmschalter(beiWechsel) {
  document.getElementById("sprachwahl")?.addEventListener("click", (e) => {
    const b = e.target.closest("[data-sprache]");
    if (!b || !wechsleSprache(b.dataset.sprache)) return;
    wendeAn();
    beiWechsel();
  });
}
