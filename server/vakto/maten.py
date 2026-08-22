"""Maatklassen en volume (R-AFG-02).

De maatklasse van een locatie is een BEREKENING, geen categorie die
iemand invult. Dat is het hele punt van Vakto: een vak van 30 cm en een
vak van 1,20 m zijn allebei "picklocatie", en gedragen zich totaal
verschillend.
"""

from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Maatregel:
    code: str
    naam: str
    min_cm3: float
    max_cm3: float


# Gelijk aan size_class_rule in het schema. Grenzen: min <= cm3 < max.
MAATREGELS: tuple[Maatregel, ...] = (
    Maatregel("XS", "Bak",            0,       8_000),
    Maatregel("S",  "Klein vak",      8_000,   50_000),
    Maatregel("M",  "Middelvak",      50_000,  200_000),
    Maatregel("L",  "Groot vak",      200_000, 900_000),
    Maatregel("XL", "Palletplaats",   900_000, 99_000_000),
)


def cm3(l_mm: int, w_mm: int, h_mm: int) -> float:
    """Volume in kubieke centimeter. Maten komen altijd in millimeter binnen."""
    return (l_mm * w_mm * h_mm) / 1000


def maatklasse(volume_cm3: float) -> str:
    """De klasse waar dit volume in valt. Boven de laatste grens: XL."""
    for r in MAATREGELS:
        if r.min_cm3 <= volume_cm3 < r.max_cm3:
            return r.code
    return "XL"


def maatklasse_van_locatie(loc) -> str:
    return maatklasse(cm3(loc.l_mm, loc.w_mm, loc.h_mm))
