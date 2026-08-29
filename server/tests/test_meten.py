"""Testgevallen T-22 t/m T-31 (R-MEET) — meten en afwijking.

Alle verwachte uitkomsten in dit bestand zijn niet met de hand bedacht
maar uit de browserversie getrokken (vakto-web/meet-vectoren.mjs). Ze
zijn dus geen mening over hoe het zou moeten, maar een afdruk van hoe de
demo die de klant ziet het écht doet. Loopt een van deze tests rood, dan
zeggen de twee versies iets anders over hetzelfde artikel — en dat is
precies wat je nooit wilt uitleggen aan een magazijnchef.

Het scenario is steeds hetzelfde artikel: 120 x 90 x 45 mm, 180 g,
gemeten veertig dagen geleden. De nieuwe meting is 140 x 100 x 50 mm en
210 g: +44,0% volume en +16,7% gewicht.
"""

import unittest
from datetime import datetime, timedelta, timezone

from vakto import Artikel, Locatie, Magazijn, Voorraadregel, Instellingen
from vakto.meten import (Maat, bepaal_afwijking, gevolgen, gevolg_tekst,
                         leg_meting_vast, te_meten, GEEN_GEVOLGEN)

NU = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
OUD = Maat(120, 90, 45, 180)
NIEUW = Maat(140, 100, 50, 210)


def magazijn(voorraad=(), maat: Maat = OUD, stapelbaar: bool = True,
             gemeten_dagen_geleden: int | None = 40,
             bron: str = "RECEIPT") -> Magazijn:
    """Twee locaties: een klein vak en een palletplaats."""
    return Magazijn(
        locaties=[
            Locatie(1, "01-01-1", 0, 300, 400, 220, 12_000, seq=1),
            Locatie(2, "02-03-2", 1, 1200, 800, 1400, 800_000, seq=2),
        ],
        artikelen=[
            Artikel(1, "TEST-001", "Testartikel",
                    l_mm=maat.l_mm if maat else None,
                    w_mm=maat.w_mm if maat else None,
                    h_mm=maat.h_mm if maat else None,
                    g=maat.g if maat else None,
                    stapelbaar=stapelbaar, bron=bron,
                    gemeten_op=(None if gemeten_dagen_geleden is None
                                else NU - timedelta(days=gemeten_dagen_geleden))),
        ],
        voorraad=[Voorraadregel(1, loc, qty) for loc, qty in voorraad],
    )


class TestAfwijking(unittest.TestCase):
    """R-MEET-02."""

    def test_t22_percentages(self):
        a = bepaal_afwijking(OUD, NIEUW, 15)
        self.assertEqual(a.d_vol, 44.0)
        self.assertEqual(a.d_gew, 16.7)
        self.assertTrue(a.melden)

    def test_t23_geen_vorige_meting_geen_melding(self):
        """Een eerste meting is geen afwijking."""
        self.assertIsNone(bepaal_afwijking(None, NIEUW, 15))

    def test_t24_binnen_de_drempel(self):
        """+8,0% volume en +3,3% gewicht: niets aan de hand."""
        a = bepaal_afwijking(OUD, Maat(124, 92, 46, 186), 15)
        self.assertEqual((a.d_vol, a.d_gew), (8.0, 3.3))
        self.assertFalse(a.melden)

    def test_t25_krimpen_telt_ook(self):
        a = bepaal_afwijking(NIEUW, OUD, 15)
        self.assertEqual((a.d_vol, a.d_gew), (-30.6, -14.3))
        self.assertTrue(a.melden)

    def test_t26_alleen_gewicht_is_genoeg(self):
        """Zelfde doos, veel zwaarder. Volume +0,8%, gewicht +27,8%."""
        a = bepaal_afwijking(OUD, Maat(121, 90, 45, 230), 15)
        self.assertEqual((a.d_vol, a.d_gew), (0.8, 27.8))
        self.assertTrue(a.melden)

    def test_drempel_op_het_onafgeronde_getal(self):
        """14,96% is minder dan 15, ook al staat er straks 15,0."""
        vorige = Maat(100, 100, 100, 1000)
        nieuw = Maat(100, 100, 100, 1149)          # +14,9%
        a = bepaal_afwijking(vorige, nieuw, 15)
        self.assertFalse(a.melden)
        a2 = bepaal_afwijking(vorige, Maat(100, 100, 100, 1150), 15)
        self.assertTrue(a2.melden)


