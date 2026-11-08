"""Koordinaten umrechnen: UTM (ETRS89) -> geographisch, und eine örtliche Anpassung zwischen
zwei ebenen Systemen (für Quellen, die ältere Gauß-Krüger-Werte mitliefern).

UTM -> Länge/Breite mit der Krüger-Reihe bis n³ (Formeln wie in Karney 2011, „Transverse
Mercator with an accuracy of a few nanometers“; bis n³ auf rund einen Millimeter genau).
"""

from __future__ import annotations

import math

A_GRS80 = 6378137.0
F_GRS80 = 1 / 298.257222101


def utm_zu_wgs84(ost: float, nord: float, zone: int = 32) -> tuple[float, float]:
    """UTM-Rechts-/Hochwert (Nordhalbkugel, ETRS89 ≈ WGS84) -> (lon, lat) in Grad."""
    n = F_GRS80 / (2 - F_GRS80)
    a_gross = A_GRS80 / (1 + n) * (1 + n**2 / 4 + n**4 / 64)
    beta = (
        n / 2 - 2 * n**2 / 3 + 37 * n**3 / 96,
        n**2 / 48 + n**3 / 15,
        17 * n**3 / 480,
    )
    delta = (
        2 * n - 2 * n**2 / 3 - 2 * n**3,
        7 * n**2 / 3 - 8 * n**3 / 5,
        56 * n**3 / 15,
    )
    k0 = 0.9996
    xi = nord / (k0 * a_gross)
    eta = (ost - 500000.0) / (k0 * a_gross)
    j_beta = list(enumerate(beta, 1))
    xi_s = xi - sum(b * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, b in j_beta)
    eta_s = eta - sum(b * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, b in j_beta)
    chi = math.asin(math.sin(xi_s) / math.cosh(eta_s))
    phi = chi + sum(d * math.sin(2 * j * chi) for j, d in enumerate(delta, 1))
    lam0 = math.radians(6 * zone - 183)
    lam = lam0 + math.atan2(math.sinh(eta_s), math.cos(xi_s))
    return math.degrees(lam), math.degrees(phi)


def affin_anpassen(
    paare: list[tuple[tuple[float, float], tuple[float, float]]],
) -> tuple[list[float], float, int]:
    """Affine Abbildung (6 Parameter) von Quell- auf Zielkoordinaten nach kleinsten Quadraten.

    Solange ein Paar mehr als 50 m Restfehler hat (Tippfehler in der Quelle), fällt das
    schlechteste heraus und es wird neu gerechnet. Rückgabe: (Parameter, mittlerer Restfehler
    in m, Anzahl verwendeter Paare)."""
    import numpy as np

    quelle = np.array([[x, y, 1.0] for (x, y), _ in paare])
    ziel = np.array([z for _, z in paare], dtype=float)
    behalten = np.ones(len(paare), dtype=bool)
    while True:
        loesung, *_ = np.linalg.lstsq(quelle[behalten], ziel[behalten], rcond=None)
        rest = np.hypot(*(quelle @ loesung - ziel).T)
        schlechtestes = int(np.argmax(np.where(behalten, rest, -1.0)))
        if rest[schlechtestes] <= 50 or behalten.sum() <= 3:
            break
        behalten[schlechtestes] = False
    parameter = [float(v) for v in loesung.T.ravel()]
    rms = float(np.sqrt(np.mean(rest[behalten] ** 2)))
    return parameter, rms, int(behalten.sum())


def affin(parameter: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = parameter
    return a * x + b * y + c, d * x + e * y + f
