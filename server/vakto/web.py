"""De webserver (stap 8) — het enige bestand dat van HTTP weet.

Drie lagen, en ze weten alleen van elkaar wat ze moeten weten:

    opslag.py    haalt op en schrijft weg   (kent SQL)
    schermen.py  tekent HTML                (kent geen database)
    web.py       verbindt de twee           (kent HTTP)

Daaronder ligt de rekenkern, die van geen van drieën iets weet. Dat is
dezelfde grens als R-BOEK-03: de database bewaakt de integriteit, Python
rekent, en het scherm laat zien wat eruit komt.

Geen framework. `http.server` uit de standaardbibliotheek doet precies
wat hier nodig is, en een pakket dat over drie jaar niet meer
onderhouden wordt kan hier niet stukgaan. Voor één magazijn met een
handvol schermen is dat ruim genoeg; komt er echt druk op, dan zet je er
een gunicorn of een nginx voor zonder dat er aan de schermen iets
verandert.

Elke handeling is een POST met daarna een omleiding (303). Dat is geen
mode maar zelfbehoud: wie na een pick op F5 drukt, boekt anders nog een
keer af. Na de omleiding staat de melding in de URL — daar is geen
koekje voor nodig.

Sinds stap 9 zit er een inlog omheen (R-GEB). Elke aanvraag zoekt eerst
op wie er aan de knoppen zit en of zijn rang genoeg is voor dit pad —
een GET net zo goed als een POST, want een knop weglaten is opmaak en
geen beveiliging. De scanstand hangt aan de sessie van die ene persoon,
zodat twee mensen tegelijk op dezelfde picklijst kunnen werken zonder
elkaars stand te zien.

Starten:

    python3 -m vakto.web                 # localhost:8000, database vakto
    python3 -m vakto.web --poort 8080 --db "dbname=vakto user=jan"

De eerste keer is de gebruikerstabel leeg en vraagt het eerste scherm om
een beheerder aan te maken (R-GEB-08). Daarna is die weg dicht.
"""

from __future__ import annotations

import argparse
import mimetypes
import sys
import threading
import traceback
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import gebruikers, opslag, schermen
from .opslag import Boekfout
from .scannen import Inslagopdracht, Pickopdracht, Scanner, Telopdracht
from .maten import maatklasse_van_locatie
from .voorstel import voorstel_inslag

# De opmaak komt uit de demo. Eén stijlbestand voor beide versies, zodat
# een verschil in beeld een verschil in gegevens is en niet in CSS.
STIJL = Path(__file__).resolve().parent.parent.parent / "demo" / "stijl.css"

# R-BASIS-07. Nooit een lijst zonder limiet, ook niet op een scherm.
LIMIET = 300


# ---------------------------------------------------------------------
#  Wat er teruggaat
# ---------------------------------------------------------------------
@dataclass
class Reactie:
    lijf: bytes | str = ""
    status: int = 200
    soort: str = "text/html; charset=utf-8"
    naar: str | None = None          # gevuld bij een omleiding
    # (naam, waarde, maximale leeftijd in seconden). Een lege waarde met
    # leeftijd 0 wist het koekje.
    koekje: tuple[str, str, int] | None = None


def omleiding(pad: str, tekst: str = "", soort: str = "") -> Reactie:
    """303 See Other: na een POST hoort de browser een GET te doen.

    De melding reist mee in de URL. Dat is met opzet: geen sessie, geen
    koekje, en je kunt het scherm dat je ziet gewoon doorsturen.
    """
    if tekst:
        pad += ("&" if "?" in pad else "?") + "m=" + quote(tekst)
        if soort:
            pad += "&s=" + quote(soort)
    return Reactie(status=303, naar=pad)


# ---------------------------------------------------------------------
#  De scanstand
#
#  Eén per ingelogde gebruiker (R-GEB-05). Twee mensen op dezelfde
#  picklijst moeten allebei hun eigen halve handeling kunnen hebben; wie
#  dat deelt, ziet de ander midden in zijn scan de stap veranderen.
#
#  Wat hier staat is bewust alleen de stánd van de handeling — welke
#  taak, welke stap, wat er al gescand is. Voorraad en picklijst komen
#  bij elke aanvraag opnieuw uit de database, want die zijn van iedereen.
#  Dit mag daarom in het geheugen staan: raakt het kwijt bij een
#  herstart, dan begint iemand opnieuw bij de eerste stap en is er niets
#  verloren. De inlog zelf staat wél in de database, juist omdát die een
#  herstart moet overleven.
# ---------------------------------------------------------------------
@dataclass
class Sessie:
    klant: str = "Vakto"
    taak: str = "PICKEN"
    gebruiker: str | None = None
    gescand: list[str] = field(default_factory=list)
    # Regels die iemand heeft overgeslagen (R-SCAN-04). Overslaan is
    # geen manco: de regel gaat achteraan en moet daar blijven, ook als
    # de picklijst tussendoor opnieuw uit de database komt.
    achteraan: list[int] = field(default_factory=list)
    # De halve handeling: locatie gescand, artikel nog niet. Bij een
    # browser is elke aanvraag op zichzelf, dus wat de scanner tussen
    # twee scans in onthoudt moet hier staan. Het is bewust alleen de
    # stand van de handeling — voorraad en picklijst komen elke keer
    # opnieuw uit de database.
    stap: str = ""
    locatie_id: int | None = None
    product_id: int | None = None
    aantal: int = 0
    # De stand van het importscherm (R-IMP). Hier omdat het moet: de
    # bestanden staan tussen "kiezen" en "overnemen" nergens anders, en
    # je wilt ze niet bij elke correctie opnieuw laten uploaden. Ze gaan
    # weg zodra de import gedaan is of iemand uitlogt.
    imp: "Import | None" = None


@dataclass
class Import:
    """Wat er tussen kiezen en overnemen in de lucht hangt."""
    bestanden: dict = field(default_factory=dict)     # soort -> Bestand
    kolommen: dict = field(default_factory=dict)      # soort -> {veld: index}
    eenheden: object = None
    standaard: object = None

    def __post_init__(self):
        from .inlezen import Eenheden, Standaard
        self.eenheden = self.eenheden or Eenheden()
        self.standaard = self.standaard or Standaard()


