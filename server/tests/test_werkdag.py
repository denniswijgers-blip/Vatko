"""T-18: een hele werkdag, van de eerste order tot de laatste pakbon.

Losse tests bewijzen dat één regel klopt. Deze bewijst dat ze elkaar niet
in de weg zitten. Er komen orders binnen, ze worden gereserveerd,
vrijgegeven, gepickt (met manco's ertussen), ingepakt en verzonden; er
komt voorraad binnen die wordt ingeslagen; de zelfcontrole draait na elke
golf en er wordt werk uitgevoerd.

Aan het eind moeten drie dingen kloppen:

  * nul negatieve voorraadregels
  * nergens res > qty
  * geen hangende reserveringen

De eerste twee bewaakt de database met een CHECK. Dat maakt ze niet
minder waard om te controleren: als iemand het schema uitkleedt "omdat
die check in de weg zat", wil je dat hier horen en niet bij een klant.

Draait alleen als er een PostgreSQL bereikbaar is. Alles gebeurt in één
transactie die aan het eind wordt teruggedraaid.
"""

import unittest
from pathlib import Path

from vakto.inlezen import (controleer, herken_kolommen, lees_bestand,
                           raad_eenheden)
from vakto.opslag import neem_over
from vakto.werkdag import DAGEIND, DAGSTART, controleer_einde, draai_werkdag, klok

from .psqlschil import PsqlVerbinding, psql_beschikbaar

VOORBEELDEN = Path(__file__).resolve().parent.parent.parent / "verkoop" / "voorbeeldbestanden"
LOCATIES = VOORBEELDEN / "Rommelig - locaties (in cm).csv"
ARTIKELEN = VOORBEELDEN / "Rommelig - artikelen (Engels, xlsx).xlsx"
VOORRAAD = VOORBEELDEN / "Rommelig - voorraad.csv"

LEEG = ("TRUNCATE journal, stock, measurement, allocation, order_line, "
        "customer_order, task, alert, event_log, product, product_group, "
        "location, zone CASCADE;")


class TestKlok(unittest.TestCase):
    """Draait altijd; de rest heeft een database nodig."""

    def test_de_klok(self):
        self.assertEqual(klok(DAGSTART), "07:00")
        self.assertEqual(klok(DAGEIND), "17:00")
        self.assertEqual(klok(9 * 60 + 35), "09:35")


