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
    ("/eigen",     "Eigen gegevens", "Beheer", "bestanden inlezen"),
    ("/instellingen", "Instellingen", "Beheer", "regels per klant"),
    ("/gebruikers", "Gebruikers", "Beheer",    "wie er mag werken"),
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


def initialen(naam: str) -> str:
    """Twee letters voor het rondje in de bovenbalk."""
    delen = [w for w in (naam or "").split() if w]
    return "".join(w[0] for w in delen[:2]).upper() or "?"


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
              lichaam: str = "", kruimel: str = "", gebruiker=None) -> str:
    """Het hele scherm, met navigatie eromheen.

    Zonder `gebruiker` staat het hele menu er (dat is hoe de tests een
    los scherm bekijken). Met een gebruiker erbij staan alleen de
    schermen erin waar zijn rol bij mag — R-GEB-01. Dat is opmaak en
    geen beveiliging: het weigeren zelf gebeurt in `web.py`, bij elke
    aanvraag, want wie het adres typt komt er anders alsnog (R-GEB-02).
    """
    tellers = tellers or {}
    groepen: list[tuple[str, list]] = []
    for p, naam, groep, bij in MENU:
        if gebruiker is not None and not gebruiker.mag(p):
            continue
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

    wie = ""
    if gebruiker is not None:
        wie = ('<div class="balkrechts">'
               '<span class="klantchip">' + esc(klant) + "</span>"
               '<a class="wiechip" href="/ik" title="' + esc(gebruiker.naam)
               + " — " + esc(gebruiker.rolnaam) + '">'
               '<span class="avatar">' + esc(initialen(gebruiker.naam))
               + "</span>"
               '<span class="wienaam">' + esc(gebruiker.naam.split(" ")[0])
               + "</span></a></div>")

    visite = ('  <div class="visite"><div class="visite-merk">Magazijn</div>'
              "<div>" + esc(klant) + "</div></div>")
    if gebruiker is not None:
        visite = ('  <div class="visite">'
                  '<div class="visite-merk">' + esc(gebruiker.naam) + "</div>"
                  "<div>" + esc(gebruiker.rolnaam) + "</div>"
                  + knop("Uitloggen", "/uitloggen", soort="stil klein")
                  + "</div>")

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
            + visite + "\n"
            "</div>\n<main>\n"
            '  <header id="balkboven">' + kruimels + wie + "</header>\n"
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


# ---------------------------------------------------------------------
#  Toegang (R-GEB)
#
#  Deze drie staan los van het geraamte: er is nog geen menu om te tonen
#  en geen gebruiker om in de balk te zetten.
# ---------------------------------------------------------------------
def kaal(titel: str, inhoud: str, melding: tuple[str, str] | None = None) -> str:
    """Een scherm zonder navigatie. Voor wie nog niet binnen is."""
    vlag = ""
    if melding:
        soort, tekst = melding
        vlag = '<div class="vlag ' + esc(soort) + '">' + esc(tekst) + "</div>"
    return ('<!doctype html>\n<html lang="nl"><head><meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            "<title>" + esc(titel) + " — Vakto</title>\n"
            '<link rel="stylesheet" href="/stijl.css">\n'
            '</head><body class="kaal">\n<main>\n'
            '<div class="aanmeldvak">'
            '<div class="merk">' + MERKTEKEN
            + '<span class="merknaam">Vakto</span></div>'
            + inhoud + "</div>\n" + vlag + "\n</main>\n</body></html>")


def veld(label: str, naam: str, waarde: str = "", soort: str = "text",
         hint: str = "", **rest) -> str:
    """Eén invoerregel. Losse functie omdat het er hier veel zijn en de
    aanhalingstekens anders niet meer te volgen zijn — dat is precies hoe
    er een keer een `value=` zonder waarde in een formulier belandt."""
    extra = "".join(
        " " + k.rstrip("_") + ('="' + esc(w) + '"' if w is not True else "")
        for k, w in rest.items() if w)
    return ("<label>" + esc(label)
            + ('<span class="hint"> ' + esc(hint) + "</span>" if hint else "")
            + '<input name="' + esc(naam) + '" type="' + esc(soort)
            + '" value="' + esc(waarde) + '"' + extra + "></label>")