class TestGevolgen(unittest.TestCase):
    """R-MEET-03 — het stuk dat het verschil maakt."""

    def test_t27_locatie_in_de_knel(self):
        k = gevolgen(magazijn([(1, 30)]), 1, NIEUW)
        self.assertEqual(len(k), 1)
        self.assertEqual((k[0].code, k[0].ligt, k[0].past), ("01-01-1", 30, 27))
        self.assertEqual(gevolg_tekst(k),
                         "Past niet meer op: 01-01-1 (ligt 30, past nog 27)")

    def test_t28_past_nog_wel(self):
        """Tien stuks in een vak waar er nog 27 passen: geen probleem."""
        k = gevolgen(magazijn([(1, 10)]), 1, NIEUW)
        self.assertEqual(k, [])
        self.assertEqual(gevolg_tekst(k), GEEN_GEVOLGEN)

    def test_t29_alleen_de_locatie_die_knelt(self):
        """Het vak zit klem, de palletplaats niet. Alleen het vak noemen."""
        k = gevolgen(magazijn([(1, 30), (2, 900)]), 1, NIEUW)
        self.assertEqual([x.code for x in k], ["01-01-1"])

    def test_zonder_voorraad_geen_knelpunt(self):
        self.assertEqual(gevolgen(magazijn([]), 1, NIEUW), [])

    def test_t30_niet_stapelbaar(self):
        """Eén laag: er passen er zes, en er liggen er acht."""
        k = gevolgen(magazijn([(1, 8)], stapelbaar=False), 1, NIEUW)
        self.assertEqual(gevolg_tekst(k),
                         "Past niet meer op: 01-01-1 (ligt 8, past nog 6)")

    def test_t31_gewicht_wordt_de_grens(self):
        """Zelfde doos, vijf keer zo zwaar. 12 kg deelt door 900 g = 13."""
        k = gevolgen(magazijn([(1, 30)]), 1, Maat(120, 90, 45, 900))
        self.assertEqual(gevolg_tekst(k),
                         "Past niet meer op: 01-01-1 (ligt 30, past nog 13)")

    def test_doorloopplekken_tellen_niet_mee(self):
        """Een pallet in de keuring "past" daar niet minder om."""
        mag = magazijn([(1, 30)])
        mag.locaties.append(Locatie(3, "QC-01", 3, 300, 400, 220, 12_000, seq=3))
        mag.voorraad.append(Voorraadregel(1, 3, 30))
        k = gevolgen(mag, 1, NIEUW)
        self.assertEqual([x.code for x in k], ["01-01-1"])

    def test_volgorde_is_altijd_gelijk(self):
        """Op location.seq, niet op de volgorde van de voorraadregels."""
        mag = magazijn([(2, 3000), (1, 30)])
        k = gevolgen(mag, 1, NIEUW)
        self.assertEqual([x.code for x in k], ["01-01-1", "02-03-2"])


