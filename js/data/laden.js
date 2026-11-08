// laden.js — Kartendaten holen: manifest.json und index.json beim Start, details/NN.json erst
// beim Klick auf eine Stelle (je Stelle eine Datei, siehe pipeline/src/zaehlkarte/site.py).

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
