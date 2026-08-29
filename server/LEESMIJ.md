# Vakto — serverversie, alle negen stappen

Dit is de echte versie, en hij is af. Wat erin zit: het
**databaseschema**, de **rekenkern**, het **boeken** met een echte
transactie en rijvergrendeling, de **metingen** als tijdlijn, de hele
**uitgaande stroom** — reserveren, picken, manco, inpakken, verzenden —
de **zelfcontrole** die zijn eigen werk aanmaakt en zijn eigen meldingen
sluit, de **import** die de rommelige bestanden van een klant inleest,
de **schermen** met de **scanmodus**, en sinds stap 9 **inloggen,
rollen en back-up**. Met de testgevallen uit de specificatie erbij.

Op een echte server zetten: zie [DRAAIEN.md](DRAAIEN.md).

---

## De schermen bekijken

```bash
pip install -r requirements.txt      # eenmalig: de databasedriver
python3 -m vakto.web
```

Open daarna <http://127.0.0.1:8000/>. De eerste keer vraagt hij om een
beheerder aan te maken; daarna is die weg dicht. Verder is het dezelfde
stijl als de browserversie, met echte gegevens uit PostgreSQL.

Staat de database nog leeg, dan lees je een klantbestand in via
**Eigen gegevens** in het menu: je kiest de drie bestanden, kijkt na wat
Vakto van de kolommen en de eenheid gemaakt heeft, en drukt pas daarna
op *Neem deze gegevens over*. Dat is het scherm dat je bij een klant aan
tafel gebruikt.

Vanaf de opdrachtregel kan het ook:

```bash
python3 -m vakto.inlezen \
  "../verkoop/voorbeeldbestanden/Rommelig - locaties (in cm).csv" \
  "../verkoop/voorbeeldbestanden/Rommelig - artikelen (Engels, xlsx).xlsx" \
  "../verkoop/voorbeeldbestanden/Rommelig - voorraad.csv"
```

Zonder `--overnemen` laat hij alleen het rapport zien en verandert er
niets. Dat is met opzet: bij een klant aan tafel wil je eerst laten zien
wat eruit komt.

En om er wat leven in te krijgen:

```bash
python3 -m vakto.werkdag       # een dag van 07:00 tot 17:00 naspelen
```

---

## Begin hier

Eén bestand doet alles: PostgreSQL opzoeken, de database aanmaken, het
schema erin zetten en alle tests draaien.

**Op een Mac:**

1. Dubbelklik de zip in je map Downloads. Er komt een map
   `vakto-server` naast te staan.
2. Open **Terminal**. (Druk `⌘` + spatie, typ `terminal`, druk enter.)
3. Typ `cd` en dan een **spatie** — dus: `cd `
4. **Sleep de map `vakto-server` uit Finder het Terminal-venster in.**
   Er verschijnt vanzelf het pad. Druk op enter.
5. Typ dit en druk op enter:

```bash
bash opzetten.sh
```

Dat is alles. Je krijgt zoiets te zien:

```
  ✓ gevonden: /Applications/Postgres.app/.../psql
  ✓ ingelogd als gebruiker 'dennis'
  ✓ database aangemaakt
  ✓ db/schema.sql geladen
  ✓ 21 tabellen en 5 views staan klaar
  ✓ Ran 67 tests in 0.13s  —  alle tests groen
  ✓ 47 controles geslaagd (boeken, meten, checks, triggers, views)
  ✓ precies één picker kreeg de laatste vijf stuks

  Alles staat en alles is groen.
```

Dat vierde punt — slepen in plaats van typen — is de truc die het hele
gedoe met paden overslaat. Je hoeft nooit te weten waar iets staat.

Gaat er iets mis, dan zegt het script wat er aan de hand is en wat je
eraan doet. Het meest voorkomende: Postgres.app staat op *Not running*.
Klik dan op het olifantje in je menubalk en druk op **Start**.

Je kunt `opzetten.sh` altijd opnieuw draaien. Hij zet het schema dan
opnieuw op, dus gegevens die je zelf hebt ingevoerd gaan weg.

---

## Rondkijken in de database

Als alles groen is, kun je erin kijken:

```bash
psql -d vakto
```

En dan:

| Typ dit | Wat je ziet |
|---|---|
| `\dt` | alle tabellen |
| `\d stock` | hoe de voorraadtabel eruitziet |
| `SELECT * FROM setting;` | alle instellingen uit hoofdstuk 14 |
| `SELECT * FROM v_location_size;` | de maatklasse per locatie, berekend |
| `\q` | stoppen |

Werkt `psql` niet los? Dan staat hij niet in je PATH. Volg dan op
<https://postgresapp.com> het kopje *Configure your $PATH*, of gebruik
het volledige pad dat `opzetten.sh` onderaan noemt.

