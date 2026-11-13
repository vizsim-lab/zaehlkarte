// permalinkFormat.js — Zustand der Karte <-> URL-Hash. REIN (kein DOM, kein window), damit
// browserlos testbar (tests/unit/permalink.test.js); die DOM-Bindung steht in main.js.
//
// Kürzel sind ein Vertrag mit geteilten Links: nie umdeuten, nur ergänzen.
//   t  Verkehrsart.Darstellung  kfz.menge | sv.menge | sv.anteil | rad.menge | rad.anteil | fuss.menge
//   a  Kennzahl-Art    w (7–19 Uhr) | w24 | sp (stärkste Stunde)
//   j  Jahre           1990-2025
//   d  Zähltage        Teilmenge von "sfhwu" (Schultag, Ferien, Feiertag, Wochenende, unbekannt)
//   q  Quellen         berlin,ravensburg (fehlt = alle)
//   u  übertragene Lagen zeigen: 0 | 1
//   dl Ebene Datenlage: 0 | 1
//   m  Kartenausschnitt zoom/lat/lon
//   s  gewählte Stelle (id aus index.json bzw. dauer/index.json)
//   f  Familie         k Kurzzeitzählungen (Standard) | d Dauerzählstellen
//   z  gewählter Tag   JJJJ-MM-TT (Dauerzählstellen; fehlt = Standardtag der Daten)
// Bei f=d steht in t die Verkehrsart der Dauerzählstellen (kfz.menge | lkw.menge); die übrigen
// Kürzel behalten ihre Bedeutung für die Kurzzeitzählungen.
import { DAUER_THEMEN } from "../data/dauer.js";
import { TAGE, THEMEN } from "../data/modell.js";

const ARTEN = ["w", "w24", "sp"];

export function kodiere(zustand, standard, karte, stelle) {
  const p = new URLSearchParams();
  if (zustand.familie === "d") {
    p.set("f", "d");
    if (zustand.dthema !== standard.dthema) p.set("t", `${zustand.dthema}.menge`);
    if (zustand.tag) p.set("z", zustand.tag);
  } else {
    const tm = `${zustand.thema}.${zustand.modus[zustand.thema]}`;
    if (tm !== `${standard.thema}.${standard.modus[standard.thema]}`) p.set("t", tm);
  }
  if (zustand.art !== standard.art) p.set("a", zustand.art);
  if (zustand.jahre[0] !== standard.jahre[0] || zustand.jahre[1] !== standard.jahre[1]) {
    p.set("j", `${zustand.jahre[0]}-${zustand.jahre[1]}`);
  }
  const tage = Object.keys(TAGE).filter((t) => zustand.tage.has(t)).join("");
  if (tage !== Object.keys(TAGE).filter((t) => standard.tage.has(t)).join("")) p.set("d", tage || "-");
  if (zustand.quellen.size !== standard.quellen.size || [...standard.quellen].some((q) => !zustand.quellen.has(q))) {
    p.set("q", [...zustand.quellen].join(",") || "-");
  }
  if (zustand.uebertragen !== standard.uebertragen) p.set("u", zustand.uebertragen ? "1" : "0");
  if (zustand.datenlage !== standard.datenlage) p.set("dl", zustand.datenlage ? "1" : "0");
  if (karte) p.set("m", `${karte.zoom.toFixed(2)}/${karte.lat.toFixed(5)}/${karte.lon.toFixed(5)}`);
  if (stelle) p.set("s", stelle);
  return p.toString().replaceAll("%2C", ",").replaceAll("%2F", "/").replaceAll("%3A", ":");
}

/** Hash -> { zustand (vollständig, Standard ergänzt), karte, stelle }; Ungültiges wird ignoriert. */
export function dekodiere(hash, standard, bekannteQuellen) {
  const p = new URLSearchParams(String(hash ?? "").replace(/^#/, ""));
  const z = {
    ...standard,
    modus: { ...standard.modus },
    jahre: [...standard.jahre],
    tage: new Set(standard.tage),
    quellen: new Set(standard.quellen),
  };
  if (p.get("f") === "d") z.familie = "d";
  const [thema, modus] = (p.get("t") ?? "").split(".");
  if (z.familie === "d") {
    if (DAUER_THEMEN[thema] && modus === "menge") z.dthema = thema;
    if (/^\d{4}-\d{2}-\d{2}$/.test(p.get("z") ?? "")) z.tag = p.get("z");
  } else if (THEMEN[thema]?.modi[modus]) {
    z.thema = thema;
    z.modus[thema] = modus;
  }
  if (ARTEN.includes(p.get("a"))) z.art = p.get("a");
  const j = /^(\d{4})-(\d{4})$/.exec(p.get("j") ?? "");
  if (j) {
    const von = Math.max(standard.jahre[0], Number(j[1]));
    const bis = Math.min(standard.jahre[1], Number(j[2]));
    if (von <= bis) z.jahre = [von, bis];
  }
  if (p.has("d")) z.tage = new Set([...p.get("d")].filter((t) => t in TAGE));
  if (p.has("q")) {
    z.quellen = new Set(p.get("q").split(",").filter((q) => bekannteQuellen.includes(q)));
  }
  if (p.has("u")) z.uebertragen = p.get("u") !== "0";
  if (p.has("dl")) z.datenlage = p.get("dl") !== "0";
  let karte = null;
  const m = /^(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)$/.exec(p.get("m") ?? "");
  if (m) {
    const [zoom, lat, lon] = m.slice(1).map(Number);
    if (zoom >= 0 && zoom <= 22 && Math.abs(lat) <= 85 && Math.abs(lon) <= 180) karte = { zoom, lat, lon };
  }
  return { zustand: z, karte, stelle: p.get("s") || null };
}