def inloggen(fout: str | None = None, naam: str = "",
             badge_mag: bool = True, terug: str = "") -> str:
    """R-GEB-03. Wachtwoord op kantoor, badge op de vloer.

    `terug` is het scherm waar iemand heen wilde toen hij tegen de inlog
    aan liep. Dat reist als verborgen veld mee, zodat hij na het inloggen
    niet nog een keer hoeft te zoeken.
    """
    heen = ('<input type="hidden" name="terug" value="' + esc(terug) + '">'
            if terug else "")
    melding = ('<div class="melding fout">' + esc(fout) + "</div>"
               if fout else "")

    badge = ""
    if badge_mag:
        badge = ('<div class="aanmeldof">of, op de vloer</div>'
                 '<form method="post" action="/inloggen" class="aanmeldform">'
                 '<input type="hidden" name="soort" value="badge">' + heen
                 + veld("Badge", "badge", placeholder="Scan je badge",
                        autocomplete="off")
                 + '<button class="groot stil">Aanmelden voor de scanmodus'
                 "</button></form>"
                 '<p class="hint">Met een badge kom je alleen in de '
                 "scanmodus. Een badge ligt op tafel; dat is geen "
                 "wachtwoord.</p>")

    return ("<h1>Inloggen</h1>" + melding
            + '<form method="post" action="/inloggen" class="aanmeldform">'
            '<input type="hidden" name="soort" value="wachtwoord">' + heen
            + veld("Gebruikersnaam", "gebruikersnaam", naam,
                   autocomplete="username", autofocus=True, required=True)
            + veld("Wachtwoord", "wachtwoord", soort="password",
                   autocomplete="current-password", required=True)
            + '<button class="groot">Inloggen</button></form>' + badge)


def eerste_beheerder(fout: str | None = None, naam: str = "",
                     gebruikersnaam: str = "") -> str:
    """R-GEB-08. Alleen als de gebruikerstabel leeg is.

    Geen standaardwachtwoord in het schema: dat staat in de
    installatiehandleiding en die staat op internet.
    """
    melding = ('<div class="melding fout">' + esc(fout) + "</div>"
               if fout else "")
    return ("<h1>Eerste beheerder</h1>"
            '<p class="lead">Er is nog niemand. Maak jezelf aan als '
            "beheerder; daarna is deze weg dicht en maak je de rest van de "
            "mensen aan vanuit het gebruikersscherm.</p>" + melding
            + '<form method="post" action="/opzetten" class="aanmeldform">'
            + veld("Je naam", "naam", naam, placeholder="Dennis Wijgers",
                   required=True, autofocus=True)
            + veld("Gebruikersnaam", "gebruikersnaam", gebruikersnaam,
                   placeholder="dennis", autocomplete="username",
                   required=True)
            + veld("Wachtwoord", "wachtwoord", soort="password",
                   autocomplete="new-password", required=True)
            + veld("Nog een keer", "nogmaals", soort="password",
                   autocomplete="new-password", required=True)
            + veld("Badge", "badge", hint="(mag leeg)",
                   placeholder="BADGE-1001", autocomplete="off")
            + '<button class="groot">Aanmaken en inloggen</button></form>'
            '<p class="hint">Minstens twaalf tekens. Lengte doet het werk; '
            'een regel over hoofdletters en leestekens levert alleen '
            '"Zomer2024!" op.</p>')


def geweigerd(gebruiker, pad: str, nodig: str) -> str:
    """R-GEB-02. Zeggen wat er nodig is, niet alleen nee."""
    return ("<h1>Hier mag je niet bij</h1>"
            '<p class="lead">Je bent ingelogd als '
            + esc(gebruiker.rolnaam.lower()) + ". Voor <span class=\"mono\">"
            + esc(pad) + "</span> heb je " + esc(nodig.lower())
            + " nodig.</p>"
            '<p class="hint">Klopt dat niet, vraag dan de beheerder om je rol '
            "aan te passen. Dat is één regel in het gebruikersscherm.</p>"
            '<div class="knoprij"><a class="knop" href="/">Naar je '
            "beginscherm</a></div>")