def _scanner(verbinding, sessie: Sessie) -> Scanner:
    """Bouwt de scanner opnieuw op uit de huidige toestand.

    De scanner bewaart zelf geen voorraad: hij krijgt een momentopname
    mee. Die opnieuw ophalen bij elke aanroep is niet zuinig, maar wel
    eerlijk — twee mensen op dezelfde picklijst zien anders elkaars werk
    niet.
    """
    regels = opslag.picklijst(verbinding, limiet=LIMIET)
    if sessie.achteraan:
        volgorde = {a: i for i, a in enumerate(sessie.achteraan)}
        regels.sort(key=lambda r: volgorde.get(r.allocation_id, -1))
    scanner = Scanner(mag=opslag.laad_magazijn(verbinding),
                      pickregels=regels,
                      inst=opslag.laad_instellingen(verbinding),
                      taak=sessie.taak)
    scanner.gescand = sessie.gescand
    scanner.gebruiker = sessie.gebruiker

    # De handeling waar iemand middenin zat weer instellen. Alleen als
    # er nog werk is: staat de scanner op KLAAR, dan is de stap van
    # daarnet niet meer waar.
    from .scannen import STAPPEN
    if sessie.stap and sessie.stap in STAPPEN[scanner.taak] \
            and scanner.stap != "KLAAR":
        scanner.stap = sessie.stap
        scanner.locatie_id = sessie.locatie_id
        scanner.product_id = sessie.product_id
        scanner.aantal = sessie.aantal
    return scanner


def _bewaar(sessie: Sessie, scanner: Scanner) -> None:
    sessie.taak = scanner.taak
    sessie.gescand = scanner.gescand
    sessie.gebruiker = scanner.gebruiker
    sessie.stap = scanner.stap
    sessie.locatie_id = scanner.locatie_id
    sessie.product_id = scanner.product_id
    sessie.aantal = scanner.aantal


class Standen:
    """De scanstanden, één per ingelogde gebruiker.

    Meer houdt de webserver niet bij. Wie er ingelogd is staat in de
    database (R-GEB-05); dit is alleen waar iemand in zijn handeling was
    toen hij de vorige knop indrukte.
    """

    def __init__(self, klant: str = "Vakto"):
        self.klant = klant
        self._per_gebruiker: dict[int, Sessie] = {}
        # Zodra er één gebruiker is, kan het er nooit weer nul worden:
        # iemand gaat uit dienst, hij verdwijnt niet. Daarom hoeft die
        # telling maar één keer (R-GEB-08).
        self._opgezet = False

    def van(self, gebruiker) -> Sessie:
        stand = self._per_gebruiker.get(gebruiker.id)
        if stand is None:
            stand = Sessie(klant=self.klant)
            self._per_gebruiker[gebruiker.id] = stand
        # R-GEB-06. Wie het boekt staat erbij, tot in journal.gebruiker.
        stand.gebruiker = gebruiker.naam
        return stand

    def vergeet(self, gebruiker_id: int) -> None:
        self._per_gebruiker.pop(gebruiker_id, None)

    def opgezet(self, verbinding) -> bool:
        if not self._opgezet:
            self._opgezet = opslag.aantal_gebruikers(verbinding) > 0
        return self._opgezet


# ---------------------------------------------------------------------
#  De router
#
#  Los van de webserver, zodat een test een heel scherm kan opvragen
#  zonder dat er een socket aan te pas komt (tests/test_schermen.py).
# ---------------------------------------------------------------------
def behandel(verbinding, standen: Standen, methode: str, pad: str,
             vraag: dict, formulier: dict, token: str | None = None,
             vanaf: str | None = None) -> Reactie:
    """Eén aanvraag, van koekje tot bladzijde.

    De volgorde is de volgorde van R-GEB: eerst kijken of er überhaupt
    een beheerder is, dan wie er aan de knoppen zit, dan of hij hier mag
    komen, en pas dan het scherm zelf. Elke aanvraag opnieuw — een GET
    net zo goed als een POST, want een knop weglaten is opmaak en geen
    beveiliging (R-GEB-02).
    """
    # R-GEB-08. Een leeg systeem laat je één keer een beheerder maken.
    if not standen.opgezet(verbinding):
        if pad == "/opzetten":
            return (_opzetten_post(verbinding, standen, formulier, vanaf)
                    if methode == "POST"
                    else Reactie(schermen.kaal("Eerste beheerder",
                                               schermen.eerste_beheerder())))
        return omleiding("/opzetten")

    gebruiker = opslag.wie_is(verbinding, token)

    if gebruiker is None:
        if pad == "/inloggen":
            if methode == "POST":
                return _inloggen_post(verbinding, formulier, vanaf)
            return Reactie(schermen.kaal(
                "Inloggen",
                schermen.inloggen(
                    terug=_een(vraag, "terug"),
                    badge_mag=opslag.laad_instellingen(verbinding).aan(
                        "inlog.badge_voor_scanner")),
                melding=_melding(vraag)))
        # Waar iemand heen wilde onthouden we, zodat hij na het inloggen
        # niet nog een keer hoeft te zoeken.
        terug = pad if methode == "GET" and pad != "/" else ""
        return omleiding("/inloggen"
                         + (("?terug=" + quote(terug, safe=""))
                            if terug else ""))

    if pad == "/uitloggen":
        opslag.meld_af(verbinding, token)
        verbinding.commit()
        standen.vergeet(gebruiker.id)
        return Reactie(status=303, naar="/inloggen?m=" + quote("Uitgelogd."),
                       koekje=(gebruikers.KOEKJE, "", 0))

    if pad == "/inloggen":
        return omleiding(gebruikers.startpad(gebruiker.rol))

    if not gebruiker.mag(pad):
        # Op je eigen beginscherm hoor je geen weigering te krijgen; je
        # hoort daar gewoon niet te beginnen. Een magazijnmedewerker die
        # "/" opvraagt gaat naar het pickscherm.
        if pad == "/":
            return omleiding(gebruikers.startpad(gebruiker.rol))
        nodig = _rolnaam_voor(pad)
        return Reactie(schermen.bladzijde(
            "Geen toegang", schermen.geweigerd(gebruiker, pad, nodig),
            pad=gebruikers.startpad(gebruiker.rol), klant=standen.klant,
            gebruiker=gebruiker), status=403)

    sessie = standen.van(gebruiker)
    if methode == "POST":
        return _post(verbinding, sessie, pad, formulier, gebruiker)
    return _get(verbinding, sessie, pad, vraag, gebruiker)


def _rolnaam_voor(pad: str) -> str:
    """Welke rol heb je hier minimaal voor nodig?"""
    nodig = gebruikers.RECHTEN.get(gebruikers.hoofdpad(pad), 1)
    for rol, (naam, _kort, rang) in gebruikers.ROLLEN.items():
        if rang == nodig:
            return naam
    return "een hogere rol"


def _melding(vraag: dict) -> tuple[str, str] | None:
    tekst = _een(vraag, "m")
    return (_een(vraag, "s"), tekst) if tekst else None


