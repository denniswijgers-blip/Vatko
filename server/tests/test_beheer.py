"""De twee beheerschermen: eigen gegevens en instellingen.

Het importscherm (R-IMP) is het scherm dat het verschil maakt tussen
"kijk eens wat een mooie demo" en "kijk, dit is jouw magazijn". Het
instellingenscherm (R-INST-01) is het antwoord op "ja maar bij ons gaat
dat anders", en de reden dat dat antwoord geen programmeerwerk is.

Wat hier bewezen wordt:

  * een geüpload bestand wordt gelezen, de kolommen herkend en de
    eenheid geraden — en dat alles wordt getóónd voordat er iets gebeurt
  * een verkeerd geraden eenheid is met de hand om te zetten, en het
    voorbeeld laat meteen zien dat het klopt
  * een kolom die verkeerd is geraden is met de hand te kiezen
  * pas op "overnemen" raakt de database iets
  * een instelling die nergens op slaat komt er niet in
  * elke wijziging staat met de oude waarde in het log

Het eerste stuk draait zonder database. De rest heeft PostgreSQL nodig.
"""

import unittest
from pathlib import Path

from vakto import instellingen as inst
from vakto import opslag, schermen, web
from vakto.inlezen import (Eenheden, Standaard, herken_kolommen, lees_inhoud,
                           voorbeeldmaat)

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


# =====================================================================
#  Zonder database
# =====================================================================
class TestMultipart(unittest.TestCase):
    """Een formulier met bestanden erin, zelf ontleed.

    Zelf en niet met `cgi.FieldStorage`: die module is in 3.11 afgekeurd
    en in 3.13 weg, en dan valt de webserver om op een machine waar
    iemand net Python heeft bijgewerkt.
    """

    def maak(self, delen, grens: str = "----X") -> tuple[bytes, str]:
        lijf = b""
        for naam, bestandsnaam, inhoud in delen:
            kop = 'Content-Disposition: form-data; name="' + naam + '"'
            if bestandsnaam is not None:
                kop += '; filename="' + bestandsnaam + '"'
            lijf += (b"--" + grens.encode() + b"\r\n" + kop.encode()
                     + b"\r\n\r\n" + inhoud + b"\r\n")
        lijf += b"--" + grens.encode() + b"--\r\n"
        return lijf, "multipart/form-data; boundary=" + grens

    def test_gewone_velden_en_bestanden_uit_elkaar(self):
        lijf, soort = self.maak([
            ("actie", None, b"overnemen"),
            ("locaties", "loc.csv", b"code;zone\r\n01-01-1;A"),
        ])
        form = web.ontleed_multipart(lijf, soort)
        self.assertEqual(form["actie"], ["overnemen"])
        self.assertEqual(form["bestand.locaties"],
                         [("loc.csv", b"code;zone\r\n01-01-1;A")])
        # Het onderscheid zit in de sleutel, niet in het soort van de
        # waarde: zo kan een aanroeper nooit bytes voor tekst aanzien.
        self.assertNotIn("locaties", form)

    def test_een_windowspad_wordt_teruggebracht_tot_de_naam(self):
        lijf, soort = self.maak([
            ("locaties", r"C:\Users\dennis\Bureaublad\locaties.csv", b"a\r\nb")])
        form = web.ontleed_multipart(lijf, soort)
        self.assertEqual(form["bestand.locaties"][0][0], "locaties.csv")

    def test_bytes_blijven_bytes(self):
        """Een xlsx is een zipbestand. Gaat dat door een decode heen, dan
        is het onbruikbaar en snapt niemand waarom."""
        rommel = bytes(range(256))
        lijf, soort = self.maak([("artikelen", "x.xlsx", rommel)])
        form = web.ontleed_multipart(lijf, soort)
        self.assertEqual(form["bestand.artikelen"][0][1], rommel)

    def test_een_leeg_bestandsveld_levert_lege_inhoud(self):
        """Wie op verzenden drukt zonder een bestand te kiezen, hoort
        geen foutmelding te krijgen."""
        lijf, soort = self.maak([("locaties", "", b"")])
        form = web.ontleed_multipart(lijf, soort)
        # Het blijft een bestandsveld — een leeg bestandsveld — en geen
        # tekstveld met een lege waarde.
        self.assertNotIn("locaties", form)
        self.assertEqual(form["bestand.locaties"], [("", b"")])

    def test_zonder_boundary_is_het_geen_formulier(self):
        with self.assertRaises(ValueError):
            web.ontleed_multipart(b"rommel", "multipart/form-data")