ROLKEUZE = (("OPERATOR", "Magazijnmedewerker"),
            ("SUPERVISOR", "Teamleider"),
            ("ADMIN", "Beheerder"))


def gebruikers(rijen_in: list[tuple], ikzelf: int | None = None) -> str:
    """Het beheerscherm. Alleen voor rang 3."""
    KLEUR = {"ADMIN": "r", "SUPERVISOR": "a", "OPERATOR": "n"}
    rijen = []
    for (uid, naam, gnaam, rol, badge, actief, at, heeft_ww,
         sessies) in rijen_in:
        rolkeuze = "".join(
            '<option value="' + k + '"' + (" selected" if k == rol else "")
            + ">" + v + "</option>" for k, v in ROLKEUZE)
        rijen.append([
            esc(naam) + (' <span class="hint">(jij)</span>'
                         if uid == ikzelf else ""),
            '<span class="mono">' + esc(gnaam) + "</span>",
            pil(KLEUR.get(rol, "n"), rol),
            '<span class="mono">' + esc(badge) + "</span>",
            (pil("g", "actief") if actief else pil("r", "uit dienst")),
            (pil("g", str(sessies)) if sessies else
             '<span class="hint">—</span>'),
            ('<form method="post" action="/gebruikers" class="meetrij">'
             '<input type="hidden" name="actie" value="rol">'
             '<input type="hidden" name="id" value="' + esc(uid) + '">'
             '<select name="rol">' + rolkeuze + "</select>"
             '<button class="klein">Rol</button></form>'),
            (knop("Uit dienst", "/gebruikers",
                  {"actie": "uit", "id": uid}, "klein stil", strak=True)
             if actief and uid != ikzelf else ""),
        ])
    nieuwe = """
    <div class="kaart"><h2>Iemand toevoegen</h2>
      <form method="post" action="/gebruikers" class="filters">
        <input type="hidden" name="actie" value="nieuw">
        <label>Naam<input name="naam" required placeholder="Kevin Timmermans">
          </label>
        <label>Gebruikersnaam<input name="gebruikersnaam" required
          placeholder="kevin" autocomplete="off"></label>
        <label>Rol<select name="rol">""" + "".join(
        '<option value="' + k + '">' + v + "</option>" for k, v in ROLKEUZE
    ) + """</select></label>
        <label>Wachtwoord <span class="hint">(mag leeg bij alleen een badge)
          </span><input name="wachtwoord" type="password"
          autocomplete="new-password"></label>
        <label>Badge<input name="badge" placeholder="BADGE-1003"
          autocomplete="off"></label>
        <button>Toevoegen</button>
      </form>
      <p class="hint">Zonder wachtwoord komt iemand alleen met zijn badge de
      scanmodus in — precies genoeg voor wie de hele dag op de vloer staat.</p>
    </div>"""
    return ("<h1>Gebruikers</h1>"
            '<p class="lead">Drie rollen met een rang, geen lijst met vinkjes. '
            "Wie welk scherm mag zien volgt daaruit, en het wordt bij elke "
            "aanvraag op de server getoetst — niet alleen in het menu.</p>"
            + tabel(["Naam", "Gebruikersnaam", "Rol", "Badge", "Stand",
                     "Sessies", "", ""], rijen, "Nog niemand.")
            + nieuwe)


def ikzelf(gebruiker, sessies: int = 0) -> str:
    """Wie ben ik, en hoe kom ik hier weer uit."""
    return ("<h1>" + esc(gebruiker.naam) + "</h1>"
            '<p class="lead">' + esc(gebruiker.rolnaam) + " — rang "
            + esc(gebruiker.rang) + "</p>"
            '<div class="kaart"><h2>Wat je mag</h2>'
            + tabel(["Scherm", "Toegang"],
                    [[esc(naam),
                      pil("g", "ja") if gebruiker.mag(p) else pil("n", "nee")]
                     for p, naam, _g, _b in MENU])
            + "</div>"
            + knop("Uitloggen", "/uitloggen", soort="stil"))