# ---------------------------------------------------------------------
#  Binnenkomen (R-GEB-03, R-GEB-07, R-GEB-08)
# ---------------------------------------------------------------------
def _aangemeld(aanmelding, terug: str = "") -> Reactie:
    """Het koekje zetten en doorsturen naar waar iemand heen wilde."""
    duur = 12 * 3600
    wie = aanmelding.gebruiker
    # Twee dingen moeten kloppen aan waar we hem heen sturen:
    #
    #   1. Het moet een pad binnen dit systeem zijn. Zonder die controle
    #      kun je iemand met een gepreparerde link na het inloggen op een
    #      andere site laten uitkomen.
    #   2. Hij moet er ook mógen komen. Iemand die net is ingelogd hoort
    #      niet meteen tegen "hier mag je niet bij" aan te lopen; dat
    #      leest als "het inloggen is mislukt".
    heen = terug if terug.startswith("/") and not terug.startswith("//") else ""
    if heen and not wie.mag(heen):
        heen = ""
    if not heen:
        heen = "/scan" if wie.alleen_scanner else gebruikers.startpad(wie.rol)
    return Reactie(status=303, naar=heen,
                   koekje=(gebruikers.KOEKJE, aanmelding.token, duur))


def _inloggen_post(verbinding, form: dict, vanaf: str | None) -> Reactie:
    terug = _een(form, "terug")
    if _een(form, "soort") == "badge":
        aanmelding = opslag.meld_aan_met_badge(
            verbinding, _een(form, "badge"), vanaf=vanaf)
    else:
        aanmelding = opslag.meld_aan(
            verbinding, _een(form, "gebruikersnaam"),
            _een(form, "wachtwoord"), vanaf=vanaf)
    # Ook een mislukte poging wordt vastgelegd, dus committen hoort ook
    # dan (R-GEB-07). Zonder dat telt het slot niets.
    verbinding.commit()
    if not aanmelding.gelukt:
        return Reactie(schermen.kaal(
            "Inloggen",
            schermen.inloggen(fout=aanmelding.fout,
                              naam=_een(form, "gebruikersnaam"),
                              terug=terug)), status=401)
    return _aangemeld(aanmelding, terug)


def _opzetten_post(verbinding, standen: Standen, form: dict,
                   vanaf: str | None) -> Reactie:
    """R-GEB-08. De eerste beheerder maakt zichzelf aan, één keer."""
    naam = _een(form, "naam").strip()
    gnaam = _een(form, "gebruikersnaam").strip()
    ww = _een(form, "wachtwoord")

    def terug(fout: str) -> Reactie:
        return Reactie(schermen.kaal(
            "Eerste beheerder",
            schermen.eerste_beheerder(fout, naam, gnaam)), status=400)

    if not naam or not gnaam:
        return terug("Vul je naam en een gebruikersnaam in.")
    if ww != _een(form, "nogmaals"):
        return terug("De twee wachtwoorden zijn niet gelijk.")
    klacht = gebruikers.zwak(ww)
    if klacht:
        return terug(klacht)
    try:
        opslag.bewaar_gebruiker(verbinding, gnaam, naam, "ADMIN", ww,
                                _een(form, "badge") or None)
        aanmelding = opslag.meld_aan(verbinding, gnaam, ww, vanaf=vanaf)
        verbinding.commit()
    except Boekfout as e:
        verbinding.rollback()
        return terug(str(e))
    standen._opgezet = True
    return _aangemeld(aanmelding)


def _een(waarden: dict, naam: str, standaard: str = "") -> str:
    lijst = waarden.get(naam) or []
    return lijst[0] if lijst else standaard


def _nummer(waarden: dict, naam: str, standaard: int = 0) -> int:
    try:
        return int(_een(waarden, naam, str(standaard)))
    except (TypeError, ValueError):
        return standaard


def _tellers(cijfers: dict) -> dict:
    return {"/taken": cijfers.get("Open taken", 0),
            "/orders": cijfers.get("Open orders", 0),
            "/picken": cijfers.get("Pickregels", 0),
            "/meten": cijfers.get("Te meten", 0)}


# ------------------------------------------------------------------ GET
def _get(verbinding, sessie: Sessie, pad: str, vraag: dict,
         gebruiker=None) -> Reactie:
    melding = _melding(vraag)
    cijfers = opslag.cijfers(verbinding)

    def blad(titel: str, inhoud: str, aan: str = pad, **rest) -> Reactie:
        return Reactie(schermen.bladzijde(
            titel, inhoud, pad=aan, melding=melding, klant=sessie.klant,
            tellers=_tellers(cijfers), gebruiker=gebruiker, **rest))

    if pad == "/":
        return blad("Dashboard", schermen.dashboard(
            cijfers, opslag.systeemlog(verbinding, 40)))

    if pad == "/taken":
        return blad("Taken", schermen.werklijst(
            opslag.werklijst(verbinding, LIMIET)))

    if pad == "/orders":
        return blad("Orders", schermen.orders(
            opslag.orderlijst(verbinding, LIMIET)))

    if pad.startswith("/orders/"):
        oid = _naar_getal(pad.rsplit("/", 1)[-1])
        order = oid and opslag.laad_order(verbinding, oid)
        if not order:
            return Reactie(schermen.bladzijde(
                "Niet gevonden", "<h1>Deze order bestaat niet</h1>"
                '<p class="lead">Misschien is hij verwijderd, of klopt het '
                'nummer in de adresbalk niet.</p><p><a href="/orders">Terug '
                "naar de orders</a></p>", pad="/orders",
                klant=sessie.klant, tellers=_tellers(cijfers),
                gebruiker=gebruiker), status=404)
        kop = (order.id, order.nummer, order.klant, order.status, order.prio,
               order.colli, order.gewicht_g)
        return blad(order.nummer, schermen.order(
            kop, opslag.orderregels_scherm(verbinding, oid),
            opslag.toewijzingen(verbinding, oid)),
            aan="/orders", kruimel=order.nummer)

    if pad == "/picken":
        return blad("Picken", schermen.picken(
            opslag.picklijst(verbinding, limiet=LIMIET)))

    if pad == "/scan":
        scanner = _scanner(verbinding, sessie)
        return Reactie(schermen.bladzijde(
            "Scanmodus", schermen.scanscherm(scanner), pad="/scan",
            melding=melding, klant=sessie.klant, lichaam="scanmodus",
            gebruiker=gebruiker))

    if pad == "/inslag":
        return blad("Inslag", _inslagscherm(verbinding, vraag))

    if pad == "/meten":
        return blad("Opmeten", schermen.meetlijst(opslag.meetlijst(verbinding, LIMIET)))

    if pad == "/locaties":
        return blad("Locaties", schermen.locaties(
            opslag.locatielijst(verbinding, LIMIET)))

    if pad == "/artikelen":
        return blad("Artikelen", schermen.artikelen(
            opslag.artikellijst(verbinding, LIMIET)))

    if pad == "/gebruikers":
        return blad("Gebruikers", schermen.gebruikers(
            opslag.gebruikerslijst(verbinding, LIMIET),
            gebruiker.id if gebruiker else None))

    if pad == "/instellingen":
        # De klachten reizen mee in de URL, zodat ze na de omleiding bij
        # de juiste regel komen te staan in plaats van als één zin
        # bovenaan (R-INST-01).
        klachten = {}
        for regel in (_een(vraag, "fout") or "").split("|"):
            sleutel, _, tekst = regel.partition(": ")
            if sleutel and tekst:
                klachten[sleutel] = tekst
        return blad("Instellingen", schermen.instellingen(
            opslag.instellingen_beheer(verbinding), klachten))

    if pad == "/eigen":
        return blad("Eigen gegevens", _importscherm(verbinding, sessie))

    if pad == "/etiketten":
        inst = opslag.laad_instellingen(verbinding)
        per_blad = int(inst.getal("ui.rows_per_page"))
        vanaf = max(0, _nummer(vraag, "vanaf"))
        return blad("Etiketten", schermen.etiketten(
            opslag.etikettenlijst(verbinding, per_blad, vanaf), vanaf,
            opslag.etikettenaantal(verbinding), per_blad))

    if pad == "/optimalisatie":
        mag = opslag.laad_magazijn(verbinding)
        inst = opslag.laad_instellingen(verbinding)
        adviezen, plekken, snel = opslag.laad_adviezen(verbinding, mag, inst)
        return blad("Optimalisatie", schermen.optimalisatie(
            opslag.laad_taken(verbinding), adviezen, plekken, snel,
            {a.id: a for a in mag.artikelen},
            {l.id: l for l in mag.locaties}, inst))

    if pad == "/ik":
        return blad("Wie ben ik", schermen.ikzelf(gebruiker),
                    aan=gebruikers.startpad(gebruiker.rol),
                    kruimel=gebruiker.naam)

    return Reactie(schermen.bladzijde(
        "Niet gevonden", "<h1>Dit scherm bestaat niet</h1>"
        '<p class="lead">Kijk het adres na, of kies links een scherm.</p>',
        pad=gebruikers.startpad(gebruiker.rol) if gebruiker else "/",
        klant=sessie.klant, tellers=_tellers(cijfers),
        gebruiker=gebruiker), status=404)


