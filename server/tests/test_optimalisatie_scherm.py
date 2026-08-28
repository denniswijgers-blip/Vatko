"""De twee schermen die overbleven: optimalisatie en etiketten.

Het optimalisatiescherm (R-OPT) toont wat het systeem zelf gevonden
heeft, plus de twee dingen waar het een oordeel van een mens voor nodig
heeft: een aanvuldrempel bijstellen (R-OPT-05) en een picklocatie
inrichten (R-OPT-06). Dat zijn besluiten over werkkapitaal en ruimte, en
die horen niet vanzelf te gaan.

Het etikettenscherm (R-SCAN-08) drukt de labels af waar de hele
scanmodus op steunt. De codering zelf staat in test_etiketten.py; hier
gaat het om wat er op het etiket komt en wie erbij mag.

Draait alleen als er een PostgreSQL bereikbaar is.
"""

import json
import unittest
from pathlib import Path

from vakto import opslag, schermen, web

from .psqlschil import PsqlVerbinding, psql_beschikbaar

VOORBEELDEN = (Path(__file__).resolve().parent.parent.parent
               / "verkoop" / "voorbeeldbestanden")
LOCATIES = VOORBEELDEN / "Rommelig - locaties (in cm).csv"
ARTIKELEN = VOORBEELDEN / "Rommelig - artikelen (Engels, xlsx).xlsx"
VOORRAAD = VOORBEELDEN / "Rommelig - voorraad.csv"

WACHTWOORD = "proefwachtwoord"
LEEG = ("TRUNCATE journal, stock, measurement, allocation, order_line, "
        "customer_order, task, alert, event_log, product, product_group, "
        "location, zone, app_user CASCADE;")


