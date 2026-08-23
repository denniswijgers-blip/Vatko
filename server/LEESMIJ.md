# Vakto — serverversie, stap 1 tot en met 7

Dit is het begin van de echte versie. Er zitten nog geen schermen in.
Wat er wel in zit: het **databaseschema**, de **rekenkern**, het
**boeken** met een echte transactie en rijvergrendeling, de **metingen**
als tijdlijn, en de hele **uitgaande stroom** — reserveren, picken,
manco, inpakken, verzenden — en de **zelfcontrole** die zijn eigen werk
aanmaakt en zijn eigen meldingen sluit, en de **import** die de
rommelige bestanden van een klant inleest. Met de testgevallen uit de
specificatie erbij.

De rest van de stappen staat in hoofdstuk 14 van *De rekenkern,
uitgeschreven*.

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
| `SELECT * FROM setting;` | alle instellingen uit hoofdstuk 12 |
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
Ran 30 tests in 0.003s

OK
```

Dertig groene tests betekent: de rekenkern in Python geeft **exact
dezelfde antwoorden** als de browserversie die je aan klanten laat zien.
Dat is de hele bedoeling van deze stap.

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
  opslag.py         De vertaallaag: database -> objecten -> rekenkern.

tests/              T-01 t/m T-31 plus de vertaallaag. Draaien zonder database.
tests-sql/          T-13 t/m T-17, T-32 t/m T-38, de checks, de triggers, de
                    views, en twee sessies die tegelijk de laatste stuks pakken
                    — één keer bij het picken, één keer bij het reserveren.
```

**Op `opslag.py` na staat er in `vakto/` geen regel database-code, en dat
is met opzet.** De rekenregels moeten testbaar zijn zonder dat er een
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

**Je hebt hier geen VPS voor nodig.** Een server komt pas bij stap 9, als
er een echte klant op zit. Voor stap 3 tot en met 8 draait alles op je
eigen machine, en dat kost niets.

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
```

Op Windows draai je die zeven regels in de SQL Shell (staat in je
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
python -m unittest tests.test_opslag -v
```

Je hoort in totaal honderdachtennegentig keer `OK` te zien. Daarnaast zijn er twee
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

## De volgende stap

Stap 8 uit hoofdstuk 14: schermen en scanmodus. Reken op zes avonden, en
op het eerste moment dat je beide versies naast elkaar nodig hebt. Neem
stap 4 van de herindeling erbij: de zeven `ui`-bestanden hernoemen naar
wat er in zit.

Begin nergens aan voordat de tests van deze stap groen zijn. Als de kern
niet klopt, bouw je er alleen maar bovenop.