class TestLegMetingVast(unittest.TestCase):
    """R-MEET-01 t/m R-MEET-03 samen."""

    def test_melding_met_gevolg(self):
        mag = magazijn([(1, 30)])
        m = leg_meting_vast(mag, 1, 140, 100, 50, 210, nu=NU)
        self.assertIsNotNone(m)
        self.assertEqual((m.d_vol, m.d_gew, m.status), (44.0, 16.7, "OPEN"))
        self.assertEqual(m.gevolg,
                         "Past niet meer op: 01-01-1 (ligt 30, past nog 27)")

    def test_melding_zonder_gevolg(self):
        mag = magazijn([])
        m = leg_meting_vast(mag, 1, 140, 100, 50, 210, nu=NU)
        self.assertEqual(m.gevolg, GEEN_GEVOLGEN)

    def test_binnen_de_drempel_geen_melding(self):
        mag = magazijn([(1, 30)])
        self.assertIsNone(leg_meting_vast(mag, 1, 124, 92, 46, 186, nu=NU))

    def test_eerste_meting_geen_melding(self):
        mag = magazijn([(1, 30)], maat=None, gemeten_dagen_geleden=None)
        self.assertIsNone(leg_meting_vast(mag, 1, 140, 100, 50, 210, nu=NU))
        self.assertTrue(mag.artikel(1).gemeten)

    def test_de_maat_gaat_mee_naar_het_artikel(self):
        """Na afloop rekent alles met de nieuwe maat, ook zonder melding."""
        mag = magazijn([(1, 30)])
        leg_meting_vast(mag, 1, 124, 92, 46, 186, bron="CONTROL", nu=NU)
        a = mag.artikel(1)
        self.assertEqual((a.l_mm, a.w_mm, a.h_mm, a.g), (124, 92, 46, 186))
        self.assertEqual((a.bron, a.gemeten_op), ("CONTROL", NU))

    def test_gevolg_rekent_met_de_nieuwe_maat(self):
        """Valkuil: eerst bijwerken, dan vergelijken = nooit een melding."""
        mag = magazijn([(1, 30)])
        m = leg_meting_vast(mag, 1, 140, 100, 50, 210, nu=NU)
        self.assertIn("past nog 27", m.gevolg)

    def test_onzin_wordt_geweigerd(self):
        mag = magazijn([(1, 30)])
        with self.assertRaises(ValueError):
            leg_meting_vast(mag, 1, 140, 100, 0, 210, nu=NU)
        with self.assertRaises(ValueError):
            leg_meting_vast(mag, 1, 140, 100, 50, 210, bron="GOKJE", nu=NU)
        with self.assertRaises(KeyError):
            leg_meting_vast(mag, 99, 140, 100, 50, 210, nu=NU)

    def test_drempel_komt_uit_de_instellingen(self):
        """R-BASIS-04: een klant met onregelmatige verpakkingen zet hem hoger."""
        inst = Instellingen({"drift.alert_threshold_pct": "50"})
        mag = magazijn([(1, 30)])
        self.assertIsNone(
            leg_meting_vast(mag, 1, 140, 100, 50, 210, inst=inst, nu=NU))


class TestTeMeten(unittest.TestCase):
    """R-MEET-04."""

    def test_nooit_gemeten_staat_bovenaan(self):
        mag = magazijn([], maat=None, gemeten_dagen_geleden=None)
        mag.artikelen.append(Artikel(2, "TEST-002", l_mm=100, w_mm=100,
                                     h_mm=100, g=100, bron="SUPPLIER",
                                     gemeten_op=NU - timedelta(days=1)))
        self.assertEqual([a.id for a in te_meten(mag, nu=NU)], [1, 2])

    def test_opgegeven_maat_is_geen_gemeten_maat(self):
        mag = magazijn([], bron="SUPPLIER", gemeten_dagen_geleden=1)
        self.assertEqual([a.id for a in te_meten(mag, nu=NU)], [1])

    def test_vers_gemeten_staat_er_niet_bij(self):
        mag = magazijn([], bron="RECEIPT", gemeten_dagen_geleden=40)
        self.assertEqual(te_meten(mag, nu=NU), [])

    def test_te_oud(self):
        mag = magazijn([], bron="RECEIPT", gemeten_dagen_geleden=181)
        self.assertEqual([a.id for a in te_meten(mag, nu=NU)], [1])

    def test_oudste_eerst(self):
        mag = magazijn([], bron="RECEIPT", gemeten_dagen_geleden=200)
        mag.artikelen.append(Artikel(2, "TEST-002", l_mm=100, w_mm=100,
                                     h_mm=100, g=100, bron="RECEIPT",
                                     gemeten_op=NU - timedelta(days=400)))
        self.assertEqual([a.id for a in te_meten(mag, nu=NU)], [2, 1])

    def test_termijn_komt_uit_de_instellingen(self):
        mag = magazijn([], bron="RECEIPT", gemeten_dagen_geleden=40)
        inst = Instellingen({"drift.remeasure_after_days": "30"})
        self.assertEqual([a.id for a in te_meten(mag, inst=inst, nu=NU)], [1])


if __name__ == "__main__":
    unittest.main()
