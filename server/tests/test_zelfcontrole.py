"""Zelfcontrole (R-ZC) — hoofdstuk 9, plus T-16 en T-17.

Alle verwachte uitkomsten zijn afgelezen uit de draaiende browserversie
met demo/test/zelfcontrole-vectoren.mjs (afspraak 2).

Dit bestand test de BESLISSING: wat vindt de zelfcontrole dat er moet
gebeuren. Dat het ook echt gebeurt — de taak vervalt in de database, de
melding gaat dicht, de verplaatsing wordt geboekt — staat in
tests-sql/test_zelfcontrole.sql en tests/test_hertoets_db.py.

Het magazijn is hetzelfde als in test_optimalisatie.py: een picklocatie
waar er dertig op passen, en twee bulkvakken.
"""

import unittest
from datetime import datetime, timedelta, timezone

from vakto import (Artikel, Artikelgroep, Instellingen, Locatie, Magazijn,
                   Taak, Voorraadregel)
from vakto.meten import Maat, Melding
from vakto.zelfcontrole import (VANZELF_OPGELOST, hertoets, laat_vervallen,
                                beoordeel_meldingen, Uitkomst)

NU = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)
DAG = timedelta(days=1)

PICK, BULK_A, BULK_B = 1, 2, 3
OUD = Maat(120, 90, 45, 180)          # er passen er 30 op de picklocatie
NIEUW = Maat(140, 100, 50, 210)       # met deze maat nog maar 27


def magazijn(voorraad=(), maat=OUD, min_qty=None, max_qty=None,
             telinterval=180, geteld_dagen_geleden=0) -> Magazijn:
    """Alles net geteld, tenzij een test er iets anders van wil. Anders
    slaat het telplan (R-OPT-04) in elke ronde aan en gaat deze test over
    iets anders dan waar hij over hoort te gaan."""
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
                           l_mm=maat.l_mm, w_mm=maat.w_mm, h_mm=maat.h_mm,
                           g=maat.g, min_qty=min_qty, max_qty=max_qty)],
        voorraad=[Voorraadregel(1, loc, qty) for loc, qty in voorraad],
        groepen={0: Artikelgroep(0, "Testgroep", telinterval)},
    )


def melding(gevolg="") -> Melding:
    m = Melding(product_id=1, at=NU, d_vol=44.0, d_gew=16.7, gevolg=gevolg)
    m.id = 1
    return m


def taak(soort, **kw) -> Taak:
    standaard = dict(soort=soort, naam=soort.title(), product_id=1, qty=10,
                     van=BULK_A, naar=PICK, at=NU - 1 * DAG)
    standaard.update(kw)
    t = Taak(**standaard)
    t.id = 99
    return t


# ---------------------------------------------------------------------
#  R-ZC-01 en R-ZC-02  Meldingen en overloop
# ---------------------------------------------------------------------
class TestMeldingBeoordelen(unittest.TestCase):
    """Uit zelfcontrole-vectoren.mjs, blok "naMeting"."""

    def test_de_melding_blijft_open_en_krijgt_de_juiste_tekst(self):
        mag = magazijn([(PICK, 30), (BULK_A, 100)], maat=NIEUW)
        m = melding()
        uit = Uitkomst()
        beoordeel_meldingen(mag, [m], [], uit)
        self.assertEqual(m.status, "OPEN")
        self.assertEqual(m.gevolg,
                         "Past niet meer op: 01-01-1 (ligt 30, past nog 27)")
        self.assertEqual(uit.bijgewerkte_meldingen, [m])

    def test_er_komt_een_verplaatstaak_bij(self):
        """R-ZC-02. Waar het systeem zelf iets kan, zet het het werk klaar."""
        mag = magazijn([(PICK, 30), (BULK_A, 100)], maat=NIEUW)
        uit = Uitkomst()
        beoordeel_meldingen(mag, [melding()], [], uit)
        self.assertEqual(len(uit.nieuwe_taken), 1)
        t = uit.nieuwe_taken[0]
        self.assertEqual((t.soort, t.prio, t.van, t.naar, t.qty),
                         ("OVERLOOP", 15, PICK, BULK_A, 3))
        self.assertEqual(t.reden, "01-01-1 zit 3 st over de nieuwe maat")

    def test_t16_de_melding_gaat_vanzelf_dicht(self):
        """T-16, tweede helft. De overlooptaak is uitgevoerd: er liggen er
        nog 27 op de picklocatie en dat past weer."""
        mag = magazijn([(PICK, 27), (BULK_A, 103)], maat=NIEUW)
        m = melding("Past niet meer op: 01-01-1 (ligt 30, past nog 27)")
        uit = Uitkomst()
        beoordeel_meldingen(mag, [m], [], uit)
        self.assertEqual(m.status, "OPGELOST")
        self.assertEqual(m.gevolg, VANZELF_OPGELOST)
        self.assertEqual(uit.gesloten, [m])
        self.assertEqual(uit.nieuwe_taken, [])

    def test_t16_er_komt_een_regel_in_het_log(self):
        """Een besluit dat het systeem zelf neemt, moet je kunnen navragen."""
        mag = magazijn([(PICK, 27)], maat=NIEUW)
        uit = Uitkomst()
        beoordeel_meldingen(mag, [melding()], [], uit)
        self.assertEqual(
            uit.regels,
            ["ZC-1: afwijking vanzelf gesloten, de voorraad past weer"])

    def test_geen_tweede_overlooptaak_voor_dezelfde_locatie(self):
        mag = magazijn([(PICK, 30), (BULK_A, 100)], maat=NIEUW)
        staand = taak("OVERLOOP", van=PICK, naar=BULK_A, qty=3)
        uit = Uitkomst()
        beoordeel_meldingen(mag, [melding()], [staand], uit)
        self.assertEqual(uit.nieuwe_taken, [])

    def test_geen_plek_is_geen_taak(self):
        """Niets gevonden om het teveel heen te brengen? Dan geen taak.
        Dat vraagt een menselijke keuze, en die leg je niet als
        onuitvoerbare opdracht op de vloer neer."""
        mag = magazijn([(PICK, 30)], maat=NIEUW)
        for loc in mag.locaties[1:]:                  # de bulkvakken zijn
            loc.actief = False                        # buiten gebruik
        uit = Uitkomst()
        beoordeel_meldingen(mag, [melding()], [], uit)
        self.assertEqual(uit.nieuwe_taken, [])
        self.assertEqual(uit.bijgewerkte_meldingen[0].status, "OPEN")

    def test_een_gesloten_melding_wordt_overgeslagen(self):
        mag = magazijn([(PICK, 30)], maat=NIEUW)
        m = melding()
        m.status = "DISMISSED"
        uit = Uitkomst()
        beoordeel_meldingen(mag, [m], [], uit)
        self.assertEqual((uit.gesloten, uit.bijgewerkte_meldingen), ([], []))


