"""Import van klantbestanden (R-IMP) — hoofdstuk 11.

Twee soorten test in dit bestand:

  1. Kleine gevallen die je in je hoofd kunt houden: een puntkomma tegen
     een komma, "12,5 kg" tegen 12.5, een stellingvak van 40 dat
     centimeters moet zijn. Draaien altijd.

  2. T-34 t/m T-36: de drie ECHTE oefenbestanden uit
     verkoop/voorbeeldbestanden/. Daar zit met opzet van alles fout in.
     De verwachte getallen zijn afgelezen uit de draaiende browserversie
     (demo/test/test-import.mjs), niet bedacht — dat is waar stap 7 op
     afgerekend wordt: dezelfde bestanden horen hetzelfde rapport te
     geven.
"""

import unittest
from pathlib import Path

from vakto.inlezen import (Eenheden, Leesfout, Standaard, controleer, getal,
                           herken_kolommen, lees_bestand, ontbrekende_velden,
                           ontleed_code, plat, raad_eenheden, raad_gewicht,
                           raad_maat, raad_scheiding, soort_naar_type)

HIER = Path(__file__).resolve().parent
VOORBEELDEN = HIER.parent.parent / "verkoop" / "voorbeeldbestanden"
LOCATIES = VOORBEELDEN / "Rommelig - locaties (in cm).csv"
ARTIKELEN = VOORBEELDEN / "Rommelig - artikelen (Engels, xlsx).xlsx"
VOORRAAD = VOORBEELDEN / "Rommelig - voorraad.csv"


def schrijf(tmp: Path, naam: str, inhoud: str) -> Path:
    pad = tmp / naam
    pad.write_text(inhoud, encoding="utf-8")
    return pad


# ---------------------------------------------------------------------
#  R-IMP-04  Een getal uit een cel
# ---------------------------------------------------------------------
class TestGetal(unittest.TestCase):

    def test_gewoon(self):
        self.assertEqual(getal("42"), 42)
        self.assertEqual(getal(42), 42)
        self.assertEqual(getal("42.5"), 42.5)

    def test_nederlandse_komma(self):
        self.assertEqual(getal("12,5"), 12.5)

    def test_duizendtallen(self):
        """De laatste van komma en punt is het decimaalteken."""
        self.assertEqual(getal("1.200,50"), 1200.5)
        self.assertEqual(getal("1,200.50"), 1200.5)

    def test_een_losse_punt_is_een_decimaalteken(self):
        """"1.200" wordt 1,2 en niet 1200. Dat kan ook niet anders: met
        alleen een punt is er geen manier om duizendtallen van decimalen
        te onderscheiden, en de browserversie doet hetzelfde. Wie hier
        struikelt heeft een bestand waar de klant naar moet kijken."""
        self.assertEqual(getal("1.200"), 1.2)

    def test_rommel_eromheen(self):
        self.assertEqual(getal("12,5 kg"), 12.5)
        self.assertEqual(getal("± 300 mm"), 300)
        self.assertEqual(getal("€ 1.250,00"), 1250)

    def test_negatief(self):
        self.assertEqual(getal("-5"), -5)

    def test_leeg_en_onzin(self):
        for waarde in (None, "", "   ", "n.v.t.", "-", "onbekend"):
            self.assertIsNone(getal(waarde), repr(waarde))


# ---------------------------------------------------------------------
#  R-IMP-01  Bestand lezen
# ---------------------------------------------------------------------
class TestScheiding(unittest.TestCase):

    def test_puntkomma_en_komma(self):
        self.assertEqual(raad_scheiding("code;zone;lengte"), ";")
        self.assertEqual(raad_scheiding("code,zone,lengte"), ",")
        self.assertEqual(raad_scheiding("code\tzone\tlengte"), "\t")

    def test_een_komma_in_een_omschrijving_is_geen_kolomgrens(self):
        self.assertEqual(
            raad_scheiding('code;"Bout, verzinkt";lengte'), ";")

    def test_zonder_scheidingsteken_valt_hij_terug_op_de_puntkomma(self):
        self.assertEqual(raad_scheiding("alleenmaartekst"), ";")


