"""Meten en afwijking (R-MEET).

Het tweede idee waar Vakto op staat: een artikelafmeting is een tijdlijn,
geen veld. Wie de maat overschrijft weet volgende maand niet meer dat de
doos in maart groter werd — en snapt dus ook niet waarom er ineens vier
pallets te weinig plek is.

Er staat hier bewust géén database-code in. De vertaallaag (`opslag.py`)
schrijft de meting en de melding weg; dit bestand rekent alleen uit wat
er waar is. Zo kun je elk geval hieronder in drie regels natesten zonder
dat er een PostgreSQL draait.

Het zwaartepunt zit niet in het signaleren maar in R-MEET-03: bij een
afwijking loopt het systeem zelf alle locaties langs waar het artikel nu
ligt en rekent met de nieuwe maat opnieuw uit hoeveel er past. Dat is het
verschil tussen "let op, deze doos is groter" en "let op, op 01-01-1 ligt
30 en er passen er nog 27".
"""

from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from .getallen import rond
from .instellingen import Instellingen
from .modellen import Artikel, Locatie, Magazijn
from .passen import pas_berekening

BRONNEN = ("SUPPLIER", "RECEIPT", "PACKING", "CONTROL")


@dataclass(frozen=True)
class Maat:
    """Eén meting, los van het artikel waar hij bij hoort."""
    l_mm: int
    w_mm: int
    h_mm: int
    g: int

    @property
    def volume_mm3(self) -> int:
        return self.l_mm * self.w_mm * self.h_mm


@dataclass(frozen=True)
class Meting:
    """Een rij uit `measurement`. Append-only (R-MEET-01)."""
    product_id: int
    at: datetime
    bron: str
    maat: Maat
    notitie: str | None = None


@dataclass(frozen=True)
class Afwijking:
    """Het verschil tussen twee metingen, in procenten (R-MEET-02)."""
    d_vol: float
    d_gew: float
    melden: bool                    # staat één van beide boven de drempel?


@dataclass(frozen=True)
class Knelpunt:
    """Een locatie waar met de nieuwe maat meer ligt dan er past."""
    location_id: int
    code: str
    ligt: int
    past: int

    def __str__(self) -> str:
        return f"{self.code} (ligt {self.ligt}, past nog {self.past})"


@dataclass
class Melding:
    """Wat er in `alert` terechtkomt."""
    product_id: int
    at: datetime
    d_vol: float
    d_gew: float
    gevolg: str
    status: str = "OPEN"
    knelpunten: list[Knelpunt] = field(default_factory=list)
    # Pas gevuld nadat de database de melding heeft weggeschreven; de
    # rekenkern zelf deelt geen nummers uit.
    id: int | None = None


GEEN_GEVOLGEN = "Geen gevolgen voor huidige voorraadlocaties."


def _pct(deel: float, geheel: float) -> float:
    """Procentueel verschil, onafgerond."""
    if not geheel:
        return 0.0
    return deel / geheel * 100


def _afgerond(pct: float) -> float:
    """Eén decimaal, afgerond zoals de browserversie het doet.

    Met opzet `rond(x * 10) / 10` en niet Python's round(x, 1): die laatste
    rondt 12,25 naar 12,2 (bankiersafronding) en Math.round naar 12,3. Twee
    implementaties die anders afronden zetten verschillende percentages in
    dezelfde melding, en dan lijkt de ene versie kapot terwijl er niets aan
    de hand is. Zie getallen.py.
    """
    return rond(pct * 10) / 10


def bepaal_afwijking(vorige: Maat | None, nieuw: Maat,
                     drempel: float) -> Afwijking | None:
    """R-MEET-02. Geen vorige meting = geen melding, klaar.

    Dat is geen luiheid maar logica: bij de eerste meting is er niets om
    van af te wijken. Een nieuw artikel hoort geen alarm te geven.
    """
    if vorige is None:
        return None
    d_vol = _pct(nieuw.volume_mm3 - vorige.volume_mm3, vorige.volume_mm3)
    d_gew = _pct(nieuw.g - vorige.g, vorige.g)
    # De drempel toetsen we op het ONAFGERONDE getal en pas daarna ronden
    # we af voor de melding. Andersom zou 14,96% na afronding 15,0 worden
    # en dus alarm geven terwijl de afwijking onder de drempel zit — een
    # melding die je niet kunt uitleggen aan degene die hem krijgt.
    melden = abs(d_vol) >= drempel or abs(d_gew) >= drempel
    return Afwijking(_afgerond(d_vol), _afgerond(d_gew), melden)


