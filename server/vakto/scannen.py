"""Scanmodus (R-SCAN) — hoofdstuk 12.

Het enige scherm dat op de vloer gebruikt wordt, met handschoenen aan en
een heftruck ernaast. De regels hieronder komen niet uit een ontwerpboek
maar uit wat er misgaat: van het verkeerde schap pakken, een scanner die
stuk lijkt omdat de cursor weg is, en een telling die stilvalt omdat het
systeem een code niet kent.

Er staat hier geen database-code in, en dat is niet uit netheid. De
scanner is een toestandsmachine: hij weet in welke stap hij staat en wat
een gescande code op dát moment betekent. Dat is te testen in drie
regels, en dat wil je ook — een fout in deze machine merkt niemand op de
vloer, die merk je pas bij de volgende telling.

Wat er geboekt moet worden komt eruit als een `Opdracht`. Die geeft de
aanroeper door aan `opslag.py`, en daar gaat hij door dezelfde functies
heen als het scherm: `bevestig_pick`, `tel_locatie`, `boek`. Er is geen
tweede route naar de voorraad, ook niet voor een scanner.
"""

from __future__ import annotations
from dataclasses import dataclass, field

from .instellingen import Instellingen
from .modellen import Magazijn
from .uitgaand import Pickregel

# De vier dingen die je met een scanner kunt doen.
TAKEN = ("PICKEN", "TELLEN", "INSLAG", "VRIJ")

# R-SCAN-02. De stappen per taak; "KLAAR" betekent dat er niets meer is.
STAPPEN = {
    "PICKEN": ("LOCATIE", "ARTIKEL", "AANTAL"),
    "TELLEN": ("LOCATIE", "TEL_ARTIKEL", "TEL_AANTAL"),
    "INSLAG": ("ARTIKEL", "INSLAG_AANTAL", "INSLAG_LOCATIE"),
    "VRIJ":   ("VRIJ",),
}


# ---------------------------------------------------------------------
#  Wat er uit een scan komt
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class Pickopdracht:
    """R-UIT-04. Meld deze pickregel af met dit aantal."""
    allocation_id: int
    aantal: int


@dataclass(frozen=True)
class Telopdracht:
    """R-SCAN-05. Zet dit vak op dit aantal."""
    location_id: int
    product_id: int
    geteld: int
    nulmeting: bool = False

    @property
    def reden(self) -> str:
        return "NULMETING" if self.nulmeting else "TELVERSCHIL"

    @property
    def ref(self) -> str:
        return "Opstartinventarisatie" if self.nulmeting else "Cyclustelling"


@dataclass(frozen=True)
class Inslagopdracht:
    """R-SCAN-06. Boek dit aantal naar dit vak (PUTAWAY)."""
    product_id: int
    location_id: int
    aantal: int


@dataclass(frozen=True)
class Antwoord:
    """Wat het scherm laat zien, en wat de aanroeper moet boeken.

    `soort` stuurt het geluid: piep bij "ok", buzz bij "fout", een
    tweetoon bij "klaar". Met oordoppen in kijk je niet naar een
    tekstregel.
    """
    stap: str
    bericht: str
    soort: str = "ok"
    opdracht: object | None = None

    @property
    def goed(self) -> bool:
        return self.soort != "fout"


@dataclass(frozen=True)
class Gebruiker:
    badge: str
    naam: str


