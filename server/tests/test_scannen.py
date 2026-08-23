"""Scanmodus (R-SCAN) — hoofdstuk 12.

De meldingen zijn hier belangrijker dan gewoonlijk. Dit is het enige
scherm dat iemand met handschoenen aan gebruikt, en "Verkeerde locatie.
Je staat bij 01-01-1, je moet naar 01-04-5." is het verschil tussen
doorlopen en stilstaan. Ze zijn woord voor woord afgelezen uit de
draaiende browserversie met demo/test/scan-vectoren.mjs (afspraak 2).

Er komt geen database aan te pas: de scanner is een toestandsmachine en
levert alleen een opdracht af. Het boeken doet `opslag.py`.
"""

import unittest

from vakto import Artikel, Instellingen, Locatie, Magazijn, Voorraadregel
from vakto.scannen import (Gebruiker, Inslagopdracht, Pickopdracht, Scanner,
                           Telopdracht)
from vakto.uitgaand import Pickregel

PICK, BULK = 1, 2


def magazijn(voorraad=()) -> Magazijn:
    return Magazijn(
        locaties=[
            Locatie(PICK, "01-01-1", 0, 300, 400, 220, 12_000, seq=1_000_110),
            Locatie(BULK, "02-01-1", 1, 1200, 800, 1500, 900_000, seq=2_999_810),
        ],
        artikelen=[
            Artikel(1, "AFD-1317", "Testartikel", l_mm=120, w_mm=90, h_mm=45,
                    g=180, barcode="8710000000017"),
            Artikel(2, "BEV-1000", "Ander artikel", l_mm=120, w_mm=90, h_mm=45,
                    g=180, barcode="8710000000024"),
            Artikel(3, "GEEN-MAAT", "Nooit opgemeten"),
        ],
        voorraad=[Voorraadregel(p, loc, qty) for p, loc, qty in voorraad],
    )


def pickregel(qty=9, gepickt=0, locatie=PICK, product=1) -> Pickregel:
    return Pickregel(allocation_id=77, order_id=1, ordernummer="ORD-1", regel=0,
                     product_id=product, sku="AFD-1317" if product == 1 else "BEV-1000",
                     oms="", location_id=locatie,
                     locatie="01-01-1" if locatie == PICK else "02-01-1",
                     seq=1_000_110, qty=qty, gepickt=gepickt)


def scanner(taak="PICKEN", regels=None, voorraad=(), inst=None) -> Scanner:
    return Scanner(mag=magazijn(voorraad),
                   pickregels=list(regels if regels is not None else [pickregel()]),
                   gebruikers=[Gebruiker("BADGE-2", "Ruben de Groot")],
                   inst=inst, taak=taak)


