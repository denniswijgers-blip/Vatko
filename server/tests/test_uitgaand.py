"""Uitgaand (R-UIT) — het deel dat in Python staat.

Het zwaartepunt van hoofdstuk 8 zit in uitgaand.sql en wordt daar
getest: tests-sql/test_uitgaand.sql doet T-14 en T-15 tegen een echte
PostgreSQL, want reserveren en picken vergrendelen rijen en boeken
voorraad. Wat hier staat is de rest — de looproute, de statusreeks, het
inpakken en de vertaallaag.

Alle verwachte uitkomsten zijn afgelezen uit de draaiende browserversie
met demo/test/uitgaand-vectoren.mjs, niet bedacht (afspraak 2). De naam
van het scenario in dat bestand staat er telkens bij. Loopt een van deze
tests rood, dan zeggen de twee versies iets anders over dezelfde order.
"""

import unittest

from vakto import Artikel, Instellingen
from vakto.opslag import (QUERIES, bevestig_pick, geef_vrij, orderregels,
                          picklijst, reserveer, verzend)
from vakto.uitgaand import (ORDERSTATUS, OVERGANGEN, STATUSNAAM, Order,
                            Orderregel, Pickregel, inpakgegevens,
                            looproute_seq, mag_naar, open_status,
                            teltaak_reden, vak_positie)


ARTIKEL = Artikel(1, "UIT-1", "Testartikel", l_mm=120, w_mm=90, h_mm=45, g=180)
ZONDER_MAAT = Artikel(2, "UIT-2", "Nooit opgemeten")


class TestLooproute(unittest.TestCase):
    """R-UIT-03. Uit uitgaand-vectoren.mjs, blok "looproute"."""

    def test_oneven_gang_telt_op(self):
        self.assertEqual(looproute_seq(1, 1, 1), 1_000_110)
        self.assertEqual(looproute_seq(1, 2, 1), 1_000_210)
        self.assertEqual(looproute_seq(1, 1, 2), 1_000_120)
        self.assertEqual(looproute_seq(3, 4, 3), 3_000_430)

    def test_even_gang_loopt_terug(self):
        """De slangroute: in gang 2 telt het vak van hoog naar laag."""
        self.assertEqual(looproute_seq(2, 1, 1), 2_999_810)
        self.assertEqual(looproute_seq(2, 2, 1), 2_999_710)
        self.assertEqual(looproute_seq(4, 4, 3), 4_999_530)

    def test_vak_positie(self):
        self.assertEqual(vak_positie(1, 3), 3)
        self.assertEqual(vak_positie(2, 3), 9996)

    def test_de_picker_loopt_de_gang_een_keer_door(self):
        """Dit is waar de formule voor bedoeld is.

        Vier vakken in twee gangen, op volgorde van seq: eerst gang 1
        oplopend, dan gang 2 aflopend. Zou je vak_positie weglaten, dan
        loopt de picker aan het eind van gang 1 helemaal terug naar het
        begin van gang 2.
        """
        vakken = [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2), (2, 3)]
        op_route = sorted(vakken, key=lambda gv: looproute_seq(gv[0], gv[1], 1))
        self.assertEqual(op_route,
                         [(1, 1), (1, 2), (1, 3), (2, 3), (2, 2), (2, 1)])


