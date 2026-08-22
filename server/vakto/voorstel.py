"""Het inslagvoorstel (R-INS).

Passen is een ja-nee-vraag. Dit is een rangschikking, en daar zit het
verschil tussen een systeem dat werkt en een systeem dat een magazijn
langzaam laat vastlopen.

Het draait om één getal: BENUTTING — welk deel van de vrije ruimte vult
deze partij? Veertig schroefsets in een palletplaats komt uit op 1,6%, en
dat voorstel hoort onderaan, ook al past het er honderd keer in.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from math import floor

from .getallen import rond
from .instellingen import Instellingen
from .modellen import Locatie, Magazijn
from .passen import PasResultaat, pas_berekening


@dataclass
class Voorstel:
    locatie: Locatie
    vrij: int                   # hoeveel er van deze partij op kan
    alles: bool                 # past de hele gevraagde partij?
    benutting: float            # 0..1, zie R-INS-03
    score: int
    redenen: list[str] = field(default_factory=list)
    fit: PasResultaat | None = None


def voorstel_inslag(mag: Magazijn, product_id: int, aantal: int,
                    inst: Instellingen | None = None,
                    limiet: int = 8) -> list[Voorstel]:
    """R-INS-01 t/m R-INS-04. Geeft de best scorende locaties, aflopend."""
    inst = inst or Instellingen()
    vul = inst.getal("putaway.fill_factor")
    straf_aan = inst.aan("putaway.prefer_smallest_fit")
    te_ruim_onder = inst.getal("putaway.te_ruim_onder")
    W = inst.weging

    artikel = mag.artikel(product_id)
    if artikel is None or not artikel.gemeten:
        return []

    p_vol = artikel.volume_mm3
    p_gew = artikel.g
    bezet = mag.bezetting()

    uit: list[Voorstel] = []

    for loc in mag.locaties:
        soort = mag.soort(loc)
        if not soort.doel or not loc.actief:
            continue                                    # R-INS-01

        fit = pas_berekening(artikel, loc, vul)
        if not fit.qty:
            continue

        b = bezet.get(loc.id)
        bezet_vol = b.vol_mm3 if b else 0
        bezet_gew = b.gew_g if b else 0
        dit_artikel = b.per_artikel.get(product_id, 0) if b else 0
        andere_soorten = len(b.per_artikel) - (1 if dit_artikel else 0) if b else 0

        # Eén artikelsoort per vak, tenzij het vak gemengd mag (R-INS-02)
        if not soort.mix and andere_soorten > 0 and dit_artikel == 0:
            continue

        # ---- R-INS-02: drie budgetten, het kleinste wint -------------
        #  1. geometrisch: wat er bij kan volgens de stapeling, MINUS wat
        #     er van dit artikel al ligt. Zonder die aftrek stelt het
        #     systeem stuks voor op een vak dat al vol is: het volume-
        #     budget is ruimer dan de echte stapeling, want dozen laten
        #     altijd lucht over.
        #  2. volume: wat er nog bij kan na alles wat er ligt
        #  3. gewicht: wat het schap nog kan dragen
        loc_vol = loc.volume_mm3
        vrij = floor(min(
            fit.qty - dit_artikel,
            (loc_vol * vul - bezet_vol) / p_vol,
            (loc.max_g - bezet_gew) / p_gew,
        ))
        if vrij <= 0:
            continue

        alles = vrij >= aantal
        geplaatst = min(aantal, vrij)

        # ---- R-INS-03: benutting ------------------------------------
        benutting = (geplaatst * p_vol) / (loc_vol * vul)

        # ---- R-INS-04: score ----------------------------------------
        score = rond(W["benutting"] * min(1.0, benutting))
        redenen: list[str] = []

        if dit_artikel > 0:
            score += rond(W["zelfde_artikel"] * min(1.0, vrij / aantal))
            redenen.append("artikel ligt hier al")

        if soort.pick and artikel.min_qty and dit_artikel < artikel.min_qty:
            score += W["picklocatie_aanvul"]
            redenen.append("picklocatie onder aanvuldrempel")

        if alles:
            score += W["hele_partij_past"]
            redenen.append("hele partij past")
        else:
            score += rond(W["deelvulling_max"] * (vrij / aantal))
            redenen.append(f"{vrij} van {aantal} st past")

        if straf_aan and benutting < te_ruim_onder:
            score += rond(W["te_ruim_straf"] * (1 - benutting / te_ruim_onder))
            redenen.append(f"benutting {benutting * 100:.1f}%")

        uit.append(Voorstel(loc, vrij, alles, benutting, score, redenen, fit))

    # Aflopend op score; bij gelijke stand op looproute, zodat de volgorde
    # altijd dezelfde is en een test niet willekeurig omvalt.
    uit.sort(key=lambda v: (-v.score, v.locatie.seq, v.locatie.id))
    return uit[:limiet]
