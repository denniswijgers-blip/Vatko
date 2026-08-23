"""De schermen (stap 8) — alleen het tekenen.

Hier staat geen database-code en geen webserver. Elke functie krijgt
gegevens mee en geeft HTML terug, zodat je een scherm kunt natesten
zonder dat er iets draait. `web.py` haalt de gegevens op en plakt het aan
elkaar.

De opmaak komt uit `demo/stijl.css` — hetzelfde bestand als de
browserversie. Dat is geen luiheid: bij stap 8 bouw je de serverschermen
mét de browserversie ernaast, en dan wil je dat een verschil in het beeld
ook echt een verschil in de gegevens is. De klassenamen hieronder zijn
dus geen keuze: ze moeten precies zijn wat in dat bestand staat.

Nederlandse namen, Nederlandse schermen. De HTML is met opzet saai: geen
framework, geen bouwstap, niets wat je over drie jaar niet meer kunt
lezen. Geen enkel scherm heeft JavaScript nodig om te werken — een
formulier posten kan een browser al sinds 1995, en op de vloer staat
soms een tablet waar je niets nieuws op geïnstalleerd krijgt.
"""

from __future__ import annotations

from html import escape

# De navigatie, in de volgorde van de werkdag: binnen, op de vloer,
# buiten. Dezelfde volgorde en dezelfde groepen als in de browserversie,
# zodat iemand die de demo kent hier niet hoeft te zoeken.
MENU = (
    ("/",          "Dashboard", "Overzicht",   "wat vraagt aandacht"),
    ("/taken",     "Taken",     "Overzicht",   "werk dat klaarstaat"),
    ("/inslag",    "Inslag",    "Inkomend",    "waar leg ik dit neer"),
    ("/meten",     "Opmeten",   "Inkomend",    "maten bijhouden"),
    ("/orders",    "Orders",    "Uitgaand",    "wat er uit moet"),
    ("/picken",    "Picken",    "Uitgaand",    "verzamelen voor een order"),
    ("/scan",      "Scanmodus", "Op de vloer", "scherm voor de scanner"),
    ("/locaties",  "Locaties",  "Magazijn",    "de vakken en stellingen"),
    ("/artikelen", "Artikelen", "Magazijn",    "de producten zelf"),
)

# Hetzelfde merkteken als in de browserversie: een doos in een vak.
MERKTEKEN = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
             '<rect x="1.6" y="1.6" width="20.8" height="20.8" rx="4" '
             'fill="none" stroke="currentColor" stroke-width="1.5" opacity=".55"/>'
             '<rect x="6.4" y="12.2" width="11.2" height="5.4" rx="1.4" '
             'fill="currentColor"/>'
             '<path d="M6.4 8.4h11.2" stroke="currentColor" stroke-width="1.2" '
             'stroke-linecap="round" opacity=".4"/></svg>')


def esc(waarde) -> str:
    return escape(str(waarde if waarde is not None else ""))


def pil(soort: str, tekst) -> str:
    return '<span class="pil ' + esc(soort) + '">' + esc(tekst) + "</span>"


def maatpil(maat) -> str:
    return '<span class="maat ' + esc(maat) + '">' + esc(maat) + "</span>"


def getal(n) -> str:
    """Duizendtallen met een punt, zoals een Nederlander ze leest."""
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return esc(n)


def datum(waarde) -> str:
    """Alleen de dag. Wie het tijdstip nodig heeft kijkt in het journaal."""
    if waarde is None:
        return ""
    tekst = str(waarde)
    return esc(tekst[:10])