def _naar_getal(tekst: str) -> int | None:
    try:
        return int(tekst)
    except (TypeError, ValueError):
        return None


def _inslagscherm(verbinding, vraag: dict) -> str:
    """R-INS. Het voorstel komt uit de rekenkern, niet uit een query."""
    keuze = opslag.artikelkeuze(verbinding, LIMIET)
    gekozen = _nummer(vraag, "product") or (keuze[0][0] if keuze else None)
    aantal = max(1, _nummer(vraag, "aantal", 24))
    voorstellen = []
    maten = {}
    if gekozen:
        mag = opslag.laad_magazijn(verbinding)
        inst = opslag.laad_instellingen(verbinding)
        voorstellen = voorstel_inslag(mag, gekozen, aantal, inst)
        maten = {loc.id: maatklasse_van_locatie(loc)
                 for loc in mag.locaties}
    return schermen.inslag(keuze, gekozen, aantal, voorstellen, maten)


# ----------------------------------------------------------------- POST
def _post(verbinding, sessie: Sessie, pad: str, form: dict,
          gebruiker=None) -> Reactie:
    """Elke handeling. Boekt, doet de zelfcontrole, en leidt om.

    De zelfcontrole draait na elke mutatie (R-ZC). Dat mag: hij trekt
    alleen conclusies uit de huidige toestand, dus twee keer draaien
    verandert niets. Het scheelt wel dat je nooit een scherm ziet waarop
    werk staat dat allang niet meer nodig is.
    """
    try:
        if pad == "/taken":
            return _taak_afmelden(verbinding, sessie, form)
        if pad.startswith("/orders/"):
            return _orderactie(verbinding, sessie, pad, form)
        if pad == "/picken":
            return _pick_afmelden(verbinding, sessie, form)
        if pad == "/scan":
            return _scanactie(verbinding, sessie, form)
        if pad == "/meten":
            return _meting(verbinding, sessie, form)
        if pad == "/gebruikers":
            return _gebruikersactie(verbinding, form, gebruiker)
        if pad == "/instellingen":
            return _instellingen(verbinding, form, gebruiker)
        if pad == "/eigen":
            return _importactie(verbinding, sessie, form, gebruiker)
        if pad == "/optimalisatie":
            return _adviesactie(verbinding, form, gebruiker)
    except Boekfout as e:
        # De database weigerde. Dat is geen storing maar een antwoord:
        # laat de tekst zien die eruit kwam, want die is voor een mens
        # geschreven (zie boeken.sql).
        verbinding.rollback()
        return omleiding(pad, str(e), "fout")
    return omleiding("/", "Deze handeling bestaat niet.", "fout")


def _taak_afmelden(verbinding, sessie: Sessie, form: dict) -> Reactie:
    taak = _nummer(form, "taak")
    aantal = _nummer(form, "aantal") or None
    opslag.voer_taak_uit(verbinding, taak, aantal, sessie.gebruiker)
    opslag.draai_zelfcontrole(verbinding)
    verbinding.commit()
    return omleiding("/taken", "Taak afgemeld.")


def _orderactie(verbinding, sessie: Sessie, pad: str, form: dict) -> Reactie:
    oid = _naar_getal(pad.rsplit("/", 1)[-1])
    actie = _een(form, "actie")
    terug = "/orders/" + str(oid)

    if actie == "reserveer":
        status = opslag.reserveer(verbinding, oid, sessie.gebruiker)
        opslag.draai_zelfcontrole(verbinding)
        verbinding.commit()
        if status == "WACHT_OP_VOORRAAD":
            return omleiding(terug, "Niet alles is er: de order wacht op "
                             "voorraad. Wat er wél was, staat vast.",
                             "waarschuw")
        return omleiding(terug, "Alles gereserveerd.")

    if actie == "vrijgeven":
        n = opslag.geef_vrij(verbinding, oid)
        verbinding.commit()
        if not n:
            return omleiding(terug, "Er viel niets vrij te geven.",
                             "waarschuw")
        return omleiding(terug, f"{n} pickregel(s) klaargezet.")

    if actie == "verzenden":
        mag = opslag.laad_magazijn(verbinding)
        inpak = opslag.pak_in(verbinding, oid,
                              {a.id: a for a in mag.artikelen},
                              opslag.laad_instellingen(verbinding))
        if inpak is None:
            verbinding.rollback()
            return omleiding(terug, "Deze order is nog niet klaar met picken.",
                             "waarschuw")
        opslag.verzend(verbinding, oid)
        opslag.draai_zelfcontrole(verbinding)
        verbinding.commit()
        colli = f"{inpak.colli} collo" if inpak.colli == 1 else \
            f"{inpak.colli} colli"
        return omleiding(terug, f"Verzonden: {colli}, "
                         f"{schermen.getal(inpak.gewicht_g)} g.")

    return omleiding(terug, "Onbekende handeling.", "fout")


