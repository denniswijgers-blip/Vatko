"""Inloggen, rollen en sessies (R-GEB) — T-39 t/m T-42.

Deze testgevallen zijn niet uit de browserversie afgelezen: die kent
geen wachtwoorden en geen sessies. Ze staan er omdat het precies de
gevallen zijn waarin een fout niemand opvalt tot het te laat is. Een
weggelaten menu-item ziet er hetzelfde uit als een dichte deur, en een
sessie die per ongeluk gedeeld wordt merk je pas als twee pickers elkaars
regels afmelden.

Het eerste deel draait zonder database: rollen, rangen en wachtwoorden
zijn rekenwerk. De rest heeft een PostgreSQL nodig en draait in één
transactie die aan het eind wordt teruggedraaid.
"""

import time
import unittest
from pathlib import Path

from vakto import gebruikers, opslag, schermen, web

from .psqlschil import PsqlVerbinding, psql_beschikbaar

WACHTWOORD = "proefwachtwoord"
ANDER = "nogeenwachtwoord"


# =====================================================================
#  Zonder database: rollen en wachtwoorden
# =====================================================================
class TestRollen(unittest.TestCase):
    """R-GEB-01 en R-GEB-02."""

    def test_de_drie_rollen_hebben_een_oplopende_rang(self):
        self.assertEqual(
            [gebruikers.rang(r) for r in
             ("OPERATOR", "SUPERVISOR", "ADMIN")], [1, 2, 3])

    def test_het_werk_op_de_vloer_mag_iedereen(self):
        for pad in ("/picken", "/scan", "/taken", "/meten", "/inslag",
                    "/locaties", "/artikelen"):
            with self.subTest(pad=pad):
                self.assertTrue(gebruikers.mag("OPERATOR", pad))

    def test_sturen_is_rang_twee_en_instellen_rang_drie(self):
        self.assertFalse(gebruikers.mag("OPERATOR", "/orders"))
        self.assertTrue(gebruikers.mag("SUPERVISOR", "/orders"))
        self.assertFalse(gebruikers.mag("SUPERVISOR", "/gebruikers"))
        self.assertTrue(gebruikers.mag("ADMIN", "/gebruikers"))

    def test_een_detailpad_erft_van_zijn_scherm(self):
        """`/orders/12` valt onder `/orders`, anders is de lijst dicht en
        de order eronder open."""
        self.assertFalse(gebruikers.mag("OPERATOR", "/orders/12"))
        self.assertTrue(gebruikers.mag("SUPERVISOR", "/orders/12"))

    def test_een_onbekend_pad_is_rang_een(self):
        """Een nieuw scherm is zichtbaar voor iedereen tot iemand er iets
        anders van vindt, en niet onzichtbaar tot iemand het merkt."""
        self.assertTrue(gebruikers.mag("OPERATOR", "/iets-nieuws"))

    def test_een_onbekende_rol_mag_niets(self):
        self.assertFalse(gebruikers.mag("HOOFDKOK", "/picken"))
        self.assertFalse(gebruikers.mag("", "/picken"))

    def test_iedereen_begint_op_een_scherm_dat_hij_mag_zien(self):
        for rol in gebruikers.ROLLEN:
            with self.subTest(rol=rol):
                self.assertTrue(gebruikers.mag(rol, gebruikers.startpad(rol)))

    def test_een_badge_komt_alleen_in_de_scanmodus(self):
        """R-GEB-03. Ook als de rol erachter beheerder is."""
        baas = gebruikers.Gebruiker(1, "Dennis", "dennis", "ADMIN",
                                    alleen_scanner=True)
        self.assertTrue(baas.mag("/scan"))
        for pad in ("/", "/orders", "/gebruikers", "/picken", "/meten"):
            with self.subTest(pad=pad):
                self.assertFalse(baas.mag(pad))
        # Uitloggen moet altijd kunnen; anders zit iemand vast.
        self.assertTrue(baas.mag("/uitloggen"))


