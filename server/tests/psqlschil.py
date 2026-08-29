"""Een verbinding die psql aanroept. ALLEEN VOOR TESTS.

Waarom dit bestaat: `opslag.py` werkt met elke DB-API 2.0-driver, en in
de praktijk wordt dat psycopg. Maar de tests van dit project draaien
bewust zonder installatie — `pip install` hoort niet nodig te zijn om te
zien of de rekenkern klopt. Tegelijk wil je van T-16 en T-17 wél weten
dat de héle keten werkt: toestand laden, laten rekenen, wegschrijven.

Dit schilletje overbrugt dat. Het houdt één psql-sessie open, zodat een
test een echte transactie kan beginnen en aan het eind alles kan
terugdraaien. Het is geen driver en zal dat nooit worden: er zit geen
enkele voorziening in voor gelijktijdigheid, prepared statements of
grote resultaten. Voor het echte werk komt psycopg (zie requirements.txt).

Antwoorden komen als JSON terug, zodat getallen getallen blijven en
tijdstippen tijdstippen. Bij `-A -t` zou alles tekst zijn en zou je hier
zitten raden of "12" een aantal of een code is.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime

EINDE = "--EINDE-ANTWOORD--"
TIJDSTIP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def psql_beschikbaar() -> str | None:
    """Het pad naar psql, of None als er geen database bereikbaar is."""
    exe = os.environ.get("PSQL") or shutil.which("psql")
    if not exe:
        return None
    try:
        r = subprocess.run(
            [*exe.split(), "-d", os.environ.get("PGDATABASE", "vakto"),
             "-qtAX", "-c", "SELECT 1"],
            capture_output=True, timeout=10, text=True)
        return exe if r.returncode == 0 else None
    except Exception:
        return None


def _waarde(v) -> str:
    """Eén parameter als SQL-literaal."""
    if v is None:
        return "NULL"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, datetime):
        return "'" + v.isoformat() + "'::timestamptz"
    return "'" + str(v).replace("'", "''") + "'"


def _vul_in(sql: str, params) -> str:
    for p in params or ():
        sql = sql.replace("%s", _waarde(p), 1)
    return sql


def _terug(waarde):
    """Zet ISO-tijdstippen terug om; de rest laat json al goed staan."""
    if isinstance(waarde, str) and TIJDSTIP.match(waarde):
        try:
            return datetime.fromisoformat(waarde)
        except ValueError:
            return waarde
    return waarde


class Psqlfout(Exception):
    """psql gaf een foutmelding terug. De tekst is die van PostgreSQL."""


class PsqlCursor:
    def __init__(self, verbinding):
        self._v = verbinding
        self._rijen: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql: str, params=()) -> None:
        vol = _vul_in(sql, params).strip().rstrip(";")
        antwoord = self._v.stuur(
            f"SELECT coalesce(json_agg(x)::text, '[]') FROM ({vol}) x;")
        rijen = json.loads(antwoord) if antwoord else []
        # json_agg geeft objecten; de sleutelvolgorde is de kolomvolgorde
        # van de query en die houdt json vast. Alle queries in QUERIES
        # hebben unieke kolomnamen, dus dat komt goed.
        self._rijen = [tuple(_terug(v) for v in r.values()) for r in rijen]

    def fetchall(self) -> list[tuple]:
        return self._rijen

    def fetchone(self):
        return self._rijen[0] if self._rijen else None


class PsqlVerbinding:
    """Eén open psql-sessie, zodat BEGIN en ROLLBACK werken."""

    def __init__(self, psql: str | None = None, db: str | None = None):
        psql = psql or psql_beschikbaar()
        if not psql:
            raise Psqlfout("Geen bereikbare PostgreSQL")
        db = db or os.environ.get("PGDATABASE", "vakto")
        self._p = subprocess.Popen(
            [*psql.split(), "-d", db, "-qtAX", "-v", "ON_ERROR_STOP=0"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1)

    def stuur(self, sql: str) -> str:
        self._p.stdin.write(sql + f"\n\\echo {EINDE}\n")
        self._p.stdin.flush()
        regels = []
        while True:
            regel = self._p.stdout.readline()
            if not regel:
                raise Psqlfout("psql is er onderuit gegaan:\n"
                               + "".join(regels))
            if regel.strip() == EINDE:
                break
            regels.append(regel)
        uit = "".join(regels).strip()
        if "ERROR:" in uit:
            eerste = next(r for r in uit.splitlines() if "ERROR:" in r)
            raise Psqlfout(eerste.split("ERROR:", 1)[1].strip())
        return uit

    def cursor(self) -> PsqlCursor:
        return PsqlCursor(self)

    def begin(self) -> None:
        self.stuur("BEGIN;")

    def rollback(self) -> None:
        self.stuur("ROLLBACK;")

    def sluit(self) -> None:
        try:
            self._p.stdin.write("\\q\n")
            self._p.stdin.flush()
        except Exception:
            pass
        try:
            self._p.wait(timeout=10)
        finally:
            for pijp in (self._p.stdin, self._p.stdout):
                try:
                    pijp.close()
                except Exception:
                    pass