def _pick_afmelden(verbinding, sessie: Sessie, form: dict) -> Reactie:
    regel = _nummer(form, "regel")
    aantal = _nummer(form, "aantal")
    stand = opslag.bevestig_pick(verbinding, regel, aantal, sessie.gebruiker)
    opslag.draai_zelfcontrole(verbinding)
    verbinding.commit()
    if stand == "MANCO":
        return omleiding("/picken", "Manco vastgelegd. De reservering is "
                         "vrijgegeven en er staat een teltaak klaar.",
                         "waarschuw")
    return omleiding("/picken", "Afgemeld.")


def _meting(verbinding, sessie: Sessie, form: dict) -> Reactie:
    """R-MEET-01 t/m R-MEET-03. Een meting is een regel erbij, nooit een
    kolom die je overschrijft."""
    pid = _nummer(form, "product")
    maten = [_nummer(form, k) for k in ("l", "w", "h", "g")]
    if pid <= 0 or min(maten) <= 0:
        return omleiding("/meten", "Vul alle vier de waarden in, groter dan "
                         "nul.", "fout")
    mag = opslag.laad_magazijn(verbinding)
    _, melding = opslag.schrijf_meting(
        verbinding, mag, pid, *maten, bron="CONTROL",
        inst=opslag.laad_instellingen(verbinding))
    opslag.draai_zelfcontrole(verbinding)
    verbinding.commit()
    if melding is not None:
        return omleiding("/meten", melding.gevolg, "waarschuw")
    return omleiding("/meten", "Maat vastgelegd.")


# ---------------------------------------------------------------------
#  Instellingen (R-INST-01)
# ---------------------------------------------------------------------
def _instellingen(verbinding, form: dict, gebruiker) -> Reactie:
    """Het hele formulier in één keer.

    Alles-of-niets zou hier averechts werken: wie één veld verkeerd
    invult, wil niet dat de andere veertien ook terugvallen. De klachten
    komen mee terug in de URL, zodat ze bij de juiste regel komen te
    staan.
    """
    from .instellingen import SOORT

    waarden = {s: _een(form, s) for s in SOORT if s in form}
    naam = gebruiker.naam if gebruiker else None
    gewijzigd, klachten = opslag.zet_instellingen(verbinding, waarden, naam)
    verbinding.commit()

    if klachten:
        return omleiding("/instellingen?fout=" + quote("|".join(klachten)),
                         "Niet alles kon worden opgeslagen; kijk de rode "
                         "regels na.", "fout")
    if not gewijzigd:
        return omleiding("/instellingen", "Er was niets veranderd.")
    return omleiding("/instellingen",
                     f"{gewijzigd} instelling(en) opgeslagen.")


# ---------------------------------------------------------------------
#  Eigen gegevens (R-IMP)
#
#  Vier dingen kunnen er in één POST binnenkomen: een bestand, een
#  kolomkeuze, een eenheid en een standaardmaat. Ze worden alle vier
#  toegepast en daarna wordt er opnieuw gecontroleerd — dat is goedkoop
#  (er wordt niets weggeschreven) en het scheelt de gebruiker een knop.
# ---------------------------------------------------------------------
SOORTEN = ("locaties", "artikelen", "voorraad")


def _importstand(sessie: Sessie) -> Import:
    if sessie.imp is None:
        sessie.imp = Import()
    return sessie.imp


def _rapport(imp: Import):
    from .inlezen import controleer
    return controleer(
        imp.bestanden.get("locaties"), imp.kolommen.get("locaties"),
        imp.bestanden.get("artikelen"), imp.kolommen.get("artikelen"),
        imp.bestanden.get("voorraad"), imp.kolommen.get("voorraad"),
        eenheden=imp.eenheden, standaard=imp.standaard)


def _importscherm(verbinding, sessie: Sessie) -> str:
    from .inlezen import voorbeeldmaat
    imp = _importstand(sessie)
    rapport = _rapport(imp) if imp.bestanden else None
    voorbeelden = {
        s: voorbeeldmaat(imp.bestanden.get(s), imp.kolommen.get(s, {}), s,
                         imp.eenheden)
        for s in ("locaties", "artikelen")}
    return schermen.eigen(imp.bestanden, imp.kolommen, imp.eenheden,
                          imp.standaard, rapport, voorbeelden,
                          al_geboekt=opslag.al_geboekt(verbinding))


def _importactie(verbinding, sessie: Sessie, form: dict, gebruiker) -> Reactie:
    from .inlezen import Leesfout, herken_kolommen, lees_inhoud, raad_eenheden

    imp = _importstand(sessie)
    nieuw_bestand = False

    # 1. Bestanden. `form` draagt ze als (naam, inhoud) onder dezelfde
    #    sleutel als het soort.
    for soort in SOORTEN:
        opgestuurd = form.get("bestand." + soort)
        if not opgestuurd:
            continue
        naam, inhoud = opgestuurd[0]
        if not inhoud:
            continue
        try:
            imp.bestanden[soort] = lees_inhoud(inhoud, naam)
        except Leesfout as e:
            return omleiding("/eigen", str(e), "fout")
        imp.kolommen[soort] = herken_kolommen(soort, imp.bestanden[soort].kop)
        nieuw_bestand = True

    # 2. Eenheden opnieuw raden zodra er een bestand bij komt, maar niet
    #    daarna: wie hem met de hand omzet, wil niet dat de volgende
    #    handeling hem terugdraait (R-IMP-03).
    if nieuw_bestand:
        imp.eenheden = raad_eenheden(
            imp.bestanden.get("locaties"), imp.kolommen.get("locaties"),
            imp.bestanden.get("artikelen"), imp.kolommen.get("artikelen"))
    else:
        for veld in ("loc_maat", "art_maat", "loc_gew", "art_gew"):
            waarde = _een(form, "eenheid." + veld)
            if waarde:
                setattr(imp.eenheden, veld, waarde)

    # 3. Kolomkeuzes met de hand. R-IMP-02: de uitkomst is altijd te
    #    corrigeren, anders is "we raden het" een loze belofte.
    if not nieuw_bestand:
        for soort in SOORTEN:
            if soort not in imp.bestanden:
                continue
            gekozen = {}
            for sleutel, waarden in form.items():
                begin = "kolom." + soort + "."
                if not sleutel.startswith(begin) or not waarden:
                    continue
                if waarden[0] != "":
                    gekozen[sleutel[len(begin):]] = int(waarden[0])
            if gekozen or any(k.startswith("kolom." + soort + ".")
                              for k in form):
                imp.kolommen[soort] = gekozen

    # 4. De standaardmaat voor locaties zonder afmeting (R-IMP-05).
    for veld in ("l_mm", "w_mm", "h_mm", "max_g"):
        waarde = _nummer(form, "std." + veld)
        if waarde > 0:
            setattr(imp.standaard, veld, waarde)

    if _een(form, "actie") != "overnemen":
        return omleiding("/eigen")

    # 5. Overnemen. Pas hier raakt de database iets.
    rapport = _rapport(imp)
    if not rapport.klaar:
        return omleiding("/eigen", "Er zijn geen bruikbare locaties. Zonder "
                         "locaties kan er niets.", "fout")
    uit = opslag.neem_over(verbinding, rapport,
                           gebruiker=gebruiker.naam if gebruiker else None)
    opslag.draai_zelfcontrole(verbinding)
    verbinding.commit()
    sessie.imp = None
    samen = ", ".join(f"{k} {w}" for k, w in uit.items())
    return omleiding("/", "Overgenomen: " + samen + ".")


