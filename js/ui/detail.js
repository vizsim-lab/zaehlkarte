// detail.js — Seitenleiste einer Stelle: alle Zählungen, Tagesgang der gewählten Zählung,
// Kennwerte, Schulweg-Kriterium, Herkunft und Lizenz, CSV der Stundenwerte.
//
// Texte aus den Daten (Namen, Bemerkungen) sind fremd: immer über esc() ins HTML.
import { ladeDetails } from "../data/laden.js";
import {
  ARTEN, GRUPPEN, GRUPPEN_NAMEN, STATUS_NAMEN, STATUSFARBEN, TAGE, bewerte, formatiere, hat, kennwert, wert,
} from "../data/modell.js";
import { proStunde, tagesgang, TG, verlauf } from "./diagramme.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const zahl = new Intl.NumberFormat("de-DE");
const SERIE_1 = "#2a78d6";
const SERIE_2 = "#eb6834";
const ANSICHTEN = {
  kfz: { name: "Kfz", reihen: ["kfz", "sv"] },
  rad: { name: "Rad", reihen: ["rad"] },
  fuss: { name: "Fuß", reihen: ["fuss", "kind"] },
};
const LAGE_TEXT = {
  gps: "Koordinaten aus der Zähldatei",
  quelle: "Koordinaten der Quelle",
  geokodiert: "aus den Straßennamen verortet (OpenStreetMap)",
  uebertragen: "von Zählungen derselben Zählstellen-Kennung übernommen",
};

function datumText(iso) {
  if (!iso) return "ohne Datum";
  const [j, m, t] = iso.split("-");
  return `${t}.${m}.${j}`;
}