class TestInstellingToetsen(unittest.TestCase):
    """R-INST-01. Bewaren en dan bij de eerstvolgende berekening omvallen
    is het slechtste van twee werelden."""

    def test_elke_instelling_heeft_een_soort(self):
        """Anders glipt er eentje langs de toets zonder dat iemand het
        merkt."""
        self.assertEqual(set(inst.STANDAARD), set(inst.SOORT))

    def test_een_getal_moet_een_getal_zijn(self):
        self.assertIsNone(inst.toets("putaway.fill_factor", "0.85"))
        self.assertIsNotNone(inst.toets("putaway.fill_factor", "veel"))
        self.assertIsNotNone(inst.toets("putaway.fill_factor", ""))

    def test_een_komma_mag_ook(self):
        """Een Nederlander typt 0,85. Daar hoeft niemand over te
        struikelen."""
        self.assertIsNone(inst.toets("putaway.fill_factor", "0,85"))
        self.assertEqual(inst.opgeschoond("putaway.fill_factor", "0,85"),
                         "0.85")

    def test_grenzen(self):
        """Een vulfactor van 3 zegt dat er meer in een vak gaat dan erin
        past. Zulke waarden vallen niet meteen om — ze geven maandenlang
        stilletjes onzin, en dat is erger."""
        self.assertIsNotNone(inst.toets("putaway.fill_factor", "3"))
        self.assertIsNotNone(inst.toets("putaway.fill_factor", "0"))
        self.assertIsNotNone(inst.toets("opt.max_open_teltaken", "0"))
        self.assertIsNone(inst.toets("opt.max_open_teltaken", "12"))

    def test_een_heel_getal_is_een_heel_getal(self):
        self.assertIsNotNone(inst.toets("ui.rows_per_page", "60.5"))
        self.assertIsNone(inst.toets("ui.rows_per_page", "60"))

    def test_ja_of_nee(self):
        for goed in ("true", "false", "TRUE", "False"):
            self.assertIsNone(inst.toets("opt.samenvoegen", goed), goed)
        for fout in ("ja", "1", "aan", ""):
            self.assertIsNotNone(inst.toets("opt.samenvoegen", fout), fout)
        self.assertEqual(inst.opgeschoond("opt.samenvoegen", "TRUE"), "true")

    def test_een_verzonnen_sleutel_wordt_geweigerd(self):
        """Een sleutel die de code niet kent doet niets, en dan zit
        iemand een middag te zoeken waarom zijn instelling geen effect
        heeft."""
        klacht = inst.toets("putaway.fill_factor_nieuw", "1")
        self.assertIsNotNone(klacht)
        self.assertIn("bestaande instelling", klacht)


class TestEenheidVoorbeeld(unittest.TestCase):
    """R-IMP-03. Eén concreet voorbeeld zegt meer dan een keuzelijst."""

    @classmethod
    def setUpClass(cls):
        if not LOCATIES.exists():
            raise unittest.SkipTest("de oefenbestanden ontbreken")
        cls.loc = lees_inhoud(LOCATIES.read_bytes(), LOCATIES.name)
        cls.kol = herken_kolommen("locaties", cls.loc.kop)

    def test_met_de_geraden_eenheid_klopt_het(self):
        v = voorbeeldmaat(self.loc, self.kol, "locaties",
                          Eenheden(loc_maat="cm"))
        self.assertEqual((v.l_mm, v.w_mm, v.h_mm), (300, 400, 220))
        self.assertFalse(v.raar)

    def test_met_de_verkeerde_eenheid_valt_het_meteen_op(self):
        """30 × 40 × 22 mm is geen stellingvak, en dat hoort het scherm
        te zeggen in plaats van het braaf over te nemen."""
        v = voorbeeldmaat(self.loc, self.kol, "locaties",
                          Eenheden(loc_maat="mm"))
        self.assertEqual((v.l_mm, v.w_mm, v.h_mm), (30, 40, 22))
        self.assertTrue(v.raar)

    def test_zonder_bestand_geen_voorbeeld(self):
        self.assertIsNone(voorbeeldmaat(None, {}, "locaties", Eenheden()))
        self.assertIsNone(voorbeeldmaat(self.loc, {}, "locaties", Eenheden()))


