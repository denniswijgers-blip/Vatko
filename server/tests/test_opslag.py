"""De vertaallaag tussen database en rekenkern.

Twee soorten test:

  1. Met een NEP-verbinding: controleert dat de rijen goed vertaald
     worden naar de objecten waar de rekenkern mee werkt. Draait altijd.

  2. Tegen een ECHTE database: controleert dat elke query ook klopt met
     het schema. Draait alleen als er een PostgreSQL bereikbaar is; zo
     niet, dan wordt hij overgeslagen in plaats van rood.
"""

import os
import shutil
import subprocess
import unittest

from vakto import Magazijn, voorstel_inslag
from vakto.opslag import QUERIES, Boekfout, boek, laad_magazijn, laad_instellingen


# ---------------------------------------------------------------------
#  1. Nep-verbinding
# ---------------------------------------------------------------------
class NepCursor:
    def __init__(self, antwoorden, log):
        self._antwoorden, self._log, self._rijen = antwoorden, log, []

    def __enter__(self):  return self
    def __exit__(self, *a): return False

    def execute(self, sql, params=()):
        self._log.append((sql.strip(), params))
        naam = next(k for k, v in QUERIES.items() if v.strip() == sql.strip())
        self._rijen = self._antwoorden.get(naam, [])
        if callable(self._rijen):
            self._rijen = self._rijen(params)

    def fetchall(self): return self._rijen
    def fetchone(self):  return self._rijen[0] if self._rijen else None


class NepVerbinding:
    def __init__(self, antwoorden):
        self.antwoorden, self.log = antwoorden, []

    def cursor(self): return NepCursor(self.antwoorden, self.log)


SOORTEN_RIJEN = [
    (0, "PL", "Picklocatie", True,  False, False, False, True),
    (1, "BL", "Bulklocatie", False, True,  False, False, True),
    (3, "QC", "Keuring",     False, False, True,  True,  False),
]
LOCATIE_RIJEN = [
    (1, "01-01-1", 0, 300, 400, 220, 12_000, 1, 1, 1, 1, 1_000_110, True, None),
    (3, "03-01-1", 1, 1200, 800, 1500, 900_000, 1, 3, 1, 1, 1_000_310, True, None),
]
ARTIKEL_RIJEN = [
    (1, "TEST-1", "Testartikel", 1, 120, 90, 45, 180, None, "RECEIPT",
     None, None, True, "8710000000017"),
    (2, "GEEN-MAAT", "Nooit gemeten", 1, None, None, None, None, None, None,
     None, None, True, None),
]