---

## Alleen de rekenkern testen, zonder database

Handig als je snel wilt weten of de berekeningen nog kloppen. Je hebt
hier alleen Python voor nodig — geen database, geen `pip install`.

**Windows** — dubbelklik `Test Vakto (Windows).bat`
**Mac** — dubbelklik `Test Vakto (Mac).command`

Of typ het zelf, vanuit deze map:

```bash
python3 -m unittest discover -s tests -t .     # Windows: python
```

Je hoort dit te zien:

```
..............................
Ran 434 tests in 28s

OK
```

Groen betekent: de rekenkern in Python geeft **exact dezelfde
antwoorden** als de browserversie die je aan klanten laat zien. Dat is
de hele bedoeling.

Zonder database draaien er een stuk minder — de tests die een PostgreSQL
nodig hebben slaan zichzelf dan over en zeggen dat ook.

Wil je zien wat er getest wordt, zet er `-v` achter.

---

## Wat waar staat

```
db/                 alles wat de database zelf doet
  schema.sql        Het PostgreSQL-schema. Tabellen, checks, views, triggers.
  seed_config.sql   De configuratietabellen: locatiesoorten, maatklassen,
                    wegingen, instellingen. Geen demodata — dit zijn de
                    regels waarmee gerekend wordt.
  boeken.sql        vakto_boek(): de enige route waarlangs voorraad verandert.
  meten.sql         vakto_meting(): meting en melding in één transactie.
                    Plus de meetlijst v_te_meten (R-MEET-04).
  uitgaand.sql      Reserveren, vrijgeven, picken, manco, inpakken, verzenden
                    (R-UIT). Plus de picklijst v_picklijst, op looproute.
  zelfcontrole.sql  Taken klaarzetten, laten vervallen en uitvoeren, en
                    tellen (R-ZC, R-OPT). Plus v_werklijst en v_ordervraag.
  import.sql        Een gecontroleerd rapport overnemen (R-IMP), in één
                    transactie. Plus vakto_zone en vakto_artikelgroep.
  gebruikers.sql    Gebruikers, sessies en het slot op mislukte pogingen
                    (R-GEB). Plus de view v_gebruikers, zonder wachtwoorden.
  beheer.sql        vakto_instelling(): alleen bestaande sleutels, en elke
                    wijziging met de oude waarde in het log (R-INST-01).
  backup.sh         Een back-up maken, en met --proef meteen terugzetten
                    om te bewijzen dat het kan.

vakto/
  getallen.py       Afronden zoals JavaScript het doet. Lees de uitleg.
  instellingen.py   Alles wat per klant verschilt (R-BASIS-04).
  maten.py          Maatklassen en volume (R-AFG-02).
  modellen.py       De gegevens waar de rekenkern mee werkt.
  passen.py         Hoeveel gaat er in deze locatie? (R-PAS)
  voorstel.py       Waar moet dit heen? (R-INS)
  meten.py          Afwijkende maten en wat ze betekenen (R-MEET).
  uitgaand.py       Looproute, statusreeks en inpakken (R-UIT-03, 06, 07).
  inlezen.py        Klantbestanden lezen, raden en controleren (R-IMP).
  zelfcontrole.py   Meldingen beoordelen, taken laten vervallen (R-ZC).
  optimalisatie.py  Samenvoegen, aanvullen, telplan, adviezen (R-OPT).
  scannen.py        De scanner als stappenmachine (R-SCAN). Raakt niets aan:
                    hij zegt alleen wat er geboekt moet worden.
  gebruikers.py     Rollen, rechten en wachtwoorden (R-GEB). Geen database:
                    wie er ingelogd is weet gebruikers.sql.
  instellingen.py   Alles wat per klant verschilt, met de toets erbij die
                    een onmogelijke waarde tegenhoudt (R-BASIS-04, R-INST-01).
  etiketten.py      Code 39 voor de locatielabels (R-SCAN-08). Streep voor
                    streep gelijk aan de browserversie.
  werkdag.py        Een hele werkdag naspelen, van 07:00 tot 17:00 (T-18).
  schermen.py       HTML tekenen. Kent geen database en geen webserver.
  web.py            De webserver: haalt op, boekt, en plakt het aan elkaar.
  opslag.py         De vertaallaag: database -> objecten -> rekenkern.

tests/              T-01 t/m T-31 plus de vertaallaag, de scanmodus, een hele
                    werkdag en een wandeling langs alle schermen.
tests-sql/          T-13 t/m T-17, T-32 t/m T-38, de checks, de triggers, de
                    views, en twee sessies die tegelijk de laatste stuks pakken
                    — één keer bij het picken, één keer bij het reserveren.
```