# =====================================================================
#  Met database, door de schermen heen
# =====================================================================
@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestBeheerschermen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not psql_beschikbaar():
            raise unittest.SkipTest("Geen bereikbare PostgreSQL.")
        cls.echt = PsqlVerbinding()
        cls.echt.begin()
        cls.v = _Proef(cls.echt)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "echt", None) is not None:
            cls.echt.rollback()
            cls.echt.sluit()

    def setUp(self):
        # Terug naar de lege stand van vóór de vorige test.
        self.v.rollback()
        self.echt.stuur(LEEG)
        # En de instellingen op hun standaardwaarde. Deze tests mogen
        # niet afhangen van wat er toevallig in de database staat —
        # iemand die met de hand een vulfactor heeft omgezet, hoort geen
        # rode tests te krijgen.
        for sleutel, waarde in inst.STANDAARD.items():
            self.echt.stuur(
                f"UPDATE setting SET waarde = '{waarde}' "
                f"WHERE sleutel = '{sleutel}';")
        opslag.bewaar_gebruiker(self.v, "dennis", "Dennis Wijgers", "ADMIN",
                                WACHTWOORD)
        opslag.bewaar_gebruiker(self.v, "kevin", "Kevin Timmermans",
                                "OPERATOR", "nogeenwachtwoord")
        self.v.commit()
        self.standen = web.Standen(klant="Proefklant")
        self.token = self.inloggen("dennis", WACHTWOORD)

    def inloggen(self, naam: str, wachtwoord: str) -> str:
        aan = opslag.meld_aan(self.v, naam, wachtwoord)
        self.assertTrue(aan.gelukt, aan.fout)
        self.v.commit()
        return aan.token

    def haal(self, pad: str, token=None, **vraag):
        return web.behandel(self.v, self.standen, "GET", pad,
                            {k: [str(w)] for k, w in vraag.items()}, {},
                            token=token or self.token)

    def post(self, pad: str, form: dict, token=None):
        return web.behandel(self.v, self.standen, "POST", pad, {}, form,
                            token=token or self.token)

    def rij(self, sql: str):
        with self.v.cursor() as cur:
            cur.execute(sql)
            return cur.fetchone()

    def bestand(self, pad: Path):
        return [(pad.name, pad.read_bytes())]

    # -----------------------------------------------------------------
    #  Instellingen (R-INST-01)
    # -----------------------------------------------------------------
    def test_het_instellingenscherm_toont_alles(self):
        scherm = self.haal("/instellingen")
        self.assertEqual(scherm.status, 200)
        for sleutel in ("putaway.fill_factor", "opt.max_open_teltaken",
                        "sessie.duur_uren"):
            self.assertIn(sleutel, scherm.lijf)
        # Een ja-of-nee hoort een keuzelijst te zijn, geen tekstveld:
        # niemand hoeft te raden of "ja" ook mag.
        self.assertIn('<select name="opt.samenvoegen"', scherm.lijf)
        # En een kommagetal hoort géén type="number" te zijn: dat veld
        # weigert de komma die een Nederlander typt, zonder uit te
        # leggen waarom.
        self.assertIn('name="putaway.fill_factor" value="0.85" '
                      'inputmode="decimal"', scherm.lijf)
        self.assertIn('type="number" step="1" name="ui.rows_per_page"',
                      scherm.lijf)

    def test_een_instelling_wijzigen(self):
        r = self.post("/instellingen", {"putaway.fill_factor": ["0,70"]})
        self.assertEqual(r.status, 303)
        # Een komma wordt een punt, en overbodige nullen gaan eraf:
        # anders staat er na één keer opslaan "0,70" in de tabel en valt
        # float() erover.
        self.assertEqual(self.rij("SELECT waarde FROM setting "
                                  "WHERE sleutel='putaway.fill_factor'")[0],
                         "0.7")
        # R-INST-01: met de oude waarde erbij, en met wie het deed.
        bericht = self.rij("SELECT bericht FROM event_log "
                           "WHERE bron='instellingen' ORDER BY id DESC "
                           "LIMIT 1")[0]
        self.assertIn("0.85", bericht)
        self.assertIn("0.7", bericht)
        self.assertIn("Dennis Wijgers", bericht)

    def test_de_rekenkern_werkt_meteen_met_de_nieuwe_waarde(self):
        """Dit is waar het scherm voor bestaat: geen code aanpassen."""
        self.post("/instellingen", {"putaway.fill_factor": ["0.60"]})
        self.assertEqual(
            opslag.laad_instellingen(self.v).getal("putaway.fill_factor"),
            0.60)

    def test_een_waarde_die_nergens_op_slaat_komt_er_niet_in(self):
        r = self.post("/instellingen", {"putaway.fill_factor": ["3"]})
        self.assertIn("fout=", r.naar)
        self.assertEqual(self.rij("SELECT waarde FROM setting "
                                  "WHERE sleutel='putaway.fill_factor'")[0],
                         "0.85")

    def test_de_rest_van_het_formulier_gaat_gewoon_door(self):
        """Wie één veld verkeerd invult, wil niet dat de andere veertien
        ook terugvallen."""
        r = self.post("/instellingen", {"putaway.fill_factor": ["9"],
                                        "opt.dekking_dagen": ["5"]})
        self.assertIn("fout=", r.naar)
        self.assertEqual(self.rij("SELECT waarde FROM setting "
                                  "WHERE sleutel='opt.dekking_dagen'")[0], "5")

    def test_de_klacht_komt_bij_de_juiste_regel_terecht(self):
        self.post("/instellingen", {"putaway.fill_factor": ["9"]})
        scherm = self.haal("/instellingen",
                           fout="putaway.fill_factor: Dit moet 1 of lager zijn.")
        self.assertIn("Dit moet 1 of lager zijn.", scherm.lijf)

    def test_een_andere_schrijfwijze_is_geen_wijziging(self):
        """`0.20` en `0.2` zijn hetzelfde getal. Wie dat als wijziging
        wegschrijft, krijgt bij elke keer opslaan een logregel voor
        velden die niemand heeft aangeraakt — en dan is het log niets
        meer waard.

        Dit ging één keer mis: het formulier meldde "2 instellingen
        opgeslagen" terwijl er één was aangepast.
        """
        voor = self.rij("SELECT count(*) n FROM event_log "
                        "WHERE bron='instellingen'")[0]
        r = self.post("/instellingen", {"putaway.te_ruim_onder": ["0.2"],
                                        "putaway.fill_factor": ["0.85"]})
        self.assertIn("niets%20veranderd", r.naar.lower())
        self.assertEqual(self.rij("SELECT count(*) n FROM event_log "
                                  "WHERE bron='instellingen'")[0], voor)
        self.assertEqual(self.rij("SELECT waarde FROM setting "
                                  "WHERE sleutel='putaway.te_ruim_onder'")[0],
                         "0.20")

    def test_alleen_wat_echt_wijzigt_wordt_geteld(self):
        r = self.post("/instellingen", {"putaway.te_ruim_onder": ["0.20"],
                                        "putaway.fill_factor": ["0,60"]})
        self.assertIn("1%20instelling", r.naar)

    def test_niets_veranderd_is_geen_wijziging(self):
        """Anders staat het log vol met regels van iemand die op Opslaan
        drukte zonder iets aan te raken, en dan is het log niets waard."""
        voor = self.rij("SELECT count(*) n FROM event_log "
                        "WHERE bron='instellingen'")[0]
        r = self.post("/instellingen", {"putaway.fill_factor": ["0.85"]})
        self.assertIn("niets%20veranderd", r.naar.lower())
        self.assertEqual(self.rij("SELECT count(*) n FROM event_log "
                                  "WHERE bron='instellingen'")[0], voor)

    def test_een_verzonnen_sleutel_wordt_genegeerd(self):
        """Het formulier stuurt alleen bestaande sleutels; wie er zelf
        een verzint, krijgt niets."""
        r = self.post("/instellingen", {"putaway.fill_factor_x": ["1"]})
        self.assertEqual(r.status, 303)
        self.assertEqual(self.rij(
            "SELECT count(*) n FROM setting "
            "WHERE sleutel='putaway.fill_factor_x'")[0], 0)

    def test_alleen_een_beheerder_komt_erbij(self):
        """R-GEB-02. Instellingen zijn rang 3."""
        picker = self.inloggen("kevin", "nogeenwachtwoord")
        self.assertEqual(self.haal("/instellingen", token=picker).status, 403)
        self.assertEqual(
            self.post("/instellingen", {"putaway.fill_factor": ["0.5"]},
                      token=picker).status, 403)
        self.assertEqual(self.rij("SELECT waarde FROM setting "
                                  "WHERE sleutel='putaway.fill_factor'")[0],
                         "0.85")

    # -----------------------------------------------------------------
    #  Eigen gegevens (R-IMP)
    # -----------------------------------------------------------------
    def test_het_lege_importscherm(self):
        scherm = self.haal("/eigen")
        self.assertEqual(scherm.status, 200)
        for woord in ("Locatiebestand", "Artikelbestand", "Voorraadbestand"):
            self.assertIn(woord, scherm.lijf)
        self.assertIn("multipart/form-data", scherm.lijf)

    def test_een_bestand_erin_geeft_meteen_het_rapport(self):
        """R-IMP-05. Het rapport is belangrijker dan de import."""
        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)})
        scherm = self.haal("/eigen").lijf
        self.assertIn("398", scherm)                 # rijen én bruikbaar
        self.assertIn("Locatiecode", scherm)          # de kolomtoewijzing
        self.assertIn("zonder afmetingen", scherm)    # het probleem
        # R-IMP-03: de eenheid is geraden op cm, en dat is te zien.
        self.assertIn("300 × 400 × 220 mm", scherm)
        # En er is nog niets gebeurd.
        self.assertEqual(self.rij("SELECT count(*) n FROM location")[0], 0)

    def test_de_eenheid_is_met_de_hand_om_te_zetten(self):
        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)})
        self.post("/eigen", {"eenheid.loc_maat": ["mm"]})
        scherm = self.haal("/eigen").lijf
        self.assertIn("30 × 40 × 22 mm", scherm)
        self.assertIn("niet te kloppen", scherm)

    def test_een_kolom_is_met_de_hand_te_kiezen(self):
        """R-IMP-02. "We raden het" is een loze belofte als je het niet
        kunt corrigeren."""
        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)})
        stand = self.standen.van(opslag.wie_is(self.v, self.token))
        geraden = dict(stand.imp.kolommen["locaties"])
        self.assertIn("code", geraden)

        # Alles wegzetten behalve de code, en die op een andere kolom.
        self.post("/eigen", {"kolom.locaties.code": ["1"]})
        stand = self.standen.van(opslag.wie_is(self.v, self.token))
        self.assertEqual(stand.imp.kolommen["locaties"], {"code": 1})

    def test_pas_op_overnemen_raakt_de_database_iets(self):
        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES),
                             "bestand.artikelen": self.bestand(ARTIKELEN),
                             "bestand.voorraad": self.bestand(VOORRAAD)})
        self.assertEqual(self.rij("SELECT count(*) n FROM location")[0], 0)

        r = self.post("/eigen", {"actie": ["overnemen"]})
        self.assertEqual(r.status, 303)
        self.assertIn("Overgenomen", r.naar)

        # T-37, maar nu via het scherm.
        self.assertEqual(self.rij("SELECT count(*) n FROM location")[0], 400)
        self.assertEqual(self.rij("SELECT count(*) n FROM product")[0], 900)
        self.assertEqual(self.rij("SELECT count(*) n FROM stock")[0], 759)
        self.assertEqual(self.rij("SELECT count(*) n FROM journal "
                                  "WHERE soort='IMPORT'")[0], 759)
        # R-GEB-06: wie het deed staat erbij.
        self.assertEqual(self.rij("SELECT gebruiker FROM journal "
                                  "ORDER BY id LIMIT 1")[0], "Dennis Wijgers")
        # En de stand is opgeruimd: geen tweede keer overnemen.
        stand = self.standen.van(opslag.wie_is(self.v, self.token))
        self.assertIsNone(stand.imp)

    def test_de_standaardmaat_werkt_door_in_het_rapport(self):
        """R-IMP-05. 53 locaties zonder maat krijgen wat je hier invult."""
        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)})
        self.post("/eigen", {"std.l_mm": ["1200"], "std.w_mm": ["800"],
                             "std.h_mm": ["1500"], "std.max_g": ["900000"]})
        self.post("/eigen", {"actie": ["overnemen"]})
        # Een van de 53 locaties zonder maat in het bestand.
        maat = self.rij("SELECT l_mm, w_mm, h_mm FROM location "
                        "WHERE code='01-01-4'")
        self.assertEqual(maat, (1200, 800, 1500))

    def test_een_import_op_een_draaiend_magazijn_wordt_geweigerd(self):
        """R-IMP-07. Anders overschrijf je een draaiend magazijn met een
        bestand van vorige week, en dat merk je pas als de picker voor
        een leeg vak staat."""
        # Met voorraad erbij, want R-IMP-07 kijkt naar het journaal en
        # dat ontstaat pas als er stuks worden ingeboekt.
        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES),
                             "bestand.artikelen": self.bestand(ARTIKELEN),
                             "bestand.voorraad": self.bestand(VOORRAAD)})
        self.post("/eigen", {"actie": ["overnemen"]})
        self.assertTrue(opslag.al_geboekt(self.v))

        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)})
        scherm = self.haal("/eigen").lijf
        self.assertIn("Er staat al een journaal", scherm)
        self.assertIn("disabled", scherm)

        r = self.post("/eigen", {"actie": ["overnemen"]})
        self.assertIn("s=fout", r.naar)

    def test_een_onleesbaar_bestand_geeft_een_zin_en_geen_stacktrace(self):
        r = self.post("/eigen",
                      {"bestand.locaties": [("oud.xls", b"rommel")]})
        self.assertIn("s=fout", r.naar)
        self.assertIn("xls", r.naar)

    def test_een_bestand_zonder_gegevensregels(self):
        r = self.post("/eigen",
                      {"bestand.locaties": [("leeg.csv", b"code;zone\n")]})
        self.assertIn("s=fout", r.naar)

    def test_alleen_een_beheerder_mag_importeren(self):
        picker = self.inloggen("kevin", "nogeenwachtwoord")
        self.assertEqual(self.haal("/eigen", token=picker).status, 403)
        self.assertEqual(
            self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)},
                      token=picker).status, 403)
        self.assertEqual(self.rij("SELECT count(*) n FROM location")[0], 0)

    def test_twee_beheerders_zitten_elkaar_niet_in_de_weg(self):
        """De importstand hangt aan de sessie, net als de scanstand
        (R-GEB-05)."""
        opslag.bewaar_gebruiker(self.v, "ruben", "Ruben de Groot", "ADMIN",
                                "nogeenwachtwoord")
        self.v.commit()
        ander = self.inloggen("ruben", "nogeenwachtwoord")

        self.post("/eigen", {"bestand.locaties": self.bestand(LOCATIES)})
        self.assertIn("398", self.haal("/eigen").lijf)
        # Ruben heeft nog niets gekozen: geen bestand, geen rapport.
        scherm = self.haal("/eigen", token=ander).lijf
        self.assertNotIn("398", scherm)
        self.assertIn("Kies bestand", scherm)
        self.assertNotIn("Neem deze gegevens over", scherm)


class _Proef:
    """Eén savepunt voor de hele klasse, waar elke test op terugvalt.

    `commit()` doet hier met opzet niets aan de transactie. Anders zou
    elke commit van de router het savepunt vrijgeven en zou de ene test
    de rommel van de vorige zien — en juist die isolatie is hier het
    punt, want deze tests gooien de hele database leeg. Dát een commit
    echt commit staat vast in test_schermen.py en test_toegang.py.
    """

    def __init__(self, echt):
        self.echt = echt
        self.echt.stuur("SAVEPOINT beheer;")

    def cursor(self):
        return self.echt.cursor()

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        self.echt.stuur("ROLLBACK TO SAVEPOINT beheer;")


if __name__ == "__main__":
    unittest.main()
