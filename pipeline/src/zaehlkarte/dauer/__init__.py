"""Familie „Dauerzählstellen“: Stunden- und Tageswerte fest eingebauter Zählstellen.

Getrennt von den Kurzzeitzählungen (eigene Quellen unter `dauer:` in sources.yaml, eigener Bau
`zaehlkarte dauer fetch|site`, eigene Kartendaten unter public/data/dauer/, nicht im Git).

Abgrenzung zu vizsim/svz: hier die gezählten Werte im Zeitverlauf (Stunden, Tage) – keine
Jahresmittel, kein DTV, keine Hochrechnung. Eine Tagessumme gibt es nur aus allen Stunden des
Tages; sonst ist der Tag „nicht vollständig gezählt“ (nie 0).

- modell.py      Dauerstelle und Messreihe (Stunden × Tage), Tagessummen, Zeitumstellung
- berlin_viz.py  Verkehrsdetektion Berlin (VIZ): Monatsarchive, Stammdaten
- site.py        Kartendaten schreiben (dauer/index.json, dauer/tage/JJJJ.json, dauer/NN.json)
- bau.py         alle Quellen holen bzw. lesen und schreiben
"""
