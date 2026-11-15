// platz.js — die schwebenden Panels nehmen Rücksicht aufeinander und auf die Karte
// (docs/KARTE.md, „Platz für die Karte“). Gerechnet wird in js/utils/platzRechnung.js (rein),
// hier wird gemessen und umgesetzt:
//   1. Geht links eine Seitenleiste auf (Stelle, Dauerzählstelle, Steckbrief) und bliebe zwischen
//      ihr und der Legende weniger als MIN_KARTE px Karte, klappt die Legende auf ihre Kopfzeile
//      zu – und wieder auf, sobald keine Seitenleiste mehr offen ist. Klappt man sie inzwischen
//      selbst auf oder zu, gilt das.
//   2. Handy-Layout (MOBIL): nie zwei Sheets – mit einer offenen Seitenleiste ist die Legende zu,
//      und sie bleibt es nach dem Schließen (wer schließt, will die Karte sehen). Die Knöpfe
//      unten links weichen, solange ein Sheet offen ist (CSS: body.hat-panel).
//   3. Die gewählte Stelle bzw. Kommune bleibt sichtbar: liegt sie unter einem Panel oder Sheet,
//      rückt die Karte sie in die Mitte des freien Teils – gleich nach dem Öffnen und auf dem
//      Handy noch einmal, wenn das Sheet mit dem geladenen Inhalt wächst (solange sich die Karte
//      nicht anders bewegt hat: Ziehen, Suche, „Stellen zeigen“ haben Vorrang).
//   4. Hover-Kärtchen öffnen zur freien Seite (popupRand), Suche und fitBounds zielen auf den
//      freien Teil (versatz, rand).
import { MOBIL_BIS, freieFlaeche, genugPlatz, kartenRand, popupRand, verschiebung, versatz } from "../utils/platzRechnung.js";
import { klappeLegende } from "./legende.js";

/** Media-Query des Handy-Layouts (dieselbe Grenze in index.html und style.css). */
export const MOBIL = `(max-width: ${MOBIL_BIS}px)`;

/** Wie lange (ms) die Karte einer Auswahl nachrückt, wenn ihr Panel noch wächst. */
const NACHRUECKEN_MS = 2500;

export function erstellePlatz(karte) {
  const legende = document.getElementById("legend");
  const panels = [...document.querySelectorAll(".detail-panel")];
  const mql = window.matchMedia(MOBIL);
  const mobil = () => mql.matches;
  const offen = () => panels.find((p) => !p.hidden) ?? null;
  const rechteck = (el) => (el ? el.getBoundingClientRect() : null);

  let warOffen = false; // war beim letzten Blick eine Seitenleiste offen?
  let automatischZu = false; // Legende wegen einer Seitenleiste zugeklappt: beim Schließen wieder auf
  let gewaehlt = null; // [lon, lat] der gewählten Stelle oder Kommune
  let nachrueckenBis = 0; // bis dahin rückt die Karte nach, wenn das Sheet wächst

  /** Was gerade wo liegt (Bildschirm-px). Die Suche entsteht erst nach dem Start – darum jedes Mal. */
  function lage() {
    return {
      breite: window.innerWidth,
      hoehe: window.innerHeight,
      mobil: mobil(),
      panel: rechteck(offen()),
      legende: rechteck(legende),
      legendeZu: legende.classList.contains("collapsed"),
      suche: rechteck(document.querySelector(".geocoder")),
    };
  }
  const frei = () => freieFlaeche(lage());

  function pruefe() {
    const panel = offen();
    document.body.classList.toggle("hat-panel", Boolean(panel));
    const neu = Boolean(panel) && !warOffen;
    warOffen = Boolean(panel);
    if (!panel) {
      gewaehlt = null;
      if (automatischZu && !mobil()) klappeLegende(false);
      automatischZu = false;
      return;
    }
    if (legende.classList.contains("collapsed")) return;
    if (mobil()) {
      klappeLegende(true); // nie zwei Sheets übereinander
      automatischZu = false;
    } else if (neu && !genugPlatz(rechteck(panel).right, rechteck(legende).left)) {
      klappeLegende(true);
      automatischZu = true;
    }
  }

  function zeigeGewaehlt(dauer = 350) {
    if (!gewaehlt || !offen()) return;
    const d = verschiebung(karte.project(gewaehlt), frei(), { breite: window.innerWidth, hoehe: window.innerHeight });
    if (d) karte.panBy(d, { duration: dauer }, { platz: true }); // eventData: als eigene Bewegung erkennbar
  }

  /** Gewählte Stelle oder Kommune ([lon, lat], null: keine) – nach dem Öffnen ihres Panels aufrufen. */
  let rahmen = 0;
  function waehle(lngLat, { sofort = false } = {}) {
    gewaehlt = lngLat ?? null;
    nachrueckenBis = gewaehlt ? Date.now() + NACHRUECKEN_MS : 0;
    cancelAnimationFrame(rahmen);
    if (gewaehlt) rahmen = requestAnimationFrame(() => zeigeGewaehlt(sofort ? 0 : 350));
  }

  // Von Hand geklappt: dann gilt das, nichts mehr von selbst wieder aufklappen
  legende.addEventListener("legende-klappt", (e) => { if (e.detail?.vonHand) automatischZu = false; });
  // Bewegt sich die Karte anders (Ziehen, Suche, fitBounds), gilt das – kein Nachrücken mehr
  karte.on("movestart", (e) => { if (!e.platz) nachrueckenBis = 0; });
  karte.on("dragstart", () => { nachrueckenBis = 0; }); // auch mitten im eigenen Rücken

  const sichtbar = new MutationObserver(pruefe);
  for (const p of panels) sichtbar.observe(p, { attributes: true, attributeFilter: ["hidden"] });
  // Nur das Handy-Sheet wächst mit dem Inhalt in die Karte; die Seitenleiste am Desktop ist fest breit
  const groesse = new ResizeObserver(() => {
    if (!mobil() || Date.now() > nachrueckenBis) return;
    cancelAnimationFrame(rahmen);
    rahmen = requestAnimationFrame(() => zeigeGewaehlt());
  });
  for (const p of panels) groesse.observe(p);
  mql.addEventListener("change", pruefe);
  window.addEventListener("resize", pruefe);
  pruefe();

  return {
    mobil,
    frei,
    waehle,
    pruefe,
    /** Versatz der Mitte des freien Teils gegen die Fenstermitte (offset für flyTo/easeTo). */
    versatz: () => versatz(frei(), window.innerWidth, window.innerHeight),
    /** Rand für fitBounds; zugeklappt deckt die Legende oben rechts eine Ecke ab. */
    rand() {
      const l = lage();
      const oben = !l.mobil && l.legendeZu && l.legende ? Math.max(70, Math.round(l.legende.bottom) + 20) : 70;
      return kartenRand(freieFlaeche(l), l.breite, l.hoehe, oben);
    },
    /** Rand für das Hover-Kärtchen an einem Bildschirmpunkt (Popup.setPadding). */
    popupRand: (punkt) => popupRand(punkt, lage()),
  };
}
