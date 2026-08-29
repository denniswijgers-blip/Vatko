"""Optimalisatie (R-OPT) — hoofdstuk 10.

Vier dingen waar een magazijn geld op verliest zonder het te merken:

  1. Hetzelfde artikel op drie plekken. Elke plek die je terugwint is een
     plek die je niet hoeft bij te bouwen.
  2. Een picklocatie die leegloopt terwijl er orders op wachten. De
     picker staat er, en dat is het duurste moment van de dag.
  3. Een hardloper met een aanvuldrempel die iemand drie jaar geleden
     heeft ingetypt. Precies dezelfde ziekte als een artikelmaat die stil
     veroudert — en daar is dit hele systeem om begonnen.
  4. Locaties die al een jaar niet geteld zijn. Niet spannend, wel de
     reden dat je voorraad langzaam wegloopt van de werkelijkheid.

Er staat hier geen database-code in. Elke functie krijgt de toestand mee
en geeft terug wát er zou moeten gebeuren; het wegschrijven doet
`opslag.py` via `zelfcontrole.sql`. Zo is elk geval hieronder in drie
regels na te testen zonder dat er een PostgreSQL draait.

Twee dingen leveren géén taak op maar een advies: de aanvuldrempel
(R-OPT-05) en een hardloper zonder picklocatie (R-OPT-06). Allebei zijn
het besluiten over werkkapitaal en ruimte, en die neemt een systeem niet.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil, floor

from .getallen import rond
from .instellingen import Instellingen
from .modellen import Artikel, Locatie, Magazijn, Taak
from .passen import pas_berekening
from .voorstel import voorstel_inslag

# Een locatie die nog nooit geteld is. In de browserversie is dat
# `geteldOp || 0`; hier hetzelfde moment, met een tijdzone erbij
# (R-BASIS-06 — elke `at` is UTC).
NOOIT_GETELD = datetime(1970, 1, 1, tzinfo=timezone.utc)


@dataclass(frozen=True)
class Pick:
    """Eén PICK-regel uit het journaal, meer heeft R-OPT-02 niet nodig."""
    product_id: int
    qty: int
    at: datetime


@dataclass(frozen=True)
class Advies:
    """R-OPT-05. Een advies met een knop, geen taak."""
    product_id: int
    sku: str
    per_dag: float
    nu: int                     # de huidige min_qty
    zou: int                    # wat het volgens het verbruik zou moeten zijn
    max_nu: int | None
    max_zou: int

    @property
    def richting(self) -> str:
        return "omhoog" if self.zou > self.nu else "omlaag"


@dataclass(frozen=True)
class Pickplek:
    """R-OPT-06. Ook een voorstel: wélk vak je vrijmaakt is een keuze."""
    product_id: int
    per_dag: float
    van: int
    naar: int
    qty: int


# ---------------------------------------------------------------------
#  R-OPT-02  Vraagsnelheid
# ---------------------------------------------------------------------
def snelheden(picks: list[Pick], inst: Instellingen | None = None,
              nu: datetime | None = None) -> dict[int, float]:
    """Stuks per dag over het venster, per artikel.

    Let op: stuks per dag, niet aantal picks per dag. Twintig keer één
    stuk pakken is iets heel anders dan één keer twintig, maar voor de
    vraag "hoeveel moet er op de picklocatie liggen" telt alleen hoeveel
    er weggaat.

    Cachen doet deze functie niet; dat hoort bij de aanroeper, op het
    aantal journaalregels. Zolang er niets geboekt is verandert de
    uitkomst niet.
    """
    inst = inst or Instellingen()
    nu = nu or datetime.now(timezone.utc)
    dagen = max(1, inst.geheel("opt.venster_dagen"))
    vanaf = nu - timedelta(days=dagen)

    totalen: dict[int, int] = {}
    for p in picks:
        if p.at < vanaf:
            continue
        totalen[p.product_id] = totalen.get(p.product_id, 0) + p.qty
    return {pid: aantal / dagen for pid, aantal in totalen.items()}


# ---------------------------------------------------------------------
#  Hulpwerk dat drie regels delen
# ---------------------------------------------------------------------
def ruimte_voor(mag: Magazijn, product_id: int, location_id: int,
                inst: Instellingen | None = None,
                bezet: dict | None = None) -> int:
    """R-INS-02. Hoeveel er nog bij kan op deze locatie.

    Dezelfde drie budgetten als het inslagvoorstel — geometrisch minus
    wat er al van dit artikel ligt, volume, gewicht — maar dan voor één
    locatie in plaats van een rangschikking. Dit is de derde term die in
    R-ZC-04 en R-OPT-03 verplicht is: minimum- en maximumvoorraad zeggen
    niets over wat er past.
    """
    inst = inst or Instellingen()
    vul = inst.getal("putaway.fill_factor")
    artikel = mag.artikel(product_id)
    loc = mag.locatie(location_id)
    if artikel is None or loc is None or not artikel.gemeten:
        return 0

    fit = pas_berekening(artikel, loc, vul)
    if not fit.qty:
        return 0

    bezet = mag.bezetting() if bezet is None else bezet
    b = bezet.get(location_id)
    bezet_vol = b.vol_mm3 if b else 0
    bezet_gew = b.gew_g if b else 0
    dit = b.per_artikel.get(product_id, 0) if b else 0

    return max(0, floor(min(
        fit.qty - dit,
        (loc.volume_mm3 * vul - bezet_vol) / artikel.volume_mm3,
        (loc.max_g - bezet_gew) / artikel.g,
    )))


def bulkbron(mag: Magazijn, product_id: int, minimaal: int = 1):
    """De bulkrij met de meeste vrije voorraad, of None.

    Vrije voorraad en niet qty: wat op naam van een order staat mag je
    niet wegrijden, ook al ligt het er nog.
    """
    beste = None
    for s in mag.voorraad:
        if s.product_id != product_id or s.qty <= 0:
            continue
        loc = mag.locatie(s.location_id)
        if loc is None or not mag.soort(loc).bulk:
            continue
        if s.vrij < minimaal:
            continue
        if beste is None or s.vrij > beste.vrij:
            beste = s
    return beste


def _pickrijen(mag: Magazijn, product_id: int) -> list:
    """De voorraadrijen van dit artikel op picklocaties, op looproute."""
    uit = []
    for s in mag.voorraad:
        if s.product_id != product_id or s.qty <= 0:
            continue
        loc = mag.locatie(s.location_id)
        if loc is None or not loc.actief or not mag.soort(loc).pick:
            continue
        uit.append((loc.seq, loc.id, s))
    uit.sort()
    return [s for _, _, s in uit]


# ---------------------------------------------------------------------
#  R-OPT-03  Drie aanleidingen, één taak
#
#  R-ZC-04 is de onderste rij van deze tabel. Het staat twee keer in de
#  specificatie omdat het bij twee hoofdstukken hoort, maar het is één
#  regel en dus één stuk code — anders geeft de zelfcontrole een taak van
#  25 stuks waar de optimalisatie er 40 wil, en staat de picker twee keer
#  voor hetzelfde vak.
# ---------------------------------------------------------------------
@dataclass
class _Verzoek:
    """Wat één aanleiding vraagt. Blijft binnen dit bestand."""
    naar: int
    qty: int
    prio: int
    aanleiding: str
    reden: str


@dataclass(frozen=True)
class Bijwerking:
    """Er ligt al een aanvultaak voor dit vak en die moet zwaarder.

    Bijwerken en niet een tweede taak maken: twee loopjes naar hetzelfde
    vak is precies wat R-OPT-03 verbiedt.
    """
    taak: Taak
    qty: int
    prio: int
    aanleiding: str
    reden: str


def aanvultaken(mag: Magazijn, taken: list[Taak], vraag: dict[int, int],
                snel: dict[int, float], inst: Instellingen | None = None
                ) -> tuple[list[Taak], list[Bijwerking]]:
    """R-OPT-03 en R-ZC-04. Geeft (nieuwe taken, bij te werken taken).

    Vragen twee aanleidingen om hetzelfde vak, dan wordt het één taak:
    het hoogste aantal, het laagste prioriteitsnummer, en de reden van de
    zwaarste aanleiding. Nooit drie loopjes voor dezelfde locatie.

    `vraag` is {product_id: nog te picken stuks uit openstaande orders},
    `snel` de uitkomst van `snelheden()`.
    """
    inst = inst or Instellingen()
    bezet = mag.bezetting()
    hardloper_per_dag = inst.getal("opt.hardloper_per_dag")
    dekking_dagen = inst.getal("opt.dekking_dagen")

    # ---- alle drie de aanleidingen verzamelen, per (artikel, vak) ----
    verzoeken: dict[tuple[int, int], _Verzoek] = {}

    def vraag_aan(product_id: int, v: _Verzoek) -> None:
        if v.qty <= 0:
            return
        sleutel = (product_id, v.naar)
        staand = verzoeken.get(sleutel)
        if staand is None:
            verzoeken[sleutel] = v
            return
        # Hoogste aantal, laagste prioriteitsnummer, reden van de zwaarste.
        if v.prio < staand.prio:
            staand.prio, staand.aanleiding, staand.reden = (
                v.prio, v.aanleiding, v.reden)
        staand.qty = max(staand.qty, v.qty)

    for artikel in mag.artikelen:
        rijen = _pickrijen(mag, artikel.id)
        if not rijen:
            continue
        doel = rijen[0]                     # de eerste op looproute
        op_pick = sum(s.qty for s in rijen)

        # 1. ordervraag — prio 10. Er staat een picker op te wachten.
        nodig = vraag.get(artikel.id, 0)
        if nodig > op_pick:
            tot = max(nodig, artikel.max_qty or nodig)
            vraag_aan(artikel.id, _Verzoek(
                doel.location_id, tot - op_pick, 10, "ordervraag",
                f"{nodig} st gevraagd door openstaande orders, "
                f"{op_pick} op de picklocatie"))

        # 2. hardloper — prio 20. Vooruit vullen op het verbruik.
        per_dag = snel.get(artikel.id, 0.0)
        if per_dag >= hardloper_per_dag and per_dag > 0:
            dagen_over = op_pick / per_dag
            if dagen_over < dekking_dagen:
                vraag_aan(artikel.id, _Verzoek(
                    doel.location_id,
                    ceil(per_dag * dekking_dagen) - op_pick, 20, "hardloper",
                    f"hardloper: {per_dag:.1f} st per dag, nog "
                    f"{dagen_over:.1f} dag(en) op de picklocatie"))

        # 3. drempel — prio 25. R-ZC-04.
        if artikel.min_qty:
            for s in rijen:
                if s.qty >= artikel.min_qty:
                    continue
                loc = mag.locatie(s.location_id)
                vraag_aan(artikel.id, _Verzoek(
                    s.location_id,
                    (artikel.max_qty or artikel.min_qty) - s.qty, 25, "drempel",
                    f"Picklocatie {loc.code} onder drempel "
                    f"({s.qty}/{artikel.min_qty})"))

    # ---- omzetten in taken, met de derde term erbij -----------------
    open_taken = {(t.product_id, t.naar): t for t in taken
                  if t.soort == "REPLENISH" and t.status == "TODO"}

    nieuw: list[Taak] = []
    bijwerken: list[Bijwerking] = []

    for (product_id, naar), v in sorted(verzoeken.items()):
        past = ruimte_voor(mag, product_id, naar, inst, bezet)
        staand = open_taken.get((product_id, naar))

        if staand is not None:
            # Er ligt al een taak voor dit vak. Hoogste aantal, laagste
            # prioriteitsnummer, reden van de ZWAARSTE aanleiding — dus
            # niet van de laatste die toevallig langskomt. Een taak die
            # "ordervraag" heet en als reden "onder drempel" geeft, laat
            # de picker het verkeerde denken over waarom hij loopt.
            qty = min(max(staand.qty, v.qty), max(1, past))
            zwaarder = v.prio < staand.prio
            prio = min(staand.prio, v.prio)
            aanleiding = v.aanleiding if zwaarder else staand.aanleiding
            reden = v.reden if zwaarder else staand.reden
            if (qty, prio, aanleiding) != (staand.qty, staand.prio,
                                           staand.aanleiding):
                bijwerken.append(Bijwerking(staand, qty, prio, aanleiding, reden))
            continue

        bron = bulkbron(mag, product_id, 1)
        if bron is None:
            continue                # niets om mee aan te vullen
        echt = min(v.qty, bron.vrij, past)
        if echt <= 0:
            continue                # het past er niet, dus het is geen taak

        nieuw.append(Taak(
            soort="REPLENISH", naam="Picklocatie aanvullen", prio=v.prio,
            product_id=product_id, van=bron.location_id, naar=naar,
            qty=echt, aanleiding=v.aanleiding, reden=v.reden))

    return nieuw, bijwerken


# ---------------------------------------------------------------------
#  R-OPT-01  Samenvoegen
# ---------------------------------------------------------------------
def samenvoegtaken(mag: Magazijn, taken: list[Taak],
                   inst: Instellingen | None = None) -> list[Taak]:
    """Hetzelfde artikel op meerdere plekken terugbrengen tot één.

    Twee regels die niet onderhandelbaar zijn:

      * gereserveerde voorraad blijft liggen. Die staat op naam van een
        order; verplaats je hem, dan klopt de pickopdracht niet meer.
      * nooit een picklocatie leeghalen naar bulk. Dan staat de picker
        morgen voor een leeg vak en heeft de optimalisatie het magazijn
        slechter gemaakt in plaats van beter.
    """
    inst = inst or Instellingen()
    if not inst.aan("opt.samenvoegen"):
        return []
    vul = inst.getal("putaway.fill_factor")
    bezet = mag.bezetting()

    per_artikel: dict[int, list] = {}
    for s in mag.voorraad:
        if s.qty <= 0:
            continue
        loc = mag.locatie(s.location_id)
        if loc is None or not mag.soort(loc).doel:
            continue
        per_artikel.setdefault(s.product_id, []).append(s)

    bezig = {t.product_id for t in taken
             if t.soort == "SAMENVOEG" and t.status == "TODO"}

    uit: list[Taak] = []
    for product_id in sorted(per_artikel):
        rijen = per_artikel[product_id]
        if not 2 <= len(rijen) <= 6:
            continue
        if any(s.res > 0 for s in rijen):
            continue
        if product_id in bezig:
            continue

        artikel = mag.artikel(product_id)
        if artikel is None or not artikel.gemeten:
            continue
        p_vol = artikel.volume_mm3
        totaal = sum(s.qty for s in rijen)

        # Waar past alles? Eigen voorraad telt hier niet mee als bezetting
        # — die gaat immers mee verhuizen.
        doel = None
        for s in rijen:
            loc = mag.locatie(s.location_id)
            if loc is None or not loc.actief:
                continue
            fit = pas_berekening(artikel, loc, vul)
            if not fit.qty:
                continue
            b = bezet.get(loc.id)
            eigen_stuks = b.per_artikel.get(product_id, 0) if b else 0
            vreemd_vol = (b.vol_mm3 - eigen_stuks * p_vol) if b else 0
            vreemd_gew = (b.gew_g - eigen_stuks * artikel.g) if b else 0
            ruimte = floor(min(
                fit.qty,
                (loc.volume_mm3 * vul - vreemd_vol) / p_vol,
                (loc.max_g - vreemd_gew) / artikel.g,
            ))
            if ruimte < totaal:
                continue
            # Liever de picklocatie houden, en anders de plek waar al het
            # meeste ligt: dan hoef je het minst te sjouwen.
            score = (1_000_000 if mag.soort(loc).pick else 0) + s.qty
            if doel is None or score > doel[1]:
                doel = (loc, score)

        if doel is None:
            continue
        doel_loc = doel[0]

        bronnen = [s for s in rijen if s.location_id != doel_loc.id]
        if not bronnen:
            continue
        if not mag.soort(doel_loc).pick and any(
                mag.soort(mag.locatie(s.location_id)).pick for s in bronnen):
            continue

        for b in sorted(bronnen, key=lambda s: s.location_id):
            code = mag.locatie(b.location_id).code
            uit.append(Taak(
                soort="SAMENVOEG", naam="Voorraad samenvoegen", prio=35,
                product_id=product_id, van=b.location_id, naar=doel_loc.id,
                qty=b.qty, aanleiding="samenvoegen",
                reden=f"{code} komt helemaal vrij; alle {totaal} st "
                      f"passen op {doel_loc.code}"))
    return uit


# ---------------------------------------------------------------------
#  R-OPT-04  Telplan
# ---------------------------------------------------------------------
def telplan(mag: Magazijn, taken: list[Taak], inst: Instellingen | None = None,
            nu: datetime | None = None) -> list[Taak]:
    """Welke locaties zijn aan de beurt om geteld te worden?

    Sorteren op de RELATIEVE overschrijding (over / interval) en niet op
    absolute dagen. Doe je dat laatste, dan komen groepen met een lang
    telinterval nooit aan bod: honderd dagen over een interval van dertig
    is erger dan honderd dagen over een interval van driehonderd.

    Teltaken uit een manco (R-UIT-05) tellen niet mee in het plafond:
    die zijn urgent en hebben een andere aanleiding.
    """
    inst = inst or Instellingen()
    nu = nu or datetime.now(timezone.utc)
    plafond = inst.geheel("opt.max_open_teltaken")

    open_uit_plan = sum(1 for t in taken
                        if t.soort == "CYCLE_COUNT" and t.status == "TODO"
                        and t.aanleiding == "telinterval")
    if open_uit_plan >= plafond:
        return []

    bezet_locaties = {t.naar for t in taken
                      if t.soort == "CYCLE_COUNT" and t.status == "TODO"}

    kandidaten = []
    gezien: set[int] = set()
    for s in mag.voorraad:
        if s.qty <= 0 or s.location_id in gezien:
            continue
        loc = mag.locatie(s.location_id)
        if loc is None or not loc.actief or not mag.soort(loc).doel:
            continue
        artikel = mag.artikel(s.product_id)
        if artikel is None:
            continue
        interval = timedelta(days=mag.telinterval(artikel))
        # Nooit geteld telt als oneindig over tijd — zo komt een vak dat
        # nog nooit aan de beurt is geweest vanzelf bovenaan.
        geteld = loc.geteld_op or NOOIT_GETELD
        over = nu - geteld - interval
        if over.total_seconds() <= 0:
            continue
        gezien.add(s.location_id)
        kandidaten.append((over / interval, loc, s, over, interval))

    # Het meest over tijd eerst; bij gelijke stand op looproute, zodat
    # dezelfde toestand altijd dezelfde volgorde geeft.
    kandidaten.sort(key=lambda k: (-k[0], k[1].seq, k[1].id))

    uit: list[Taak] = []
    for _, loc, s, over, interval in kandidaten:
        if open_uit_plan + len(uit) >= plafond:
            break
        if loc.id in bezet_locaties:
            continue
        # R-OPT-04. Nooit geteld heet ook zo. "20508 dag(en) over het
        # telinterval" is rekenkundig waar (geteld_op is dan 1970) maar
        # onzin om te lezen, en bij een nieuwe klant staat het op elke
        # taak. Wie dat leest, gelooft de rest van het scherm ook niet.
        if loc.geteld_op is None:
            reden = "nog nooit geteld"
        else:
            dagen = int(over.total_seconds() // 86400)
            reden = (f"{dagen} dag(en) over het telinterval van "
                     f"{interval.days} dagen")
        uit.append(Taak(
            soort="CYCLE_COUNT", naam="Locatie tellen", prio=45,
            product_id=s.product_id, van=loc.id, naar=loc.id, qty=s.qty,
            aanleiding="telinterval", reden=reden))
    return uit


# ---------------------------------------------------------------------
#  R-OPT-05  Drempeladvies — een advies, geen taak
# ---------------------------------------------------------------------
def drempeladvies(mag: Magazijn, snel: dict[int, float],
                  inst: Instellingen | None = None,
                  limiet: int = 40) -> list[Advies]:
    """Klopt de aanvuldrempel nog met wat er werkelijk weggaat?

    Dit is hetzelfde idee als een artikelmaat die stil veroudert: een
    getal dat iemand ooit heeft ingetypt en waar niemand meer naar kijkt.
    Het verschil is dat het systeem hier niet zelf ingrijpt — hoeveel je
    op de vloer wilt hebben is een besluit over werkkapitaal en ruimte.
    """
    inst = inst or Instellingen()
    dekking = inst.getal("opt.dekking_dagen")
    grens = inst.getal("opt.drempel_afwijking_pct") / 100

    uit: list[Advies] = []
    for artikel in mag.artikelen:
        per_dag = snel.get(artikel.id, 0.0)
        if per_dag < 0.5 or not artikel.min_qty or artikel.drempel_akkoord:
            continue
        # rond() en niet round(): de browserversie gebruikt Math.round en
        # dat rondt halve getallen naar boven. Zonder dit geeft een
        # verbruik van 4,5 st/dag hier 13 en daar 14 (zie getallen.py).
        zou = max(1, rond(per_dag * dekking))
        afwijking = abs(zou - artikel.min_qty) / max(1, zou)
        if afwijking < grens:
            continue
        uit.append(Advies(artikel.id, artikel.sku, per_dag, artikel.min_qty,
                          zou, artikel.max_qty, max(zou * 3, zou + 1)))

    uit.sort(key=lambda a: (-a.per_dag, a.product_id))
    return uit[:limiet]


# ---------------------------------------------------------------------
#  R-OPT-06  Hardloper zonder picklocatie — ook een voorstel
# ---------------------------------------------------------------------
def pickplekvoorstellen(mag: Magazijn, taken: list[Taak],
                        snel: dict[int, float],
                        inst: Instellingen | None = None,
                        limiet: int = 12) -> list[Pickplek]:
    """Een artikel dat elke dag twaalf keer gepakt wordt en alleen in de
    palletstelling ligt, laat je picker elke keer een eind lopen.

    Het systeem rekent uit welk vak past; wélk vak je ervoor vrijmaakt
    blijft een keuze van de teamleider.
    """
    inst = inst or Instellingen()
    drempel = inst.getal("opt.hardloper_per_dag")
    dekking = inst.getal("opt.dekking_dagen")

    bezig = {t.product_id for t in taken
             if t.soort == "PICKPLEK" and t.status == "TODO"}

    uit: list[Pickplek] = []
    for artikel in mag.artikelen:
        per_dag = snel.get(artikel.id, 0.0)
        if per_dag < drempel or artikel.id in bezig:
            continue
        if _pickrijen(mag, artikel.id):
            continue                        # heeft er al een
        bron = bulkbron(mag, artikel.id, 1)
        if bron is None:
            continue
        nodig = max(1, ceil(per_dag * dekking))
        keuze = next(
            (v for v in voorstel_inslag(mag, artikel.id, nodig, inst, limiet=8)
             if mag.soort(v.locatie).pick
             and v.locatie.id != bron.location_id), None)
        if keuze is None:
            continue
        uit.append(Pickplek(
            artikel.id, per_dag, bron.location_id, keuze.locatie.id,
            max(1, min(nodig, bron.vrij, nodig if keuze.alles else keuze.vrij))))

    uit.sort(key=lambda p: (-p.per_dag, p.product_id))
    return uit[:limiet]
