// dauerdetail.js — Seitenleiste einer Dauerzählstelle: Tagessummen über die ganze Reihe,
// Tagesgang des gewählten Tags, Herkunft, Lizenz und CSV.
//
// Nur gezählte Werte: eine Tagessumme gibt es nur, wenn jede Stunde des Tages gezählt ist;
// sonst steht da, wie viele Stunden fehlen. Texte aus den Daten (Straßen, Richtungen,
// Hinweise der Stammdaten) sind fremd: immer über esc() ins HTML, lang="de".
import { ladeDauer } from "../data/laden.js";
import {
  DAUER_GRUPPEN, DAUER_THEMEN, hatGruppe, plusTage, stundenAm, stundenDesTags, tagAusDetail, tageZwischen, tagtyp,
  zeitraumText,
} from "../data/dauer.js";
import { TAGE } from "../data/modell.js";
import { datum, t, uhr, wochentag, zahl } from "../sprache/texte.js";
import { TG, TR_FARBEN, tagesgang, tagesreihe } from "./diagramme.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
// Farben der Reihen im Tagesgang nach Reihenfolge der Gruppen der Stelle (wie bei den
// Kurzzeitzählungen: erste Reihe blau, zweite orange)
const FARBEN = ["#2a78d6", "#eb6834", "#1f9e6e", "#8a5cd1"];