# ---------------------------------------------------------------------
#  Het geraamte
# ---------------------------------------------------------------------
def bladzijde(titel: str, inhoud: str, pad: str = "/",
              melding: tuple[str, str] | None = None,
              klant: str = "Vakto", tellers: dict | None = None,
              lichaam: str = "", kruimel: str = "") -> str:
    """Het hele scherm, met navigatie eromheen."""
    tellers = tellers or {}
    groepen: list[tuple[str, list]] = []
    for p, naam, groep, bij in MENU:
        if not groepen or groepen[-1][0] != groep:
            groepen.append((groep, []))
        groepen[-1][1].append((p, naam, bij))

    nav = []
    for groep, items in groepen:
        nav.append('<div class="navgroep">' + esc(groep) + "</div>")
        for p, naam, bij in items:
            aan = " actief" if p == pad else ""
            teller = tellers.get(p)
            badge = ('<span class="badge">' + getal(teller) + "</span>"
                     if teller else "")
            nav.append(
                '<a href="' + esc(p) + '" class="' + aan.strip() + '">'
                '<span class="lbl"><span class="lbltekst">'
                '<span class="lbltitel">' + esc(naam) + "</span>"
                '<span class="lblbij">' + esc(bij) + "</span>"
                "</span></span>" + badge + "</a>")

    vlag = ""
    if melding:
        soort, tekst = melding
        vlag = ('<div class="vlag ' + esc(soort) + '">' + esc(tekst) + "</div>")

    groep_van = {p: g for p, _, g, _ in MENU}
    naam_van = {p: n for p, n, _, _ in MENU}
    kruimels = ('<nav class="kruimels" aria-label="Waar je bent">'
                "<span>" + esc(groep_van.get(pad, "Vakto")) + "</span>"
                '<span class="sep">/</span>'
                "<b>" + esc(kruimel or naam_van.get(pad, titel))
                + "</b></nav>")

    return ('<!doctype html>\n<html lang="nl"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            "<title>" + esc(titel) + " — Vakto</title>\n"
            '<link rel="stylesheet" href="/stijl.css">\n'
            "</head><body" + (' class="' + esc(lichaam) + '"' if lichaam else "")
            + ">\n"
            '<div id="nav">\n'
            '  <div class="merk">' + MERKTEKEN
            + '<span class="merknaam">Vakto</span></div>\n'
            '  <div class="ondertitel">Warehouse Management</div>\n  '
            + "\n  ".join(nav) + "\n"
            '  <div class="visite"><div class="visite-merk">Magazijn</div>'
            "<div>" + esc(klant) + "</div></div>\n"
            "</div>\n<main>\n"
            '  <header id="balkboven">' + kruimels + "</header>\n"
            '  <div id="inhoud">' + inhoud + "</div>\n"
            + vlag + "\n</main>\n</body></html>")


def tabel(koppen: list[str], rijen: list[list[str]],
          leeg: str = "Niets te zien.") -> str:
    if not rijen:
        return '<p class="leeg">' + esc(leeg) + "</p>"
    kop = "".join("<th>" + esc(k) + "</th>" for k in koppen)
    lijf = "".join("<tr>" + "".join("<td>" + c + "</td>" for c in r) + "</tr>"
                   for r in rijen)
    return ('<div class="tabelwrap"><table><thead><tr>' + kop
            + "</tr></thead><tbody>" + lijf + "</tbody></table></div>")


def knop(tekst: str, pad: str, velden: dict | None = None,
         soort: str = "", strak: bool = False) -> str:
    """Een knop is een formulier: alles wat iets verandert is een POST.

    Geen links die boeken. Een browser mag een link vooruit ophalen, en
    dan staat er ineens voorraad afgeboekt omdat iemand er met de muis
    overheen ging.

    `strak` laat de marge van `.knoprij` weg. In een tabelcel duwt die
    de knop een regel naar beneden, en dan staat hij niet meer naast de
    rij waar hij bij hoort.
    """
    verborgen = "".join(
        '<input type="hidden" name="' + esc(k) + '" value="' + esc(v) + '">'
        for k, v in (velden or {}).items())
    return ('<form method="post" action="' + esc(pad) + '"'
            + ("" if strak else ' class="knoprij"') + ">"
            + verborgen + '<button class="' + esc(soort) + '">' + esc(tekst)
            + "</button></form>")


