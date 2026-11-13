import { test } from "node:test";
import assert from "node:assert/strict";
import { achse, pfad, proStunde, tagesgang, tagesreihe, verlauf } from "../../js/ui/diagramme.js";

test("tagesreihe: ein Pfad je Tagtyp, Lücken bleiben, Jahresachse, Tag unter dem Zeiger", () => {
  assert.equal(tagesreihe([null, null], "ss", "2024-12-31").svg, "");
  const werte = [100, null, 300, 200];
  const { svg, index } = tagesreihe(werte, "swfs", "2024-12-30", 2);
  assert.match(svg, /^<svg class="tr"/);
  const pfade = svg.match(/class="tr-tage"[^>]*d="([^"]+)"/g);
  assert.equal(pfade.length, 2); // Schultag (2 Tage) und Ferien; der Tag ohne Wert fehlt
  assert.equal((svg.match(/V/g) ?? []).length, 3);
  assert.match(svg, />2025</); // Jahresanfang 1.1.2025
  assert.match(svg, /class="tr-gewaehlt"/);
  assert.equal(index(42), 0);
  assert.equal(index(330), 3);
});

test("achse: runde Schritte", () => {
  assert.deepEqual(achse(1473), { max: 1500, schritt: 500 });
  assert.deepEqual(achse(9), { max: 10, schritt: 2.5 });
  assert.deepEqual(achse(0), { max: 10, schritt: 5 });
});

test("proStunde und Lücken im Pfad", () => {
  const st = proStunde(7, [1, 2, null, 4]);
  assert.equal(st.length, 24);
  assert.deepEqual(st.slice(6, 12), [null, 1, 2, null, 4, null]);
  const d = pfad(st, (h) => h, (v) => v);
  assert.equal((d.match(/M/g) ?? []).length, 2); // zwei Abschnitte
});

test("tagesgang und verlauf liefern SVG", () => {
  const { svg } = tagesgang([{ id: "kfz", name: "Kfz", farbe: "#2a78d6", stunden: proStunde(7, Array(12).fill(100)) }]);
  assert.match(svg, /^<svg class="tg"/);
  assert.equal((svg.match(/class="tg-band"/g) ?? []).length, 12);
  assert.equal(verlauf([{ datum: "2020-01-01", wert: 1, text: "a" }]), "");
  assert.match(verlauf([{ datum: "2020-01-01", wert: 1, text: "a" }, { datum: "2021-01-01", wert: 2, text: "<b>" }]), /&lt;b&gt;/);
});
