// main.js — Start der Zählkarte: Daten laden, Karte und Legende aufbauen, Zustand <-> Karte.
//
// Ablauf: manifest.json + index.json + datenlage.json laden (parallel zur Karte), Zustand aus
// dem Permalink (#…) lesen, Layer anlegen, bei jeder Änderung `zeichne()`. Details einer
// Stelle lädt detail.js erst beim Klick. Test-Hook: window.__app (tests/web/).
// Familie Dauerzählstellen (f=d): dauer/index.json erst beim Umschalten – im Standard zeigt sie je
// Stelle ihren jüngsten Schultag (alle Quellen zugleich); erst mit einem gewählten Tag (z=) kommt
// dessen Jahresdatei dazu. Details einer Dauerstelle lädt dauerdetail.js beim Klick.
// Sprache (DE Standard, EN wählbar): js/sprache/ – nach einem Wechsel wird neu gezeichnet.
// Kommunen der Datenlage: in beiden Ansichten; ein Klick öffnet ihren Steckbrief (js/ui/kommune.js,
// beide Zählarten) – eine Zeile dort stellt Zählart und Verkehrsart um und zeigt die Stellen.
import { Map as Karte } from "./js/lib/maplibre.js";
import { gibtDauer, ladeDauer, ladeStart } from "./js/data/laden.js";
import { TAGE, ansicht, csv, entpacke, features, lizenzFuerCsv, standardZustand, zaehleKlassen, zaehlen } from "./js/data/modell.js";
import { dauerQuellenJeKommune, kommuneDerDauerstelle, kommuneDerStelle } from "./js/data/kommune.js";
import {
  ansichtDauer, ansichtJuengster, csvDauer, csvDauerJuengster, entpackeDauer, featuresDauer, imJuengsten, tagDerStelle,
  tagImZeitraum, themaFuerKommune, themaIn, zaehleDauer,
} from "./js/data/dauer.js";
import { addBasemapTerrain } from "./js/map/basemapTerrain.js";
import {
  bindeHover, fuegeEbenenHinzu, setzeAuswahl, setzeDatenlage, setzeDauer, setzeFamilie, setzeStellen,
} from "./js/map/ebenen.js";
import { t } from "./js/sprache/texte.js";
import { bindeUmschalter, ersteSprache, wendeAn } from "./js/sprache/umschalter.js";
import { erstelleDauerDetail } from "./js/ui/dauerdetail.js";
import { erstelleDetail } from "./js/ui/detail.js";
import { erstelleKommune } from "./js/ui/kommune.js";
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
  const aufruf = dekodiere(location.hash, standard);
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

  // Kommune einer Stelle (Link „was es dort gibt“ in der Seitenleiste): Kurzzeit über ihre Quelle,
  // Dauer über die eigene Quelle oder die Gemeinde, in der sie liegt (js/data/kommune.js)
  const dauerQuellen = dauerQuellenJeKommune(datenlage);
  const detail = erstelleDetail({
    manifest,
    daten,
    gibZustand: () => zustand,
    kommuneVon: (s) => kommuneDerStelle(datenlage, s),
    beiKommune: (ags) => oeffneKommune(ags),
    beiSchliessen: () => { setzeAuswahl(karte, null); merkeLink(); },
    beiWechsel: () => merkeLink(),
  });
  const dauerDetail = erstelleDauerDetail({
    gibDauer: () => dauer,
    gibZustand: () => zustand,
    gibTag: (s) => (dauer ? tagDerStelle(dauer, zustand, s) : null),
    kommuneVon: (s) => kommuneDerDauerstelle(datenlage, s, dauerQuellen),
    beiKommune: (ags) => oeffneKommune(ags),
    beiTag: (iso) => tagWechseln(iso),
    beiStelle: (s) => oeffneDauer(s),
    beiSchliessen: () => { setzeAuswahl(karte, null); merkeLink(); },
  });
  const kommune = erstelleKommune({
    datenlage, manifest, daten,
    gibDauer: () => dauer,
    holeDauer: () => holeDauer(),
    gibtDauer: () => gibtDauer(),
    gibZustand: () => zustand,
    beiZeile: (z) => zeigeInKarte(z),
    beiCsv: (p) => csvKommune(p),
    beiSchliessen: () => merkeLink(),
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
    legende.zeichne();
    await zeichne(); // ein offener Steckbrief bleibt (er zeigt beide Zählarten) und markiert die Zeile
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
    setzeDatenlage(karte, zustand.datenlage);
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
    kommune.markiere();
    merkeLink();
    document.documentElement.dataset.gezeichnet = String(nr);
  }

  let linkTimer = null;
  function merkeLink() {
    clearTimeout(linkTimer);
    linkTimer = setTimeout(() => {
      const c = karte.getCenter();
      const stelle = zustand.familie === "d" ? dauerDetail.stelle?.id : detail.stelle?.id;
      const hash = kodiere(zustand, standard, { zoom: karte.getZoom(), lat: c.lat, lon: c.lng }, stelle ?? null,
        kommune.offen ? kommune.ags : null);
      history.replaceState(null, "", `#${hash}`); // ?lang= bleibt stehen
    }, 250);
  }
  karte.on("moveend", merkeLink);

  function oeffneStelle(s, zaehlung = null) {
    kommune.schliesse();
    detail.zeige(s, zaehlung ?? jeStelle.get(s.index)?.z.index ?? null);
    setzeAuswahl(karte, s);
    merkeLink();
  }

  function oeffneDauer(s) {
    kommune.schliesse();
    detail.schliesse();
    dauerDetail.zeige(s);
    setzeAuswahl(karte, s);
    merkeLink();
  }

  /** Steckbrief einer Kommune (Klick auf ihren Punkt, Link aus der Seitenleiste, Permalink k=). */
  function oeffneKommune(ags) {
    detail.schliesse();
    dauerDetail.schliesse();
    setzeAuswahl(karte, null);
    if (kommune.zeige(ags)) merkeLink();
  }

  /** Rand der Karte, den Steckbrief und Legende verdecken (für fitBounds). */
  function kartenRand() {
    const rand = { top: 70, bottom: 50, left: 50, right: 50 };
    if (window.innerWidth <= 640) return rand;
    const panel = document.getElementById("kommune-detail");
    if (!panel.hidden) rand.left = Math.round(panel.getBoundingClientRect().right) + 30;
    const leg = document.getElementById("legend");
    if (!leg.classList.contains("collapsed")) rand.right = Math.round(window.innerWidth - leg.getBoundingClientRect().left) + 30;
    if (window.innerWidth - rand.left - rand.right < 220) Object.assign(rand, { left: 50, right: 50 });
    return rand;
  }

  /**
   * Zeile des Steckbriefs: Zählart und Verkehrsart umstellen und die Stellen der Kommune zeigen.
   * Liegt die Zeile außerhalb des gewählten Zeitraums (Kurzzeit: Jahre) bzw. Tages (Dauer), gilt
   * wieder der ganze Zeitraum bzw. je Stelle ihr jüngster Schultag – sonst bliebe die Karte leer.
   */
  async function zeigeInKarte({ familie, thema, von, bis, umriss }) {
    if (familie !== zustand.familie) await familieWechseln(familie);
    if (familie !== zustand.familie) return; // Dauerzählstellen nicht verfügbar
    if (familie === "d") {
      zustand.dthema = thema;
      if (zustand.tag && (zustand.tag < von || zustand.tag > bis)) zustand.tag = null;
    } else {
      zustand.thema = thema;
      if (zustand.jahre[1] < Number(von) || zustand.jahre[0] > Number(bis)) zustand.jahre = [...daten.jahre];
    }
    legende.zeichne();
    await zeichne();
    if (window.innerWidth <= 640) kommune.schliesse(); // auf dem Handy die Karte frei machen
    if (umriss) karte.fitBounds(umriss, { padding: kartenRand(), maxZoom: 14, duration: 700 });
  }

  /** Lizenz einer Kurzzeit-Zählung für den CSV-Export (null: Quelle ohne Lizenz, Zeile weglassen). */
  function lizenzVon(quelle, lieferung) {
    const q = manifest.quellen.find((x) => x.code === quelle);
    const code = lieferung ? lieferung.split(":")[1] : quelle;
    return lizenzFuerCsv(q.lizenzen.find((l) => l.code === code) ?? q.lizenzen[0]);
  }

  function ladeCsv(text, name) {
    const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  /** Alle Kurzzeitzählungen einer Kommune (ihre Quellen, alle Jahre und Zähltage) als CSV. */
  function csvKommune(p) {
    const z = {
      ...zustand, quellen: new Set(p.kurzzeit?.quellen ?? []), jahre: [...daten.jahre],
      tage: new Set(Object.keys(TAGE)), uebertragen: true,
    };
    ladeCsv(csv(daten, z, lizenzVon), `zaehlungen_${p.ags}_${manifest.erzeugt}.csv`);
  }

  const popup = bindeHover(karte, {
    daten, manifest, datenlage, gibZustand: () => zustand, gibEintrag: (i) => jeStelle.get(i),
    gibDauer: () => ({ d: dauer, juengster: imJuengsten(dauer, zustand), eintrag: (i) => jeDauer.get(i) }),
  });
  karte.on("click", (e) => {
    const treffer = karte.queryRenderedFeatures(e.point, { layers: ["stellen-kreis", "dauer-kreis", "datenlage-kreis"] });
    const s = treffer.find((f) => f.layer.id === "stellen-kreis");
    if (s) { oeffneStelle(daten.stellen[s.properties.i]); return; }
    const ds = treffer.find((f) => f.layer.id === "dauer-kreis");
    if (ds && dauer) { oeffneDauer(dauer.stellen[ds.properties.i]); return; }
    const d = treffer.find((f) => f.layer.id === "datenlage-kreis");
    if (d) { oeffneKommune(d.properties.ags); return; }
    detail.schliesse();
    dauerDetail.schliesse();
    kommune.schliesse();
  });

  document.getElementById("export-csv").addEventListener("click", () => {
    if (zustand.familie === "d" && dauer) {
      // gewählter Tag: alle Stellen an dem Tag; im Standard je Stelle ihr jüngster Schultag
      const tag = tagJetzt();
      // Quellen ohne Lizenz: null – ihre Stellen bleiben weg
      const lizenz = (quelle) => lizenzFuerCsv(dauer.quellenMeta.find((q) => q.code === quelle)?.lizenzen[0]);
      const text = tag == null ? csvDauerJuengster(dauer, lizenz) : csvDauer(dauer, dauerJahr, tag, lizenz);
      ladeCsv(text, tag == null ? `dauerzaehlstellen_juengster_schultag_${dauer.erzeugt}.csv` : `dauerzaehlstellen_${tag}.csv`);
      return;
    }
    ladeCsv(csv(daten, zustand, lizenzVon), `zaehlungen_${manifest.erzeugt}.csv`);
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
    kommune.zeichne();
  });

  if (aufruf.stelle) {
    const s = zustand.familie === "d" ? dauer?.jeId.get(aufruf.stelle) : daten.stellen.find((x) => x.id === aufruf.stelle);
    if (s) {
      if (zustand.familie === "d") oeffneDauer(s); else oeffneStelle(s);
      if (!aufruf.karte) karte.jumpTo({ center: [s.lon, s.lat], zoom: 14 });
    }
  } else if (aufruf.kommune) {
    const f = datenlage.features.find((x) => x.properties.ags === aufruf.kommune);
    if (f) {
      oeffneKommune(aufruf.kommune);
      if (!aufruf.karte) karte.jumpTo({ center: f.geometry.coordinates, zoom: 9 });
    }
  }
  window.__app = {
    karte, daten, zustand, manifest, datenlage, zeichne, oeffneStelle, oeffneKommune, kommune, detail, eintraege: () => eintraege,
    dauer: () => dauer, dauerDetail, oeffneDauer, familieWechseln, tagWechseln, dauerModus, dauerEintraege: () => dauerEintraege,
  };
  document.documentElement.dataset.bereit = "1";
}

start().catch((err) => {
  console.error(err);
  zeigeFehler(t("fehler.laden", { fehler: err.message }));
});
