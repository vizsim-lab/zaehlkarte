// legende.js — die Legende rechts: Verkehrsart, Darstellung, Kennzahl, Klassen mit Zählern,
// Filter, Datenlage, Quellen. Setzt nur ZUSTAND und ruft `geaendert()`; was die Karte daraus
// macht, entscheidet main.js.
//
// data-tip nur an reinen Hinweis-Zeichen (ⓘ), nie an Bedienelementen: der Tooltip fängt
// Klicks darauf ab (Touch-Bedienung, js/ui/tooltip.js). Knöpfe tragen `title`.
import { ARTEN, STUFENFARBEN, TAGE, THEMEN, kennzahlText, stufenFuer, stufenText } from "../data/modell.js";
import { DATENLAGE_KLASSEN } from "../map/ebenen.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const zahl = new Intl.NumberFormat("de-DE");
const $ = (id) => document.getElementById(id);

const MODUS_TIPS = {
  "sv.anteil": "Schwerverkehr (Lkw, Lastzüge, Busse) geteilt durch alle Kfz – nur, wo beides gezählt ist.",
  "rad.anteil": "Radfahrende geteilt durch Radfahrende + Kfz – nur, wo auch Kfz gezählt sind.",
};

function setzeChips(container, attr, wert) {
  container.querySelectorAll(`[data-${attr}]`).forEach((b) => {
    const an = b.dataset[attr] === wert;
    b.classList.toggle("is-active", an);
    b.setAttribute("aria-checked", String(an));
  });
}