# ---------------------------------------------------------------------
#  De twee adviezen (R-OPT-05 en R-OPT-06)
#
#  Dit zijn de enige twee knoppen in het hele systeem waar een mens iets
#  beslist wat het systeem niet zelf doet. Hoeveel je op de vloer wilt
#  hebben en welk vak je daarvoor vrijmaakt zijn besluiten over ruimte en
#  werkkapitaal — die horen niet vanzelf te gaan.
# ---------------------------------------------------------------------
def _adviesactie(verbinding, form: dict, gebruiker) -> Reactie:
    actie = _een(form, "actie")
    pid = _nummer(form, "product")
    naam = gebruiker.naam if gebruiker else None
    mag = opslag.laad_magazijn(verbinding)
    artikel = mag.artikel(pid)
    if artikel is None:
        return omleiding("/optimalisatie", "Dat artikel bestaat niet.", "fout")

    if actie == "drempel":
        opslag.zet_drempel(verbinding, pid, _nummer(form, "min"),
                           _nummer(form, "max"), gebruiker=naam)
        verbinding.commit()
        return omleiding("/optimalisatie", f"De drempel van {artikel.sku} "
                         f"staat nu op {_nummer(form, 'min')}.")

    if actie == "negeer":
        opslag.zet_drempel(verbinding, pid, akkoord=True, gebruiker=naam)
        verbinding.commit()
        return omleiding("/optimalisatie", f"{artikel.sku}: advies genegeerd, "
                         "dit artikel wordt niet meer voorgesteld.")

    if actie == "pickplek":
        _, plekken, _ = opslag.laad_adviezen(verbinding, mag)
        voorstel = next((v for v in plekken if v.product_id == pid), None)
        if voorstel is None:
            return omleiding("/optimalisatie", "Dit voorstel geldt niet meer; "
                             "de voorraad is inmiddels veranderd.", "waarschuw")
        opslag.maak_pickplektaak(verbinding, voorstel, artikel.sku, naam)
        verbinding.commit()
        naar = mag.locatie(voorstel.naar)
        code = naar.code if naar else str(voorstel.naar)
        return omleiding("/optimalisatie", f"Taak klaargezet: {voorstel.qty} "
                         f"st naar {code}.")

    return omleiding("/optimalisatie", "Onbekende handeling.", "fout")


def _gebruikersactie(verbinding, form: dict, ikzelf) -> Reactie:
    """R-GEB-01. Iemand toevoegen, een rol wijzigen, uit dienst zetten.

    Alleen rang 3 komt hier; dat is al getoetst in `behandel()`. Wat hier
    wél nog moet: je kunt jezelf niet uit dienst zetten. Anders sluit de
    enige beheerder zichzelf buiten en is er geen weg meer terug behalve
    met psql.
    """
    actie = _een(form, "actie")

    if actie == "nieuw":
        naam = _een(form, "naam").strip()
        gnaam = _een(form, "gebruikersnaam").strip()
        ww = _een(form, "wachtwoord")
        badge = _een(form, "badge").strip() or None
        if not naam or not gnaam:
            return omleiding("/gebruikers", "Vul een naam en een "
                             "gebruikersnaam in.", "fout")
        if not ww and not badge:
            return omleiding("/gebruikers", "Geef een wachtwoord of een "
                             "badge — zonder allebei kan hij nergens in.",
                             "fout")
        opslag.bewaar_gebruiker(verbinding, gnaam, naam,
                                _een(form, "rol", "OPERATOR"), ww or None,
                                badge)
        verbinding.commit()
        return omleiding("/gebruikers", f"{naam} toegevoegd.")

    uid = _nummer(form, "id")

    if actie == "rol":
        rol = _een(form, "rol")
        if rol not in gebruikers.ROLLEN:
            return omleiding("/gebruikers", "Onbekende rol.", "fout")
        if ikzelf is not None and uid == ikzelf.id and rol != ikzelf.rol:
            return omleiding("/gebruikers", "Je eigen rol verlagen kan niet: "
                             "dan sluit je jezelf buiten.", "waarschuw")
        rijen = opslag.gebruikerslijst(verbinding, LIMIET)
        wie = next((r for r in rijen if r[0] == uid), None)
        if wie is None:
            return omleiding("/gebruikers", "Die gebruiker bestaat niet.",
                             "fout")
        opslag.bewaar_gebruiker(verbinding, wie[2], wie[1], rol)
        verbinding.commit()
        return omleiding("/gebruikers",
                         f"{wie[1]} is nu {gebruikers.rolnaam(rol).lower()}.")

    if actie == "uit":
        if ikzelf is not None and uid == ikzelf.id:
            return omleiding("/gebruikers", "Jezelf uit dienst zetten kan "
                             "niet.", "waarschuw")
        naam = opslag.zet_gebruiker_uit(verbinding, uid)
        verbinding.commit()
        if naam is None:
            return omleiding("/gebruikers", "Die gebruiker bestaat niet.",
                             "fout")
        return omleiding("/gebruikers", f"{naam} staat uit dienst; zijn "
                         "sessies zijn ingetrokken.")

    return omleiding("/gebruikers", "Onbekende handeling.", "fout")


