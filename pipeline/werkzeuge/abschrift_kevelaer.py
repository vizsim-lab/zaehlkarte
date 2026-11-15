"""Kevelaer: Abschrift der Bildseiten des Berichts „Ergebnisse der Verkehrszählungen“ (2019).

Von den 74 Seiten des Berichts (büro stadtVerkehr, November 2019) sind 25 nur Bilder: bei 13
Knotenpunkten die Morgentabelle (6–10 Uhr), bei 12 die Summenseite. Dieses Werkzeug liest sie:

1. Seite -> die vier Bildstreifen (pdfimages) übereinander -> Graubild.
2. Gitter: waagrechte Linien über fast die ganze Breite (dünn, höchstens 5 Pixel), senkrechte
   über die halbe Höhe der Tabelle; die letzten 13 senkrechten begrenzen die zwölf Ströme.
3. Je Zeile: Text links (Tesseract, deu) und die zwölf Zellen. Ziffern per Mustervergleich: Die
   Tabellen sind gerastert, jede Ziffer gleich gesetzt. Zeichen über die senkrechte Projektion
   trennen, Muster je Ziffer aus Zellen, deren Tesseract-Lesung (ganze Zeile, nur Ziffern) so viele
   Ziffern hat wie die Zelle Zeichen; jedes Zeichen zum nächsten Muster. Leere Zelle = den Strom
   gibt es an diesem Knoten nicht (drei Arme).
4. Morgentabelle: nach drei Kopfzeilen 64 Zeilen, je Viertelstunde 06:00–09:45 die Arten PKW,
   KRAD, LIEFERWAGEN, LKW. Summenseite: „Summe Kfz|Pkw|Lkw/4h (6-10|15-19)“ und die vier Zeilen
   ab „davon mo“ bzw. „davon“. Kopf (Datum, Name) aus dem Kopf der Morgentabelle; die Namen
   stehen unten (NAMEN), weil Tesseract die Straßennummern verliest („B9“ -> „89“).

Geprüft wird im Adapter (`zaehlkarte.adapters.kevelaer_pdf`): je Knotenpunkt und Zählfenster
müssen die Viertelstunden die Summenzeilen treffen – Morgentabelle und Summenseite sind zwei
unabhängige Lesungen, die Nachmittagstabellen (Text) prüfen die Lesung der Summenseiten.
Stand 15.11.2026: alle 32 Fenster stimmen.

Braucht Tesseract (mit `deu`) und poppler-utils (pdfimages, pdftotext). Aus pipeline/:
    uv run python werkzeuge/abschrift_kevelaer.py \\
        data/raw/kevelaer/ergebnisse_verkehrszaehlungen_2019.pdf abschriften/kevelaer.csv
Das Ergebnis `abschriften/kevelaer.csv` nicht von Hand ändern.
"""

from __future__ import annotations

import csv
import re
import subprocess
import sys
import tempfile
from itertools import pairwise
from pathlib import Path

import numpy as np
from PIL import Image

ARTEN = ["PKW", "KRAD", "LIEFERWAGEN", "LKW"]
B, H = 14, 18  # Rahmen für den Vergleich der Zeichen (Breite, Höhe)

# Namen der Knotenpunkte wie im Kopf der Bildseiten (Tesseract verliest die Straßennummern);
# 13: der Kopf schreibt „gmontstraße“, die Tabelle „Egmontstraße“.
NAMEN = {
    2: "Kölner Str. B9/Wettener Str./Feldstraße",
    4: "Rheinstraße/Kölner Straße B9/Klever Straße B9",
    5: "Wellener Landstraße L491/Südstraße",
    7: "Weller Landstraße L261/Twistedener Straße K36",
    8: "Weller Landstraße L261/Wember Straße",
    9: "Wember Straße/Hüls/Wember Straße/Heideweg",
    10: "Twistedener Straße/Walbecker Straße/Kroatenstraße",
    11: "Twistedener Straße/Römerstraße/Marktstraße/Venloer Straße",
    12: "Marktstraße/Geldener Straße/Bahnstraße/Hauptstraße",
    13: "Wember Straße/Kroatenstraße/Egmontstraße",
    14: "Klever Straße/Lindenstraße",
    15: "Egmontstraße/Kardinal-von-Galen-Straße/Blumenstraße",
    16: "Grotendonker Straße (K13)/Rheinstraße (L491)/Schravelen (L491)",
}


# --- Bild und Gitter -----------------------------------------------------------------------------


def laeufe(xs: list[int], luecke: int = 2) -> list[list[int]]:
    out: list[list[int]] = []
    for x in xs:
        if out and x - out[-1][1] <= luecke:
            out[-1][1] = x
        else:
            out.append([x, x])
    return out


