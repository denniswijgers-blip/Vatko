# Vakto — overdracht

**Plak dit bestand in een nieuw gesprek en je hoeft niets opnieuw uit te leggen.**
Het is met opzet kort: het moet goedkoop zijn om mee te sturen.

---

## Wat Vakto is

Een WMS (warehouse management system) voor Nederlandse B2B-groothandels: kleine tot
middelgrote bedrijven zonder WMS, of met een WMS dat slecht werkt of te duur is.
Gebouwd door Dennis Wijgers, teamleider logistiek met tien jaar ervaring, met de
bedoeling er een bedrijf van te maken. Dennis is beginnend programmeur; dit is zijn
eerste project.

**Wat Vakto anders doet dan de rest** — twee ideeën waar alles op staat:

1. **Benutting in plaats van "past het".** Een locatie krijgt punten voor hoe goed de
   ruimte benut wordt, met een strafterm als het vak veel te ruim is. Veertig
   schroefsets horen niet in een palletplaats, ook al passen ze er.
2. **Artikelafmetingen zijn een tijdlijn, geen veld.** Wordt een doos groter, dan zoekt
   het systeem zélf uit op welke locaties er nu te veel ligt, en schrijft dat op:
   *"Past niet meer op: 01-01-1 (ligt 30, past nog 27)."*

Verder: het systeem maakt zijn eigen werk aan (aanvullen, samenvoegen, tellen,
overloop) en sluit zijn eigen meldingen. De enige menselijke keuzes die overblijven
zijn "meld dit artikel niet meer" en "deze aanvuldrempel is akkoord".

---

## Twee versies, en waarom

| | Waar | Rol |
|---|---|---|
| **Browserversie** | `demo/` | Eén HTML-bestand, opent zonder installatie. Verkoopt en bewijst. Gaat ooit uit de lucht als product en blijft alleen demo. |
| **Serverversie** | `server/` | Het echte product. Python + PostgreSQL. Hier komt alles uiteindelijk terecht. |

De browserversie is dus geen prototype dat weggegooid wordt, maar ook geen product.
Hij is het bewijsstuk waar de serverversie tegenaan getest wordt.

---

## Waar we staan

**Alle negen stappen zijn af.** Uit `spec/rekenkern.html`, hoofdstuk 16:

| | Stap | Status |
|---|---|---|
| 1 | Schema in PostgreSQL, views | ✅ |
| 2 | Rekenkern: passen en inslagvoorstel | ✅ |
| 3 | `boek()` met transactie en rijvergrendeling | ✅ |
| 4 | Metingen en afwijkingen | ✅ |
| 5 | Uitgaand: reserveren, picken, manco | ✅ |
| 6 | Zelfcontrole en optimalisatie | ✅ |
| 7 | Import van klantbestanden | ✅ |
| 8 | Schermen en scanmodus | ✅ |
| 9 | Inloggen, rollen, back-up, server | ✅ |

Alles groen: **370 Python-tests** en **234 SQL-controles**, plus twee tests met
twee sessies tegelijk (de laatste vijf stuks picken, en de laatste tien reserveren),
en een back-up die zichzelf terugzet om te bewijzen dat het kan.

**Wat stap 9 opleverde.** Er zit een inlog omheen. Drie rollen met een rang —
magazijnmedewerker, teamleider, beheerder — precies zoals de browserversie ze al kende.
Dat is nu **hoofdstuk 13 (R-GEB-01 t/m R-GEB-08)**; Instellingen, Testgevallen en
Volgorde zijn 14, 15 en 16 geworden.

Vier keuzes die het uitleggen waard zijn:

* **Rechten worden op de server getoetst, niet in het menu.** Een scherm weglaten is
  opmaak; wie het adres typt komt er anders alsnog. Elke aanvraag toetst zelf, en een
  POST net zo goed als een GET — anders is de knop weg maar het formulier nog te
  versturen. Dat is T-40.
* **Een badge is geen wachtwoord.** Hij ligt op tafel en iedereen kan hem lezen. Een
  badge geeft daarom alleen toegang tot de scanmodus, ook als de rol erachter beheerder
  is.
* **Een sessie is een rij in de database.** Een herstart logt niemand uit, twee mensen
  kunnen tegelijk werken zonder elkaars stand te zien, en een sessie is in te trekken —
  iemand die uit dienst gaat is er ook echt uit.
