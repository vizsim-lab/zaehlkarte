// main.js — Start der Zählkarte: Daten laden, Karte und Legende aufbauen, Zustand <-> Karte.
//
// Ablauf: manifest.json + index.json + datenlage.json laden (parallel zur Karte), Zustand aus
// dem Permalink (#…) lesen, Layer anlegen, bei jeder Änderung `zeichne()`. Details einer
// Stelle lädt detail.js erst beim Klick. Test-Hook: window.__app (tests/web/).
// Familie Dauerzählstellen (f=d): dauer/index.json erst beim Umschalten – im Standard zeigt sie je
// Stelle ihren jüngsten Schultag (alle Quellen zugleich); erst mit einem gewählten Tag (z=) kommt
// dessen Jahresdatei dazu. Details einer Dauerstelle lädt dauerdetail.js beim Klick.
// Sprache (DE Standard, EN wählbar): js/sprache/ – nach einem Wechsel wird neu gezeichnet.
import { Map as Karte } from "./js/lib/maplibre.js";
import { gibtDauer, ladeDauer, ladeStart } from "./js/data/laden.js";
import { ansicht, csv, entpacke, features, standardZustand, zaehleKlassen, zaehlen } from "./js/data/modell.js";
import {
  ansichtDauer, ansichtJuengster, csvDauer, csvDauerJuengster, entpackeDauer, featuresDauer, imJuengsten, tagDerStelle,
  tagImZeitraum, themaFuerKommune, themaIn, zaehleDauer,
} from "./js/data/dauer.js";
import { addBasemapTerrain } from "./js/map/basemapTerrain.js";
import {
  bindeHover, fuegeEbenenHinzu, setzeAuswahl, setzeDatenlage, setzeDauer, setzeFamilie, setzeStellen, standText,
  standTextDauer,
} from "./js/map/ebenen.js";
import { t, zahl } from "./js/sprache/texte.js";
import { bindeUmschalter, ersteSprache, wendeAn } from "./js/sprache/umschalter.js";
import { erstelleDauerDetail } from "./js/ui/dauerdetail.js";
import { erstelleDetail } from "./js/ui/detail.js";
import { erstelleLegende } from "./js/ui/legende.js";
import { setupMobileLayout } from "./js/ui/mobileLayout.js";
import { addNavigationControl, beschrifteSteuerung, rueckeNebenPanels, setupMapPanel } from "./js/ui/setupMapPanel.js";
import { setupTooltips } from "./js/ui/tooltip.js";
import { setupPhotonGeocoder } from "./js/utils/geocoder.js";
import { dekodiere, kodiere } from "./js/utils/permalinkFormat.js";

const START = { center: [10.45, 51.16], zoom: 5.3 };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

// Sprache sofort anwenden – vor dem Laden der Daten, damit die Legende nicht erst deutsch steht
ersteSprache();
wendeAn();

function zeigeFehler(text) {
  const el = document.getElementById("fehler");
  el.textContent = text;
  el.hidden = false;
}

