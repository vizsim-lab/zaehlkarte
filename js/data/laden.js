// laden.js — Kartendaten holen: manifest.json und index.json beim Start, details/NN.json erst
// beim Klick auf eine Stelle (je Stelle eine Datei, siehe pipeline/src/zaehlkarte/site.py).
// Dauerzählstellen (pipeline/src/zaehlkarte/dauer/site.py): dauer/index.json erst beim
// Umschalten, dauer/tage/JJJJ.json je Jahr des gewählten Tags, dauer/NN.json beim Klick.

const BASIS = "./data/";
const cache = new Map();

async function json(pfad) {
  const r = await fetch(BASIS + pfad);
  if (!r.ok) throw new Error(`${pfad}: HTTP ${r.status}`);
  return r.json();
}

export async function ladeStart() {
  const manifest = await json("manifest.json");
  const [index, datenlage] = await Promise.all([
    json(manifest.dateien.index),
    json(manifest.dateien.datenlage),
  ]);
  // Datenlage der Dauerzählstellen (`dauer` je Kommune): den Stand flach daneben, damit die
  // Kartenebene ihn in Ausdrücken lesen kann (verschachtelte Werte kommen dort nur als Text an)
  for (const f of datenlage.features) {
    if (f.properties.dauer) f.properties.dauer_stand = f.properties.dauer.stand;
  }
  return { manifest, index, datenlage };
}

/** Details einer Chunk-Datei (zwischengespeichert). */
export function ladeDetails(manifest, chunk) {
  if (!cache.has(chunk)) {
    const p = json(manifest.dateien.details.replace("{n}", String(chunk))).catch((e) => {
      cache.delete(chunk);
      throw e;
    });
    cache.set(chunk, p);
  }
  return cache.get(chunk);
}

/** Gibt es Dauerzählstellen? Nur ein HEAD auf dauer/index.json – geladen wird erst beim Umschalten. */
export async function gibtDauer() {
  try {
    return (await fetch(`${BASIS}dauer/index.json`, { method: "HEAD" })).ok;
  } catch {
    return false;
  }
}

/** Eine Datei der Dauerzählstellen (Pfad relativ zu data/, zwischengespeichert). */
export function ladeDauer(pfad = "dauer/index.json") {
  const schluessel = `dauer:${pfad}`;
  if (!cache.has(schluessel)) {
    cache.set(schluessel, json(pfad).catch((e) => {
      cache.delete(schluessel);
      throw e;
    }));
  }
  return cache.get(schluessel);
}
