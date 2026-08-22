"""Zelfcontrole (R-ZC) — hoofdstuk 9.

Draait na elke mutatie. Alles hier is een gevolgtrekking uit de huidige
toestand, dus het mag zo vaak draaien als je wilt zonder dat er iets
dubbel gebeurt. Dat is niet toevallig zo gebouwd maar de kern van
R-BASIS-03: een mens vinkt niets af. Meldingen sluiten zichzelf zodra de
aanleiding weg is, taken vervallen zodra ze overbodig zijn.

Wat wél een mens blijft, zijn precies twee dingen: "niet meer melden voor
dit artikel" (R-MEET) en een aanvuldrempel aanpassen (R-OPT-05). Beide
zijn oordelen. Al het andere — opmerken, klaarzetten, sluiten, laten
vervallen — doet het systeem.

Er staat hier geen database-code in. `hertoets()` krijgt de toestand mee
en geeft terug wat er zou moeten veranderen; `opslag.py` schrijft dat weg
via `zelfcontrole.sql`, in één transactie. Zo kun je elk geval hieronder
natesten zonder dat er een PostgreSQL draait — en dat is precies wat
tests/test_zelfcontrole.py doet.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .instellingen import Instellingen
from .maten import cm3
from .meten import Knelpunt, Maat, Melding, gevolgen
from .modellen import Magazijn, Taak
from .optimalisatie import (Advies, Bijwerking, Pick, Pickplek, aanvultaken,
                            drempeladvies, pickplekvoorstellen, samenvoegtaken,
                            snelheden, telplan)
from .passen import pas_berekening
from .voorstel import voorstel_inslag

VANZELF_OPGELOST = "Vanzelf opgelost — de voorraad past weer."


@dataclass(frozen=True)
class Vervallen:
    """Een taak die niet meer nodig is. De reden gaat mee (R-ZC-03)."""
    taak: Taak
    reden: str


@dataclass
class Uitkomst:
    """Wat de zelfcontrole van deze ronde vindt dat er moet gebeuren.

    Niets hiervan is weggeschreven: dit is een voorstel aan `opslag.py`.
    Dat maakt de hele hertoets testbaar zonder database, en het maakt
    zichtbaar wat er zou gebeuren voordat het gebeurt.
    """
    nieuwe_taken: list[Taak] = field(default_factory=list)
    bijwerken: list[Bijwerking] = field(default_factory=list)
    vervallen: list[Vervallen] = field(default_factory=list)
    gesloten: list[Melding] = field(default_factory=list)
    bijgewerkte_meldingen: list[Melding] = field(default_factory=list)
    adviezen: list[Advies] = field(default_factory=list)
    pickplekken: list[Pickplek] = field(default_factory=list)
    regels: list[str] = field(default_factory=list)

    def noteer(self, tekst: str) -> None:
        self.regels.append(tekst)

    @property
    def stil(self) -> bool:
        """Niets te doen. Handig om te weten of er iets te schrijven valt."""
        return not (self.nieuwe_taken or self.bijwerken or self.vervallen
                    or self.gesloten or self.bijgewerkte_meldingen)


# ---------------------------------------------------------------------
#  R-ZC-01 en R-ZC-02  Meldingen opnieuw beoordelen, overloop verplaatsen
# ---------------------------------------------------------------------
def _huidige_maat(mag: Magazijn, product_id: int) -> Maat | None:
    a = mag.artikel(product_id)
    if a is None or not a.gemeten:
        return None
    return Maat(a.l_mm, a.w_mm, a.h_mm, a.g)


def beoordeel_meldingen(mag: Magazijn, meldingen: list[Melding],
                        taken: list[Taak], uit: Uitkomst,
                        inst: Instellingen | None = None) -> None:
    """R-ZC-01. Een melding is een uitspraak over de huidige toestand.

    Klopt die uitspraak niet meer, dan gaat hij dicht — vanzelf, met een
    regel in het log erbij zodat je later kunt navragen waarom. Klopt hij
    nog wel, dan wordt de tekst bijgewerkt en zet het systeem het werk
    klaar dat het zelf kan bedenken (R-ZC-02).
    """
    inst = inst or Instellingen()

    for melding in meldingen:
        if melding.status != "OPEN":
            continue
        artikel = mag.artikel(melding.product_id)
        if artikel is None:
            continue
        sku = artikel.sku
        maat = _huidige_maat(mag, melding.product_id)
        knel = gevolgen(mag, melding.product_id, maat, inst) if maat else []

        if not knel:
            melding.status = "OPGELOST"
            melding.gevolg = VANZELF_OPGELOST
            uit.gesloten.append(melding)
            uit.noteer(f"{sku}: afwijking vanzelf gesloten, de voorraad past weer")
            continue

        melding.knelpunten = list(knel)
        melding.gevolg = "Past niet meer op: " + ", ".join(str(k) for k in knel)
        uit.bijgewerkte_meldingen.append(melding)
        _overloop(mag, melding, knel, taken, uit, inst, sku)


def _overloop(mag: Magazijn, melding: Melding, knel: list[Knelpunt],
              taken: list[Taak], uit: Uitkomst, inst: Instellingen,
              sku: str) -> None:
    """R-ZC-02. Per locatie in de knel: zoek een plek voor het teveel.

    Niets gevonden is geen taak. Dat vraagt een menselijke keuze — welk
    vak maak je vrij? — en dan zeg je dat er ook bij in plaats van een
    onuitvoerbare taak op de vloer af te leveren.
    """
    open_overloop = {(t.product_id, t.van) for t in taken
                     if t.soort == "OVERLOOP" and t.status == "TODO"}
    nieuw_overloop = {(t.product_id, t.van) for t in uit.nieuwe_taken
                      if t.soort == "OVERLOOP"}

    for k in knel:
        teveel = k.ligt - k.past
        if teveel <= 0:
            continue
        sleutel = (melding.product_id, k.location_id)
        if sleutel in open_overloop or sleutel in nieuw_overloop:
            continue

        doel = next((v for v in voorstel_inslag(mag, melding.product_id,
                                                teveel, inst, limiet=4)
                     if v.locatie.id != k.location_id), None)
        if doel is None:
            continue

        nieuw_overloop.add(sleutel)
        uit.nieuwe_taken.append(Taak(
            soort="OVERLOOP", naam="Overloop verplaatsen", prio=15,
            product_id=melding.product_id, van=k.location_id,
            naar=doel.locatie.id,
            qty=teveel if doel.alles else min(teveel, doel.vrij),
            aanleiding="afwijking",
            reden=f"{k.code} zit {teveel} st over de nieuwe maat"))
        uit.noteer(f"{sku}: verplaatstaak aangemaakt, {teveel} st van "
                   f"{k.code} naar {doel.locatie.code}")


# ---------------------------------------------------------------------
#  R-ZC-03  Taken laten vervallen
#
#  Vervallen taken blijven staan met status VERVALLEN en de reden erbij.
#  Verwijderen mag niet: dan kun je achteraf niet meer navragen wat er
#  gebeurde, en juist dat is waar een magazijnchef om vraagt zodra er
#  iets misgaat.
# ---------------------------------------------------------------------
def _rij(mag: Magazijn, product_id: int, location_id: int | None):
    if location_id is None:
        return None
    for s in mag.voorraad:
        if s.product_id == product_id and s.location_id == location_id:
            return s
    return None


def _reden_vervallen(mag: Magazijn, taak: Taak,
                     inst: Instellingen) -> str | None:
    """Waarom is deze taak niet meer nodig? None = hij is nog nodig."""
    vul = inst.getal("putaway.fill_factor")
    artikel = mag.artikel(taak.product_id)
    bron = _rij(mag, taak.product_id, taak.van)
    doel = _rij(mag, taak.product_id, taak.naar)

    if taak.soort == "REPLENISH":
        if artikel and artikel.min_qty and doel and doel.qty >= artikel.min_qty:
            return "picklocatie is weer op peil"
        if bron is None or bron.qty <= 0:
            return "er ligt geen bulkvoorraad meer om mee aan te vullen"
        return None

    if taak.soort == "OVERLOOP":
        if bron is None or bron.qty <= 0:
            return "de bronlocatie is inmiddels leeg"
        loc = mag.locatie(taak.van)
        if artikel and loc:
            fit = pas_berekening(artikel, loc, vul)
            if fit.qty is not None and fit.qty >= bron.qty:
                return "het past er inmiddels weer in"
        return None

    if taak.soort == "SAMENVOEG":
        if bron is None or bron.qty <= 0:
            return "de bronlocatie is al leeg"
        if bron.res > 0 or (doel is not None and doel.res > 0):
            return "er is inmiddels voorraad gereserveerd voor een order"
        if doel is None:
            return "op de doellocatie ligt dit artikel niet meer"
        return None

    if taak.soort == "PICKPLEK":
        for s in mag.voorraad:
            if s.product_id != taak.product_id or s.qty <= 0:
                continue
            loc = mag.locatie(s.location_id)
            if loc is not None and mag.soort(loc).pick:
                return "het artikel heeft inmiddels een picklocatie"
        return None

    if taak.soort == "CYCLE_COUNT":
        loc = mag.locatie(taak.naar)
        if loc is not None and loc.geteld_op and taak.at \
                and loc.geteld_op > taak.at:
            return "de locatie is inmiddels geteld"
        if not any(s.location_id == taak.naar and s.qty > 0
                   for s in mag.voorraad):
            return "er ligt niets meer op deze locatie"
        return None

    return None


def laat_vervallen(mag: Magazijn, taken: list[Taak], uit: Uitkomst,
                   inst: Instellingen | None = None) -> None:
    """R-ZC-03. Elke openstaande taak langs zijn eigen vervalvoorwaarde."""
    inst = inst or Instellingen()
    for taak in taken:
        if taak.status != "TODO":
            continue
        reden = _reden_vervallen(mag, taak, inst)
        if reden is None:
            continue
        artikel = mag.artikel(taak.product_id)
        sku = artikel.sku if artikel else str(taak.product_id)
        uit.vervallen.append(Vervallen(taak, reden))
        uit.noteer(f"{sku}: taak vervallen — {reden}")


# ---------------------------------------------------------------------
#  Alles achter elkaar
# ---------------------------------------------------------------------
def hertoets(mag: Magazijn, taken: list[Taak], meldingen: list[Melding],
             vraag: dict[int, int] | None = None,
             picks: list[Pick] | None = None,
             inst: Instellingen | None = None,
             nu: datetime | None = None,
             zwaar: bool = True) -> Uitkomst:
    """Eén ronde zelfcontrole. Geeft terug wat er zou moeten gebeuren.

    De volgorde is niet willekeurig:

      1. eerst meldingen beoordelen, want daar komt werk uit (R-ZC-02);
      2. dan taken laten vervallen, zodat de optimalisatie daarna niet
         redeneert tegen taken die er niet meer horen te zijn;
      3. dan pas nieuw werk bedenken.

    `zwaar=False` slaat hoofdstuk 10 over. In de browserversie draait dat
    hooguit één keer per 900 ms; op een server hoort het in een
    achtergrondtaak elke paar minuten, of na een golf boekingen. Wat er
    hierboven staat moet wél elke keer kloppen: dat is wat iemand op zijn
    scherm ziet op het moment dat hij kijkt.
    """
    inst = inst or Instellingen()
    nu = nu or datetime.now(timezone.utc)
    uit = Uitkomst()

    beoordeel_meldingen(mag, meldingen, taken, uit, inst)
    laat_vervallen(mag, taken, uit, inst)

    # Wat zojuist vervallen is, telt niet meer mee als bestaand werk.
    vervallen_taken = {id(v.taak) for v in uit.vervallen}
    nog_open = [t for t in taken if id(t) not in vervallen_taken]
    nog_open += uit.nieuwe_taken

    snel = snelheden(picks or [], inst, nu)

    nieuw, bijwerken = aanvultaken(mag, nog_open, vraag or {}, snel, inst)
    uit.nieuwe_taken += nieuw
    uit.bijwerken += bijwerken
    for t in nieuw:
        artikel = mag.artikel(t.product_id)
        loc = mag.locatie(t.naar)
        uit.noteer(f"{artikel.sku if artikel else t.product_id}: aanvultaak "
                   f"{t.qty} st naar {loc.code if loc else t.naar} ({t.aanleiding})")

    if not zwaar:
        return uit

    nog_open = nog_open + nieuw
    uit.nieuwe_taken += samenvoegtaken(mag, nog_open, inst)
    uit.nieuwe_taken += telplan(mag, nog_open, inst, nu)
    uit.adviezen = drempeladvies(mag, snel, inst)
    uit.pickplekken = pickplekvoorstellen(mag, nog_open, snel, inst)
    return uit