**Op `opslag.py` na staat er in `vakto/` geen regel SQL, en dat is met
opzet.** (`web.py` opent wel een verbinding, maar schrijft geen query:
alles loopt via `opslag.py`.) De rekenregels moeten testbaar zijn zonder dat er een
PostgreSQL draait. Verandert het schema, dan verandert alleen `opslag.py`
mee.

De grens die we aanhouden:

| | |
|---|---|
| **De database** | bewaakt integriteit: boeken, vergrendelen, checks, append-only |
| **Python** | doet de berekeningen: passen, benutting, scoren, optimaliseren |

Boeken zit dus in de database (`vakto_boek` in db/boeken.sql) en niet in
Python. Dat is geen luiheid maar R-BASIS-01: zet je die logica in de
applicatie, dan geldt hij alleen zolang iedereen die route gebruikt. Eén
importscriptje dat "even snel" een UPDATE doet, en je journaal klopt niet
meer. In de database geldt hij voor iedereen — ook voor jou met psql om
elf uur 's avonds.

---

## PostgreSQL op je eigen laptop

**Je hebt hier geen VPS voor nodig zolang je de enige gebruiker bent.**
Alles draait op je eigen machine, en dat kost niets. Komt er een klant
op, dan staat in [DRAAIEN.md](DRAAIEN.md) wat erbij hoort: https,
systemd, een back-up in een cron en een firewall.

**Windows.** Ga naar <https://www.postgresql.org/download/windows/> en
download de installer van EDB. Klik door de installatie heen en
**onthoud het wachtwoord dat je opgeeft** — dat vraagt hij later terug.
Alle vinkjes standaard laten staan. Na afloop heb je "SQL Shell (psql)"
in je startmenu.

**Mac.** Het makkelijkst is <https://postgresapp.com> — dat is één app
die je naar Programma's sleept en start. Klik daarna in de app op
*Initialize*. Om `psql` ook in de Terminal te kunnen typen, volg je op
die site het kopje "Configure your $PATH".

**Controleren of het werkt:** open een terminal of de SQL Shell en typ
`psql --version`. Krijg je een versienummer, dan sta je goed.

### Het schema neerzetten

Vanuit deze map:

```bash
createdb vakto
psql -d vakto -f db/schema.sql
psql -d vakto -f db/seed_config.sql
psql -d vakto -f db/boeken.sql
psql -d vakto -f db/meten.sql
psql -d vakto -f db/uitgaand.sql
psql -d vakto -f db/zelfcontrole.sql
psql -d vakto -f db/import.sql
psql -d vakto -f db/gebruikers.sql
psql -d vakto -f db/beheer.sql
```

Op Windows draai je die negen regels in de SQL Shell (staat in je
startmenu onder PostgreSQL), of in PowerShell als je PostgreSQL aan je
PATH hebt laten toevoegen. `opzetten.sh` werkt alleen op Mac en Linux.

### En dan de databasetests

**Mac of Linux:** dubbelklik `Test database (Mac + Linux).command`.
**Windows:** typ in PowerShell, vanuit deze map:

```powershell
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_boeken.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_meten.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_uitgaand.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_zelfcontrole.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_import.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_gebruikers.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_beheer.sql
python -m unittest tests.test_opslag -v
```

Je hoort in totaal tweehonderdvierenveertig keer `OK` te zien. Daarnaast zijn er twee
tests met twee sessies tegelijk (`tests-sql/test_gelijktijdig.sh` en
`tests-sql/test_gelijktijdig_reserveren.sh`); die draaien alleen op Mac
en Linux, en `opzetten.sh` doet ze allebei vanzelf. Precies één van de
twee sessies hoort te slagen — dat is de hele reden dat er PostgreSQL
onder zit en geen SQLite.

Wat er in het schema is afgedwongen, zodat de database het onthoudt in
plaats van de programmeur:

| Regel | Hoe |
|---|---|
| R-BASIS-01 | `journal` en `measurement` zijn append-only, met een trigger |
| R-BASIS-02 | Afgeleide waarden zijn views, geen kolommen |
| R-BASIS-04 | Gedrag staat in `location_type`, `size_class_rule`, `weging`, `setting` |
| R-UIT-01 | `CHECK (res <= qty)` — dubbel verkopen wordt hier tegengehouden |
| R-ZC-04 | Unieke index: nooit twee open aanvultaken voor hetzelfde vak |

---

## Wat er in de database is afgedwongen

Wat de database onthoudt, hoeft de programmeur niet te onthouden:

| Regel | Hoe |
|---|---|
| R-BASIS-01 | `journal` en `measurement` zijn append-only, met een trigger die UPDATE en DELETE weigert |
| R-BOEK-01 | `vakto_boek()` doet voorraad en journaal in één transactie, of geen van beide |
| R-BOEK-02 | Rijvergrendeling in vaste volgorde (laagste `location_id` eerst), zodat A→B en B→A niet vastlopen |
| R-UIT-01 | `CHECK (res <= qty)` — je kunt geen gereserveerde voorraad wegboeken zonder de reservering vrij te geven |
| R-ZC-04 | Unieke index: nooit twee open aanvultaken voor hetzelfde artikel en vak |
| R-AFG-01..04 | Afgeleide waarden zijn views, geen kolommen |
| R-GEB-04 | `CHECK (wachtwoord LIKE 'scrypt$%')` — een leesbaar wachtwoord komt er niet in |
| R-GEB-01 | `CHECK (rol IN (...))` en: geen gebruiker zonder wachtwoord én zonder badge |
| R-INST-01 | `vakto_instelling()` weigert een sleutel die niet bestaat, en logt de oude waarde |

---

## Wat deze stap al heeft opgeleverd

Het uitschrijven en natesten heeft meteen **twee echte fouten** in de
browserversie gevonden. Allebei van dezelfde soort: het systeem kon werk
klaarzetten voor een locatie die al vol was.

1. **Inslagvoorstel telde de eigen voorraad niet af van de stapeling.**
   Een vak waar er dertig in gaan en waar er dertig lagen, kreeg nog een
   voorstel voor zestien stuks. Oorzaak: het volumebudget is ruimer dan
   de echte stapeling, want dozen laten lucht over. Testgeval T-19.

2. **Aanvultaken keken helemaal niet of het paste.** Die rekenden alleen
   met de minimum- en maximumvoorraad. Een taak van 115 stuks naar een
   vak waar er zestig in gaan is geen taak, dat is een probleem dat je op
   de vloer aflevert.

Allebei gerepareerd in de browserversie én hier, met een test die
voorkomt dat het terugkomt.

Dat is precies waar dit voor bedoeld was. Fouten die je niet ziet in een
demo, zie je wel als je de regels moet opschrijven.

---

## Stap 4: metingen en afwijkingen

Deze zit er nu in, en heeft opnieuw drie dingen aan het licht gebracht
die in de browserversie niet vastlagen. Geen fouten deze keer — losse
eindjes, en die zijn in beide versies gelijkgetrokken:

1. **Afronden op één decimaal.** De browserversie deed `toFixed(1)`,
   Python doet standaard bankiersafronding. Bij 12,25% geeft de een 12,3
   en de ander 12,2. Nu doen ze allebei `rond(x × 10) / 10`. En de
   drempel wordt op het *onafgeronde* getal getoetst, want anders slaat
   14,96% alarm nadat het 15,0 is geworden.

2. **Ontvangst, keuring en verzendgereed tellen niet mee.** Dat zijn
   doorloopplekken met een nominale maat. Een pallet die daar een dag
   staat "past" er niet minder om, en er is niets aan te doen. De
   zelfcontrole deed dat al goed, het vastleggen van een meting nog niet
   — waardoor een melding zichzelf meteen weer kon sluiten.

3. **Nog hoogstens één open melding per artikel.** Wijkt hetzelfde
   artikel twee keer achter elkaar af, dan wordt de bestaande melding
   bijgewerkt in plaats van dat er een tweede naast komt. Een melding is
   een uitspraak over de huidige toestand, geen regel op een takenlijst.

Wat je er nu mee kunt: leg een afwijkende meting vast en het systeem
zoekt zelf uit op welke locaties er meer ligt dan er nog past, en zet dat
in één zin in de melding. `"Past niet meer op: 01-01-1 (ligt 30, past nog
27)"` — dat is T-27, en dat is het testgeval dat het product verkoopt.

---

## Stap 5: uitgaand

Van order tot verzending. De grootste brok tot nu toe, en de plek waar
zelfbouwsystemen het vaakst omvallen.

De keuze die alles bepaalt in deze stap: **reserveren, picken en manco
staan in de database en niet in Python.** Dat is dezelfde afweging als
bij `boek()` (R-BOEK-03). Reserveren verhoogt `stock.res`, en dat mag
nooit boven `qty` uitkomen — ook niet als twee verkopers op hetzelfde
moment op de knop drukken. Een lus in Python die eerst leest en daarna
schrijft kan dat niet garanderen; tussen lezen en schrijven zit een gat
waar een tweede sessie doorheen loopt. Met `SELECT … FOR UPDATE` zit dat
gat er niet, en geldt de regel ook voor wie hem met `psql` aanroept.

Wat er dan nog wél in Python hoort staat in `vakto/uitgaand.py`: de
looproute (R-UIT-03, nodig bij het aanmaken van locaties, ver vóór er een
order bestaat), de statusreeks (R-UIT-06, zodat een schermknop weet of
een overgang mag) en het inpakken (R-UIT-07, een som).