# ---------------------------------------------------------------------
#  R-SCAN-02 en R-SCAN-04  Picken
# ---------------------------------------------------------------------
class TestPicken(unittest.TestCase):
    """Uit scan-vectoren.mjs, blok "picken"."""

    def setUp(self):
        self.s = scanner()

    def test_hij_begint_bij_de_locatie(self):
        self.assertEqual(self.s.stap, "LOCATIE")

    def test_eerst_de_locatie_dan_pas_het_artikel(self):
        """Andersom pakt iemand van het verkeerde schap en klopt de
        voorraad niet meer."""
        a = self.s.scan("8710000000017")
        self.assertEqual(a.bericht, "Scan eerst de locatie waar je staat")
        self.assertEqual(a.soort, "fout")
        self.assertEqual(self.s.stap, "LOCATIE")

    def test_een_onbekende_code_zegt_wat_er_aan_de_hand_kan_zijn(self):
        a = self.s.scan("87999999999")
        self.assertEqual(a.bericht, "Onbekende code: 87999999999. Label "
                                    "onleesbaar of locatie niet in het systeem.")
        self.assertEqual(a.soort, "fout")

    def test_de_verkeerde_locatie_zegt_waar_je_wel_heen_moet(self):
        """R-SCAN-03. "Fout" laat iemand raden; dit laat hem lopen."""
        s = scanner(regels=[pickregel(locatie=BULK)])
        a = s.scan("01-01-1")
        self.assertEqual(a.bericht, "Verkeerde locatie. Je staat bij 01-01-1, "
                                    "je moet naar 02-01-1.")
        self.assertEqual(a.soort, "fout")

    def test_de_goede_locatie_brengt_je_een_stap_verder(self):
        a = self.s.scan("01-01-1")
        self.assertEqual(a.bericht, "01-01-1 — scan nu het artikel")
        self.assertEqual((a.stap, a.soort), ("ARTIKEL", "ok"))

    def test_het_verkeerde_artikel_noemt_allebei_de_nummers(self):
        self.s.scan("01-01-1")
        a = self.s.scan("8710000000024")
        self.assertEqual(a.bericht,
                         "Verkeerd artikel. Dit is BEV-1000, gevraagd is AFD-1317.")

    def test_het_goede_artikel_stelt_het_openstaande_aantal_voor(self):
        self.s.scan("01-01-1")
        a = self.s.scan("8710000000017")
        self.assertEqual(a.bericht, "AFD-1317 — bevestig het aantal")
        self.assertEqual((a.stap, self.s.aantal), ("AANTAL", 9))

    def test_een_artikelnummer_scant_net_zo_goed_als_een_barcode(self):
        self.s.scan("01-01-1")
        self.assertEqual(self.s.scan("afd-1317").stap, "AANTAL")

    def test_volledig_afmelden(self):
        self.s.scan("01-01-1")
        self.s.scan("8710000000017")
        a = self.s.bevestig(9)
        self.assertEqual(a.bericht, "Afgemeld: 9 st")
        self.assertEqual(a.soort, "klaar")
        self.assertEqual(a.opdracht, Pickopdracht(77, 9))

    def test_minder_afmelden_is_een_manco(self):
        self.s.scan("01-01-1")
        self.s.scan("8710000000017")
        a = self.s.bevestig(8)
        self.assertEqual(a.bericht, "Manco vastgelegd. Reservering "
                                    "vrijgegeven en teltaak aangemaakt.")
        self.assertEqual(a.soort, "fout")
        self.assertEqual(a.opdracht, Pickopdracht(77, 8))

    def test_na_afmelden_staat_de_volgende_regel_klaar(self):
        s = scanner(regels=[pickregel(), pickregel(locatie=BULK)])
        s.scan("01-01-1")
        s.scan("8710000000017")
        s.bevestig(9)
        self.assertEqual(s.stap, "LOCATIE")
        self.assertEqual(s.regel.locatie, "02-01-1")

    def test_zonder_regels_is_hij_klaar(self):
        s = scanner(regels=[])
        self.assertEqual(s.stap, "KLAAR")
        self.assertEqual(s.scan("01-01-1").bericht, "Geen openstaande pickregels")

    def test_overslaan_is_geen_manco(self):
        """De regel gaat achteraan en je komt er later langs. Er wordt
        niets geboekt en er ontstaat geen teltaak."""
        s = scanner(regels=[pickregel(), pickregel(locatie=BULK)])
        eerste = s.regel
        a = s.sla_over()
        self.assertEqual(a.bericht, "Regel achteraan gezet")
        self.assertIsNone(a.opdracht)
        self.assertEqual(s.regel.locatie, "02-01-1")
        self.assertIs(s.pickregels[-1], eerste)


