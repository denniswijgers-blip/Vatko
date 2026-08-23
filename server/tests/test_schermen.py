"""De schermen: elk scherm opvragen en er een hele order doorheen halen.

Dit is de servertegenhanger van `demo/test/test-paden.mjs`. Daar loopt
een browser door de demo heen; hier loopt de test door de router heen.
Er komt geen socket aan te pas: `web.behandel()` krijgt een verbinding,
een pad en een formulier, en geeft een reactie terug. Zo blijft een
scherm te testen zonder dat er iets draait — dezelfde scheiding als
overal in dit project.

Wat hier bewezen wordt:

  * elk scherm uit het menu geeft een bladzijde terug, geen fout
  * een order loopt via de schermen van NIEUW tot VERZONDEN
  * een pick met te weinig stuks levert een manco op, ook via het scherm
  * de scanmodus boekt echt (R-SCAN), en overslaan is geen manco
  * een meting via het scherm komt als regel in de tijdlijn terecht
  * een POST antwoordt nooit met een bladzijde maar met een omleiding,
    zodat F5 niet nog een keer boekt

Draait alleen als er een PostgreSQL bereikbaar is. Alles gebeurt in één
transactie die aan het eind wordt teruggedraaid.
"""

import json
import re
import unittest
from pathlib import Path

from vakto import schermen, web
from vakto.modellen import Magazijn
from vakto.scannen import Scanner
from vakto.uitgaand import Pickregel
from vakto.inlezen import (controleer, herken_kolommen, lees_bestand,
                           raad_eenheden)
from vakto.opslag import neem_over

from .psqlschil import PsqlVerbinding, psql_beschikbaar

WORTEL = Path(__file__).resolve().parent.parent.parent
VOORBEELDEN = WORTEL / "verkoop" / "voorbeeldbestanden"
STIJL = WORTEL / "demo" / "stijl.css"
LOCATIES = VOORBEELDEN / "Rommelig - locaties (in cm).csv"
ARTIKELEN = VOORBEELDEN / "Rommelig - artikelen (Engels, xlsx).xlsx"
VOORRAAD = VOORBEELDEN / "Rommelig - voorraad.csv"

LEEG = ("TRUNCATE journal, stock, measurement, allocation, order_line, "
        "customer_order, task, alert, event_log, product, product_group, "
        "location, zone CASCADE;")


class Proefverbinding:
    """Doet alsof commit en rollback echt zijn, binnen één transactie.

    De router commit na elke handeling — dat hoort ook zo, anders staat
    een pick pas vast als er toevallig nog iets anders gebeurt. Maar een
    test die echt commit laat rommel achter. Met een savepoint krijg je
    allebei: binnen de test gedragen commit en rollback zich normaal, en
    aan het eind rolt de buitenste transactie alles terug.
    """

    def __init__(self, echt):
        self.echt = echt
        self.echt.stuur("SAVEPOINT web;")

    def cursor(self):
        return self.echt.cursor()

    def commit(self) -> None:
        self.echt.stuur("RELEASE SAVEPOINT web; SAVEPOINT web;")

    def rollback(self) -> None:
        self.echt.stuur("ROLLBACK TO SAVEPOINT web;")