# ---------------------------------------------------------------------
#  Instellingen (hoofdstuk 14, R-INST-01)
# ---------------------------------------------------------------------
def instellingen(rijen_in: list[tuple], klachten: dict | None = None) -> str:
    """Alles wat per klant kan verschillen, op groep geordend.

    Dit scherm is het antwoord op "ja maar bij ons gaat dat anders", en
    de reden dat dat antwoord geen programmeerwerk is. Eén formulier voor
    alles: wie drie dingen wil wijzigen, wil niet drie keer opslaan.
    """
    from .instellingen import SOORT

    klachten = klachten or {}
    groepen: list[tuple[str, list]] = []
    for sleutel, waarde, groep, uitleg in rijen_in:
        if not groepen or groepen[-1][0] != groep:
            groepen.append((groep, []))
        groepen[-1][1].append((sleutel, waarde, uitleg))

    kaarten = []
    for groep, regels in groepen:
        rijen = []
        for sleutel, waarde, uitleg in regels:
            soort, laag, hoog = SOORT.get(sleutel, ("tekst", None, None))
            klacht = klachten.get(sleutel)
            if soort == "janee":
                invoer = ('<select name="' + esc(sleutel) + '">'
                          + "".join(
                              '<option value="' + w + '"'
                              + (" selected" if str(waarde).lower() == w else "")
                              + ">" + n + "</option>"
                              for w, n in (("true", "ja"), ("false", "nee")))
                          + "</select>")
            elif soort == "komma":
                # Met opzet geen type="number". Een Nederlander typt
                # 0,60, en een getalveld weigert die komma zonder uit te
                # leggen waarom — in een browser met een Engelse taal
                # instelling verdwijnt de toetsaanslag gewoon. De toets
                # op de server begrijpt de komma wél (R-INST-01), en de
                # zin die daar uitkomt is duidelijker dan een tooltip
                # van de browser.
                invoer = ('<input name="' + esc(sleutel) + '" value="'
                          + esc(waarde) + '" inputmode="decimal">'
                          '<div class="hint">tussen ' + esc(_kort(laag))
                          + " en " + esc(_kort(hoog)) + "</div>")
            else:
                grens = ""
                if laag is not None:
                    grens = (' min="' + esc(_kort(laag)) + '" max="'
                             + esc(_kort(hoog)) + '"')
                invoer = ('<input type="number" step="1" name="'
                          + esc(sleutel) + '" value="' + esc(waarde) + '"'
                          + grens + ">")
                if laag is not None:
                    # Ook hier het bereik erbij. De browser houdt het
                    # tegen, maar zonder een tooltip te openen weet
                    # niemand waarom een 3 wél mag en een 2 niet.
                    invoer += ('<div class="hint">tussen ' + esc(_kort(laag))
                               + " en " + esc(_kort(hoog)) + "</div>")
            rijen.append([
                '<span class="mono">' + esc(sleutel) + "</span>",
                invoer + ('<div class="fout hint">' + esc(klacht) + "</div>"
                          if klacht else ""),
                '<span class="hint">' + esc(uitleg) + "</span>"])
        kaarten.append('<div class="kaart"><h2>' + esc(groep) + "</h2>"
                       + tabel(["Sleutel", "Waarde", "Wat het doet"], rijen)
                       + "</div>")

    return ("<h1>Instellingen</h1>"
            '<p class="lead">Alles wat per klant kan verschillen staat hier, '
            "en niet in de code. Dát is wat \"een algemeen systeem dat je per "
            "klant inricht\" in de praktijk betekent.</p>"
            '<div class="uitleg"><b>Probeer dit eens.</b> Zet '
            '<span class="mono">putaway.fill_factor</span> op 0,60 en doe '
            "daarna dezelfde inslag opnieuw. Alle voorstellen veranderen, "
            "zonder dat er ook maar één regel code is aangepast. Dat is het "
            "antwoord op \"ja, maar bij ons stapelen we anders\".</div>"
            '<form method="post" action="/instellingen">'
            + "".join(kaarten)
            + '<div class="knoprij"><button>Opslaan</button></div></form>'
            '<p class="hint">Elke wijziging komt met de oude waarde en jouw '
            "naam in het systeemlog. Een magazijn waar de vulfactor ineens op "
            "0,4 staat en niemand weet sinds wanneer, is een magazijn waar "
            "niemand de voorstellen meer gelooft.</p>")


