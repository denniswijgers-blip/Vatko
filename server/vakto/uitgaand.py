"""Uitgaand (R-UIT) — het rekenwerk dat zonder database moet gelden.

Het grootste deel van hoofdstuk 8 staat níét hier maar in `uitgaand.sql`,
en dat is met opzet. Reserveren, picken en manco raken voorraad aan: ze
verhogen `stock.res` of ze boeken af. Zulke regels moeten ook gelden voor
wie ze buiten de applicatie om aanroept, en ze moeten rijen kunnen
vergrendelen. Dat is R-BOEK-03, en het is dezelfde afweging als bij
`boek()`.

Wat er dan nog wél in Python hoort is alles waar niets te vergrendelen
valt en dat je in drie regels moet kunnen natesten:

  * de looproute (R-UIT-03) — nodig bij het aanmaken van locaties, dus
    ver vóór er ook maar één order bestaat;
  * de statusreeks (R-UIT-06) — een schermknop moet weten of een
    overgang mag, zonder er de database voor lastig te vallen;
  * inpakken (R-UIT-07) — colli en gewicht zijn een som, geen boeking.

De vertaallaag (`opslag.py`) roept de databasefuncties aan en geeft de
uitkomsten hier terug als gewone objecten.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil

from .instellingen import Instellingen
from .modellen import Artikel


# ---------------------------------------------------------------------
#  R-UIT-06  De statusreeks
#
#      NIEUW → GERESERVEERD ─────────→ VRIJGEGEVEN → PICKEN → GEPICKT
#           ↘ WACHT_OP_VOORRAAD ↗                  → INGEPAKT → VERZONDEN
#
#  Een tabel en geen reeks ifs (R-BASIS-04): wil een klant orders zonder
#  inpakstap, dan haal je hier één regel weg.
# ---------------------------------------------------------------------
ORDERSTATUS: tuple[str, ...] = (
    "NIEUW", "GERESERVEERD", "WACHT_OP_VOORRAAD", "VRIJGEGEVEN",
    "PICKEN", "GEPICKT", "INGEPAKT", "VERZONDEN",
)

STATUSNAAM: dict[str, str] = {
    "NIEUW": "Nieuw",
    "GERESERVEERD": "Gereserveerd",
    "WACHT_OP_VOORRAAD": "Wacht op voorraad",
    "VRIJGEGEVEN": "Vrijgegeven",
    "PICKEN": "Wordt gepickt",
    "GEPICKT": "Gepickt",
    "INGEPAKT": "Ingepakt",
    "VERZONDEN": "Verzonden",
}

OVERGANGEN: dict[str, tuple[str, ...]] = {
    "NIEUW":             ("GERESERVEERD", "WACHT_OP_VOORRAAD"),
    "WACHT_OP_VOORRAAD": ("GERESERVEERD", "WACHT_OP_VOORRAAD"),
    "GERESERVEERD":      ("VRIJGEGEVEN",),
    "VRIJGEGEVEN":       ("PICKEN", "GEPICKT"),
    "PICKEN":            ("GEPICKT",),
    "GEPICKT":           ("INGEPAKT",),
    "INGEPAKT":          ("VERZONDEN",),
    "VERZONDEN":         (),
}


def mag_naar(van: str, naar: str) -> bool:
    """Mag een order van deze status naar die status?

    Een order die al gepickt is opnieuw reserveren, of vanuit NIEUW
    rechtstreeks naar VERZONDEN springen: allebei nee. Geen vrij
    tekstveld waar iemand "klaar?" in typt.
    """
    if van not in OVERGANGEN:
        raise KeyError(f"Onbekende orderstatus {van!r}")
    if naar not in ORDERSTATUS:
        raise KeyError(f"Onbekende orderstatus {naar!r}")
    return naar in OVERGANGEN[van]


def open_status(status: str) -> bool:
    """Staat deze order nog ergens op een lijst?"""
    return status != "VERZONDEN"


# ---------------------------------------------------------------------
#  R-UIT-03  Looproute
# ---------------------------------------------------------------------
#  seq = gang x 1.000.000 + vak_positie x 100 + niveau x 10
#  vak_positie = vak           als de gang oneven is
#                9999 - vak    als de gang even is
#
#  Die tweede regel is de slangroute: in een even gang loopt de picker
#  terug, dus telt het vak van hoog naar laag. Zonder dat loopt hij aan
#  het eind van elke gang helemaal terug naar het begin.
# ---------------------------------------------------------------------
def vak_positie(gang: int, vak: int) -> int:
    """Het vaknummer zoals de looproute het ziet."""
    return vak if gang % 2 else 9999 - vak


def looproute_seq(gang: int, vak: int, niveau: int) -> int:
    """R-UIT-03. De volgorde waarin een picker de locaties tegenkomt."""
    return gang * 1_000_000 + vak_positie(gang, vak) * 100 + niveau * 10


# ---------------------------------------------------------------------
#  R-UIT-07  Inpakken
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class Inpak:
    """Wat er op de vrachtbrief komt."""
    colli: int
    gewicht_g: int


def inpakgegevens(regels: dict[int, int], artikelen: dict[int, Artikel],
                  inst: Instellingen | None = None) -> Inpak:
    """R-UIT-07. Colli en gewicht uit wat er werkelijk gepickt is.

    `regels` is {product_id: gepickt aantal}. Artikelen zonder gewicht
    tellen niet mee — liever onderschatten dan een verzonnen getal op de
    vrachtbrief zetten. Dat is dezelfde keuze als in R-AFG-04.

    Het manco gaat niet mee: er wordt over `gepickt` gerekend, niet over
    `besteld`. Wat niet in de doos zit, weegt niets.
    """
    inst = inst or Instellingen()
    max_per_collo = inst.geheel("uit.max_colli_gewicht_g")
    if max_per_collo <= 0:
        raise ValueError("uit.max_colli_gewicht_g moet groter dan 0 zijn")

    gewicht = 0
    for product_id, aantal in regels.items():
        if aantal <= 0:
            continue
        a = artikelen.get(product_id)
        if a is None or a.g is None:
            continue
        gewicht += a.g * aantal

    return Inpak(colli=max(1, ceil(gewicht / max_per_collo)), gewicht_g=gewicht)


# ---------------------------------------------------------------------
#  De objecten waar de schermen mee werken
#
#  Bewust dezelfde soort dataclasses als in modellen.py: platte gegevens
#  zonder gedrag, gevuld door de vertaallaag.
# ---------------------------------------------------------------------
@dataclass
class Orderregel:
    idx: int
    product_id: int
    besteld: int
    gereserveerd: int = 0
    gepickt: int = 0
    manco: int = 0

    @property
    def open(self) -> int:
        """Wat er nog gereserveerd moet worden."""
        return max(0, self.besteld - self.gereserveerd)


@dataclass
class Order:
    id: int
    nummer: str
    klant: str
    status: str = "NIEUW"
    prio: int = 3
    at: datetime | None = None
    plaats: str | None = None
    land: str | None = None
    vervoerder: str | None = None
    soort: str | None = None
    colli: int | None = None
    gewicht_g: int | None = None
    track: str | None = None
    regels: list[Orderregel] = field(default_factory=list)

    @property
    def statusnaam(self) -> str:
        return STATUSNAAM.get(self.status, self.status)

    @property
    def compleet_gereserveerd(self) -> bool:
        return all(r.open == 0 for r in self.regels)

    @property
    def manco(self) -> int:
        return sum(r.manco for r in self.regels)


@dataclass
class Pickregel:
    """Een regel uit v_picklijst. Dit is de allocation-rij zelf."""
    allocation_id: int
    order_id: int
    ordernummer: str
    regel: int
    product_id: int
    sku: str
    oms: str
    location_id: int
    locatie: str
    seq: int
    qty: int
    gepickt: int = 0
    prio: int = 3
    zone_id: int = 0

    @property
    def nog_te_picken(self) -> int:
        return self.qty - self.gepickt


def teltaak_reden(ordernummer: str, tekort: int, gevraagd: int,
                  locatie: str) -> str:
    """De tekst bij de teltaak uit R-UIT-05, punt 3.

    Staat hier en niet in SQL om dezelfde reden als `gevolg_tekst` in
    meten.py: een tekst die een mens leest, schrijf je op de plek waar je
    hem kunt natesten zonder database. De databasefunctie vult dezelfde
    zin in als je hem niet meegeeft, zodat een aanroep met psql ook een
    leesbare teltaak oplevert.
    """
    return (f"Manco bij {ordernummer}: {tekort} van {gevraagd} "
            f"niet gevonden op {locatie}")