# ---------------------------------------------------------------------
#  R-ZC-03  Taken laten vervallen
# ---------------------------------------------------------------------
class TestVervallen(unittest.TestCase):
    """Elke soort heeft zijn eigen vervalvoorwaarde."""

    def _reden(self, mag, t) -> str | None:
        uit = Uitkomst()
        laat_vervallen(mag, [t], uit)
        return uit.vervallen[0].reden if uit.vervallen else None

    def test_t17_picklocatie_is_weer_op_peil(self):
        """T-17. Iemand vult de picklocatie met de hand bij tot boven de
        drempel. De aanvultaak is dan overbodig en vervalt — met de reden
        erbij, want verwijderen mag niet."""
        mag = magazijn([(PICK, 25), (BULK_A, 500)], min_qty=20, max_qty=40)
        t = taak("REPLENISH", qty=25)
        uit = Uitkomst()
        laat_vervallen(mag, [t], uit)
        self.assertEqual(len(uit.vervallen), 1)
        self.assertEqual(uit.vervallen[0].reden, "picklocatie is weer op peil")
        self.assertEqual(uit.regels,
                         ["ZC-1: taak vervallen — picklocatie is weer op peil"])

    def test_t17_onder_de_drempel_blijft_de_taak_staan(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        self.assertIsNone(self._reden(mag, taak("REPLENISH", qty=25)))

    def test_aanvullen_zonder_bulkvoorraad(self):
        mag = magazijn([(PICK, 5)], min_qty=20)
        self.assertEqual(self._reden(mag, taak("REPLENISH")),
                         "er ligt geen bulkvoorraad meer om mee aan te vullen")

    def test_overloop_bron_leeg(self):
        mag = magazijn([(BULK_A, 100)], maat=NIEUW)
        t = taak("OVERLOOP", van=PICK, naar=BULK_A, qty=3)
        self.assertEqual(self._reden(mag, t), "de bronlocatie is inmiddels leeg")

    def test_overloop_past_er_weer_in(self):
        """Het artikel is opnieuw gemeten en weer kleiner geworden."""
        mag = magazijn([(PICK, 27), (BULK_A, 100)], maat=OUD)
        t = taak("OVERLOOP", van=PICK, naar=BULK_A, qty=3)
        self.assertEqual(self._reden(mag, t), "het past er inmiddels weer in")

    def test_overloop_blijft_staan_zolang_het_niet_past(self):
        mag = magazijn([(PICK, 30), (BULK_A, 100)], maat=NIEUW)
        t = taak("OVERLOOP", van=PICK, naar=BULK_A, qty=3)
        self.assertIsNone(self._reden(mag, t))

    def test_samenvoegen_bron_leeg(self):
        mag = magazijn([(PICK, 20)])
        t = taak("SAMENVOEG", van=BULK_A, naar=PICK, qty=8)
        self.assertEqual(self._reden(mag, t), "de bronlocatie is al leeg")

    def test_samenvoegen_met_een_reservering(self):
        """Gereserveerde voorraad staat op naam van een order. Daar gaan
        we niet aan zitten, ook niet als de taak er al lag."""
        mag = magazijn([(PICK, 12), (BULK_A, 8)])
        mag.voorraad[1].res = 1
        t = taak("SAMENVOEG", van=BULK_A, naar=PICK, qty=8)
        self.assertEqual(self._reden(mag, t),
                         "er is inmiddels voorraad gereserveerd voor een order")

    def test_samenvoegen_doel_is_leeggelopen(self):
        mag = magazijn([(BULK_A, 8)])
        t = taak("SAMENVOEG", van=BULK_A, naar=PICK, qty=8)
        self.assertEqual(self._reden(mag, t),
                         "op de doellocatie ligt dit artikel niet meer")

    def test_pickplek_is_ingericht(self):
        mag = magazijn([(PICK, 30), (BULK_A, 100)])
        t = taak("PICKPLEK", van=BULK_A, naar=PICK, qty=30)
        self.assertEqual(self._reden(mag, t),
                         "het artikel heeft inmiddels een picklocatie")

    def test_teltaak_na_een_telling(self):
        mag = magazijn([(PICK, 10)], geteld_dagen_geleden=0)
        t = taak("CYCLE_COUNT", van=PICK, naar=PICK, at=NU - 5 * DAG)
        self.assertEqual(self._reden(mag, t), "de locatie is inmiddels geteld")

    def test_teltaak_op_een_leeg_vak(self):
        # vijf dagen geleden geteld, de taak is van gisteren: hij is dus
        # niet "inmiddels geteld" en valt op de andere voorwaarde
        mag = magazijn([(BULK_A, 10)], geteld_dagen_geleden=5)
        t = taak("CYCLE_COUNT", van=PICK, naar=PICK)
        self.assertEqual(self._reden(mag, t),
                         "er ligt niets meer op deze locatie")

    def test_een_afgehandelde_taak_vervalt_niet_alsnog(self):
        mag = magazijn([(PICK, 25), (BULK_A, 500)], min_qty=20)
        t = taak("REPLENISH", status="DONE")
        uit = Uitkomst()
        laat_vervallen(mag, [t], uit)
        self.assertEqual(uit.vervallen, [])


# ---------------------------------------------------------------------
#  Alles achter elkaar
# ---------------------------------------------------------------------
class TestHertoets(unittest.TestCase):

    def test_een_ronde_kan_sluiten_vervallen_en_aanmaken_tegelijk(self):
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        m = melding()
        uit = hertoets(mag, [], [m], nu=NU)
        self.assertEqual(uit.gesloten, [m])          # past weer, dus dicht
        self.assertEqual(len(uit.nieuwe_taken), 1)   # maar wel aanvullen
        self.assertEqual(uit.nieuwe_taken[0].soort, "REPLENISH")

    def test_twee_keer_draaien_verandert_niets_extra(self):
        """R-ZC-00, zeg maar: alles is een gevolgtrekking uit de huidige
        toestand. Draai je hem twee keer op dezelfde toestand, dan komt er
        precies hetzelfde uit — niet het dubbele."""
        mag = magazijn([(PICK, 5), (BULK_A, 500)], min_qty=20, max_qty=40)
        een = hertoets(mag, [], [], nu=NU)
        twee = hertoets(mag, [], [], nu=NU)
        self.assertEqual(len(een.nieuwe_taken), len(twee.nieuwe_taken))
        self.assertEqual(een.nieuwe_taken[0].qty, twee.nieuwe_taken[0].qty)

    def test_een_zojuist_vervallen_taak_blokkeert_geen_nieuwe(self):
        """De aanvultaak vervalt (het vak is op peil) en in dezelfde ronde
        vraagt een order om aanvulling. Dat mag dan gewoon een nieuwe taak
        worden: de oude telt niet meer mee."""
        mag = magazijn([(PICK, 25), (BULK_A, 500)], min_qty=20, max_qty=40)
        oud = taak("REPLENISH", qty=25)
        uit = hertoets(mag, [oud], [], vraag={1: 60}, nu=NU)
        self.assertEqual(len(uit.vervallen), 1)
        self.assertEqual(len(uit.nieuwe_taken), 1)
        self.assertEqual(uit.nieuwe_taken[0].aanleiding, "ordervraag")

    def test_de_lichte_ronde_slaat_hoofdstuk_10_over(self):
        """In de browserversie draait het zware werk hooguit één keer per
        900 ms. Meldingen en vervallen taken moeten wél elke keer kloppen:
        dat is wat iemand op zijn scherm ziet."""
        mag = magazijn([(PICK, 12), (BULK_A, 8)])
        zwaar = hertoets(mag, [], [], nu=NU)
        licht = hertoets(mag, [], [], nu=NU, zwaar=False)
        self.assertTrue(any(t.soort == "SAMENVOEG" for t in zwaar.nieuwe_taken))
        self.assertEqual(licht.nieuwe_taken, [])

    def test_een_stille_ronde_meldt_zich_als_stil(self):
        uit = hertoets(magazijn(), [], [], nu=NU)
        self.assertTrue(uit.stil)
        self.assertEqual(uit.regels, [])


if __name__ == "__main__":
    unittest.main()