@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestWerkdag(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest(
                "Geen bereikbare PostgreSQL. Zet hem op met opzetten.sh, of "
                "sla deze tests over — de rest draait gewoon.")
        loc = lees_bestand(LOCATIES)
        art = lees_bestand(ARTIKELEN)
        vrd = lees_bestand(VOORRAAD)
        k_loc = herken_kolommen("locaties", loc.kop)
        k_art = herken_kolommen("artikelen", art.kop)
        k_vrd = herken_kolommen("voorraad", vrd.kop)
        rapport = controleer(loc, k_loc, art, k_art, vrd, k_vrd,
                             raad_eenheden(loc, k_loc, art, k_art))

        # De dag draait één keer voor alle tests hieronder. Ze kijken er
        # alleen naar en veranderen niets, en een werkdag naspelen duurt
        # een paar seconden — dat wil je niet elf keer.
        cls.v = PsqlVerbinding()
        cls.v.begin()
        cls.v.stuur(LEEG)
        neem_over(cls.v, rapport, gebruiker="dennis")
        cls.verslag = draai_werkdag(cls.v)
        cls.controle = controleer_einde(cls.v)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "v", None) is not None:
            cls.v.rollback()
            cls.v.sluit()

    def tel(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]

    # -----------------------------------------------------------------
    #  T-18 zelf
    # -----------------------------------------------------------------
    def test_t18_geen_negatieve_voorraadregels(self):
        self.assertEqual(self.controle.negatief, 0)

    def test_t18_nergens_meer_gereserveerd_dan_er_ligt(self):
        self.assertEqual(self.controle.overgereserveerd, 0)

    def test_t18_geen_hangende_reserveringen(self):
        """Een verzonden order die nog voorraad vasthoudt is het ergste
        wat er kan gebeuren: die stuks zijn voor niemand meer te gebruiken
        en niemand merkt het."""
        self.assertEqual(self.controle.hangend, 0)
        self.assertTrue(self.controle.schoon, str(self.controle))

    # -----------------------------------------------------------------
    #  Er moet ook écht een dag gedraaid zijn
    # -----------------------------------------------------------------
    def test_er_is_een_dag_werk_gedaan(self):
        """Zonder dit zou een dag waarin niets gebeurde ook slagen."""
        self.assertGreater(self.verslag.orders, 30)
        self.assertGreater(self.verslag.regels, 50)
        self.assertGreater(self.verslag.stuks, 200)
        self.assertGreater(self.verslag.taken, 20)

    def test_de_dag_loopt_rond(self):
        """Elke order die binnenkwam is ook de deur uit gegaan."""
        self.assertEqual(self.verslag.verzonden, self.verslag.orders)
        self.assertEqual(self.controle.open_orders, 0)

    def test_er_zijn_manco_s_geweest(self):
        """Een dag zonder tegenslag bewijst de helft. R-UIT-05 moet ook
        onder druk kloppen."""
        self.assertGreater(self.verslag.manco, 0)
        self.assertGreater(
            self.tel("SELECT count(*) n FROM journal "
                     "WHERE soort='ADJUST' AND reden='MANCO'"), 0)
        self.assertGreater(
            self.tel("SELECT count(*) n FROM task "
                     "WHERE soort='CYCLE_COUNT' AND aanleiding='manco'"), 0)

    def test_de_hele_stroom_staat_in_het_journaal(self):
        """R-BASIS-01. Elke voorraadwijziging heeft een journaalregel, en
        alle vijf de soorten van een werkdag komen voor."""
        soorten = {r[0] for r in self._rijen(
            "SELECT DISTINCT soort FROM journal")}
        self.assertEqual(soorten, {"IMPORT", "RECEIPT", "PUTAWAY", "PICK",
                                   "ADJUST"})

    def test_elke_pick_hoort_bij_een_order(self):
        self.assertEqual(
            self.tel("SELECT count(*) n FROM journal "
                     "WHERE soort='PICK' AND ref IS NULL"), 0)

    def test_de_voorraad_klopt_met_het_journaal(self):
        """De optelsom van alles wat erin en eruit ging, per artikel en
        locatie, moet precies de voorraad zijn die er nu staat. Loopt dat
        uiteen, dan is er ergens buiten vakto_boek() om geboekt."""
        scheef = self.tel("""
            SELECT count(*) n FROM (
              SELECT s.product_id, s.location_id, s.qty,
                     COALESCE((SELECT sum(j.qty) FROM journal j
                                WHERE j.product_id = s.product_id
                                  AND j.naar = s.location_id), 0)
                   - COALESCE((SELECT sum(j.qty) FROM journal j
                                WHERE j.product_id = s.product_id
                                  AND j.van = s.location_id), 0) AS uit_journaal
                FROM stock s
            ) x WHERE qty <> uit_journaal
        """)
        self.assertEqual(scheef, 0)

    def test_de_zelfcontrole_heeft_gedraaid(self):
        self.assertGreater(
            self.tel("SELECT count(*) n FROM task WHERE status='DONE'"), 20)
        self.assertGreater(
            self.tel("SELECT count(*) n FROM event_log"), 0)

    def test_geen_enkele_order_blijft_halverwege_steken(self):
        """Niets op PICKEN of VRIJGEGEVEN aan het eind van de dag: dan
        staat er werk op de vloer waar niemand meer naar kijkt."""
        blijft = self.tel("""
            SELECT count(*) n FROM customer_order
             WHERE status IN ('VRIJGEGEVEN','PICKEN','GEPICKT','INGEPAKT')
        """)
        self.assertEqual(blijft, 0)

    def _rijen(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


if __name__ == "__main__":
    unittest.main()
