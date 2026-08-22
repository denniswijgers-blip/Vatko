"""Import van klantbestanden (R-IMP) — hoofdstuk 11.

Het verschil tussen "kijk eens wat een mooie demo" en "kijk, dit is jouw
magazijn". Niemand levert een bestand aan met de kolomnamen die jij wilt,
in de eenheid die jij wilt, zonder gaten. Dus raden we — en laten we zien
wát we geraden hebben, want raden zonder tonen is precies hoe imports
stilletjes fout gaan.

Er staat hier geen database-code in. Dit bestand leest, raadt, controleert
en levert een rapport; `opslag.py` neemt dat rapport over via
`import.sql`. Zo kun je een klantbestand nakijken zonder dat er iets
weggeschreven wordt — en dat is precies wat je bij een klant aan tafel
wilt doen: eerst laten zien wat eruit komt, dan pas op de knop drukken.

De xlsx-kant is hier veel korter dan in de browserversie. Die moet een
zipbestand met de hand uitpakken omdat er geen bibliotheek beschikbaar is;
Python heeft `zipfile` en `xml.etree` gewoon in de standaardbibliotheek
zitten. Dezelfde regels, minder code.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

# De naamruimte van een xlsx-werkblad. Staat in elk bestand hetzelfde.
NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


# ---------------------------------------------------------------------
#  R-IMP-04  Een getal uit een cel
# ---------------------------------------------------------------------
def getal(waarde) -> float | None:
    """Een klantbestand is geen rekenblad.

    Er staat "12,5 kg", "1.200" of "n.v.t." in een kolom waar een getal
    hoort. Alles wat geen cijfer, komma, punt of minteken is gaat eraf.
    Staan er een komma én een punt in, dan is de laatste van de twee het
    decimaalteken — zo leest "1.200,50" als 1200,5 en "1,200.50" ook.
    """
    if waarde is None:
        return None
    if isinstance(waarde, (int, float)) and not isinstance(waarde, bool):
        return float(waarde)

    s = str(waarde).strip()
    if not s:
        return None
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not s or s == "-":
        return None

    if "," in s and "." in s:
        s = (s.replace(".", "").replace(",", ".")
             if s.rfind(",") > s.rfind(".") else s.replace(",", ""))
    elif "," in s:
        s = s.replace(",", ".")

    try:
        n = float(s)
    except ValueError:
        return None
    return n if n == n and abs(n) != float("inf") else None


# ---------------------------------------------------------------------
#  R-IMP-01  Bestand lezen
# ---------------------------------------------------------------------
@dataclass
class Bestand:
    """Wat er uit een bestand komt: een kopregel en de rijen eronder."""
    naam: str
    kop: list[str]
    rijen: list[list[str]]

    def kolom(self, index: int | None) -> list[str]:
        """Alle waarden van één kolom, voor het raden van de eenheid."""
        if index is None:
            return []
        return [r[index] for r in self.rijen if index < len(r)]


class Leesfout(Exception):
    """Het bestand is niet te lezen. De tekst is bedoeld om te tonen."""


def raad_scheiding(regel: str) -> str:
    """Puntkomma, komma, tab of pijp — welke staat er het vaakst in?

    Een Nederlandse Excel-export gebruikt de puntkomma, een Engelse de
    komma. Fout raden geeft één kolom met alles erin, en dat is precies
    waar mensen op vastlopen. Wat tussen aanhalingstekens staat telt niet
    mee: een omschrijving met een komma erin is geen kolomgrens.
    """
    beste, hoogste = ";", 0
    for kandidaat in (";", ",", "\t", "|"):
        n, in_aanhaling = 0, False
        for teken in regel:
            if teken == '"':
                in_aanhaling = not in_aanhaling
            elif teken == kandidaat and not in_aanhaling:
                n += 1
        if n > hoogste:
            beste, hoogste = kandidaat, n
    return beste


def _csv_rijen(tekst: str) -> list[list[str]]:
    if tekst.startswith("﻿"):
        tekst = tekst[1:]
    eerste = next((r for r in tekst.splitlines() if r.strip()), "")
    sep = raad_scheiding(eerste)

    rijen: list[list[str]] = []
    rij: list[str] = []
    veld: list[str] = []
    in_aanhaling = False
    i, n = 0, len(tekst)
    while i < n:
        c = tekst[i]
        if in_aanhaling:
            if c == '"':
                if i + 1 < n and tekst[i + 1] == '"':
                    veld.append('"')
                    i += 1
                else:
                    in_aanhaling = False
            else:
                veld.append(c)
        elif c == '"':
            in_aanhaling = True
        elif c == sep:
            rij.append("".join(veld))
            veld = []
        elif c == "\n":
            rij.append("".join(veld))
            rijen.append(rij)
            rij, veld = [], []
        elif c == "\r":
            pass
        else:
            veld.append(c)
        i += 1
    if veld or rij:
        rij.append("".join(veld))
        rijen.append(rij)
    return [r for r in rijen if any(str(c).strip() for c in r)]


def _kolom_index(verwijzing: str | None) -> int:
    """A1 -> 0, B1 -> 1, AA3 -> 26. Een xlsx slaat lege cellen niet op,
    dus zonder dit schuift alles op zodra er een gat in een rij zit."""
    n = 0
    for teken in (verwijzing or ""):
        if teken.isalpha():
            n = n * 26 + (ord(teken.upper()) - 64)
        else:
            break
    return max(0, n - 1)


def _xlsx_rijen(inhoud: bytes) -> list[list[str]]:
    try:
        zip_ = zipfile.ZipFile(BytesIO(inhoud))
    except zipfile.BadZipFile as e:
        raise Leesfout(
            "Dit lijkt geen geldig xlsx-bestand. Sla het in Excel op als "
            "'Excel-werkmap (.xlsx)' of als CSV.") from e

    # De gedeelde tekstentabel: Excel zet elke tekst één keer neer en
    # verwijst er daarna naar met een nummer.
    tekst: list[str] = []
    if "xl/sharedStrings.xml" in zip_.namelist():
        for si in ET.fromstring(zip_.read("xl/sharedStrings.xml")):
            tekst.append("".join(t.text or "" for t in si.iter(f"{{{NS['x']}}}t")))

    bladen = sorted((n for n in zip_.namelist()
                     if re.fullmatch(r"xl/worksheets/sheet\d*\.xml", n)),
                    key=lambda n: (len(n), n))
    if not bladen:
        raise Leesfout("Geen werkblad gevonden in dit bestand.")

    rijen: list[list[str]] = []
    for r in ET.fromstring(zip_.read(bladen[0])).iter(f"{{{NS['x']}}}row"):
        rij: dict[int, str] = {}
        for c in r.iter(f"{{{NS['x']}}}c"):
            soort = c.get("t")
            if soort == "s":
                v = c.find(f"{{{NS['x']}}}v")
                nr = int(v.text) if v is not None and v.text else -1
                waarde = tekst[nr] if 0 <= nr < len(tekst) else ""
            elif soort == "inlineStr":
                waarde = "".join(t.text or "" for t in c.iter(f"{{{NS['x']}}}t"))
            else:
                v = c.find(f"{{{NS['x']}}}v")
                waarde = v.text if v is not None and v.text else ""
            rij[_kolom_index(c.get("r"))] = waarde
        breedte = max(rij) + 1 if rij else 0
        rijen.append([rij.get(i, "") for i in range(breedte)])
    return [r for r in rijen if any(str(c).strip() for c in r)]


def lees_bestand(pad, naam: str | None = None) -> Bestand:
    """Leest een CSV of xlsx en geeft kopregel plus rijen terug.

    Het oude .xls kan niet: dat is een heel ander formaat en het is in
    Excel met twee klikken op te lossen. Beter een duidelijke zin dan een
    half werkend bestand.
    """
    pad = Path(pad)
    naam = naam or pad.name
    laag = naam.lower()

    if laag.endswith(".xls"):
        raise Leesfout(
            "Het oude .xls-formaat kan ik niet lezen. Open het in Excel en "
            "sla het op als .xlsx of .csv.")
    if laag.endswith((".xlsx", ".xlsm")):
        rijen = _xlsx_rijen(pad.read_bytes())
    else:
        rijen = _csv_rijen(pad.read_text(encoding="utf-8-sig", errors="replace"))

    if len(rijen) < 2:
        raise Leesfout("Dit bestand heeft geen gegevensregels onder de kopregel.")

    breedte = max(len(r) for r in rijen)
    kop = [str(rijen[0][i]).strip() if i < len(rijen[0]) else ""
           for i in range(breedte)]
    kop = [k or f"kolom {i + 1}" for i, k in enumerate(kop)]
    return Bestand(
        naam=naam, kop=kop,
        rijen=[[str(r[i]).strip() if i < len(r) else "" for i in range(breedte)]
               for r in rijen[1:]])


# ---------------------------------------------------------------------
#  R-IMP-02  Kolommen herkennen
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class Veld:
    k: str
    naam: str
    syn: tuple[str, ...]
    eis: bool = False


VELDEN: dict[str, tuple[Veld, ...]] = {
    "locaties": (
        Veld("code", "Locatiecode", (
            "locatie", "locatiecode", "location", "locationcode", "loccode",
            "bin", "binlocation", "binlocatie", "plaats", "adres",
            "locatienummer", "code", "magazijnlocatie", "stellingplaats"), eis=True),
        Veld("zone", "Zone of gebied", (
            "zone", "gebied", "area", "warehouse", "magazijn", "afdeling",
            "sectie", "zonecode")),
        Veld("soort", "Soort locatie", (
            "soort", "type", "locatietype", "locationtype", "kind",
            "categorie", "soortlocatie")),
        Veld("L", "Diepte / lengte (binnenmaat)", (
            "diepte", "depth", "lengte", "length", "l", "d", "dieptemm",
            "lengtemm")),
        Veld("W", "Breedte", ("breedte", "width", "b", "w", "breedtemm")),
        Veld("H", "Hoogte", ("hoogte", "height", "h", "hoogtemm", "vrijehoogte")),
        Veld("maxG", "Maximaal gewicht", (
            "maxgewicht", "maximaalgewicht", "draagvermogen", "maxweight",
            "capaciteit", "belasting", "gewichtmax", "maxkg", "maxbelasting")),
    ),
    "artikelen": (
        Veld("sku", "Artikelnummer", (
            "artikelnummer", "artikelnr", "artikel", "sku", "itemcode", "item",
            "itemnumber", "productcode", "productnummer", "code", "nummer",
            "art", "artnr"), eis=True),
        Veld("oms", "Omschrijving", (
            "omschrijving", "omschr", "description", "naam",
            "artikelomschrijving", "benaming", "itemdescription", "tekst")),
        Veld("groep", "Artikelgroep", (
            "groep", "artikelgroep", "productgroep", "categorie", "category",
            "group", "itemgroup", "hoofdgroep", "assortiment")),
        Veld("L", "Lengte", ("lengte", "length", "l", "diepte", "depth", "d",
                             "lengtemm")),
        Veld("W", "Breedte", ("breedte", "width", "b", "w", "breedtemm")),
        Veld("H", "Hoogte", ("hoogte", "height", "h", "dikte", "hoogtemm")),
        Veld("G", "Gewicht per stuk", (
            "gewicht", "weight", "g", "massa", "stukgewicht", "gewichtperstuk",
            "nettogewicht", "brutogewicht", "kg", "gram")),
        Veld("barcode", "Barcode", (
            "barcode", "ean", "eancode", "gtin", "streepjescode", "upc",
            "scancode")),
        Veld("min", "Minimum op picklocatie", (
            "min", "minimum", "minvoorraad", "bestelniveau", "aanvuldrempel",
            "minimumvoorraad", "meldpunt", "minqty")),
        Veld("max", "Maximum op picklocatie", (
            "max", "maximum", "maxvoorraad", "maximumvoorraad", "maxqty",
            "bestelniveaumax")),
    ),
    "voorraad": (
        Veld("sku", "Artikelnummer", (
            "artikelnummer", "artikelnr", "artikel", "sku", "itemcode", "item",
            "productcode", "code", "nummer"), eis=True),
        Veld("locatie", "Locatiecode", (
            "locatie", "locatiecode", "location", "bin", "plaats", "adres",
            "loccode"), eis=True),
        Veld("qty", "Aantal", (
            "aantal", "voorraad", "qty", "quantity", "stuks", "hoeveelheid",
            "stock", "onhand", "aanwezig", "saldo"), eis=True),
    ),
}

_ACCENTEN = str.maketrans("èéêëàáâäòóôöìíîï", "eeeeaaaaoooo" + "iiii")


def plat(tekst) -> str:
    """Kleine letters, accenten eraf, alleen a-z en 0-9 over."""
    return re.sub(r"[^a-z0-9]", "",
                  str(tekst or "").lower().translate(_ACCENTEN))


def herken_kolommen(soort: str, kop: list[str]) -> dict[str, int]:
    """R-IMP-02. Welke kolom hoort bij welk veld?

    Elk veld en elke kolom mag maar één keer gebruikt worden. Dat is de
    hele truc: zonder die regel komen "Lengte" en "Lengte verpakking"
    allebei op hetzelfde veld terecht en verliest er één stilletjes.
    """
    punten: list[tuple[int, int, str, int]] = []
    for i, naam in enumerate(kop):
        p = plat(naam)
        if not p:
            continue
        for veld in VELDEN[soort]:
            score = 0
            for syn in veld.syn:
                if p == syn:
                    score = max(score, 100)
                elif p.startswith(syn) and len(syn) >= 3:
                    score = max(score, 70)
                elif syn in p and len(syn) >= 4:
                    score = max(score, 55)
            if score:
                punten.append((-score, i, veld.k, score))

    # Hoogste punten eerst; bij gelijke stand de kolom die het eerst komt,
    # zodat dezelfde kopregel altijd dezelfde uitkomst geeft.
    punten.sort()
    uit: dict[str, int] = {}
    gebruikt: set[int] = set()
    for _, kolom, veld, _score in punten:
        if veld in uit or kolom in gebruikt:
            continue
        uit[veld] = kolom
        gebruikt.add(kolom)
    return uit


def ontbrekende_velden(soort: str, kolommen: dict[str, int]) -> list[str]:
    """De verplichte velden die niet herkend zijn. Leeg = je kunt door."""
    return [v.naam for v in VELDEN[soort] if v.eis and v.k not in kolommen]


# ---------------------------------------------------------------------
#  R-IMP-03  Eenheid raden — per soort anders
# ---------------------------------------------------------------------
NAAR_MM = {"mm": 1, "cm": 10, "m": 1000}
NAAR_G = {"g": 1, "kg": 1000}


def _gesorteerd(waarden) -> list[float]:
    return sorted(g for g in (getal(w) for w in waarden) if g and g > 0)


def raad_maat(waarden, soort: str) -> str:
    """Millimeter, centimeter of meter?

    Dit moet per soort anders. Een stellingvak van 40 is altijd
    centimeters — 40 mm diep bestaat niet — maar een artikel van 40 is
    bijna altijd millimeters. Dezelfde regel voor allebei gaat
    gegarandeerd een keer mis, en dan staan er pallets in een
    bakkenstelling.
    """
    g = _gesorteerd(waarden)
    if not g:
        return "mm"
    mediaan = g[len(g) // 2]
    if soort == "locaties":
        if mediaan < 3:
            return "m"
        if mediaan < 200:
            return "cm"
        return "mm"

    hoog, max_ = g[int(len(g) * 0.9)], g[-1]
    if hoog < 3:
        return "m"
    if max_ > 400:
        return "mm"
    if max_ <= 100:
        return "cm"
    return "mm"


def raad_gewicht(waarden, soort: str) -> str:
    """Gram of kilo? Een schap draagt kilo's, een artikel weegt grammen."""
    g = _gesorteerd(waarden)
    if not g:
        return "kg" if soort == "locaties" else "g"
    mediaan, max_ = g[len(g) // 2], g[-1]
    if soort == "locaties":
        return "g" if max_ > 20_000 else "kg"
    if max_ > 2000:
        return "g"
    return "kg" if mediaan < 300 else "g"


@dataclass
class Eenheden:
    """Wat de klant blijkbaar gebruikt. Altijd te overrulen met de hand."""
    loc_maat: str = "mm"
    art_maat: str = "mm"
    loc_gew: str = "kg"
    art_gew: str = "g"


def raad_eenheden(locaties: Bestand | None, kolom_loc: dict[str, int] | None,
                  artikelen: Bestand | None,
                  kolom_art: dict[str, int] | None) -> Eenheden:
    """De vier eenheden in één keer, uit de kolommen die herkend zijn."""
    e = Eenheden()
    if locaties and kolom_loc:
        maten = sum((locaties.kolom(kolom_loc.get(k)) for k in "LWH"), [])
        e.loc_maat = raad_maat(maten, "locaties")
        e.loc_gew = raad_gewicht(locaties.kolom(kolom_loc.get("maxG")), "locaties")
    if artikelen and kolom_art:
        maten = sum((artikelen.kolom(kolom_art.get(k)) for k in "LWH"), [])
        e.art_maat = raad_maat(maten, "artikelen")
        e.art_gew = raad_gewicht(artikelen.kolom(kolom_art.get("G")), "artikelen")
    return e


# ---------------------------------------------------------------------
#  R-IMP-05  Controleren — het rapport is belangrijker dan de import
# ---------------------------------------------------------------------
@dataclass
class Probleem:
    sleutel: str
    tekst: str
    ernst: str = "let"          # "fout" = de rij gaat niet mee
    n: int = 0
    voorbeeld: list[str] = field(default_factory=list)


@dataclass
class Deel:
    """Wat er van één bestand terechtkwam."""
    rijen: int = 0
    goed: int = 0
    problemen: list[Probleem] = field(default_factory=list)

    def noteer(self, sleutel: str, tekst: str, voorbeeld: str,
               ernst: str = "let") -> None:
        p = next((x for x in self.problemen if x.sleutel == sleutel), None)
        if p is None:
            p = Probleem(sleutel, tekst, ernst)
            self.problemen.append(p)
        p.n += 1
        if len(p.voorbeeld) < 3:
            p.voorbeeld.append(voorbeeld)


@dataclass
class Locatieregel:
    code: str
    zone: str
    soort: str
    l_mm: int
    w_mm: int
    h_mm: int
    max_g: int
    geschat: bool


@dataclass
class Artikelregel:
    sku: str
    oms: str
    groep: str
    l_mm: int | None
    w_mm: int | None
    h_mm: int | None
    g: int | None
    barcode: str | None
    min_qty: int | None
    max_qty: int | None

    @property
    def gemeten(self) -> bool:
        return None not in (self.l_mm, self.w_mm, self.h_mm, self.g)


@dataclass
class Voorraadregel:
    sku: str
    locatie: str
    qty: int


@dataclass
class Standaard:
    """Wat een locatie krijgt als het bestand geen maat noemt.

    Een gok, en dat staat er ook bij: zulke locaties worden gemarkeerd
    als `geschat`, zodat je later kunt zien waar het systeem iets heeft
    ingevuld dat niemand gemeten heeft.
    """
    l_mm: int = 600
    w_mm: int = 400
    h_mm: int = 350
    max_g: int = 50_000


@dataclass
class Rapport:
    locaties: Deel = field(default_factory=Deel)
    artikelen: Deel = field(default_factory=Deel)
    voorraad: Deel = field(default_factory=Deel)
    loc_regels: dict[str, Locatieregel] = field(default_factory=dict)
    art_regels: dict[str, Artikelregel] = field(default_factory=dict)
    vrd_regels: list[Voorraadregel] = field(default_factory=list)

    @property
    def klaar(self) -> bool:
        """Zonder locaties heb je geen magazijn en valt er niets over te
        nemen. Artikelen en voorraad mogen later komen."""
        return self.locaties.goed > 0

    @property
    def problemen(self) -> list[Probleem]:
        return (self.locaties.problemen + self.artikelen.problemen
                + self.voorraad.problemen)


def controleer(locaties: Bestand | None = None,
               kolom_loc: dict[str, int] | None = None,
               artikelen: Bestand | None = None,
               kolom_art: dict[str, int] | None = None,
               voorraad: Bestand | None = None,
               kolom_vrd: dict[str, int] | None = None,
               eenheden: Eenheden | None = None,
               standaard: Standaard | None = None) -> Rapport:
    """R-IMP-05. Leest de drie bestanden na en schrijft op wat er mis is.

    Er wordt hier niets weggeschreven. Dat is het punt: je kunt dit bij
    een klant aan tafel draaien, het rapport laten zien, en pas daarna
    besluiten of je op de knop drukt.
    """
    eenheden = eenheden or Eenheden()
    standaard = standaard or Standaard()
    R = Rapport()

    # ---- locaties ---------------------------------------------------
    if locaties and kolom_loc:
        K = kolom_loc
        f_maat = NAAR_MM[eenheden.loc_maat]
        f_gew = NAAR_G[eenheden.loc_gew]
        R.locaties.rijen = len(locaties.rijen)
        for r in locaties.rijen:
            code = _cel(r, K.get("code"))
            if not code:
                R.locaties.noteer(
                    "geencode", "Rij zonder locatiecode; wordt overgeslagen",
                    "(lege rij)", "fout")
                continue
            if code.upper() in R.loc_regels:
                R.locaties.noteer(
                    "dubbel",
                    "Locatiecode komt meer dan één keer voor; alleen de eerste telt",
                    code, "fout")
                continue

            maten = [(getal(_cel(r, K.get(k))) or 0) * f_maat for k in "LWH"]
            mg = getal(_cel(r, K.get("maxG"))) or 0
            zonder = not all(m > 0 for m in maten)
            if zonder:
                R.locaties.noteer(
                    "geenmaat",
                    "Locatie zonder afmetingen; krijgt de standaardmaat", code)
            if mg <= 0:
                R.locaties.noteer(
                    "geengewicht",
                    "Locatie zonder maximaal gewicht; krijgt het standaardgewicht",
                    code)

            R.loc_regels[code.upper()] = Locatieregel(
                code=code, zone=_cel(r, K.get("zone")),
                soort=_cel(r, K.get("soort")),
                l_mm=standaard.l_mm if zonder else round(maten[0]),
                w_mm=standaard.w_mm if zonder else round(maten[1]),
                h_mm=standaard.h_mm if zonder else round(maten[2]),
                max_g=round(mg * f_gew) if mg > 0 else standaard.max_g,
                geschat=zonder)
            R.locaties.goed += 1

    # ---- artikelen --------------------------------------------------
    if artikelen and kolom_art:
        K = kolom_art
        f_maat = NAAR_MM[eenheden.art_maat]
        f_gew = NAAR_G[eenheden.art_gew]
        R.artikelen.rijen = len(artikelen.rijen)
        for r in artikelen.rijen:
            sku = _cel(r, K.get("sku"))
            if not sku:
                R.artikelen.noteer(
                    "geensku", "Rij zonder artikelnummer; wordt overgeslagen",
                    "(lege rij)", "fout")
                continue
            if sku.upper() in R.art_regels:
                R.artikelen.noteer(
                    "dubbel",
                    "Artikelnummer komt meer dan één keer voor; alleen de eerste telt",
                    sku, "fout")
                continue

            maten = [(getal(_cel(r, K.get(k))) or 0) * f_maat for k in "LWH"]
            gew = (getal(_cel(r, K.get("G"))) or 0) * f_gew
            gemeten = all(m > 0 for m in maten) and gew > 0
            if not gemeten:
                R.artikelen.noteer(
                    "nietgemeten",
                    "Artikel zonder complete maat of gewicht; komt op de lijst "
                    "'nog opmeten'", sku)

            R.art_regels[sku.upper()] = Artikelregel(
                sku=sku, oms=_cel(r, K.get("oms")) or sku,
                groep=_cel(r, K.get("groep")) or "Overig",
                l_mm=round(maten[0]) if gemeten else None,
                w_mm=round(maten[1]) if gemeten else None,
                h_mm=round(maten[2]) if gemeten else None,
                g=round(gew) if gemeten else None,
                barcode=_cel(r, K.get("barcode")) or None,
                min_qty=_geheel(getal(_cel(r, K.get("min")))),
                max_qty=_geheel(getal(_cel(r, K.get("max")))))
            R.artikelen.goed += 1

    # ---- voorraad ---------------------------------------------------
    if voorraad and kolom_vrd:
        K = kolom_vrd
        R.voorraad.rijen = len(voorraad.rijen)
        for r in voorraad.rijen:
            sku = _cel(r, K.get("sku")).upper()
            loc = _cel(r, K.get("locatie")).upper()
            q = getal(_cel(r, K.get("qty")))
            if not sku or not loc:
                R.voorraad.noteer("leeg", "Rij zonder artikel of locatie",
                                  "(lege rij)", "fout")
                continue
            if sku not in R.art_regels:
                R.voorraad.noteer(
                    "onbekendart",
                    "Voorraad op een artikel dat niet in het artikelbestand staat",
                    sku, "fout")
                continue
            if loc not in R.loc_regels:
                R.voorraad.noteer(
                    "onbekendloc",
                    "Voorraad op een locatie die niet in het locatiebestand staat",
                    loc, "fout")
                continue
            if not q or q <= 0:
                R.voorraad.noteer(
                    "nul", "Regel met nul of geen aantal; overgeslagen", sku)
                continue
            R.vrd_regels.append(Voorraadregel(sku, loc, round(q)))
            R.voorraad.goed += 1

    return R


def _cel(rij: list[str], index: int | None) -> str:
    if index is None or index >= len(rij):
        return ""
    return str(rij[index]).strip()


def _geheel(n: float | None) -> int | None:
    return int(n) if n else None


# ---------------------------------------------------------------------
#  R-IMP-06  Looproute uit de locatiecode
# ---------------------------------------------------------------------
@dataclass(frozen=True)
class Plek:
    gang: int
    vak: int
    niveau: int


def ontleed_code(code: str, volgnr: int = 0) -> Plek:
    """Gang, vak en niveau uit een locatiecode halen.

    Werkt op 01-02-3, A.12.4 en 1/14/2. Lukt het niet, dan is de volgorde
    in het bestand de looproute — dat is nog altijd beter dan willekeurig.
    """
    delen = [d for d in re.split(r"[-_./\s]+", str(code)) if d]
    nums = []
    for d in delen:
        m = re.search(r"(\d+)", d)
        nums.append(int(m.group(1)) if m else None)

    if len(delen) >= 3 and nums[-1] is not None and nums[-2] is not None:
        niveau, vak = nums[-1], nums[-2]
        gang = nums[-3]
        if gang is None:
            s = delen[-3]
            gang = (ord(s[0].upper()) - 64) if s else 1
        return Plek(gang, vak, niveau)
    return Plek(1, volgnr + 1, 1)


def soort_naar_type(tekst: str, code: str) -> int:
    """Welke `location_type` hoort bij wat er in het bestand staat?

    Zowel de soort-kolom als de code doen mee: een klant die geen
    soortkolom levert, noemt zijn expeditievak meestal wél EXP-01.
    """
    t = plat(tekst) + " " + plat(code)
    if re.search(r"ontvang|receiv|inbound|inkomend|dock", t):
        return 2
    if re.search(r"keur|qc|quality|inspect|quarantaine", t):
        return 3
    if re.search(r"schade|damage|defect|breuk", t):
        return 4
    if re.search(r"expedit|verzend|ship|outbound|uitgaand", t):
        return 5
    if re.search(r"bulk|pallet|reserve|voorraadlocatie|stelling", t):
        return 1
    return 0