export function erstelleDauerDetail({ gibDauer, gibZustand, gibTag, beiTag, beiSchliessen }) {
  const el = document.getElementById("dauer-detail");
  let stelle = null;
  let detail = null;
  let fehler = null;
  let ladeNr = 0;

  el.addEventListener("click", (e) => {
    if (e.target.closest("[data-schliessen]")) { schliesse(); return; }
    if (e.target.closest("[data-csv-tage]")) { csvTage(); return; }
    if (e.target.closest("[data-csv-stunden]")) csvStunden();
  });

  async function zeige(s) {
    stelle = s;
    detail = null;
    fehler = null;
    el.hidden = false;
    const nr = ++ladeNr;
    zeichne();
    try {
      const d = gibDauer();
      const chunk = await ladeDauer(d.dateien.details.replace("{n}", String(s.chunk)));
      if (nr !== ladeNr) return;
      detail = chunk.stellen[s.id] ?? null;
    } catch (err) {
      if (nr !== ladeNr) return;
      fehler = err.message;
    }
    zeichne();
  }

  function schliesse() {
    if (el.hidden) return;
    el.hidden = true;
    stelle = null;
    detail = null;
    ladeNr += 1;
    beiSchliessen?.();
  }

  const quelle = (d) => d.quellenMeta.find((q) => q.code === stelle.quelle);

  function zeichne() {
    if (!stelle) return;
    const d = gibDauer();
    const z = gibZustand();
    const tag = gibTag();
    const q = quelle(d);
    const kopf = `
      <header class="detail-kopf">
        <div>
          <div class="pop-eyebrow">${esc(t("dd.typ"))} · ${esc(q?.name ?? stelle.quelle)} · ${esc(stelle.id.split(":").slice(1).join(":"))}</div>
          <h2 class="detail-titel">${esc(stelle.name)}</h2>
          <div class="pop-meta" lang="de">${esc([stelle.abschnitt, stelle.richtung].filter(Boolean).join(" · "))}</div>
        </div>
        <button class="detail-zu" data-schliessen aria-label="${esc(t("schliessen"))}" type="button">×</button>
      </header>`;
    if (!detail) {
      el.innerHTML = `${kopf}<div class="pop-meta">${esc(fehler ? t("detail.ladefehler", { fehler }) : t("detail.lade"))}</div>`;
      return;
    }
    const g = hatGruppe(stelle, z.dthema) ? z.dthema : stelle.gruppen[0];
    const werte = detail.tage[g] ?? [];
    const kal = d.kalender?.[q?.land] ?? "";
    const ab = tageZwischen(d.von, detail.von);
    const typen = kal.slice(ab, ab + werte.length);
    const gewaehlt = tageZwischen(detail.von, tag);
    const tr = tagesreihe(werte, typen, detail.von, gewaehlt);
    const reihe = tr.svg ? `
      <div class="detail-abschnitt">${esc(t("dd.reihe", { gruppe: DAUER_THEMEN[g].name, zeitraum: zeitraumText(stelle.von, stelle.bis) }))}</div>
      <div class="tr-wrap">${tr.svg}<div class="tg-tooltip" hidden></div></div>
      <div class="tr-legende">
        <span><i style="background:${TR_FARBEN.s}"></i>${esc(TAGE.s)}</span>
        <span><i style="background:${TR_FARBEN.f}"></i>${esc(TAGE.f)}</span>
        <span><i style="background:${TR_FARBEN.w}"></i>${esc(t("dd.legende.w"))}</span>
      </div>
      <div class="pop-meta">${esc(t("dd.reihe_hinweis"))}</div>` : "";

    // der gewählte Tag
    const typ = tagtyp(d, q?.land, tag);
    let tagTeil;
    let stunden = null; // { reihen, tg }, wenn es Stundenwerte des Tags gibt
    if (tag < stelle.von || tag > stelle.bis) {
      tagTeil = `<div class="pop-meta">${esc(t("dd.ausserhalb", { datum: datum(tag), von: datum(stelle.von), bis: datum(stelle.bis) }))}</div>`;
    } else {
      const gruppen = DAUER_GRUPPEN.filter((x) => hatGruppe(stelle, x));
      const reihen = gruppen.map((x, i) => ({ id: x, name: DAUER_THEMEN[x].name, farbe: FARBEN[i], stunden: stundenAm(detail, x, tag) }))
        .filter((r) => r.stunden);
      const tg = reihen.length ? tagesgang(reihen) : null;
      const soll = stundenDesTags(tag);
      const zeilen = gruppen.map((x) => {
        const { wert, stunden } = tagAusDetail(detail, x, tag);
        const text = wert != null ? zahl(wert) : t(stunden ? "dd.unvollstaendig" : "dd.nicht_gezaehlt", { n: zahl(stunden), soll });
        return `<tr><td>${esc(DAUER_THEMEN[x].name)}</td><td${wert == null ? ' class="is-leer"' : ""}>${esc(text)}</td></tr>`;
      }).join("");
      const hinweise = [
        detail.doppelt?.includes(tag) ? t("dd.doppelt") : null,
        soll === 23 ? t("dd.sommerzeit") : null,
      ].filter(Boolean);
      tagTeil = `
        ${tg ? `<div class="tg-wrap">${tg.svg}<div class="tg-tooltip" hidden></div></div>
          ${reihen.length > 1 ? `<div class="tg-legende">${reihen.map((r) => `<span><i style="background:${r.farbe}"></i>${esc(r.name)}</span>`).join("")}</div>` : ""}
          <div class="pop-meta">${esc(t("dd.stunden"))}</div>`
        : `<div class="pop-meta">${esc(t("dd.ohne_stunden", { datum: datum(detail.stunden_von) }))}</div>`}
        <table class="pop-table detail-kennwerte"><thead><tr><td></td><td>${esc(t("dd.summe"))}</td></tr></thead><tbody>${zeilen}</tbody></table>
        ${hinweise.map((h) => `<div class="pop-meta">${esc(h)}</div>`).join("")}`;
      if (tg) stunden = { reihen, tg };
    }

    const lz = q?.lizenzen?.[0] ?? {};
    const verfahren = (q?.verfahren ?? []).find((v) => v.von <= tag && tag <= v.bis) ?? (q?.verfahren ?? []).at(-1);
    const hinweise = [...(detail.hinweise ?? []), ...(q?.hinweise ?? [])].map((h) => `<li>${esc(h)}</li>`).join("");
    el.innerHTML = `${kopf}
      ${reihe}
      <section class="detail-tag" aria-live="polite">
        <div class="detail-abschnitt">${esc(t("dd.tag", { wochentag: wochentag(tag), datum: datum(tag), tag: TAGE[typ] }))}</div>
        ${tagTeil}
      </section>
      ${hinweise ? `<div class="detail-abschnitt">${esc(t("detail.hinweise"))}</div><ul class="detail-hinweise" lang="de">${hinweise}</ul>` : ""}
      <div class="detail-abschnitt">${esc(t("detail.herkunft"))}</div>
      <table class="pop-table">
        <tr><td>${esc(t("detail.kennung"))}</td><td>${esc(detail.kennung)}</td></tr>
        ${stelle.richtung ? `<tr><td>${esc(t("dd.richtung"))}</td><td lang="de">${esc(stelle.richtung)}</td></tr>` : ""}
        ${detail.fahrstreifen?.length ? `<tr><td>${esc(t("dd.fahrstreifen"))}</td><td lang="de">${detail.fahrstreifen.map(esc).join("<br>")}</td></tr>` : ""}
        <tr><td>${esc(t("dd.zeitraum"))}</td><td>${esc(datum(stelle.von))} – ${esc(datum(stelle.bis))}</td></tr>
        ${verfahren ? `<tr><td>${esc(t("dd.verfahren"))}</td><td lang="de">${esc(verfahren.text)}</td></tr>` : ""}
        <tr><td>${esc(t("detail.quelle"))}</td><td lang="de">${esc(lz.titel ?? "")}${lz.herausgeber ? `, ${esc(lz.herausgeber)}` : ""}</td></tr>
        <tr><td>${esc(t("detail.lizenz"))}</td><td>${lz.lizenz_url ? `<a href="${esc(lz.lizenz_url)}" target="_blank" rel="noopener">${esc(lz.lizenz)}</a>` : esc(lz.lizenz ?? "")}</td></tr>
      </table>
      <div class="pop-foot detail-links">
        ${q?.archiv ? `<a href="${esc(q.archiv)}" target="_blank" rel="noopener">${esc(t("dd.archiv"))}</a>` : ""}
        ${lz.herkunft_url ? `<a href="${esc(lz.herkunft_url)}" target="_blank" rel="noopener">${esc(t("detail.herkunft_link"))}</a>` : ""}
        <button type="button" class="link-knopf" data-csv-tage>${esc(t("dd.csv_tage"))}</button>
        ${stunden ? `<button type="button" class="link-knopf" data-csv-stunden>${esc(t("dd.csv_stunden"))}</button>` : ""}
      </div>`;
    if (tr.svg) bindeReihe(el.querySelector(".tr-wrap"), werte, typen, tr);
    if (stunden) bindeTagesgang(el.querySelector(".detail-tag .tg-wrap"), stunden.reihen, stunden.tg);
  }

  /** Hover und Klick auf der Tagesreihe: Wert des Tags zeigen, Klick wählt den Tag. */
  function bindeReihe(wrap, werte, typen, tr) {
    const svg = wrap.querySelector("svg");
    const kreuz = svg.querySelector(".tg-kreuz");
    const tip = wrap.querySelector(".tg-tooltip");
    const breite = Number(svg.viewBox.baseVal.width);
    const position = (clientX) => {
      const box = svg.getBoundingClientRect();
      return tr.index(((clientX - box.left) / box.width) * breite);
    };
    svg.addEventListener("pointermove", (e) => {
      const i = position(e.clientX);
      const iso = plusTage(detail.von, i);
      const box = svg.getBoundingClientRect();
      const xx = tr.x(i);
      kreuz.setAttribute("x1", xx);
      kreuz.setAttribute("x2", xx);
      kreuz.setAttribute("visibility", "visible");
      tip.replaceChildren();
      const k = document.createElement("div");
      k.className = "tg-tip-kopf";
      k.textContent = `${wochentag(iso)} ${datum(iso)} · ${TAGE[typen[i] || "u"]}`;
      const b = document.createElement("b");
      b.textContent = werte[i] == null ? t("dauer.nicht") : zahl(werte[i]);
      tip.append(k, b);
      tip.hidden = false;
      const links = (xx / breite) * box.width;
      tip.style.left = `${Math.min(box.width - 150, Math.max(0, links + 8))}px`;
    });
    svg.addEventListener("pointerleave", () => {
      kreuz.setAttribute("visibility", "hidden");
      tip.hidden = true;
    });
    svg.addEventListener("click", (e) => beiTag?.(plusTage(detail.von, position(e.clientX))));
  }

  function bindeTagesgang(wrap, reihen, tg) {
    const svg = wrap.querySelector("svg");
    const kreuz = svg.querySelector(".tg-kreuz");
    const tip = wrap.querySelector(".tg-tooltip");
    svg.addEventListener("pointermove", (e) => {
      const box = svg.getBoundingClientRect();
      const sx = ((e.clientX - box.left) / box.width) * TG.breite;
      const h = Math.max(0, Math.min(23, Math.floor(((sx - TG.l) / (TG.breite - TG.l - TG.r)) * 24)));
      const xx = tg.x(h + 0.5);
      kreuz.setAttribute("x1", xx);
      kreuz.setAttribute("x2", xx);
      kreuz.setAttribute("visibility", "visible");
      tip.replaceChildren();
      const k = document.createElement("div");
      k.className = "tg-tip-kopf";
      k.textContent = uhr(`${h}–${h + 1}`);
      tip.append(k);
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
      tip.style.left = `${Math.min(box.width - 120, Math.max(0, (xx / TG.breite) * box.width + 8))}px`;
    });
    svg.addEventListener("pointerleave", () => {
      kreuz.setAttribute("visibility", "hidden");
      tip.hidden = true;
    });
  }

  function quellzeile() {
    const q = quelle(gibDauer());
    const lz = q?.lizenzen?.[0] ?? {};
    const von = `${lz.titel ?? ""}${lz.herausgeber ? `, ${lz.herausgeber}` : ""}`;
    return `# ${stelle.name}${stelle.richtung ? ` (${stelle.richtung})` : ""}; ${t("csv.quelle", { von, lizenz: lz.lizenz ?? "" }, "de")}`;
  }

  function lade(text, name) {
    const blob = new Blob([`﻿${text}`], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function csvTage() {
    if (!detail) return;
    const d = gibDauer();
    const q = quelle(d);
    const gruppen = DAUER_GRUPPEN.filter((x) => detail.tage[x]);
    const zeilen = [["datum", "tagtyp", ...gruppen.flatMap((x) => [`${x}_tagessumme`, `${x}_gezaehlte_stunden`])].join(";")];
    const n = detail.tage[gruppen[0]]?.length ?? 0;
    for (let i = 0; i < n; i += 1) {
      const iso = plusTage(detail.von, i);
      zeilen.push([iso, t(`tag.${tagtyp(d, q?.land, iso)}`, {}, "de"),
        ...gruppen.flatMap((x) => [detail.tage[x][i] ?? "", detail.n?.[x]?.[i] ?? 0])].join(";"));
    }
    zeilen.push("", quellzeile());
    lade(`${zeilen.join("\n")}\n`, `dauerzaehlstelle_${detail.kennung}_tage.csv`);
  }

  function csvStunden() {
    if (!detail) return;
    const tag = gibTag();
    const gruppen = DAUER_GRUPPEN.filter((x) => stundenAm(detail, x, tag));
    const reihen = gruppen.map((x) => stundenAm(detail, x, tag));
    const zeilen = [["stunde", ...gruppen].join(";")];
    for (let h = 0; h < 24; h += 1) zeilen.push([`${h}-${h + 1}`, ...reihen.map((r) => r[h] ?? "")].join(";"));
    zeilen.push("", `${quellzeile()}; ${tag}`);
    lade(`${zeilen.join("\n")}\n`, `dauerzaehlstelle_${detail.kennung}_${tag}.csv`);
  }

  return {
    zeige,
    schliesse,
    aktualisiere() { if (stelle) zeichne(); },
    get stelle() { return stelle; },
  };
}
