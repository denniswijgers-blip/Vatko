"""Vakto — de rekenkern.

Dit pakket bevat GEEN database-code. Dat is met opzet: de rekenregels
moeten testbaar zijn zonder dat er een PostgreSQL draait, en ze moeten
overal hetzelfde antwoord geven — in een test, in een webverzoek, in een
achtergrondtaak.

Zie de specificatie "De rekenkern, uitgeschreven". Elke functie hieronder
noemt de regel die hij uitvoert (R-PAS-02, R-INS-04, enzovoort).
"""

from .instellingen import Instellingen, STANDAARD
from .modellen import (Artikel, Locatie, LocatieSoort, Voorraadregel,
                       Magazijn, SOORTEN)
from .maten import cm3, maatklasse, MAATREGELS
from .passen import pas_berekening, orientaties, PasResultaat
from .voorstel import voorstel_inslag, Voorstel
from .meten import (Maat, Meting, Afwijking, Knelpunt, Melding,
                    bepaal_afwijking, gevolgen, gevolg_tekst,
                    leg_meting_vast, te_meten, GEEN_GEVOLGEN)
from .opslag import (boek, Boekfout, laad_magazijn, laad_instellingen,
                     schrijf_meting, sluit_melding, open_meldingen, meetlijst,
                     metingen_van, QUERIES)

__all__ = [
    "Instellingen", "STANDAARD",
    "Artikel", "Locatie", "LocatieSoort", "Voorraadregel", "Magazijn", "SOORTEN",
    "cm3", "maatklasse", "MAATREGELS",
    "pas_berekening", "orientaties", "PasResultaat",
    "voorstel_inslag", "Voorstel",
    "Maat", "Meting", "Afwijking", "Knelpunt", "Melding",
    "bepaal_afwijking", "gevolgen", "gevolg_tekst", "leg_meting_vast",
    "te_meten", "GEEN_GEVOLGEN",
    "boek", "Boekfout", "laad_magazijn", "laad_instellingen",
    "schrijf_meting", "sluit_melding", "open_meldingen", "meetlijst",
    "metingen_van",
    "QUERIES",
]