# ---------------------------------------------------------------------
#  R-SCAN-05  Tellen
# ---------------------------------------------------------------------
class TestTellen(unittest.TestCase):
    """Uit scan-vectoren.mjs, blokken "tellen" en "telVerschil"."""

    def setUp(self):
        self.s = scanner("TELLEN", voorraad=[(1, PICK, 27)])

    def test_ook_hier_eerst_de_locatie(self):
        a = self.s.scan("8710000000017")
        self.assertEqual(a.bericht, "Scan de locatie die je gaat tellen")

    def test_de_stappen(self):
        a = self.s.scan("01-01-1")
        self.assertEqual(a.bericht, "01-01-1 — scan het artikel")
        self.assertEqual(a.stap, "TEL_ARTIKEL")
        a = self.s.scan("8710000000017")
        self.assertEqual(a.bericht, "AFD-1317 — tel en vul het echte aantal in")
        self.assertEqual((a.stap, self.s.aantal), ("TEL_AANTAL", 27))

    def test_een_kloppende_telling(self):
        self.s.scan("01-01-1")
        self.s.scan("8710000000017")
        a = self.s.bevestig(27)
        self.assertEqual(a.bericht, "Telling klopt")
        self.assertEqual(a.soort, "klaar")
        self.assertEqual(a.opdracht, Telopdracht(PICK, 1, 27, False))

    def test_een_verschil_wordt_benoemd_en_geboekt(self):
        self.s.scan("01-01-1")
        self.s.scan("8710000000017")
        a = self.s.bevestig(25)
        self.assertEqual(a.bericht,
                         "Verschil van -2 geboekt met reden TELVERSCHIL")
        self.assertEqual(a.soort, "fout")
        self.assertEqual(a.opdracht.geteld, 25)
        self.assertEqual(a.opdracht.reden, "TELVERSCHIL")

    def test_een_verschil_omhoog_krijgt_een_plus(self):
        self.s.scan("01-01-1")
        self.s.scan("8710000000017")
        self.assertEqual(self.s.bevestig(30).bericht,
                         "Verschil van +3 geboekt met reden TELVERSCHIL")

    def test_het_telstempel_gaat_altijd(self):
        """Ook als er niets verschilt: daar hangt R-ZC-03 op."""
        self.s.scan("01-01-1")
        self.s.scan("8710000000017")
        self.assertIsNotNone(self.s.bevestig(27).opdracht)


class TestNulmeting(unittest.TestCase):
    """R-SCAN-05. Een magazijn dat nooit iets vastlegde."""

    def setUp(self):
        self.aan = Instellingen({"opstart.onbekend_aanmaken": "true"})

    def test_een_onbekende_code_wordt_een_nieuw_artikel(self):
        s = scanner("TELLEN", inst=self.aan)
        s.scan("01-01-1")
        a = s.scan("8712345678901")
        self.assertEqual(a.bericht, "Nieuw artikel 8712345678901 aangemaakt "
                                    "— hoeveel liggen er?")
        self.assertEqual((a.stap, a.soort), ("TEL_AANTAL", "waarschuw"))

    def test_zonder_die_instelling_wordt_hij_geweigerd(self):
        """Buiten een nulmeting ontstaan er anders artikelen door een
        verkeerd label."""
        s = scanner("TELLEN")
        s.scan("01-01-1")
        a = s.scan("8712345678901")
        self.assertEqual(a.bericht, "Scan het artikel")
        self.assertEqual(a.soort, "fout")

    def test_het_heet_geen_telverschil_maar_een_nulmeting(self):
        """Anders lijkt de eerste dag van een nieuwe klant vol telfouten
        te zitten."""
        s = scanner("TELLEN", inst=self.aan)
        s.scan("01-01-1")
        s.scan("8710000000017")
        a = s.bevestig(37)
        self.assertEqual(a.bericht, "37 st vastgelegd op 01-01-1")
        self.assertEqual(a.soort, "klaar")
        self.assertEqual(a.opdracht.reden, "NULMETING")
        self.assertEqual(a.opdracht.ref, "Opstartinventarisatie")

    def test_op_een_vak_waar_al_iets_lag_is_het_gewoon_een_verschil(self):
        s = scanner("TELLEN", voorraad=[(1, PICK, 27)], inst=self.aan)
        s.scan("01-01-1")
        s.scan("8710000000017")
        self.assertEqual(s.bevestig(25).opdracht.reden, "TELVERSCHIL")