def seitenbild(pdf: Path, seite: int, tmp: Path) -> np.ndarray:
    for f in tmp.glob("st-*"):
        f.unlink()
    subprocess.run(
        ["pdfimages", "-f", str(seite), "-l", str(seite), "-png", str(pdf), str(tmp / "st")],
        check=True,
    )
    teile = [Image.open(f).convert("L") for f in sorted(tmp.glob("st-*.png"))]
    bild = Image.new("L", (max(t.width for t in teile), sum(t.height for t in teile)), 255)
    y = 0
    for t in teile:
        bild.paste(t, (0, y))
        y += t.height
    return np.array(bild)


def gitter(im: np.ndarray) -> tuple[list[list[int]], list[list[int]]]:
    d = im < 150
    h, w = d.shape
    hl = [r for r in laeufe([y for y in range(h) if d[y].sum() > 0.45 * w]) if r[1] - r[0] <= 5]
    y0, y1 = hl[0][0], hl[-1][1]
    vl = laeufe([x for x in range(w) if d[y0:y1, x].sum() > 0.5 * (y1 - y0)])
    return hl, vl


def tesseract(bild: np.ndarray, tmp: Path, psm: int, ziffern: bool) -> str:
    p = tmp / "z.png"
    Image.fromarray(bild).save(p)
    args = ["tesseract", str(p), "-", "--psm", str(psm), "-l", "deu"]
    if ziffern:
        args += ["-c", "tessedit_char_whitelist=0123456789."]
    return subprocess.run(args, capture_output=True, text=True, check=True).stdout.strip()


def sauber(z: np.ndarray, faktor: int) -> np.ndarray:
    z = np.pad(np.where(z < 140, 0, 255).astype(np.uint8), 10, constant_values=255)
    b = Image.fromarray(z)
    return np.array(b.resize((b.width * faktor, b.height * faktor), Image.LANCZOS))


# --- Zeichen ------------------------------------------------------------------------------------


def rahmen(g: np.ndarray) -> np.ndarray:
    r = np.zeros((H, B), bool)
    h, w = min(g.shape[0], H), min(g.shape[1], B)
    x0 = (B - w) // 2
    r[H - h :, x0 : x0 + w] = g[-h:, :w]
    return r


def zeichen(zelle: np.ndarray) -> list[np.ndarray]:
    z = zelle < 128
    z[:, :2] = z[:, -2:] = False
    z[:2, :] = z[-2:, :] = False
    spalten = z.any(axis=0)
    out, x = [], 0
    while x < z.shape[1]:
        if not spalten[x]:
            x += 1
            continue
        a = x
        while x < z.shape[1] and spalten[x]:
            x += 1
        g = z[:, a:x]
        zeilen = np.where(g.any(axis=1))[0]
        g = g[zeilen[0] : zeilen[-1] + 1]
        if g.sum() >= 2:
            out.append(g)
    return out


def ist_punkt(g: np.ndarray) -> bool:
    return g.sum() <= 12 and g.shape[0] <= 5 and g.shape[1] <= 5


def muster_bauen(proben: list[tuple[np.ndarray, str]]) -> dict[str, np.ndarray]:
    je: dict[str, list[np.ndarray]] = {}
    for g, c in proben:
        je.setdefault(c, []).append(rahmen(g).astype(float))
    muster = {}
    for c, gs in je.items():
        m = np.mean(gs, axis=0)
        d = [np.abs(g - m).sum() for g in gs]
        grenze = np.median(d) * 2 + 2
        muster[c] = np.mean([g for g, x in zip(gs, d, strict=True) if x <= grenze], axis=0) > 0.5
    return muster


def erkennen(g: np.ndarray, muster: dict[str, np.ndarray]) -> tuple[str, int, int]:
    d = sorted((int(np.logical_xor(rahmen(g), m).sum()), c) for c, m in muster.items())
    return d[0][1], d[0][0], d[1][0]


# --- Seiten lesen -------------------------------------------------------------------------------


