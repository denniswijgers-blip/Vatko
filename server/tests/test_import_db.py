"""T-37 en T-38: de oefenbestanden er echt in zetten.

`test_inlezen.py` bewijst dat het rapport klopt, `tests-sql/test_import.sql`
bewijst dat de database het goed wegschrijft. Dit bestand doet het hele
kunstje in één keer: drie rommelige klantbestanden erin, en aan de andere
kant een magazijn waar de rekenkern meteen mee kan werken.

Dat is waar stap 7 op afgerekend wordt, en het is ook het moment waarop
dit systeem zichzelf verkoopt: een klant die zijn eigen artikelnummers op
zijn eigen locaties terugziet, met de eerste week meetwerk er al bij
opgeschreven, hoeft niets meer voorgesteld te krijgen.

Draait alleen als er een PostgreSQL bereikbaar is. Alles gebeurt in één
transactie die aan het eind wordt teruggedraaid.
"""

import unittest
from pathlib import Path

from vakto import voorstel_inslag
from vakto.inlezen import (controleer, herken_kolommen, lees_bestand,
                           raad_eenheden)
from vakto.opslag import (Boekfout, laad_magazijn, meetlijst, neem_over)

from .psqlschil import PsqlVerbinding, psql_beschikbaar

VOORBEELDEN = Path(__file__).resolve().parent.parent.parent / "verkoop" / "voorbeeldbestanden"
LOCATIES = VOORBEELDEN / "Rommelig - locaties (in cm).csv"
ARTIKELEN = VOORBEELDEN / "Rommelig - artikelen (Engels, xlsx).xlsx"
VOORRAAD = VOORBEELDEN / "Rommelig - voorraad.csv"

# Een import wil een leeg magazijn (R-IMP-07). In een test doen we alsof:
# TRUNCATE mag hier omdat alles wordt teruggedraaid.
LEEG = ("TRUNCATE journal, stock, measurement, allocation, order_line, "
        "customer_order, task, alert, event_log, product, product_group, "
        "location, zone CASCADE;")


def rapport_van_de_oefenbestanden():
    loc = lees_bestand(LOCATIES)
    art = lees_bestand(ARTIKELEN)
    vrd = lees_bestand(VOORRAAD)
    k_loc = herken_kolommen("locaties", loc.kop)
    k_art = herken_kolommen("artikelen", art.kop)
    k_vrd = herken_kolommen("voorraad", vrd.kop)
    return controleer(loc, k_loc, art, k_art, vrd, k_vrd,
                      raad_eenheden(loc, k_loc, art, k_art))


@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestImportTegenDeDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest(
                "Geen bereikbare PostgreSQL. Zet hem op met opzetten.sh, of "
                "sla deze tests over — de rest draait gewoon.")
        cls.rapport = rapport_van_de_oefenbestanden()

    def setUp(self):
        self.v = PsqlVerbinding()
        self.v.begin()
        self.v.stuur(LEEG)

    def tearDown(self):
        self.v.rollback()
        self.v.sluit()

    def tel(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]

    # -----------------------------------------------------------------
    #  T-37
    # -----------------------------------------------------------------
    def test_t37_de_oefenbestanden_erin(self):
        uit = neem_over(self.v, self.rapport, gebruiker="dennis")

        # 398 uit het bestand plus de doorloopplekken die erin ontbraken.
        self.assertEqual(uit["locaties"], 400)
        self.assertEqual(uit["aangemaakt"], 2)
        self.assertEqual(uit["artikelen"], 900)
        self.assertEqual(uit["voorraad"], 759)
        self.assertEqual(uit["zones"], 4)
        self.assertEqual(uit["groepen"], 5)
        # 900 artikelen min de 167 zonder complete maat.
        self.assertEqual(uit["metingen"], 733)

    def test_t37_beginvoorraad_staat_in_het_journaal(self):
        neem_over(self.v, self.rapport)
        self.assertEqual(self.tel("SELECT count(*) n FROM journal"), 759)
        self.assertEqual(
            self.tel("SELECT count(*) n FROM journal WHERE soort='IMPORT'"), 759)
        self.assertEqual(self.tel("SELECT count(*) n FROM stock"), 759)

    def test_t37_de_hele_lijst_moet_gemeten_worden(self):
        """Elk artikel staat op de meetlijst: 167 omdat er niets bekend is,
        de rest omdat een opgave van de leverancier geen weging is. Dat is
        precies het gesprek dat je bij een klant wilt voeren."""
        neem_over(self.v, self.rapport)
        lijst = meetlijst(self.v, limiet=2000)
        self.assertEqual(len(lijst), 900)
        redenen = {r[5] for r in lijst}
        self.assertEqual(redenen, {"NOOIT_GEMETEN", "OPGAVE_LEVERANCIER"})
        self.assertEqual(sum(1 for r in lijst if r[5] == "NOOIT_GEMETEN"), 167)

    def test_t37_de_rekenkern_kan_er_meteen_mee_werken(self):
        """Vanaf hier is er geen verschil meer met een magazijn dat al
        draaide: hetzelfde inslagvoorstel, dezelfde regels."""
        neem_over(self.v, self.rapport)
        mag = laad_magazijn(self.v)

        self.assertEqual(len(mag.locaties), 400)
        self.assertEqual(len(mag.artikelen), 900)
        self.assertEqual(len(mag.groepen), 5)

        gemeten = next(a for a in mag.artikelen if a.gemeten)
        voorstellen = voorstel_inslag(mag, gemeten.id, 40)
        self.assertTrue(voorstellen, "een gemeten artikel hoort een plek te krijgen")
        self.assertGreater(voorstellen[0].score, 0)

    def test_t37_de_maten_zijn_omgerekend(self):
        """De klant levert centimeters. Een vak van 30 cm hoort 300 mm te
        worden en niet 30 — anders past er niets meer in."""
        neem_over(self.v, self.rapport)
        kleinste = self.tel("SELECT min(l_mm) n FROM location")
        self.assertGreater(kleinste, 50)

    def test_t37_de_looproute_is_gevuld(self):
        """R-IMP-06. Zonder seq loopt de picker straks willekeurig."""
        neem_over(self.v, self.rapport)
        self.assertEqual(
            self.tel("SELECT count(*) n FROM location "
                     "WHERE seq = 0 AND type_id IN (0,1)"), 0)

    def test_t37_de_zones_hebben_verschillende_codes(self):
        neem_over(self.v, self.rapport)
        self.assertEqual(self.tel("SELECT count(DISTINCT code) n FROM zone"),
                         self.tel("SELECT count(*) n FROM zone"))

    # -----------------------------------------------------------------
    #  T-38 en de rest
    # -----------------------------------------------------------------
    def test_t38_een_tweede_import_wordt_geweigerd(self):
        """R-IMP-07. Een import is een nulmeting; twee keer draaien zou
        een draaiend magazijn overschrijven met een oud bestand."""
        neem_over(self.v, self.rapport)
        with self.assertRaises(Boekfout) as e:
            neem_over(self.v, self.rapport)
        self.assertIn("nulmeting", str(e.exception))

    def test_zonder_locaties_gebeurt_er_niets(self):
        leeg = controleer()
        with self.assertRaises(Boekfout) as e:
            neem_over(self.v, leeg)
        self.assertIn("locaties", str(e.exception))
        self.assertEqual(self.tel("SELECT count(*) n FROM journal"), 0)


if __name__ == "__main__":
    unittest.main()
