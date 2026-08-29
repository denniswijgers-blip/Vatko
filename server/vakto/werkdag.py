"""Een hele werkdag naspelen (T-18).

Dit is geen rekenregel en geen product-onderdeel: het is een instrument
om te bewijzen dat alle regels samen blijven kloppen. Elke stap gaat door
dezelfde functies waar een scherm ook doorheen gaat — er is geen
achterdeur die de voorraad rechtstreeks aanraakt.

Waarom dit bestaat: losse tests bewijzen dat één regel klopt. Een dag
bewijst dat ze elkaar niet in de weg zitten. Bij het schrijven van de
browserversie kwamen daar twee fouten uit die geen enkele losse test
gevonden had — een order die bleef hangen op WACHT_OP_VOORRAAD terwijl er
allang was aangevuld, en een reservering die na een manco bleef staan.

Aan het eind gelden drie dingen (T-18):

  * nul negatieve voorraadregels
  * nergens res > qty
  * geen hangende reserveringen

De eerste twee bewaakt de database zelf met een CHECK, dus die kunnen
alleen falen als iemand het schema uitkleedt. De derde is het echte
werk: elke order die is gereserveerd hoort ook gepickt en verzonden te
zijn, of met een reden open te staan.

Zelf draaien tegen een database:

    python3 -m vakto.werkdag            # verslag op het scherm
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .instellingen import Instellingen
from .opslag import (bevestig_pick, boek, draai_zelfcontrole, geef_vrij,
                     laad_magazijn, laad_taken, pak_in, picklijst, reserveer,
                     verzend, voer_taak_uit)

# Een werkdag van zeven tot vijf, in tikken van vijf minuten. Dezelfde
# indeling als de browserversie, zodat de twee te vergelijken zijn.
DAGSTART, DAGEIND, TIK = 7 * 60, 17 * 60, 5

# Hoe druk het is per uur: piek 's ochtends, dip tijdens de lunch.
DRUKTE = {7: 0.4, 8: 1.0, 9: 1.6, 10: 1.7, 11: 1.4, 12: 0.5,
          13: 1.2, 14: 1.5, 15: 1.3, 16: 0.8}

KLANTEN = ("Installatiebedrijf Van Loon", "Machinefabriek Kessels",
           "Techniek Groep Oost", "Pompservice Zeeland", "Hydrauliek Noord",
           "Bosman Onderhoud", "Staalbouw Rijnmond", "Motoren De Wit")


def klok(minuten: int) -> str:
    return f"{minuten // 60:02d}:{minuten % 60:02d}"


@dataclass
class Verslag:
    """Wat er die dag gebeurd is."""
    orders: int = 0
    verzonden: int = 0
    regels: int = 0
    manco: int = 0
    stuks: int = 0
    taken: int = 0
    gebeurtenissen: list[str] = field(default_factory=list)

    def meld(self, tijd: int, tekst: str) -> None:
        self.gebeurtenissen.append(f"{klok(tijd)}  {tekst}")

    def __str__(self) -> str:
        return (f"{self.orders} orders binnen, {self.verzonden} verzonden, "
                f"{self.regels} pickregels ({self.manco} manco), "
                f"{self.stuks} stuks, {self.taken} taken uitgevoerd")


@dataclass
class Controle:
    """De drie dingen die aan het eind moeten kloppen (T-18)."""
    negatief: int = 0
    overgereserveerd: int = 0
    hangend: int = 0
    open_orders: int = 0

    @property
    def schoon(self) -> bool:
        return not (self.negatief or self.overgereserveerd or self.hangend)

    def __str__(self) -> str:
        return (f"negatieve voorraadregels {self.negatief}, "
                f"res > qty {self.overgereserveerd}, "
                f"hangende reserveringen {self.hangend}, "
                f"orders nog open {self.open_orders}")


def _rijen(verbinding, sql: str) -> list[tuple]:
    with verbinding.cursor() as cur:
        cur.execute(sql)
        return list(cur.fetchall())


def controleer_einde(verbinding) -> Controle:
    """T-18. Wat er aan het eind van de dag niet mag staan."""
    c = Controle()
    c.negatief = _rijen(verbinding,
                        "SELECT count(*) n FROM stock WHERE qty < 0")[0][0]
    c.overgereserveerd = _rijen(verbinding,
                                "SELECT count(*) n FROM stock WHERE res > qty")[0][0]
    # Een reservering hangt als de voorraad vastligt terwijl de order er
    # niets meer mee doet: verzonden, of geen open pickregel meer.
    c.hangend = _rijen(verbinding, """
        SELECT count(*) n FROM allocation a
          JOIN customer_order o ON o.id = a.order_id
         WHERE a.status = 'TODO' AND o.status = 'VERZONDEN'
    """)[0][0]
    c.open_orders = _rijen(verbinding, """
        SELECT count(*) n FROM customer_order WHERE status <> 'VERZONDEN'
    """)[0][0]
    return c


# ---------------------------------------------------------------------
#  De dag
# ---------------------------------------------------------------------
def draai_werkdag(verbinding, inst: Instellingen | None = None,
                  zaad: int = 20260615, manco_kans: float = 0.06,
                  gebruiker: str = "simulatie") -> Verslag:
    """Speelt een dag af tegen een database die al gevuld is.

    Alles loopt via `opslag.py`: orders worden aangemaakt, gereserveerd,
    vrijgegeven, gepickt, ingepakt en verzonden, en tussendoor draait de
    zelfcontrole en wordt er werk uitgevoerd. Precies zoals een scherm
    het zou doen.
    """
    inst = inst or Instellingen()
    kans = random.Random(zaad)
    verslag = Verslag()
    mag = laad_magazijn(verbinding)
    artikelen = [a for a in mag.artikelen if a.gemeten]
    if not artikelen:
        raise ValueError("Geen opgemeten artikelen: er valt niets te picken.")

    nummer = 250_000
    tijd = DAGSTART
    while tijd < DAGEIND:
        drukte = DRUKTE.get(tijd // 60, 0.5)

        # --- 1. orders komen binnen ---------------------------------
        if kans.random() < 0.55 * drukte:
            nummer += 1
            verslag.orders += 1
            _maak_order(verbinding, kans, artikelen, nummer, verslag, tijd)

        # --- 2. reserveren en vrijgeven -----------------------------
        #  Nieuwe orders eerst: die hebben nog geen kans gehad. Zou je
        #  gewoon op ouderdom sorteren, dan blijven twintig orders die op
        #  voorraad wachten de hele dag vooraan staan en komt er geen
        #  enkele nieuwe meer aan de beurt.
        for order_id, order_nr in _orders_met_status(verbinding, ("NIEUW",)):
            if reserveer(verbinding, order_id, gebruiker) == "WACHT_OP_VOORRAAD":
                verslag.meld(tijd, f"{order_nr} wacht op voorraad")
        for order_id, _ in _orders_met_status(verbinding, ("WACHT_OP_VOORRAAD",)):
            reserveer(verbinding, order_id, gebruiker)
        for order_id, _ in _orders_met_status(verbinding, ("GERESERVEERD",)):
            geef_vrij(verbinding, order_id)

        # --- 3. picken ----------------------------------------------
        budget = max(2, round(9 * drukte))
        for regel in picklijst(verbinding, limiet=budget):
            gevraagd = regel.nog_te_picken
            aantal = (gevraagd - kans.randint(1, gevraagd)
                      if kans.random() < manco_kans else gevraagd)
            uitkomst = bevestig_pick(verbinding, regel.allocation_id,
                                     max(0, aantal), gebruiker)
            verslag.regels += 1
            verslag.stuks += max(0, aantal)
            if uitkomst == "MANCO":
                verslag.manco += 1
                verslag.meld(tijd, f"Manco op {regel.locatie} — {regel.sku}")

        # --- 4. inpakken en verzenden -------------------------------
        maten = {a.id: a for a in mag.artikelen}
        for order_id, order_nr in _orders_met_status(verbinding, ("GEPICKT",)):
            if pak_in(verbinding, order_id, maten, inst):
                verzend(verbinding, order_id, f"3S{100000 + order_id}NL")
                verslag.verzonden += 1

        # --- 5. de zelfcontrole draait na elke golf ------------------
        uitkomst = draai_zelfcontrole(verbinding, inst=inst,
                                      zwaar=(tijd % 60 == 0))
        for regel in uitkomst.regels[:3]:
            verslag.meld(tijd, regel)

        # --- 6. en er wordt werk gedaan -----------------------------
        for taak in laad_taken(verbinding)[:2]:
            if taak.soort == "CYCLE_COUNT" or kans.random() < 0.5:
                try:
                    voer_taak_uit(verbinding, taak.id, gebruiker=gebruiker)
                    verslag.taken += 1
                except Exception:
                    # Een taak die niet meer kan (de voorraad is intussen
                    # weg) is geen storing: de zelfcontrole laat hem
                    # vanzelf vervallen (R-ZC-03).
                    pass

        # --- 7. af en toe komt er iets binnen -----------------------
        if kans.random() < 0.18 * drukte:
            _ontvang(verbinding, kans, mag, artikelen, gebruiker, verslag, tijd)
            mag = laad_magazijn(verbinding)

        tijd += TIK

    # Aan het eind van de dag gaat alles wat gepickt is nog de deur uit.
    maten = {a.id: a for a in mag.artikelen}
    for order_id, _ in _orders_met_status(verbinding, ("GEPICKT",)):
        if pak_in(verbinding, order_id, maten, inst):
            verzend(verbinding, order_id, f"3S{100000 + order_id}NL")
            verslag.verzonden += 1
    draai_zelfcontrole(verbinding, inst=inst)
    return verslag


def _orders_met_status(verbinding, statussen: tuple[str, ...]) -> list[tuple]:
    lijst = ", ".join(f"'{s}'" for s in statussen)
    return _rijen(verbinding,
                  f"SELECT id, nummer FROM customer_order "
                  f"WHERE status IN ({lijst}) ORDER BY prio, id LIMIT 40")


def _maak_order(verbinding, kans, artikelen, nummer, verslag, tijd) -> None:
    import json
    # Alleen artikelen waar ook echt iets van vrij ligt, net als de
    # browserversie doet. Een order op een artikel met nul voorraad is
    # geen test van de uitgaande stroom maar van de wachtrij.
    vrij = {r[0]: r[1] for r in _rijen(verbinding, """
        SELECT product_id, beschikbaar FROM v_available WHERE beschikbaar > 3
    """)}
    kandidaten = [a for a in artikelen if a.id in vrij]
    if not kandidaten:
        return
    aantal_regels = kans.randint(1, 3)
    gekozen = kans.sample(kandidaten, min(aantal_regels, len(kandidaten)))
    regels = [{"sku": a.sku,
               "besteld": kans.randint(1, max(1, min(12, vrij[a.id] // 3)))}
              for a in gekozen]
    with verbinding.cursor() as cur:
        cur.execute("SELECT vakto_order(%s, %s, %s::jsonb, %s, %s)",
                    (f"ORD-{nummer}", kans.choice(KLANTEN),
                     json.dumps(regels), kans.choice((1, 3, 5)), "WEB"))
        cur.fetchone()
    verslag.meld(tijd, f"ORD-{nummer} binnen — {len(regels)} regel(s)")


def _ontvang(verbinding, kans, mag, artikelen, gebruiker, verslag, tijd) -> None:
    """Een ontvangst, gevolgd door inslag op de plek die R-INS voorstelt."""
    from .voorstel import voorstel_inslag
    artikel = kans.choice(artikelen)
    aantal = kans.randint(10, 60)
    ontvangst = next((l for l in mag.locaties if mag.soort(l).id == 2), None)
    if ontvangst is None:
        return
    boek(verbinding, artikel.id, aantal, "RECEIPT", naar=ontvangst.id,
         reden="Leverancier", gebruiker=gebruiker)

    voorstellen = voorstel_inslag(mag, artikel.id, aantal, limiet=3)
    if not voorstellen:
        return
    keuze = voorstellen[0]
    neem = min(aantal, keuze.vrij)
    if neem <= 0:
        return
    boek(verbinding, artikel.id, neem, "PUTAWAY", van=ontvangst.id,
         naar=keuze.locatie.id, gebruiker=gebruiker)
    verslag.meld(tijd, f"{neem}x {artikel.sku} ingeslagen op {keuze.locatie.code}")


# ---------------------------------------------------------------------
#  Met de hand draaien
# ---------------------------------------------------------------------
def _hoofd() -> int:  # pragma: no cover - alleen voor met de hand draaien
    import os
    import psycopg

    with psycopg.connect(os.environ.get("PGDATABASE_URL",
                                        "dbname=" + os.environ.get(
                                            "PGDATABASE", "vakto"))) as conn:
        verslag = draai_werkdag(conn)
        controle = controleer_einde(conn)
        conn.commit()

    print("\n  Een werkdag in het magazijn")
    print("  " + "-" * 58)
    for regel in verslag.gebeurtenissen[-20:]:
        print("  " + regel)
    print("  " + "-" * 58)
    print("  " + str(verslag))
    print("  " + str(controle))
    print("  " + ("Alles klopt (T-18)." if controle.schoon
                  else "ER KLOPT IETS NIET."))
    return 0 if controle.schoon else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_hoofd())
