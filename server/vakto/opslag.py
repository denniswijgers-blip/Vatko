"""De vertaallaag tussen PostgreSQL en de rekenkern.

Dit is het enige bestand dat van een database weet. De rekenkern in
`passen.py` en `voorstel.py` blijft er onwetend van, en dat moet zo
blijven: verandert het schema, dan verandert alleen dit bestand mee.

Werkt met elke DB-API 2.0-driver. In de praktijk psycopg 3:

    import psycopg
    from vakto.opslag import boek, laad_magazijn

    with psycopg.connect("dbname=vakto") as conn:
        magazijn = laad_magazijn(conn)
        boek(conn, product_id=1, aantal=10, soort="RECEIPT", naar=42)

Boeken doet de database zelf, via de functie `vakto_boek` uit
boeken.sql. Dat is geen luiheid maar R-BASIS-01: zet je die logica in
Python, dan geldt hij alleen zolang iedereen die route gebruikt.
"""

from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Any, Protocol

from datetime import datetime

from .modellen import (Artikel, Artikelgroep, Locatie, LocatieSoort, Magazijn,
                       Taak, Voorraadregel)
from .meten import Melding
from .optimalisatie import Pick
from .uitgaand import Inpak, Order, Orderregel, Pickregel
from .zelfcontrole import Uitkomst
from . import gebruikers as _gebruikers
from . import inlezen as _inlezen
from . import meten as _meten
from . import uitgaand as _uitgaand
from . import zelfcontrole as _zelfcontrole


class Boekfout(Exception):
    """De database weigerde de boeking. De tekst is bedoeld om te tonen."""


class Verbinding(Protocol):          # pragma: no cover - alleen voor typen
    def cursor(self) -> Any: ...


