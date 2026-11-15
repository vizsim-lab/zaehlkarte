// kommune.js (ui) — Steckbrief einer Kommune beim Klick auf ihren Punkt: was es dort gibt, für
// beide Zählarten zugleich – je Verkehrsart eine Zeile mit Zeitstrahl und Umfang (Kurzzeitzählungen
// als Jahreskästchen, Lücken sichtbar; Dauerzählstellen als Balken, hell, solange es nur Tageswerte
// der Quelle gibt). Ein Klick auf eine Zeile stellt Zählart und Verkehrsart um und zeigt die
// Stellen (main.js). Darunter, zugeklappt, sobald etwas in der Karte ist: Datenlage beider
// Zählarten, Kontakt, Anfragetext, Rechtslage und Belege.
//
// Was zu einer Kommune gehört, rechnet js/data/kommune.js. Oberfläche in der gewählten Sprache,
// die Recherche-Texte deutsch (lang="de"); Texte aus den Daten nur über esc() ins HTML.
import {
  anteil, dauerDerKommune, dauerQuellenJeKommune, klasseVon, kurzzeitDerKommune, zeitachse,
} from "../data/kommune.js";
import { DAUER_THEMEN } from "../data/dauer.js";
import { THEMEN } from "../data/modell.js";
import { standText } from "../map/ebenen.js";
import { datum, t, zahl } from "../sprache/texte.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const BLAU = [42, 120, 214]; // Farbe „in der Karte“ (js/map/ebenen.js)

/** Zeile einer Zählart: Name, Zeitstrahl, Umfang; ein Knopf, der die Ansicht umstellt. */
function zeile({ familie, thema, name, spur, n, titel, von, bis, umriss }) {
  return `<button type="button" class="kz-zeile" data-zeile data-familie="${familie}" data-thema="${thema}"
    data-von="${esc(von)}" data-bis="${esc(bis)}" data-umriss="${esc(JSON.stringify(umriss))}" title="${esc(titel)}" aria-label="${esc(titel)}">
    <span class="kz-name">${esc(name)}</span><span class="kz-spur" aria-hidden="true">${spur}</span><span class="kz-n">${esc(n)}</span></button>`;
}

/** Kurzzeitzählungen: ein Kästchen je Jahr der Achse, je dunkler, desto mehr Zählungen. */
function jahresKaestchen(x, achse) {
  const max = Math.max(...Object.values(x.jahre));
  let html = "";
  for (let j = achse[0]; j <= achse[1]; j += 1) {
    const n = x.jahre[j] ?? 0;
    const a = n ? (0.3 + 0.7 * (n / max)).toFixed(2) : 0;
    html += `<span class="kz-jahr"${n ? ` style="background:rgba(${BLAU.join(",")},${a})"` : ""}></span>`;
  }
  return html;
}

/** Dauerzählstellen: Balken vom ersten bis zum letzten Tag; hell, solange nur Tageswerte der Quelle. */
function balken(x, achse) {
  const links = anteil(x.von, achse);
  const rechts = anteil(x.bis, achse);
  const tw = x.twBis && x.twBis >= x.von ? anteil(x.twBis < x.bis ? x.twBis : x.bis, achse) : null;
  const teil = (a, b, klasse) => `<span class="kz-balken${klasse}" style="left:${(a * 100).toFixed(2)}%;width:${(Math.max(b - a, 0.006) * 100).toFixed(2)}%"></span>`;
  if (tw == null) return teil(links, rechts, "");
  return teil(links, tw, " kz-balken--tw") + (rechts > tw ? teil(tw, rechts, "") : "");
}

/** Beschriftung der Achse: erstes und letztes Jahr, dazwischen volle Jahrzehnte mit Abstand zu den Enden. */
function achsenText(achse) {
  const spanne = achse[1] + 1 - achse[0];
  const marken = [[achse[0], 0]];
  for (let j = Math.ceil((achse[0] + 1) / 10) * 10; j < achse[1]; j += 10) {
    const a = (j - achse[0]) / spanne;
    if (a > 0.18 && a < 0.82) marken.push([j, a]);
  }
  marken.push([achse[1], 1]);
  return marken.map(([j, a]) => `<span style="left:${(a * 100).toFixed(1)}%">${j}</span>`).join("");
}

