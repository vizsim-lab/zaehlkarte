from __future__ import annotations

from datetime import date

from zaehlkarte import kennzahlen as kz
from zaehlkarte.modell import Zaehlung

TAGTYP = {"s": "schule", "f": "ferien", "h": "feiertag", "w": "wochenende", None: None}


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


def test_kriterium_wie_im_frontend(kriterium_faelle):
    k = kz.Kriterien.aus_config(kriterium_faelle["kriterien"])
    for f in kriterium_faelle["faelle"]:
        z = zaehlung(f["kh0"], **({"kind": f["kh"]} if f["kh"] else {}))
        wert, gruende = kz.verdacht(z, k)
        assert wert == f["wert"], f["name"]
        assert gruende == f["gruende"], f["name"]
        assert kz.status(wert, TAGTYP[f["tag"]]) == f["status"], f["name"]


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
