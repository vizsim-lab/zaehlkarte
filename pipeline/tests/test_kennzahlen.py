from __future__ import annotations

from datetime import date

from zaehlkarte import kennzahlen as kz
from zaehlkarte.modell import Zaehlung


def zaehlung(h0: int | None, **stunden) -> Zaehlung:
    return Zaehlung(
        "t",
        "x",
        None,
        "Test",
        "K",
        13.4,
        52.5,
        "gps",
        date(2024, 5, 14),
        [(420, 1140)],
        15,
        h0=h0,
        stunden=stunden,
    )


def test_summe_nur_wenn_jede_stunde_gezaehlt():
    z = zaehlung(7, kfz=[100] * 12)
    assert kz.summe(z, "kfz", 7, 19) == 1200
    assert kz.summe(z, "kfz", 6, 19) is None  # 6 Uhr nicht gezählt
    z = zaehlung(7, kfz=[100, None] + [100] * 10)
    assert kz.summe(z, "kfz", 7, 19) is None


def test_tag24_aus_summen_oder_stunden():
    z = zaehlung(None)
    z.summen = {"kfz": 12345}
    assert kz.tag24(z, "kfz") == 12345
    z = zaehlung(0, rad=list(range(24)))
    assert kz.tag24(z, "rad") == sum(range(24))


def test_spitzenstunde():
    z = zaehlung(7, kfz=[10, 50, None, 50, 20])
    assert kz.spitzenstunde(z, "kfz") == (8, 50)  # bei Gleichstand die frühere Stunde
    assert kz.spitzenstunde(z, "rad") is None


def test_summe6_22_aus_stunden_oder_genau_diesem_fenster():
    z = zaehlung(0, kfz=list(range(24)))
    assert kz.summe6_22(z, "kfz") == sum(range(6, 22))
    assert kz.summe6_22(zaehlung(7, kfz=[100] * 12), "kfz") is None  # 6 und 19–22 Uhr nicht gezählt
    z = zaehlung(None)
    z.fenster, z.fenstersummen = [(360, 1320)], {"kfz": 25757}  # Nürnberg: nur die Summe 6–22 Uhr
    assert kz.summe6_22(z, "kfz") == 25757 and kz.summe6_22(z, "rad") is None
    z.fenster = [(420, 600), (900, 1080)]  # anderes Fenster (Potsdam): keine Summe 6–22 Uhr
    assert kz.summe6_22(z, "kfz") is None