* **Wachtwoorden staan er als scrypt-afdruk in**, met de parameters erbij, zodat je die
  over vijf jaar kunt verhogen zonder dat bestaande rijen onleesbaar worden. En er zit
  géén standaardwachtwoord in het schema: is de gebruikerstabel leeg, dan vraagt het
  eerste scherm om een beheerder aan te maken en daarna is die weg dicht (R-GEB-08).

T-39 is waar deze stap op afgerekend werd: twee mensen tegelijk ingelogd, allebei in de
scanmodus op dezelfde picklijst. Ieder ziet zijn eigen stand, de een die overslaat
schuift bij de ander niets op, en precies één van de twee krijgt de laatste stuks.

Verder: `db/backup.sh --proef` maakt een back-up én zet hem meteen terug in een
wegwerpdatabase om te bewijzen dat het kan, en `DRAAIEN.md` beschrijft https met nginx,
een systemd-unit, de cron voor de back-up en een firewall.

**Wat stap 8 opleverde.** De serverversie heeft nu schermen. Drie lagen die alleen van
elkaar weten wat ze moeten weten: `vakto/opslag.py` kent SQL, `vakto/schermen.py` kent
geen database, `vakto/web.py` kent HTTP. Daaronder ligt de rekenkern, die van geen van
drieën iets weet. Starten: `python3 -m vakto.web`, dan <http://127.0.0.1:8000/>.

Geen framework en geen JavaScript: `http.server` uit de standaardbibliotheek, en elk
scherm werkt met formulieren. Elke handeling is een POST met een omleiding erna, zodat
F5 na een pick niets nog een keer afboekt; de melding reist mee in de URL, dus er is geen
sessiekoekje nodig. De opmaak komt uit `demo/stijl.css` — hetzelfde bestand als de
browserversie, zodat een verschil in beeld een verschil in gegevens is.

De scanmodus is **hoofdstuk 12 (R-SCAN-01 t/m R-SCAN-07)** geworden; Instellingen,
Testgevallen en Volgorde zijn daardoor 13, 14 en 15. `vakto/scannen.py` raakt geen
database aan: hij zegt alleen wat er geboekt moet worden, en `web.py` boekt dat via
dezelfde functies als de rest. En T-18 staat in `vakto/werkdag.py` — een hele werkdag
van 07:00 tot 17:00 naspelen (`python3 -m vakto.werkdag`), met aan het eind nul negatieve
voorraadregels, nergens `res > qty` en geen hangende reserveringen.

Twee dingen kwamen boven water, allebei rechtgezet (spec v1.7):

* `vakto_tellen()` boekte een telverschil met reden `TELLING`, terwijl R-SCAN-05 en de
  browserversie `TELVERSCHIL` zeggen — en `NULMETING` als er nog niets was vastgelegd.
  Het document had gelijk; de database is bijgetrokken.
* Een locatie die nog nooit geteld is kreeg als reden *"20508 dag(en) over het
  telinterval"*. Rekenkundig waar (`geteld_op` is dan 1970), maar bij een nieuwe klant
  staat dat op elke taak, en wie dat leest gelooft de rest van het scherm ook niet meer.
  Nu heet het *"nog nooit geteld"*, in beide versies.

Ook nieuw: `python3 -m vakto.inlezen <locaties> <artikelen> <voorraad> --overnemen`, om
een database met echte klantbestanden te vullen voordat je de schermen bekijkt.

**Wat stap 7 opleverde.** De import zit in `server/vakto/inlezen.py` (lezen, kolommen
raden, eenheid raden, controleren) en `server/import.sql` (overnemen, in één transactie).
De drie rommelige oefenbestanden uit `verkoop/voorbeeldbestanden/` geven op de server
exact hetzelfde rapport als in de browserversie — dat is waar deze stap op afgerekend
werd, en het lukte in één keer.

De specificatie had geen hoofdstuk over import, terwijl er wel degelijk rekenregels in
zitten. Dat is nu **hoofdstuk 11 (R-IMP-01 t/m R-IMP-07)**; Instellingen, Testgevallen en
Volgorde zijn daardoor 12, 13 en 14 geworden. Eén regel is er nieuw bij: een import is een
nulmeting en weigert zodra er al een journaal staat.