def bildseiten(pdf: Path) -> list[tuple[int, int, str]]:
    out = []
    for kp in range(1, 17):
        for seite, teil in ((4 * kp, "morgens"), (4 * kp + 2, "summen")):
            text = subprocess.run(
                ["pdftotext", "-f", str(seite), "-l", str(seite), str(pdf), "-"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            if not text.strip():
                out.append((kp, seite, teil))
    return out


def lesen(pdf: Path) -> list[dict]:
    zeilen = []
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        for kp, seite, teil in bildseiten(pdf):
            im = seitenbild(pdf, seite, tmp)
            hl, vl = gitter(im)
            xs, links = vl[-13:], vl[0][1]
            kopf = (
                tesseract(sauber(im[: hl[0][0] - 2], 2), tmp, 6, False) if teil == "morgens" else ""
            )
            for i, (a, b) in enumerate(pairwise(hl)):
                y0, y1 = a[1], b[0]
                if y1 - y0 < 12:
                    continue
                text = tesseract(
                    sauber(im[y0 + 1 : y1, links + 2 : xs[0][0] - 2], 2), tmp, 7, False
                )
                zellen = [im[y0 + 1 : y1, p[1] + 1 : q[0]] for p, q in pairwise(xs)]
                hoehe = max(z.shape[0] for z in zellen)
                teile = [np.full((hoehe, 40), 255, np.uint8)]
                for z in zellen:
                    z2 = np.full((hoehe, z.shape[1]), 255, np.uint8)
                    z2[: z.shape[0]] = z
                    teile += [z2, np.full((hoehe, 40), 255, np.uint8)]
                ocr = tesseract(sauber(np.hstack(teile), 2), tmp, 7, True).split()
                zeilen.append(
                    {
                        "kp": kp,
                        "seite": seite,
                        "teil": teil,
                        "nr": i,
                        "text": text,
                        "ocr": ocr,
                        "zeichen": [zeichen(z) for z in zellen],
                        "kopf": kopf,
                    }
                )
                kopf = ""
            print(f"Knotenpunkt {kp}, Seite {seite} ({teil})", file=sys.stderr)
    return zeilen


def main(pdf: Path, ziel: Path) -> None:
    zeilen = lesen(pdf)
    proben = []
    for z in zeilen:
        if len(z["ocr"]) != 12:
            continue
        for s, gs in zip(z["ocr"], z["zeichen"], strict=True):
            ziffern = [g for g in gs if not ist_punkt(g)]
            s2 = s.replace(".", "")
            if s2.isdigit() and len(s2) == len(ziffern):
                proben += list(zip(ziffern, s2, strict=True))
    muster = muster_bauen(proben)
    knapp: list[str] = []

    def werte(z: dict) -> list[int | str]:
        out: list[int | str] = []
        for s, gs in enumerate(z["zeichen"]):
            txt = ""
            for g in gs:
                if ist_punkt(g):
                    continue  # Tausenderpunkt
                c, d1, d2 = erkennen(g, muster)
                txt += c
                if d2 - d1 < 6 or d1 > 30:
                    knapp.append(
                        f"K{z['kp']} S.{z['seite']} Zeile {z['nr']} s{s + 1}: {c} ({d1}/{d2})"
                    )
            out.append(int(txt) if txt else "")
        return out

    seiten: dict[tuple[int, int], list[dict]] = {}
    for z in zeilen:
        seiten.setdefault((z["kp"], z["seite"]), []).append(z)
    with open(ziel, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            [
                "knotenpunkt",
                "seite",
                "abschnitt",
                "zeit",
                "art",
                *[f"s{i}" for i in range(1, 13)],
                "text",
            ]
        )
        for (kp, seite), zs in sorted(seiten.items()):
            if zs[0]["teil"] == "morgens":
                d = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", zs[0]["kopf"])
                if not d:
                    raise SystemExit(f"Knotenpunkt {kp}: kein Datum im Kopf: {zs[0]['kopf']!r}")
                w.writerow([kp, seite, "kopf", f"{d[3]}-{d[2]}-{d[1]}", "", *[""] * 12, NAMEN[kp]])
                daten = zs[3:]
                if len(daten) != 64:
                    raise SystemExit(
                        f"Knotenpunkt {kp}, Seite {seite}: {len(daten)} Zeilen statt 64"
                    )
                for i, z in enumerate(daten):
                    minute = 6 * 60 + (i // 4) * 15
                    w.writerow(
                        [
                            kp,
                            seite,
                            "viertelstunde",
                            f"{minute // 60:02d}:{minute % 60:02d}",
                            ARTEN[i % 4],
                            *werte(z),
                            z["text"],
                        ]
                    )
                continue
            gefunden = set()
            for i, z in enumerate(zs):
                if s := re.search(r"Summe\s*(Kfz|Pkw|Lkw)\S*\s*\((6-10|15-19)\)", z["text"]):
                    w.writerow([kp, seite, "summe", s[2], s[1], *werte(z), z["text"]])
                    gefunden.add(("summe", s[1], s[2]))
                elif re.match(r"davon", z["text"].strip(), re.I):
                    abschnitt = "davon_mo" if re.search(r"davon\s*mo", z["text"], re.I) else "davon"
                    for j, art in enumerate(ARTEN):
                        w.writerow(
                            [kp, seite, abschnitt, "", art, *werte(zs[i + j]), zs[i + j]["text"]]
                        )
                    gefunden.add((abschnitt,))
            if len(gefunden) != 8:
                raise SystemExit(
                    f"Knotenpunkt {kp}, Seite {seite}: Summenzeilen {sorted(gefunden)}"
                )
    print(f"{len(proben)} Proben für die Muster; {len(knapp)} knappe Zeichen", file=sys.stderr)
    for k in knapp:
        print("  " + k, file=sys.stderr)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