def _kort(n) -> str:
    if n is None:
        return ""
    return str(int(n)) if float(n) == int(n) else str(n)


# ---------------------------------------------------------------------
#  Eigen gegevens (R-IMP)
#
#  Het scherm dat het verschil maakt tussen "kijk eens wat een mooie
#  demo" en "kijk, dit is jouw magazijn". De volgorde is met opzet:
#  kiezen, kolommen bevestigen, eenheid nakijken, rapport lezen, en pas
#  daarna de knop. Raden zonder tonen is precies hoe imports stilletjes
#  fout gaan (R-IMP-02).
# ---------------------------------------------------------------------
SOORTNAAM = {"locaties": "Locatiebestand", "artikelen": "Artikelbestand",
             "voorraad": "Voorraadbestand"}

SOORTUITLEG = {
    "locaties": "Elke stellingplaats één regel. Minimaal de code; "
                "afmetingen als je ze hebt.",
    "artikelen": "Elk artikel één regel. Zonder maten kan het ook — die "
                 "komen dan op de meetlijst.",
    "voorraad": "Wat er nu waar ligt. Heb je dit niet, sla het over en "
                "begin met een nulmeting.",
}


def _bestandsblok(soort: str, bestand, kolommen: dict) -> str:
    from .inlezen import VELDEN

    verplicht = soort == "locaties"
    kop = ('<div class="impkop"><div><b>' + SOORTNAAM[soort] + "</b> "
           + (pil("a", "nodig") if verplicht else pil("n", "mag ontbreken"))
           + '<div class="hint">' + esc(SOORTUITLEG[soort]) + "</div></div>"
           '<label class="impknop"><span>'
           + ("Ander bestand" if bestand else "Kies bestand") + "</span>"
           '<input type="file" name="' + soort + '" '
           'accept=".csv,.txt,.xlsx,.xlsm" hidden onchange="this.form.submit()">'
           "</label></div>")

    if bestand is None:
        return '<div class="impvak">' + kop + "</div>"

    rijen = []
    for veld in VELDEN[soort]:
        gekozen = kolommen.get(veld.k)
        keuze = ('<option value="">— niet aanwezig —</option>'
                 + "".join(
                     '<option value="' + str(i) + '"'
                     + (" selected" if gekozen == i else "") + ">"
                     + esc(h) + "</option>"
                     for i, h in enumerate(bestand.kop)))
        proef = ""
        if gekozen is not None:
            waarden = [r[gekozen] for r in bestand.rijen[:3]
                       if gekozen < len(r) and r[gekozen]]
            proef = esc(" · ".join(waarden))
        mist = gekozen is None and veld.eis
        rijen.append([
            esc(veld.naam) + (' <span class="fout">*</span>' if veld.eis else "")
            + ('<div class="fout hint">niet gevonden — kies zelf</div>'
               if mist else ""),
            '<select name="kolom.' + soort + "." + veld.k + '">' + keuze
            + "</select>",
            '<span class="mono hint">' + (proef or "—") + "</span>"])

    return ('<div class="impvak geladen">' + kop
            + '<div class="impgelezen"><span class="mono">'
            + esc(bestand.naam) + "</span>"
            '<span class="hint">' + getal(len(bestand.rijen)) + " regels, "
            + getal(len(bestand.kop)) + " kolommen</span></div>"
            + tabel(["Vakto verwacht", "Jouw kolom", "Eerste waarden"], rijen)
            + "</div>")