Ook gedaan: **stap 3 van de herindeling**. `import.js` (667 regels) is gesplitst in zeven
bestanden, op de kopbalken die er zelf al in stonden.

**Wat stap 6 opleverde.** Hoofdstuk 9 en 10 zijn bijna helemaal rekenwerk, dus die staan
in Python: `server/vakto/zelfcontrole.py` (meldingen beoordelen, taken laten vervallen) en
`server/vakto/optimalisatie.py` (samenvoegen, aanvullen, telplan, adviezen). De database
schrijft alleen weg en voert taken uit — dat laatste is een voorraadmutatie en gaat dus
door `vakto_boek()` heen. T-16 en T-17 worden van begin tot eind getest tegen een echte
PostgreSQL (`server/tests/test_hertoets_db.py`).

Het schrijven van deze stap bracht drie afwijkingen aan het licht die in beide versies
zijn rechtgezet (spec v1.5): R-ZC-04 en de onderste rij van R-OPT-03 zijn dezelfde regel
en horen dus één stuk code te zijn; bij het samenvoegen van twee aanleidingen hoort de
reden van de zwaarste te blijven staan, niet die van de laatste die langskomt; en
teltaken uit een manco vallen buiten het plafond van het telplan.

**Wat stap 5 opleverde.** Reserveren, picken en manco staan in `server/uitgaand.sql` en
niet in Python: ze vergrendelen rijen en boeken voorraad, dus geldt R-BOEK-03 net zo hard
als bij `boek()`. Python heeft wat er zonder database moet gelden — de looproute, de
statusreeks en het inpakken — in `server/vakto/uitgaand.py`.

**Herindeling:** helemaal af. Alle zeven stappen uit `spec/herindeling.html` zijn
gedaan: versiebeheer, één projectmap, `router.js` en `import.js` opgesplitst, de zeven
`ui`-bestanden herverdeeld over tien schermbestanden, de SQL naar `server/db/`, en een
`LEESMIJ.md` bovenaan die de weg wijst.

Bij stap 4 stond nog één keuze open: je kreeg `2-logica/uitgaand.js` én
`4-schermen/uitgaand.js`. Het scherm heet nu `uitgaand-scherm.js` en de logica houdt
zijn naam. Reden: de serverversie heeft `vakto/uitgaand.py` voor precies die logica, en
die twee naast elkaar willen kunnen leggen is het hele punt van stap 8.

---

## Vaste afspraken

Deze gelden zonder dat ze elke keer opnieuw gezegd hoeven te worden.

1. **Specificatie eerst, dan code, in beide versies.** Wijkt de code af van
   `spec/rekenkern.html`, dan heb je twee systemen. Verander eerst het document.
2. **Testgevallen worden afgelezen, niet bedacht.** De verwachte uitkomsten in de
   Python-tests komen uit de draaiende browserversie. Zo bewijzen ze pariteit in
   plaats van een mening.
3. **Gedrag staat in tabellen, niet in `if`.** `location_type`, `size_class_rule`,
   `weging`, `setting`. Een klant die gemengde bulk wil, zet dat aan — er hoeft geen
   regel code voor om.
4. **Afgeleide waarden worden nooit opgeslagen.** Beschikbare voorraad, maatklasse,
   actuele afmeting, status van een melding: allemaal berekend.
5. **De database bewaakt integriteit, Python rekent.** Boeken, vergrendelen, checks en
   append-only horen in PostgreSQL; passen, benutting en scoren in Python.
6. **Nederlands.** Code, commentaar, functienamen, documentatie. Ook in gesprekken.
7. **Geen AskUserQuestion-tool.** Vragen gewoon in gewone tekst stellen.

---

## Hoe het is ingedeeld

```
Vakto/
├── LEESMIJ.md             de wegwijzer
├── OVERDRACHT.md          dit bestand
├── server/                het product — Python + PostgreSQL
│   ├── DRAAIEN.md         op een echte server zetten: https, systemd, back-up
│   ├── vakto/             de rekenkern, zeventien modules
│   ├── db/                het schema en de databasefuncties
│   ├── tests/  tests-sql/
│   └── opzetten.sh
├── demo/                  de browserversie
│   ├── bron/1-kern/       passen, voorstellen, grafieken
│   │      2-logica/       boeken, meten, uitgaand, optimaliseren, scannen
│   │      3-import/       klantbestanden inlezen — zeven bestanden
│   │      4-schermen/     tien schermen, in de volgorde van het menu
│   │      5-schil/        menu, tekenen, klikken, toetsen, bovenbalk
│   ├── test/              browsertests + testbestanden
│   ├── stijl.css  bouw.py
├── spec/                  rekenkern.html, herindeling.html
└── verkoop/               businessplan, huisstijl, voorbeeldbestanden
```