# ---------------------------------------------------------------------
#  De scanner
# ---------------------------------------------------------------------
@dataclass
class Scanner:
    """R-SCAN-01. Eén invoerveld; de stap bepaalt wat een code betekent.

    Geef hem een momentopname van het magazijn en de openstaande
    pickregels mee. Hij raakt niets aan: hij zegt alleen wat er moet
    gebeuren.
    """
    mag: Magazijn
    pickregels: list[Pickregel] = field(default_factory=list)
    gebruikers: list[Gebruiker] = field(default_factory=list)
    inst: Instellingen | None = None

    taak: str = "PICKEN"
    stap: str = "LOCATIE"
    locatie_id: int | None = None
    product_id: int | None = None
    aantal: int = 0
    regel: Pickregel | None = None
    gebruiker: str | None = None
    gescand: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.inst = self.inst or Instellingen()
        self.start(self.taak)

    # -- de stand ----------------------------------------------------
    @property
    def nulmeting(self) -> bool:
        """R-SCAN-05. Staat de opstartstand aan?"""
        return self.inst.aan("opstart.onbekend_aanmaken")

    def start(self, taak: str) -> Antwoord:
        if taak not in TAKEN:
            raise ValueError(f"Onbekende scantaak {taak!r}")
        self.taak = taak
        self.gescand = []
        return self._volgende()

    def _volgende(self) -> Antwoord:
        """Klaarzetten voor de volgende handeling."""
        self.locatie_id = self.product_id = None
        self.aantal = 0
        self.regel = None

        if self.taak == "PICKEN":
            open_regels = [r for r in self.pickregels if r.nog_te_picken > 0]
            if not open_regels:
                self.stap = "KLAAR"
                return Antwoord("KLAAR", "Alles gepickt", "klaar")
            self.regel = open_regels[0]
            self.stap = "LOCATIE"
        else:
            self.stap = STAPPEN[self.taak][0]
        return Antwoord(self.stap, "", "ok")

    # -- herkennen ---------------------------------------------------
    def herken(self, code: str) -> tuple[str, object]:
        """Wat is dit voor code? Locatie, artikel, badge of niets."""
        code = (code or "").strip()
        if not code:
            return "leeg", None
        for loc in self.mag.locaties:
            if loc.code.lower() == code.lower():
                return "locatie", loc
        for art in self.mag.artikelen:
            if art.barcode == code or art.sku.lower() == code.lower():
                return "artikel", art
        for g in self.gebruikers:
            if g.badge == code:
                return "gebruiker", g
        return "onbekend", code

    # -- de kern -----------------------------------------------------
    def scan(self, code: str) -> Antwoord:
        soort, wat = self.herken(code)
        if soort == "leeg":
            return Antwoord(self.stap, "", "ok")

        # R-SCAN-07. Een badge werkt altijd, in elke stap.
        if soort == "gebruiker":
            self.gebruiker = wat.naam
            return self._zeg(f"Ingelogd als {wat.naam}")

        if self.taak == "VRIJ" or self.stap == "VRIJ":
            if soort == "locatie":
                self.locatie_id = wat.id
                return self._zeg(f"Locatie {wat.code}")
            if soort == "artikel":
                self.product_id = wat.id
                return self._zeg(f"{wat.sku}")
            return self._fout(f"Onbekende code: {wat}")

        if self.taak == "PICKEN":
            return self._scan_picken(soort, wat)
        if self.taak == "TELLEN":
            return self._scan_tellen(soort, wat)
        if self.taak == "INSLAG":
            return self._scan_inslag(soort, wat)
        return self._fout("Onverwachte scan op deze stap")

    # -- picken (R-SCAN-02, R-SCAN-04) -------------------------------
    def _scan_picken(self, soort: str, wat) -> Antwoord:
        if self.regel is None:
            return self._fout("Geen openstaande pickregels")

        if self.stap == "LOCATIE":
            if soort == "onbekend":
                return self._fout(f"Onbekende code: {wat}. Label onleesbaar "
                                  f"of locatie niet in het systeem.")
            if soort != "locatie":
                return self._fout("Scan eerst de locatie waar je staat")
            if wat.id != self.regel.location_id:
                return self._fout(
                    f"Verkeerde locatie. Je staat bij {wat.code}, "
                    f"je moet naar {self.regel.locatie}.")
            self.locatie_id = wat.id
            self.stap = "ARTIKEL"
            return self._zeg(f"{wat.code} — scan nu het artikel")

        if self.stap == "ARTIKEL":
            if soort == "onbekend":
                return self._fout(f"Onbekende code: {wat}. Label onleesbaar "
                                  f"of artikel niet in het systeem.")
            if soort != "artikel":
                return self._fout("Scan het artikel, niet de locatie")
            if wat.id != self.regel.product_id:
                return self._fout(f"Verkeerd artikel. Dit is {wat.sku}, "
                                  f"gevraagd is {self.regel.sku}.")
            self.product_id = wat.id
            self.aantal = self.regel.nog_te_picken
            self.stap = "AANTAL"
            return self._zeg(f"{wat.sku} — bevestig het aantal")

        return self._fout("Onverwachte scan op deze stap")

    # -- tellen (R-SCAN-05) ------------------------------------------
    def _scan_tellen(self, soort: str, wat) -> Antwoord:
        if self.stap == "LOCATIE":
            if soort != "locatie":
                return self._fout("Scan de locatie die je gaat tellen")
            self.locatie_id = wat.id
            self.stap = "TEL_ARTIKEL"
            return self._zeg(f"{wat.code} — scan het artikel")

        if self.stap == "TEL_ARTIKEL":
            # Bij een nulmeting is bijna elke code onbekend. Weigeren
            # betekent dat het tellen stilvalt.
            if soort == "onbekend" and self.nulmeting:
                self.product_id = None
                self.nieuwe_code = wat
                self.aantal = 0
                self.stap = "TEL_AANTAL"
                return Antwoord(
                    self.stap,
                    f"Nieuw artikel {wat} aangemaakt — hoeveel liggen er?",
                    "waarschuw")
            if soort != "artikel":
                return self._fout("Scan het artikel")
            self.product_id = wat.id
            self.aantal = self._ligt_er(wat.id, self.locatie_id)
            self.stap = "TEL_AANTAL"
            return self._zeg(f"{wat.sku} — tel en vul het echte aantal in")

        return self._fout("Onverwachte scan op deze stap")

    # -- inslaan (R-SCAN-06) -----------------------------------------
    def _scan_inslag(self, soort: str, wat) -> Antwoord:
        if self.stap == "ARTIKEL":
            if soort != "artikel":
                return self._fout("Scan het artikel dat je wilt inslaan")
            if not wat.gemeten:
                return self._fout(
                    f"{wat.sku} is nooit opgemeten — meet het eerst op")
            self.product_id = wat.id
            self.aantal = 12
            self.stap = "INSLAG_AANTAL"
            return self._zeg(f"{wat.sku} — hoeveel sla je in?")

        if self.stap == "INSLAG_LOCATIE":
            if soort != "locatie":
                return self._fout("Scan de locatie waar je het neerzet")
            keuze = self._voorstel(wat.id)
            if keuze is None:
                return self._fout("Hier past het niet, of de locatie zit "
                                  "vol. Kies een voorgestelde plek.")
            neem = min(self.aantal, keuze.vrij)
            artikel = self.mag.artikel(self.product_id)
            opdracht = Inslagopdracht(self.product_id, wat.id, neem)
            antwoord = Antwoord(
                "ARTIKEL", f"{neem} x {artikel.sku} ingeslagen op {wat.code}",
                "klaar", opdracht)
            self._noteer(antwoord.bericht)
            self._volgende()
            return antwoord

        return self._fout("Onverwachte scan op deze stap")

    # -- bevestigen --------------------------------------------------
    def bevestig(self, aantal) -> Antwoord:
        """Het aantal invullen. Hier komt de opdracht uit."""
        try:
            aantal = max(0, int(aantal))
        except (TypeError, ValueError):
            aantal = 0

        if self.taak == "PICKEN" and self.stap == "AANTAL":
            regel, gevraagd = self.regel, self.regel.nog_te_picken
            opdracht = Pickopdracht(regel.allocation_id, aantal)
            manco = aantal < gevraagd
            bericht = ("Manco vastgelegd. Reservering vrijgegeven en "
                       "teltaak aangemaakt." if manco
                       else f"Afgemeld: {aantal} st")
            self._noteer(f"{regel.locatie} · {regel.sku} · {aantal} st")
            self._afgehandeld(regel)
            self._volgende()
            return Antwoord(self.stap, bericht,
                            "fout" if manco else "klaar", opdracht)

        if self.taak == "INSLAG" and self.stap == "INSLAG_AANTAL":
            self.aantal = max(1, aantal)
            self.stap = "INSLAG_LOCATIE"
            return self._zeg("Loop naar een van de voorgestelde plekken "
                             "en scan die")

        if self.taak == "TELLEN" and self.stap == "TEL_AANTAL":
            return self._bevestig_telling(aantal)

        return self._fout("Er valt hier niets te bevestigen")

    def _bevestig_telling(self, aantal: int) -> Antwoord:
        was = self._ligt_er(self.product_id, self.locatie_id)
        verschil = aantal - was
        code = self._locatiecode(self.locatie_id)
        # Bij een nulmeting is er geen "verschil": er was nog niets
        # vastgelegd. Dat hoort ook zo in het journaal te staan, anders
        # lijkt de eerste dag van een nieuwe klant vol telfouten te zitten.
        nul = was == 0 and self.nulmeting
        opdracht = Telopdracht(self.locatie_id, self.product_id, aantal, nul)

        if verschil == 0:
            artikel = self.mag.artikel(self.product_id)
            sku = artikel.sku if artikel else "?"
            self._noteer(f"{code} · {sku} · klopt ({aantal})")
            antwoord = Antwoord(self.stap, "Telling klopt", "klaar", opdracht)
        elif nul:
            antwoord = Antwoord(self.stap, f"{aantal} st vastgelegd op {code}",
                                "klaar", opdracht)
        else:
            teken = "+" if verschil > 0 else ""
            antwoord = Antwoord(
                self.stap,
                f"Verschil van {teken}{verschil} geboekt met reden TELVERSCHIL",
                "fout", opdracht)
        self._volgende()
        return antwoord

    # -- overslaan (R-SCAN-04) ---------------------------------------
    def sla_over(self) -> Antwoord:
        """Overslaan is geen manco: de regel gaat achteraan.

        Een manco zegt "dit ligt er niet"; overslaan zegt "nu even niet".
        Die twee door elkaar halen levert teltaken op voor vakken waar
        niets aan de hand is.
        """
        if self.taak == "PICKEN" and self.regel is not None:
            regel = self.regel
            self.pickregels = [r for r in self.pickregels if r is not regel]
            self.pickregels.append(regel)
            self._volgende()
            return Antwoord(self.stap, "Regel achteraan gezet", "ok")
        self._volgende()
        return Antwoord(self.stap, "", "ok")

    # -- kleine hulpjes ----------------------------------------------
    def _zeg(self, tekst: str) -> Antwoord:
        return Antwoord(self.stap, tekst, "ok")

    def _fout(self, tekst: str) -> Antwoord:
        return Antwoord(self.stap, tekst, "fout")

    def _noteer(self, tekst: str) -> None:
        self.gescand.insert(0, tekst)
        del self.gescand[40:]

    def _afgehandeld(self, regel: Pickregel) -> None:
        self.pickregels = [r for r in self.pickregels if r is not regel]

    def _ligt_er(self, product_id: int | None, location_id: int | None) -> int:
        for s in self.mag.voorraad:
            if s.product_id == product_id and s.location_id == location_id:
                return s.qty
        return 0

    def _locatiecode(self, location_id: int | None) -> str:
        loc = self.mag.locatie(location_id) if location_id else None
        return loc.code if loc else "?"

    def _voorstel(self, location_id: int):
        from .voorstel import voorstel_inslag
        for v in voorstel_inslag(self.mag, self.product_id, self.aantal,
                                 self.inst, limiet=40):
            if v.locatie.id == location_id:
                return v
        return None
