"""De afrondingsval (vakto/getallen.py).

Python's round() rondt 112,5 af naar 112, JavaScript naar 113. In het
scoren van een inslagvoorstel komt precies zo'n half getal voor:
150 x (30/40) is exact 112,5. Testgeval T-07 valt hierop om.
"""

import unittest
from vakto.getallen import rond


class TestAfronden(unittest.TestCase):

    def test_halve_naar_boven(self):
        self.assertEqual(rond(112.5), 113)
        self.assertEqual(rond(0.5), 1)
        self.assertEqual(rond(1.5), 2)
        self.assertEqual(rond(2.5), 3)     # Python's round() geeft hier 2

    def test_verschilt_van_de_ingebouwde_round(self):
        self.assertNotEqual(rond(112.5), round(112.5))

    def test_negatieve_getallen(self):
        """Math.round(-506.5) is -506 in JavaScript, niet -507."""
        self.assertEqual(rond(-506.3), -506)
        self.assertEqual(rond(-506.5), -506)
        self.assertEqual(rond(-506.6), -507)
