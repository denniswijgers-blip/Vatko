"""Locatie-etiketten met een streepjescode (R-SCAN-08).

Dit is code waar een fout niet opvalt. Een etiket dat er goed uitziet en
niet scant, merk je pas als er iemand met een handscanner voor de
stelling staat — en dan zijn er al duizend geplakt. Daarom worden de
streepjes hier nageteld in plaats van dat er naar het plaatje gekeken
wordt.

De verwachte waarden komen uit de draaiende browserversie: `code39()` in
`demo/bron/4-schermen/etiketten.js` is streep voor streep vergeleken met
wat hier uitkomt. Wijkt er iets af, dan drukt de ene versie een ander
etiket af dan de andere — en dat is precies het soort verschil waar
niemand op bedacht is.

Draait zonder database.
"""

import unittest

from vakto import etiketten as e


class TestCode39(unittest.TestCase):

    def test_de_tekenset(self):
        """Veertig tekens, elk negen strepen waarvan drie breed — vandaar
        de naam "3 van 9".

        Volledig Code 39 kent er vierenveertig; de vier die hier
        ontbreken zijn `$ / + %`. Die komen in geen enkele locatiecode
        voor, en `schoon()` maakt er een streepje van. Dezelfde veertig
        als de browserversie, want een etiket dat daar anders uitkomt is
        een etiket dat niet scant.
        """
        self.assertEqual(len(e.C39), 40)
        self.assertNotIn("$", e.C39)
        for teken, patroon in e.C39.items():
            with self.subTest(teken=teken):
                self.assertEqual(len(patroon), 9)
                self.assertEqual(patroon.count("w"), 3)

    def test_elk_patroon_is_uniek(self):
        """Twee tekens met hetzelfde patroon zou betekenen dat een
        scanner ze niet uit elkaar kan houden."""
        self.assertEqual(len(set(e.C39.values())), len(e.C39))

    def test_wat_er_niet_in_past_wordt_een_streepje(self):
        """Weigeren zou netter lijken, maar dan drukt hij voor een
        locatie met een rare code helemaal geen etiket af — en dan staat
        er straks één vak zonder label."""
        self.assertEqual(e.schoon("01-01-1"), "01-01-1")
        self.assertEqual(e.schoon("a/b#c"), "A-B-C")
        self.assertEqual(e.schoon("vak*1"), "VAK-1")     # ook de ster zelf
        self.assertEqual(e.schoon("é"), "-")

    def test_de_sterren_staan_eromheen(self):
        """Zonder start- en stopteken begint een scanner nergens aan."""
        strepen = e.strepen("A")
        # drie tekens (* A *) van negen strepen, met twee scheidingen
        self.assertEqual(len(strepen), 3 * 9 + 2)

    def test_smal_en_breed_verhouden_zich_als_een_op_drie(self):
        """R-SCAN-08. Wordt die verhouding ergens anders, dan piept de
        scanner en denkt de klant dat het systeem niet werkt."""
        breedtes = {b for b, _ in e.strepen("01-01-1")}
        self.assertEqual(breedtes, {1, 3})

    def test_de_strepen_wisselen_zwart_en_wit_af(self):
        """Binnen een teken. Tussen twee tekens zit een witte scheiding,
        dus daar staan twee witte naast elkaar."""
        strepen = e.strepen("A")
        for i in range(9):
            self.assertEqual(strepen[i][1], i % 2 == 0)

    def test_drie_brede_strepen_per_teken(self):
        for tekst in ("0", "Z", "-", "01-01-1"):
            with self.subTest(tekst=tekst):
                breed = sum(1 for b, _ in e.strepen(tekst) if b == e.BREED)
                self.assertEqual(breed, 3 * (len(tekst) + 2))

    def test_de_rustzone_staat_aan_weerskanten(self):
        """Zonder wit eromheen vindt een scanner het begin niet, en dan
        lijkt het etiket leeg."""
        svg = e.svg("01-01-1")
        # De eerste zwarte streep begint precies na de rustzone.
        self.assertIn(f'<rect x="{e.RUSTZONE}" y="0"', svg)
        # En de breedte is de som plus twee keer de rustzone.
        som = sum(b for b, _ in e.strepen("01-01-1"))
        self.assertIn(f'viewBox="0 0 {som + 2 * e.RUSTZONE} ', svg)

    def test_het_is_een_svg_met_vaste_verhoudingen(self):
        """Als SVG en niet als reeks blokjes: uitrekken mag niet."""
        svg = e.svg("01-01-1")
        self.assertIn('preserveAspectRatio="none"', svg)
        self.assertIn('viewBox=', svg)
        self.assertIn('role="img"', svg)

    def test_de_code_staat_in_de_toegankelijke_naam(self):
        self.assertIn('aria-label="streepjescode 01-01-1"', e.svg("01-01-1"))

    def test_een_code_met_aanhalingstekens_breekt_de_svg_niet(self):
        svg = e.svg('01"><script>')
        self.assertNotIn("<script>", svg)

    # -----------------------------------------------------------------
    #  Afgelezen uit de browserversie
    # -----------------------------------------------------------------
    def test_dezelfde_breedte_als_de_browserversie(self):
        """Uit `code39()` in demo/bron/4-schermen/etiketten.js, met de
        Playwright-vergelijking die de streepposities één voor één
        naliep."""
        for tekst, breed in (("01-01-1", 163), ("A", 67),
                             ("ART-2001", 179), ("ZZ 99.9", 163),
                             ("a/b#c", 131)):
            with self.subTest(tekst=tekst):
                self.assertIn(f'viewBox="0 0 {breed} 30"', e.svg(tekst))

    def test_het_aantal_zwarte_strepen(self):
        """Vijf zwarte strepen per teken, inclusief de twee sterren."""
        for tekst, strepen in (("01-01-1", 45), ("A", 15), ("ART-2001", 50)):
            with self.subTest(tekst=tekst):
                self.assertEqual(e.svg(tekst).count("<rect x=") - 1, strepen)


if __name__ == "__main__":
    unittest.main()
