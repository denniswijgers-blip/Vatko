"""Gebruikers, rollen en wachtwoorden (R-GEB).

Alles wat je zonder database kunt uitrekenen staat hier: welke rol wat
mag, hoe een wachtwoord tot een afdruk wordt en hoe je die weer toetst.
Wie er ingelogd is en tot wanneer, dat weet de database — zie
`db/gebruikers.sql` en `opslag.py`.

Waarom die grens ook hier ligt (R-BOEK-03): een wachtwoord toetsen is
rekenwerk en hoort zonder PostgreSQL na te testen te zijn. Een sessie
die geldig moet blijven na een herstart, en die je moet kunnen
intrekken, is een rij — die hoort in de database.

Geen enkel pakket van buiten. `hashlib.scrypt` zit in de standaard­
bibliotheek en is precies waar het voor bedoeld is; een eigen bedenksel
met sha256 eromheen is het klassieke moment waarop een project onveilig
wordt zonder dat iemand het merkt.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

# ---------------------------------------------------------------------
#  R-GEB-01  Drie rollen, met een rang
#
#  Een rang en geen lijst met vinkjes. Vijf rollen met elk vijftien
#  vinkjes zijn vijfenzeventig keuzes die niemand bijhoudt; drie rangen
#  zijn er drie.
# ---------------------------------------------------------------------
ROLLEN: dict[str, tuple[str, str, int]] = {
    "OPERATOR":   ("Magazijnmedewerker", "MW",  1),
    "SUPERVISOR": ("Teamleider",         "TL",  2),
    "ADMIN":      ("Beheerder",          "BEH", 3),
}


def rolnaam(rol: str) -> str:
    return ROLLEN.get(rol, ("Onbekend", "?", 0))[0]


def rang(rol: str) -> int:
    return ROLLEN.get(rol, ("", "", 0))[2]


# Welke rang heb je minimaal nodig voor welk scherm? Dezelfde verdeling
# als in de browserversie (`RECHTEN` in gebruikers.js): het werk op de
# vloer is rang 1, sturen is rang 2, instellen is rang 3.
RECHTEN: dict[str, int] = {
    "/":           2,          # dashboard
    "/taken":      1,
    "/orders":     2,
    "/picken":     1,
    "/scan":       1,
    "/inslag":     1,
    "/meten":      1,
    "/locaties":   1,
    "/artikelen":  1,
    "/gebruikers": 3,
}


def mag(rol: str, pad: str) -> bool:
    """R-GEB-01 en R-GEB-02. Mag deze rol dit pad?

    Een pad dat hier niet in staat heeft minimumrang 1. Dat is met opzet
    zo om: een nieuw scherm is dan zichtbaar voor iedereen tot iemand er
    iets anders van vindt, en niet onzichtbaar voor iedereen tot iemand
    het merkt.
    """
    return rang(rol) >= RECHTEN.get(hoofdpad(pad), 1)


def hoofdpad(pad: str) -> str:
    """`/orders/12` valt onder `/orders`."""
    if pad.count("/") > 1:
        return "/" + pad.split("/")[1]
    return pad or "/"


def startpad(rol: str) -> str:
    """Waar iemand terechtkomt na het inloggen.

    Een magazijnmedewerker mag niet op het dashboard komen, en op zijn
    eigen beginscherm hoort hij geen weigering te krijgen — hij hoort
    daar gewoon niet te beginnen.
    """
    return "/" if mag(rol, "/") else "/picken"


def zichtbaar(rol: str, menu) -> list:
    """De schermen die deze rol in het menu hoort te zien."""
    return [regel for regel in menu if mag(rol, regel[0])]


@dataclass(frozen=True)
class Gebruiker:
    id: int
    naam: str
    gebruikersnaam: str
    rol: str
    badge: str | None = None
    # R-GEB-03. Een badge geeft alleen toegang tot de scanmodus. Hij ligt
    # op tafel en iedereen kan hem lezen; dat is geen wachtwoord.
    alleen_scanner: bool = False

    @property
    def rolnaam(self) -> str:
        return rolnaam(self.rol)

    @property
    def rang(self) -> int:
        return rang(self.rol)

    def mag(self, pad: str) -> bool:
        if self.alleen_scanner:
            return hoofdpad(pad) in ("/scan", "/uitloggen")
        return mag(self.rol, pad)


# ---------------------------------------------------------------------
#  R-GEB-04  Wachtwoorden worden nooit bewaard
#
#  Wat er in de kolom staat is een afdruk waar het wachtwoord niet uit
#  terug te rekenen is. De parameters staan erbij, zodat je ze over vijf
#  jaar kunt verhogen zonder dat bestaande rijen onleesbaar worden.
# ---------------------------------------------------------------------
N, R, P = 2 ** 14, 8, 1          # ~50 ms per poging op een gewone laptop
ZOUTLENGTE = 16
SLEUTELLENGTE = 32


def versleutel(wachtwoord: str, zout: bytes | None = None,
               n: int = N, r: int = R, p: int = P) -> str:
    """Geeft de regel die in de kolom komt te staan."""
    if not wachtwoord:
        raise ValueError("Een leeg wachtwoord is geen wachtwoord")
    zout = zout or os.urandom(ZOUTLENGTE)
    afdruk = hashlib.scrypt(wachtwoord.encode("utf-8"), salt=zout,
                            n=n, r=r, p=p, dklen=SLEUTELLENGTE)
    return f"scrypt${n}${r}${p}${zout.hex()}${afdruk.hex()}"


# Een afdruk van een wachtwoord dat niemand heeft. Hij bestaat om bij
# een onbekende gebruikersnaam evenveel rekenwerk te doen als bij een
# bekende (R-GEB-07): anders verraadt de snelheid van het antwoord wie
# er wél bestaat, hoe zorgvuldig de tekst ook gekozen is.
NEP = versleutel("dit wachtwoord bestaat niet", zout=b"\x00" * ZOUTLENGTE)


def klopt(wachtwoord: str, opgeslagen: str | None) -> bool:
    """Toetst een wachtwoord tegen wat er in de kolom staat.

    Vergelijken gebeurt in constante tijd. Met `==` stopt de vergelijking
    bij het eerste verschillende teken, en dat verschil is te meten.
    """
    regel = opgeslagen or NEP
    try:
        soort, n, r, p, zout, afdruk = regel.split("$")
        if soort != "scrypt":
            raise ValueError(soort)
        opnieuw = hashlib.scrypt(
            (wachtwoord or "").encode("utf-8"), salt=bytes.fromhex(zout),
            n=int(n), r=int(r), p=int(p), dklen=len(bytes.fromhex(afdruk)))
    except (ValueError, TypeError):
        # Een onleesbare regel is geen reden om binnen te laten, en ook
        # geen reden om sneller te antwoorden.
        hashlib.scrypt(b"x", salt=b"\x00" * ZOUTLENGTE, n=N, r=R, p=P,
                       dklen=SLEUTELLENGTE)
        return False
    gelijk = hmac.compare_digest(opnieuw.hex(), afdruk)
    # Zonder opgeslagen wachtwoord kan het antwoord nooit ja zijn, ook
    # niet als iemand toevallig het nepwachtwoord raadt.
    return gelijk and opgeslagen is not None


def zwak(wachtwoord: str) -> str | None:
    """Geeft terug wat er mis is, of None als het goed genoeg is.

    Geen woordenboek en geen regels over hoofdletters en leestekens:
    lengte doet het werk, en een eis die mensen omzeilen met "Zomer2024!"
    levert niets op. Twaalf tekens is het advies dat het NCSC ook geeft.
    """
    if len(wachtwoord or "") < 12:
        return "Een wachtwoord van minder dan twaalf tekens is te raden."
    if wachtwoord.strip() != wachtwoord:
        return "Begin of eindig niet met een spatie; dat gaat een keer mis."
    return None


# ---------------------------------------------------------------------
#  R-GEB-05  Sessies
# ---------------------------------------------------------------------
KOEKJE = "vakto"


def nieuw_token() -> str:
    """32 willekeurige bytes. Niet te raden, ook niet met een miljoen
    pogingen per seconde."""
    return secrets.token_urlsafe(32)


def afdruk(token: str) -> str:
    """Wat er van een sessietoken in de database komt te staan.

    Het token zelf niet: dan levert een gestolen back-up meteen een
    stapel geldige sessies op. Een sha256 is hier genoeg — het token is
    al willekeurig, dus er valt niets te raden en een zout voegt niets
    toe.
    """
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()