Drie dingen zijn onderweg aan de specificatie toegevoegd — eerst het
document, dan de code:

1. **De pickregel is de `allocation`-rij zelf**, met een status ernaast
   (TODO, DONE, MANCO). Een aparte tabel met pickregels zou dezelfde
   gegevens nog een keer opschrijven, en dan lopen ze uit elkaar zodra
   iemand er één van bijwerkt.
2. **Inpakken en verzenden** zaten wel in de browserversie maar stonden
   nergens beschreven. Nu R-UIT-07, met het collogewicht als instelling
   in plaats van een 25000 midden in een regel code.
3. **`event_log`**, waar het systeem opschrijft wat het zelf besloten
   heeft. R-UIT-02 wil één waarschuwing bij een tekort — niet bij elke
   poging opnieuw. Dat de order al op `WACHT_OP_VOORRAAD` stond is het
   bewijs dat het al gemeld is; daar is geen apart vlaggetje voor nodig.

R-UIT-05 is het hart van deze stap: bij een manco gebeuren er vier
dingen tegelijk, en niets minder. Reservering vrijgeven, systeemaantal
corrigeren (nooit meer dan er volgens het systeem ligt), teltaak
aanmaken, orderregel markeren. Sla je er één over, dan houdt het systeem
voorraad vast die er niet is en merkt niemand het tot de volgende
inventarisatie.

---

## Stap 6: zelfcontrole en optimalisatie

Het spiegelbeeld van stap 5. Daar ging bijna alles naar de database
omdat er vergrendeld en geboekt moest worden; hier gaat bijna alles naar
Python, want hoofdstuk 9 en 10 zijn van begin tot eind rekenwerk: uit de
huidige toestand afleiden welk werk er zou moeten liggen, welke
meldingen niet meer kloppen en welke taken overbodig zijn geworden.

`vakto/zelfcontrole.py` en `vakto/optimalisatie.py` raken geen database
aan. Ze krijgen de toestand mee en geven terug wát er zou moeten
gebeuren; `opslag.py` schrijft dat weg via `zelfcontrole.sql`. Dat maakt
elk geval in drie regels na te testen — en het maakt zichtbaar wat er
zou gebeuren vóórdat het gebeurt, wat handig wordt zodra er schermen op
komen.

Eén ding hoort wél in de database: een taak uitvoeren. Dat is een
voorraadmutatie, dus gaat het door `vakto_boek()` heen en nergens anders
langs.

Wat deze stap aan het licht bracht — drie keer hetzelfde soort fout, en
alle drie in beide versies rechtgezet:

1. **R-ZC-04 en de onderste rij van R-OPT-03 zijn dezelfde regel.** Ze
   staan in twee hoofdstukken omdat ze bij twee onderwerpen horen, maar
   het is één stuk code. Bouw je het twee keer, dan geeft de
   zelfcontrole een taak van 25 stuks waar de optimalisatie er 40 wil.
2. **Bij het samenvoegen van twee aanleidingen blijft de reden van de
   zwaarste staan**, niet die van de laatste die langskomt. Een taak die
   "ordervraag" heet en als reden "onder drempel" geeft, laat de picker
   het verkeerde denken over waarom hij loopt.
3. **Teltaken uit een manco vallen buiten het plafond van het telplan.**
   Die zijn urgent en horen de twaalf geplande tellingen niet te
   verdringen.

T-16 en T-17 staan in `tests/test_hertoets_db.py` en draaien tegen een
echte database: taak aanmaken, met de hand bijvullen, taak zien
vervallen; en melding, overlooptaak, uitvoeren, melding zien sluiten.
Draait er geen PostgreSQL, dan worden ze overgeslagen.

---

## Stap 7: import van klantbestanden

Het verschil tussen "kijk eens wat een mooie demo" en "kijk, dit is jouw
magazijn". Niemand levert een bestand aan met de kolomnamen die jij wilt,
in de eenheid die jij wilt, zonder gaten. Dus raadt het systeem — en laat
het zien wát het geraden heeft, want raden zonder tonen is precies hoe
imports stilletjes fout gaan.

De verdeling is dezelfde als bij stap 6. `vakto/inlezen.py` leest, raadt
en controleert zonder ook maar iets weg te schrijven; `import.sql` neemt
een gecontroleerd rapport over in één transactie. Dat is met opzet zo:
je wilt bij een klant aan tafel het rapport kunnen laten zien vóórdat je
op de knop drukt.

Drie dingen waar het in de praktijk op stukloopt, en wat eraan gedaan is:

1. **Eenheden.** Een stellingvak van 40 is altijd centimeters — 40 mm
   diep bestaat niet — maar een artikel van 40 is bijna altijd
   millimeters. Daarom raadt R-IMP-03 per soort bestand anders. Eén regel
   voor allebei gaat gegarandeerd een keer mis, en dan staan er pallets
   in een bakkenstelling.
