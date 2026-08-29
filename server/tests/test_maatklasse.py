"""Testgevallen T-08 t/m T-12 (R-AFG-02).

De maatklasse is een berekening uit de afmetingen, nooit een veld dat
iemand invult. Dat is precies wat Vakto anders doet dan de rest.
"""

import unittest
from vakto import cm3, maatklasse


class TestMaatklasse(unittest.TestCase):

    GEVALLEN = [
        ("T-08", (200, 200, 150),      6_000,     "XS"),
        ("T-09", (300, 400, 220),      26_400,    "S"),
        ("T-10", (600, 400, 350),      84_000,    "M"),
        ("T-11", (1200, 600, 500),     360_000,   "L"),
        ("T-12", (1200, 800, 1500),    1_440_000, "XL"),
    ]

    def test_gevallen(self):
        for naam, (l, w, h), verwacht_cm3, verwachte_klasse in self.GEVALLEN:
            with self.subTest(naam):
                self.assertEqual(cm3(l, w, h), verwacht_cm3)
                self.assertEqual(maatklasse(cm3(l, w, h)), verwachte_klasse)

    def test_grenzen_zijn_min_tot_max(self):
        """min <= cm3 < max. Precies op de grens hoort bij de klasse erboven."""
        self.assertEqual(maatklasse(7_999.9), "XS")
        self.assertEqual(maatklasse(8_000),   "S")
        self.assertEqual(maatklasse(49_999),  "S")
        self.assertEqual(maatklasse(50_000),  "M")

    def test_boven_de_laatste_grens(self):
        """Een zeecontainer is ook een palletplaats, wat ons betreft."""
        self.assertEqual(maatklasse(500_000_000), "XL")


if __name__ == "__main__":
    unittest.main()