# ---------------------------------------------------------------------
#  De schermen
# ---------------------------------------------------------------------
def dashboard(cijfers: dict, log: list[tuple]) -> str:
    """Waar staat het magazijn nu, en wat heeft het zelf besloten?"""
    vakjes = "".join(
        '<div class="controle-cijfer"><b>' + getal(w) + "</b>"
        "<span>" + esc(n) + "</span></div>"
        for n, w in cijfers.items())
    regels = "".join(
        '<div class="logregel">' + pil(_logkleur(n), n) + " "
        + '<span class="hint">' + _tijd(at) + "</span> " + esc(b) + "</div>"
        for n, b, at in log[:20])
    if not regels:
        regels = '<p class="leeg">Nog niets gebeurd.</p>'
    return ("<h1>Dashboard</h1>\n"
            '<p class="lead">Wat er stilstaat en dus opgelost moet worden.</p>\n'
            '<div class="kaart"><div class="controle-cijfers">' + vakjes
            + "</div></div>\n"
            '<div class="kaart"><h2>Wat het systeem zelf besloten heeft</h2>'
            '<div class="logboek">' + regels + "</div></div>")


def _logkleur(niveau: str) -> str:
    return {"WARN": "o", "FOUT": "r"}.get(niveau, "n")


def _tijd(waarde) -> str:
    tekst = str(waarde or "")
    return esc(tekst[11:16])


def werklijst(taken: list[tuple]) -> str:
    """R-ZC en R-OPT: het werk dat het systeem zelf heeft klaargezet."""
    rijen = []
    for t in taken:
        (tid, soort, naam, prio, _pid, sku, _oms, _van, van_code,
         _naar, naar_code, qty, _aanleiding, reden, _at) = t
        rijen.append([
            pil("n", soort), esc(naam),
            '<span class="num">' + esc(prio) + "</span>",
            '<span class="mono">' + esc(sku) + "</span>",
            '<span class="mono">' + esc(van_code) + "</span>",
            '<span class="mono">' + esc(naar_code) + "</span>",
            '<span class="num">' + getal(qty) + "</span>",
            '<span class="hint">' + esc(reden) + "</span>",
            knop("Afmelden", "/taken", {"taak": tid, "aantal": qty or ""},
                 "klein", strak=True),
        ])
    return ("<h1>Taken</h1>\n"
            '<p class="lead">Niemand maakt deze aan en niemand vinkt ze af: '
            "ze volgen uit de toestand van het magazijn en vervallen zodra ze "
            "overbodig zijn.</p>\n"
            + tabel(["Soort", "Wat", "Prio", "Artikel", "Van", "Naar",
                     "Aantal", "Waarom", ""], rijen, "Geen openstaand werk."))


STATUSKLEUR = {"NIEUW": "n", "GERESERVEERD": "a", "WACHT_OP_VOORRAAD": "r",
               "VRIJGEGEVEN": "a", "PICKEN": "o", "GEPICKT": "g",
               "INGEPAKT": "g", "VERZONDEN": "g"}


def orders(rijen_in: list[tuple]) -> str:
    rijen = []
    for oid, nummer, klant, status, prio, regels in rijen_in:
        rijen.append([
            '<a href="/orders/' + esc(oid) + '" class="mono">'
            + esc(nummer) + "</a>",
            esc(klant), pil(STATUSKLEUR.get(status, "n"), status),
            '<span class="num">' + esc(prio) + "</span>",
            '<span class="num">' + esc(regels) + "</span>",
        ])
    return ("<h1>Orders</h1>\n"
            '<p class="lead">Klantorders van binnenkomst tot verzending. '
            "Open orders bovenaan, op prioriteit.</p>\n"
            + tabel(["Order", "Klant", "Status", "Prio", "Regels"], rijen,
                    "Geen orders."))