# ---------------------------------------------------------------------
#  R-SCAN-06  Inslaan
# ---------------------------------------------------------------------
class TestInslag(unittest.TestCase):
    """Uit scan-vectoren.mjs, blokken "inslag" en verder."""

    def setUp(self):
        self.s = scanner("INSLAG")

    def test_hij_begint_bij_het_artikel(self):
        self.assertEqual(self.s.stap, "ARTIKEL")
        a = self.s.scan("01-01-1")
        self.assertEqual(a.bericht, "Scan het artikel dat je wilt inslaan")

    def test_een_artikel_stelt_een_aantal_voor(self):
        a = self.s.scan("8710000000024")
        self.assertEqual(a.bericht, "BEV-1000 — hoeveel sla je in?")
        self.assertEqual((a.stap, self.s.aantal), ("INSLAG_AANTAL", 12))

    def test_zonder_maat_geen_inslag(self):
        """Zonder maat is er geen voorstel, en dus geen plek."""
        a = self.s.scan("GEEN-MAAT")
        self.assertEqual(a.bericht,
                         "GEEN-MAAT is nooit opgemeten — meet het eerst op")
        self.assertEqual(a.soort, "fout")

    def test_na_het_aantal_moet_je_naar_een_voorgestelde_plek(self):
        self.s.scan("8710000000024")
        a = self.s.bevestig(6)
        self.assertEqual(a.bericht,
                         "Loop naar een van de voorgestelde plekken en scan die")
        self.assertEqual(a.stap, "INSLAG_LOCATIE")

    def test_een_plek_die_niet_is_voorgesteld_wordt_geweigerd(self):
        """Anders is de hele benuttingsberekening een advies dat niemand
        opvolgt."""
        s = scanner("INSLAG", voorraad=[(2, PICK, 30)])   # de picklocatie is vol
        s.scan("8710000000024")
        s.bevestig(6)
        a = s.scan("01-01-1")
        self.assertEqual(a.bericht, "Hier past het niet, of de locatie zit "
                                    "vol. Kies een voorgestelde plek.")
        self.assertEqual(a.soort, "fout")

    def test_een_voorgestelde_plek_levert_een_boeking(self):
        self.s.scan("8710000000024")
        self.s.bevestig(6)
        a = self.s.scan("01-01-1")
        self.assertEqual(a.bericht, "6 x BEV-1000 ingeslagen op 01-01-1")
        self.assertEqual(a.soort, "klaar")
        self.assertEqual(a.opdracht, Inslagopdracht(2, PICK, 6))
        self.assertEqual(self.s.stap, "ARTIKEL")   # klaar voor de volgende


# ---------------------------------------------------------------------
#  R-SCAN-07  De badge
# ---------------------------------------------------------------------
class TestBadge(unittest.TestCase):

    def test_een_badge_werkt_in_elke_stap(self):
        for taak in ("PICKEN", "TELLEN", "INSLAG", "VRIJ"):
            s = scanner(taak)
            a = s.scan("BADGE-2")
            self.assertEqual(a.bericht, "Ingelogd als Ruben de Groot", taak)
            self.assertEqual(s.gebruiker, "Ruben de Groot")

    def test_een_badge_haalt_je_niet_uit_je_stap(self):
        """Wisselen van gebruiker gaat op de vloer om de tien minuten en
        mag nooit betekenen dat je opnieuw moet beginnen."""
        s = scanner()
        s.scan("01-01-1")
        s.scan("BADGE-2")
        self.assertEqual(s.stap, "ARTIKEL")


class TestVrij(unittest.TestCase):
    """Opzoeken zonder dat er iets gebeurt."""

    def test_een_locatie_en_een_artikel_worden_alleen_getoond(self):
        s = scanner("VRIJ")
        self.assertEqual(s.scan("01-01-1").bericht, "Locatie 01-01-1")
        self.assertEqual(s.scan("8710000000017").bericht, "AFD-1317")

    def test_een_onbekende_code_blijft_onbekend(self):
        s = scanner("VRIJ")
        a = s.scan("999")
        self.assertEqual(a.bericht, "Onbekende code: 999")
        self.assertEqual(a.soort, "fout")

    def test_er_komt_nooit_een_opdracht_uit(self):
        s = scanner("VRIJ")
        self.assertIsNone(s.scan("01-01-1").opdracht)


if __name__ == "__main__":
    unittest.main()
