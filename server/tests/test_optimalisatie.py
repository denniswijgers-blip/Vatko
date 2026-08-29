"""Optimalisatie (R-OPT) — hoofdstuk 10.

Alle verwachte uitkomsten zijn afgelezen uit de draaiende browserversie
met demo/test/zelfcontrole-vectoren.mjs, niet bedacht (afspraak 2). De
naam van het scenario in dat bestand staat er telkens bij.

Het magazijn is overal hetzelfde en klein genoeg om in je hoofd te
houden:

    01-01-1  picklocatie  300 x 400 x 220 mm, 12 kg
    02-01-1  bulk        1200 x 800 x 1500 mm, 900 kg
    03-01-1  bulk        1200 x 800 x 1500 mm, 900 kg

Artikel ZC-1 is 120 x 90 x 45 mm en 180 g. Daar passen er dertig van op
de picklocatie — hetzelfde getal als in T-07 en T-27, en dat is geen
toeval: het is steeds dezelfde pas-berekening.
"""

import unittest
from datetime import datetime, timedelta, timezone

from vakto import (Artikel, Artikelgroep, Instellingen, Locatie, Magazijn,
                   Taak, Voorraadregel)
from vakto.optimalisatie import (Pick, aanvultaken, bulkbron, drempeladvies,
                                 pickplekvoorstellen, ruimte_voor,
                                 samenvoegtaken, snelheden, telplan)

NU = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
DAG = timedelta(days=1)

PICK, BULK_A, BULK_B = 1, 2, 3


def magazijn(voorraad=(), min_qty=None, max_qty=None, telinterval=180,
             geteld_dagen_geleden=None, drempel_akkoord=False) -> Magazijn:
    return Magazijn(
        locaties=[
            Locatie(PICK, "01-01-1", 0, 300, 400, 220, 12_000, seq=1_000_110,
                    geteld_op=(None if geteld_dagen_geleden is None
                               else NU - geteld_dagen_geleden * DAG)),
            Locatie(BULK_A, "02-01-1", 1, 1200, 800, 1500, 900_000,
                    seq=2_999_810, geteld_op=NU),
            Locatie(BULK_B, "03-01-1", 1, 1200, 800, 1500, 900_000,
                    seq=3_000_110, geteld_op=NU),
        ],
        artikelen=[Artikel(1, "ZC-1", "Testartikel", group_id=0,
                           l_mm=120, w_mm=90, h_mm=45, g=180,
                           min_qty=min_qty, max_qty=max_qty,
                           drempel_akkoord=drempel_akkoord)],
        voorraad=[Voorraadregel(1, loc, qty) for loc, qty in voorraad],
        groepen={0: Artikelgroep(0, "Testgroep", telinterval)},
    )


# ---------------------------------------------------------------------
#  R-OPT-02  Vraagsnelheid
# ---------------------------------------------------------------------
class TestSnelheid(unittest.TestCase):
    """Uit zelfcontrole-vectoren.mjs, blok "snel"."""

    def test_stuks_per_dag_over_het_venster(self):
        picks = [Pick(1, 30, NU - 1 * DAG),
                 Pick(1, 60, NU - 10 * DAG),
                 Pick(1, 900, NU - 40 * DAG)]      # buiten het venster
        self.assertEqual(snelheden(picks, nu=NU), {1: 3.0})

    def test_zonder_picks_geen_snelheid(self):
        self.assertEqual(snelheden([], nu=NU), {})

    def test_het_venster_staat_in_een_instelling(self):
        """R-BASIS-04. Korter venster reageert sneller op seizoen."""
        picks = [Pick(1, 30, NU - 1 * DAG), Pick(1, 60, NU - 10 * DAG)]
        inst = Instellingen({"opt.venster_dagen": "5"})
        self.assertEqual(snelheden(picks, inst, nu=NU), {1: 6.0})

    def test_stuks_en_niet_aantal_picks(self):
        """Twintig keer één stuk is hetzelfde verbruik als één keer
        twintig. Voor de vraag hoeveel er op de picklocatie moet liggen
        telt alleen hoeveel er weggaat."""
        veel = [Pick(1, 1, NU - 1 * DAG) for _ in range(20)]
        een = [Pick(1, 20, NU - 1 * DAG)]
        self.assertEqual(snelheden(veel, nu=NU), snelheden(een, nu=NU))