def order(kop: tuple, regels: list[tuple], toewijzingen: list[tuple]) -> str:
    oid, nummer, klant, status, prio, colli, gewicht = kop
    rijen = [['<span class="mono">' + esc(sku) + "</span>", esc(oms),
              '<span class="num">' + getal(besteld) + "</span>",
              '<span class="num">' + getal(gereserveerd) + "</span>",
              '<span class="num">' + getal(gepickt) + "</span>",
              '<span class="num">' + (getal(manco) if manco else "") + "</span>"]
             for sku, oms, besteld, gereserveerd, gepickt, manco in regels]
    toe = [['<span class="mono">' + esc(code) + "</span>",
            '<span class="mono">' + esc(sku) + "</span>",
            '<span class="num">' + getal(qty) + "</span>",
            '<span class="num">' + getal(gepickt) + "</span>",
            pil("g" if st == "DONE" else "r" if st == "MANCO" else "n", st)]
           for code, sku, qty, gepickt, st in toewijzingen]

    # Alleen de stap die nu aan de beurt is. R-UIT-01 kent de volgorde;
    # een knop die toch geweigerd wordt is een knop die niet hoort te
    # staan.
    knoppen = ""
    if status in ("NIEUW", "WACHT_OP_VOORRAAD"):
        knoppen = knop("Reserveren", "/orders/" + str(oid),
                       {"actie": "reserveer"})
    elif status == "GERESERVEERD":
        knoppen = knop("Vrijgeven voor picken", "/orders/" + str(oid),
                       {"actie": "vrijgeven"})
    elif status == "GEPICKT":
        knoppen = knop("Inpakken en verzenden", "/orders/" + str(oid),
                       {"actie": "verzenden"})

    pakbon = ""
    if colli:
        pakbon = ('<p class="hint">' + getal(colli)
                  + (" collo, " if colli == 1 else " colli, ")
                  + getal(gewicht) + " g</p>")
    return ("<h1>" + esc(nummer) + "</h1>\n"
            '<p class="lead">' + esc(klant) + " — "
            + pil(STATUSKLEUR.get(status, "n"), status)
            + " — prioriteit " + esc(prio) + "</p>\n" + pakbon + knoppen
            + '\n<div class="kaart"><h2>Regels</h2>'
            + tabel(["Artikel", "Omschrijving", "Besteld", "Gereserveerd",
                     "Gepickt", "Manco"], rijen) + "</div>\n"
            '<div class="kaart"><h2>Waar het vandaan komt</h2>'
            + tabel(["Locatie", "Artikel", "Aantal", "Gepickt", "Stand"], toe,
                    "Nog niets gereserveerd.") + "</div>")


def picken(regels: list) -> str:
    """R-UIT-03. Op looproute, want dat is het hele verschil."""
    kaarten = []
    for i, r in enumerate(regels):
        kaarten.append(
            '<div class="kaart pickkaart">'
            '<div class="pickkop"><span class="hint">'
            + esc(r.ordernummer) + "</span>"
            + pil("a", "regel " + str(i + 1) + " van " + str(len(regels)))
            + "</div>"
            '<div class="picklocatie mono">' + esc(r.locatie) + "</div>"
            '<div class="pickartikel"><b>' + esc(r.sku) + "</b><br>"
            '<span class="hint">' + esc(r.oms) + "</span></div>"
            '<div class="pickaantal"><span class="pickcijfer">'
            + getal(r.nog_te_picken) + '</span><span class="hint">stuks '
            "te pakken</span></div>"
            '<form method="post" action="/picken" class="knoprij">'
            '<input type="hidden" name="regel" value="'
            + esc(r.allocation_id) + '">'
            '<input type="number" name="aantal" value="'
            + esc(r.nog_te_picken) + '" min="0" max="'
            + esc(r.nog_te_picken) + '">'
            "<button>Afmelden</button></form></div>")
    inhoud = "".join(kaarten) or '<p class="leeg">Niets te picken.</p>'
    return ("<h1>Picken</h1>\n"
            '<p class="lead">Op looproute, niet op ordervolgorde. Dat is het '
            "verschil tussen één keer door de gang lopen en heen en weer "
            "sjouwen. Minder dan gevraagd afmelden is een manco: de "
            "reservering komt vrij en er komt een teltaak.</p>\n"
            '<div class="tweeluik">' + inhoud + "</div>")