async function start() {
  setupTooltips();
  const karte = new Karte({
    container: "map",
    style: "./style.json",
    ...START,
    attributionControl: { compact: true },
    dragRotate: false,
  });
  // Auf den STIL warten, nicht auf "load": "load" kommt erst, wenn auch die Hintergrund-
  // Kacheln da sind – ist OpenFreeMap nicht erreichbar, bliebe die Karte sonst ganz leer.
  const [{ manifest, index, datenlage }] = await Promise.all([
    ladeStart(),
    new Promise((ok) => (karte.isStyleLoaded() ? ok() : karte.once("style.load", ok))),
  ]);

  const daten = entpacke(index);
  const standard = standardZustand(daten.jahre, daten.quellen);
  const aufruf = dekodiere(location.hash, standard, daten.quellen);
  const zustand = aufruf.zustand;
  if (aufruf.karte) karte.jumpTo({ center: [aufruf.karte.lon, aufruf.karte.lat], zoom: aufruf.karte.zoom });

  addBasemapTerrain(karte);
  fuegeEbenenHinzu(karte, datenlage);

  let eintraege = [];
  let jeStelle = new Map();
  // Dauerzählstellen: entpackte dauer/index.json, Jahresdatei des Tags, Einträge je Stelle
  let dauer = null;
  let dauerJahr = null;
  let dauerEintraege = [];
  let jeDauer = new Map();
  // gewählter Tag (null im Standard: je Stelle ihr jüngster Schultag)
  const tagJetzt = () => (dauer && !imJuengsten(dauer, zustand) ? tagImZeitraum(dauer, zustand.tag) : null);

  const detail = erstelleDetail({
    manifest,
    daten,
    gibZustand: () => zustand,
    beiSchliessen: () => { setzeAuswahl(karte, null); merkeLink(); },
    beiWechsel: () => merkeLink(),
  });
  const dauerDetail = erstelleDauerDetail({
    gibDauer: () => dauer,
    gibZustand: () => zustand,
    gibTag: (s) => (dauer ? tagDerStelle(dauer, zustand, s) : null),
    beiTag: (iso) => tagWechseln(iso),
    beiStelle: (s) => oeffneDauer(s),
    beiSchliessen: () => { setzeAuswahl(karte, null); merkeLink(); },
  });
  const legende = erstelleLegende({
    manifest, daten, zustand, datenlage, geaendert: () => zeichne(),
    familieWechseln: (f) => familieWechseln(f),
    tagWechseln: (iso) => tagWechseln(iso),
    dauerModus: (m) => dauerModus(m),
  });

  async function holeDauer() {
    if (!dauer) {
      dauer = entpackeDauer(await ladeDauer());
      zustand.dthema = themaIn(dauer, zustand.dthema);
      legende.setzeDauer({ da: true, d: dauer });
    }
    return dauer;
  }

  async function familieWechseln(f) {
    if (f === "d") {
      try {
        await holeDauer();
      } catch (err) {
        legende.hinweis(t("familie.d_fehlt", { fehler: err.message }));
        return;
      }
    }
    legende.hinweis(null);
    zustand.familie = f;
    detail.schliesse();
    dauerDetail.schliesse();
    setzeAuswahl(karte, null);
    // offene Datenlage einer Kommune: in der neuen Familie zeigen (ohne Eintrag dort: schließen)
    if (!dlPanel.hidden && dlPanel.dataset.kommune) {
      const p = datenlage.features.find((x) => x.properties.kommune === dlPanel.dataset.kommune)?.properties;
      if ((f === "d" && !p?.dauer) || (f !== "d" && !p?.stand)) schliesseDatenlage();
      else zeigeDatenlage(dlPanel.dataset.kommune);
    }
    legende.zeichne();
    await zeichne();
  }

  /** Ein Tag für alle Stellen (auch aus der Standardansicht heraus: Tagesreihe, Sprung, Tag wählen). */
  async function tagWechseln(iso) {
    if (!dauer) return;
    zustand.tag = tagImZeitraum(dauer, iso);
    legende.zeichne();
    await zeichne();
  }

  /** j: je Stelle ihr jüngster Schultag (Standard) | t: Tag wählen (zuerst der Standardtag der Daten). */
  async function dauerModus(m) {
    if (!dauer) return;
    if (m === "j" && zustand.tag != null) {
      zustand.tag = null;
      legende.zeichne();
      await zeichne();
    } else if (m === "t" && imJuengsten(dauer, zustand)) {
      await tagWechseln(dauer.standardtag);
    }
  }

  let zeichneNr = 0;
  async function zeichne() {
    const nr = ++zeichneNr;
    setzeFamilie(karte, zustand.familie);
    setzeDatenlage(karte, zustand.datenlage, zustand.familie);
    if (zustand.familie === "d" && dauer) {
      const tag = tagJetzt();
      if (tag == null) {
        // Standard: je Stelle ihr jüngster Schultag – steht in dauer/index.json, keine Jahresdatei
        dauerJahr = null;
        dauerEintraege = ansichtJuengster(dauer, zustand);
      } else {
        let jahr = null;
        try {
          jahr = await ladeDauer(dauer.dateien.tage.replace("{jahr}", tag.slice(0, 4)));
        } catch (err) {
          legende.hinweis(t("familie.d_fehlt", { fehler: err.message }));
        }
        if (nr !== zeichneNr) return;
        dauerJahr = jahr;
        dauerEintraege = ansichtDauer(dauer, zustand, jahr, tag);
      }
      jeDauer = new Map(dauerEintraege.map((e) => [e.stelle.index, e]));
      setzeDauer(karte, featuresDauer(dauerEintraege));
      legende.zeichneDauer(tag, zaehleDauer(dauerEintraege), dauerEintraege);
      dauerDetail.aktualisiere();
    } else {
      eintraege = ansicht(daten, zustand);
      jeStelle = new Map(eintraege.map((e) => [e.stelle.index, e]));
      setzeStellen(karte, features(eintraege));
      legende.zeichneKlassen(zaehleKlassen(eintraege), zaehlen(daten, zustand, eintraege));
      detail.aktualisiere();
    }
    merkeLink();
    document.documentElement.dataset.gezeichnet = String(nr);
  }

  let linkTimer = null;
  function merkeLink() {
    clearTimeout(linkTimer);
    linkTimer = setTimeout(() => {
      const c = karte.getCenter();
      const stelle = zustand.familie === "d" ? dauerDetail.stelle?.id : detail.stelle?.id;
      const hash = kodiere(zustand, standard, { zoom: karte.getZoom(), lat: c.lat, lon: c.lng }, stelle ?? null);
      history.replaceState(null, "", `#${hash}`); // ?lang= bleibt stehen
    }, 250);
  }
  karte.on("moveend", merkeLink);

  const dlPanel = document.getElementById("datenlage-detail");
  function schliesseDatenlage() {
    dlPanel.hidden = true;
  }

  function oeffneStelle(s, zaehlung = null) {
    detail.zeige(s, zaehlung ?? jeStelle.get(s.index)?.z.index ?? null);
    setzeAuswahl(karte, s);
    dlPanel.hidden = true;
    merkeLink();
  }

  function oeffneDauer(s) {
    detail.schliesse();
    dauerDetail.zeige(s);
    setzeAuswahl(karte, s);
    dlPanel.hidden = true;
    merkeLink();
  }

  // Datenlage einer Kommune in der gewählten Familie: Oberfläche in der gewählten Sprache, die
  // Recherche-Texte deutsch. Dauerzählstellen: ihr eigener Stand mit Text und Belegen (`dauer`),
  // ohne Anfragetext – der gilt den Kurzzeitzählungen.
  function zeigeDatenlage(kommune, { behalteScroll = false } = {}) {
    const f = datenlage.features.find((x) => x.properties.kommune === kommune);
    if (!f) return;
    const p = f.properties;
    // Dauerzählstellen – oder eine Kommune, von der nur sie bekannt sind
    const dl = zustand.familie === "d" || !p.stand ? p.dauer : null;
    const el = dlPanel;
    const scroll = el.scrollTop;
    const links = (dl ? dl.links : p.links).map((l) => `<li><a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.titel)}</a></li>`).join("");
    const k = p.kontakt;
    const kontakt = k ? `<div class="detail-abschnitt">${esc(t("dl.kontakt"))}</div><p class="detail-text">
        ${k.name ? `<span lang="de">${esc(k.name)}</span><br>` : ""}${k.email ? `<a href="mailto:${esc(k.email)}">${esc(k.email)}</a><br>` : ""}
        ${k.fds ? `<a href="${esc(k.fds)}" target="_blank" rel="noopener">${esc(t(k.fds_suche ? "dl.fds_suche" : "dl.fds"))} →</a>` : ""}</p>` : "";
    const a = dl ? null : p.anfrage;
    const deutsch = t("dl.deutsch");
    const recht = p.recht ? `<div class="detail-abschnitt">${esc(t("dl.recht"))}</div><p class="detail-text"><span lang="de">${esc(p.recht)}.</span> ${esc(t("dl.keine_beratung"))}</p>` : "";
    const inhalt = dl ? `
      <p class="detail-text" lang="de">${esc(dl.was ?? "")}</p>
      ${dl.stand === "in_karte" ? `<p class="detail-text"><button type="button" class="link-knopf" data-hinzoomen>${esc(t("dl.d.in_karte"))}</button></p>` : ""}
      ${dl.situation ? `<div class="detail-abschnitt">${esc(t("dl.lage"))}</div><p class="detail-text" lang="de">${esc(dl.situation)}</p>` : ""}
      ${dl.stand === "in_karte" ? "" : kontakt}
      ${dl.stand === "in_karte" ? "" : recht}` : `
      ${p.zaehlungen ? `<p class="detail-text" lang="de">${esc(p.was ?? "")}</p><p class="detail-text"><button type="button" class="link-knopf" data-hinzoomen>${esc(t("dl.in_karte", { n: zahl(p.zaehlungen) }))}</button></p>` : ""}
      ${p.situation ? `<div class="detail-abschnitt">${esc(t("dl.lage"))}</div><p class="detail-text" lang="de">${esc(p.situation)}</p>` : (p.zaehlungen ? "" : `<p class="detail-text" lang="de">${esc(p.was ?? "")}</p>`)}
      ${p.empfehlung ? `<div class="detail-abschnitt">${esc(t("dl.empfehlung"))}</div><p class="detail-text" lang="de">${esc(p.empfehlung)}</p>` : ""}
      ${p.weg ? `<p class="detail-text"><span class="pop-chip" lang="de">${esc(p.weg)}</span></p>` : ""}
      ${kontakt}
      ${a ? `<div class="detail-abschnitt">${esc(t("dl.anfrage"))}</div>
        <p class="pop-meta">${esc(t("dl.anfrage_hinweis", { betreff: a.betreff }))}</p>
        <textarea class="anfrage-text" readonly rows="9" lang="de" aria-label="${esc(t("dl.anfrage"))}">${esc(a.text)}</textarea>
        <p class="detail-links"><button type="button" class="link-knopf" data-kopieren>${esc(t("dl.kopieren"))}</button>
        ${k?.fds ? `<a href="${esc(k.fds)}" target="_blank" rel="noopener">${esc(t("dl.stellen"))}</a>` : ""}</p>` : ""}
      ${recht}`;
    el.innerHTML = `
      <header class="detail-kopf">
        <div><div class="pop-eyebrow">${esc(t(dl ? "hover.datenlage_d" : "hover.datenlage", { land: p.land ?? "" }))}</div>
        <h2 class="detail-titel">${esc(p.kommune)}</h2>
        <div class="pop-meta">${esc(dl ? standTextDauer(dl.stand) : standText(manifest, p.stand))}</div></div>
        <button class="detail-zu" type="button" data-schliessen aria-label="${esc(t("schliessen"))}">×</button>
      </header>
      ${deutsch ? `<p class="pop-meta dl-sprache">${esc(deutsch)}</p>` : ""}
      ${inhalt}
      ${links ? `<div class="detail-abschnitt">${esc(t("dl.belege"))}</div><ul class="detail-hinweise" lang="de">${links}</ul>` : ""}
      <div class="pop-foot"><a href="https://github.com/vizsim-lab/zaehlkarte/issues/new?template=zaehlung-melden.yml" target="_blank" rel="noopener">${esc(t("dl.melden", { kommune: p.kommune }))}</a></div>`;
    el.hidden = false;
    el.scrollTop = behalteScroll ? scroll : 0;
    el.querySelector("[data-schliessen]").onclick = schliesseDatenlage;
    el.querySelector("[data-hinzoomen]")?.addEventListener("click", () => {
      // Dauerzählstellen: auf die Verkehrsart wechseln, die die Kommune zählt (Leipzig nur Rad)
      if (dl && dauer) {
        const thema = themaFuerKommune(dauer, p.kommune, ...f.geometry.coordinates, zustand.dthema);
        if (thema !== zustand.dthema) {
          zustand.dthema = thema;
          legende.zeichne();
          zeichne();
        }
      }
      karte.flyTo({ center: f.geometry.coordinates, zoom: 11 });
      el.hidden = true;
    });
    el.querySelector("[data-kopieren]")?.addEventListener("click", async (e) => {
      const feld = el.querySelector(".anfrage-text");
      try {
        await navigator.clipboard.writeText(feld.value);
      } catch {
        feld.select();
        document.execCommand("copy");
      }
      e.target.textContent = t("dl.kopiert");
    });
    detail.schliesse();
    dauerDetail.schliesse();
    el.dataset.kommune = kommune;
  }

  const popup = bindeHover(karte, {
    daten, manifest, gibZustand: () => zustand, gibEintrag: (i) => jeStelle.get(i),
    gibDauer: () => ({ d: dauer, juengster: imJuengsten(dauer, zustand), eintrag: (i) => jeDauer.get(i) }),
  });
  karte.on("click", (e) => {
    const treffer = karte.queryRenderedFeatures(e.point, { layers: ["stellen-kreis", "dauer-kreis", "datenlage-kreis"] });
    const s = treffer.find((f) => f.layer.id === "stellen-kreis");
    if (s) { oeffneStelle(daten.stellen[s.properties.i]); return; }
    const ds = treffer.find((f) => f.layer.id === "dauer-kreis");
    if (ds && dauer) { oeffneDauer(dauer.stellen[ds.properties.i]); return; }
    const d = treffer.find((f) => f.layer.id === "datenlage-kreis");
    if (d) { zeigeDatenlage(d.properties.kommune); return; }
    detail.schliesse();
    dauerDetail.schliesse();
    schliesseDatenlage();
  });

  document.getElementById("export-csv").addEventListener("click", () => {
    if (zustand.familie === "d" && dauer) {
      // gewählter Tag: alle Stellen an dem Tag; im Standard je Stelle ihr jüngster Schultag
      const tag = tagJetzt();
      const lizenz = (quelle) => dauer.quellenMeta.find((q) => q.code === quelle)?.lizenzen[0]?.lizenz ?? "";
      const text = tag == null ? csvDauerJuengster(dauer, lizenz) : csvDauer(dauer, dauerJahr, tag, lizenz);
      const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = tag == null ? `dauerzaehlstellen_juengster_schultag_${dauer.erzeugt}.csv` : `dauerzaehlstellen_${tag}.csv`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      return;
    }
    const lizenzVon = (quelle, lieferung) => {
      const q = manifest.quellen.find((x) => x.code === quelle);
      const code = lieferung ? lieferung.split(":")[1] : quelle;
      return (q.lizenzen.find((l) => l.code === code) ?? q.lizenzen[0])?.lizenz ?? "";
    };
    const blob = new Blob([csv(daten, zustand, lizenzVon)], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `zaehlungen_${manifest.erzeugt}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });

  setupPhotonGeocoder(karte);
  setupMapPanel(karte);
  addNavigationControl(karte);
  beschrifteSteuerung();
  rueckeNebenPanels();
  setupMobileLayout();
  // Dauerzählstellen: nur nachsehen, ob es sie gibt; geladen wird beim Umschalten (oder f=d)
  gibtDauer().then((da) => { if (!dauer) legende.setzeDauer({ da }); });
  if (zustand.familie === "d") {
    try {
      await holeDauer();
    } catch (err) {
      zustand.familie = "k";
      legende.hinweis(t("familie.d_fehlt", { fehler: err.message }));
    }
  }
  legende.zeichne();
  await zeichne();

  // Sprachwechsel: statische Texte setzt der Umschalter, hier alles Erzeugte neu zeichnen
  bindeUmschalter(() => {
    popup.remove();
    beschrifteSteuerung(); // Kompass entsteht erst kurz nach dem Einhängen
    legende.uebersetze();
    zeichne();
    if (!dlPanel.hidden && dlPanel.dataset.kommune) zeigeDatenlage(dlPanel.dataset.kommune, { behalteScroll: true });
  });

  if (aufruf.stelle) {
    const s = zustand.familie === "d" ? dauer?.jeId.get(aufruf.stelle) : daten.stellen.find((x) => x.id === aufruf.stelle);
    if (s) {
      if (zustand.familie === "d") oeffneDauer(s); else oeffneStelle(s);
      if (!aufruf.karte) karte.jumpTo({ center: [s.lon, s.lat], zoom: 14 });
    }
  }
  window.__app = {
    karte, daten, zustand, manifest, datenlage, zeichne, oeffneStelle, zeigeDatenlage, detail, eintraege: () => eintraege,
    dauer: () => dauer, dauerDetail, oeffneDauer, familieWechseln, tagWechseln, dauerModus, dauerEintraege: () => dauerEintraege,
  };
  document.documentElement.dataset.bereit = "1";
}

start().catch((err) => {
  console.error(err);
  zeigeFehler(t("fehler.laden", { fehler: err.message }));
});
