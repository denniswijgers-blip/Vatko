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

Stap **6 van 9** is af. Uit `spec/rekenkern.html`, hoofdstuk 13:

| | Stap | Status |
|---|---|---|
| 1 | Schema in PostgreSQL, views | ✅ |
| 2 | Rekenkern: passen en inslagvoorstel | ✅ |
| 3 | `boek()` met transactie en rijvergrendeling | ✅ |
| 4 | Metingen en afwijkingen | ✅ |
| 5 | Uitgaand: reserveren, picken, manco | ✅ |
| 6 | Zelfcontrole en optimalisatie | ✅ |
| 7 | Import van klantbestanden | ← nu |
| 8 | Schermen en scanmodus | |
| 9 | Inloggen, rollen, back-up, server | |

Alles groen: **175 Python-tests** en **167 SQL-controles**, plus twee tests met
twee sessies tegelijk (de laatste vijf stuks picken, en de laatste tien reserveren).

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

**Herindeling:** stap 0 t/m 2 uit `spec/herindeling.html` zijn gedaan (versiebeheer,
één projectmap, `router.js` opgesplitst). Stap 3 (`import.js`) en stap 4 (de schermen
hernoemen) staan bewust nog open: die betalen zich pas terug vlak vóór stap 8, als je
de serverschermen bouwt met de browserversie ernaast.

Bij stap 4 moet er nog één keuze gemaakt worden: je krijgt dan
`2-logica/uitgaand.js` én `4-schermen/uitgaand.js`. Verschillende mappen, dus het
werkt — maar verwarrend in een foutmelding. Noem het scherm `uitgaand-scherm.js`, of
de logica `orders.js`.

Stap 3 van de herindeling gaat over `import.js`, en dat is precies waar stap 7 van de
serverversie over gaat. Het is dus het moment om ze samen te doen: eerst `import.js`
opsplitsen, dan de serverkant ernaast bouwen.

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
├── OVERDRACHT.md          dit bestand
├── server/                het product — Python + PostgreSQL
│   ├── vakto/             de rekenkern, twaalf modules
│   ├── tests/  tests-sql/
│   └── *.sql  opzetten.sh
├── demo/                  de browserversie
│   ├── bron/1-kern/       passen, voorstellen, grafieken
│   │      2-logica/       boeken, meten, uitgaand, optimaliseren, scannen
│   │      3-import/       klantbestanden inlezen
│   │      4-schermen/     ui.js t/m ui7.js — nog te hernoemen (stap 4)
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
bash tests-sql/test_gelijktijdig.sh
bash tests-sql/test_gelijktijdig_reserveren.sh

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

**Juridisch.** Aan het begin van dit project zijn schermafbeeldingen van het WMS van
Dennis' werkgever (REV'IT) als referentie gebruikt. Die bevatten bedrijfsgegevens:
klantnamen, 41 medewerkersnamen, interne IP-adressen, de magazijnindeling. Afspraak:
niet bewaren, niet delen, en verder bouwen vanuit openbare bronnen. Nog te doen:
een ICT/IE-jurist naar het arbeidscontract laten kijken (nevenwerkzaamheden,
geheimhouding, art. 7 Auteurswet) voordat er iets verkocht wordt.

---

## Links

- Specificatie (v1.5): https://claude.ai/code/artifact/dd8951b3-eb2d-4da3-9e88-2830f6a505fb
- Werkende demo: https://claude.ai/code/artifact/2e9f6aeb-2b7c-4122-8cb3-363d010babc3
- Businessplan: https://claude.ai/code/artifact/502071aa-3f51-4f08-b0f9-ff2004bf2557
- Herindelingsvoorstel: https://claude.ai/code/artifact/767b2b1c-f103-4a4b-9ee3-31d220c7e133

---

## Een nieuw gesprek beginnen

Stuur dit bestand mee plus de map waar je aan werkt (`server/` voor stap 7, `demo/`
als het over de browserversie gaat). Niet allebei tegelijk: dat is de helft duurder
en meestal niet nodig.

Openingszin die werkt:

> Dit is mijn WMS-project Vakto. In OVERDRACHT.md staat waar we zijn en welke
> afspraken gelden. Ik wil verder met stap 7 (import van klantbestanden).
