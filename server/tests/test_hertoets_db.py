"""T-16 en T-17 van begin tot eind, tegen een echte PostgreSQL.

De andere testbestanden knippen de keten in tweeën: `test_zelfcontrole.py`
bewijst dat de zelfcontrole het juiste bedenkt, `tests-sql/test_zelfcontrole.sql`
bewijst dat de database het juiste opschrijft. Wat geen van beide bewijst
is dat die twee helften ook aan elkaar geknoopt zijn.

Dat doet dit bestand, met de twee testgevallen waar stap 6 op afgerekend
wordt:

  T-16  Voer een OVERLOOP-taak uit → de bijbehorende melding gaat vanzelf
        naar OPGELOST, met een regel in het log.
  T-17  Vul een picklocatie handmatig bij tot boven de drempel → de
        aanvultaak krijgt status VERVALLEN met reden "picklocatie is weer
        op peil".

Draait alleen als er een PostgreSQL bereikbaar is; zo niet, dan wordt hij
overgeslagen in plaats van rood. Alles gebeurt in één transactie die aan
het eind wordt teruggedraaid — de database is daarna weer zoals hij was.
"""

import unittest
from datetime import datetime, timedelta, timezone

from vakto import Instellingen, draai_zelfcontrole, voer_taak_uit, tel_locatie
from vakto.opslag import boek, laad_magazijn, laad_taken, open_meldingen

from .psqlschil import PsqlVerbinding, psql_beschikbaar

PICK, BULK_A, BULK_B = 930, 931, 932
ARTIKEL = 930

# Eerst schoonvegen. Niet uit netheid: de gelijktijdigheidstests laten
# locaties achter die ze niet kunnen opruimen — het journaal is
# append-only en houdt ze vast (R-BASIS-01). Deze test kijkt naar het
# hele magazijn, dus die zouden meetellen in een inslagvoorstel.
# TRUNCATE mag hier omdat alles aan het eind wordt teruggedraaid.
OPZET = """
TRUNCATE journal, stock, measurement, allocation, order_line, customer_order,
         task, alert, event_log, product, product_group, location, zone CASCADE;
INSERT INTO zone (id, code, naam) VALUES (930,'TST','Testzone hertoets');
INSERT INTO location (id, code, zone_id, type_id, aisle, bay, level, seq,
                      l_mm, w_mm, h_mm, max_g, geteld_op) VALUES
  (930,'H-01-1',930,0,1,1,1,1000110, 300, 400, 220,  12000, now()),
  (931,'H-02-1',930,1,2,1,1,2999810,1200, 800,1500, 900000, now()),
  (932,'H-03-1',930,1,3,1,1,3000110,1200, 800,1500, 900000, now());
INSERT INTO product_group (id, naam, telinterval) VALUES (930,'Testgroep H',180);
INSERT INTO product (id, sku, oms, group_id, min_qty, max_qty) VALUES
  (930,'HT-1','Testartikel hertoets',930,20,40);
INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g, at) VALUES
  (930,'RECEIPT',120,90,45,180, now() - interval '40 days');
"""