2. **Kolommen.** Elk veld en elke kolom mag maar één keer gebruikt
   worden. Zonder die regel komen "Lengte" en "Lengte verpakking" allebei
   op hetzelfde veld terecht en verliest er één stilletjes.
3. **Een aangeleverde maat is geen weging.** Hij wordt een meting met
   bron `SUPPLIER` (R-AFG-01), zodat er vanaf dag één staat dat het een
   opgave is — en zodat elk artikel meteen op de meetlijst komt. Bij de
   oefenbestanden zijn dat er negenhonderd. Dat is geen probleem maar het
   gesprek: de eerste week is meten.

Nieuw is ook dat een import een **nulmeting** is. Staat er al een
journaal, dan weigert hij. Anders overschrijf je een draaiend magazijn
met een bestand van vorige week, en dat merk je pas als de picker voor
een leeg vak staat.

T-34 t/m T-38 draaien op de echte oefenbestanden uit
`verkoop/voorbeeldbestanden/`. Daar zit met opzet van alles fout in, en
het rapport dat eruit komt is tot op de laatste teller gelijk aan dat van
de browserversie.

---

## Stap 8: schermen en scanmodus

Drie stukken, en alle drie met dezelfde scheiding als de rest van het
project:

| Bestand | Weet van | Weet niet van |
|---|---|---|
| `opslag.py` | SQL | HTML, HTTP |
| `schermen.py` | HTML | database, webserver |
| `web.py` | HTTP | SQL |

Daaronder ligt de rekenkern, die van geen van drieën iets weet. Dat
betekent dat je een scherm kunt natesten zonder dat er iets draait:
`tests/test_schermen.py` loopt door de router heen en niet door een
socket. Achttien tests halen een hele order van NIEUW tot VERZONDEN, via
dezelfde knoppen die een gebruiker indrukt.

Drie keuzes die het uitleggen waard zijn:

1. **Geen framework en geen JavaScript.** `http.server` uit de
   standaardbibliotheek doet wat hier nodig is. Elk scherm werkt met
   formulieren die een browser al sinds 1995 kan versturen — handig op
   de vloer, waar soms een tablet staat waar je niets nieuws op
   geïnstalleerd krijgt.
2. **Elke handeling is een POST met een omleiding erna.** Wie na een
   pick op F5 drukt, herhaalt de omleiding en niet de boeking. De
   melding reist mee in de URL, dus er is geen koekje nodig en je kunt
   het scherm dat je ziet gewoon doorsturen.
3. **Dezelfde `stijl.css` als de demo.** Eén stijlbestand voor beide
   versies. Zo is een verschil in beeld een verschil in gegevens.

De scanmodus (hoofdstuk 12) staat helemaal in `scannen.py` en raakt geen
database aan: hij zegt alleen wat er geboekt moet worden, en `web.py`
boekt dat via dezelfde functies als de rest van het systeem. Daardoor
zijn de vier taken — picken, tellen, inslaan, vrij — in
`tests/test_scannen.py` na te lopen zonder dat er iets draait.

En T-18 staat in `vakto/werkdag.py`: een hele werkdag van 07:00 tot
17:00, met orders die binnenkomen, manco's, ontvangsten, inslag en een
zelfcontrole na elke golf. Aan het eind moeten er nul negatieve
voorraadregels zijn, mag nergens `res > qty` staan en mag er geen enkele
hangende reservering over zijn.

```bash
python3 -m vakto.werkdag        # de dag naspelen en het verslag zien
```

Wat deze stap aan het licht bracht: `vakto_tellen()` boekte een
telverschil met reden `TELLING`, terwijl R-SCAN-05 en de browserversie
`TELVERSCHIL` zeggen — en `NULMETING` als er nog niets was vastgelegd.
Dat verschil is niet cosmetisch: het is het verschil tussen "hier gaat
iets mis" en "hier begint een nieuwe klant". Het document had gelijk, de
database is bijgetrokken.

---

## Stap 9: inloggen, rollen en back-up

Tot hier kon iedereen alles. Dat kan zolang er één persoon naar het
scherm kijkt; zodra er een tweede bij komt gaat het op twee manieren
mis. Iemand ziet een scherm waar hij niets te zoeken heeft, en — erger —
bij een telverschil van veertig stuks weet niemand meer wie het geboekt
heeft.

**Drie rollen met een rang**, precies zoals de browserversie ze al kent:

| Rol | Rang | Doet |
|---|---|---|
| Magazijnmedewerker | 1 | picken, tellen, inslaan, opmeten |
| Teamleider | 2 | daarnaast orders, dashboard |
| Beheerder | 3 | daarnaast instellingen, import, gebruikers |