class TestWachtwoorden(unittest.TestCase):
    """R-GEB-04 en R-GEB-07."""

    def test_het_wachtwoord_staat_niet_in_de_afdruk(self):
        afdruk = gebruikers.versleutel("hetgeheimewachtwoord")
        self.assertNotIn("hetgeheimewachtwoord", afdruk)
        self.assertTrue(afdruk.startswith("scrypt$"))

    def test_twee_keer_hetzelfde_wachtwoord_geeft_twee_afdrukken(self):
        """Zonder zout zie je in de tabel wie hetzelfde wachtwoord heeft."""
        self.assertNotEqual(gebruikers.versleutel("zelfdewachtwoord"),
                            gebruikers.versleutel("zelfdewachtwoord"))

    def test_toetsen(self):
        afdruk = gebruikers.versleutel("eenlangwachtwoord")
        self.assertTrue(gebruikers.klopt("eenlangwachtwoord", afdruk))
        self.assertFalse(gebruikers.klopt("eenlangwachtwoorD", afdruk))
        self.assertFalse(gebruikers.klopt("", afdruk))

    def test_zonder_afdruk_kan_het_antwoord_nooit_ja_zijn(self):
        """Iemand zonder wachtwoord komt alleen met zijn badge binnen."""
        self.assertFalse(gebruikers.klopt("wat dan ook", None))
        self.assertFalse(gebruikers.klopt("", None))

    def test_een_onleesbare_afdruk_laat_niemand_binnen(self):
        for rommel in ("", "x", "bcrypt$2b$12$abc", "scrypt$abc"):
            with self.subTest(afdruk=rommel):
                self.assertFalse(gebruikers.klopt("iets", rommel))

    def test_de_parameters_verhuizen_mee(self):
        """R-GEB-04. Worden ze over vijf jaar te licht, dan kun je ze
        verhogen zonder dat bestaande rijen onleesbaar worden."""
        oud = gebruikers.versleutel("eenlangwachtwoord", n=2 ** 12)
        self.assertIn("$4096$", oud)
        self.assertTrue(gebruikers.klopt("eenlangwachtwoord", oud))

    def test_een_onbekende_naam_kost_evenveel_tijd(self):
        """R-GEB-07. Anders verraadt de snelheid wie er wél bestaat, hoe
        zorgvuldig de tekst ook gekozen is.

        De marge is ruim: dit is geen meting maar een vangnet tegen het
        verschil tussen "rekenen" en "meteen terug".
        """
        afdruk = gebruikers.versleutel("eenlangwachtwoord")

        def duur(opgeslagen) -> float:
            begin = time.perf_counter()
            gebruikers.klopt("een poging", opgeslagen)
            return time.perf_counter() - begin

        bestaat = min(duur(afdruk) for _ in range(3))
        bestaat_niet = min(duur(None) for _ in range(3))
        self.assertGreater(bestaat_niet, bestaat / 3)

    def test_een_kort_wachtwoord_wordt_geweigerd(self):
        self.assertIsNotNone(gebruikers.zwak("kort"))
        self.assertIsNotNone(gebruikers.zwak("elftekens1"))
        self.assertIsNone(gebruikers.zwak("twaalftekens"))

    def test_een_token_is_niet_te_raden(self):
        tokens = {gebruikers.nieuw_token() for _ in range(200)}
        self.assertEqual(len(tokens), 200)
        self.assertGreater(len(gebruikers.nieuw_token()), 30)

    def test_het_token_zelf_gaat_de_database_niet_in(self):
        """R-GEB-05. Anders levert een gestolen back-up meteen een stapel
        geldige sessies op."""
        token = gebruikers.nieuw_token()
        self.assertNotIn(token, gebruikers.afdruk(token))
        self.assertEqual(gebruikers.afdruk(token), gebruikers.afdruk(token))


