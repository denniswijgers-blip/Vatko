"""Passen — hoeveel stuks gaan er in deze locatie? (R-PAS)

Dit is de kern van het hele product en de plek waar het het vaakst
subtiel misgaat. Lees de valkuil bij `pas_berekening` voordat je hier
iets verandert.
"""

from __future__ import annotations
from dataclasses import dataclass
from math import floor

from .modellen import Artikel, Locatie


@dataclass(frozen=True)
class PasResultaat:
    qty: int | None                 # None = niet te bepalen (nooit gemeten)
    limiet: str                     # AFMETING | GEWICHT | ONBEKEND
    orientatie: tuple[int, int, int] | None
    reden: str

    def __bool__(self) -> bool:
        return bool(self.qty)


def orientaties(l: int, w: int, h: int, stapelbaar: bool):
    """R-PAS-01. Zes draaiingen als het gestapeld mag, anders twee.

    Niet-stapelbaar betekent: alleen liggend draaien, nooit op zijn kant.
    Een pomp op zijn kant leggen is geen ruimtewinst maar schade.
    """
    if stapelbaar:
        return ((l, w, h), (l, h, w), (w, l, h), (w, h, l), (h, l, w), (h, w, l))
    return ((l, w, h), (w, l, h))


def pas_berekening(artikel: Artikel, locatie: Locatie,
                   vulfactor: float) -> PasResultaat:
    """R-PAS-02 en R-PAS-03.

    VALKUIL — de max(1, ...) is geen detail
    ---------------------------------------
    Een pomp die precies één keer in een palletplaats past geeft
    floor(1 * 0.85) = 0. Zonder die max(1, ...) past zo'n artikel
    NERGENS, en dan zoek je een dag naar de fout in je scoringsregels
    terwijl het probleem één afronding is.

    Let ook op de volgorde: eerst het aantal per draaiing bepalen, DAN de
    vulfactor toepassen. Andersom rond je twee keer af.
    """
    if not artikel.gemeten:
        return PasResultaat(None, "ONBEKEND", None,
                            "Artikel is nog nooit opgemeten")

    beste = 0
    beste_orientatie: tuple[int, int, int] | None = None

    for ol, ow, oh in orientaties(artikel.l_mm, artikel.w_mm, artikel.h_mm,
                                  artikel.stapelbaar):
        if ol > locatie.l_mm or ow > locatie.w_mm or oh > locatie.h_mm:
            continue
        if artikel.stapelbaar:
            n = (locatie.l_mm // ol) * (locatie.w_mm // ow) * (locatie.h_mm // oh)
        else:
            n = (locatie.l_mm // ol) * (locatie.w_mm // ow)   # één laag
        if n > beste:
            beste = n
            beste_orientatie = (ol, ow, oh)

    if beste == 0:
        return PasResultaat(
            0, "AFMETING", None,
            f"Artikel ({artikel.l_mm}x{artikel.w_mm}x{artikel.h_mm} mm) past in geen "
            f"enkele draaiing in deze locatie "
            f"({locatie.l_mm}x{locatie.w_mm}x{locatie.h_mm} mm)")

    op_maat = max(1, floor(beste * vulfactor))
    op_gewicht = locatie.max_g // artikel.g

    if op_gewicht < op_maat:
        return PasResultaat(
            op_gewicht, "GEWICHT", beste_orientatie,
            f"Ruimte biedt plek aan {op_maat} st, maar het maximale gewicht "
            f"({round(locatie.max_g / 1000)} kg) is bij {op_gewicht} st bereikt")

    return PasResultaat(
        op_maat, "AFMETING", beste_orientatie,
        f"{op_maat} st passen (vulfactor {round(vulfactor * 100)}%); "
        f"gewicht zou {op_gewicht} st toestaan")
