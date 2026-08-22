"""Testgevallen T-01 t/m T-06c uit hoofdstuk 13 van de specificatie.

Alle verwachte waarden komen uit de draaiende browserversie. Wijkt een
uitkomst af, dan is het niet de test die fout is: dan wijkt deze versie
af van de versie die bij klanten draait.
"""

import unittest
from vakto import Artikel, Locatie, pas_berekening


def artikel(l, w, h, g_gram, stapelbaar=True):
    return Artikel(1, "TEST-1", l_mm=l, w_mm=w, h_mm=h, g=g_gram,
                   stapelbaar=stapelbaar)


def locatie(l, w, h, max_kg, type_id=1):
    return Locatie(1, "TEST-LOC", type_id, l, w, h, int(max_kg * 1000))


class TestPassen(unittest.TestCase):

    def test_t01_past_precies_een_keer(self):
        """R-PAS-03. De max(1, ...)-val: floor(1 * 0.85) is nul."""
        r = pas_berekening(artikel(1200, 800, 1500, 68_000),
                           locatie(1200, 800, 1500, 900), 0.85)
        self.assertEqual(r.qty, 1)
        self.assertEqual(r.limiet, "AFMETING")

    def test_t02_kleingoed_in_palletplaats(self):
        """R-PAS-02. De beste draaiing is 120x45x90, niet 120x90x45."""
        r = pas_berekening(artikel(120, 90, 45, 180),
                           locatie(1200, 800, 1500, 900), 0.85)
        self.assertEqual(r.qty, 2312)
        self.assertEqual(r.limiet, "AFMETING")
        self.assertEqual(r.orientatie, (120, 45, 90))

    def test_t03_past_alleen_gedraaid(self):
        """R-PAS-01. Zonder draaiingen zou hier nul uitkomen."""
        r = pas_berekening(artikel(600, 300, 200, 4_000),
                           locatie(400, 700, 250, 50), 0.85)
        self.assertEqual(r.qty, 1)
        self.assertEqual(r.orientatie, (300, 600, 200))

    def test_t04_past_in_geen_enkele_draaiing(self):
        """R-PAS-02. Nul is een geldig antwoord, geen None."""
        r = pas_berekening(artikel(900, 900, 900, 5_000),
                           locatie(300, 400, 220, 12), 0.85)
        self.assertEqual(r.qty, 0)
        self.assertEqual(r.limiet, "AFMETING")
        self.assertIsNone(r.orientatie)

    def test_t05_gewicht_is_de_beperking(self):
        """R-PAS-03. 142 passen er qua ruimte, 13 qua gewicht."""
        r = pas_berekening(artikel(200, 200, 200, 9_000),
                           locatie(1200, 800, 1500, 120), 0.85)
        self.assertEqual(r.qty, 13)
        self.assertEqual(r.limiet, "GEWICHT")

    def test_t06_niet_stapelbaar(self):
        """R-PAS-01. Eén laag, en maar twee draaiingen."""
        r = pas_berekening(artikel(300, 300, 400, 20_000, stapelbaar=False),
                           locatie(1200, 800, 1500, 900), 0.85)
        self.assertEqual(r.qty, 6)
        self.assertEqual(r.limiet, "AFMETING")

    def test_t06b_vulfactor_060(self):
        r = pas_berekening(artikel(120, 90, 45, 180),
                           locatie(600, 400, 350, 45), 0.60)
        self.assertEqual(r.qty, 84)

    def test_t06c_vulfactor_100(self):
        """Zelfde geval als T-06b. 140 x 0,60 = 84: de vulfactor werkt
        op het aantal, niet op de afmetingen."""
        r = pas_berekening(artikel(120, 90, 45, 180),
                           locatie(600, 400, 350, 45), 1.00)
        self.assertEqual(r.qty, 140)

    def test_nooit_gemeten_geeft_geen_getal(self):
        """R-AFG-01. Geen maat is niet hetzelfde als maat nul."""
        a = Artikel(1, "TEST-1")
        r = pas_berekening(a, locatie(600, 400, 350, 45), 0.85)
        self.assertIsNone(r.qty)
        self.assertEqual(r.limiet, "ONBEKEND")


if __name__ == "__main__":
    unittest.main()