# ---------------------------------------------------------------------
#  De queries staan hier bij elkaar, met een naam. Zo kan een test ze
#  stuk voor stuk langs de echte database halen (tests/test_opslag.py).
# ---------------------------------------------------------------------
QUERIES: dict[str, str] = {

    "locatiesoorten": """
        SELECT id, code, naam, pick, bulk, mix, blok, doel
          FROM location_type
         ORDER BY id
    """,

    "locaties": """
        SELECT l.id, l.code, l.type_id, l.l_mm, l.w_mm, l.h_mm, l.max_g,
               l.zone_id, l.aisle, l.bay, l.level, l.seq, l.actief, l.geteld_op
          FROM location l
         WHERE l.actief
         ORDER BY l.seq, l.id
    """,

    # R-AFG-01: de actuele maat komt uit de view, niet uit product.
    "artikelen": """
        SELECT p.id, p.sku, p.oms, p.group_id,
               c.l_mm, c.w_mm, c.h_mm, c.g, c.gemeten_op, c.bron,
               p.min_qty, p.max_qty, p.stapelbaar, p.barcode,
               p.drempel_akkoord
          FROM product p
          LEFT JOIN v_product_current c ON c.product_id = p.id
         ORDER BY p.id
    """,

    # Alleen het telplan heeft ze nodig (R-OPT-04).
    "artikelgroepen": """
        SELECT id, naam, telinterval FROM product_group ORDER BY id
    """,

    "voorraad": """
        SELECT product_id, location_id, qty, res
          FROM stock
         WHERE qty > 0
    """,

    "instellingen": """
        SELECT sleutel, waarde FROM setting
    """,

    "wegingen": """
        SELECT sleutel, punten FROM weging
    """,

    "boek": """
        SELECT vakto_boek(%s, %s, %s, %s, %s, %s, %s, %s)
    """,

    # R-MEET-01 t/m R-MEET-03. Meting en melding in één transactie,
    # zie meten.sql. De percentages en de gevolg-tekst rekent Python uit.
    "meting": """
        SELECT meting_id, melding_id
          FROM vakto_meting(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,

    "melding_sluiten": """
        SELECT vakto_melding_sluiten(%s, %s)
    """,

    # R-ZC-01. Alleen de gevolg-tekst; de percentages horen bij de meting.
    "melding_bijwerken": """
        SELECT vakto_melding_bijwerken(%s, %s)
    """,

    "open_meldingen": """
        SELECT id, product_id, at, d_vol, d_gew, gevolg
          FROM alert
         WHERE status = 'OPEN'
         ORDER BY at, id
    """,

    # R-MEET-04. De view doet de sortering; zie meten.sql.
    "te_meten": """
        SELECT product_id, sku, oms, gemeten_op, bron, reden
          FROM v_te_meten
         LIMIT %s
    """,

    # De hele tijdlijn van één artikel, nieuwste eerst.
    "metingen_van": """
        SELECT id, at, bron, l_mm, w_mm, h_mm, g, notitie
          FROM measurement
         WHERE product_id = %s
         ORDER BY at DESC, id DESC
    """,

    # ---------------------------------------------------------------
    #  Uitgaand (R-UIT). De vier functies staan in uitgaand.sql; hier
    #  worden ze alleen aangeroepen. Rekenen gebeurt niet in een query.
    # ---------------------------------------------------------------
    "reserveer": """
        SELECT vakto_reserveer(%s, %s)
    """,

    "geef_vrij": """
        SELECT vakto_geef_vrij(%s)
    """,

    "pick": """
        SELECT vakto_pick(%s, %s, %s, %s)
    """,

    "pak_in": """
        SELECT vakto_pak_in(%s, %s, %s)
    """,

    "verzend": """
        SELECT vakto_verzend(%s, %s)
    """,

    "order": """
        SELECT id, nummer, klant, plaats, land, vervoerder, soort, prio,
               status, at, colli, gewicht_g, track
          FROM customer_order
         WHERE id = %s
    """,

    "orderregels": """
        SELECT idx, product_id, besteld, gereserveerd, gepickt, manco
          FROM order_line
         WHERE order_id = %s
         ORDER BY idx
    """,

    # R-UIT-03. De view sorteert op looproute; R-BASIS-07 wil een limiet.
    "picklijst": """
        SELECT allocation_id, order_id, ordernummer, prio, regel, product_id,
               sku, oms, location_id, locatie, zone_id, seq, qty, gepickt
          FROM v_picklijst
         LIMIT %s
    """,

    "picklijst_order": """
        SELECT allocation_id, order_id, ordernummer, prio, regel, product_id,
               sku, oms, location_id, locatie, zone_id, seq, qty, gepickt
          FROM v_picklijst
         WHERE order_id = %s
         LIMIT %s
    """,

    # ---------------------------------------------------------------
    #  Zelfcontrole en optimalisatie (R-ZC, R-OPT). Het rekenwerk staat
    #  in zelfcontrole.py en optimalisatie.py; dit haalt de toestand op
    #  en schrijft de uitkomst weg.
    # ---------------------------------------------------------------
    "open_taken": """
        SELECT id, soort, naam, prio, status, product_id, van, naar, qty,
               aanleiding, reden, automatisch, at
          FROM task
         WHERE status = 'TODO'
         ORDER BY prio, id
    """,

    "ordervraag": """
        SELECT product_id, open_vraag FROM v_ordervraag
    """,

    # R-OPT-02. Alleen PICK-regels binnen het venster; de rekenkern telt
    # ze op tot stuks per dag.
    "picks": """
        SELECT product_id, qty, at
          FROM journal
         WHERE soort = 'PICK'
           AND at >= now() - (%s || ' days')::interval
    """,

    "taak": """
        SELECT vakto_taak(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """,

    "taak_bijwerken": """
        SELECT vakto_taak_bijwerken(%s, %s, %s, %s, %s)
    """,

    "taak_vervallen": """
        SELECT vakto_taak_vervallen(%s, %s)
    """,

    "taak_uitvoeren": """
        SELECT vakto_taak_uitvoeren(%s, %s, %s)
    """,

    "tellen": """
        SELECT vakto_tellen(%s, %s, %s, %s, %s, %s)
    """,

    "log": """
        SELECT vakto_log(%s, %s, %s, %s)
    """,

    # R-IMP-07. Het hele rapport in één aanroep: alles of niets.
    "import": """
        SELECT vakto_import(%s::jsonb, %s::jsonb, %s::jsonb, %s)
    """,

    # R-BASIS-07. Nooit een lijst zonder limiet.
    "werklijst": """
        SELECT id, soort, naam, prio, product_id, sku, oms,
               van, van_code, naar, naar_code, qty, aanleiding, reden, at
          FROM v_werklijst
         LIMIT %s
    """,

    # De regel waar de picker nu voor staat, met wat hij moet weten om
    # een manco te kunnen samenstellen.
    "pickregel": """
        SELECT a.id, a.order_id, o.nummer, a.regel, a.product_id, p.sku,
               a.location_id, l.code, a.qty, a.gepickt, a.status
          FROM allocation a
          JOIN customer_order o ON o.id = a.order_id
          JOIN location       l ON l.id = a.location_id
          JOIN product        p ON p.id = a.product_id
         WHERE a.id = %s
    """,

    # ---------------------------------------------------------------
    #  De schermen (stap 8)
    #
    #  Ook deze queries staan hier en niet in web.py. Een webserver die
    #  zelf SQL schrijft is een webserver die je bij elke schemawijziging
    #  moet doorlezen; nu staat alles wat de database kent op één plek.
    #  Ze halen alleen op — boeken gebeurt via de functies hierboven.
    # ---------------------------------------------------------------
    "cijfers": """
        SELECT (SELECT count(*) FROM task WHERE status = 'TODO') AS taken,
               (SELECT count(*) FROM alert WHERE status = 'OPEN') AS meldingen,
               (SELECT count(*) FROM customer_order
                 WHERE status <> 'VERZONDEN')                     AS orders,
               (SELECT count(*) FROM allocation
                 WHERE status = 'TODO')                           AS pickregels,
               (SELECT count(*) FROM v_te_meten)                  AS te_meten,
               (SELECT count(*) FROM location WHERE actief)       AS locaties,
               (SELECT count(*) FROM product)                     AS artikelen,
               (SELECT coalesce(sum(qty), 0) FROM stock)          AS stuks
    """,

    # R-BASIS-07 geldt ook voor een logboek: nieuwste eerst, met limiet.
    "systeemlog": """
        SELECT niveau, bericht, at
          FROM event_log
         ORDER BY id DESC
         LIMIT %s
    """,

    # Open orders eerst; binnen dezelfde stand op prioriteit. Verzonden
    # orders horen onderaan, niet weg: iemand wil kunnen nakijken wat er
    # vanmorgen de deur uit is gegaan.
    "orders_scherm": """
        SELECT o.id, o.nummer, o.klant, o.status, o.prio,
               (SELECT count(*) FROM order_line r
                 WHERE r.order_id = o.id) AS regels
          FROM customer_order o
         ORDER BY (o.status = 'VERZONDEN'), o.prio, o.id DESC
         LIMIT %s
    """,

    "orderregels_scherm": """
        SELECT p.sku, p.oms, r.besteld, r.gereserveerd, r.gepickt, r.manco
          FROM order_line r
          JOIN product p ON p.id = r.product_id
         WHERE r.order_id = %s
         ORDER BY r.idx
    """,

    "toewijzingen": """
        SELECT l.code, p.sku, a.qty, a.gepickt, a.status
          FROM allocation a
          JOIN location l ON l.id = a.location_id
          JOIN product  p ON p.id = a.product_id
         WHERE a.order_id = %s
         ORDER BY l.seq, a.id
    """,

    # R-AFG-02 en R-AFG-04: maatklasse en bezetting komen uit de views,
    # niet uit een kolom.
    "locaties_scherm": """
        SELECT l.code, z.naam AS zone, t.naam AS soort, m.maatklasse,
               l.l_mm, l.w_mm, l.h_mm,
               coalesce(v.soorten, 0) AS soorten,
               coalesce(g.stuks, 0)   AS stuks
          FROM location l
          JOIN zone           z ON z.id = l.zone_id
          JOIN location_type  t ON t.id = l.type_id
          JOIN v_location_size m ON m.location_id = l.id
          LEFT JOIN v_location_load v ON v.location_id = l.id
          LEFT JOIN (SELECT location_id, sum(qty) AS stuks
                       FROM stock GROUP BY location_id) g
                 ON g.location_id = l.id
         WHERE l.actief
         ORDER BY l.seq, l.id
         LIMIT %s
    """,

    # R-AFG-01: de maat in de kolom is de nieuwste meting, geen veld.
    "artikelen_scherm": """
        SELECT p.sku, p.oms, pg.naam AS groep,
               c.l_mm, c.w_mm, c.h_mm, c.g,
               coalesce(a.aanwezig, 0) AS voorraad, c.bron
          FROM product p
          JOIN product_group pg ON pg.id = p.group_id
          LEFT JOIN v_product_current c ON c.product_id = p.id
          LEFT JOIN v_available       a ON a.product_id = p.id
         ORDER BY p.sku
         LIMIT %s
    """,

    "artikelkeuze": """
        SELECT id, sku, oms FROM product ORDER BY sku LIMIT %s
    """,

    # ---------------------------------------------------------------
    #  Gebruikers, rollen en sessies (R-GEB)
    #
    #  Het rekenwerk staat in gebruikers.py: welke rol wat mag, en een
    #  wachtwoord tot een afdruk maken en die toetsen. Hier staat wat de
    #  database bewaakt — wie er is, wie er ingelogd is en tot wanneer.
    #  Het wachtwoord komt er alleen versleuteld in en gaat er alleen
    #  versleuteld weer uit.
    # ---------------------------------------------------------------
    "gebruiker_bewaren": """
        SELECT vakto_gebruiker(%s, %s, %s, %s, %s) AS id
    """,

    "gebruiker_op_naam": """
        SELECT id, naam, gebruikersnaam, rol, badge, wachtwoord
          FROM app_user
         WHERE gebruikersnaam = lower(trim(%s)) AND actief
    """,

    "gebruiker_op_badge": """
        SELECT id, naam, gebruikersnaam, rol, badge, wachtwoord
          FROM app_user
         WHERE badge = %s AND actief
    """,

    "sessie_start": """
        SELECT vakto_sessie_start(%s, %s, %s, %s, %s) AS tot
    """,

    "sessie": """
        SELECT user_id, naam, gebruikersnaam, rol, badge, alleen_scanner, tot
          FROM vakto_sessie(%s)
    """,

    "sessie_eind": """
        SELECT vakto_sessie_eind(%s) AS gelukt
    """,

    "sessies_van": """
        SELECT vakto_sessies_van(%s) AS aantal
    """,

    # R-GEB-07. Eerst kijken of de naam op slot staat, en pas daarna
    # rekenen — anders is een slot een uitnodiging om door te gaan.
    "op_slot": """
        SELECT vakto_op_slot(%s, %s, %s) AS op_slot
    """,

    "inlogpoging": """
        SELECT vakto_inlogpoging(%s, %s, %s)
    """,

    "gebruikers": """
        SELECT id, naam, gebruikersnaam, rol, badge, actief, at,
               heeft_wachtwoord, sessies
          FROM v_gebruikers
         LIMIT %s
    """,

    # R-GEB-08. Is de tabel leeg, dan — en alleen dan — mag het eerste
    # scherm om een beheerder vragen.
    "aantal_gebruikers": """
        SELECT count(*) AS n FROM app_user
    """,

    "gebruiker_uitzetten": """
        SELECT vakto_gebruiker_uit(%s) AS naam
    """,
}


def _rijen(verbinding: Verbinding, naam: str, params: tuple = ()) -> list[tuple]:
    with verbinding.cursor() as cur:
        cur.execute(QUERIES[naam], params)
        return list(cur.fetchall())


# ---------------------------------------------------------------------
#  Laden
# ---------------------------------------------------------------------
def laad_magazijn(verbinding: Verbinding) -> Magazijn:
    """Bouwt de momentopname waar de rekenkern mee werkt.

    Let op: dit laadt het hele magazijn in het geheugen. Prima voor een
    paar duizend locaties en artikelen. Loopt een klant tegen honderd­
    duizenden artikelen aan, dan wordt dit een gerichte query per vraag —
    en dan is het fijn dat de rekenregels er niets van hoeven te weten.
    """
    soorten = {
        r[0]: LocatieSoort(id=r[0], code=r[1], naam=r[2], pick=r[3],
                           bulk=r[4], mix=r[5], blok=r[6], doel=r[7])
        for r in _rijen(verbinding, "locatiesoorten")
    }
    locaties = [
        Locatie(id=r[0], code=r[1], type_id=r[2], l_mm=r[3], w_mm=r[4],
                h_mm=r[5], max_g=r[6], zone_id=r[7], aisle=r[8], bay=r[9],
                level=r[10], seq=r[11], actief=r[12], geteld_op=r[13])
        for r in _rijen(verbinding, "locaties")
    ]
    artikelen = [
        Artikel(id=r[0], sku=r[1], oms=r[2], group_id=r[3],
                l_mm=r[4], w_mm=r[5], h_mm=r[6], g=r[7],
                gemeten_op=r[8], bron=r[9],
                min_qty=r[10], max_qty=r[11], stapelbaar=r[12], barcode=r[13],
                drempel_akkoord=r[14])
        for r in _rijen(verbinding, "artikelen")
    ]
    groepen = {
        r[0]: Artikelgroep(id=r[0], naam=r[1], telinterval=r[2])
        for r in _rijen(verbinding, "artikelgroepen")
    }
    voorraad = [
        Voorraadregel(product_id=r[0], location_id=r[1], qty=r[2], res=r[3])
        for r in _rijen(verbinding, "voorraad")
    ]
    return Magazijn(locaties=locaties, artikelen=artikelen,
                    voorraad=voorraad, soorten=soorten, groepen=groepen)


def laad_instellingen(verbinding: Verbinding):
    """Instellingen en wegingen uit de database (R-BASIS-04)."""
    from .instellingen import Instellingen
    waarden = {r[0]: r[1] for r in _rijen(verbinding, "instellingen")}
    weging = {r[0]: r[1] for r in _rijen(verbinding, "wegingen")}
    return Instellingen(waarden, weging)


# ---------------------------------------------------------------------
#  Boeken (R-BOEK-01)
# ---------------------------------------------------------------------
def boek(verbinding: Verbinding, product_id: int, aantal: int, soort: str,
         van: int | None = None, naar: int | None = None,
         reden: str | None = None, ref: str | None = None,
         gebruiker: str | None = None) -> int:
    """Roept vakto_boek() aan en geeft het journaalnummer terug.

    Alle controles zitten in de database, inclusief de rijvergrendeling.
    Deze functie doet er niets bovenop — juist niet: elke extra controle
    hier is een controle die een ander stuk code kan overslaan.

    Gooit `Boekfout` met een leesbare tekst als de database weigert.
    """
    try:
        with verbinding.cursor() as cur:
            cur.execute(QUERIES["boek"],
                        (product_id, aantal, soort, van, naar,
                         reden, ref, gebruiker))
            rij = cur.fetchone()
            return int(rij[0])
    except Boekfout:
        raise
    except Exception as e:
        # psycopg geeft de RAISE EXCEPTION uit PL/pgSQL door. De eerste
        # regel daarvan is de tekst die we aan een gebruiker willen tonen.
        tekst = str(e).strip().splitlines()[0] if str(e).strip() else str(e)
        raise Boekfout(tekst) from e


# ---------------------------------------------------------------------
#  Meten (R-MEET)
# ---------------------------------------------------------------------
def schrijf_meting(verbinding: Verbinding, mag: Magazijn, product_id: int,
                   l_mm: int, w_mm: int, h_mm: int, g: int,
                   bron: str = "RECEIPT", notitie: str | None = None,
                   inst=None, nu: datetime | None = None
                   ) -> tuple[int, Melding | None]:
    """Rekent de afwijking uit en laat de database het wegschrijven.

    De volgorde is met opzet zo:

      1. Python bepaalt de afwijking en de gevolgen tegen de momentopname
         in `mag` — dat is de rekenkant, en die moet zonder database te
         testen zijn (R-BOEK-03).
      2. De database schrijft meting en melding weg in één transactie.
         Half schrijven mag niet: een meting zonder melding is een
         gemiste waarschuwing.

    Let op dat `mag` een MOMENTOPNAME is. Is die ouder dan de voorraad in
    de database, dan klopt de gevolg-tekst niet meer. Laad hem opnieuw
    vlak voor je dit aanroept, of accepteer dat de zelfcontrole (R-ZC-01)
    hem straks bijwerkt — dat laatste is meestal prima, want die draait
    toch na elke mutatie.

    Committen doet deze functie niet. Dat hoort bij de aanroeper, samen
    met de rest van wat er in dezelfde handeling gebeurt.
    """
    melding = _meten.leg_meting_vast(mag, product_id, l_mm, w_mm, h_mm, g,
                                     bron=bron, notitie=notitie,
                                     inst=inst, nu=nu)
    params = (product_id, l_mm, w_mm, h_mm, g, bron, notitie,
              None if melding is None else melding.d_vol,
              None if melding is None else melding.d_gew,
              None if melding is None else melding.gevolg)
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["meting"], params)
        rij = cur.fetchone()
    if melding is not None:
        melding.id = int(rij[1])
    return int(rij[0]), melding


def sluit_melding(verbinding: Verbinding, melding_id: int,
                  status: str = "OPGELOST") -> bool:
    """R-ZC-01. Geeft False als de melding al niet meer open stond."""
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["melding_sluiten"], (melding_id, status))
        return bool(cur.fetchone()[0])


def open_meldingen(verbinding: Verbinding) -> list[Melding]:
    """Alle openstaande meldingen, oudste eerst."""
    uit = []
    for r in _rijen(verbinding, "open_meldingen"):
        m = Melding(product_id=r[1], at=r[2], d_vol=float(r[3]),
                    d_gew=float(r[4]), gevolg=r[5])
        m.id = int(r[0])
        uit.append(m)
    return uit


def meetlijst(verbinding: Verbinding, limiet: int = 200) -> list[tuple]:
    """R-MEET-04, rechtstreeks uit de view. Nooit gemeten bovenaan.

    Met een limiet, want R-BASIS-07 geldt ook hier: bij een nieuwe klant
    staan er negenhonderd artikelen op deze lijst en dan wil je geen
    scherm van een halve megabyte. De volgorde doet het werk — wie de
    bovenste twintig afwerkt, heeft de twintig belangrijkste gehad.
    """
    return _rijen(verbinding, "te_meten", (limiet,))


def metingen_van(verbinding: Verbinding, product_id: int) -> list[tuple]:
    """De hele tijdlijn van één artikel, nieuwste eerst."""
    return _rijen(verbinding, "metingen_van", (product_id,))


# ---------------------------------------------------------------------
#  Uitgaand (R-UIT)
#
#  Dun met opzet. Het werk gebeurt in uitgaand.sql, waar het onder een
#  rijvergrendeling staat; deze functies vertalen alleen heen en terug.
#  Elke controle die je hier bovenop zou zetten, is een controle die een
#  ander stuk code kan overslaan (R-BOEK-03).
#
#  Committen doen ze geen van alle. Dat hoort bij de aanroeper, samen met
#  de rest van wat er in dezelfde handeling gebeurt.
# ---------------------------------------------------------------------
def reserveer(verbinding: Verbinding, order_id: int,
              gebruiker: str | None = None) -> str:
    """R-UIT-01 en R-UIT-02. Geeft de nieuwe orderstatus terug.

    `GERESERVEERD` als alles vastgelegd kon worden, anders
    `WACHT_OP_VOORRAAD`. Stond de order al op WACHT_OP_VOORRAAD, dan komt
    er geen tweede waarschuwing in het log — één keer melden is genoeg.
    """
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["reserveer"], (order_id, gebruiker))
        return str(cur.fetchone()[0])


def geef_vrij(verbinding: Verbinding, order_id: int) -> int:
    """R-UIT-03. Geeft het aantal pickregels terug, 0 als er niets ging."""
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["geef_vrij"], (order_id,))
        return int(cur.fetchone()[0])


def bevestig_pick(verbinding: Verbinding, allocation_id: int, aantal: int,
                  gebruiker: str | None = None) -> str:
    """R-UIT-04 en R-UIT-05. Geeft `DONE` of `MANCO` terug.

    De teltaak-tekst stellen we hier samen en niet in SQL, om dezelfde
    reden als bij `gevolg_tekst` in meten.py: een zin die een mens leest,
    schrijf je waar je hem zonder database kunt natesten.
    """
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["pickregel"], (allocation_id,))
        rij = cur.fetchone()
        if rij is None:
            raise Boekfout(f"Pickregel {allocation_id} bestaat niet")

        _, _, nummer, _, _, _, _, code, qty, gepickt, _ = rij
        gevraagd = qty - gepickt
        tekort = max(0, gevraagd - max(0, aantal))
        reden = (_uitgaand.teltaak_reden(nummer, tekort, qty, code)
                 if tekort else None)

        try:
            cur.execute(QUERIES["pick"], (allocation_id, aantal, gebruiker, reden))
            return str(cur.fetchone()[0])
        except Boekfout:
            raise
        except Exception as e:
            tekst = str(e).strip().splitlines()[0] if str(e).strip() else str(e)
            raise Boekfout(tekst) from e


def pak_in(verbinding: Verbinding, order_id: int, artikelen: dict,
           inst=None) -> Inpak | None:
    """R-UIT-07. Rekent colli en gewicht uit en legt ze vast.

    Geeft None als de order niet op GEPICKT stond. `artikelen` is
    {product_id: Artikel} — meestal `{a.id: a for a in magazijn.artikelen}`.
    """
    regels = {r.product_id: r.gepickt for r in orderregels(verbinding, order_id)}
    inpak = _uitgaand.inpakgegevens(regels, artikelen, inst)
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["pak_in"], (order_id, inpak.colli, inpak.gewicht_g))
        return inpak if bool(cur.fetchone()[0]) else None


def verzend(verbinding: Verbinding, order_id: int,
            track: str | None = None) -> bool:
    """R-UIT-06. False als de order niet op INGEPAKT stond."""
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["verzend"], (order_id, track))
        return bool(cur.fetchone()[0])


def laad_order(verbinding: Verbinding, order_id: int) -> Order | None:
    """De order met zijn regels, of None als hij niet bestaat."""
    rijen = _rijen(verbinding, "order", (order_id,))
    if not rijen:
        return None
    r = rijen[0]
    return Order(id=r[0], nummer=r[1], klant=r[2], plaats=r[3], land=r[4],
                 vervoerder=r[5], soort=r[6], prio=r[7], status=r[8], at=r[9],
                 colli=r[10], gewicht_g=r[11], track=r[12],
                 regels=orderregels(verbinding, order_id))


def orderregels(verbinding: Verbinding, order_id: int) -> list[Orderregel]:
    return [Orderregel(idx=r[0], product_id=r[1], besteld=r[2],
                       gereserveerd=r[3], gepickt=r[4], manco=r[5])
            for r in _rijen(verbinding, "orderregels", (order_id,))]


def picklijst(verbinding: Verbinding, order_id: int | None = None,
              limiet: int = 200) -> list[Pickregel]:
    """R-UIT-03. Op looproute gesorteerd, altijd met een limiet (R-BASIS-07)."""
    naam = "picklijst" if order_id is None else "picklijst_order"
    params = (limiet,) if order_id is None else (order_id, limiet)
    return [Pickregel(allocation_id=r[0], order_id=r[1], ordernummer=r[2],
                      prio=r[3], regel=r[4], product_id=r[5], sku=r[6],
                      oms=r[7], location_id=r[8], locatie=r[9], zone_id=r[10],
                      seq=r[11], qty=r[12], gepickt=r[13])
            for r in _rijen(verbinding, naam, params)]


# ---------------------------------------------------------------------
#  Zelfcontrole en optimalisatie (R-ZC, R-OPT)
#
#  Dezelfde taakverdeling als bij meten: Python bepaalt wat er zou moeten
#  gebeuren tegen een momentopname, de database schrijft het weg in één
#  transactie. Half schrijven mag niet — een melding die gesloten wordt
#  zonder de log-regel erbij is een besluit dat niemand meer kan navragen.
# ---------------------------------------------------------------------
def laad_taken(verbinding: Verbinding) -> list[Taak]:
    """Alle openstaande taken, op prioriteit."""
    uit = []
    for r in _rijen(verbinding, "open_taken"):
        t = Taak(soort=r[1], naam=r[2], prio=r[3], status=r[4],
                 product_id=r[5], van=r[6], naar=r[7], qty=r[8],
                 aanleiding=r[9], reden=r[10], automatisch=r[11], at=r[12])
        t.id = int(r[0])
        uit.append(t)
    return uit


def laad_ordervraag(verbinding: Verbinding) -> dict[int, int]:
    """R-OPT-03. Nog te picken stuks uit orders die nog op de vloer liggen."""
    return {int(r[0]): int(r[1]) for r in _rijen(verbinding, "ordervraag")}


def laad_picks(verbinding: Verbinding, inst=None) -> list[Pick]:
    """R-OPT-02. De PICK-regels binnen het venster.

    Het venster komt uit de instellingen en gaat als parameter mee naar
    de query: zo staat het getal op één plek en niet ook nog een keer in
    SQL (R-BASIS-04).
    """
    from .instellingen import Instellingen
    inst = inst or Instellingen()
    dagen = max(1, inst.geheel("opt.venster_dagen"))
    return [Pick(product_id=int(r[0]), qty=int(r[1]), at=r[2])
            for r in _rijen(verbinding, "picks", (str(dagen),))]


def schrijf_uitkomst(verbinding: Verbinding, uit: Uitkomst) -> Uitkomst:
    """Zet één ronde zelfcontrole om in rijen. Committen doet de aanroeper.

    De volgorde is bewust: eerst vervallen, dan bijwerken, dan nieuw. Zou
    je eerst nieuwe taken schrijven, dan botst een verse aanvultaak met
    een oude die in dezelfde ronde vervalt — en dan houdt de unieke index
    op `task` er terecht een tegen.
    """
    with verbinding.cursor() as cur:
        for v in uit.vervallen:
            if v.taak.id is None:
                continue
            cur.execute(QUERIES["taak_vervallen"], (v.taak.id, v.reden))
            cur.fetchone()

        for b in uit.bijwerken:
            if b.taak.id is None:
                continue
            cur.execute(QUERIES["taak_bijwerken"],
                        (b.taak.id, b.qty, b.prio, b.aanleiding, b.reden))
            cur.fetchone()

        for t in uit.nieuwe_taken:
            cur.execute(QUERIES["taak"],
                        (t.soort, t.naam, t.prio, t.product_id, t.van, t.naar,
                         t.qty, t.aanleiding, t.reden, t.automatisch))
            rij = cur.fetchone()
            if rij and rij[0] is not None:
                t.id = int(rij[0])

        for m in uit.gesloten:
            if m.id is None:
                continue
            cur.execute(QUERIES["melding_sluiten"], (m.id, "OPGELOST"))
            cur.fetchone()

        for m in uit.bijgewerkte_meldingen:
            if m.id is None:
                continue
            cur.execute(QUERIES["melding_bijwerken"], (m.id, m.gevolg))
            cur.fetchone()

        # De log-regels als laatste: dan staat er niets in het log wat
        # niet ook echt gebeurd is.
        for regel in uit.regels:
            cur.execute(QUERIES["log"], ("zelfcontrole", regel, "INFO", None))
            cur.fetchone()
    return uit


def draai_zelfcontrole(verbinding: Verbinding, mag: Magazijn | None = None,
                       inst=None, nu: datetime | None = None,
                       zwaar: bool = True) -> Uitkomst:
    """Eén ronde: toestand laden, laten rekenen, uitkomst wegschrijven.

    Dit is de functie die een achtergrondtaak elke paar minuten aanroept,
    en die na elke boeking gedraaid mag worden — er gebeurt niets dubbel,
    want alles is een gevolgtrekking uit de huidige toestand.

    Geef `mag` mee als je hem toch al geladen had; anders wordt hij hier
    opgehaald. Committen doet de aanroeper.
    """
    from .instellingen import Instellingen
    inst = inst or laad_instellingen(verbinding)
    mag = laad_magazijn(verbinding) if mag is None else mag

    uitkomst = _zelfcontrole.hertoets(
        mag,
        taken=laad_taken(verbinding),
        meldingen=open_meldingen(verbinding),
        vraag=laad_ordervraag(verbinding),
        picks=laad_picks(verbinding, inst),
        inst=inst, nu=nu, zwaar=zwaar)
    return schrijf_uitkomst(verbinding, uitkomst)


def voer_taak_uit(verbinding: Verbinding, taak_id: int,
                  aantal: int | None = None,
                  gebruiker: str | None = None) -> int | None:
    """Meldt een taak af. Geeft het journaalnummer, of None bij tellen."""
    try:
        with verbinding.cursor() as cur:
            cur.execute(QUERIES["taak_uitvoeren"], (taak_id, aantal, gebruiker))
            rij = cur.fetchone()
            return None if rij is None or rij[0] is None else int(rij[0])
    except Boekfout:
        raise
    except Exception as e:
        tekst = str(e).strip().splitlines()[0] if str(e).strip() else str(e)
        raise Boekfout(tekst) from e


def tel_locatie(verbinding: Verbinding, location_id: int, product_id: int,
                geteld: int, gebruiker: str | None = None,
                reden: str = "TELVERSCHIL",
                ref: str | None = "Cyclustelling") -> int | None:
    """R-OPT-04 en R-SCAN-05. Boekt het verschil en zet het telstempel.

    `reden` is TELVERSCHIL, behalve bij een nulmeting: dan is er niets om
    van af te wijken en heet het NULMETING. Die twee namen staan niet
    voor niets in het journaal — ze zijn het verschil tussen "hier gaat
    iets mis" en "hier begint een nieuwe klant".
    """
    try:
        with verbinding.cursor() as cur:
            cur.execute(QUERIES["tellen"],
                        (location_id, product_id, geteld, gebruiker,
                         reden, ref))
            rij = cur.fetchone()
            return None if rij is None or rij[0] is None else int(rij[0])
    except Boekfout:
        raise
    except Exception as e:
        tekst = str(e).strip().splitlines()[0] if str(e).strip() else str(e)
        raise Boekfout(tekst) from e


def werklijst(verbinding: Verbinding, limiet: int = 200) -> list[tuple]:
    """Openstaand werk, op prioriteit en daarna op looproute."""
    return _rijen(verbinding, "werklijst", (limiet,))


# ---------------------------------------------------------------------
#  De schermen (stap 8)
#
#  Alleen ophalen. Wat een scherm ermee tekent staat in schermen.py, wat
#  een knop doet in web.py; hier staat wat de database erover weet.
# ---------------------------------------------------------------------
def cijfers(verbinding: Verbinding) -> dict:
    """De koppen van het dashboard, in de volgorde waarin ze er staan."""
    r = _rijen(verbinding, "cijfers")[0]
    namen = ("Open taken", "Meldingen", "Open orders", "Pickregels",
             "Te meten", "Locaties", "Artikelen", "Stuks")
    return dict(zip(namen, (int(w) for w in r)))


def systeemlog(verbinding: Verbinding, limiet: int = 40) -> list[tuple]:
    """Wat het systeem zelf besloten heeft, nieuwste eerst."""
    return _rijen(verbinding, "systeemlog", (limiet,))


def orderlijst(verbinding: Verbinding, limiet: int = 200) -> list[tuple]:
    return _rijen(verbinding, "orders_scherm", (limiet,))


def orderregels_scherm(verbinding: Verbinding, order_id: int) -> list[tuple]:
    return _rijen(verbinding, "orderregels_scherm", (order_id,))


def toewijzingen(verbinding: Verbinding, order_id: int) -> list[tuple]:
    """R-UIT-01. Waar de gereserveerde stuks vandaan komen."""
    return _rijen(verbinding, "toewijzingen", (order_id,))


def locatielijst(verbinding: Verbinding, limiet: int = 500) -> list[tuple]:
    return _rijen(verbinding, "locaties_scherm", (limiet,))


def artikellijst(verbinding: Verbinding, limiet: int = 500) -> list[tuple]:
    return _rijen(verbinding, "artikelen_scherm", (limiet,))


def artikelkeuze(verbinding: Verbinding, limiet: int = 500) -> list[tuple]:
    """Voor het uitrolmenu op het inslagscherm."""
    return _rijen(verbinding, "artikelkeuze", (limiet,))


# ---------------------------------------------------------------------
#  Gebruikers, rollen en sessies (R-GEB)
#
#  Dit is de enige plek waar een wachtwoord in leesbare vorm langskomt,
#  en het gaat er meteen versleuteld weer uit. Geen enkele aanroeper
#  hoeft te weten hoe dat werkt, en niemand kan het per ongeluk overslaan.
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class Aanmelding:
    """Wat er uit een inlogpoging komt.

    Bij een weigering staat er een tekst in `fout` die je aan de
    gebruiker kunt laten zien. Die tekst is met opzet vaag over wát er
    mis was (R-GEB-07): "onbekende gebruiker" vertelt wie er wél bestaat.
    """
    token: str | None = None
    gebruiker: _gebruikers.Gebruiker | None = None
    fout: str | None = None

    @property
    def gelukt(self) -> bool:
        return self.token is not None


def bewaar_gebruiker(verbinding: Verbinding, gebruikersnaam: str, naam: str,
                     rol: str = "OPERATOR", wachtwoord: str | None = None,
                     badge: str | None = None) -> int:
    """Aanmaken of bijwerken. Geeft het gebruikersnummer terug.

    Het wachtwoord wordt hier versleuteld en gaat als afdruk de database
    in (R-GEB-04). Laat je het leeg, dan blijft het bestaande staan —
    dat is wat je wilt als je alleen de rol aanpast.
    """
    if rol not in _gebruikers.ROLLEN:
        raise Boekfout(f"Onbekende rol {rol!r}")
    if wachtwoord:
        klacht = _gebruikers.zwak(wachtwoord)
        if klacht:
            raise Boekfout(klacht)
    afdruk = _gebruikers.versleutel(wachtwoord) if wachtwoord else None
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["gebruiker_bewaren"],
                    (gebruikersnaam, naam, rol, afdruk, badge))
        return int(cur.fetchone()[0])


def _uit_rij(rij, alleen_scanner: bool = False) -> _gebruikers.Gebruiker:
    return _gebruikers.Gebruiker(
        id=rij[0], naam=rij[1], gebruikersnaam=rij[2], rol=rij[3],
        badge=rij[4], alleen_scanner=alleen_scanner)


def meld_aan(verbinding: Verbinding, gebruikersnaam: str, wachtwoord: str,
             inst=None, vanaf: str | None = None) -> Aanmelding:
    """R-GEB-03, R-GEB-05 en R-GEB-07. Inloggen met naam en wachtwoord.

    De volgorde is met opzet zo:

      1. Staat de naam op slot? Dan meteen weg, zonder te rekenen.
      2. De gebruiker opzoeken — bestaat hij niet, dan toch toetsen,
         tegen een afdruk die niemand heeft. Anders verraadt de snelheid
         van het antwoord wie er wél bestaat.
      3. De poging opschrijven, gelukt of niet.
      4. Pas dan een sessie.
    """
    inst = inst or laad_instellingen(verbinding)
    naam = (gebruikersnaam or "").strip()
    if not naam:
        return Aanmelding(fout="Vul een gebruikersnaam in.")

    with verbinding.cursor() as cur:
        cur.execute(QUERIES["op_slot"],
                    (naam, int(inst.getal("inlog.max_pogingen")), 15))
        if bool(cur.fetchone()[0]):
            return Aanmelding(fout="Te veel mislukte pogingen. Probeer het "
                                   "over een kwartier opnieuw.")

    rijen = _rijen(verbinding, "gebruiker_op_naam", (naam,))
    rij = rijen[0] if rijen else None
    goed = _gebruikers.klopt(wachtwoord, rij[5] if rij else None)

    with verbinding.cursor() as cur:
        cur.execute(QUERIES["inlogpoging"], (naam, goed, vanaf))
        cur.fetchone()

    if not goed:
        return Aanmelding(fout="Gebruikersnaam of wachtwoord klopt niet.")
    return _start_sessie(verbinding, _uit_rij(rij), inst, vanaf)


def meld_aan_met_badge(verbinding: Verbinding, badge: str, inst=None,
                       vanaf: str | None = None) -> Aanmelding:
    """R-GEB-03. Een badge geeft toegang tot de scanmodus en tot niets anders.

    Hij ligt op tafel en iedereen kan hem lezen; dat is geen wachtwoord.
    Een teamleider die zich zo aanmeldt staat op de vloer als medewerker
    — wil hij bij de orders, dan logt hij in.
    """
    inst = inst or laad_instellingen(verbinding)
    if not inst.aan("inlog.badge_voor_scanner"):
        return Aanmelding(fout="Aanmelden met een badge staat uit. Log in "
                               "met je gebruikersnaam en wachtwoord.")
    code = (badge or "").strip()
    if not code:
        return Aanmelding(fout="Scan je badge.")
    rijen = _rijen(verbinding, "gebruiker_op_badge", (code,))
    if not rijen:
        with verbinding.cursor() as cur:
            cur.execute(QUERIES["inlogpoging"], (f"badge:{code}", False, vanaf))
            cur.fetchone()
        return Aanmelding(fout="Deze badge kennen we niet.")
    return _start_sessie(verbinding, _uit_rij(rijen[0], alleen_scanner=True),
                         inst, vanaf)


def _start_sessie(verbinding: Verbinding, gebruiker, inst,
                  vanaf: str | None) -> Aanmelding:
    token = _gebruikers.nieuw_token()
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["sessie_start"],
                    (gebruiker.id, _gebruikers.afdruk(token),
                     int(inst.getal("sessie.duur_uren")),
                     gebruiker.alleen_scanner, vanaf))
        cur.fetchone()
    return Aanmelding(token=token, gebruiker=gebruiker)


def wie_is(verbinding: Verbinding, token: str | None):
    """De gebruiker achter een sessietoken, of None.

    Geeft ook None als de sessie verlopen is of als de gebruiker
    inmiddels uitstaat. Dat laatste is het punt van R-GEB-05: iemand die
    uit dienst gaat is er bij de volgende aanvraag uit, en niet pas als
    de server toevallig herstart.
    """
    if not token:
        return None
    rijen = _rijen(verbinding, "sessie", (_gebruikers.afdruk(token),))
    if not rijen:
        return None
    r = rijen[0]
    return _gebruikers.Gebruiker(id=r[0], naam=r[1], gebruikersnaam=r[2],
                                 rol=r[3], badge=r[4], alleen_scanner=r[5])


def meld_af(verbinding: Verbinding, token: str | None) -> bool:
    """Uitloggen. De rij weg, niet alleen het koekje."""
    if not token:
        return False
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["sessie_eind"], (_gebruikers.afdruk(token),))
        return bool(cur.fetchone()[0])


def trek_sessies_in(verbinding: Verbinding, user_id: int) -> int:
    """Alle sessies van één gebruiker. Voor als een telefoon kwijt is."""
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["sessies_van"], (user_id,))
        return int(cur.fetchone()[0])


def zet_gebruiker_uit(verbinding: Verbinding, user_id: int) -> str | None:
    """Uit dienst: geen toegang meer, maar zijn naam blijft in het
    journaal staan. Verwijderen zou de geschiedenis onleesbaar maken."""
    with verbinding.cursor() as cur:
        cur.execute(QUERIES["gebruiker_uitzetten"], (user_id,))
        rij = cur.fetchone()
    return None if rij is None or rij[0] is None else str(rij[0])


def gebruikerslijst(verbinding: Verbinding, limiet: int = 200) -> list[tuple]:
    return _rijen(verbinding, "gebruikers", (limiet,))


def aantal_gebruikers(verbinding: Verbinding) -> int:
    """R-GEB-08. Nul betekent: er moet nog een eerste beheerder komen."""
    return int(_rijen(verbinding, "aantal_gebruikers")[0][0])


# ---------------------------------------------------------------------
#  Import (R-IMP)
#
#  Het lezen, raden en controleren gebeurt in inlezen.py en raakt geen
#  database aan. Hier wordt een gecontroleerd rapport omgezet in rijen —
#  in één aanroep, dus in één transactie. Een import die halverwege
#  stukloopt laat je achter met locaties zonder artikelen.
# ---------------------------------------------------------------------
def neem_over(verbinding: Verbinding, rapport, gebruiker: str | None = None,
              inst=None) -> dict:
    """R-IMP-06 en R-IMP-07. Geeft de tellingen terug die de database maakte.

    De looproute wordt hier uitgerekend en niet in SQL: `ontleed_code`
    en `looproute_seq` zijn rekenregels (R-IMP-06, R-UIT-03) en horen
    zonder database te kunnen draaien.
    """
    if not rapport.klaar:
        raise Boekfout(
            "Zonder bruikbare locaties valt er niets over te nemen. "
            "Kijk eerst het locatiebestand na.")

    locaties = []
    for volgnr, regel in enumerate(rapport.loc_regels.values()):
        plek = _inlezen.ontleed_code(regel.code, volgnr)
        locaties.append({
            "code": regel.code, "zone": regel.zone,
            "type_id": _inlezen.soort_naar_type(regel.soort, regel.code),
            "gang": plek.gang, "vak": plek.vak, "niveau": plek.niveau,
            "seq": _uitgaand.looproute_seq(plek.gang, plek.vak, plek.niveau),
            "l_mm": regel.l_mm, "w_mm": regel.w_mm, "h_mm": regel.h_mm,
            "max_g": regel.max_g})

    artikelen = [{
        "sku": a.sku, "oms": a.oms, "groep": a.groep,
        "l_mm": a.l_mm, "w_mm": a.w_mm, "h_mm": a.h_mm, "g": a.g,
        "barcode": a.barcode, "min_qty": a.min_qty, "max_qty": a.max_qty}
        for a in rapport.art_regels.values()]

    voorraad = [{"sku": v.sku, "locatie": v.locatie, "qty": v.qty}
                for v in rapport.vrd_regels]

    try:
        with verbinding.cursor() as cur:
            cur.execute(QUERIES["import"],
                        (json.dumps(locaties), json.dumps(artikelen),
                         json.dumps(voorraad), gebruiker))
            rij = cur.fetchone()
    except Boekfout:
        raise
    except Exception as e:
        tekst = str(e).strip().splitlines()[0] if str(e).strip() else str(e)
        raise Boekfout(tekst) from e

    uit = rij[0] if rij else {}
    return json.loads(uit) if isinstance(uit, str) else uit