def _scanactie(verbinding, sessie: Sessie, form: dict) -> Reactie:
    """R-SCAN. De scanner rekent, deze functie boekt wat eruit komt."""
    actie = _een(form, "actie")
    scanner = _scanner(verbinding, sessie)

    if actie == "taak":
        antwoord = scanner.start(_een(form, "taak", "PICKEN"))
        sessie.achteraan = []
        _bewaar(sessie, scanner)
        return omleiding("/scan", antwoord.bericht, _kleur(antwoord))

    if actie == "overslaan":
        vorige = scanner.regel
        antwoord = scanner.sla_over()
        if vorige is not None:
            sessie.achteraan = [a for a in sessie.achteraan
                                if a != vorige.allocation_id]
            sessie.achteraan.append(vorige.allocation_id)
        _bewaar(sessie, scanner)
        return omleiding("/scan", antwoord.bericht, _kleur(antwoord))

    if actie == "scan":
        antwoord = scanner.scan(_een(form, "code"))
    elif actie == "bevestig":
        antwoord = scanner.bevestig(_een(form, "aantal", "0"))
    else:
        return omleiding("/scan", "Onbekende handeling.", "fout")

    _bewaar(sessie, scanner)
    if antwoord.opdracht is None:
        return omleiding("/scan", antwoord.bericht, _kleur(antwoord))

    _boek_opdracht(verbinding, sessie, antwoord.opdracht)
    opslag.draai_zelfcontrole(verbinding)
    verbinding.commit()
    return omleiding("/scan", antwoord.bericht, _kleur(antwoord))


def _boek_opdracht(verbinding, sessie: Sessie, opdracht) -> None:
    """De scanner raakt de database niet aan; hier gebeurt dat wel.

    Die scheiding is het hele punt van R-SCAN: de stappenlogica kun je
    zonder database natesten (tests/test_scannen.py), en wat er geboekt
    wordt loopt langs dezelfde functies als de rest van het systeem.
    """
    if isinstance(opdracht, Pickopdracht):
        opslag.bevestig_pick(verbinding, opdracht.allocation_id,
                             opdracht.aantal, sessie.gebruiker)
    elif isinstance(opdracht, Telopdracht):
        opslag.tel_locatie(verbinding, opdracht.location_id,
                           opdracht.product_id, opdracht.geteld,
                           sessie.gebruiker, opdracht.reden, opdracht.ref)
    elif isinstance(opdracht, Inslagopdracht):
        opslag.boek(verbinding, opdracht.product_id, opdracht.aantal,
                    "PUTAWAY", naar=opdracht.location_id,
                    reden="SCAN", gebruiker=sessie.gebruiker)


def _kleur(antwoord) -> str:
    return {"fout": "fout", "klaar": ""}.get(antwoord.soort, "")


# ---------------------------------------------------------------------
#  Een formulier met bestanden erin
#
#  Zelf ontleden en niet met `cgi.FieldStorage`: die module is in 3.11
#  afgekeurd en in 3.13 weg, en dan valt dit bestand om op een machine
#  waar iemand net Python heeft bijgewerkt. Het formaat is niet
#  ingewikkeld — het staat in RFC 7578 en past hieronder.
# ---------------------------------------------------------------------
MAX_FORM = 1_000_000            # een gewoon formulier
MAX_UPLOAD = 25_000_000         # drie klantbestanden, ruim genomen


def _kopwaarde(kop: str, naam: str) -> str:
    """Haalt `naam="..."` uit een Content-Disposition-regel."""
    merk = naam + '="'
    begin = kop.find(merk)
    if begin < 0:
        return ""
    begin += len(merk)
    eind = kop.find('"', begin)
    return kop[begin:eind] if eind > 0 else ""


def ontleed_multipart(ruw: bytes, soort: str) -> dict:
    """Geeft dezelfde vorm terug als `parse_qs`, met bestanden erbij.

    Gewone velden komen als {naam: [tekst]}; een bestand komt als
    {"bestand.<naam>": [(bestandsnaam, bytes)]}. Dat onderscheid staat in
    de sleutel en niet in het soort van de waarde, zodat een aanroeper
    nooit per ongeluk bytes voor tekst aanziet.
    """
    merk = "boundary="
    if merk not in soort:
        raise ValueError("geen boundary")
    grens = soort.split(merk, 1)[1].strip().strip('"')
    scheiding = b"--" + grens.encode("ascii")

    uit: dict[str, list] = {}
    for stuk in ruw.split(scheiding):
        stuk = stuk.strip(b"\r\n")
        if not stuk or stuk == b"--":
            continue
        kop, _, lijf = stuk.partition(b"\r\n\r\n")
        koptekst = kop.decode("utf-8", "replace")
        naam = _kopwaarde(koptekst, "name")
        if not naam:
            continue
        # Op de aanwezigheid van `filename`, niet op de inhoud ervan:
        # een leeg bestandsveld stuurt `filename=""` mee, en dat is nog
        # steeds een bestandsveld — geen tekstveld met een lege waarde.
        if 'filename="' in koptekst:
            bestandsnaam = _kopwaarde(koptekst, "filename")
            # Alleen de naam, nooit het pad. Een browser stuurt soms
            # "C:\\Users\\dennis\\locaties.csv" mee, en daar heeft de
            # server niets aan — behalve last.
            kaal = bestandsnaam.replace("\\", "/").rsplit("/", 1)[-1]
            uit.setdefault("bestand." + naam, []).append((kaal, lijf))
        else:
            uit.setdefault(naam, []).append(lijf.decode("utf-8", "replace"))
    return uit