# ---------------------------------------------------------------------
#  R-INS-02 als losse vraag: wat past er nog?
# ---------------------------------------------------------------------
class TestRuimteVoor(unittest.TestCase):

    def test_leeg_vak(self):
        self.assertEqual(ruimte_voor(magazijn(), 1, PICK), 30)

    def test_wat_er_al_ligt_gaat_eraf(self):
        self.assertEqual(ruimte_voor(magazijn([(PICK, 5)]), 1, PICK), 25)

    def test_een_vol_vak_geeft_nul_en_niet_negatief(self):
        self.assertEqual(ruimte_voor(magazijn([(PICK, 30)]), 1, PICK), 0)
        self.assertEqual(ruimte_voor(magazijn([(PICK, 40)]), 1, PICK), 0)

    def test_zonder_maat_geen_getal(self):
        mag = magazijn()
        mag.artikelen[0].l_mm = None
        self.assertEqual(ruimte_voor(mag, 1, PICK), 0)


class TestBulkbron(unittest.TestCase):

    def test_de_rij_met_de_meeste_vrije_voorraad(self):
        mag = magazijn([(BULK_A, 100), (BULK_B, 250)])
        self.assertEqual(bulkbron(mag, 1).location_id, BULK_B)

    def test_gereserveerde_voorraad_telt_niet_mee(self):
        """Wat op naam van een order staat mag je niet wegrijden, ook al
        ligt het er nog."""
        mag = magazijn([(BULK_A, 100), (BULK_B, 250)])
        mag.voorraad[1].res = 240
        self.assertEqual(bulkbron(mag, 1).location_id, BULK_A)

    def test_een_picklocatie_is_geen_bulkbron(self):
        self.assertIsNone(bulkbron(magazijn([(PICK, 30)]), 1))


