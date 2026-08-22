"""De gegevens waar de rekenkern mee werkt.

Bewust simpele dataclasses en geen ORM-objecten. De rekenkern moet je
kunnen aanroepen met drie regels code in een test, zonder database,
zonder migraties, zonder fixtures.

De serverlaag (stap 3) vult deze objecten uit PostgreSQL. Verandert er
iets aan het schema, dan verandert alleen die vertaallaag mee — niet de
rekenregels.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class LocatieSoort:
    """Gedrag als vlaggen, niet als if in de code (R-BASIS-04)."""
    id: int
    code: str
    naam: str
    pick: bool = False
    bulk: bool = False
    mix: bool = False      # False = één artikelsoort per vak
    blok: bool = False     # True  = telt niet mee als beschikbaar
    doel: bool = False     # False = komt nooit in een inslagvoorstel


SOORTEN: dict[int, LocatieSoort] = {
    0: LocatieSoort(0, "PL",  "Picklocatie",   pick=True,  doel=True),
    1: LocatieSoort(1, "BL",  "Bulklocatie",   bulk=True,  doel=True),
    2: LocatieSoort(2, "INC", "Ontvangst",     mix=True),
    3: LocatieSoort(3, "QC",  "Keuring",       mix=True, blok=True),
    4: LocatieSoort(4, "DM",  "Schade",        mix=True, blok=True),
    5: LocatieSoort(5, "EXP", "Verzendgereed", mix=True, blok=True),
}


@dataclass
class Locatie:
    id: int
    code: str
    type_id: int
    l_mm: int
    w_mm: int
    h_mm: int
    max_g: int                    # draagvermogen in GRAM, niet in kilo
    zone_id: int = 0
    aisle: int = 0
    bay: int = 0
    level: int = 0
    seq: int = 0
    actief: bool = True
    geteld_op: datetime | None = None

    @property
    def volume_mm3(self) -> int:
        return self.l_mm * self.w_mm * self.h_mm


@dataclass
class Artikel:
    """Let op: de afmetingen zitten hier WEL in, maar als momentopname.

    In de database staan ze in `measurement` en is de actuele maat de
    nieuwste rij (R-AFG-01). De vertaallaag zet die nieuwste meting hier
    neer voordat de rekenkern aan het werk gaat. Zo hoeft de rekenkern
    niet te weten hoe de tijdlijn is opgeslagen.
    """
    id: int
    sku: str
    oms: str = ""
    group_id: int = 0
    l_mm: int | None = None
    w_mm: int | None = None
    h_mm: int | None = None
    g: int | None = None
    gemeten_op: datetime | None = None
    bron: str | None = None
    min_qty: int | None = None
    max_qty: int | None = None
    stapelbaar: bool = True
    barcode: str | None = None

    @property
    def gemeten(self) -> bool:
        """Een artikel zonder complete maat doet mee, maar krijgt nooit
        een inslagvoorstel. Nul is geen maat en een gok is geen maat."""
        return all(v is not None and v > 0
                   for v in (self.l_mm, self.w_mm, self.h_mm, self.g))

    @property
    def volume_mm3(self) -> int:
        if not self.gemeten:
            raise ValueError(f"{self.sku} is niet opgemeten")
        return self.l_mm * self.w_mm * self.h_mm


@dataclass
class Voorraadregel:
    product_id: int
    location_id: int
    qty: int
    res: int = 0

    @property
    def vrij(self) -> int:
        """R-UIT-01. Vrije voorraad is altijd qty - res."""
        return self.qty - self.res


@dataclass
class Magazijn:
    """Een momentopname waar de rekenkern mee werkt.

    Alleen wat nodig is om een inslagvoorstel te maken. Geen orders,
    geen journaal: die horen bij latere stappen.
    """
    locaties: list[Locatie] = field(default_factory=list)
    artikelen: list[Artikel] = field(default_factory=list)
    voorraad: list[Voorraadregel] = field(default_factory=list)
    # De soorten locatie komen uit de tabel location_type en reizen dus
    # mee met de gegevens. Een klant die gemengde bulk wil, zet dat daar
    # aan; er hoeft geen regel code voor aangepast te worden.
    soorten: dict[int, LocatieSoort] = field(
        default_factory=lambda: dict(SOORTEN))

    def soort(self, loc: Locatie) -> LocatieSoort:
        try:
            return self.soorten[loc.type_id]
        except KeyError:
            raise KeyError(
                f"Locatie {loc.code} heeft soort {loc.type_id}, en die staat "
                f"niet in location_type. Vul de tabel aan."
            ) from None

    def artikel(self, product_id: int) -> Artikel | None:
        for a in self.artikelen:
            if a.id == product_id:
                return a
        return None

    def locatie(self, location_id: int) -> Locatie | None:
        for l in self.locaties:
            if l.id == location_id:
                return l
        return None

    def bezetting(self) -> dict[int, "Bezetting"]:
        """R-AFG-04 en R-BASIS-05: bezetting telt in volume en gewicht,
        nooit in stuks. Artikelen zonder maat tellen niet mee."""
        uit: dict[int, Bezetting] = {}
        maten = {a.id: a for a in self.artikelen}
        for s in self.voorraad:
            if s.qty <= 0:
                continue
            a = maten.get(s.product_id)
            if a is None or not a.gemeten:
                continue
            b = uit.setdefault(s.location_id, Bezetting())
            b.vol_mm3 += s.qty * a.volume_mm3
            b.gew_g += s.qty * a.g
            b.per_artikel[s.product_id] = b.per_artikel.get(s.product_id, 0) + s.qty
        return uit


@dataclass
class Bezetting:
    vol_mm3: int = 0
    gew_g: int = 0
    per_artikel: dict[int, int] = field(default_factory=dict)