# ---------------------------------------------------------------------
#  De webserver eromheen
# ---------------------------------------------------------------------
class Afhandelaar(BaseHTTPRequestHandler):
    server_version = "Vakto"
    sys_version = ""

    # -- het saaie deel ----------------------------------------------
    def do_GET(self) -> None:                       # noqa: N802
        deel = urlparse(self.path)
        # Het stijlbestand valt buiten de inlog. Het staat toch al in elke
        # browsercache, en een inlogscherm zonder opmaak is een inlogscherm
        # waar niemand doorheen komt.
        if deel.path == "/stijl.css":
            return self._stijl()
        self._draai("GET", deel.path, parse_qs(deel.query), {})

    def do_POST(self) -> None:                      # noqa: N802
        soort = self.headers.get("Content-Type") or ""
        lengte = int(self.headers.get("Content-Length") or 0)
        grens = MAX_UPLOAD if soort.startswith("multipart/") else MAX_FORM
        if lengte > grens:                          # R-BASIS-07, ook hier
            return self._stuur(Reactie(
                "Dat bestand is te groot. De grens ligt op "
                f"{grens // 1_000_000} MB.", status=413,
                soort="text/plain; charset=utf-8"))
        ruw = self.rfile.read(lengte)
        deel = urlparse(self.path)

        if soort.startswith("multipart/form-data"):
            try:
                form = ontleed_multipart(ruw, soort)
            except ValueError:
                return self._stuur(Reactie("Onleesbaar formulier", status=400,
                                           soort="text/plain; charset=utf-8"))
        else:
            form = parse_qs(ruw.decode("utf-8", "replace"))

        self._draai("POST", deel.path, parse_qs(deel.query), form)

    def log_message(self, formaat, *args) -> None:  # noqa: A002
        pass                                        # de toegangslog hoeft niet

    # -- het werk ----------------------------------------------------
    def _koekje(self) -> str | None:
        """Het sessietoken uit de Cookie-kop, of None."""
        ruw = self.headers.get("Cookie") or ""
        for stuk in ruw.split(";"):
            naam, _, waarde = stuk.strip().partition("=")
            if naam == gebruikers.KOEKJE:
                return waarde or None
        return None

    def _draai(self, methode: str, pad: str, vraag: dict, form: dict) -> None:
        server = self.server
        try:
            with server.verbinding() as verbinding:
                reactie = behandel(verbinding, server.standen, methode, pad,
                                   vraag, form, token=self._koekje(),
                                   vanaf=self.client_address[0])
        except Exception:                           # pragma: no cover
            # Nooit een kale stacktrace naar de browser: daar staan
            # tabelnamen en paden in die niemand hoeft te weten. In de
            # terminal komt hij wel, want daar zit de beheerder.
            traceback.print_exc()
            reactie = Reactie(schermen.kaal(
                "Er ging iets mis",
                "<h1>Er ging iets mis</h1>"
                '<p class="lead">De handeling is niet uitgevoerd. In het '
                "venster waar de server draait staat wat er misging.</p>"),
                status=500)
        self._stuur(reactie)

    def _zet_koekje(self, reactie: Reactie) -> None:
        """R-GEB-05. HttpOnly en SameSite, en Secure achter https.

        HttpOnly houdt het koekje uit handen van JavaScript op de
        pagina. SameSite=Lax zorgt dat een formulier op een andere site
        niet namens jou kan posten. Secure zet de browser erop dat hij
        het nooit over een onversleutelde verbinding stuurt — dat kan
        alleen aan als er ook echt https voor staat, anders komt het
        koekje nooit aan.
        """
        if reactie.koekje is None:
            return
        naam, waarde, leeftijd = reactie.koekje
        stukken = [f"{naam}={waarde}", "Path=/", f"Max-Age={leeftijd}",
                   "HttpOnly", "SameSite=Lax"]
        if getattr(self.server, "https", False):
            stukken.append("Secure")
        if leeftijd == 0:
            stukken.append("Expires=Thu, 01 Jan 1970 00:00:00 GMT")
        self.send_header("Set-Cookie", "; ".join(stukken))

    def _stuur(self, reactie: Reactie) -> None:
        if reactie.naar:
            self.send_response(303)
            self.send_header("Location", reactie.naar)
            self._zet_koekje(reactie)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        lijf = (reactie.lijf if isinstance(reactie.lijf, bytes)
                else str(reactie.lijf).encode("utf-8"))
        self.send_response(reactie.status)
        self.send_header("Content-Type", reactie.soort)
        self._zet_koekje(reactie)
        # Een scherm met voorraadcijfers hoort niet in de cache van een
        # gedeelde tablet te blijven staan nadat iemand is uitgelogd.
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(lijf)))
        self.end_headers()
        self.wfile.write(lijf)

    def _stijl(self) -> None:
        try:
            lijf = STIJL.read_bytes()
        except OSError:
            return self._stuur(Reactie("", status=404,
                                       soort="text/plain; charset=utf-8"))
        soort = mimetypes.guess_type("stijl.css")[0] or "text/css"
        self._stuur(Reactie(lijf, soort=soort + "; charset=utf-8"))


class Vaktoserver(ThreadingHTTPServer):
    """Draagt de databaseverbinding en de scanstanden."""

    daemon_threads = True

    def __init__(self, adres, dsn: str, klant: str = "Vakto",
                 https: bool = False):
        super().__init__(adres, Afhandelaar)
        self.dsn = dsn
        self.standen = Standen(klant=klant)
        self.https = https
        self._slot = threading.Lock()

    def verbinding(self):
        """Eén verbinding tegelijk, met commit of rollback eromheen.

        Een verbindingspoel is netter, maar dit is eerlijker over wat er
        gebeurt: één magazijn, een handvol schermen, en alle
        gelijktijdigheid die ertoe doet zit in de database zelf
        (R-BOEK-02). Loopt dit vast op drukte, dan is een poel een
        kwestie van deze ene functie vervangen.
        """
        import contextlib

        import psycopg

        @contextlib.contextmanager
        def geopend():
            with self._slot:
                with psycopg.connect(self.dsn) as verbinding:
                    yield verbinding

        return geopend()


def bedien(dsn: str = "dbname=vakto", poort: int = 8000,
           adres: str = "127.0.0.1", klant: str = "Vakto",
           https: bool = False) -> None:
    server = Vaktoserver((adres, poort), dsn, klant, https)
    print(f"Vakto draait op http://{adres}:{poort}/  (Ctrl+C stopt hem)")
    if adres not in ("127.0.0.1", "localhost", "::1") and not https:
        print("  Let op: dit adres is bereikbaar buiten deze machine, en er "
              "staat\n  geen https voor. Wachtwoorden gaan dan leesbaar over "
              "de lijn.\n  Zie DRAAIEN.md — met nginx ervoor is het tien "
              "minuten werk.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGestopt.")
    finally:
        server.server_close()


def hoofd(argumenten=None) -> int:
    p = argparse.ArgumentParser(
        description="De Vakto-schermen, op je eigen machine.")
    p.add_argument("--db", default="dbname=vakto",
                   help="verbindingstekst voor PostgreSQL")
    p.add_argument("--poort", type=int, default=8000)
    p.add_argument("--adres", default="127.0.0.1",
                   help="127.0.0.1 is alleen deze machine; 0.0.0.0 is het "
                        "hele netwerk — zet daar https voor, zie DRAAIEN.md")
    p.add_argument("--klant", default="Vakto")
    p.add_argument("--https", action="store_true",
                   help="er staat een https-proxy voor deze server; het "
                        "sessiekoekje krijgt dan de vlag Secure")
    a = p.parse_args(argumenten)
    try:
        import psycopg                              # noqa: F401
    except ImportError:
        print("De webserver heeft psycopg nodig:\n\n"
              "    pip install 'psycopg[binary]'\n\n"
              "De rekenkern en de tests werken er zonder.", file=sys.stderr)
        return 1
    bedien(a.db, a.poort, a.adres, a.klant, a.https)
    return 0


if __name__ == "__main__":                          # pragma: no cover
    raise SystemExit(hoofd())
