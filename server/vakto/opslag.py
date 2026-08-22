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
from typing import Any, Protocol

from datetime import datetime

from .modellen import (Artikel, Artikelgroep, Locatie, LocatieSoort, Magazijn,
                       Taak, Voorraadregel)
from .meten import Melding
from .optimalisatie import Pick
from .uitgaand import Inpak, Order, Orderregel, Pickregel
from .zelfcontrole import Uitkomst
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
        SELECT vakto_tellen(%s, %s, %s, %s)
    """,

    "log": """
        SELECT vakto_log(%s, %s, %s, %s)
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


def meetlijst(verbinding: Verbinding) -> list[tuple]:
    """R-MEET-04, rechtstreeks uit de view. Nooit gemeten bovenaan."""
    return _rijen(verbinding, "te_meten")


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
                geteld: int, gebruiker: str | None = None) -> int | None:
    """R-OPT-04. Boekt het verschil en zet het telstempel."""
    try:
        with verbinding.cursor() as cur:
            cur.execute(QUERIES["tellen"],
                        (location_id, product_id, geteld, gebruiker))
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
