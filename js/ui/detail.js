// detail.js — Seitenleiste einer Stelle: alle Zählungen je Verkehrsart, Tagesgang der gewählten
// Zählung, Kennwerte, Herkunft und Lizenz, CSV der Stundenwerte.
//
// Texte aus den Daten (Namen, Bemerkungen) sind fremd: immer über esc() ins HTML. Sie bleiben
// deutsch (lang="de"); die Oberfläche folgt der gewählten Sprache (js/sprache/texte.js).
import { ladeDetails } from "../data/laden.js";
import {
  ARTEN, GRUPPEN, GRUPPEN_NAMEN, TAGE, formatiere, hat, kennwert, kennzahlText, wert,
} from "../data/modell.js";
import { datum, name, t, uhr, wochentag, zahl } from "../sprache/texte.js";
import { proStunde, tagesgang, TG, verlauf } from "./diagramme.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const SERIE_1 = "#2a78d6";
const SERIE_2 = "#eb6834";
const ANSICHTEN = {
  kfz: ["kfz", "sv"],
  rad: ["rad"],
  fuss: ["fuss", "kind"],
};

export function erstelleDetail({ manifest, daten, gibZustand, beiSchliessen, beiWechsel }) {
  const el = document.getElementById("detail");
  const quellen = Object.fromEntries(manifest.quellen.map((q) => [q.code, q]));
  let stelle = null;
  let gewaehlt = null; // Zählungs-Index
  let ansicht = null;
  let ladeNr = 0;

  el.addEventListener("click", (e) => {
    const zu = e.target.closest("[data-schliessen]");
    if (zu) { schliesse(); return; }
    const zeile = e.target.closest("[data-zaehlung]");
    if (zeile) { waehle(Number(zeile.dataset.zaehlung)); return; }
    const chip = e.target.closest("[data-ansicht]");
    if (chip) { ansicht = chip.dataset.ansicht; zeichneZaehlung(); return; }
    const csvKnopf = e.target.closest("[data-csv]");
    if (csvKnopf) ladeCsv();
  });
  el.addEventListener("keydown", (e) => {
    const zeile = e.target.closest("[data-zaehlung]");
    if (zeile && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      waehle(Number(zeile.dataset.zaehlung));
    }
  });

  function lizenz(z) {
    const q = quellen[stelle.quelle];
    const code = z.lieferung ? z.lieferung.split(":")[1] : stelle.quelle;
    return q.lizenzen.find((l) => l.code === code) ?? q.lizenzen[0];
  }

  function zeige(s, zaehlungIndex = null) {
    stelle = s;
    const z = gibZustand();
    const passende = s.zaehlungen.filter((x) => hat(x, z.thema));
    gewaehlt = zaehlungIndex ?? (passende.at(-1) ?? s.zaehlungen.at(-1)).index;
    ansicht = z.thema === "sv" ? "kfz" : z.thema; // Schwerverkehr steht im Kfz-Tagesgang
    el.hidden = false;
    zeichneKopf();
    zeichneZaehlung();
  }

  function schliesse() {
    if (el.hidden) return;
    el.hidden = true;
    stelle = null;
    beiSchliessen?.();
  }

  function waehle(index) {
    gewaehlt = index;
    zeichneKopf();
    zeichneZaehlung();
    beiWechsel?.(stelle, index);
  }

  function zeichneKopf() {
    const z = gibZustand();
    const q = quellen[stelle.quelle];
    const typ = t(stelle.typ === "K" || stelle.typ === "Q" ? `detail.typ.${stelle.typ}` : "detail.typ.sonst");
    const kennung = stelle.id.split(":").slice(1).join(":");
    const zeilen = [...stelle.zaehlungen].reverse().map((x) => {
      const zellen = ["kfz", "sv", "rad", "fuss"].map((g) => {
        if (!hat(x, g)) return "<td class=\"is-leer\">–</td>";
        const v = wert(x, g, z.art);
        return `<td>${v == null ? `<span class="pop-hint" data-tip="${esc(t("detail.nicht_voll"))}">·</span>` : zahl(v)}</td>`;
      });
      const aktiv = x.index === gewaehlt ? " is-aktiv" : "";
      return `<tr class="dz-zeile${aktiv}" data-zaehlung="${x.index}" tabindex="0">
        <td>${esc(datum(x.datum))}</td><td class="dz-tag" title="${esc(TAGE[x.tag ?? "u"])}">${esc(t(`tag_kurz.${x.tag ?? "u"}`))}</td><td class="dz-uhr">${String(x.fenster ?? "").split(", ").map((f) => `<span class="nw">${esc(f)}</span>`).join(", ")}</td>${zellen.join("")}</tr>`;
    });
    const anzahl = stelle.zaehlungen.length === 1 ? t("detail.eine") : t("detail.n", { n: zahl(stelle.zaehlungen.length) });
    const spalte = (g) => `<th title="${esc(GRUPPEN_NAMEN[g])}">${esc(t(`kurz.${g}`))}</th>`;
    el.innerHTML = `
      <header class="detail-kopf">
        <div>
          <div class="pop-eyebrow">${esc(typ)} · ${esc(q.name)} · ${esc(kennung)}</div>
          <h2 class="detail-titel">${esc(stelle.name)}</h2>
          <div class="pop-meta">${esc(anzahl)} · ${esc(t("detail.lage", { lage: t(`lage.${stelle.lage}`) }))}</div>
        </div>
        <button class="detail-zu" data-schliessen aria-label="${esc(t("schliessen"))}" type="button">×</button>
      </header>
      <div class="detail-verlauf" id="detail-verlauf"></div>
      <div class="detail-tabelle-wrap">
        <table class="detail-tabelle">
          <thead><tr><th>${esc(t("detail.spalte.datum"))}</th><th>${esc(t("detail.spalte.tag"))}</th><th>${esc(t("detail.spalte.uhr"))}</th>${["kfz", "sv", "rad", "fuss"].map(spalte).join("")}</tr></thead>
          <tbody>${zeilen.join("")}</tbody>
        </table>
        <div class="pop-meta">${esc(t("detail.werte", { art: ARTEN[z.art] }))}</div>
      </div>
      <section class="detail-zaehlung" id="detail-zaehlung" aria-live="polite"></section>`;
    zeichneVerlauf();
  }

  function zeichneVerlauf() {
    const z = gibZustand();
    const m = z.modus[z.thema];
    const punkte = stelle.zaehlungen.filter((x) => x.datum).map((x) => {
      const v = kennwert(x, z.thema, m, z.art);
      return {
        datum: x.datum,
        wert: v,
        aktiv: x.index === gewaehlt,
        text: `${datum(x.datum)}: ${formatiere(v, m)}`,
      };
    });
    const svg = verlauf(punkte, (v) => formatiere(v, m));
    const titel = kennzahlText(z.thema, m, z.art);
    document.getElementById("detail-verlauf").innerHTML = svg
      ? `<div class="detail-abschnitt">${esc(t("detail.verlauf", { kennzahl: titel }))}</div>${svg}`
      : "";
  }

  async function zeichneZaehlung() {
    const nr = ++ladeNr;
    const ziel = document.getElementById("detail-zaehlung");
    const x = daten.zaehlungen[gewaehlt];
    ziel.innerHTML = `<div class="pop-meta">${esc(t("detail.lade"))}</div>`;
    let d;
    try {
      d = (await ladeDetails(manifest, stelle.chunk)).zaehlungen[String(gewaehlt)];
    } catch (err) {
      if (nr === ladeNr) ziel.innerHTML = `<div class="pop-meta">${esc(t("detail.ladefehler", { fehler: err.message }))}</div>`;
      return;
    }
    if (nr !== ladeNr || !d) return;
    const verfuegbar = Object.keys(ANSICHTEN).filter((a) => hat(x, a));
    if (!verfuegbar.includes(ansicht)) ansicht = verfuegbar[0];
    const chips = d.stunden
      ? verfuegbar.map((a) => `<button type="button" class="legend-chip${a === ansicht ? " is-active" : ""}" data-ansicht="${a}" aria-pressed="${a === ansicht}">${esc(GRUPPEN_NAMEN[a])}</button>`).join("")
      : "";
    // Quellen ohne Stundenreihe (Potsdam): Spitzenstunden und Summe über das Zählfenster
    const spitzen = d.spitzen ?? [];
    const zeit = (m) => (m % 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, "0")}` : `${m / 60}`);

    const reihen = ANSICHTEN[ansicht]?.filter((g) => d.stunden?.[g]).map((g, i) => ({
      id: g, name: GRUPPEN_NAMEN[g], farbe: i === 0 ? SERIE_1 : SERIE_2, stunden: proStunde(d.h0, d.stunden[g]),
    })) ?? [];
    const tg = reihen.length ? tagesgang(reihen) : null;
    const legende = reihen.length > 1
      ? `<div class="tg-legende">${reihen.map((r) => `<span><i style="background:${r.farbe}"></i>${esc(r.name)}</span>`).join("")}</div>`
      : "";

    const kennzeilen = GRUPPEN.filter((g) => hat(x, g)).map((g) => {
      const st = d.stunden?.[g] ? proStunde(d.h0, d.stunden[g]) : null;
      let spitze = "–";
      if (st) {
        let hm = -1;
        st.forEach((v, h) => { if (v != null && (hm < 0 || v > st[hm])) hm = h; });
        if (hm >= 0) spitze = `${zahl(st[hm])} <span class="pop-unit">${esc(uhr(`${hm}–${hm + 1}`))}</span>`;
      } else {
        // nur für die Gruppe, nach der die Spitzenstunden bestimmt sind (wie `sp` in index.json)
        const s = spitzen.filter((p) => p.nach === g && p.werte?.[g] != null)
          .reduce((a, p) => (a && a.werte[g] >= p.werte[g] ? a : p), null);
        if (s) spitze = `${zahl(s.werte[g])} <span class="pop-unit">${esc(uhr(`${zeit(s.von)}–${zeit(s.bis)}`))}</span>`;
      }
      const f = (v) => (v == null ? "–" : zahl(v));
      return `<tr><td>${esc(GRUPPEN_NAMEN[g])}</td><td>${f(wert(x, g, "w"))}</td><td>${f(wert(x, g, "w24"))}</td><td>${spitze}</td></tr>`;
    });

    const zpGruppen = GRUPPEN.filter((g) => spitzen.some((p) => p.werte?.[g] != null) || d.fenstersummen?.[g] != null);
    const zpZeilen = [
      ...spitzen.map((p) => ({ name: `${name(p.name)} ${uhr(`${zeit(p.von)}–${zeit(p.bis)}`)}`, werte: p.werte })),
      ...(d.fenstersummen ? [{ name: t("detail.summe_fenster", { fenster: uhr(x.fenster) }), werte: d.fenstersummen }] : []),
    ];
    const nach = spitzen[0]?.nach;
    const zaehlplan = zpZeilen.length ? `
      <div class="detail-abschnitt">${esc(t("detail.zaehlplan"))}</div>
      <table class="pop-table detail-zaehlplan">
        <thead><tr><td></td>${zpGruppen.map((g) => `<td>${esc(GRUPPEN_NAMEN[g])}</td>`).join("")}</tr></thead>
        <tbody>${zpZeilen.map((r) => `<tr><td>${esc(r.name)}</td>${zpGruppen.map((g) => `<td>${r.werte?.[g] == null ? "–" : zahl(r.werte[g])}</td>`).join("")}</tr>`).join("")}</tbody>
      </table>
      ${nach && zpGruppen.length > 1 ? `<div class="pop-meta">${esc(t("detail.spitze_nach", { gruppe: GRUPPEN_NAMEN[nach] }))}</div>` : ""}` : "";
    const lz = lizenz(x);
    const hinweise = (d.hinweise ?? []).map((h) => `<li>${esc(h)}</li>`).join("");
    const tagText = [TAGE[x.tag ?? "u"], d.tagname ? name(d.tagname) : null].filter(Boolean).join(": ");
    const ohneStunden = d.summen ? "detail.nur_summen" : zpZeilen.length ? "detail.nur_zaehlplan" : "detail.keine_stunden";
    ziel.innerHTML = `
      <div class="detail-abschnitt">${esc(t("detail.zaehlung_vom", { wochentag: wochentag(x.datum), datum: datum(x.datum), tag: tagText }))}</div>
      ${chips ? `<div class="pop-chips">${chips}</div>` : ""}
      ${tg ? `<div class="tg-wrap">${tg.svg}<div class="tg-tooltip" hidden></div></div>${legende}
      <div class="pop-meta">${esc(t("detail.je_stunde", { fenster: uhr(x.fenster) }))}</div>`
      : `<div class="pop-meta">${esc(t(ohneStunden))}</div>`}
      <table class="pop-table detail-kennwerte">
        <thead><tr><td></td><td>${esc(t("art.w"))}</td><td>${esc(t("art.w24_kurz"))}</td><td>${esc(t("art.sp"))}</td></tr></thead>
        <tbody>${kennzeilen.join("")}</tbody>
      </table>
      ${zaehlplan}
      ${d.bemerkung ? `<div class="detail-abschnitt">${esc(t("detail.bemerkung"))}</div><div class="pop-meta" lang="de">${esc(d.bemerkung)}</div>` : ""}
      ${hinweise ? `<div class="detail-abschnitt">${esc(t("detail.hinweise"))}</div><ul class="detail-hinweise" lang="de">${hinweise}</ul>` : ""}
      <div class="detail-abschnitt">${esc(t("detail.herkunft"))}</div>
      <table class="pop-table">
        <tr><td>${esc(t("detail.kennung"))}</td><td>${esc(d.kennung)}</td></tr>
        ${d.kategorien ? `<tr><td>${esc(t("detail.kategorien"))}</td><td lang="de">${esc(d.kategorien)}</td></tr>` : ""}
        ${d.richtungen ? `<tr><td>${esc(t("detail.richtungen"))}</td><td>${d.richtungen}</td></tr>` : ""}
        ${d.intervall ? `<tr><td>${esc(t("detail.intervall"))}</td><td>${esc(t("detail.minuten", { n: d.intervall }))}</td></tr>` : ""}
        <tr><td>${esc(t("detail.quelle"))}</td><td lang="de">${esc(lz.titel ?? "")}${lz.herausgeber ? `, ${esc(lz.herausgeber)}` : ""}</td></tr>
        <tr><td>${esc(t("detail.lizenz"))}</td><td>${lz.lizenz_url ? `<a href="${esc(lz.lizenz_url)}" target="_blank" rel="noopener">${esc(lz.lizenz)}</a>` : esc(lz.lizenz ?? "")}</td></tr>
      </table>
      <div class="pop-foot detail-links">
        ${d.rohdatei ? `<a href="${esc(d.rohdatei)}" target="_blank" rel="noopener">${esc(t("detail.rohdatei"))}</a>` : ""}
        ${lz.herkunft_url ? `<a href="${esc(lz.herkunft_url)}" target="_blank" rel="noopener">${esc(t("detail.herkunft_link"))}</a>` : ""}
        ${d.stunden ? `<button type="button" class="link-knopf" data-csv>${esc(t("detail.csv"))}</button>` : ""}
      </div>`;
    if (tg) bindeHover(ziel.querySelector(".tg-wrap"), reihen, tg);
  }

  function bindeHover(wrap, reihen, tg) {
    const svg = wrap.querySelector("svg");
    const kreuz = svg.querySelector(".tg-kreuz");
    const tip = wrap.querySelector(".tg-tooltip");
    const zeige = (clientX) => {
      const box = svg.getBoundingClientRect();
      const sx = ((clientX - box.left) / box.width) * TG.breite;
      const h = Math.max(0, Math.min(23, Math.floor(((sx - TG.l) / (TG.breite - TG.l - TG.r)) * 24)));
      const xx = tg.x(h + 0.5);
      kreuz.setAttribute("x1", xx);
      kreuz.setAttribute("x2", xx);
      kreuz.setAttribute("visibility", "visible");
      tip.replaceChildren();
      const kopf = document.createElement("div");
      kopf.className = "tg-tip-kopf";
      kopf.textContent = uhr(`${h}–${h + 1}`);
      tip.append(kopf);
      for (const r of reihen) {
        const zeile = document.createElement("div");
        const strich = document.createElement("i");
        strich.style.background = r.farbe;
        const b = document.createElement("b");
        b.textContent = r.stunden[h] == null ? t("detail.nicht_gezaehlt") : zahl(r.stunden[h]);
        zeile.append(strich, b, document.createTextNode(` ${r.name}`));
        tip.append(zeile);
      }
      tip.hidden = false;
      const links = (xx / TG.breite) * box.width;
      tip.style.left = `${Math.min(box.width - 120, Math.max(0, links + 8))}px`;
    };
    svg.addEventListener("pointermove", (e) => zeige(e.clientX));
    svg.addEventListener("pointerleave", () => {
      kreuz.setAttribute("visibility", "hidden");
      tip.hidden = true;
    });
  }

  async function ladeCsv() {
    const x = daten.zaehlungen[gewaehlt];
    const d = (await ladeDetails(manifest, stelle.chunk)).zaehlungen[String(gewaehlt)];
    const gruppen = GRUPPEN.filter((g) => d.stunden?.[g]);
    const kopf = ["stunde", ...gruppen];
    const zeilen = [kopf.join(";")];
    const reihen = gruppen.map((g) => proStunde(d.h0, d.stunden[g]));
    for (let h = 0; h < 24; h += 1) {
      if (reihen.every((r) => r[h] == null)) continue;
      zeilen.push([`${h}-${h + 1}`, ...reihen.map((r) => r[h] ?? "")].join(";"));
    }
    const lz = lizenz(x);
    const von = `${lz.titel ?? ""}${lz.herausgeber ? `, ${lz.herausgeber}` : ""}`;
    zeilen.push("", `# ${stelle.name}; ${x.datum}; ${t("csv.quelle", { von, lizenz: lz.lizenz ?? "" })}`);
    const blob = new Blob([`﻿${zeilen.join("\n")}\n`], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `zaehlung_${d.kennung}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  return {
    zeige,
    schliesse,
    aktualisiere() { if (stelle) { zeichneKopf(); zeichneZaehlung(); } },
    get stelle() { return stelle; },
    get zaehlung() { return gewaehlt; },
  };
}