# ---------------------------------------------------------------------
#  Scanmodus (R-SCAN). Vol scherm, grote raakvlakken, één invoerveld.
# ---------------------------------------------------------------------
SCANTAAK_NAAM = {"PICKEN": "Picken", "TELLEN": "Tellen",
                 "INSLAG": "Inslag", "VRIJ": "Vrij"}


def scanscherm(scanner, laatste=None) -> str:
    """R-SCAN-01 t/m R-SCAN-07. De cursor staat altijd in het invoerveld."""
    from .scannen import STAPPEN, TAKEN

    taken = "".join(
        '<form method="post" action="/scan">'
        '<input type="hidden" name="actie" value="taak">'
        '<input type="hidden" name="taak" value="' + t + '">'
        '<button class="scantaak' + (" aan" if scanner.taak == t else "")
        + '">' + SCANTAAK_NAAM[t] + "</button></form>"
        for t in TAKEN)

    stappen = "".join(
        '<span class="scanstap' + _stapstand(scanner, s, STAPPEN[scanner.taak])
        + '">' + esc(s.replace("_", " ").lower()) + "</span>"
        for s in STAPPEN[scanner.taak])

    bericht = ""
    if laatste is not None and laatste.bericht:
        bericht = ('<div class="scanbericht ' + esc(laatste.soort) + '">'
                   + esc(laatste.bericht) + "</div>")

    if scanner.stap == "KLAAR":
        inhoud = ('<div class="scanklaar"><div class="scangroot">Klaar</div>'
                  '<p class="scanhint">Er staat niets meer open.</p></div>')
    else:
        inhoud = '<div class="scaninhoud">' + _scanvelden(scanner) + "</div>"

    aantal = ""
    if scanner.stap in ("AANTAL", "TEL_AANTAL", "INSLAG_AANTAL"):
        vooraf = (scanner.regel.nog_te_picken
                  if scanner.stap == "AANTAL" and scanner.regel else "")
        aantal = ('<form method="post" action="/scan">'
                  '<input type="hidden" name="actie" value="bevestig">'
                  '<div class="aantalrij"><input type="number" name="aantal" '
                  'value="' + esc(vooraf) + '" min="0" autofocus></div>'
                  '<button class="groot">Bevestigen</button></form>')

    log = "".join('<div class="scanlogregel">' + esc(r) + "</div>"
                  for r in scanner.gescand[:10])

    wie = esc(scanner.gebruiker or "niet ingelogd")
    return ('<div class="scanschil">'
            '<div class="scanbalk">'
            '<a class="knop scanuit" href="/">×</a>'
            '<div class="scantaken">' + taken + "</div>"
            '<span class="scanwie">' + wie + "</span></div>"
            '<div class="scanstappen">' + stappen + "</div>"
            + bericht + inhoud
            + '<form method="post" action="/scan" class="scaninvoer">'
            '<input type="hidden" name="actie" value="scan">'
            '<input name="code" placeholder="Scan of typ een code" '
            'autocomplete="off" autofocus>'
            "<button>Verwerken</button></form>"
            + aantal
            + '<form method="post" action="/scan">'
            '<input type="hidden" name="actie" value="overslaan">'
            '<button class="stil">Overslaan</button></form>'
            '<div class="scanlog">' + log + "</div></div>")


def _stapstand(scanner, stap: str, stappen: tuple) -> str:
    if scanner.stap == stap:
        return " nu"
    if scanner.stap in stappen and stappen.index(stap) < stappen.index(scanner.stap):
        return " gedaan"
    return ""


