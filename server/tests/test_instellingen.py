"""Bewaakt dat de specificatie, het schema en de code hetzelfde zeggen.

Deze test bestaat om precies één reden: zodra iemand een instelling
toevoegt in de code maar vergeet in seed_config.sql (of andersom), lopen
de browserversie en de serverversie uit elkaar. Dat gebeurt stil, en je
merkt het pas bij een klant.
"""

import re
import unittest
from pathlib import Path

from vakto.instellingen import STANDAARD, WEGING, Instellingen

WORTEL = Path(__file__).resolve().parent.parent


def sleutels_uit_sql(bestand: str, tabel: str) -> set[str]:
    tekst = (WORTEL / bestand).read_text(encoding="utf-8")
    blok = tekst.split(f"INSERT INTO {tabel}", 1)[1].split(";", 1)[0]
    return set(re.findall(r"\('([a-z0-9._]+)'", blok))


class TestInstellingen(unittest.TestCase):

    def test_code_en_sql_kennen_dezelfde_instellingen(self):
        uit_sql = sleutels_uit_sql("seed_config.sql", "setting")
        self.assertEqual(set(STANDAARD), uit_sql,
                         "STANDAARD in instellingen.py en seed_config.sql "
                         "moeten precies dezelfde sleutels hebben")

    def test_code_en_sql_kennen_dezelfde_wegingen(self):
        uit_sql = sleutels_uit_sql("seed_config.sql", "weging")
        self.assertEqual(set(WEGING), uit_sql)

    def test_de_straf_weegt_zwaarder_dan_hele_partij_past(self):
        """R-INS-04. Dit is de invariant die er echt toe doet.

        Bij een benutting die naar nul gaat, gaat ook de benuttingsbonus
        naar nul en blijft er over: hele_partij_past minus de volle straf.
        Is die som positief, dan wordt "alles past" beloond in een vak dat
        veel te ruim is — precies wat we willen voorkomen.

        (De straf is NIET groter dan zelfde_artikel + hele_partij_past
        samen, en dat hoeft ook niet: een vak waar het artikel al ligt is
        een goede plek, want dat scheelt een locatie.)
        """
        self.assertGreater(abs(WEGING["te_ruim_straf"]),
                           WEGING["hele_partij_past"])

    def test_omzetten_van_tekst(self):
        i = Instellingen({"putaway.fill_factor": "0.6"})
        self.assertEqual(i.getal("putaway.fill_factor"), 0.6)
        self.assertTrue(i.aan("putaway.prefer_smallest_fit"))
        self.assertEqual(i.geheel("ui.rows_per_page"), 60)

    def test_onbekende_sleutel_zegt_wat_je_moet_doen(self):
        with self.assertRaises(KeyError) as e:
            Instellingen().tekst("bestaat.niet")
        self.assertIn("seed_config.sql", str(e.exception))