class TestKetenTegenDeDatabase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest(
                "Geen bereikbare PostgreSQL. Zet hem op met opzetten.sh, of "
                "sla deze tests over — de rest draait gewoon.")

    def setUp(self):
        self.v = PsqlVerbinding()
        self.v.begin()
        self.v.stuur(OPZET)
        self.inst = Instellingen()

    def tearDown(self):
        self.v.rollback()
        self.v.sluit()

    def taken(self, soort=None) -> list:
        return [t for t in laad_taken(self.v)
                if soort is None or t.soort == soort]

    def logregels(self, bron=None) -> list[str]:
        with self.v.cursor() as cur:
            cur.execute("SELECT bericht FROM event_log"
                        + (f" WHERE bron = '{bron}'" if bron else "")
                        + " ORDER BY id")
            return [r[0] for r in cur.fetchall()]

    def alle_taken(self) -> list[tuple]:
        with self.v.cursor() as cur:
            cur.execute("SELECT soort, status, vervallen_reden, qty "
                        "FROM task WHERE product_id = 930 ORDER BY id")
            return cur.fetchall()

    # -----------------------------------------------------------------
    #  T-17
    # -----------------------------------------------------------------
    def test_t17_handmatig_bijvullen_laat_de_aanvultaak_vervallen(self):
        boek(self.v, ARTIKEL, 5, "RECEIPT", naar=PICK)
        boek(self.v, ARTIKEL, 500, "RECEIPT", naar=BULK_A)

        # 1. De zelfcontrole ziet dat de picklocatie onder de drempel zit.
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        aanvul = [t for t in uit.nieuwe_taken if t.soort == "REPLENISH"]
        self.assertEqual(len(aanvul), 1)
        self.assertEqual(aanvul[0].qty, 25)          # niet 35: meer past er niet
        self.assertEqual(aanvul[0].aanleiding, "drempel")
        self.assertIsNotNone(aanvul[0].id)           # echt weggeschreven
        self.assertEqual(len(self.taken("REPLENISH")), 1)

        # 2. Iemand vult het vak met de hand bij, buiten de taak om.
        boek(self.v, ARTIKEL, 20, "MOVE", van=BULK_A, naar=PICK)

        # 3. De volgende ronde trekt de taak in.
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual(len(uit.vervallen), 1)
        self.assertEqual(uit.vervallen[0].reden, "picklocatie is weer op peil")

        soort, status, reden, _ = self.alle_taken()[0]
        self.assertEqual((soort, status, reden),
                         ("REPLENISH", "VERVALLEN", "picklocatie is weer op peil"))
        self.assertIn("HT-1: taak vervallen — picklocatie is weer op peil",
                      self.logregels())
        self.assertEqual(self.taken("REPLENISH"), [])

    def test_t17_de_taak_blijft_staan_zolang_het_vak_leeg_blijft(self):
        boek(self.v, ARTIKEL, 5, "RECEIPT", naar=PICK)
        boek(self.v, ARTIKEL, 500, "RECEIPT", naar=BULK_A)
        draai_zelfcontrole(self.v, inst=self.inst)

        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual(uit.vervallen, [])
        self.assertEqual(len(self.taken("REPLENISH")), 1)

    def test_de_aanvultaak_uitvoeren_lost_hem_ook_op(self):
        """De andere weg naar hetzelfde punt: de picker doet gewoon zijn
        werk. Dan is de taak DONE en niet VERVALLEN."""
        boek(self.v, ARTIKEL, 5, "RECEIPT", naar=PICK)
        boek(self.v, ARTIKEL, 500, "RECEIPT", naar=BULK_A)
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        taak = uit.nieuwe_taken[0]

        journaal = voer_taak_uit(self.v, taak.id, gebruiker="dennis")
        self.assertIsNotNone(journaal)

        mag = laad_magazijn(self.v)
        rij = next(s for s in mag.voorraad if s.location_id == PICK)
        self.assertEqual(rij.qty, 30)
        self.assertEqual(self.alle_taken()[0][1], "DONE")

        # En de ronde daarna is er niets meer te doen voor dit artikel.
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual([t for t in uit.nieuwe_taken
                          if t.soort == "REPLENISH"], [])

    # -----------------------------------------------------------------
    #  T-16
    # -----------------------------------------------------------------
    def _meet_groter(self) -> None:
        """Het artikel blijkt 140 x 100 x 50 mm en 210 g: er passen er nog
        27 op de picklocatie in plaats van 30 (hetzelfde geval als T-27)."""
        self.v.stuur(
            "INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g) "
            "VALUES (930,'RECEIPT',140,100,50,210);")
        self.v.stuur(
            "INSERT INTO alert (product_id, d_vol, d_gew, gevolg) "
            "VALUES (930, 44.0, 16.7, "
            "'Past niet meer op: H-01-1 (ligt 30, past nog 27)');")

    def test_t16_de_melding_sluit_zichzelf_na_de_overlooptaak(self):
        boek(self.v, ARTIKEL, 30, "RECEIPT", naar=PICK)
        boek(self.v, ARTIKEL, 100, "RECEIPT", naar=BULK_A)
        self._meet_groter()

        # 1. De melding klopt nog, en het systeem zet het werk klaar.
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual(uit.gesloten, [])
        overloop = [t for t in uit.nieuwe_taken if t.soort == "OVERLOOP"]
        self.assertEqual(len(overloop), 1)
        self.assertEqual((overloop[0].van, overloop[0].naar, overloop[0].qty),
                         (PICK, BULK_A, 3))
        self.assertEqual(overloop[0].reden,
                         "H-01-1 zit 3 st over de nieuwe maat")
        self.assertEqual(open_meldingen(self.v)[0].gevolg,
                         "Past niet meer op: H-01-1 (ligt 30, past nog 27)")

        # 2. De taak wordt uitgevoerd.
        voer_taak_uit(self.v, overloop[0].id, gebruiker="dennis")
        mag = laad_magazijn(self.v)
        self.assertEqual(
            next(s for s in mag.voorraad if s.location_id == PICK).qty, 27)

        # 3. T-16: de melding gaat vanzelf dicht, met een regel in het log.
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual(len(uit.gesloten), 1)
        self.assertEqual(open_meldingen(self.v), [])
        self.assertIn(
            "HT-1: afwijking vanzelf gesloten, de voorraad past weer",
            self.logregels("zelfcontrole"))

        with self.v.cursor() as cur:
            cur.execute("SELECT status, opgelost_op FROM alert "
                        "WHERE product_id = 930")
            status, opgelost_op = cur.fetchone()
        self.assertEqual(status, "OPGELOST")
        self.assertIsNotNone(opgelost_op)

    def test_t16_zonder_plek_komt_er_geen_taak_en_blijft_de_melding_open(self):
        """Niets gevonden om het teveel heen te brengen is geen taak. Dat
        vraagt een menselijke keuze, en dat zeg je er ook bij."""
        self.v.stuur("UPDATE location SET actief = false WHERE id IN (931,932);")
        boek(self.v, ARTIKEL, 30, "RECEIPT", naar=PICK)
        self._meet_groter()

        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual([t for t in uit.nieuwe_taken
                          if t.soort == "OVERLOOP"], [])
        self.assertEqual(open_meldingen(self.v)[0].status, "OPEN")

    def test_de_melding_sluit_ook_als_de_voorraad_op_een_andere_manier_weggaat(self):
        """R-BASIS-03: een melding is een uitspraak over de huidige
        toestand. Verdwijnt de aanleiding, dan gaat hij dicht — hoe die
        aanleiding ook verdwenen is."""
        boek(self.v, ARTIKEL, 30, "RECEIPT", naar=PICK)
        self._meet_groter()
        draai_zelfcontrole(self.v, inst=self.inst)

        boek(self.v, ARTIKEL, 10, "PICK", van=PICK, ref="ORD-1")
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual(len(uit.gesloten), 1)
        self.assertEqual(open_meldingen(self.v), [])

    # -----------------------------------------------------------------
    #  De ronde als geheel
    # -----------------------------------------------------------------
    def test_twee_rondes_achter_elkaar_maken_niets_dubbel(self):
        """Alles is een gevolgtrekking uit de huidige toestand, dus de
        zelfcontrole mag zo vaak draaien als je wilt."""
        boek(self.v, ARTIKEL, 5, "RECEIPT", naar=PICK)
        boek(self.v, ARTIKEL, 500, "RECEIPT", naar=BULK_A)

        draai_zelfcontrole(self.v, inst=self.inst)
        na_een = self.alle_taken()
        draai_zelfcontrole(self.v, inst=self.inst)
        draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual(self.alle_taken(), na_een)

    def test_het_telplan_pakt_een_locatie_die_te_lang_niet_geteld_is(self):
        """R-OPT-04, door de hele keten: van de view tot de teltaak en
        weer terug als hij geteld is."""
        boek(self.v, ARTIKEL, 10, "RECEIPT", naar=BULK_B)
        self.v.stuur("UPDATE location SET geteld_op = now() - interval '400 days' "
                     "WHERE id = 932;")

        uit = draai_zelfcontrole(self.v, inst=self.inst)
        tel = [t for t in uit.nieuwe_taken if t.soort == "CYCLE_COUNT"]
        self.assertEqual(len(tel), 1)
        self.assertEqual(tel[0].aanleiding, "telinterval")
        self.assertEqual(tel[0].naar, BULK_B)
        self.assertIn("dag(en) over het telinterval van 180 dagen", tel[0].reden)

        # Tellen zet het stempel, en dan is de taak klaar.
        tel_locatie(self.v, BULK_B, ARTIKEL, 9, gebruiker="dennis")
        self.assertEqual([t for t in self.taken("CYCLE_COUNT")], [])

        mag = laad_magazijn(self.v)
        self.assertEqual(
            next(s for s in mag.voorraad if s.location_id == BULK_B).qty, 9)

        # En de volgende ronde vraagt er niet opnieuw om.
        uit = draai_zelfcontrole(self.v, inst=self.inst)
        self.assertEqual([t for t in uit.nieuwe_taken
                          if t.soort == "CYCLE_COUNT"], [])


if __name__ == "__main__":
    unittest.main()