def _scanveld(label: str, waarde: str, vraag: bool, hint: str = "") -> str:
    stand = " vraag" if vraag else (" gedaan" if waarde else "")
    vink = '<span class="scanvink">✓</span>' if waarde and not vraag else ""
    return ('<div class="scanveld' + stand + '">'
            '<span class="scanlabel">' + esc(label) + "</span>"
            '<span class="scanwaarde">' + (esc(waarde) or "—") + "</span>"
            + ('<span class="scanhint">' + esc(hint) + "</span>" if hint else "")
            + vink + "</div>")


def _scanvelden(scanner) -> str:
    """Wat er nu op het scherm hoort te staan, per taak."""
    locatie = scanner._locatiecode(scanner.locatie_id) if scanner.locatie_id else ""
    art = scanner.mag.artikel(scanner.product_id) if scanner.product_id else None
    sku = art.sku if art else ""
    oms = art.oms if art else ""

    if scanner.taak == "PICKEN":
        r = scanner.regel
        if r is None:
            return ""
        return (_scanveld("Loop naar", r.locatie, scanner.stap == "LOCATIE")
                + _scanveld("Pak", r.sku, scanner.stap == "ARTIKEL", r.oms)
                + _scanveld("Aantal", str(r.nog_te_picken),
                            scanner.stap == "AANTAL", "stuks gevraagd"))
    if scanner.taak == "TELLEN":
        return (_scanveld("Vak", locatie, scanner.stap == "LOCATIE")
                + _scanveld("Artikel", sku, scanner.stap == "TEL_ARTIKEL", oms)
                + _scanveld("Geteld", "", scanner.stap == "TEL_AANTAL",
                            "wat er echt ligt"))
    if scanner.taak == "INSLAG":
        return (_scanveld("Artikel", sku, scanner.stap == "ARTIKEL", oms)
                + _scanveld("Aantal", str(scanner.aantal or ""),
                            scanner.stap == "INSLAG_AANTAL")
                + _scanveld("Leg neer op", locatie,
                            scanner.stap == "INSLAG_LOCATIE",
                            "scan een van de voorgestelde plekken"))
    return (_scanveld("Locatie", locatie, False)
            + _scanveld("Artikel", sku, False, oms))


# ---------------------------------------------------------------------
#  Magazijn
# ---------------------------------------------------------------------
def locaties(rijen_in: list[tuple]) -> str:
    rijen = [['<span class="mono">' + esc(code) + "</span>", esc(zone),
              esc(soort), maatpil(maat),
              '<span class="num">' + getal(l) + "×" + getal(w) + "×"
              + getal(h) + "</span>",
              '<span class="num">' + getal(soorten) + "</span>",
              '<span class="num">' + getal(stuks) + "</span>"]
             for code, zone, soort, maat, l, w, h, soorten, stuks in rijen_in]
    return ("<h1>Locaties</h1>\n"
            '<p class="lead">Elke plek met zijn echte binnenmaat en '
            "draagvermogen. De maatklasse staat nergens opgeslagen: die "
            "volgt uit het volume (R-AFG-02).</p>\n"
            + tabel(["Code", "Zone", "Soort", "Maat", "Binnenmaat (mm)",
                     "Soorten", "Stuks"], rijen, "Geen locaties."))


def artikelen(rijen_in: list[tuple]) -> str:
    rijen = []
    for sku, oms, groep, l, w, h, g, voorraad, bron in rijen_in:
        maat = (getal(l) + "×" + getal(w) + "×" + getal(h) + " mm, "
                + getal(g) + " g" if l else pil("r", "nog opmeten"))
        rijen.append(['<span class="mono">' + esc(sku) + "</span>", esc(oms),
                      esc(groep), maat,
                      '<span class="num">' + getal(voorraad or 0) + "</span>",
                      esc(bron)])
    return ("<h1>Artikelen</h1>\n"
            '<p class="lead">De actuele maat is de nieuwste meting, geen veld '
            "(R-AFG-01). Zonder maat kan het systeem niets uitrekenen.</p>\n"
            + tabel(["Artikel", "Omschrijving", "Groep", "Actuele maat",
                     "Voorraad", "Bron"], rijen, "Geen artikelen."))