# =====================================================================
#  Met database
# =====================================================================
class TestToegang(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest(
                "Geen bereikbare PostgreSQL. Zet hem op met opzetten.sh, of "
                "sla deze tests over — de rest draait gewoon.")
        cls.v = PsqlVerbinding()
        cls.v.begin()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "v", None) is not None:
            cls.v.rollback()
            cls.v.sluit()

    def setUp(self):
        self.v.stuur("SAVEPOINT t; TRUNCATE app_user CASCADE;"
                     " DELETE FROM inlogpoging;")
        self.baas = opslag.bewaar_gebruiker(
            self.v, "dennis", "Dennis Wijgers", "ADMIN", WACHTWOORD,
            "BADGE-1001")
        self.picker = opslag.bewaar_gebruiker(
            self.v, "kevin", "Kevin Timmermans", "OPERATOR", ANDER,
            "BADGE-1003")

    def tearDown(self):
        self.v.stuur("ROLLBACK TO SAVEPOINT t;")

    def tel(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()[0]

    # -----------------------------------------------------------------
    #  Inloggen (R-GEB-03, R-GEB-05)
    # -----------------------------------------------------------------
    def test_inloggen_en_weer_uitloggen(self):
        aan = opslag.meld_aan(self.v, "dennis", WACHTWOORD)
        self.assertTrue(aan.gelukt)
        wie = opslag.wie_is(self.v, aan.token)
        self.assertEqual((wie.naam, wie.rol), ("Dennis Wijgers", "ADMIN"))
        self.assertFalse(wie.alleen_scanner)

        self.assertTrue(opslag.meld_af(self.v, aan.token))
        self.assertIsNone(opslag.wie_is(self.v, aan.token))
        # Twee keer uitloggen is geen fout, maar levert ook niets op.
        self.assertFalse(opslag.meld_af(self.v, aan.token))

    def test_de_gebruikersnaam_is_hoofdletterongevoelig(self):
        self.assertTrue(opslag.meld_aan(self.v, "DENNIS", WACHTWOORD).gelukt)
        self.assertTrue(opslag.meld_aan(self.v, " Dennis ", WACHTWOORD).gelukt)

    def test_een_verzonnen_token_geeft_niemand(self):
        self.assertIsNone(opslag.wie_is(self.v, gebruikers.nieuw_token()))
        self.assertIsNone(opslag.wie_is(self.v, ""))
        self.assertIsNone(opslag.wie_is(self.v, None))

    def test_een_badge_geeft_alleen_de_scanmodus(self):
        """R-GEB-03, ook voor een beheerder."""
        aan = opslag.meld_aan_met_badge(self.v, "BADGE-1001")
        self.assertTrue(aan.gelukt)
        wie = opslag.wie_is(self.v, aan.token)
        self.assertTrue(wie.alleen_scanner)
        self.assertEqual(wie.rol, "ADMIN")       # de rol blijft wat hij is
        self.assertTrue(wie.mag("/scan"))
        self.assertFalse(wie.mag("/orders"))

    def test_een_onbekende_badge_komt_er_niet_in(self):
        aan = opslag.meld_aan_met_badge(self.v, "BADGE-9999")
        self.assertFalse(aan.gelukt)
        self.assertIn("badge", aan.fout.lower())

    def test_wie_uit_dienst_gaat_is_er_meteen_uit(self):
        """R-GEB-05. Niet pas als de server toevallig herstart."""
        aan = opslag.meld_aan(self.v, "kevin", ANDER)
        self.assertIsNotNone(opslag.wie_is(self.v, aan.token))
        opslag.zet_gebruiker_uit(self.v, self.picker)
        self.assertIsNone(opslag.wie_is(self.v, aan.token))
        self.assertFalse(opslag.meld_aan(self.v, "kevin", ANDER).gelukt)

    def test_sessies_intrekken(self):
        """Voor als een telefoon kwijt is."""
        a = opslag.meld_aan(self.v, "kevin", ANDER)
        b = opslag.meld_aan(self.v, "kevin", ANDER)
        self.assertEqual(opslag.trek_sessies_in(self.v, self.picker), 2)
        self.assertIsNone(opslag.wie_is(self.v, a.token))
        self.assertIsNone(opslag.wie_is(self.v, b.token))

    def test_een_verlopen_sessie_geldt_niet_meer(self):
        aan = opslag.meld_aan(self.v, "dennis", WACHTWOORD)
        # Terugzetten in de tijd, allebei: de tabel bewaakt zelf dat
        # `tot` na `at` ligt, en dat is precies de bedoeling.
        self.v.stuur("UPDATE app_session SET at  = now() - interval '13 hours',"
                     "                       tot = now() - interval '1 hour';")
        self.assertIsNone(opslag.wie_is(self.v, aan.token))

    # -----------------------------------------------------------------
    #  T-41  Mislukte pogingen
    # -----------------------------------------------------------------
    def test_t41_te_veel_pogingen_zet_de_naam_op_slot(self):
        for _ in range(10):
            self.assertFalse(
                opslag.meld_aan(self.v, "dennis", "verkeerd").gelukt)
        op_slot = opslag.meld_aan(self.v, "dennis", "verkeerd")
        self.assertIn("kwartier", op_slot.fout)
        # En ook het góéde wachtwoord komt er nu niet meer doorheen.
        self.assertFalse(opslag.meld_aan(self.v, "dennis", WACHTWOORD).gelukt)
        # Een ander is er niet de dupe van.
        self.assertTrue(opslag.meld_aan(self.v, "kevin", ANDER).gelukt)

    def test_t41_een_onbekende_naam_geeft_dezelfde_melding(self):
        """R-GEB-07. "Onbekende gebruiker" vertelt wie er wél bestaat."""
        bestaat = opslag.meld_aan(self.v, "dennis", "verkeerd")
        bestaat_niet = opslag.meld_aan(self.v, "sinterklaas", "verkeerd")
        self.assertEqual(bestaat.fout, bestaat_niet.fout)

    def test_een_gelukte_poging_wist_de_teller(self):
        """Anders loopt wie vanmorgen drie keer misklikte vanmiddag
        alsnog tegen het slot aan."""
        for _ in range(5):
            opslag.meld_aan(self.v, "dennis", "verkeerd")
        self.assertTrue(opslag.meld_aan(self.v, "dennis", WACHTWOORD).gelukt)
        self.assertEqual(self.tel(
            "SELECT count(*) n FROM inlogpoging WHERE NOT gelukt"), 0)

    def test_het_foute_wachtwoord_wordt_niet_opgeschreven(self):
        """Meestal is dat het góéde wachtwoord van een ander systeem."""
        opslag.meld_aan(self.v, "dennis", "mijnbankwachtwoord")
        with self.v.cursor() as cur:
            cur.execute("SELECT count(*) n FROM inlogpoging p "
                        "WHERE p.gebruikersnaam LIKE '%bank%'")
            self.assertEqual(cur.fetchone()[0], 0)

    # -----------------------------------------------------------------
    #  T-42  Wie het boekte staat erbij
    # -----------------------------------------------------------------
    def test_t42_inloggen_en_uitloggen_staan_in_het_log(self):
        voor = self.tel("SELECT count(*) n FROM event_log WHERE bron='inloggen'")
        aan = opslag.meld_aan(self.v, "kevin", ANDER)
        opslag.meld_af(self.v, aan.token)
        opslag.meld_aan(self.v, "kevin", "verkeerd")
        na = self.tel("SELECT count(*) n FROM event_log WHERE bron='inloggen'")
        self.assertEqual(na - voor, 3)
        self.assertGreater(self.tel(
            "SELECT count(*) n FROM event_log "
            "WHERE bron='inloggen' AND niveau='WARN'"), 0)

    # -----------------------------------------------------------------
    #  Beheer
    # -----------------------------------------------------------------
    def test_een_bestaande_gebruiker_bijwerken_wist_zijn_wachtwoord_niet(self):
        opslag.bewaar_gebruiker(self.v, "kevin", "Kevin Timmermans",
                                "SUPERVISOR")
        aan = opslag.meld_aan(self.v, "kevin", ANDER)
        self.assertTrue(aan.gelukt)
        self.assertEqual(opslag.wie_is(self.v, aan.token).rol, "SUPERVISOR")

    def test_een_zwak_wachtwoord_wordt_geweigerd(self):
        with self.assertRaises(opslag.Boekfout):
            opslag.bewaar_gebruiker(self.v, "kort", "Kort", "OPERATOR", "abc")

    def test_een_onbekende_rol_wordt_geweigerd(self):
        with self.assertRaises(opslag.Boekfout):
            opslag.bewaar_gebruiker(self.v, "kok", "Kok", "HOOFDKOK",
                                    WACHTWOORD)

    def test_de_lijst_toont_nooit_het_wachtwoord(self):
        for rij in opslag.gebruikerslijst(self.v):
            self.assertNotIn("scrypt", str(rij))
        # Wel of er een is: zonder dat weet een beheerder niet wie er
        # alleen met een badge werkt.
        self.assertTrue(all(r[7] for r in opslag.gebruikerslijst(self.v)))


# =====================================================================
#  T-39 en T-40: door de schermen heen
#
#  Deze twee zijn het punt van stap 9. Alle andere tests bewijzen dat een
#  functie klopt; deze bewijzen dat het systeem klopt zodra er een tweede
#  persoon bij komt.
# =====================================================================
VOORBEELDEN = (Path(__file__).resolve().parent.parent.parent
               / "verkoop" / "voorbeeldbestanden")
LOCATIES = VOORBEELDEN / "Rommelig - locaties (in cm).csv"
ARTIKELEN = VOORBEELDEN / "Rommelig - artikelen (Engels, xlsx).xlsx"
VOORRAAD = VOORBEELDEN / "Rommelig - voorraad.csv"

LEEG = ("TRUNCATE journal, stock, measurement, allocation, order_line, "
        "customer_order, task, alert, event_log, product, product_group, "
        "location, zone, app_user CASCADE;")


@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestTweeMensen(unittest.TestCase):
    """T-39 en T-40, via `web.behandel()` — dus langs dezelfde weg als een
    browser, maar zonder socket."""

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest("Geen bereikbare PostgreSQL.")
        from vakto.inlezen import (controleer, herken_kolommen, lees_bestand,
                                   raad_eenheden)
        loc = lees_bestand(LOCATIES)
        art = lees_bestand(ARTIKELEN)
        vrd = lees_bestand(VOORRAAD)
        k_loc = herken_kolommen("locaties", loc.kop)
        k_art = herken_kolommen("artikelen", art.kop)
        rapport = controleer(loc, k_loc, art, k_art, vrd,
                             herken_kolommen("voorraad", vrd.kop),
                             raad_eenheden(loc, k_loc, art, k_art))
        cls.echt = PsqlVerbinding()
        cls.echt.begin()
        cls.echt.stuur(LEEG)
        opslag.neem_over(cls.echt, rapport, gebruiker="opzet")
        cls.v = _Proef(cls.echt)
        opslag.bewaar_gebruiker(cls.v, "dennis", "Dennis Wijgers", "ADMIN",
                                WACHTWOORD, "BADGE-1001")
        opslag.bewaar_gebruiker(cls.v, "kevin", "Kevin Timmermans",
                                "OPERATOR", ANDER, "BADGE-1003")
        opslag.bewaar_gebruiker(cls.v, "marta", "Marta Nowak", "OPERATOR",
                                ANDER, "BADGE-1004")
        cls.v.commit()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "echt", None) is not None:
            cls.echt.rollback()
            cls.echt.sluit()

    def setUp(self):
        self.standen = web.Standen(klant="Proefklant")
        self.tokens = {}

    # -- hulpjes -----------------------------------------------------
    def token(self, naam: str, wachtwoord: str = ANDER) -> str:
        if naam not in self.tokens:
            aan = opslag.meld_aan(self.v, naam, wachtwoord)
            self.assertTrue(aan.gelukt, aan.fout)
            self.v.commit()
            self.tokens[naam] = aan.token
        return self.tokens[naam]

    def haal(self, naam: str, pad: str, **vraag):
        return web.behandel(
            self.v, self.standen, "GET", pad,
            {k: [str(w)] for k, w in vraag.items()}, {},
            token=self.tokens.get(naam))

    def post(self, naam: str, pad: str, **velden):
        return web.behandel(
            self.v, self.standen, "POST", pad, {},
            {k: [str(w)] for k, w in velden.items()},
            token=self.tokens.get(naam))

    def rij(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()

    def order_klaarzetten(self, nummer: str, aantal: int = 4) -> int:
        import json
        regels = self.rij("""
            SELECT json_agg(json_build_object('sku', x.sku,
                                              'besteld', %s))::text
              FROM (SELECT p.sku FROM v_available v
                      JOIN product p ON p.id = v.product_id
                     WHERE v.beschikbaar > 20 ORDER BY p.id LIMIT 3) x
        """ % aantal)[0]
        with self.v.cursor() as cur:
            cur.execute("SELECT vakto_order(%s, %s, %s::jsonb, %s, %s) AS id",
                        (nummer, "Proefklant", regels, 1, "TEST"))
            oid = int(cur.fetchone()[0])
        opslag.reserveer(self.v, oid, "opzet")
        opslag.geef_vrij(self.v, oid)
        self.v.commit()
        return oid

    # -----------------------------------------------------------------
    #  T-40  Rechten worden op de server getoetst
    # -----------------------------------------------------------------
    def test_t40_een_medewerker_komt_niet_bij_de_orders(self):
        """R-GEB-02. Het menu weglaten is opmaak, geen beveiliging."""
        self.token("kevin")
        scherm = self.haal("kevin", "/picken")
        self.assertEqual(scherm.status, 200)
        # Niet in het menu…
        self.assertNotIn('href="/orders"', scherm.lijf)
        # …maar dat is niet waar het om gaat: het adres zelf is dicht.
        geweigerd = self.haal("kevin", "/orders")
        self.assertEqual(geweigerd.status, 403)
        self.assertIn("teamleider", geweigerd.lijf.lower())

    def test_t40_ook_een_post_wordt_geweigerd(self):
        """Anders is de knop weg maar het formulier nog te versturen."""
        self.token("kevin")
        oid = self.order_klaarzetten("T40-1")
        antwoord = self.post("kevin", f"/orders/{oid}", actie="verzenden")
        self.assertEqual(antwoord.status, 403)
        self.assertEqual(
            self.rij(f"SELECT status FROM customer_order WHERE id={oid}")[0],
            "VRIJGEGEVEN")

    def test_t40_een_detailpad_is_net_zo_dicht_als_de_lijst(self):
        self.token("kevin")
        oid = self.order_klaarzetten("T40-2")
        self.assertEqual(self.haal("kevin", f"/orders/{oid}").status, 403)

    def test_t40_het_beheerscherm_is_alleen_voor_rang_drie(self):
        self.token("kevin")
        self.token("dennis", WACHTWOORD)
        self.assertEqual(self.haal("kevin", "/gebruikers").status, 403)
        self.assertEqual(self.haal("dennis", "/gebruikers").status, 200)

    def test_zonder_inloggen_kom_je_nergens(self):
        for pad in ("/", "/picken", "/orders", "/scan", "/gebruikers"):
            with self.subTest(pad=pad):
                r = self.haal("niemand", pad)
                self.assertEqual(r.status, 303)
                self.assertTrue(r.naar.startswith("/inloggen"))

    def test_waar_je_heen_wilde_blijft_bewaard(self):
        """En het reist ook echt mee tot in het formulier, anders is het
        na het inloggen alsnog kwijt."""
        r = self.haal("niemand", "/locaties")
        self.assertIn("terug=%2Flocaties", r.naar)
        scherm = web.behandel(self.v, self.standen, "GET", "/inloggen",
                              {"terug": ["/locaties"]}, {})
        self.assertIn('name="terug" value="/locaties"', scherm.lijf)
        klaar = web.behandel(self.v, self.standen, "POST", "/inloggen", {},
                             {"soort": ["wachtwoord"],
                              "gebruikersnaam": ["kevin"],
                              "wachtwoord": [ANDER],
                              "terug": ["/locaties"]})
        self.assertEqual(klaar.naar, "/locaties")

    def test_een_medewerker_begint_op_het_pickscherm(self):
        """Op je eigen beginscherm hoor je geen weigering te krijgen."""
        self.token("kevin")
        r = self.haal("kevin", "/")
        self.assertEqual(r.status, 303)
        self.assertEqual(r.naar, "/picken")
        self.assertEqual(self.haal("dennis", "/").status, 303)   # nog niet in

    def test_een_badge_komt_alleen_op_het_scanscherm(self):
        aan = opslag.meld_aan_met_badge(self.v, "BADGE-1001")
        self.v.commit()
        self.tokens["badge"] = aan.token
        self.assertEqual(self.haal("badge", "/scan").status, 200)
        self.assertEqual(self.haal("badge", "/gebruikers").status, 403)
        self.assertEqual(self.haal("badge", "/picken").status, 403)

    # -----------------------------------------------------------------
    #  T-39  Twee mensen tegelijk
    # -----------------------------------------------------------------
    def test_t39_ieder_ziet_zijn_eigen_scanstand(self):
        """De kern van R-GEB-05. Wie de scanstand deelt, ziet de ander
        midden in zijn scan de stap veranderen."""
        self.token("kevin")
        self.token("marta")
        self.order_klaarzetten("T39-1")

        self.post("kevin", "/scan", actie="taak", taak="TELLEN")
        self.assertEqual(self.haal("kevin", "/scan").status, 200)

        # Marta staat nog gewoon op picken.
        marta = opslag.wie_is(self.v, self.tokens["marta"])
        self.assertEqual(self.standen.van(marta).taak, "PICKEN")
        kevin = opslag.wie_is(self.v, self.tokens["kevin"])
        self.assertEqual(self.standen.van(kevin).taak, "TELLEN")

    def test_t39_overslaan_schuift_bij_de_ander_niets_op(self):
        """R-SCAN-04 per persoon. Overslaan is een keuze van één picker."""
        self.token("kevin")
        self.token("marta")
        self.order_klaarzetten("T39-2")

        kevin = opslag.wie_is(self.v, self.tokens["kevin"])
        marta = opslag.wie_is(self.v, self.tokens["marta"])
        eerste = web._scanner(self.v, self.standen.van(kevin)).regel
        self.assertIsNotNone(eerste)

        self.post("kevin", "/scan", actie="overslaan")

        self.assertEqual(
            web._scanner(self.v, self.standen.van(marta)).regel.allocation_id,
            eerste.allocation_id)
        self.assertNotEqual(
            web._scanner(self.v, self.standen.van(kevin)).regel.allocation_id,
            eerste.allocation_id)

    def test_t39_precies_een_van_de_twee_krijgt_de_laatste_stuks(self):
        """De voorraad mag niet scheef lopen doordat er twee mensen zijn.

        Dit is de schermversie van `tests-sql/test_gelijktijdig.sh`. Daar
        gaat het om twee sessies die tegelijk vergrendelen; hier om twee
        ingelogde mensen die dezelfde pickregel afmelden. De tweede hoort
        niets meer te kunnen afboeken.
        """
        self.token("kevin")
        self.token("marta")
        oid = self.order_klaarzetten("T39-3")

        aid, qty = self.rij(f"SELECT id, qty FROM allocation "
                            f"WHERE order_id={oid} ORDER BY id LIMIT 1")
        pid, loc = self.rij(f"SELECT product_id, location_id FROM allocation "
                            f"WHERE id={aid}")
        voor = self.rij(f"SELECT qty FROM stock WHERE product_id={pid} "
                        f"AND location_id={loc}")[0]

        self.post("kevin", "/picken", regel=aid, aantal=qty)
        self.post("marta", "/picken", regel=aid, aantal=qty)

        na = self.rij(f"SELECT qty FROM stock WHERE product_id={pid} "
                      f"AND location_id={loc}")[0]
        self.assertEqual(na, voor - qty, "er is twee keer afgeboekt")
        self.assertEqual(self.rij(
            f"SELECT gepickt FROM allocation WHERE id={aid}")[0], qty)
        self.assertEqual(self.rij(
            "SELECT count(*) n FROM stock WHERE qty < 0 OR res > qty")[0], 0)

    def test_t39_wie_het_boekte_staat_erbij(self):
        """R-GEB-06, T-42 door de schermen heen."""
        self.token("kevin")
        oid = self.order_klaarzetten("T39-4")
        aid, qty = self.rij(f"SELECT id, qty FROM allocation "
                            f"WHERE order_id={oid} ORDER BY id LIMIT 1")
        self.post("kevin", "/picken", regel=aid, aantal=qty)
        self.assertEqual(self.rij(
            "SELECT gebruiker FROM journal WHERE soort='PICK' "
            "ORDER BY id DESC LIMIT 1")[0], "Kevin Timmermans")

    def test_t39_uitloggen_raakt_de_ander_niet(self):
        self.token("kevin")
        self.token("marta")
        web.behandel(self.v, self.standen, "POST", "/uitloggen", {}, {},
                     token=self.tokens["kevin"])
        self.assertIsNone(opslag.wie_is(self.v, self.tokens["kevin"]))
        self.assertIsNotNone(opslag.wie_is(self.v, self.tokens["marta"]))
        self.assertEqual(self.haal("marta", "/picken").status, 200)

    # -----------------------------------------------------------------
    #  De weg naar binnen
    # -----------------------------------------------------------------
    def test_inloggen_via_het_scherm(self):
        r = web.behandel(self.v, self.standen, "POST", "/inloggen", {},
                         {"soort": ["wachtwoord"],
                          "gebruikersnaam": ["kevin"],
                          "wachtwoord": [ANDER]})
        self.assertEqual(r.status, 303)
        self.assertEqual(r.naar, "/picken")
        naam, waarde, leeftijd = r.koekje
        self.assertEqual(naam, "vakto")
        self.assertGreater(leeftijd, 0)
        self.assertIsNotNone(opslag.wie_is(self.v, waarde))

    def test_een_verkeerd_wachtwoord_geeft_401_en_geen_koekje(self):
        r = web.behandel(self.v, self.standen, "POST", "/inloggen", {},
                         {"soort": ["wachtwoord"],
                          "gebruikersnaam": ["kevin"],
                          "wachtwoord": ["verkeerd"]})
        self.assertEqual(r.status, 401)
        self.assertIsNone(r.koekje)
        self.assertIn("klopt niet", r.lijf)

    def test_je_komt_nooit_op_een_scherm_uit_waar_je_niet_mag(self):
        """Wie net is ingelogd hoort niet meteen tegen "hier mag je niet
        bij" aan te lopen; dat leest als "het inloggen is mislukt"."""
        r = web.behandel(self.v, self.standen, "POST", "/inloggen", {},
                         {"soort": ["wachtwoord"], "gebruikersnaam": ["kevin"],
                          "wachtwoord": [ANDER], "terug": ["/orders"]})
        self.assertEqual(r.naar, "/picken")

    def test_een_gepreparerde_terugverwijzing_werkt_niet(self):
        """Zonder deze controle kun je iemand met een link na het
        inloggen op een andere site laten uitkomen."""
        r = web.behandel(self.v, self.standen, "POST", "/inloggen", {},
                         {"soort": ["wachtwoord"], "gebruikersnaam": ["kevin"],
                          "wachtwoord": [ANDER],
                          "terug": ["//ergens-anders.nl/"]})
        self.assertEqual(r.naar, "/picken")

    def test_uitloggen_wist_het_koekje(self):
        self.token("kevin")
        r = web.behandel(self.v, self.standen, "POST", "/uitloggen", {}, {},
                         token=self.tokens["kevin"])
        self.assertEqual(r.koekje, ("vakto", "", 0))

    def test_wie_al_ingelogd_is_hoeft_het_inlogscherm_niet(self):
        self.token("kevin")
        r = self.haal("kevin", "/inloggen")
        self.assertEqual(r.naar, "/picken")


class _Proef:
    """Zelfde truc als in test_schermen.py: commit en rollback als
    savepunt, zodat alles aan het eind terugdraait."""

    def __init__(self, echt):
        self.echt = echt
        self.echt.stuur("SAVEPOINT toegang;")

    def cursor(self):
        return self.echt.cursor()

    def commit(self) -> None:
        self.echt.stuur("RELEASE SAVEPOINT toegang; SAVEPOINT toegang;")

    def rollback(self) -> None:
        self.echt.stuur("ROLLBACK TO SAVEPOINT toegang;")


if __name__ == "__main__":
    unittest.main()