Een rang en geen lijst met vinkjes. Vijf rollen met elk vijftien vinkjes
zijn vijfenzeventig keuzes die niemand bijhoudt; drie rangen zijn er
drie.

Vier keuzes die het uitleggen waard zijn:

1. **Rechten worden op de server getoetst, niet in het menu.** Een
   scherm weglaten is opmaak; wie het adres typt komt er anders alsnog.
   Elke aanvraag toetst zelf, en een POST net zo goed als een GET —
   anders is de knop weg maar het formulier nog te versturen. Dat is
   T-40.
2. **Een badge is geen wachtwoord.** Hij ligt op tafel en iedereen kan
   hem lezen. Daarom geeft een badge alleen toegang tot de scanmodus,
   ook als de rol erachter beheerder is. Wie bij de orders wil, logt in.
3. **Een sessie is een rij in de database, geen variabele in het
   geheugen.** Dat kost een query per aanvraag en levert drie dingen op
   die je anders niet hebt: een herstart logt niemand uit, twee mensen
   kunnen tegelijk werken zonder elkaars stand te zien, en een sessie is
   in te trekken — iemand die uit dienst gaat is er ook echt uit.
4. **Wachtwoorden staan er als scrypt-afdruk in**, met de parameters
   erbij. Worden die over vijf jaar te licht, dan kun je ze verhogen
   zonder dat de bestaande rijen onleesbaar worden: die dragen hun eigen
   instelling bij zich. Een gestolen back-up levert dan geen
   wachtwoorden op — en een back-up staat per definitie ergens anders
   dan de database.

T-39 is waar deze stap op afgerekend werd: twee mensen tegelijk
ingelogd, allebei in de scanmodus op dezelfde picklijst. Ieder ziet zijn
eigen stand, de een die overslaat schuift bij de ander niets op, en
precies één van de twee krijgt de laatste stuks. Dat staat in
`tests/test_toegang.py` en loopt door dezelfde router als een browser.

### De back-up

```bash
bash db/backup.sh              # een dump wegschrijven
bash db/backup.sh --proef      # én meteen toetsen of hij terug kan
```

Die tweede is het punt. **Een back-up die nooit is teruggezet is geen
back-up**, en dit is het enige moment waarop je erachter kunt komen dat
het níét werkt. `--proef` zet de verse dump terug in een
wegwerpdatabase en telt na of de rijen en de `vakto_`-functies er nog
zijn. Eén keer per maand in een cron, en je weet het in plaats van dat
je het hoopt.

---

## De twee beheerschermen

Deze zaten wel in de browserversie en nog niet op de server. Ze horen bij
het gesprek dat je met een klant voert, en daarom kwamen ze als eerste na
stap 9.

### Eigen gegevens (R-IMP)

Het verschil tussen "kijk eens wat een mooie demo" en "kijk, dit is jouw
magazijn". Je kiest de drie bestanden en het scherm laat zien wát het
geraden heeft:

* **welke kolom op welk veld ligt**, met de eerste drie waarden ernaast —
  en elk daarvan is met een keuzelijst te corrigeren. R-IMP-02 belooft
  dat de uitkomst altijd te corrigeren is; zonder die lijst is dat een
  loze belofte.
* **in welke eenheid de klant werkt**, met één concreet voorbeeld eronder:
  *"01-01-1 wordt 300 × 400 × 220 mm"*. Zet de eenheid verkeerd en er
  staat *"30 × 40 × 22 mm — dat lijkt niet te kloppen voor een
  stellingvak"*. Een keuzelijst laat iedereen twijfelen; dat zinnetje
  niet.
* **het rapport**: hoeveel rijen, hoeveel bruikbaar, en wat er opvalt met
  een teller en drie voorbeelden per probleem.

Pas op *Neem deze gegevens over* raakt de database iets. Dat is het punt
van R-IMP-05: je wilt het rapport kunnen laten zien vóórdat je op de knop
drukt.

Draait het magazijn al, dan weigert hij (R-IMP-07) en zegt hij waarom.
Anders overschrijf je een draaiend magazijn met een bestand van vorige
week, en dat merk je pas als de picker voor een leeg vak staat.

### Instellingen (hoofdstuk 14, R-INST-01)

Het antwoord op "ja maar bij ons gaat dat anders", en de reden dat dat
antwoord geen programmeerwerk is. Zet `putaway.fill_factor` op 0,60 en
doe dezelfde inslag opnieuw: alle voorstellen veranderen, zonder dat er
één regel code is aangepast.

Drie dingen die het uitleggen waard zijn:

1. **De waarde wordt getoetst vóórdat hij erin gaat.** Een vulfactor van
   3 zegt dat er meer in een vak gaat dan erin past. Zulke waarden vallen
   niet meteen om — ze geven maandenlang stilletjes onzin, en dat is
   erger.