class TestVertaling(unittest.TestCase):

    def magazijn(self) -> Magazijn:
        v = NepVerbinding({
            "locatiesoorten": SOORTEN_RIJEN,
            "locaties": LOCATIE_RIJEN,
            "artikelen": ARTIKEL_RIJEN,
            "voorraad": [(1, 1, 12, 4)],
        })
        return laad_magazijn(v)

    def test_rijen_worden_objecten(self):
        mag = self.magazijn()
        self.assertEqual([l.code for l in mag.locaties], ["01-01-1", "03-01-1"])
        self.assertTrue(mag.soort(mag.locatie(1)).pick)
        self.assertTrue(mag.soort(mag.locatie(3)).bulk)

    def test_actuele_maat_komt_uit_de_view(self):
        """R-AFG-01. De maat hoort bij de meting, niet bij het artikel."""
        mag = self.magazijn()
        self.assertTrue(mag.artikel(1).gemeten)
        self.assertEqual(mag.artikel(1).volume_mm3, 120 * 90 * 45)

    def test_artikel_zonder_meting_is_niet_gemeten(self):
        mag = self.magazijn()
        self.assertFalse(mag.artikel(2).gemeten)
        self.assertEqual(voorstel_inslag(mag, 2, 10), [])

    def test_reservering_komt_mee(self):
        """R-UIT-01. Vrije voorraad is qty - res."""
        mag = self.magazijn()
        rij = mag.voorraad[0]
        self.assertEqual((rij.qty, rij.res, rij.vrij), (12, 4, 8))

    def test_geladen_magazijn_geeft_een_voorstel(self):
        """De hele keten: database -> objecten -> rekenkern."""
        v = voorstel_inslag(self.magazijn(), product_id=1, aantal=40)
        self.assertEqual([x.locatie.code for x in v], ["01-01-1", "03-01-1"])

    def test_boek_geeft_het_journaalnummer(self):
        v = NepVerbinding({"boek": lambda p: [(4711,)]})
        self.assertEqual(boek(v, 1, 10, "RECEIPT", naar=3), 4711)
        sql, params = v.log[0]
        self.assertIn("vakto_boek", sql)
        self.assertEqual(params, (1, 10, "RECEIPT", None, 3, None, None, None))

    def test_boekfout_houdt_de_leesbare_regel_over(self):
        class Stuk(NepVerbinding):
            def cursor(self):
                raise RuntimeError(
                    "Onvoldoende voorraad op bronlocatie 01-01-1 "
                    "(aanwezig 3, gevraagd 10)\nCONTEXT: PL/pgSQL function ...")
        with self.assertRaises(Boekfout) as e:
            boek(Stuk({}), 1, 10, "PICK", van=1)
        self.assertIn("Onvoldoende voorraad", str(e.exception))
        self.assertNotIn("CONTEXT", str(e.exception))

    def test_instellingen_uit_de_database_winnen(self):
        v = NepVerbinding({
            "instellingen": [("putaway.fill_factor", "0.60")],
            "wegingen": [("benutting", 250)],
        })
        inst = laad_instellingen(v)
        self.assertEqual(inst.getal("putaway.fill_factor"), 0.60)
        self.assertEqual(inst.weging["benutting"], 250)
        # Wat niet in de database staat, valt terug op de standaard.
        self.assertEqual(inst.geheel("ui.rows_per_page"), 60)


# ---------------------------------------------------------------------
#  2. Echte database — wordt overgeslagen als er geen is
# ---------------------------------------------------------------------
def psql_beschikbaar() -> str | None:
    exe = os.environ.get("PSQL") or shutil.which("psql")
    if not exe:
        return None
    try:
        r = subprocess.run([*exe.split(), "-d", os.environ.get("PGDATABASE", "vakto"),
                            "-qtAX", "-c", "SELECT 1"],
                           capture_output=True, timeout=10, text=True)
        return exe if r.returncode == 0 else None
    except Exception:
        return None


class TestQueriesTegenHetSchema(unittest.TestCase):
    """Elke query wordt door PostgreSQL zelf nagekeken met PREPARE.

    Dat vangt tikfouten in kolomnamen, verdwenen views en een `boek` die
    het verkeerde aantal parameters meestuurt — precies de fouten die je
    anders pas ziet als er een klant op zit.
    """

    @classmethod
    def setUpClass(cls):
        cls.psql = psql_beschikbaar()
        if not cls.psql:
            raise unittest.SkipTest(
                "Geen bereikbare PostgreSQL. Zet hem op met schema.sql en "
                "boeken.sql, of sla deze tests over — de rest draait gewoon.")

    def test_elke_query_klopt_met_het_schema(self):
        db = os.environ.get("PGDATABASE", "vakto")
        for naam, sql in QUERIES.items():
            with self.subTest(naam):
                # $1..$n in plaats van %s: dat is wat PostgreSQL zelf spreekt.
                n = sql.count("%s")
                voorbereid = sql
                for i in range(1, n + 1):
                    voorbereid = voorbereid.replace("%s", f"${i}", 1)
                r = subprocess.run(
                    [*self.psql.split(), "-d", db, "-qtAX", "-v", "ON_ERROR_STOP=1",
                     "-c", f"PREPARE p_{naam} AS {voorbereid}"],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(r.returncode, 0,
                                 f"query {naam} wordt door PostgreSQL geweigerd:\n"
                                 f"{r.stderr.strip()}")


if __name__ == "__main__":
    unittest.main()
