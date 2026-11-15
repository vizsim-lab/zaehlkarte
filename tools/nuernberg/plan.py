"""Zählstellenpläne (Vektorkarten) lesen: je Nummer der Mittelpunkt des Punkts neben dem Etikett."""
import pdfplumber, re, json, math, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pfade import ARBEIT, BERICHTE  # noqa: E402
KARTEN = {2012: [23, 26, 27], 2022: [22], 2023: [17], 2024: [19], 2025: [21]}
NR = re.compile(r"^\d{1,3}[a-zA-Z]{0,2}(/\d{1,2}[a-z]?)?$")
out = {}
for jahr, seiten in KARTEN.items():
    with pdfplumber.open(BERICHTE / f"bericht_{jahr}.pdf") as pdf:
        for n in seiten:
            s = pdf.pages[n - 1]
            ws = s.extract_words(keep_blank_chars=False, extra_attrs=["size"])
            punkte = []
            for c in s.curves:
                w, h = c["x1"] - c["x0"], c["bottom"] - c["top"]
                if 2 < w < 15 and 2 < h < 15 and abs(w - h) < 1.5:
                    punkte.append(((c["x0"] + c["x1"]) / 2, (c["top"] + c["bottom"]) / 2, w, str(c.get("non_stroking_color"))))
            groessen = Counter(round(p[2], 1) for p in punkte).most_common(3)
            labs = [w for w in ws if NR.match(w["text"])]
            treffer = []
            for w in labs:
                ly = (w["top"] + w["bottom"]) / 2
                kand = [p for p in punkte if -25 < w["x0"] - p[0] < 25 and abs(p[1] - ly) < 12]
                if not kand:
                    kand = [p for p in punkte if math.dist((p[0], p[1]), (w["x0"], ly)) < 30]
                if kand:
                    p = min(kand, key=lambda p: math.dist((p[0], p[1]), (w["x0"], ly)))
                    treffer.append({"nummer": w["text"], "x": p[0], "y": p[1], "farbe": p[3], "lx": w["x0"], "ly": ly})
            out[f"{jahr}-{n}"] = {"breite": s.width, "hoehe": s.height, "punkte": treffer}
            print(jahr, n, "Etiketten", len(labs), "Punkte", len(punkte), groessen, "zugeordnet", len(treffer))
json.dump(out, open(ARBEIT / "plaene.json", "w"), indent=0)