export function erstelleKommune({ datenlage, manifest, daten, gibDauer, holeDauer, gibtDauer, gibZustand, beiZeile, beiCsv, beiSchliessen }) {
  const el = document.getElementById("kommune-detail");
  const anzahl = dauerQuellenJeKommune(datenlage);
  const jeAgs = new Map(datenlage.features.map((f) => [f.properties.ags, f.properties]));
  let p = null;
  let dauerFehlt = false; // Dauerzählstellen nicht verfügbar (kein Asset)
  // Datenlage auf- oder zugeklappt, wie zuletzt von Hand gewählt (null: offen, solange nichts der
  // Kommune in der Karte ist) – bleibt beim Neuzeichnen (Dauerzählstellen geladen, Sprache)
  let datenlageOffen = null;

  el.addEventListener("click", async (e) => {
    if (e.target.closest("[data-schliessen]")) { schliesse(); return; }
    const summary = e.target.closest(".kz-datenlage > summary");
    if (summary) { datenlageOffen = !summary.parentElement.open; return; }
    const z = e.target.closest("[data-zeile]");
    if (z) {
      beiZeile?.({ familie: z.dataset.familie, thema: z.dataset.thema, von: z.dataset.von, bis: z.dataset.bis, umriss: JSON.parse(z.dataset.umriss) }, p);
      return;
    }
    if (e.target.closest("[data-csv]")) { beiCsv?.(p); return; }
    const kopieren = e.target.closest("[data-kopieren]");
    if (kopieren) {
      const feld = el.querySelector(".anfrage-text");
      try {
        await navigator.clipboard.writeText(feld.value);
      } catch {
        feld.select();
        document.execCommand("copy");
      }
      kopieren.textContent = t("dl.kopiert");
    }
  });

  function zeige(ags) {
    const neu = jeAgs.get(ags);
    if (!neu) return false;
    if (neu !== p) datenlageOffen = null;
    p = neu;
    zeichne({ oben: true });
    el.hidden = false;
    // Dauerzählstellen erst jetzt laden, falls noch nicht geschehen (wie beim Umschalten)
    if (!gibDauer() && !dauerFehlt) {
      gibtDauer().then((da) => (da ? holeDauer() : Promise.reject(new Error("fehlt")))).then(() => {
        if (p === neu) zeichne();
      }).catch(() => {
        dauerFehlt = true;
        if (p === neu) zeichne();
      });
    }
    return true;
  }

  function schliesse() {
    if (el.hidden) return;
    el.hidden = true;
    p = null;
    beiSchliessen?.();
  }

  /** Die Zeile der gezeigten Ansicht (Zählart und Verkehrsart) hervorheben. */
  function markiere() {
    if (!p) return;
    const z = gibZustand();
    const thema = z.familie === "d" ? z.dthema : z.thema;
    el.querySelectorAll("[data-zeile]").forEach((b) => {
      const an = b.dataset.familie === z.familie && b.dataset.thema === thema;
      b.classList.toggle("is-aktiv", an);
      b.setAttribute("aria-pressed", String(an));
    });
  }

  /** Stand einer Zählart der Kommune als Kennzeichen (oder „noch nicht recherchiert“). */
  function standChip(block, familie, mitZeilen) {
    if (!block) {
      // ohne eigene Recherche, aber mit Stellen in der Karte (etwa Zählstellen des Landes)
      return mitZeilen ? `<span class="kz-stand kz-stand--karte">${esc(standText(datenlage, "in_karte", familie))}</span>`
        : `<span class="kz-stand">${esc(t("kommune.nicht_recherchiert"))}</span>`;
    }
    const karte = block.quellen?.length > 0;
    return `<span class="kz-stand${karte ? " kz-stand--karte" : ""}">${esc(standText(datenlage, block.stand, familie))}</span>`;
  }

  function familieHtml(familie, block, inhalt, umfang, quellen) {
    const name = t(familie === "d" ? "familie.d" : "familie.k");
    const mitZeilen = inhalt.includes("kz-zeile");
    return `<section class="kz-familie" data-familie-block="${familie}">
      <div class="kz-familie-kopf"><span class="kz-familie-name">${esc(name)}</span>${standChip(block, familie, mitZeilen)}</div>
      ${umfang ? `<div class="kz-umfang">${esc(umfang)}</div>` : ""}
      ${inhalt}
      ${quellen.length ? `<div class="pop-meta kz-quellen" lang="de">${esc(t(quellen.length > 1 ? "kommune.quellen" : "kommune.quelle", { quellen: quellen.join(", ") }))}</div>` : ""}
    </section>`;
  }

  /** Datenlage, Kontakt, Anfrage, Rechtslage, Belege – beide Zählarten (Texte deutsch). */
  function datenlageHtml(offen) {
    const teile = [];
    for (const [familie, b] of [["k", p.kurzzeit], ["d", p.dauer]]) {
      if (!b) continue;
      const links = b.links.map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.titel)}</a></li>`).join("");
      teile.push(`<div class="detail-abschnitt">${esc(t(familie === "d" ? "familie.d" : "familie.k"))} · ${esc(standText(datenlage, b.stand, familie))}</div>
        ${b.was ? `<p class="detail-text" lang="de">${esc(b.was)}</p>` : ""}
        ${b.situation ? `<p class="detail-text" lang="de">${esc(b.situation)}</p>` : ""}
        ${b.empfehlung ? `<p class="detail-text"><strong>${esc(t("dl.empfehlung"))}:</strong> <span lang="de">${esc(b.empfehlung)}</span></p>` : ""}
        ${b.weg ? `<p class="detail-text"><span class="pop-chip" lang="de">${esc(b.weg)}</span></p>` : ""}
        ${links ? `<ul class="detail-hinweise kz-belege" lang="de" aria-label="${esc(t("dl.belege"))}">${links}</ul>` : ""}`);
    }
    // Kontakt und Rechtslage, solange eine Anfrage noch etwas bringt (eine Zählart nicht mit Lizenz in der Karte)
    const anfragen = [p.kurzzeit, p.dauer].some((b) => b && b.stand !== "in_karte");
    const k = p.kontakt;
    if (anfragen && k) {
      teile.push(`<div class="detail-abschnitt">${esc(t("dl.kontakt"))}</div><p class="detail-text">
        ${k.name ? `<span lang="de">${esc(k.name)}</span><br>` : ""}${k.email ? `<a href="mailto:${esc(k.email)}">${esc(k.email)}</a><br>` : ""}
        ${k.fds ? `<a href="${esc(k.fds)}" target="_blank" rel="noopener">${esc(t(k.fds_suche ? "dl.fds_suche" : "dl.fds"))} →</a>` : ""}</p>`);
    }
    const a = p.kurzzeit?.anfrage;
    if (a) {
      teile.push(`<div class="detail-abschnitt">${esc(t("dl.anfrage"))}</div>
        <p class="pop-meta">${esc(t("dl.anfrage_hinweis", { betreff: a.betreff }))}</p>
        <textarea class="anfrage-text" readonly rows="9" lang="de" aria-label="${esc(t("dl.anfrage"))}">${esc(a.text)}</textarea>
        <p class="detail-links"><button type="button" class="link-knopf" data-kopieren>${esc(t("dl.kopieren"))}</button>
        ${k?.fds ? `<a href="${esc(k.fds)}" target="_blank" rel="noopener">${esc(t("dl.stellen"))}</a>` : ""}</p>`);
    }
    if (anfragen && p.recht) {
      teile.push(`<div class="detail-abschnitt">${esc(t("dl.recht"))}</div><p class="detail-text"><span lang="de">${esc(p.recht)}.</span> ${esc(t("dl.keine_beratung"))}</p>`);
    }
    const deutsch = t("dl.deutsch");
    return `<details class="kz-datenlage"${offen ? " open" : ""}>
      <summary>${esc(t("kommune.datenlage"))}</summary>
      ${deutsch ? `<p class="pop-meta dl-sprache">${esc(deutsch)}</p>` : ""}
      ${teile.join("")}
    </details>`;
  }

  function zeichne({ oben = false } = {}) {
    if (!p) return;
    const scroll = el.scrollTop;
    const d = gibDauer();
    const kurz = p.kurzzeit?.quellen?.length ? kurzzeitDerKommune(daten, p.kurzzeit.quellen) : null;
    const lang = d ? dauerDerKommune(d, p, anzahl) : null;
    const achse = zeitachse(kurz, lang);

    // Kurzzeitzählungen
    const qk = manifest.quellen.filter((q) => p.kurzzeit?.quellen?.includes(q.code));
    const kInhalt = kurz?.themen.map((x) => zeile({
      familie: "k", thema: x.thema, name: THEMEN[x.thema].name, spur: jahresKaestchen(x, achse), n: zahl(x.zaehlungen),
      titel: t("kommune.zeile_k", { art: THEMEN[x.thema].name, n: zahl(x.zaehlungen), zeitraum: x.von === x.bis ? String(x.von) : `${x.von}–${x.bis}` }),
      von: x.von, bis: x.bis, umriss: x.umriss,
    })).join("") ?? "";
    const kUmfang = kurz ? t("kommune.umfang_k", { zaehlungen: zahl(kurz.zaehlungen), stellen: zahl(kurz.stellen) }) : "";

    // Dauerzählstellen (geladen beim ersten Steckbrief, wie beim Umschalten)
    let dInhalt = "";
    if (lang) {
      dInhalt = lang.themen.map((x) => zeile({
        familie: "d", thema: x.thema, name: DAUER_THEMEN[x.thema].name, spur: balken(x, achse), n: zahl(x.stellen),
        titel: t(x.twBis ? "kommune.zeile_d_tw" : "kommune.zeile_d", {
          art: DAUER_THEMEN[x.thema].name, n: zahl(x.stellen), von: datum(x.von), bis: datum(x.bis), tw: x.twBis ? datum(x.twBis) : "",
        }),
        von: x.von, bis: x.bis, umriss: x.umriss,
      })).join("");
      if (lang.themen.some((x) => x.twBis)) dInhalt += `<div class="kz-hinweis">${esc(t("kommune.tw_hinweis"))}</div>`;
    } else if (!dauerFehlt) {
      dInhalt = `<div class="kz-hinweis" data-laedt>${esc(t("kommune.dauer_laedt"))}</div>`;
    } else if (dauerFehlt && p.dauer?.quellen?.length) {
      dInhalt = `<div class="kz-hinweis">${esc(t("kommune.dauer_fehlt"))}</div>`;
    }
    const dUmfang = lang?.stellen ? t("kommune.umfang_d", { stellen: zahl(lang.stellen) }) : "";

    const imKarte = Boolean(kurz?.themen.length || lang?.themen.length);
    const csvMoeglich = qk.some((q) => q.lizenzen.some((l) => !l.ohne_lizenz)) && kurz?.zaehlungen > 0;
    el.innerHTML = `
      <header class="detail-kopf">
        <div><div class="pop-eyebrow">${esc(t("kommune.eyebrow", { land: p.land ?? "" }))}</div>
        <h2 class="detail-titel">${esc(p.name)}</h2>
        <div class="pop-meta">${esc(t(imKarte ? "kommune.untertitel" : "kommune.untertitel_leer"))}</div></div>
        <button class="detail-zu" type="button" data-schliessen aria-label="${esc(t("schliessen"))}">×</button>
      </header>
      ${achse && imKarte ? `<div class="kz-achse" aria-hidden="true"><span></span><span class="kz-achse-skala">${achsenText(achse)}</span><span></span></div>` : ""}
      ${familieHtml("k", p.kurzzeit, kInhalt, kUmfang, qk.map((q) => q.name))}
      ${familieHtml("d", p.dauer, dInhalt, dUmfang, (lang?.quellen ?? []).map((q) => q.name))}
      ${imKarte ? `<p class="kz-tipp">${esc(t("kommune.tipp"))}</p>` : ""}
      ${csvMoeglich ? `<p class="detail-links"><button type="button" class="link-knopf" data-csv>${esc(t("kommune.csv"))}</button></p>` : ""}
      ${datenlageHtml(datenlageOffen ?? !imKarte)}
      <div class="pop-foot"><a href="https://github.com/vizsim-lab/zaehlkarte/issues/new?template=zaehlung-melden.yml" target="_blank" rel="noopener">${esc(t("dl.melden", { kommune: p.name }))}</a></div>`;
    el.dataset.ags = p.ags;
    el.dataset.klasse = klasseVon(p);
    el.scrollTop = oben ? 0 : scroll;
    markiere();
  }

  return {
    zeige, schliesse, zeichne, markiere,
    get ags() { return p?.ags ?? null; },
    get offen() { return !el.hidden; },
  };
}