Het nummer in de mapnamen onder `bron/` is de **bouwvolgorde** die `bouw.py`
aanhoudt, geen versiering: alles wordt aan elkaar geplakt tot één HTML-bestand, dus
wat onderaan staat mag rekenen op wat erboven staat. `5-schil/toetsen.js` moet
altijd als laatste blijven — daar staan de twee regels die de demo starten.

---

## Hoe je alles test

```bash
# serverversie, alles in één keer (Mac/Linux):
cd server && bash opzetten.sh

# of los:
python3 -m unittest discover -s tests -t .
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_boeken.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_meten.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_uitgaand.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_zelfcontrole.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_import.sql
psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_gebruikers.sql
bash tests-sql/test_gelijktijdig.sh
bash tests-sql/test_gelijktijdig_reserveren.sh

# de schermen bekijken (heeft psycopg nodig):
cd server && pip install -r requirements.txt && python3 -m vakto.web

# een back-up maken én toetsen of hij terug te zetten is:
cd server && bash db/backup.sh --proef

# browserversie:
cd demo && python3 bouw.py
cd test && node test3.mjs && node test-import.mjs && node test-paden.mjs && node rooktest.mjs

# de verwachte waarden van de Python-tests uit de demo aflezen:
node uitgaand-vectoren.mjs
node zelfcontrole-vectoren.mjs
```

De browsertests hebben `playwright` nodig: `npm install playwright` in `demo/test/`.

**Versiebeheer.** Er zit git op het project, met drie momenten vastgelegd. `git log
--oneline` laat ze zien; `git status` laat zien wat je sindsdien veranderd hebt. Leg
na elke afgeronde stap opnieuw vast, dan kun je altijd terug.

---

## Wat er nog moet

**Juridisch: afgehandeld.** Een ICT/IE-jurist heeft het arbeidscontract bekeken
(nevenwerkzaamheden, geheimhouding, art. 7 Auteurswet) en ziet geen belemmering. De
afspraak over de REV'IT-schermafbeeldingen uit het begin van het project blijft staan:
niet bewaren, niet delen, en verder bouwen vanuit openbare bronnen.

**Bewust niet gebouwd**, met de reden erbij (staat ook onderaan `server/DRAAIEN.md`):
geen tweefactorauthenticatie, geen wachtwoordherstel per e-mail, en één
databaseverbinding tegelijk. Geen van drieën is nodig voor één magazijn binnen een
bedrijfsnetwerk; alle drie worden ze het zodra dat verandert.

**De volgende stap is geen code.** De negen stappen zijn af. Wat er nu moet gebeuren is
een eerste klant: de browserversie verkoopt, de serverversie levert. Zodra die draait,
gaat de browserversie uit de lucht als product en blijft hij alleen demo — twee
codebases onderhouden naast een baan gaat niet.

---

## Links

- Specificatie (v1.8): https://claude.ai/code/artifact/dd8951b3-eb2d-4da3-9e88-2830f6a505fb
- Werkende demo: https://claude.ai/code/artifact/2e9f6aeb-2b7c-4122-8cb3-363d010babc3
- Businessplan: https://claude.ai/code/artifact/502071aa-3f51-4f08-b0f9-ff2004bf2557
- Herindelingsvoorstel: https://claude.ai/code/artifact/767b2b1c-f103-4a4b-9ee3-31d220c7e133

---

## Een nieuw gesprek beginnen

Stuur dit bestand mee plus de map waar je aan werkt — meestal alleen `server/`. Niet
allebei de versies tegelijk: dat is de helft duurder en sinds stap 8 nog maar zelden
nodig.

Openingszin die werkt:

> Dit is mijn WMS-project Vakto. In OVERDRACHT.md staat waar we zijn en welke
> afspraken gelden. Ik wil [wat je wilt].

De negen stappen zijn af, dus er is geen "volgende stap" meer die vastligt. Wat er nu
speelt is onderhoud, een eerste klant, en wat die klant vraagt.