def _eenheidsblok(bestanden: dict, kolommen: dict, eenheden,
                  voorbeelden: dict) -> str:
    if not bestanden:
        return ""

    def kies(sleutel: str, opties) -> str:
        nu = getattr(eenheden, sleutel)
        return ('<select name="eenheid.' + sleutel + '">'
                + "".join('<option value="' + w + '"'
                          + (" selected" if nu == w else "") + ">" + n
                          + "</option>" for w, n in opties) + "</select>")

    velden = []
    if bestanden.get("locaties"):
        velden.append('<label class="inlijn">Locatiematen in '
                      + kies("loc_maat", (("mm", "millimeter"),
                                          ("cm", "centimeter"),
                                          ("m", "meter"))) + "</label>")
        velden.append('<label class="inlijn">Draagvermogen in '
                      + kies("loc_gew", (("kg", "kilo"), ("g", "gram")))
                      + "</label>")
    if bestanden.get("artikelen"):
        velden.append('<label class="inlijn">Artikelmaten in '
                      + kies("art_maat", (("mm", "millimeter"),
                                          ("cm", "centimeter"),
                                          ("m", "meter"))) + "</label>")
        velden.append('<label class="inlijn">Artikelgewicht in '
                      + kies("art_gew", (("g", "gram"), ("kg", "kilo")))
                      + "</label>")

    proeven = ""
    for soort in ("locaties", "artikelen"):
        v = voorbeelden.get(soort)
        if v is None:
            continue
        gewicht = ""
        if v.g:
            gewicht = (", " + (f"{v.g / 1000:.1f} kg" if v.g >= 1000
                               else getal(v.g) + " gram"))
        proeven += ('<div class="melding ' + ("waarschuw" if v.raar else "")
                    + '"><span class="mono">' + esc(v.naam) + "</span> wordt "
                    "<b>" + getal(v.l_mm) + " × " + getal(v.w_mm) + " × "
                    + getal(v.h_mm) + " mm</b>" + gewicht + "."
                    + ('<span class="hint"> Dat lijkt niet te kloppen voor '
                       + ("een stellingvak" if soort == "locaties"
                          else "een artikel")
                       + ". Zet de eenheid om.</span>" if v.raar else "")
                    + "</div>")

    return ('<div class="kaart"><h2>In welke eenheid staat het?</h2>'
            '<div class="filters">' + "".join(velden) + "</div>"
            '<p class="hint">Vakto raadt dit uit de getallen zelf. Klopt het '
            "niet, zet het hier om. Kijk vooral naar de regel hieronder: dáár "
            "zie je meteen of het klopt.</p>" + proeven + "</div>")


