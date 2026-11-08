// data-tip nur an reinen Hinweis-Zeichen (ⓘ), nie an Bedienelementen: der Tooltip fängt
// Klicks darauf ab (Touch-Bedienung, js/ui/tooltip.js). Knöpfe tragen `title`.
//
// legende.js — die Legende rechts: Thema, Darstellung, Kennzahl, Klassen mit Zählern,
// Schulweg-Regler, Filter, Datenlage, Quellen. Setzt nur ZUSTAND und ruft `geaendert()`;
// was die Karte daraus macht, entscheidet main.js.
import {
  ARTEN, STATUS_NAMEN, STATUSFARBEN, STUFENFARBEN, TAGE, THEMEN, stufenFuer, stufenText,
} from "../data/modell.js";
import { DATENLAGE_KLASSEN } from "../map/ebenen.js";

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const zahl = new Intl.NumberFormat("de-DE");
const $ = (id) => document.getElementById(id);

const MODUS_TIPS = {
  svanteil: "Schwerverkehr (Lkw über 3,5 t, Lastzüge, Busse) geteilt durch alle Kfz.",
  radanteil: "Radfahrende geteilt durch Radfahrende + Kfz – nur, wo auch Kfz gezählt sind.",
  verdacht: "Viele Kinder/Jugendliche zu Schulzeiten – nur, wo nach Alter getrennt gezählt ist.",
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
    if (kopf.dataset.toggle === "legend-root") {
      const zu = legende.classList.toggle("collapsed");
      kopf.querySelector(".toggle-arrow")?.classList.toggle("open", !zu);
      kopf.querySelector(".toggle-arrow")?.setAttribute("aria-expanded", String(!zu));
      return;
    }
    const sektion = kopf.closest(".legend-section");
    const zu = sektion.classList.toggle("collapsed");
    kopf.querySelector(".toggle-arrow")?.classList.toggle("open", !zu);
    kopf.querySelector(".toggle-arrow")?.setAttribute("aria-expanded", String(!zu));
  });
  if (legende.classList.contains("collapsed")) {
    legende.querySelector(".toggle-root")?.classList.remove("open");
  }

  $("thema-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-thema]");
    if (!b) return;
    zustand.thema = b.dataset.thema;
    zeichne();
    geaendert();
  });
  $("modus-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-modus]");
    if (!b) return;
    zustand.modus[zustand.thema] = b.dataset.modus;
    zeichne();
    geaendert();
  });
  $("art-chips").addEventListener("click", (e) => {
    const b = e.target.closest("[data-art]");
    if (!b) return;
    zustand.art = b.dataset.art;
    zeichne();
    geaendert();
  });

  // Schulweg-Regler
  const stunde = $("schwelle-stunde");
  const tag = $("schwelle-tag");
  const regler = () => {
    zustand.kriterien.schwelle_stunde = Number(stunde.value);
    zustand.kriterien.schwelle_tag = Number(tag.value);
    zeichneRegler();
    geaendert();
  };
  stunde.addEventListener("input", regler);
  tag.addEventListener("input", regler);
  $("schulstunden").textContent = zustand.kriterien.schulstunden.join(", ");

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

  function zeichneRegler() {
    $("schwelle-stunde-wert").textContent = zahl.format(zustand.kriterien.schwelle_stunde);
    $("schwelle-tag-wert").textContent = zahl.format(zustand.kriterien.schwelle_tag);
    for (const [r, max] of [[stunde, 200], [tag, 1500]]) {
      const p = ((Number(r.value) - Number(r.min)) / (max - Number(r.min))) * 100;
      r.style.setProperty("--progress", `${p}%`);
    }
  }

  function zeichneJahre() {
    $("jahre-wert").textContent = zustand.jahre[0] === zustand.jahre[1]
      ? String(zustand.jahre[0]) : `${zustand.jahre[0]}–${zustand.jahre[1]}`;
  }

  /** Statische Teile nach Zustand (Chips, Regler, Häkchen). */
  function zeichne() {
    setzeChips($("thema-chips"), "thema", zustand.thema);
    const modi = THEMEN[zustand.thema].modi;
    const modus = zustand.modus[zustand.thema];
    $("modus-chips").innerHTML = Object.entries(modi).map(([id, m]) => `
      <button type="button" class="legend-chip" data-modus="${id}" role="radio"${MODUS_TIPS[id] ? ` title="${esc(MODUS_TIPS[id])}"` : ""}>${esc(m.name)}</button>`).join("");
    setzeChips($("modus-chips"), "modus", modus);
    setzeChips($("art-chips"), "art", zustand.art);
    $("art-wahl").hidden = modus === "verdacht";
    $("kriterium").hidden = modus !== "verdacht";
    stunde.value = zustand.kriterien.schwelle_stunde;
    tag.value = zustand.kriterien.schwelle_tag;
    zeichneRegler();
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
    let zeilen;
    if (modus === "verdacht") {
      zeilen = Object.entries(STATUS_NAMEN).map(([k, name]) => ({
        farbe: STATUSFARBEN[k], name, n: n[k] ?? 0, hohl: !STATUSFARBEN[k],
        tip: k === "unbekannt" ? "Kinder/Jugendliche nicht getrennt oder nicht zu Schulzeiten gezählt" : (k === "schulfrei" ? "Ferien, Feiertag oder Wochenende – die Zahlen zeigen keinen Schulweg" : null),
      }));
    } else {
      const grenzen = stufenFuer(zustand.thema, modus, zustand.art);
      zeilen = stufenText(grenzen, modus).map((name, i) => ({ farbe: STUFENFARBEN[i], name, n: n[String(i)] ?? 0, groesse: i }));
      zeilen.reverse();
      zeilen.push({ name: `nicht in „${ARTEN[zustand.art]}“ gezählt`, n: n["-1"] ?? 0, hohl: true, tip: "Die Zählung deckt die gewählte Kennzahl nicht ab – etwa nur 15–19 Uhr gezählt. Klick zeigt den Tagesgang." });
    }
    const titel = modus === "verdacht" ? "Stärkste Einstufung im Filter"
      : modus === "menge" ? `${THEMEN[zustand.thema].name === "Fuß & Schulweg" ? "Fußverkehr" : THEMEN[zustand.thema].name}, Summe ${ARTEN[zustand.art]}`
        : (modus === "svanteil" ? `Schwerverkehrsanteil (${ARTEN[zustand.art]})` : `Radanteil (${ARTEN[zustand.art]})`);
    $("klassen-legende").innerHTML = `<div class="legend-hint legend-hint--titel">${esc(titel)}</div>` + zeilen.map((z) => `
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
