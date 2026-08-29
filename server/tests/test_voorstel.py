"""Testgeval T-07 (R-INS) — het belangrijkste testgeval dat er is.

Een leeg magazijn met drie locaties. Veertig kleine artikelen. De
palletplaats past alles en scoort toch het laagst van de drie.

Zakt deze test, dan verkoop je een WMS dat palletplaatsen volgooit met
schroefjes. Dat is geen schoonheidsfoutje: dat is het product.
"""

import unittest
from vakto import (Artikel, Locatie, LocatieSoort, Magazijn, SOORTEN,
                   Voorraadregel, voorstel_inslag)


def leeg_magazijn() -> Magazijn:
    return Magazijn(
        locaties=[
            #  id  code       soort  L     W    H     max_g          seq
            Locatie(1, "01-01-1", 0, 300,  400, 220,  12_000,  seq=1),
            Locatie(2, "02-01-1", 0, 600,  400, 350,  45_000,  seq=2),
            Locatie(3, "03-01-1", 1, 1200, 800, 1500, 900_000, seq=3),
        ],
        artikelen=[
            Artikel(1, "TEST-1", "Testartikel",
                    l_mm=120, w_mm=90, h_mm=45, g=180),
        ],
        voorraad=[],
    )


class TestVoorstel(unittest.TestCase):

    def test_t07_rangschikking_en_scores(self):
        v = voorstel_inslag(leeg_magazijn(), product_id=1, aantal=40)
        self.assertEqual([x.locatie.code for x in v],
                         ["01-01-1", "02-01-1", "03-01-1"])
        self.assertEqual([x.vrij for x in v],  [30, 119, 2312])
        self.assertEqual([x.score for x in v], [438, 336, -298])
        self.assertEqual([x.alles for x in v], [False, True, True])

    def test_t07_benutting(self):
        v = voorstel_inslag(leeg_magazijn(), product_id=1, aantal=40)
        self.assertAlmostEqual(v[0].benutting * 100, 64.97, places=2)
        self.assertAlmostEqual(v[1].benutting * 100, 27.23, places=2)
        self.assertAlmostEqual(v[2].benutting * 100, 1.59,  places=2)

    def test_t07_de_palletplaats_verliest(self):
        """Het hart van het product in één regel."""
        v = voorstel_inslag(leeg_magazijn(), product_id=1, aantal=40)
        pallet = next(x for x in v if x.locatie.code == "03-01-1")
        klein = next(x for x in v if x.locatie.code == "01-01-1")
        self.assertTrue(pallet.alles, "de palletplaats past de hele partij")
        self.assertFalse(klein.alles, "het kleine vak past maar een deel")
        self.assertGreater(klein.score, pallet.score,
                           "en tóch hoort het kleine vak bovenaan")

    def test_strafterm_uit_zetten_draait_de_volgorde_om(self):
        """R-BASIS-04. Gedrag zit in een instelling, niet in de code."""
        from vakto import Instellingen
        inst = Instellingen({"putaway.prefer_smallest_fit": "false"})
        v = voorstel_inslag(leeg_magazijn(), 1, 40, inst=inst)
        self.assertEqual(v[0].locatie.code, "01-01-1")
        pallet = next(x for x in v if x.locatie.code == "03-01-1")
        self.assertEqual(pallet.score, 208)   # 8 + 200, zonder straf

    def test_t19_vol_vak_krijgt_geen_voorstel_meer(self):
        """R-INS-02, het derde budget.

        Deze test heeft een echte fout in de browserversie gevonden.
        Locatie 01-01-1 houdt er geometrisch 30; leg er 30 in en het
        systeem stelde er nog 16 bij voor. Oorzaak: het volumebudget is
        ruimer dan de echte stapeling, want dozen laten lucht over. De
        geometrische capaciteit moet ook verminderd worden met wat er al
        van dit artikel ligt.
        """
        mag = leeg_magazijn()
        mag.voorraad.append(Voorraadregel(product_id=1, location_id=1, qty=30))
        codes = [x.locatie.code for x in voorstel_inslag(mag, 1, 40)]
        self.assertNotIn("01-01-1", codes)

    def test_t20_gedeeltelijk_gevuld_vak_telt_correct_af(self):
        """R-INS-02. 2312 passen er in de palletplaats; liggen er 300,
        dan kunnen er nog 2012 bij. Niet 2218 (het volumebudget) en niet
        2312 (alsof er niets lag)."""
        mag = leeg_magazijn()
        mag.voorraad.append(Voorraadregel(product_id=1, location_id=3, qty=300))
        v = voorstel_inslag(mag, product_id=1, aantal=40)
        pallet = next(x for x in v if x.locatie.code == "03-01-1")
        self.assertEqual(pallet.vrij, 2012)

    def test_bezetting_van_andere_artikelen_telt_in_gewicht(self):
        """R-BASIS-05 en R-INS-02, op een vak dat gemengd mag.

        Twintig artikelen van 40 kg leggen 800 kg van de 900 kg vast. Er
        kan nog 100 kg bij, en dat zijn 555 stuks van 180 gram — niet
        2312 (de ruimte) en niet 2292 (2312 min de twintig stuks).
        """
        mag = leeg_magazijn()
        mag.soorten[6] = LocatieSoort(6, "BLM", "Gemengde bulk",
                                      bulk=True, mix=True, doel=True)
        mag.locatie(3).type_id = 6
        mag.artikelen.append(Artikel(2, "ZWAAR-1", l_mm=100, w_mm=100,
                                     h_mm=100, g=40_000))
        mag.voorraad.append(Voorraadregel(product_id=2, location_id=3, qty=20))
        v = voorstel_inslag(mag, product_id=1, aantal=40)
        pallet = next(x for x in v if x.locatie.code == "03-01-1")
        self.assertEqual(pallet.vrij, 555)

    def test_onbekende_locatiesoort_zegt_wat_je_moet_doen(self):
        mag = leeg_magazijn()
        mag.locatie(1).type_id = 99
        with self.assertRaises(KeyError) as e:
            voorstel_inslag(mag, 1, 40)
        self.assertIn("location_type", str(e.exception))

    def test_een_soort_per_vak_tenzij_gemengd(self):
        """R-INS-02. Ligt er al een ander artikel in een niet-gemengd vak,
        dan valt die locatie af."""
        mag = leeg_magazijn()
        mag.artikelen.append(Artikel(2, "ANDER-1", l_mm=50, w_mm=50, h_mm=50, g=100))
        mag.voorraad.append(Voorraadregel(product_id=2, location_id=1, qty=5))
        codes = [x.locatie.code for x in voorstel_inslag(mag, 1, 40)]
        self.assertNotIn("01-01-1", codes)

    def test_geen_voorstel_zonder_maat(self):
        """R-AFG-01. Nooit gemeten betekent: doet mee in voorraad, maar
        het systeem verzint geen plek."""
        mag = leeg_magazijn()
        mag.artikelen[0] = Artikel(1, "TEST-1")
        self.assertEqual(voorstel_inslag(mag, 1, 40), [])


if __name__ == "__main__":
    unittest.main()