export function erstelleLegende({ manifest, daten, zustand, geaendert, datenlage }) {
  const legende = $("legend");

  // Ein-/Ausklappen: Wurzel und Abschnitte (Zustand als Klasse, CSS entscheidet)
  legende.addEventListener("click", (e) => {
    const kopf = e.target.closest("[data-toggle]");
    if (!kopf || e.target.closest("input, label, .info-icon")) return;
    const ziel = kopf.dataset.toggle === "legend-root" ? legende : kopf.closest(".legend-section");
    const zu = ziel.classList.toggle("collapsed");
    const pfeil = kopf.querySelector(".toggle-arrow");
    pfeil?.classList.toggle("open", !zu);
    pfeil?.setAttribute("aria-expanded", String(!zu));
  });
  if (legende.classList.contains("collapsed")) {
    legende.querySelector(".toggle-root")?.classList.remove("open");
  }

  for (const [id, feld] of [["thema-chips", "thema"], ["modus-chips", "modus"], ["art-chips", "art"]]) {
    $(id).addEventListener("click", (e) => {
      const b = e.target.closest(`[data-${feld}]`);
      if (!b) return;
      if (feld === "modus") zustand.modus[zustand.thema] = b.dataset.modus;
      else zustand[feld] = b.dataset[feld];
      zeichne();
      geaendert();
    });
  }

  // Jahre: zwei Regler übereinander
  const von = $("jahr-von");
  const bis = $("jahr-bis");
  for (const r of [von, bis]) {
    r.min = daten.jahre[0];
    r.max = daten.jahre[1];
    r.step = 1;
  }
  const jahre = (e) => {
    let a = Number(von.value);
    let b = Number(bis.value);
    if (a > b) {
      if (e?.target === von) b = a; else a = b;
    }
    zustand.jahre = [a, b];
    zeichneJahre();
    geaendert();
  };
  von.addEventListener("input", jahre);
  bis.addEventListener("input", jahre);

  // Zähltage
  $("tage-liste").innerHTML = Object.entries(TAGE).map(([k, name]) => `
    <label class="legend-item legend-item--check"><span class="label-wrapper">
      <input type="checkbox" data-tag="${k}"> ${esc(name)}</span><span class="count-badge" id="tag-n-${k}">0</span></label>`).join("");
  $("tage-liste").addEventListener("change", (e) => {
    const t = e.target.dataset.tag;
    if (!t) return;
    if (e.target.checked) zustand.tage.add(t); else zustand.tage.delete(t);
    geaendert();
  });

  // Quellen
  $("quellen-liste").innerHTML = manifest.quellen.map((q) => `
    <label class="legend-item legend-item--check"><span class="label-wrapper">
      <input type="checkbox" data-quelle="${esc(q.code)}"> ${esc(q.name)}</span><span class="count-badge" id="quelle-n-${esc(q.code)}">0</span></label>`).join("");
  $("quellen-liste").addEventListener("change", (e) => {
    const q = e.target.dataset.quelle;
    if (!q) return;
    if (e.target.checked) zustand.quellen.add(q); else zustand.quellen.delete(q);
    geaendert();
  });
  $("toggle-uebertragen").addEventListener("change", (e) => {
    zustand.uebertragen = e.target.checked;
    geaendert();
  });

  // Datenlage
  const anzahl = Object.fromEntries(DATENLAGE_KLASSEN.map((k) => [k.id, datenlage.features.filter((f) => k.stand.includes(f.properties.stand)).length]));
  $("datenlage-legende").innerHTML = DATENLAGE_KLASSEN.map((k) => `
    <div class="legend-item"><span class="label-wrapper"><span class="punkt" style="background:${k.farbe}"></span>${esc(k.name)}</span>
    <span class="count-badge">${anzahl[k.id]}</span></div>`).join("");
  $("toggle-datenlage").addEventListener("change", (e) => {
    zustand.datenlage = e.target.checked;
    geaendert();
  });

  // Quellen & Lizenzen aus dem Manifest
  $("quellen-text").innerHTML = manifest.quellen.map((q) => `
    <div class="quelle-eintrag">
      <div class="quelle-name">${esc(q.name)} <span class="pop-meta">${zahl.format(q.zaehlungen)} Zählungen an ${zahl.format(q.stellen)} Stellen${q.von ? `, ${q.von}–${q.bis}` : ""}</span></div>
      <div class="pop-meta">${esc(q.art ?? "")}${q.weg ? ` · ${esc(q.weg)}` : ""}</div>
      ${q.ohne_lage ? `<div class="pop-meta">${zahl.format(q.ohne_lage)} weitere Zählungen noch ohne Lage (nicht in der Karte)</div>` : ""}
      <ul>${q.lizenzen.map((l) => `<li>${l.herkunft_url ? `<a href="${esc(l.herkunft_url)}" target="_blank" rel="noopener">${esc(l.titel)}</a>` : esc(l.titel)}${l.herausgeber ? `, ${esc(l.herausgeber)}` : ""} – ${l.lizenz_url ? `<a href="${esc(l.lizenz_url)}" target="_blank" rel="noopener">${esc(l.lizenz)}</a>` : esc(l.lizenz ?? "")}</li>`).join("")}</ul>
    </div>`).join("") + `<div class="pop-meta">Karte: © OpenStreetMap-Mitwirkende, OpenFreeMap; Relief: Mapterhorn. Stand der Daten: ${esc(manifest.erzeugt)}.</div>`;

  function zeichneJahre() {
    $("jahre-wert").textContent = zustand.jahre[0] === zustand.jahre[1]
      ? String(zustand.jahre[0]) : `${zustand.jahre[0]}–${zustand.jahre[1]}`;
  }

  /** Statische Teile nach Zustand (Chips, Regler, Häkchen). */
  function zeichne() {
    setzeChips($("thema-chips"), "thema", zustand.thema);
    const modi = Object.entries(THEMEN[zustand.thema].modi);
    $("modus-chips").hidden = modi.length < 2;
    $("modus-chips").innerHTML = modi.map(([id, m]) => {
      const tip = MODUS_TIPS[`${zustand.thema}.${id}`];
      return `<button type="button" class="legend-chip" data-modus="${id}" role="radio"${tip ? ` title="${esc(tip)}"` : ""}>${esc(m.name)}</button>`;
    }).join("");
    setzeChips($("modus-chips"), "modus", zustand.modus[zustand.thema]);
    setzeChips($("art-chips"), "art", zustand.art);
    von.value = zustand.jahre[0];
    bis.value = zustand.jahre[1];
    zeichneJahre();
    legende.querySelectorAll("[data-tag]").forEach((c) => { c.checked = zustand.tage.has(c.dataset.tag); });
    legende.querySelectorAll("[data-quelle]").forEach((c) => { c.checked = zustand.quellen.has(c.dataset.quelle); });
    $("toggle-uebertragen").checked = zustand.uebertragen;
    $("toggle-datenlage").checked = zustand.datenlage;
  }

  /** Klassenzeilen mit Zählern (nach jedem Filterwechsel). */
  function zeichneKlassen(n, zahlen) {
    const modus = zustand.modus[zustand.thema];
    const grenzen = stufenFuer(zustand.thema, modus, zustand.art);
    const zeilen = stufenText(grenzen, modus).map((name, i) => ({ farbe: STUFENFARBEN[i], name, n: n[String(i)] ?? 0, groesse: i }));
    zeilen.reverse();
    zeilen.push({
      name: `nicht in „${ARTEN[zustand.art]}“ gezählt`,
      n: n["-1"] ?? 0,
      hohl: true,
      tip: "Gezählt, aber nicht in diesem Zeitfenster – etwa nur 15–19 Uhr statt 7–19 Uhr. Klick zeigt den Tagesgang.",
    });
    $("klassen-legende").innerHTML = `<div class="legend-hint legend-hint--titel">${esc(kennzahlText(zustand.thema, modus, zustand.art))}</div>` + zeilen.map((z) => `
      <div class="legend-item"><span class="label-wrapper">
        <span class="punkt${z.hohl ? " punkt--hohl" : ""}" style="${z.farbe ? `background:${z.farbe};` : ""}${z.groesse != null ? `--g:${z.groesse}` : ""}"></span>
        ${esc(z.name)}${z.tip ? ` <span class="info-icon" data-tip="${esc(z.tip)}">i</span>` : ""}</span>
        <span class="count-badge">${zahl.format(z.n)}</span></div>`).join("");
    $("fc-stellen").textContent = zahl.format(zahlen.stellen);
    $("fc-zaehlungen").textContent = zahl.format(zahlen.zaehlungen);
    for (const [k, v] of Object.entries(zahlen.tage)) {
      const el = $(`tag-n-${k}`);
      if (el) el.textContent = zahl.format(v);
    }
    for (const [k, v] of Object.entries(zahlen.quellen)) {
      const el = $(`quelle-n-${k}`);
      if (el) el.textContent = zahl.format(v);
    }
  }

  zeichne();
  return { zeichne, zeichneKlassen };
}