class TestLezen(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_csv_met_puntkomma(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv",
                                 "Code;Zone\n01-01-1;Stelling\n01-01-2;Stelling\n"))
        self.assertEqual(b.kop, ["Code", "Zone"])
        self.assertEqual(b.rijen, [["01-01-1", "Stelling"], ["01-01-2", "Stelling"]])

    def test_aanhalingstekens_en_ingesloten_scheidingsteken(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv",
                                 'Code;Oms\n1;"Bout, verzinkt"\n'))
        self.assertEqual(b.rijen, [["1", "Bout, verzinkt"]])

    def test_een_dubbel_aanhalingsteken_binnen_een_veld(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv",
                                 'Code;Oms\n1;"Bout 1/2"" gas"\n'))
        self.assertEqual(b.rijen, [["1", 'Bout 1/2" gas']])

    def test_bom_gaat_eraf(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv", "﻿Code;Zone\n1;A\n"))
        self.assertEqual(b.kop[0], "Code")

    def test_lege_regels_tellen_niet_mee(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv", "Code;Zone\n1;A\n\n;\n2;B\n"))
        self.assertEqual(len(b.rijen), 2)

    def test_een_lege_kop_krijgt_een_naam(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv", "Code;;Zone\n1;x;A\n"))
        self.assertEqual(b.kop, ["Code", "kolom 2", "Zone"])

    def test_korte_rijen_worden_aangevuld(self):
        b = lees_bestand(schrijf(self.tmp, "a.csv", "Code;Zone;Maat\n1;A\n"))
        self.assertEqual(b.rijen, [["1", "A", ""]])

    def test_alleen_een_kopregel_is_geen_bestand(self):
        with self.assertRaises(Leesfout):
            lees_bestand(schrijf(self.tmp, "a.csv", "Code;Zone\n"))

    def test_het_oude_xls_zegt_wat_je_moet_doen(self):
        pad = self.tmp / "a.xls"
        pad.write_bytes(b"\xd0\xcf\x11\xe0")
        with self.assertRaises(Leesfout) as e:
            lees_bestand(pad)
        self.assertIn("sla het op als .xlsx of .csv", str(e.exception))

    def test_een_kapot_xlsx_zegt_wat_je_moet_doen(self):
        pad = self.tmp / "a.xlsx"
        pad.write_bytes(b"dit is geen zip")
        with self.assertRaises(Leesfout) as e:
            lees_bestand(pad)
        self.assertIn("Excel-werkmap", str(e.exception))


# ---------------------------------------------------------------------
#  R-IMP-02  Kolommen herkennen
# ---------------------------------------------------------------------
class TestKolommen(unittest.TestCase):

    def test_plat_slaan(self):
        self.assertEqual(plat("Max belasting (kg)"), "maxbelastingkg")
        self.assertEqual(plat("Vrije hoogte"), "vrijehoogte")

    def test_nederlandse_kopnamen(self):
        k = herken_kolommen("locaties",
                            ["Locatiecode", "Zone", "Soort locatie", "Diepte",
                             "Breedte", "Vrije hoogte", "Max belasting (kg)"])
        self.assertEqual(k, {"code": 0, "zone": 1, "soort": 2, "L": 3,
                             "W": 4, "H": 5, "maxG": 6})

    def test_engelse_kopnamen(self):
        k = herken_kolommen("artikelen",
                            ["Item code", "Description", "Product group",
                             "Length", "Width", "Height", "Weight (g)", "EAN"])
        self.assertEqual(k["sku"], 0)
        self.assertEqual(k["oms"], 1)
        self.assertEqual(k["G"], 6)
        self.assertEqual(k["barcode"], 7)

    def test_elke_kolom_maar_een_keer(self):
        """Zonder die regel komen "Lengte" en "Lengte verpakking" allebei
        op hetzelfde veld terecht en verliest er één stilletjes."""
        k = herken_kolommen("artikelen",
                            ["Artikelnummer", "Lengte", "Lengte verpakking"])
        self.assertEqual(k["L"], 1)
        self.assertEqual(len(set(k.values())), len(k))

    def test_een_exacte_naam_wint_van_een_gedeeltelijke(self):
        k = herken_kolommen("artikelen", ["Artikelgroepcode", "Artikelnummer"])
        self.assertEqual(k["sku"], 1)

    def test_wat_niet_herkend_wordt_blijft_weg(self):
        k = herken_kolommen("locaties", ["Locatiecode", "Kostenplaats"])
        self.assertEqual(k, {"code": 0})

    def test_ontbrekende_verplichte_velden_worden_benoemd(self):
        self.assertEqual(ontbrekende_velden("voorraad", {"sku": 0}),
                         ["Locatiecode", "Aantal"])
        self.assertEqual(
            ontbrekende_velden("voorraad", {"sku": 0, "locatie": 1, "qty": 2}), [])

    def test_dezelfde_kopregel_geeft_altijd_dezelfde_uitkomst(self):
        kop = ["Code", "Lengte", "Breedte", "Hoogte", "Gewicht"]
        self.assertEqual(herken_kolommen("artikelen", kop),
                         herken_kolommen("artikelen", kop))


# ---------------------------------------------------------------------
#  R-IMP-03  Eenheid raden
# ---------------------------------------------------------------------
class TestEenheid(unittest.TestCase):

    def test_een_stellingvak_van_veertig_is_centimeters(self):
        """40 mm diep bestaat niet."""
        self.assertEqual(raad_maat([40, 60, 80, 120], "locaties"), "cm")

    def test_een_artikel_van_veertig_is_millimeters(self):
        self.assertEqual(raad_maat([40, 60, 80, 120], "artikelen"), "mm")

    def test_dat_verschil_is_de_hele_reden_voor_twee_regels(self):
        maten = [40, 60, 80, 120]
        self.assertNotEqual(raad_maat(maten, "locaties"),
                            raad_maat(maten, "artikelen"))

    def test_millimeters_blijven_millimeters(self):
        self.assertEqual(raad_maat([300, 400, 1200], "locaties"), "mm")
        self.assertEqual(raad_maat([500, 900, 1200], "artikelen"), "mm")

    def test_meters(self):
        self.assertEqual(raad_maat([1.2, 0.8, 1.5], "locaties"), "m")
        self.assertEqual(raad_maat([1.2, 0.8, 1.5], "artikelen"), "m")

    def test_zonder_getallen_valt_hij_terug_op_millimeters(self):
        self.assertEqual(raad_maat(["", "n.v.t."], "locaties"), "mm")

    def test_gewicht(self):
        self.assertEqual(raad_gewicht([12, 45, 900], "locaties"), "kg")
        self.assertEqual(raad_gewicht([12000, 45000], "locaties"), "g")
        self.assertEqual(raad_gewicht([180, 240, 3500], "artikelen"), "g")
        self.assertEqual(raad_gewicht([0.2, 1.5, 12], "artikelen"), "kg")


# ---------------------------------------------------------------------
#  R-IMP-06  Looproute uit de locatiecode
# ---------------------------------------------------------------------
class TestOntleedCode(unittest.TestCase):

    def test_streepjes(self):
        p = ontleed_code("01-02-3")
        self.assertEqual((p.gang, p.vak, p.niveau), (1, 2, 3))

    def test_punten_met_een_letter_als_gang(self):
        p = ontleed_code("A.12.4")
        self.assertEqual((p.gang, p.vak, p.niveau), (1, 12, 4))
        self.assertEqual(ontleed_code("B.1.1").gang, 2)

    def test_schuine_strepen(self):
        p = ontleed_code("1/14/2")
        self.assertEqual((p.gang, p.vak, p.niveau), (1, 14, 2))

    def test_meer_dan_drie_delen(self):
        p = ontleed_code("MAG-01-02-3")
        self.assertEqual((p.gang, p.vak, p.niveau), (1, 2, 3))

    def test_wat_niet_te_ontleden_is_volgt_de_volgorde_in_het_bestand(self):
        """Nog altijd beter dan willekeurig."""
        p = ontleed_code("MAGAZIJN", volgnr=41)
        self.assertEqual((p.gang, p.vak, p.niveau), (1, 42, 1))


class TestSoort(unittest.TestCase):

    def test_uit_de_soortkolom(self):
        self.assertEqual(soort_naar_type("Palletstelling", ""), 1)
        self.assertEqual(soort_naar_type("Ontvangst", ""), 2)
        self.assertEqual(soort_naar_type("Keuring", ""), 3)
        self.assertEqual(soort_naar_type("Schade", ""), 4)
        self.assertEqual(soort_naar_type("Expeditie", ""), 5)
        self.assertEqual(soort_naar_type("Legbord", ""), 0)

    def test_ook_uit_de_code(self):
        """Een klant die geen soortkolom levert, verraadt de soort vaak
        in de code: QC-02 is een keuringsvak."""
        self.assertEqual(soort_naar_type("", "QC-02"), 3)
        self.assertEqual(soort_naar_type("", "ONTVANGST"), 2)

    def test_een_afkorting_is_geen_woord(self):
        """EXP-01 wordt géén expeditielocatie. De regel kijkt naar
        woorden, niet naar afkortingen — "expeditie" wel, "exp" niet.
        Anders wordt een vak dat "Expansievaten" heet ineens de
        verzendbalie. Ontbreekt de expeditielocatie daardoor helemaal,
        dan maakt R-IMP-07 er zelf een aan."""
        self.assertEqual(soort_naar_type("", "EXP-01"), 0)
        self.assertEqual(soort_naar_type("Expeditie", "EXP-01"), 5)

    def test_engels_werkt_ook(self):
        self.assertEqual(soort_naar_type("Receiving", ""), 2)
        self.assertEqual(soort_naar_type("Bulk storage", ""), 1)


# ---------------------------------------------------------------------
#  R-IMP-05  Het rapport
# ---------------------------------------------------------------------
class TestRapport(unittest.TestCase):

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _rapport(self, loc_csv, art_csv=None, vrd_csv=None, eenheden=None):
        loc = lees_bestand(schrijf(self.tmp, "l.csv", loc_csv))
        art = lees_bestand(schrijf(self.tmp, "a.csv", art_csv)) if art_csv else None
        vrd = lees_bestand(schrijf(self.tmp, "v.csv", vrd_csv)) if vrd_csv else None
        return controleer(
            loc, herken_kolommen("locaties", loc.kop),
            art, herken_kolommen("artikelen", art.kop) if art else None,
            vrd, herken_kolommen("voorraad", vrd.kop) if vrd else None,
            eenheden or Eenheden())

    def test_een_schone_rij_geeft_geen_problemen(self):
        R = self._rapport("Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n"
                          "01-01-1;300;400;220;12\n")
        self.assertEqual((R.locaties.rijen, R.locaties.goed), (1, 1))
        self.assertEqual(R.problemen, [])
        self.assertTrue(R.klaar)

    def test_de_eenheid_wordt_toegepast(self):
        R = self._rapport("Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n"
                          "01-01-1;30;40;22;12\n",
                          eenheden=Eenheden(loc_maat="cm", loc_gew="kg"))
        regel = R.loc_regels["01-01-1"]
        self.assertEqual((regel.l_mm, regel.w_mm, regel.h_mm), (300, 400, 220))
        self.assertEqual(regel.max_g, 12_000)

    def test_t38_een_dubbele_code_telt_een_keer(self):
        """T-38. De tweede telt niet mee en staat als fout in het rapport."""
        R = self._rapport("Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n"
                          "01-01-1;300;400;220;12\n"
                          "01-01-1;600;400;350;45\n")
        self.assertEqual(R.locaties.goed, 1)
        self.assertEqual(R.loc_regels["01-01-1"].l_mm, 300)   # de eerste
        p = next(x for x in R.problemen if x.sleutel == "dubbel")
        self.assertEqual((p.n, p.ernst), (1, "fout"))

    def test_een_locatie_zonder_maat_krijgt_de_standaard_en_heet_geschat(self):
        R = self._rapport("Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n"
                          "01-01-1;;;;\n")
        regel = R.loc_regels["01-01-1"]
        self.assertEqual((regel.l_mm, regel.w_mm, regel.h_mm),
                         (Standaard().l_mm, Standaard().w_mm, Standaard().h_mm))
        self.assertTrue(regel.geschat)
        self.assertEqual({p.sleutel for p in R.problemen},
                         {"geenmaat", "geengewicht"})
        self.assertTrue(all(p.ernst == "let" for p in R.problemen))

    def test_een_rij_zonder_code_gaat_niet_mee(self):
        R = self._rapport("Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n"
                          ";300;400;220;12\n"
                          "01-01-1;300;400;220;12\n")
        self.assertEqual((R.locaties.rijen, R.locaties.goed), (2, 1))
        self.assertEqual(next(p for p in R.problemen
                              if p.sleutel == "geencode").ernst, "fout")

    def test_een_artikel_zonder_complete_maat_komt_op_de_meetlijst(self):
        R = self._rapport(
            "Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n01-01-1;300;400;220;12\n",
            "Artikelnummer;Lengte;Breedte;Hoogte;Gewicht\n"
            "A-1;120;90;45;180\n"
            "A-2;120;90;;180\n")
        self.assertFalse(R.art_regels["A-2"].gemeten)
        self.assertIsNone(R.art_regels["A-2"].l_mm)
        self.assertTrue(R.art_regels["A-1"].gemeten)
        self.assertEqual(next(p for p in R.problemen
                              if p.sleutel == "nietgemeten").n, 1)

    def test_een_lege_omschrijving_wordt_het_artikelnummer(self):
        R = self._rapport(
            "Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n01-01-1;300;400;220;12\n",
            "Artikelnummer;Omschrijving;Artikelgroep\nA-1;;\n")
        self.assertEqual(R.art_regels["A-1"].oms, "A-1")
        self.assertEqual(R.art_regels["A-1"].groep, "Overig")

    def test_voorraad_op_iets_dat_niet_bestaat_gaat_niet_mee(self):
        R = self._rapport(
            "Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n01-01-1;300;400;220;12\n",
            "Artikelnummer;Lengte;Breedte;Hoogte;Gewicht\nA-1;120;90;45;180\n",
            "Artikelnummer;Locatie;Aantal\n"
            "A-1;01-01-1;10\n"
            "A-9;01-01-1;10\n"
            "A-1;99-99-9;10\n"
            "A-1;01-01-1;0\n")
        self.assertEqual((R.voorraad.rijen, R.voorraad.goed), (4, 1))
        self.assertEqual({p.sleutel: p.n for p in R.voorraad.problemen},
                         {"onbekendart": 1, "onbekendloc": 1, "nul": 1})

    def test_hoogstens_drie_voorbeelden_per_probleem(self):
        rijen = "".join(f"L-{i};;;;\n" for i in range(10))
        R = self._rapport("Locatiecode;Diepte;Breedte;Hoogte;Draagvermogen\n" + rijen)
        p = next(x for x in R.problemen if x.sleutel == "geenmaat")
        self.assertEqual(p.n, 10)
        self.assertEqual(len(p.voorbeeld), 3)

    def test_zonder_locaties_valt_er_niets_over_te_nemen(self):
        R = controleer()
        self.assertFalse(R.klaar)


# ---------------------------------------------------------------------
#  T-34 t/m T-36  De echte oefenbestanden
# ---------------------------------------------------------------------
@unittest.skipUnless(LOCATIES.exists(), "de oefenbestanden ontbreken")
class TestOefenbestanden(unittest.TestCase):
    """Uit demo/test/test-import.mjs, afgelezen uit de browserversie.

    Loopt een van deze tests rood, dan zeggen de twee versies iets anders
    over hetzelfde klantbestand — en dan klopt het rapport niet dat je
    bij een klant op tafel legt.
    """

    @classmethod
    def setUpClass(cls):
        cls.loc = lees_bestand(LOCATIES)
        cls.art = lees_bestand(ARTIKELEN)
        cls.vrd = lees_bestand(VOORRAAD)
        cls.k_loc = herken_kolommen("locaties", cls.loc.kop)
        cls.k_art = herken_kolommen("artikelen", cls.art.kop)
        cls.k_vrd = herken_kolommen("voorraad", cls.vrd.kop)
        cls.eenheden = raad_eenheden(cls.loc, cls.k_loc, cls.art, cls.k_art)
        cls.rapport = controleer(cls.loc, cls.k_loc, cls.art, cls.k_art,
                                 cls.vrd, cls.k_vrd, cls.eenheden)

    def test_t34_locaties(self):
        """CSV met puntkomma, maten in centimeters, 7 van 7 kolommen."""
        self.assertEqual(len(self.loc.rijen), 398)
        self.assertEqual(self.k_loc, {"code": 0, "zone": 1, "soort": 2,
                                      "L": 3, "W": 4, "H": 5, "maxG": 6})
        self.assertEqual(self.eenheden.loc_maat, "cm")
        self.assertEqual(self.eenheden.loc_gew, "kg")
        self.assertEqual((self.rapport.locaties.rijen,
                          self.rapport.locaties.goed), (398, 398))
        tellingen = {p.sleutel: p.n for p in self.rapport.locaties.problemen}
        self.assertEqual(tellingen, {"geenmaat": 53, "geengewicht": 53})

    def test_t35_artikelen(self):
        """Excel met Engelse kopnamen, 9 van de 10 velden herkend."""
        self.assertEqual(len(self.art.rijen), 900)
        self.assertEqual(len(self.k_art), 9)
        self.assertNotIn("max", self.k_art)      # die kolom levert de klant niet
        self.assertEqual(self.eenheden.art_maat, "mm")
        self.assertEqual(self.eenheden.art_gew, "g")
        self.assertEqual((self.rapport.artikelen.rijen,
                          self.rapport.artikelen.goed), (900, 900))
        self.assertEqual({p.sleutel: p.n for p in self.rapport.artikelen.problemen},
                         {"nietgemeten": 167})

    def test_t36_voorraad(self):
        """CSV met komma; drie regels die nergens heen kunnen."""
        self.assertEqual(self.k_vrd, {"sku": 0, "locatie": 1, "qty": 2})
        self.assertEqual((self.rapport.voorraad.rijen,
                          self.rapport.voorraad.goed), (762, 759))
        self.assertEqual({p.sleutel: p.n for p in self.rapport.voorraad.problemen},
                         {"onbekendart": 1, "onbekendloc": 1, "nul": 1})

    def test_de_maten_zijn_omgerekend_naar_millimeters(self):
        """De klant levert centimeters; het systeem rekent in millimeters."""
        eerste = next(iter(self.rapport.loc_regels.values()))
        self.assertGreater(eerste.l_mm, 100)

    def test_het_rapport_is_klaar_om_over_te_nemen(self):
        self.assertTrue(self.rapport.klaar)


if __name__ == "__main__":
    unittest.main()