class TestStatusreeks(unittest.TestCase):
    """R-UIT-06. Een toestandsmachine, geen vrij tekstveld."""

    def test_de_gewone_weg(self):
        weg = ["NIEUW", "GERESERVEERD", "VRIJGEGEVEN", "PICKEN", "GEPICKT",
               "INGEPAKT", "VERZONDEN"]
        for van, naar in zip(weg, weg[1:]):
            self.assertTrue(mag_naar(van, naar), f"{van} → {naar} hoort te mogen")

    def test_tekort_en_terug(self):
        self.assertTrue(mag_naar("NIEUW", "WACHT_OP_VOORRAAD"))
        self.assertTrue(mag_naar("WACHT_OP_VOORRAAD", "GERESERVEERD"))
        # Opnieuw proberen mag; het blijft dan gewoon staan.
        self.assertTrue(mag_naar("WACHT_OP_VOORRAAD", "WACHT_OP_VOORRAAD"))

    def test_wat_niet_mag(self):
        self.assertFalse(mag_naar("NIEUW", "VERZONDEN"))
        self.assertFalse(mag_naar("GEPICKT", "GERESERVEERD"))
        self.assertFalse(mag_naar("VERZONDEN", "PICKEN"))
        # Een order die al gepickt is, geef je niet nog een keer vrij.
        self.assertFalse(mag_naar("GEPICKT", "VRIJGEGEVEN"))

    def test_een_verzonden_order_is_klaar(self):
        self.assertEqual(OVERGANGEN["VERZONDEN"], ())
        self.assertFalse(open_status("VERZONDEN"))
        self.assertTrue(open_status("WACHT_OP_VOORRAAD"))

    def test_onbekende_status_is_een_fout_en_geen_false(self):
        """Een tikfout hoort te knallen, niet stilletjes 'nee' te zeggen."""
        with self.assertRaises(KeyError):
            mag_naar("GERESERVEEERD", "VRIJGEGEVEN")
        with self.assertRaises(KeyError):
            mag_naar("NIEUW", "ONDERWEG")

    def test_elke_status_heeft_een_naam_en_een_regel(self):
        for s in ORDERSTATUS:
            self.assertIn(s, STATUSNAAM)
            self.assertIn(s, OVERGANGEN)
        for van, naartoe in OVERGANGEN.items():
            for naar in naartoe:
                self.assertIn(naar, ORDERSTATUS, f"{van} verwijst naar {naar}")


class TestInpakken(unittest.TestCase):
    """R-UIT-07. Uit uitgaand-vectoren.mjs, blok "inpakken"."""

    def setUp(self):
        self.artikelen = {1: ARTIKEL, 2: ZONDER_MAAT}

    def test_een_collo(self):
        uit = inpakgegevens({1: 24}, self.artikelen)
        self.assertEqual((uit.colli, uit.gewicht_g), (1, 4320))

    def test_precies_op_de_grens(self):
        """138 x 180 g = 24.840 g. Net onder de 25 kg, dus één doos."""
        uit = inpakgegevens({1: 138}, self.artikelen)
        self.assertEqual((uit.colli, uit.gewicht_g), (1, 24_840))

    def test_net_erover(self):
        uit = inpakgegevens({1: 139}, self.artikelen)
        self.assertEqual((uit.colli, uit.gewicht_g), (2, 25_020))

    def test_niets_gepickt_is_nog_altijd_een_doos(self):
        """Een order met alleen manco gaat wel de deur uit — leeg, met
        een pakbon erin. Nul colli bestaat niet."""
        uit = inpakgegevens({1: 0}, self.artikelen)
        self.assertEqual((uit.colli, uit.gewicht_g), (1, 0))

    def test_artikel_zonder_maat_telt_niet_mee(self):
        """Liever onderschatten dan een verzonnen getal op de vrachtbrief
        (dezelfde keuze als R-AFG-04)."""
        uit = inpakgegevens({1: 24, 2: 100}, self.artikelen)
        self.assertEqual(uit.gewicht_g, 4320)

    def test_onbekend_artikel_laat_de_som_niet_omvallen(self):
        uit = inpakgegevens({1: 24, 99: 5}, self.artikelen)
        self.assertEqual(uit.gewicht_g, 4320)

    def test_de_grens_staat_in_een_instelling(self):
        """R-BASIS-04. Rijdt de klant zelf, dan mag er meer in een doos."""
        inst = Instellingen({"uit.max_colli_gewicht_g": "50000"})
        uit = inpakgegevens({1: 139}, self.artikelen, inst)
        self.assertEqual(uit.colli, 1)

    def test_een_grens_van_nul_is_een_fout(self):
        inst = Instellingen({"uit.max_colli_gewicht_g": "0"})
        with self.assertRaises(ValueError):
            inpakgegevens({1: 1}, self.artikelen, inst)