def _rapportblok(rapport, standaard) -> str:
    def deel(d, titel: str) -> list | None:
        if not d.rijen:
            return None
        problemen = "".join(
            '<div class="impprobleem ' + esc(p.ernst) + '">'
            + pil("r" if p.ernst == "fout" else "o", getal(p.n) + "×") + " "
            + esc(p.tekst) + ' <span class="hint mono">'
            + esc(", ".join(p.voorbeeld)) + (" …" if p.n > 3 else "")
            + "</span></div>" for p in d.problemen)
        return ['<span class="sterk">' + titel + "</span>",
                '<span class="num">' + getal(d.rijen) + "</span>",
                '<span class="num' + (" fout" if d.goed < d.rijen else "")
                + '">' + getal(d.goed) + "</span>",
                problemen or '<span class="hint">Niets bijzonders.</span>']

    rijen = [r for r in (deel(rapport.locaties, "Locaties"),
                         deel(rapport.artikelen, "Artikelen"),
                         deel(rapport.voorraad, "Voorraad")) if r]

    geen_maat = next((p for p in rapport.locaties.problemen
                      if p.sleutel == "geenmaat"), None)
    niet_gemeten = next((p for p in rapport.artikelen.problemen
                         if p.sleutel == "nietgemeten"), None)

    standaardvak = ""
    if geen_maat:
        standaardvak = (
            '<div class="uitleg"><b>' + getal(geen_maat.n) + " locaties zonder "
            "afmeting.</b> Dat is normaal: bijna geen enkel systeem legt dit "
            "vast — en precies daarom kan zo'n systeem ook niet uitrekenen wat "
            "waar past. Geef hieronder één standaardmaat op, en meet daarna "
            "per zone één stellingvak op. Eén middag werk, en het klopt voor "
            "duizend locaties tegelijk."
            '<div class="filters">'
            '<label class="inlijn">Diepte <input type="number" '
            'name="std.l_mm" value="' + esc(standaard.l_mm) + '" min="1"> mm</label>'
            '<label class="inlijn">Breedte <input type="number" '
            'name="std.w_mm" value="' + esc(standaard.w_mm) + '" min="1"> mm</label>'
            '<label class="inlijn">Hoogte <input type="number" '
            'name="std.h_mm" value="' + esc(standaard.h_mm) + '" min="1"> mm</label>'
            '<label class="inlijn">Max <input type="number" '
            'name="std.max_g" value="' + esc(standaard.max_g) + '" min="1"> g</label>'
            "</div></div>")

    meetvak = ""
    if niet_gemeten:
        meetvak = ('<div class="uitleg"><b>' + getal(niet_gemeten.n)
                   + " artikelen zonder complete maat.</b> Die komen op de "
                   'lijst <a href="/meten">Opmeten</a>. Ze doen gewoon mee, '
                   "alleen kan Vakto er nog geen plek voor uitrekenen. Meet ze "
                   "bij de eerstvolgende ontvangst: dan heb je ze toch in je "
                   "handen en kost het niets.</div>")

    return ('<div class="kaart"><h2>Wat er in de bestanden staat</h2>'
            + tabel(["Bestand", "Regels", "Bruikbaar", "Wat opvalt"], rijen,
                    "Nog geen bestand gekozen.")
            + standaardvak + meetvak + "</div>")


def eigen(bestanden: dict, kolommen: dict, eenheden, standaard,
          rapport=None, voorbeelden: dict | None = None,
          al_geboekt: bool = False) -> str:
    """R-IMP. Het hele scherm: kiezen, bevestigen, lezen, overnemen."""
    blokken = "".join(_bestandsblok(s, bestanden.get(s), kolommen.get(s, {}))
                      for s in ("locaties", "artikelen", "voorraad"))

    overnemen = ""
    if rapport is not None and bestanden:
        klaar = rapport.klaar and not al_geboekt
        waarschuwing = ""
        if al_geboekt:
            waarschuwing = ('<p class="fout">Er staat al een journaal: dit '
                            "magazijn draait. Een import is een nulmeting "
                            "(R-IMP-07) en overschrijft niets. Wil je "
                            "opnieuw beginnen, gooi dan eerst de database "
                            "leeg — dat is een besluit dat iemand met zijn "
                            "handen moet nemen.</p>")
        elif not rapport.klaar:
            waarschuwing = ('<p class="fout">Er zijn geen bruikbare locaties. '
                            "Zonder locaties kan er niets.</p>")
        overnemen = (
            '<div class="knoprij">'
            '<button name="actie" value="overnemen"'
            + ("" if klaar else " disabled") + ">Neem deze gegevens over"
            "</button>"
            '<button class="stil" name="actie" value="controleer">Opnieuw '
            "controleren</button></div>" + waarschuwing
            + ('<p class="hint">Hierna draait alles op deze gegevens: '
               "dashboard, inslag, picken, scannen.</p>" if klaar else ""))

    return ("<h1>Eigen gegevens</h1>"
            '<p class="lead">Zet Vakto om naar de locaties en artikelen van '
            "een echte klant. Niemand levert een bestand aan met de kolomnamen "
            "die jij wilt, in de eenheid die jij wilt, zonder gaten — dus "
            "raadt Vakto het, en laat het zien wát het geraden heeft.</p>"
            '<form method="post" action="/eigen" enctype="multipart/form-data">'
            + blokken
            + _eenheidsblok(bestanden, kolommen, eenheden, voorbeelden or {})
            + (_rapportblok(rapport, standaard) if rapport is not None else "")
            + overnemen
            + '<noscript><div class="knoprij"><button name="actie" '
            'value="controleer">Bestanden inlezen</button></div></noscript>'
            "</form>")
