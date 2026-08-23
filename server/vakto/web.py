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
keer af. Na de omleiding staat de melding in de URL — er is geen
sessiekoekje nodig om te kunnen zeggen dat het gelukt is.

Starten:

    python3 -m vakto.web                 # localhost:8000, database vakto
    python3 -m vakto.web --poort 8080 --db "dbname=vakto user=jan"
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

from . import opslag, schermen
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
#  De sessie
#
#  Eén gedeelde scanstand voor de hele server. Dat is genoeg voor stap 8
#  — er staat nog geen inlog omheen. Bij stap 9 komen gebruikers en
#  rollen, en dan wordt dit een sessie per medewerker; de scanner zelf
#  hoeft daar niets voor te veranderen, want die houdt zijn stand al in
#  één object bij.
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


# ---------------------------------------------------------------------
#  De router
#
#  Los van de webserver, zodat een test een heel scherm kan opvragen
#  zonder dat er een socket aan te pas komt (tests/test_schermen.py).
# ---------------------------------------------------------------------
def behandel(verbinding, sessie: Sessie, methode: str, pad: str,
             vraag: dict, formulier: dict) -> Reactie:
    if methode == "POST":
        return _post(verbinding, sessie, pad, formulier)
    return _get(verbinding, sessie, pad, vraag)


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
def _get(verbinding, sessie: Sessie, pad: str, vraag: dict) -> Reactie:
    melding = None
    tekst = _een(vraag, "m")
    if tekst:
        melding = (_een(vraag, "s"), tekst)

    cijfers = opslag.cijfers(verbinding)

    def blad(titel: str, inhoud: str, aan: str = pad, **rest) -> Reactie:
        return Reactie(schermen.bladzijde(
            titel, inhoud, pad=aan, melding=melding, klant=sessie.klant,
            tellers=_tellers(cijfers), **rest))

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
                klant=sessie.klant, tellers=_tellers(cijfers)), status=404)
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
            melding=melding, klant=sessie.klant, lichaam="scanmodus"))

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

    return Reactie(schermen.bladzijde(
        "Niet gevonden", "<h1>Dit scherm bestaat niet</h1>"
        '<p class="lead">Kijk het adres na, of kies links een scherm.</p>',
        pad="/", klant=sessie.klant, tellers=_tellers(cijfers)), status=404)


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
def _post(verbinding, sessie: Sessie, pad: str, form: dict) -> Reactie:
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
#  De webserver eromheen
# ---------------------------------------------------------------------
class Afhandelaar(BaseHTTPRequestHandler):
    server_version = "Vakto"
    sys_version = ""

    # -- het saaie deel ----------------------------------------------
    def do_GET(self) -> None:                       # noqa: N802
        deel = urlparse(self.path)
        if deel.path == "/stijl.css":
            return self._stijl()
        self._draai("GET", deel.path, parse_qs(deel.query), {})

    def do_POST(self) -> None:                      # noqa: N802
        lengte = int(self.headers.get("Content-Length") or 0)
        if lengte > 1_000_000:                      # R-BASIS-07, ook hier
            return self._stuur(Reactie("Te veel gegevens", status=413,
                                       soort="text/plain; charset=utf-8"))
        ruw = self.rfile.read(lengte).decode("utf-8", "replace")
        deel = urlparse(self.path)
        self._draai("POST", deel.path, parse_qs(deel.query), parse_qs(ruw))

    def log_message(self, formaat, *args) -> None:  # noqa: A002
        pass                                        # de toegangslog hoeft niet

    # -- het werk ----------------------------------------------------
    def _draai(self, methode: str, pad: str, vraag: dict, form: dict) -> None:
        server = self.server
        try:
            with server.verbinding() as verbinding:
                reactie = behandel(verbinding, server.sessie, methode, pad,
                                   vraag, form)
        except Exception:                           # pragma: no cover
            # Nooit een kale stacktrace naar de browser: daar staan
            # tabelnamen en paden in die niemand hoeft te weten. In de
            # terminal komt hij wel, want daar zit de beheerder.
            traceback.print_exc()
            reactie = Reactie(schermen.bladzijde(
                "Er ging iets mis",
                "<h1>Er ging iets mis</h1>"
                '<p class="lead">De handeling is niet uitgevoerd. In het '
                "venster waar de server draait staat wat er misging.</p>",
                pad="/"), status=500)
        self._stuur(reactie)

    def _stuur(self, reactie: Reactie) -> None:
        if reactie.naar:
            self.send_response(303)
            self.send_header("Location", reactie.naar)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        lijf = (reactie.lijf if isinstance(reactie.lijf, bytes)
                else str(reactie.lijf).encode("utf-8"))
        self.send_response(reactie.status)
        self.send_header("Content-Type", reactie.soort)
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
    """Draagt de databaseverbinding en de scanstand."""

    daemon_threads = True

    def __init__(self, adres, dsn: str, klant: str = "Vakto"):
        super().__init__(adres, Afhandelaar)
        self.dsn = dsn
        self.sessie = Sessie(klant=klant)
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
           adres: str = "127.0.0.1", klant: str = "Vakto") -> None:
    server = Vaktoserver((adres, poort), dsn, klant)
    print(f"Vakto draait op http://{adres}:{poort}/  (Ctrl+C stopt hem)")
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
                        "hele netwerk — doe dat pas na stap 9, want er zit "
                        "nog geen inlog omheen")
    p.add_argument("--klant", default="Vakto")
    a = p.parse_args(argumenten)
    try:
        import psycopg                              # noqa: F401
    except ImportError:
        print("De webserver heeft psycopg nodig:\n\n"
              "    pip install 'psycopg[binary]'\n\n"
              "De rekenkern en de tests werken er zonder.", file=sys.stderr)
        return 1
    bedien(a.db, a.poort, a.adres, a.klant)
    return 0


if __name__ == "__main__":                          # pragma: no cover
    raise SystemExit(hoofd())