function wochentag(iso) {
  return iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("de-DE", { weekday: "short" }) : "";
}

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
    ansicht = z.thema;
    el.hidden = false;
    document.body.classList.add("detail-offen");
    zeichneKopf();
    zeichneZaehlung();
  }

  function schliesse() {
    if (el.hidden) return;
    el.hidden = true;
    stelle = null;
    document.body.classList.remove("detail-offen");
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
    const typ = stelle.typ === "K" ? "Knotenpunkt" : stelle.typ === "Q" ? "Querschnitt" : "Zählstelle";
    const kennung = stelle.id.split(":").slice(1).join(":");
    const zeilen = [...stelle.zaehlungen].reverse().map((x) => {
      const zellen = ["kfz", "rad", "fuss"].map((g) => {
        if (!hat(x, g)) return "<td class=\"is-leer\">–</td>";
        const v = wert(x, g, z.art);
        return `<td>${v == null ? "<span class=\"pop-hint\" data-tip=\"in diesem Zeitraum nicht vollständig gezählt\">·</span>" : zahl.format(v)}</td>`;
      });
      const aktiv = x.index === gewaehlt ? " is-aktiv" : "";
      return `<tr class="dz-zeile${aktiv}" data-zaehlung="${x.index}" tabindex="0">
        <td>${datumText(x.datum)}</td><td class="dz-tag">${esc(TAGE[x.tag ?? "u"])}</td><td>${esc(x.fenster)}</td>${zellen.join("")}</tr>`;
    });
    el.innerHTML = `
      <header class="detail-kopf">
        <div>
          <div class="pop-eyebrow">${esc(typ)} · ${esc(q.name)} · ${esc(kennung)}</div>
          <h2 class="detail-titel">${esc(stelle.name)}</h2>
          <div class="pop-meta">${stelle.zaehlungen.length === 1 ? "eine Zählung" : `${stelle.zaehlungen.length} Zählungen`} · Lage ${esc(LAGE_TEXT[stelle.lage] ?? stelle.lage)}</div>
        </div>
        <button class="detail-zu" data-schliessen aria-label="Schließen" type="button">×</button>
      </header>
      <div class="detail-verlauf" id="detail-verlauf"></div>
      <div class="detail-tabelle-wrap">
        <table class="detail-tabelle">
          <thead><tr><th>Datum</th><th>Tag</th><th>Uhr</th><th>Kfz</th><th>Rad</th><th>Fuß</th></tr></thead>
          <tbody>${zeilen.join("")}</tbody>
        </table>
        <div class="pop-meta">Werte: Summe ${esc(ARTEN[z.art])}, alle Richtungen</div>
      </div>
      <section class="detail-zaehlung" id="detail-zaehlung" aria-live="polite"></section>`;
    zeichneVerlauf();
  }

  function zeichneVerlauf() {
    const z = gibZustand();
    const modus = z.modus[z.thema];
    const m = modus === "verdacht" ? "menge" : modus;
    const punkte = stelle.zaehlungen.filter((x) => x.datum).map((x) => {
      const v = kennwert(x, z.thema, m, z.art);
      return {
        datum: x.datum,
        wert: v,
        aktiv: x.index === gewaehlt,
        text: `${datumText(x.datum)}: ${formatiere(v, m)}`,
      };
    });
    const svg = verlauf(punkte, (v) => formatiere(v, m));
    const titel = m === "menge" ? `${GRUPPEN_NAMEN[z.thema]} (${ARTEN[z.art]})` : (m === "svanteil" ? "Schwerverkehrsanteil" : "Radanteil");
    document.getElementById("detail-verlauf").innerHTML = svg
      ? `<div class="detail-abschnitt">Verlauf an dieser Stelle · ${esc(titel)}</div>${svg}`
      : "";
  }

  async function zeichneZaehlung() {
    const nr = ++ladeNr;
    const ziel = document.getElementById("detail-zaehlung");
    const x = daten.zaehlungen[gewaehlt];
    ziel.innerHTML = `<div class="pop-meta">Lade Stundenwerte …</div>`;
    let d;
    try {
      d = (await ladeDetails(manifest, stelle.chunk)).zaehlungen[String(gewaehlt)];
    } catch (err) {
      if (nr === ladeNr) ziel.innerHTML = `<div class="pop-meta">Stundenwerte nicht ladbar (${esc(err.message)})</div>`;
      return;
    }
    if (nr !== ladeNr || !d) return;
    const z = gibZustand();
    const verfuegbar = Object.keys(ANSICHTEN).filter((a) => hat(x, a));
    if (!verfuegbar.includes(ansicht)) ansicht = verfuegbar[0];
    const chips = verfuegbar.map((a) => `<button type="button" class="legend-chip${a === ansicht ? " is-active" : ""}" data-ansicht="${a}" aria-pressed="${a === ansicht}">${ANSICHTEN[a].name}</button>`).join("");

    const reihen = ANSICHTEN[ansicht]?.reihen.filter((g) => d.stunden?.[g]).map((g, i) => ({
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
        if (hm >= 0) spitze = `${zahl.format(st[hm])} <span class="pop-unit">${hm}–${hm + 1} Uhr</span>`;
      }
      const f = (v) => (v == null ? "–" : zahl.format(v));
      return `<tr><td>${esc(GRUPPEN_NAMEN[g])}</td><td>${f(wert(x, g, "w"))}</td><td>${f(wert(x, g, "w24"))}</td><td>${spitze}</td></tr>`;
    });

    let schulweg = "";
    if (hat(x, "kind") || (z.thema === "fuss" && hat(x, "fuss"))) {
      const b = bewerte(x, z.kriterien);
      const k = z.kriterien;
      const grund = b.gruende.length ? b.gruende.map(esc).join(" · ") : "keine Schwelle überschritten";
      const farbe = STATUSFARBEN[b.status] ?? "#c3c7cc";
      schulweg = `<div class="detail-abschnitt">Schulweg-Kriterium</div>
        <div class="dz-status"><span class="pop-pill" style="--pill-dot:${farbe}">${esc(STATUS_NAMEN[b.status])}</span>
        <span class="pop-meta">${grund}</span></div>
        <div class="pop-meta">Verdacht, wenn um ${k.schulstunden.join(", ")} Uhr mehr als ${k.schwelle_stunde} oder von ${k.tag_von} bis ${k.tag_bis} Uhr mehr als ${k.schwelle_tag} Kinder/Jugendliche gezählt sind – nie an schulfreien Tagen. Eigene Heuristik, keine amtliche Einstufung.</div>`;
    }

    const lz = lizenz(x);
    const hinweise = (d.hinweise ?? []).map((h) => `<li>${esc(h)}</li>`).join("");
    const tagText = [TAGE[x.tag ?? "u"], d.tagname].filter(Boolean).join(": ");
    ziel.innerHTML = `
      <div class="detail-abschnitt">Zählung vom ${wochentag(x.datum)} ${datumText(x.datum)} · ${esc(tagText)}</div>
      <div class="pop-chips">${chips}</div>
      ${tg ? `<div class="tg-wrap">${tg.svg}<div class="tg-tooltip" hidden></div></div>${legende}
      <div class="pop-meta">je Stunde, alle Richtungen · grau hinterlegt: gezählte Stunden (${esc(x.fenster)} Uhr)</div>`
      : `<div class="pop-meta">${d.summen ? "Nur Tagessummen geliefert (keine Stundenwerte)." : "Für diese Gruppe keine Stundenwerte."}</div>`}
      <table class="pop-table detail-kennwerte">
        <thead><tr><td></td><td>7–19 Uhr</td><td>24 h</td><td>stärkste Stunde</td></tr></thead>
        <tbody>${kennzeilen.join("")}</tbody>
      </table>
      ${schulweg}
      ${d.bemerkung ? `<div class="detail-abschnitt">Bemerkung</div><div class="pop-meta">${esc(d.bemerkung)}</div>` : ""}
      ${hinweise ? `<div class="detail-abschnitt">Hinweise</div><ul class="detail-hinweise">${hinweise}</ul>` : ""}
      <div class="detail-abschnitt">Herkunft</div>
      <table class="pop-table">
        <tr><td>Kennung</td><td>${esc(d.kennung)}</td></tr>
        ${d.kategorien ? `<tr><td>Kategorien</td><td>${esc(d.kategorien)}</td></tr>` : ""}
        ${d.richtungen ? `<tr><td>Richtungen</td><td>${d.richtungen}</td></tr>` : ""}
        ${d.intervall ? `<tr><td>Intervall</td><td>${d.intervall} Minuten</td></tr>` : ""}
        <tr><td>Quelle</td><td>${esc(lz.titel ?? "")}${lz.herausgeber ? `, ${esc(lz.herausgeber)}` : ""}</td></tr>
        <tr><td>Lizenz</td><td>${lz.lizenz_url ? `<a href="${esc(lz.lizenz_url)}" target="_blank" rel="noopener">${esc(lz.lizenz)}</a>` : esc(lz.lizenz ?? "")}</td></tr>
      </table>
      <div class="pop-foot detail-links">
        ${d.rohdatei ? `<a href="${esc(d.rohdatei)}" target="_blank" rel="noopener">Rohdatei →</a>` : ""}
        ${lz.herkunft_url ? `<a href="${esc(lz.herkunft_url)}" target="_blank" rel="noopener">Herkunft →</a>` : ""}
        ${d.stunden ? `<button type="button" class="link-knopf" data-csv>Stundenwerte als CSV</button>` : ""}
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
      kopf.textContent = `${h}–${h + 1} Uhr`;
      tip.append(kopf);
      for (const r of reihen) {
        const zeile = document.createElement("div");
        const strich = document.createElement("i");
        strich.style.background = r.farbe;
        const b = document.createElement("b");
        b.textContent = r.stunden[h] == null ? "nicht gezählt" : zahl.format(r.stunden[h]);
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
    zeilen.push("", `# ${stelle.name}; ${x.datum}; Quelle: ${lz.titel ?? ""} (${lz.lizenz ?? ""}) – über vizsim-lab/zaehlkarte`);
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