@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestOptimalisatiescherm(unittest.TestCase):

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
        for naam, volledig, rol in (("dennis", "Dennis Wijgers", "ADMIN"),
                                    ("ruben", "Ruben de Groot", "SUPERVISOR"),
                                    ("kevin", "Kevin Timmermans", "OPERATOR")):
            opslag.bewaar_gebruiker(cls.echt, naam, volledig, rol, WACHTWOORD)
        # Het savepunt komt ná de vaste gegevens, zodat elke test daarop
        # terugvalt en niet de picks van de vorige ziet.
        cls.v = _Proef(cls.echt)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "echt", None) is not None:
            cls.echt.rollback()
            cls.echt.sluit()

    def setUp(self):
        self.v.rollback()
        self.standen = web.Standen(klant="Proefklant")
        self.tokens = {}

    def token(self, naam: str = "dennis") -> str:
        if naam not in self.tokens:
            aan = opslag.meld_aan(self.v, naam, WACHTWOORD)
            self.assertTrue(aan.gelukt, aan.fout)
            self.v.commit()
            self.tokens[naam] = aan.token
        return self.tokens[naam]

    def haal(self, pad: str, naam: str = "dennis", **vraag):
        return web.behandel(self.v, self.standen, "GET", pad,
                            {k: [str(w)] for k, w in vraag.items()}, {},
                            token=self.token(naam))

    def post(self, pad: str, naam: str = "dennis", **velden):
        return web.behandel(self.v, self.standen, "POST", pad, {},
                            {k: [str(w)] for k, w in velden.items()},
                            token=self.token(naam))

    def rij(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()

    def op_picklocatie(self):
        """Een artikel dat op een picklocatie ligt, met zijn vak erbij."""
        rij = self.rij("""
            SELECT s.product_id, s.location_id, p.sku
              FROM stock s
              JOIN product p ON p.id = s.product_id
              JOIN location l ON l.id = s.location_id
              JOIN location_type t ON t.id = l.type_id
             WHERE t.pick AND s.qty > 0 AND s.res = 0
             ORDER BY s.product_id LIMIT 1
        """)
        if rij is None:
            self.skipTest("geen artikel op een picklocatie")
        return rij

    def verbruik(self, pid: int, loc: int, per_dag: int,
                 dagen: int = 20) -> int:
        """Zet picks in het journaal, zodat er iets te adviseren valt.

        R-OPT-02 rekent de vraagsnelheid uit het journaal en niet uit een
        veld dat iemand ooit heeft ingevuld — dus moet een test die over
        snelheid gaat ook echt picks maken.
        """
        # Ruim bijboeken, anders is het vak leeg voordat we klaar zijn.
        opslag.boek(self.v, pid, per_dag * dagen * 2, "RECEIPT", naar=loc)
        # Rechtstreeks in het journaal, en niet via vakto_boek(): die zet
        # `at` op now() en dan liggen alle picks op dezelfde dag. R-OPT-02
        # meet over een venster, dus ze moeten uit elkaar liggen.
        self.echt.stuur(
            f"INSERT INTO journal (at, soort, product_id, van, qty, reden, ref)"
            f" SELECT now() - g * interval '1 day', 'PICK', {pid}, {loc},"
            f" {per_dag}, 'proef', 'T-OPT'"
            f" FROM generate_series(0, {dagen - 1}) g;")
        self.v.commit()
        return pid

    # -----------------------------------------------------------------
    #  Het scherm
    # -----------------------------------------------------------------
    def test_het_scherm_komt_in_beeld(self):
        r = self.haal("/optimalisatie")
        self.assertEqual(r.status, 200)
        for kop in ("Voorraad samenvoegen", "Hardlopers",
                    "Waarom er wordt aangevuld", "Telplan",
                    "Aanvuldrempels die niet meer kloppen"):
            self.assertIn(kop, r.lijf)

    def test_de_vier_tegels_tellen_het_open_werk(self):
        opslag.draai_zelfcontrole(self.v)
        self.v.commit()
        taken = opslag.laad_taken(self.v)
        tel = len([t for t in taken if t.soort == "CYCLE_COUNT"
                   and t.aanleiding == "telinterval"])
        r = self.haal("/optimalisatie")
        self.assertIn("Te tellen locaties", r.lijf)
        self.assertIn(f'<span class="cijfer">{tel}</span>', r.lijf)

    def test_een_hardloper_verschijnt_met_zijn_snelheid(self):
        """R-OPT-02. Uit het journaal, niet uit een veld.

        En over het hele venster gedeeld, niet over de dagen waarop er
        toevallig gepickt is: 12 st per dag gedurende 20 dagen is over
        een venster van 30 dagen 8 st per dag. Dat is de bedoeling — een
        artikel dat drie weken stilligt en dan één dag hard gaat, is geen
        hardloper.
        """
        pid, loc, sku = self.op_picklocatie()
        self.verbruik(pid, loc, per_dag=12, dagen=20)
        inst = opslag.laad_instellingen(self.v)
        verwacht = 12 * 20 / inst.getal("opt.venster_dagen")
        r = self.haal("/optimalisatie")
        self.assertIn(sku, r.lijf)
        self.assertIn(f"{verwacht:.1f}", r.lijf)

    def test_een_medewerker_komt_er_niet_bij(self):
        """R-GEB-02. Optimalisatie is rang 2."""
        self.assertEqual(self.haal("/optimalisatie", "kevin").status, 403)
        self.assertEqual(self.haal("/optimalisatie", "ruben").status, 200)
        self.assertEqual(
            self.post("/optimalisatie", "kevin", actie="negeer",
                      product=1).status, 403)

    # -----------------------------------------------------------------
    #  R-OPT-05  Het drempeladvies
    # -----------------------------------------------------------------
    def klaar_voor_advies(self) -> tuple[int, str]:
        """Een artikel met een drempel die niet meer klopt."""
        pid, loc, sku = self.op_picklocatie()
        self.verbruik(pid, loc, per_dag=20)
        # Drempel op 1: met 20 st/dag en 3 dagen dekking zou hij 60 zijn.
        opslag.zet_drempel(self.v, pid, 1, 4)
        self.v.commit()
        return pid, sku

    def test_een_advies_verschijnt_met_beide_knoppen(self):
        pid, sku = self.klaar_voor_advies()
        adviezen, _, _ = opslag.laad_adviezen(self.v)
        self.assertTrue(any(a.product_id == pid for a in adviezen))
        r = self.haal("/optimalisatie")
        self.assertIn("Overnemen", r.lijf)
        self.assertIn("Laten", r.lijf)
        self.assertIn("te laag — misgrijpen", r.lijf)

    def test_het_advies_overnemen_zet_de_drempel(self):
        pid, sku = self.klaar_voor_advies()
        advies = next(a for a in opslag.laad_adviezen(self.v)[0]
                      if a.product_id == pid)
        r = self.post("/optimalisatie", actie="drempel", product=pid,
                      min=advies.zou, max=advies.max_zou)
        self.assertEqual(r.status, 303)
        self.assertEqual(self.rij(
            f"SELECT min_qty, max_qty FROM product WHERE id={pid}"),
            (advies.zou, advies.max_zou))
        # R-GEB-06: met de oude waarde en wie het deed in het log.
        bericht = self.rij("SELECT bericht FROM event_log WHERE bron='advies' "
                           "ORDER BY id DESC LIMIT 1")[0]
        self.assertIn(sku, bericht)
        self.assertIn("Dennis Wijgers", bericht)
        # En het advies is weg, want de drempel klopt nu.
        self.assertFalse(any(a.product_id == pid
                             for a in opslag.laad_adviezen(self.v)[0]))

    def test_het_advies_laten_haalt_het_artikel_van_de_lijst(self):
        """Dat is de menselijke keuze uit R-OPT-05: iemand vindt de
        drempel goed zoals hij is, en dan hoort het systeem er niet elke
        week opnieuw over te beginnen."""
        pid, sku = self.klaar_voor_advies()
        was = self.rij(f"SELECT min_qty FROM product WHERE id={pid}")[0]

        r = self.post("/optimalisatie", actie="negeer", product=pid)
        self.assertEqual(r.status, 303)
        self.assertTrue(self.rij(
            f"SELECT drempel_akkoord FROM product WHERE id={pid}")[0])
        # De drempel zelf blijft staan.
        self.assertEqual(self.rij(
            f"SELECT min_qty FROM product WHERE id={pid}")[0], was)
        self.assertFalse(any(a.product_id == pid
                             for a in opslag.laad_adviezen(self.v)[0]))

    def test_een_nieuwe_drempel_zet_het_akkoord_weer_uit(self):
        """Vanaf dan mag het systeem er opnieuw iets van vinden."""
        pid, _ = self.klaar_voor_advies()
        opslag.zet_drempel(self.v, pid, akkoord=True)
        opslag.zet_drempel(self.v, pid, 60, 180)
        self.v.commit()
        self.assertFalse(self.rij(
            f"SELECT drempel_akkoord FROM product WHERE id={pid}")[0])

    # -----------------------------------------------------------------
    #  R-OPT-06  De picklocatie
    # -----------------------------------------------------------------
    def bulkhardloper(self):
        """Een artikel dat hard gaat en alleen in bulk ligt.

        Zelf gemaakt en niet uit het oefenbestand gevist: R-OPT-06 gaat
        precies over dit geval, en een test die zichzelf overslaat omdat
        het toevallig niet voorkomt bewijst niets.
        """
        rij = self.rij("""
            SELECT s.product_id, s.location_id, p.sku
              FROM stock s
              JOIN product p ON p.id = s.product_id
              JOIN location l ON l.id = s.location_id
              JOIN location_type t ON t.id = l.type_id
              JOIN v_product_current c ON c.product_id = p.id
             WHERE t.bulk AND s.qty > 40 AND s.res = 0
               AND NOT EXISTS (
                     SELECT 1 FROM stock s2
                       JOIN location l2 ON l2.id = s2.location_id
                       JOIN location_type t2 ON t2.id = l2.type_id
                      WHERE s2.product_id = s.product_id AND s2.qty > 0
                        AND t2.pick)
             ORDER BY s.qty DESC LIMIT 1
        """)
        if rij is None:
            self.skipTest("geen artikel dat alleen in bulk ligt")
        pid, loc, sku = rij
        self.verbruik(pid, loc, per_dag=15)
        return pid, loc, sku

    def test_een_pickplekvoorstel_wordt_een_taak_en_niets_meer(self):
        """Er moet iemand met een pallettruck naartoe; het systeem boekt
        hier niet zelf."""
        pid, _, _ = self.bulkhardloper()
        _, plekken, _ = opslag.laad_adviezen(self.v)
        voorstel = next((v for v in plekken if v.product_id == pid), None)
        self.assertIsNotNone(voorstel, "R-OPT-06 had hier een voorstel moeten "
                                       "doen")
        voorraad_voor = self.rij(
            f"SELECT qty FROM stock WHERE product_id={voorstel.product_id} "
            f"AND location_id={voorstel.van}")[0]

        r = self.post("/optimalisatie", actie="pickplek",
                      product=voorstel.product_id)
        self.assertEqual(r.status, 303)
        self.assertIn("Taak%20klaargezet", r.naar)

        taak = self.rij("SELECT soort, status, van, naar, qty, automatisch "
                        "FROM task WHERE soort='PICKPLEK' "
                        "ORDER BY id DESC LIMIT 1")
        self.assertEqual(taak[:2], ("PICKPLEK", "TODO"))
        self.assertEqual((taak[2], taak[3], taak[4]),
                         (voorstel.van, voorstel.naar, voorstel.qty))
        self.assertFalse(taak[5], "dit is geen automatische taak")

        # Er is niets verplaatst.
        self.assertEqual(self.rij(
            f"SELECT qty FROM stock WHERE product_id={voorstel.product_id} "
            f"AND location_id={voorstel.van}")[0], voorraad_voor)

    def test_hetzelfde_voorstel_komt_niet_twee_keer(self):
        pid, _, _ = self.bulkhardloper()
        self.assertTrue(any(v.product_id == pid
                            for v in opslag.laad_adviezen(self.v)[1]))
        self.post("/optimalisatie", actie="pickplek", product=pid)
        _, opnieuw, _ = opslag.laad_adviezen(self.v)
        self.assertFalse(any(v.product_id == pid for v in opnieuw))

    def test_een_voorstel_dat_niet_meer_geldt(self):
        """De voorraad kan inmiddels veranderd zijn. Dan hoort er een
        nette zin te komen en geen stacktrace."""
        pid = self.rij("SELECT id FROM product ORDER BY id DESC LIMIT 1")[0]
        r = self.post("/optimalisatie", actie="pickplek", product=pid)
        self.assertIn("geldt%20niet%20meer", r.naar)

    # -----------------------------------------------------------------
    #  Etiketten (R-SCAN-08)
    # -----------------------------------------------------------------
    def test_het_etikettenscherm(self):
        r = self.haal("/etiketten")
        self.assertEqual(r.status, 200)
        code = self.rij("SELECT l.code FROM location l "
                        "JOIN location_type t ON t.id = l.type_id "
                        "WHERE l.actief AND t.doel ORDER BY l.seq LIMIT 1")[0]
        self.assertIn(code, r.lijf)
        self.assertIn('<svg class="c39"', r.lijf)
        # Naast de code ook de maatklasse en de binnenmaat: wie plakt
        # ziet dan meteen of hij bij het goede vak staat.
        self.assertIn("mm · max", r.lijf)

    def test_alleen_locaties_waar_iets_mag_liggen(self):
        """Een etiket op een doorloopplek zet mensen op het verkeerde
        been."""
        alles = self.rij("SELECT count(*) n FROM location WHERE actief")[0]
        doel = opslag.etikettenaantal(self.v)
        self.assertLess(doel, alles)
        expeditie = self.rij(
            "SELECT l.code FROM location l JOIN location_type t "
            "ON t.id = l.type_id WHERE NOT t.doel LIMIT 1")
        if expeditie:
            self.assertNotIn(expeditie[0], self.haal("/etiketten").lijf)

    def test_bladeren(self):
        """R-BASIS-07: nooit alles tegelijk. Vierhonderd etiketten in één
        pagina is een pagina die niemand afdrukt."""
        eerste = self.haal("/etiketten").lijf
        tweede = self.haal("/etiketten", vanaf=60).lijf
        self.assertIn("Volgende", eerste)
        self.assertIn("Vorige", tweede)
        self.assertNotEqual(eerste, tweede)

    def test_een_medewerker_komt_er_niet_bij(self):
        self.assertEqual(self.haal("/etiketten", "kevin").status, 403)
        self.assertEqual(self.haal("/etiketten", "ruben").status, 200)


class _Proef:
    """Eén savepunt voor de hele klasse, waar elke test op terugvalt.

    `commit()` doet hier met opzet niets: anders zou elke commit van de
    router het savepunt vrijgeven en zou de ene test de picks van de
    vorige zien — en dan hangt de uitkomst af van de volgorde waarin ze
    draaien. Dát een commit echt commit staat vast in test_schermen.py.
    """

    def __init__(self, echt):
        self.echt = echt
        self.echt.stuur("SAVEPOINT opt;")

    def cursor(self):
        return self.echt.cursor()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        self.echt.stuur("ROLLBACK TO SAVEPOINT opt;")


if __name__ == "__main__":
    unittest.main()