class TestTeltaakTekst(unittest.TestCase):
    """R-UIT-05, punt 3. Uit uitgaand-vectoren.mjs, blok "picken"."""

    def test_de_zin_is_woord_voor_woord_die_van_de_browserversie(self):
        self.assertEqual(
            teltaak_reden("ORD-910", 11, 20, "U-02-1"),
            "Manco bij ORD-910: 11 van 20 niet gevonden op U-02-1")


class TestOrderObjecten(unittest.TestCase):
    """De platte gegevens waar de schermen mee werken."""

    def test_open_is_wat_er_nog_gereserveerd_moet_worden(self):
        r = Orderregel(0, 1, besteld=35, gereserveerd=15)
        self.assertEqual(r.open, 20)

    def test_open_wordt_nooit_negatief(self):
        r = Orderregel(0, 1, besteld=5, gereserveerd=8)
        self.assertEqual(r.open, 0)

    def test_order_telt_zijn_regels_op(self):
        """De uitkomst van T-15: besteld 35 = 24 gepickt + 11 manco."""
        o = Order(1, "ORD-910", "Testklant", status="GEPICKT", regels=[
            Orderregel(0, 1, besteld=35, gereserveerd=35, gepickt=24, manco=11)])
        self.assertTrue(o.compleet_gereserveerd)
        self.assertEqual(o.manco, 11)
        self.assertEqual(o.statusnaam, "Gepickt")

    def test_een_order_met_een_tekort_is_niet_compleet(self):
        o = Order(2, "ORD-911", "Testklant", status="WACHT_OP_VOORRAAD", regels=[
            Orderregel(0, 1, besteld=40, gereserveerd=15)])
        self.assertFalse(o.compleet_gereserveerd)
        self.assertEqual(o.statusnaam, "Wacht op voorraad")

    def test_pickregel_weet_wat_er_nog_moet(self):
        r = Pickregel(allocation_id=1, order_id=1, ordernummer="ORD-910", regel=0,
                      product_id=1, sku="UIT-1", oms="", location_id=2,
                      locatie="U-02-1", seq=2_999_810, qty=20, gepickt=9)
        self.assertEqual(r.nog_te_picken, 11)


# ---------------------------------------------------------------------
#  De vertaallaag, met een nep-verbinding
#
#  Wat hier bewezen wordt: opslag.py stuurt de juiste parameters naar de
#  juiste functie en vertaalt het antwoord terug. Of die functies zelf
#  kloppen, staat in tests-sql/test_uitgaand.sql — daar is een echte
#  database voor nodig en dat hoort ook zo.
# ---------------------------------------------------------------------
class NepCursor:
    def __init__(self, antwoorden, log):
        self._antwoorden, self._log, self._rijen = antwoorden, log, []

    def __enter__(self):  return self
    def __exit__(self, *a): return False

    def execute(self, sql, params=()):
        naam = next(k for k, v in QUERIES.items() if v.strip() == sql.strip())
        self._log.append((naam, params))
        rijen = self._antwoorden.get(naam, [])
        self._rijen = rijen(params) if callable(rijen) else rijen

    def fetchall(self): return self._rijen
    def fetchone(self):  return self._rijen[0] if self._rijen else None


class NepVerbinding:
    def __init__(self, antwoorden):
        self.antwoorden, self.log = antwoorden, []

    def cursor(self): return NepCursor(self.antwoorden, self.log)

    def aanroep(self, naam):
        """De parameters waarmee `naam` is aangeroepen."""
        return next(p for n, p in self.log if n == naam)


