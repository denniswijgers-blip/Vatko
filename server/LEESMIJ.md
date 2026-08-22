# Vakto — serverversie, stap 1 tot en met 3

Dit is het begin van de echte versie. Er zitten nog geen schermen in.
Wat er wel in zit: het **databaseschema**, de **rekenkern**, en het
**boeken** met een echte transactie en rijvergrendeling — met de
testgevallen uit de specificatie erbij.

De rest van de stappen staat in hoofdstuk 13 van *De rekenkern,
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
  ✓ schema.sql geladen
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
| `SELECT * FROM setting;` | alle instellingen uit hoofdstuk 11 |
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
schema.sql          Het PostgreSQL-schema. Tabellen, checks, views, triggers.
seed_config.sql     De configuratietabellen: locatiesoorten, maatklassen,
                    wegingen, instellingen. Geen demodata — dit zijn de
                    regels waarmee gerekend wordt.
boeken.sql          vakto_boek(): de enige route waarlangs voorraad verandert.
meten.sql           vakto_meting(): meting en melding in één transactie.
                    Plus de meetlijst v_te_meten (R-MEET-04).

vakto/
  getallen.py       Afronden zoals JavaScript het doet. Lees de uitleg.
  instellingen.py   Alles wat per klant verschilt (R-BASIS-04).
  maten.py          Maatklassen en volume (R-AFG-02).
  modellen.py       De gegevens waar de rekenkern mee werkt.
  passen.py         Hoeveel gaat er in deze locatie? (R-PAS)
  voorstel.py       Waar moet dit heen? (R-INS)
  meten.py          Afwijkende maten en wat ze betekenen (R-MEET).
  opslag.py         De vertaallaag: database -> objecten -> rekenkern.

tests/              T-01 t/m T-31 plus de vertaallaag. Draaien zonder database.
tests-sql/          T-13, T-32, T-33, de checks, de triggers, de views, en twee
                    pickers die tegelijk de laatste vijf stuks pakken.
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

Boeken zit dus in de database (`vakto_boek` in boeken.sql) en niet in
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
psql -d vakto -f schema.sql
psql -d vakto -f seed_config.sql
psql -d vakto -f boeken.sql
psql -d vakto -f meten.sql
```

Op Windows draai je die vier regels in de SQL Shell (staat in je
startmenu onder PostgreSQL), of in PowerShell als je PostgreSQL aan je
PATH hebt laten toevoegen. `opzetten.sh` werkt alleen op Mac en Linux.

### En dan de databasetests

**Mac of Linux:** dubbelklik `Test database (Mac + Linux).command`.
**Windows:** typ in PowerShell, vanuit deze map:

```powershell
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_boeken.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_meten.sql
python -m unittest tests.test_opslag -v
```

Je hoort in totaal zevenenveertig keer `OK` te zien, en bij de laatste
test dat er precies één van twee pickers de laatste vijf stuks krijgt.

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

## De volgende stap

Stap 5 uit hoofdstuk 13: uitgaand. Dat is de grootste brok: reserveren,
picken, manco. Reken op vijf avonden.

Reserveren is ook de plek waar zelfbouwsystemen het vaakst omvallen, dus
lees hoofdstuk 8 van de specificatie voordat je begint — vooral R-UIT-05,
waar vier dingen tegelijk moeten gebeuren.

Begin nergens aan voordat de tests van deze stap groen zijn. Als de kern
niet klopt, bouw je er alleen maar bovenop.