def gevolgen(mag: Magazijn, product_id: int, nieuw: Maat,
             inst: Instellingen | None = None) -> list[Knelpunt]:
    """R-MEET-03. Waar ligt er nu meer dan er straks nog past?

    Let op de volgorde van de uitkomst: op `location.seq`, niet op de
    volgorde waarin de voorraadregels toevallig uit de database komen.
    De tekst van een melding moet bij elke herberekening dezelfde zijn,
    anders lijkt een ongewijzigde melding steeds te veranderen — en dan
    gaat de zelfcontrole (R-ZC-01) meldingen bijwerken die niets nieuws
    te zeggen hebben.

    Ontvangst, keuring, schade en verzendgereed tellen niet mee. Dat zijn
    doorloopplekken met een nominale maat — een pallet die daar een dag
    staat "past" er niet minder om, en een melding erover kun je nergens
    mee oplossen. De vlag is `location_type.doel`, dus een klant die dat
    anders wil zet het in de tabel om (R-BASIS-04).
    """
    inst = inst or Instellingen()
    vul = inst.getal("putaway.fill_factor")
    artikel = mag.artikel(product_id)
    if artikel is None:
        return []

    # Een artikel met de níeuwe maat, zonder het magazijn aan te raken.
    nep = replace(artikel, l_mm=nieuw.l_mm, w_mm=nieuw.w_mm,
                  h_mm=nieuw.h_mm, g=nieuw.g)

    uit: list[tuple[int, int, Knelpunt]] = []
    for s in mag.voorraad:
        if s.product_id != product_id or s.qty <= 0:
            continue
        loc = mag.locatie(s.location_id)
        if loc is None or not mag.soort(loc).doel:
            continue
        fit = pas_berekening(nep, loc, vul)
        if fit.qty is not None and fit.qty < s.qty:
            uit.append((loc.seq, loc.id,
                        Knelpunt(loc.id, loc.code, s.qty, fit.qty)))
    uit.sort(key=lambda r: (r[0], r[1]))
    return [k for _, _, k in uit]


def gevolg_tekst(knelpunten: list[Knelpunt]) -> str:
    """De zin die de magazijnchef leest. Eén tekst, twee vormen."""
    if not knelpunten:
        return GEEN_GEVOLGEN
    return "Past niet meer op: " + ", ".join(str(k) for k in knelpunten)


def leg_meting_vast(mag: Magazijn, product_id: int, l_mm: int, w_mm: int,
                    h_mm: int, g: int, bron: str = "RECEIPT",
                    notitie: str | None = None,
                    inst: Instellingen | None = None,
                    nu: datetime | None = None) -> Melding | None:
    """R-MEET-01 t/m R-MEET-03 in één handeling.

    Werkt de momentopname in `mag` bij naar de nieuwe maat en geeft een
    melding terug als die er is — of None als er niets aan de hand is.

    De volgorde is belangrijk: eerst de afwijking bepalen (die kijkt naar
    de OUDE maat), dan pas het artikel bijwerken. Andersom vergelijk je
    de nieuwe maat met zichzelf en krijg je nooit een melding.

    Wat dit NIET doet is wegschrijven. Dat hoort in één transactie samen
    met de melding, en dat regelt `opslag.leg_meting_vast()`.
    """
    if bron not in BRONNEN:
        raise ValueError(f"Onbekende bron {bron!r}; kies uit {', '.join(BRONNEN)}")
    for naam, waarde in (("lengte", l_mm), ("breedte", w_mm),
                         ("hoogte", h_mm), ("gewicht", g)):
        if waarde is None or waarde <= 0:
            raise ValueError(f"De {naam} moet groter dan 0 zijn, niet {waarde!r}")

    inst = inst or Instellingen()
    nu = nu or datetime.now(timezone.utc)
    drempel = inst.getal("drift.alert_threshold_pct")

    artikel = mag.artikel(product_id)
    if artikel is None:
        raise KeyError(f"Artikel {product_id} bestaat niet in dit magazijn")

    vorige = (Maat(artikel.l_mm, artikel.w_mm, artikel.h_mm, artikel.g)
              if artikel.gemeten else None)
    nieuw = Maat(l_mm, w_mm, h_mm, g)

    afw = bepaal_afwijking(vorige, nieuw, drempel)

    # De momentopname bijwerken: vanaf nu rekent alles met de nieuwe maat.
    artikel.l_mm, artikel.w_mm = l_mm, w_mm
    artikel.h_mm, artikel.g = h_mm, g
    artikel.gemeten_op, artikel.bron = nu, bron

    if afw is None or not afw.melden:
        return None

    knel = gevolgen(mag, product_id, nieuw, inst)
    return Melding(product_id=product_id, at=nu,
                   d_vol=afw.d_vol, d_gew=afw.d_gew,
                   gevolg=gevolg_tekst(knel), knelpunten=knel)


def te_meten(mag: Magazijn, inst: Instellingen | None = None,
             nu: datetime | None = None) -> list[Artikel]:
    """R-MEET-04. Wat moet er (opnieuw) op de weegschaal?

    Drie redenen, in deze volgorde van ernst:
      1. nooit gemeten          — zonder maat geen inslagvoorstel
      2. nieuwste bron SUPPLIER — een opgegeven maat is geen gemeten maat
      3. ouder dan de instelling `drift.remeasure_after_days`

    Oudste eerst, en nooit-gemeten helemaal bovenaan. Zo is de lijst
    meteen een werkvolgorde en niet nog een lijst om te sorteren.
    """
    inst = inst or Instellingen()
    nu = nu or datetime.now(timezone.utc)
    dagen = inst.geheel("drift.remeasure_after_days")
    grens = nu - timedelta(days=dagen)

    uit: list[tuple[int, float, Artikel]] = []
    for a in mag.artikelen:
        if not a.gemeten or a.gemeten_op is None:
            uit.append((0, 0.0, a))
            continue
        gemeten_op = a.gemeten_op
        if gemeten_op.tzinfo is None:
            gemeten_op = gemeten_op.replace(tzinfo=timezone.utc)
        if a.bron == "SUPPLIER" or gemeten_op < grens:
            uit.append((1, gemeten_op.timestamp(), a))
    uit.sort(key=lambda r: (r[0], r[1], r[2].id))
    return [a for _, _, a in uit]