2. **Een kommagetal is géén `type="number"`.** Dat veld weigert de komma
   die een Nederlander typt, zonder uit te leggen waarom; in een browser
   met een Engelse taalinstelling verdwijnt de toetsaanslag gewoon. De
   toets op de server begrijpt `0,60` wél.
3. **Alleen wat echt wijzigt komt in het log**, met de oude waarde erbij.
   `0.20` en `0.2` zijn hetzelfde getal; wie dat als wijziging
   wegschrijft, krijgt bij elke keer opslaan regels voor velden die
   niemand heeft aangeraakt — en dan is het log niets meer waard.

Allebei de schermen zijn rang 3 (R-GEB-01), en dat wordt bij elke
aanvraag op de server getoetst — een GET net zo goed als een POST.

---

## En de laatste twee: optimalisatie en etiketten

Daarmee kan de serverversie alles wat de browserversie kan.

### Optimalisatie (R-OPT)

Wat het systeem zelf gevonden heeft, op één scherm: locaties die vrij te
spelen zijn, waarom er wordt aangevuld, welke artikelen hard gaan, en het
telplan. Vier tegels bovenaan, en niemand vult hier iets in.

Behalve op twee plekken, en dat is precies het punt:

* **Aanvuldrempels die niet meer kloppen (R-OPT-05).** Vakto vergelijkt de
  drempel met het werkelijke verbruik uit het journaal. Dat is een
  *advies*, geen taak: hoeveel je op de vloer wilt hebben is een besluit
  over werkkapitaal en ruimte. Twee knoppen — *Overnemen* zet de nieuwe
  drempel, *Laten* haalt het artikel van de lijst. Een nieuwe drempel
  overnemen zet dat "laten" weer uit, want vanaf dan mag het systeem er
  opnieuw iets van vinden.
* **Hardlopers zonder picklocatie (R-OPT-06).** Een artikel dat elke dag
  twaalf keer gepakt wordt en alleen in de palletstelling ligt, laat je
  picker elke keer een eind lopen. Vakto rekent uit welk vak past;
  wélk vak je ervoor vrijmaakt blijft een keuze. Op *Vak inrichten* komt
  er een taak, en verder niets — er moet iemand met een pallettruck
  naartoe.

### Etiketten (R-SCAN-08)

Zonder labels op de stelling werkt de scanmodus niet. Code 39, want die
leest elke handscanner zonder dat je er iets voor hoeft in te stellen —
bij een klant met onbekende apparatuur is dat meer waard dan de dichtheid
van een modernere code.

Twee dingen die niet mogen verschuiven, en die daarom in de specificatie
staan:

1. **De verhouding smal : breed is 1 : 3.** Wordt de code ergens uitgerekt
   of samengedrukt, dan piept de scanner en denkt de klant dat het
   systeem niet werkt. Daarom een SVG met vaste verhoudingen, geen reeks
   blokjes.
2. **Tien eenheden wit aan weerskanten.** Zonder rustzone vindt een
   scanner het begin niet, en dan lijkt het etiket leeg.

De codering staat in `vakto/etiketten.py` en is **streep voor streep
vergeleken** met `code39()` uit de browserversie: dezelfde breedte,
dezelfde posities, voor vijf verschillende codes. Dat is geen
overdreven zorgvuldigheid — een etiket dat er goed uitziet en niet scant,
merk je pas als er duizend geplakt zijn.

Naast de code staat de maatklasse en de binnenmaat op het label. Wie
plakt ziet dan meteen of hij bij het goede vak staat, en een verkeerd
geplakt etiket is de duurste fout van de hele invoering.

```
Print de pagina met Ctrl + P (Cmd + P op een Mac). Menu, uitleg en
bladerknoppen vallen dan vanzelf weg.
```

---

## Hierna

De negen stappen uit hoofdstuk 16 zijn af. Wat er nog niet in zit staat
onderaan [DRAAIEN.md](DRAAIEN.md), met de reden erbij — tweefactor­
authenticatie, wachtwoordherstel per e-mail en een verbindingspoel. Geen
van drieën is nodig voor één magazijn binnen een bedrijfsnetwerk; alle
drie worden ze het zodra dat verandert.

**De serverversie kan nu alles wat de browserversie kan.** Wat er nog
alleen in de demo zit, zit daar met opzet: de rondleiding en de
dagsimulatie zijn verkoopgereedschap, geen product.

Wat wél de volgende stap is: **een echte klant**. De browserversie
verkoopt, de serverversie levert. Zodra de eerste klant draait, gaat de
browserversie uit de lucht als product en blijft hij alleen demo — twee
codebases onderhouden naast een baan gaat niet.