# ---------------------------------------------------------------------
#  R-OPT-03 en R-ZC-04  Aanvullen
# ---------------------------------------------------------------------
class TestAanvullen(unittest.TestCase):
    """Uit zelfcontrole-vectoren.mjs, blokken "drempel" en "samenEen"."""

    def test_drempel(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        nieuw, bij = aanvultaken(mag, [], {}, {})
        self.assertEqual(len(nieuw), 1)
        t = nieuw[0]
        self.assertEqual(
            (t.soort, t.prio, t.van, t.naar, t.qty, t.aanleiding),
            ("REPLENISH", 25, BULK_A, PICK, 25, "drempel"))
        self.assertEqual(t.reden, "Picklocatie 01-01-1 onder drempel (5/20)")

    def test_de_derde_term_is_verplicht(self):
        """max_qty zegt 40 en er liggen er 5, dus 35 zou je denken. Er
        passen er nog maar 25 op dat vak. Een aanvultaak van 35 stuks
        naar een vak waar er 25 in gaan is geen taak maar een probleem
        dat je op de vloer aflevert."""
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        nieuw, _ = aanvultaken(mag, [], {}, {})
        self.assertEqual(nieuw[0].qty, 25)

    def test_zonder_bulkvoorraad_geen_taak(self):
        mag = magazijn([(PICK, 5)], min_qty=20, max_qty=40)
        nieuw, _ = aanvultaken(mag, [], {}, {})
        self.assertEqual(nieuw, [])

    def test_een_vol_picklocatie_vraagt_niets(self):
        mag = magazijn([(PICK, 30), (BULK_A, 500)], min_qty=20, max_qty=40)
        nieuw, _ = aanvultaken(mag, [], {}, {})
        self.assertEqual(nieuw, [])

    def test_twee_aanleidingen_worden_een_taak(self):
        """R-OPT-03. Ordervraag (prio 10) en drempel (prio 25) vragen om
        hetzelfde vak. Dat wordt één loopje, met de zwaarste aanleiding."""
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        nieuw, _ = aanvultaken(mag, [], {1: 28}, {})
        self.assertEqual(len(nieuw), 1)
        t = nieuw[0]
        self.assertEqual((t.prio, t.qty, t.aanleiding), (10, 25, "ordervraag"))
        self.assertEqual(
            t.reden, "28 st gevraagd door openstaande orders, 5 op de picklocatie")

    def test_hardloper_vult_vooruit(self):
        """Zes per dag over drie dagen dekking is achttien; er liggen er
        vijf. Zonder drempel is er geen andere aanleiding."""
        mag = magazijn([(PICK, 5), (BULK_A, 500)])
        nieuw, _ = aanvultaken(mag, [], {}, {1: 6.0})
        self.assertEqual(len(nieuw), 1)
        t = nieuw[0]
        self.assertEqual((t.prio, t.qty, t.aanleiding), (20, 13, "hardloper"))
        self.assertIn("6.0 st per dag", t.reden)

    def test_een_langzaam_artikel_is_geen_hardloper(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)])
        nieuw, _ = aanvultaken(mag, [], {}, {1: 2.0})
        self.assertEqual(nieuw, [])

    def test_een_bestaande_taak_wordt_bijgewerkt_en_niet_verdubbeld(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        staand = Taak(soort="REPLENISH", naam="Picklocatie aanvullen", prio=25,
                      product_id=1, van=BULK_A, naar=PICK, qty=10,
                      aanleiding="drempel")
        staand.id = 7
        nieuw, bij = aanvultaken(mag, [staand], {1: 28}, {})
        self.assertEqual(nieuw, [])
        self.assertEqual(len(bij), 1)
        self.assertEqual((bij[0].qty, bij[0].prio, bij[0].aanleiding),
                         (25, 10, "ordervraag"))

    def test_een_bestaande_taak_die_al_zwaarder_is_blijft_staan(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        staand = Taak(soort="REPLENISH", naam="Picklocatie aanvullen", prio=10,
                      product_id=1, van=BULK_A, naar=PICK, qty=25,
                      aanleiding="ordervraag")
        staand.id = 7
        nieuw, bij = aanvultaken(mag, [staand], {}, {})
        self.assertEqual((nieuw, bij), ([], []))


# ---------------------------------------------------------------------
#  R-OPT-01  Samenvoegen
# ---------------------------------------------------------------------
class TestSamenvoegen(unittest.TestCase):
    """Uit zelfcontrole-vectoren.mjs, blokken "samenvoegen"."""

    def test_alles_naar_de_picklocatie(self):
        mag = magazijn([(PICK, 12), (BULK_A, 8)])
        taken = samenvoegtaken(mag, [])
        self.assertEqual(len(taken), 1)
        t = taken[0]
        self.assertEqual((t.soort, t.prio, t.van, t.naar, t.qty),
                         ("SAMENVOEG", 35, BULK_A, PICK, 8))
        self.assertEqual(
            t.reden, "02-01-1 komt helemaal vrij; alle 20 st passen op 01-01-1")

    def test_nooit_een_picklocatie_leeghalen_naar_bulk(self):
        """Vijfenzestig stuks passen niet op de picklocatie, dus het
        bulkvak zou het doel worden. Dan staat de picker morgen voor een
        leeg vak — en heeft de optimalisatie het magazijn slechter
        gemaakt in plaats van beter. Deze regel is niet onderhandelbaar."""
        self.assertEqual(samenvoegtaken(magazijn([(PICK, 25), (BULK_A, 40)]), []), [])

    def test_gereserveerde_voorraad_blijft_liggen(self):
        mag = magazijn([(PICK, 12), (BULK_A, 8)])
        mag.voorraad[1].res = 1
        self.assertEqual(samenvoegtaken(mag, []), [])

    def test_een_artikel_op_een_plek_hoeft_niets(self):
        self.assertEqual(samenvoegtaken(magazijn([(PICK, 12)]), []), [])

    def test_niet_als_er_al_een_samenvoegtaak_ligt(self):
        mag = magazijn([(PICK, 12), (BULK_A, 8)])
        staand = Taak(soort="SAMENVOEG", naam="Voorraad samenvoegen",
                      product_id=1, qty=8, van=BULK_A, naar=PICK)
        self.assertEqual(samenvoegtaken(mag, [staand]), [])

    def test_uit_te_zetten_met_een_instelling(self):
        mag = magazijn([(PICK, 12), (BULK_A, 8)])
        inst = Instellingen({"opt.samenvoegen": "false"})
        self.assertEqual(samenvoegtaken(mag, [], inst), [])


# ---------------------------------------------------------------------
#  R-OPT-04  Telplan
# ---------------------------------------------------------------------
class TestTelplan(unittest.TestCase):
    """Uit zelfcontrole-vectoren.mjs, blok "telplan"."""

    def test_over_het_telinterval(self):
        mag = magazijn([(PICK, 10)], telinterval=30, geteld_dagen_geleden=100)
        taken = telplan(mag, [], nu=NU)
        self.assertEqual(len(taken), 1)
        t = taken[0]
        self.assertEqual((t.soort, t.prio, t.van, t.naar, t.qty, t.aanleiding),
                         ("CYCLE_COUNT", 45, PICK, PICK, 10, "telinterval"))
        self.assertEqual(t.reden,
                         "70 dag(en) over het telinterval van 30 dagen")

    def test_op_tijd_geteld_is_geen_taak(self):
        mag = magazijn([(PICK, 10)], telinterval=30, geteld_dagen_geleden=10)
        self.assertEqual(telplan(mag, [], nu=NU), [])

    def test_nooit_geteld_staat_vooraan(self):
        mag = magazijn([(PICK, 10)], telinterval=30, geteld_dagen_geleden=None)
        taken = telplan(mag, [], nu=NU)
        self.assertEqual(len(taken), 1)
        # R-OPT-04. Rekenkundig is dit "20508 dag(en) over het
        # telinterval" — geteld_op is dan 1970 — maar dat is onzin om te
        # lezen, en bij een nieuwe klant staat het op elke taak.
        self.assertEqual(taken[0].reden, "nog nooit geteld")

    def test_de_relatieve_overschrijding_bepaalt_de_volgorde(self):
        """Honderd dagen over een interval van dertig is erger dan
        honderd dagen over een interval van driehonderd. Sorteer je op
        absolute dagen, dan komt een langzame groep nooit aan bod."""
        mag = magazijn([(PICK, 10), (BULK_A, 10)], telinterval=30,
                       geteld_dagen_geleden=100)
        # de bulklocatie is 400 dagen geleden geteld: absoluut verder over
        # tijd, relatief minder ver dan het picklocatievak
        mag.locaties[1].geteld_op = NU - 200 * DAG
        mag.artikelen.append(Artikel(2, "ZC-2", group_id=1, l_mm=120, w_mm=90,
                                     h_mm=45, g=180))
        mag.groepen[1] = Artikelgroep(1, "Trage groep", 300)
        mag.voorraad[1] = Voorraadregel(2, BULK_A, 10)
        volgorde = [t.van for t in telplan(mag, [], nu=NU)]
        self.assertEqual(volgorde[0], PICK)

    def test_het_plafond_wordt_gerespecteerd(self):
        mag = magazijn([(PICK, 10)], telinterval=30, geteld_dagen_geleden=100)
        inst = Instellingen({"opt.max_open_teltaken": "0"})
        self.assertEqual(telplan(mag, [], inst, nu=NU), [])

    def test_een_teltaak_uit_een_manco_vult_het_plafond_niet(self):
        """R-UIT-05 maakt ook teltaken. Die zijn urgent en hebben een
        andere aanleiding; ze horen het telplan niet te verdringen."""
        mag = magazijn([(PICK, 10)], telinterval=30, geteld_dagen_geleden=100)
        manco = Taak(soort="CYCLE_COUNT", naam="Tellen na manco",
                     product_id=1, qty=3, van=BULK_A, naar=BULK_A,
                     aanleiding="manco")
        inst = Instellingen({"opt.max_open_teltaken": "1"})
        self.assertEqual(len(telplan(mag, [manco], inst, nu=NU)), 1)

    def test_niet_twee_keer_hetzelfde_vak(self):
        mag = magazijn([(PICK, 10)], telinterval=30, geteld_dagen_geleden=100)
        staand = Taak(soort="CYCLE_COUNT", naam="Locatie tellen", product_id=1,
                      qty=10, van=PICK, naar=PICK, aanleiding="telinterval")
        self.assertEqual(telplan(mag, [staand], nu=NU), [])


# ---------------------------------------------------------------------
#  R-OPT-05  Drempeladvies — een advies, geen taak
# ---------------------------------------------------------------------
class TestDrempeladvies(unittest.TestCase):
    """Uit zelfcontrole-vectoren.mjs, blok "advies"."""

    def test_de_drempel_staat_veel_te_laag(self):
        mag = magazijn([(PICK, 10)], min_qty=4, max_qty=8)
        adviezen = drempeladvies(mag, {1: 10.0})
        self.assertEqual(len(adviezen), 1)
        a = adviezen[0]
        self.assertEqual((a.per_dag, a.nu, a.zou, a.max_nu, a.max_zou),
                         (10.0, 4, 30, 8, 90))
        self.assertEqual(a.richting, "omhoog")

    def test_een_kloppende_drempel_geeft_geen_advies(self):
        mag = magazijn([(PICK, 10)], min_qty=30)
        self.assertEqual(drempeladvies(mag, {1: 10.0}), [])

    def test_te_traag_om_iets_over_te_zeggen(self):
        mag = magazijn([(PICK, 10)], min_qty=4)
        self.assertEqual(drempeladvies(mag, {1: 0.4}), [])

    def test_zonder_drempel_geen_advies(self):
        mag = magazijn([(PICK, 10)])
        self.assertEqual(drempeladvies(mag, {1: 10.0}), [])

    def test_akkoord_is_akkoord(self):
        """Een van de twee dingen die een mens beslist. Heeft hij gezegd
        dat de drempel klopt, dan houdt het systeem zijn mond."""
        mag = magazijn([(PICK, 10)], min_qty=4, drempel_akkoord=True)
        self.assertEqual(drempeladvies(mag, {1: 10.0}), [])


# ---------------------------------------------------------------------
#  R-OPT-06  Hardloper zonder picklocatie
# ---------------------------------------------------------------------
class TestPickplek(unittest.TestCase):

    def test_alleen_in_bulk_terwijl_het_hard_loopt(self):
        mag = magazijn([(BULK_A, 500)])
        voorstellen = pickplekvoorstellen(mag, [], {1: 12.0})
        self.assertEqual(len(voorstellen), 1)
        v = voorstellen[0]
        self.assertEqual((v.van, v.naar), (BULK_A, PICK))
        # ceil(12 x 3 dagen dekking) is 36, maar er passen er 30 op dat
        # vak. Ook een voorstel wordt nooit groter dan wat er past.
        self.assertEqual(v.qty, 30)

    def test_met_een_picklocatie_hoeft_er_niets(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)])
        self.assertEqual(pickplekvoorstellen(mag, [], {1: 12.0}), [])

    def test_een_langzaam_artikel_hoeft_geen_picklocatie(self):
        mag = magazijn([(BULK_A, 500)])
        self.assertEqual(pickplekvoorstellen(mag, [], {1: 2.0}), [])

    def test_niet_als_er_al_een_voorstel_ligt(self):
        mag = magazijn([(BULK_A, 500)])
        staand = Taak(soort="PICKPLEK", naam="Picklocatie inrichten",
                      product_id=1, qty=36, van=BULK_A, naar=PICK)
        self.assertEqual(pickplekvoorstellen(mag, [staand], {1: 12.0}), [])


if __name__ == "__main__":
    unittest.main()