@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestSchermen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest(
                "Geen bereikbare PostgreSQL. Zet hem op met opzetten.sh, of "
                "sla deze tests over — de rest draait gewoon.")
        loc = lees_bestand(LOCATIES)
        art = lees_bestand(ARTIKELEN)
        vrd = lees_bestand(VOORRAAD)
        rapport = controleer(
            loc, herken_kolommen("locaties", loc.kop),
            art, herken_kolommen("artikelen", art.kop),
            vrd, herken_kolommen("voorraad", vrd.kop),
            raad_eenheden(loc, herken_kolommen("locaties", loc.kop),
                          art, herken_kolommen("artikelen", art.kop)))
        cls.echt = PsqlVerbinding()
        cls.echt.begin()
        cls.echt.stuur(LEEG)
        neem_over(cls.echt, rapport, gebruiker="dennis")
        cls.v = Proefverbinding(cls.echt)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "echt", None) is not None:
            cls.echt.rollback()
            cls.echt.sluit()

    def setUp(self):
        self.sessie = web.Sessie(klant="Proefklant")

    # -----------------------------------------------------------------
    #  Hulpjes
    # -----------------------------------------------------------------
    def haal(self, pad: str, **vraag):
        vraag = {k: [str(w)] for k, w in vraag.items()}
        return web.behandel(self.v, self.sessie, "GET", pad, vraag, {})

    def post(self, pad: str, **velden):
        form = {k: [str(w)] for k, w in velden.items()}
        return web.behandel(self.v, self.sessie, "POST", pad, {}, form)

    def rij(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()

    def rijen(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()

    def nieuwe_order(self, nummer: str, regels, prio: int = 3) -> int:
        with self.v.cursor() as cur:
            cur.execute("SELECT vakto_order(%s, %s, %s::jsonb, %s, %s)",
                        (nummer, "Proefklant", json.dumps(regels), prio, "TEST"))
            return int(cur.fetchone()[0])

    def voorraadartikel(self):
        """Een artikel met genoeg vrije voorraad om mee te spelen."""
        return self.rij("""
            SELECT p.id, p.sku, v.beschikbaar
              FROM v_available v JOIN product p ON p.id = v.product_id
             WHERE v.beschikbaar > 8
             ORDER BY v.beschikbaar DESC, p.id
             LIMIT 1
        """)

    # -----------------------------------------------------------------
    #  Elk scherm komt in beeld
    # -----------------------------------------------------------------
    def test_elk_scherm_uit_het_menu_geeft_een_bladzijde(self):
        from vakto.schermen import MENU
        for pad, naam, _groep, _bij in MENU:
            with self.subTest(scherm=naam):
                r = self.haal(pad)
                self.assertEqual(r.status, 200)
                self.assertIn("<!doctype html>", r.lijf)
                self.assertIn("</html>", r.lijf)
                self.assertIn("/stijl.css", r.lijf)

    def test_het_menu_wijst_het_scherm_aan_waar_je_staat(self):
        r = self.haal("/locaties")
        self.assertIn('href="/locaties" class="actief"', r.lijf)
        self.assertNotIn('href="/taken" class="actief"', r.lijf)

    def test_het_dashboard_toont_wat_er_in_de_database_staat(self):
        aantal = self.rij("SELECT count(*) n FROM location WHERE actief")[0]
        r = self.haal("/")
        self.assertIn("Locaties", r.lijf)
        self.assertIn(f"{aantal:,}".replace(",", "."), r.lijf)

    def test_een_scherm_dat_niet_bestaat_geeft_404(self):
        r = self.haal("/kantine")
        self.assertEqual(r.status, 404)
        self.assertIn("bestaat niet", r.lijf)

    def test_een_order_die_niet_bestaat_geeft_404(self):
        self.assertEqual(self.haal("/orders/99999999").status, 404)

    def test_locaties_en_artikelen_staan_er_echt_in(self):
        code = self.rij("SELECT code FROM location ORDER BY seq LIMIT 1")[0]
        sku = self.rij("SELECT sku FROM product ORDER BY sku LIMIT 1")[0]
        self.assertIn(code, self.haal("/locaties").lijf)
        self.assertIn(sku, self.haal("/artikelen").lijf)

    def test_het_inslagscherm_rekent_een_voorstel_uit(self):
        pid, sku, _ = self.voorraadartikel()
        r = self.haal("/inslag", product=pid, aantal=12)
        self.assertEqual(r.status, 200)
        self.assertIn("Benutting", r.lijf)
        # R-INS-03: er staat een benuttingspercentage, geen "past/past niet".
        self.assertIn("%", r.lijf)

    # -----------------------------------------------------------------
    #  Een order van NIEUW tot VERZONDEN, alleen via de schermen
    # -----------------------------------------------------------------
    def test_een_order_loopt_via_de_schermen_de_deur_uit(self):
        pid, sku, vrij = self.voorraadartikel()
        oid = self.nieuwe_order("SCHERM-1", [{"sku": sku, "besteld": 4}])

        self.assertIn("SCHERM-1", self.haal("/orders").lijf)
        scherm = self.haal(f"/orders/{oid}").lijf
        self.assertIn("Reserveren", scherm)

        r = self.post(f"/orders/{oid}", actie="reserveer")
        self.assertEqual(r.status, 303)
        self.assertIn("/orders/", r.naar)
        self.assertEqual(self.stand(oid), "GERESERVEERD")
        self.assertIn("Vrijgeven", self.haal(f"/orders/{oid}").lijf)

        self.post(f"/orders/{oid}", actie="vrijgeven")
        self.assertEqual(self.stand(oid), "VRIJGEGEVEN")

        # Het pickscherm staat op looproute (R-UIT-03) en kent deze regel.
        picken = self.haal("/picken").lijf
        self.assertIn("SCHERM-1", picken)

        for aid, qty, gepickt in self.rijen(
                f"SELECT id, qty, gepickt FROM allocation "
                f"WHERE order_id = {oid} ORDER BY id"):
            self.post("/picken", regel=aid, aantal=qty - gepickt)
        self.assertEqual(self.stand(oid), "GEPICKT")

        r = self.post(f"/orders/{oid}", actie="verzenden")
        self.assertEqual(r.status, 303)
        self.assertEqual(self.stand(oid), "VERZONDEN")

        # R-UIT-07: colli en gewicht staan vast, en op het scherm.
        colli, gewicht = self.rij(
            f"SELECT colli, gewicht_g FROM customer_order WHERE id = {oid}")
        self.assertGreater(colli, 0)
        self.assertGreater(gewicht, 0)
        self.assertIn("collo", self.haal(f"/orders/{oid}").lijf)

        # R-UIT-06: niets blijft hangen.
        self.assertEqual(self.rij(
            f"SELECT count(*) n FROM allocation WHERE order_id = {oid} "
            f"AND status = 'TODO'")[0], 0)

    def stand(self, oid: int) -> str:
        return self.rij(f"SELECT status FROM customer_order WHERE id = {oid}")[0]

    def test_minder_afmelden_dan_gevraagd_is_een_manco(self):
        """R-UIT-05, via het scherm. De reservering komt vrij en er komt
        een teltaak — precies zoals bij de scanner en de simulatie."""
        pid, sku, _ = self.voorraadartikel()
        oid = self.nieuwe_order("SCHERM-2", [{"sku": sku, "besteld": 6}])
        self.post(f"/orders/{oid}", actie="reserveer")
        self.post(f"/orders/{oid}", actie="vrijgeven")

        aid, qty = self.rij(f"SELECT id, qty FROM allocation "
                            f"WHERE order_id = {oid} ORDER BY id LIMIT 1")
        taken_voor = self.rij(
            "SELECT count(*) n FROM task WHERE soort = 'CYCLE_COUNT'")[0]

        r = self.post("/picken", regel=aid, aantal=qty - 2)
        self.assertEqual(r.status, 303)
        self.assertIn("Manco", r.naar)

        self.assertEqual(self.rij(
            f"SELECT status FROM allocation WHERE id = {aid}")[0], "MANCO")
        self.assertGreater(self.rij(
            "SELECT count(*) n FROM task WHERE soort = 'CYCLE_COUNT'")[0],
            taken_voor)

    def test_een_order_zonder_voorraad_gaat_wachten(self):
        """R-UIT-02. Geen foutmelding maar een stand, en dat moet de
        gebruiker ook te zien krijgen."""
        sku = self.rij("""
            SELECT p.sku FROM product p
             WHERE NOT EXISTS (SELECT 1 FROM stock s
                                WHERE s.product_id = p.id AND s.qty > 0)
             LIMIT 1
        """)
        if sku is None:
            self.skipTest("elk artikel heeft voorraad in dit bestand")
        oid = self.nieuwe_order("SCHERM-3", [{"sku": sku[0], "besteld": 3}])
        r = self.post(f"/orders/{oid}", actie="reserveer")
        self.assertIn("wacht", r.naar.lower())
        self.assertEqual(self.stand(oid), "WACHT_OP_VOORRAAD")

    # -----------------------------------------------------------------
    #  Scanmodus (R-SCAN)
    # -----------------------------------------------------------------
    def test_de_scanmodus_neemt_het_hele_scherm_over(self):
        r = self.haal("/scan")
        self.assertIn('class="scanmodus"', r.lijf)
        self.assertIn("scanschil", r.lijf)
        # Eén invoerveld, en de cursor staat erin (R-SCAN-01).
        self.assertIn('name="code"', r.lijf)
        self.assertIn("autofocus", r.lijf)

    def test_tellen_via_de_scanner_boekt_het_verschil(self):
        """R-SCAN-05. Wat de scanner uitrekent wordt hier ook echt
        geboekt — dat is precies de naad tussen scannen.py en web.py."""
        loc, pid, qty, code, sku = self.telbaar()
        self.post("/scan", actie="taak", taak="TELLEN")
        self.assertEqual(self.sessie.taak, "TELLEN")

        self.post("/scan", actie="scan", code=code)
        self.post("/scan", actie="scan", code=sku)
        r = self.post("/scan", actie="bevestig", aantal=qty - 3)
        self.assertEqual(r.status, 303)
        self.assertIn("TELVERSCHIL", r.naar)

        self.assertEqual(self.rij(
            f"SELECT qty FROM stock WHERE location_id = {loc} "
            f"AND product_id = {pid}")[0], qty - 3)
        # R-SCAN-05: soort COUNT, reden TELVERSCHIL. Niet "ADJUST" en
        # niet "TELLING" — die naam is het verschil tussen "hier gaat
        # iets mis" en "hier begint een nieuwe klant".
        self.assertEqual(self.rij(
            f"SELECT count(*) n FROM journal WHERE soort = 'COUNT' "
            f"AND reden = 'TELVERSCHIL' AND product_id = {pid}")[0], 1)

    def telbaar(self):
        return self.rij("""
            SELECT s.location_id, s.product_id, s.qty, l.code, p.sku
              FROM stock s
              JOIN location l ON l.id = s.location_id
              JOIN product  p ON p.id = s.product_id
             WHERE s.qty > 5 AND s.res = 0
             ORDER BY s.location_id, s.product_id
             LIMIT 1
        """)

    def test_overslaan_zet_de_regel_achteraan_en_boekt_niets(self):
        """R-SCAN-04. Overslaan zegt "nu even niet", niet "het ligt er
        niet". Boekt er iets, dan staat er straks een teltaak voor een
        vak waar niets aan de hand is."""
        pid, sku, _ = self.voorraadartikel()
        oid = self.nieuwe_order("SCHERM-4", [{"sku": sku, "besteld": 2}])
        self.post(f"/orders/{oid}", actie="reserveer")
        self.post(f"/orders/{oid}", actie="vrijgeven")

        eerste = web._scanner(self.v, self.sessie).regel
        journaal = self.rij("SELECT count(*) n FROM journal")[0]

        self.post("/scan", actie="overslaan")
        self.assertIn(eerste.allocation_id, self.sessie.achteraan)
        self.assertEqual(self.rij("SELECT count(*) n FROM journal")[0],
                         journaal)

        # En de regel is ook echt naar achteren geschoven.
        opnieuw = web._scanner(self.v, self.sessie)
        if len(opnieuw.pickregels) > 1:
            self.assertNotEqual(opnieuw.regel.allocation_id,
                                eerste.allocation_id)
        self.assertEqual(opnieuw.pickregels[-1].allocation_id,
                         eerste.allocation_id)

    def test_een_badge_werkt_in_elke_stap(self):
        """R-SCAN-07. Er is nog geen gebruikerstabel; tot stap 9 kent de
        server geen badges en hoort een onbekende code een nette
        foutmelding te geven in plaats van een lege pagina."""
        r = self.post("/scan", actie="scan", code="ZZZ-BESTAAT-NIET")
        self.assertEqual(r.status, 303)
        self.assertIn("s=fout", r.naar)

    # -----------------------------------------------------------------
    #  Opmeten (R-MEET)
    # -----------------------------------------------------------------
    def test_een_meting_via_het_scherm_komt_in_de_tijdlijn(self):
        pid, sku, _ = self.voorraadartikel()
        voor = self.rij(f"SELECT count(*) n FROM measurement "
                        f"WHERE product_id = {pid}")[0]
        r = self.post("/meten", product=pid, l=310, w=210, h=110, g=850)
        self.assertEqual(r.status, 303)
        self.assertEqual(self.rij(f"SELECT count(*) n FROM measurement "
                                  f"WHERE product_id = {pid}")[0], voor + 1)
        # R-AFG-01: de actuele maat is de nieuwste meting, niet een veld.
        self.assertEqual(self.rij(f"SELECT l_mm FROM v_product_current "
                                  f"WHERE product_id = {pid}")[0], 310)

    def test_een_halve_meting_wordt_geweigerd(self):
        pid, sku, _ = self.voorraadartikel()
        voor = self.rij("SELECT count(*) n FROM measurement")[0]
        r = self.post("/meten", product=pid, l=310, w=0, h=110, g=850)
        self.assertIn("s=fout", r.naar)
        self.assertEqual(self.rij("SELECT count(*) n FROM measurement")[0],
                         voor)

    # -----------------------------------------------------------------
    #  Taken (R-ZC, R-OPT)
    # -----------------------------------------------------------------
    def test_een_taak_afmelden_via_het_scherm(self):
        from vakto.opslag import draai_zelfcontrole
        draai_zelfcontrole(self.v)
        self.v.commit()
        taak = self.rij("SELECT id, qty FROM task WHERE status = 'TODO' "
                        "AND soort = 'CYCLE_COUNT' ORDER BY prio, id LIMIT 1")
        if taak is None:
            self.skipTest("de zelfcontrole had niets te doen")
        r = self.post("/taken", taak=taak[0], aantal=taak[1] or "")
        self.assertEqual(r.status, 303)
        self.assertNotEqual(self.rij(
            f"SELECT status FROM task WHERE id = {taak[0]}")[0], "TODO")

    # -----------------------------------------------------------------
    #  Wat een POST nooit mag doen
    # -----------------------------------------------------------------
    def test_elke_post_antwoordt_met_een_omleiding(self):
        """POST-omleiding-GET. Wie na een boeking op F5 drukt, herhaalt
        de GET en niet de boeking."""
        pid, sku, _ = self.voorraadartikel()
        oid = self.nieuwe_order("SCHERM-5", [{"sku": sku, "besteld": 1}])
        for pad, velden in ((f"/orders/{oid}", {"actie": "reserveer"}),
                            ("/scan", {"actie": "taak", "taak": "VRIJ"}),
                            ("/meten", {"product": pid})):
            with self.subTest(pad=pad):
                r = self.post(pad, **velden)
                self.assertEqual(r.status, 303)
                self.assertTrue(r.naar.startswith("/"))
                self.assertEqual(r.lijf, "")



class TestStijl(unittest.TestCase):
    """Elke klassenaam die de schermen gebruiken, moet in `stijl.css` staan.

    Dit is de test die het vaakst iets vangt en het minst kost. De
    serverschermen lenen het stijlbestand van de browserversie, en een
    naam die daar niet in staat levert geen foutmelding op maar een
    scherm dat er nét naast zit — een knop zonder achtergrond, een
    menu-item dat niet oplicht. Dat zie je pas als je ernaar kijkt, en
    dan is het al een keer aan een klant getoond.

    Draait zonder database en zonder browser.
    """

    @classmethod
    def setUpClass(cls):
        if not STIJL.exists():
            raise unittest.SkipTest("demo/stijl.css ontbreekt")
        cls.css = STIJL.read_text(encoding="utf-8")

    def klassen(self, html: str) -> set[str]:
        namen = set()
        for waarde in re.findall(r'class="([^"]*)"', html):
            namen.update(w for w in waarde.split() if w)
        return namen

    def toets(self, html: str) -> None:
        ontbreekt = sorted(k for k in self.klassen(html)
                           if f".{k}" not in self.css)
        self.assertEqual(ontbreekt, [], f"onbekend in stijl.css: {ontbreekt}")

    def test_het_geraamte(self):
        self.toets(schermen.bladzijde(
            "Proef", "<p>hoi</p>", pad="/taken",
            melding=("fout", "er ging iets mis"),
            tellers={"/taken": 3}))

    def test_de_lege_schermen(self):
        """Ook zonder gegevens moet elke klasse kloppen."""
        for naam, html in (
                ("dashboard", schermen.dashboard({"Open taken": 0}, [])),
                ("taken", schermen.werklijst([])),
                ("orders", schermen.orders([])),
                ("picken", schermen.picken([])),
                ("locaties", schermen.locaties([])),
                ("artikelen", schermen.artikelen([])),
                ("meten", schermen.meetlijst([])),
                ("inslag", schermen.inslag([]))):
            with self.subTest(scherm=naam):
                self.toets(html)

    def test_de_schermen_met_gegevens(self):
        self.toets(schermen.werklijst([
            (1, "MOVE", "Aanvullen", 20, 7, "ART-1", "Een doos", 3, "02-01-1",
             4, "01-01-1", 12, "ordervraag", "onder drempel", None)]))
        self.toets(schermen.orders([
            (1, "ORD-1", "Klant", "WACHT_OP_VOORRAAD", 3, 2)]))
        self.toets(schermen.order(
            (1, "ORD-1", "Klant", "GEPICKT", 1, 2, 34000),
            [("ART-1", "Een doos", 4, 4, 3, 1)],
            [("01-01-1", "ART-1", 4, 3, "MANCO")]))
        self.toets(schermen.locaties([
            ("01-01-1", "Stelling A", "Picklocatie", "S", 400, 300, 200, 1, 12)]))
        self.toets(schermen.artikelen([
            ("ART-1", "Een doos", "Gereedschap", 300, 200, 100, 900, 12,
             "SUPPLIER"),
            ("ART-2", "Nooit gemeten", "Slangen", None, None, None, None, 0,
             None)]))
        self.toets(schermen.meetlijst([
            (1, "ART-1", "Een doos", None, None, "NOOIT_GEMETEN")]))

    def test_het_pickscherm_met_een_regel(self):
        regel = Pickregel(allocation_id=1, order_id=1, ordernummer="ORD-1",
                          prio=1, regel=1, product_id=1, sku="ART-1",
                          oms="Een doos", location_id=1, locatie="01-01-1",
                          zone_id=1, seq=1010010, qty=6, gepickt=2)
        self.toets(schermen.picken([regel]))

    def test_de_scanmodus_in_elke_stap(self):
        """Alle vier de taken, en binnen elke taak elke stap."""
        from vakto.scannen import STAPPEN, TAKEN, Antwoord

        mag = Magazijn(locaties=[], artikelen=[], voorraad=[], soorten={},
                       groepen={})
        for taak in TAKEN:
            scanner = Scanner(mag=mag, taak=taak)
            for stap in STAPPEN[taak] + ("KLAAR",):
                with self.subTest(taak=taak, stap=stap):
                    scanner.stap = stap
                    self.toets(schermen.scanscherm(
                        scanner, Antwoord(stap, "een bericht", "fout")))


if __name__ == "__main__":
    unittest.main()