def meetlijst(rijen_in: list[tuple]) -> str:
    """R-MEET-04. Nooit gemeten bovenaan, daarna de oudste."""
    REDEN = {"NOOIT_GEMETEN": ("r", "nooit gemeten"),
             "OPGAVE_LEVERANCIER": ("o", "opgave leverancier"),
             "TE_OUD": ("a", "te oud")}
    rijen = []
    for pid, sku, oms, gemeten_op, _bron, reden in rijen_in:
        kleur, tekst = REDEN.get(reden, ("n", reden))
        rijen.append([
            '<span class="mono">' + esc(sku) + "</span>", esc(oms),
            pil(kleur, tekst), datum(gemeten_op),
            '<form method="post" action="/meten" class="meetrij">'
            '<input type="hidden" name="product" value="' + esc(pid) + '">'
            '<input type="number" name="l" placeholder="L" min="1" required>'
            '<input type="number" name="w" placeholder="B" min="1" required>'
            '<input type="number" name="h" placeholder="H" min="1" required>'
            '<input type="number" name="g" placeholder="g" min="1" required>'
            '<button class="klein">Vastleggen</button></form>'])
    return ("<h1>Opmeten</h1>\n"
            '<p class="lead">Een artikelmaat is een tijdlijn, geen veld. Wie '
            "de maat overschrijft weet volgende maand niet meer dat de doos "
            "in maart groter werd — en snapt dus ook niet waarom er ineens "
            "pallets te weinig plek is.</p>\n"
            + tabel(["Artikel", "Omschrijving", "Waarom", "Laatst gemeten",
                     "Nieuwe maat (mm / g)"], rijen, "Alles is opgemeten."))


def inslag(keuze_in: list[tuple], gekozen=None, aantal: int = 24,
           voorstellen=None, maten: dict | None = None) -> str:
    """R-INS-01 t/m R-INS-04. Niet "past het" maar "hoe goed benut je het"."""
    maten = maten or {}
    keuze = "".join(
        '<option value="' + esc(pid) + '"'
        + (" selected" if str(gekozen) == str(pid) else "") + ">"
        + esc(sku) + " — " + esc(oms) + "</option>"
        for pid, sku, oms in keuze_in)
    rijen = []
    for v in (voorstellen or []):
        rijen.append([
            '<span class="mono">' + esc(v.locatie.code) + "</span>",
            maatpil(maten.get(v.locatie.id, "")),
            '<span class="num">' + getal(v.vrij) + "</span>",
            pil("g", "alles") if v.alles else pil("o", "deel"),
            '<span class="num">' + f"{v.benutting * 100:.1f}" + "%</span>",
            '<span class="num"><b>' + esc(v.score) + "</b></span>",
            '<span class="hint">' + esc(", ".join(v.redenen)) + "</span>"])
    return ("<h1>Inslag</h1>\n"
            '<p class="lead">Er komt iets binnen: het systeem rekent uit op '
            "welke locatie het past. Niet \"past het\" maar \"hoe goed benut "
            "je de ruimte\" — veertig schroefsets horen niet in een "
            "palletplaats, ook al passen ze er.</p>\n"
            '<form method="get" action="/inslag" class="filters">'
            '<label>Artikel<select name="product">' + keuze + "</select></label>"
            '<label>Aantal<input type="number" name="aantal" value="'
            + esc(aantal) + '" min="1"></label>'
            "<button>Voorstel</button></form>\n"
            + tabel(["Locatie", "Maat", "Past", "Alles?", "Benutting",
                     "Score", "Waarom"], rijen,
                    "Geen plek gevonden. Is het artikel al opgemeten?"))