class TestVertaallaag(unittest.TestCase):

    def test_reserveren_geeft_de_status_terug(self):
        v = NepVerbinding({"reserveer": [("WACHT_OP_VOORRAAD",)]})
        self.assertEqual(reserveer(v, 910, "dennis"), "WACHT_OP_VOORRAAD")
        self.assertEqual(v.aanroep("reserveer"), (910, "dennis"))

    def test_vrijgeven_geeft_het_aantal_pickregels(self):
        v = NepVerbinding({"geef_vrij": [(3,)]})
        self.assertEqual(geef_vrij(v, 910), 3)

    def test_een_volledige_pick_stuurt_geen_teltaak_mee(self):
        """Geen manco, dus geen teltaak. Anders zou er bij elke pick een
        telopdracht klaarstaan en telt niemand er meer één."""
        v = NepVerbinding({
            "pickregel": [(1, 910, "ORD-910", 0, 1, "UIT-1", 2, "U-02-1", 20, 0, "TODO")],
            "pick": [("DONE",)],
        })
        self.assertEqual(bevestig_pick(v, 1, 20), "DONE")
        self.assertEqual(v.aanroep("pick"), (1, 20, None, None))

    def test_bij_een_manco_gaat_de_teltaaktekst_mee(self):
        """T-15 (3), woord voor woord zoals de browserversie hem schrijft."""
        v = NepVerbinding({
            "pickregel": [(1, 910, "ORD-910", 0, 1, "UIT-1", 2, "U-02-1", 20, 0, "TODO")],
            "pick": [("MANCO",)],
        })
        self.assertEqual(bevestig_pick(v, 1, 9), "MANCO")
        self.assertEqual(
            v.aanroep("pick"),
            (1, 9, None, "Manco bij ORD-910: 11 van 20 niet gevonden op U-02-1"))

    def test_een_deels_gepickte_regel_rekent_over_wat_er_nog_open_staat(self):
        """Er is al 9 van de 20 gepickt; nu komt er 0 bij. Het tekort is
        dan 11 en niet 20."""
        v = NepVerbinding({
            "pickregel": [(1, 910, "ORD-910", 0, 1, "UIT-1", 2, "U-02-1", 20, 9, "TODO")],
            "pick": [("MANCO",)],
        })
        bevestig_pick(v, 1, 0)
        self.assertIn("11 van 20", v.aanroep("pick")[3])

    def test_verzenden_geeft_waar_of_onwaar(self):
        v = NepVerbinding({"verzend": [(False,)]})
        self.assertFalse(verzend(v, 910, "3S123456NL"))
        self.assertEqual(v.aanroep("verzend"), (910, "3S123456NL"))

    def test_picklijst_wordt_omgezet_naar_pickregels(self):
        v = NepVerbinding({"picklijst": [
            (1, 910, "ORD-910", 3, 0, 1, "UIT-1", "Testartikel", 2, "U-02-1",
             1, 2_999_810, 20, 9)]})
        regels = picklijst(v)
        self.assertEqual(len(regels), 1)
        self.assertEqual(regels[0].locatie, "U-02-1")
        self.assertEqual(regels[0].nog_te_picken, 11)

    def test_de_picklijst_heeft_altijd_een_limiet(self):
        """R-BASIS-07. Nooit een scherm zonder limiet."""
        v = NepVerbinding({"picklijst": []})
        picklijst(v)
        self.assertEqual(v.aanroep("picklijst"), (200,))
        v = NepVerbinding({"picklijst_order": []})
        picklijst(v, order_id=910, limiet=50)
        self.assertEqual(v.aanroep("picklijst_order"), (910, 50))

    def test_orderregels_worden_objecten(self):
        v = NepVerbinding({"orderregels": [(0, 1, 35, 35, 24, 11)]})
        regels = orderregels(v, 910)
        self.assertEqual(regels[0].besteld, 35)
        self.assertEqual(regels[0].manco, 11)
        self.assertEqual(regels[0].open, 0)


if __name__ == "__main__":
    unittest.main()
