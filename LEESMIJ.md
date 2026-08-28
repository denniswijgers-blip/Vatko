# Vakto

Een WMS voor Nederlandse B2B-groothandels: kleine tot middelgrote bedrijven zonder
warehouse management systeem, of met een systeem dat slecht werkt of te duur is.

Dit bestand is de wegwijzer. Het is geschreven voor één specifieke lezer: jezelf, in
januari, als je er drie weken niet naar gekeken hebt.

---

## Waar begin je?

| Je wilt… | Ga naar |
|---|---|
| weten waar het project staat en wat de afspraken zijn | [`OVERDRACHT.md`](OVERDRACHT.md) |
| aan de serverversie werken | [`server/LEESMIJ.md`](server/LEESMIJ.md) |
| hem op een echte server zetten | [`server/DRAAIEN.md`](server/DRAAIEN.md) |
| weten hoe een rekenregel hoort te werken | `spec/rekenkern.html` |
| de demo laten zien aan een klant | `demo/vakto-demo.html` openen in een browser |
| de serverschermen bekijken | `cd server && python3 -m vakto.web` |
| een klantbestand oefenen | `verkoop/voorbeeldbestanden/` |

Begin je aan een nieuw gesprek met een AI-assistent, stuur dan `OVERDRACHT.md` mee. Daar
staat in wat er af is en welke afspraken gelden, zodat je dat niet elke keer opnieuw hoeft
uit te leggen.

---

## Wat waar staat

```
Vakto/
├── LEESMIJ.md      dit bestand — de wegwijzer
├── OVERDRACHT.md   waar we staan, en de afspraken die zonder herhaling gelden
│
├── spec/           de specificatie: hoe het hoort te werken
│   ├── rekenkern.html      elke rekenregel, vijftien hoofdstukken
│   └── herindeling.html    het opruimvoorstel voor de browserversie
│
├── server/         het product — Python + PostgreSQL
│   ├── vakto/      de rekenkern (passen, meten, uitgaand, optimaliseren,
│   │               inlezen, scannen, gebruikers, etiketten) plus de
│   │               schermen en de webserver
│   ├── db/         het schema, alles wat de database zelf doet, en backup.sh
│   ├── tests/      Python-tests, de meeste draaien zonder database
│   ├── tests-sql/  tests die een echte PostgreSQL nodig hebben
│   ├── DRAAIEN.md  op een echte server zetten: https, systemd, back-up
│   └── opzetten.sh database opzetten en alles testen, in één opdracht
│
├── demo/           de browserversie — één HTML-bestand, opent zonder installatie
│   ├── bron/       de losse bestanden waar bouw.py het uit samenstelt
│   ├── test/       browsertests en oefenbestanden
│   └── bouw.py     bron/ → vakto-demo.html
│
└── verkoop/        businessplan, huisstijl, voorbeeldbestanden voor klanten
```

---

## Twee versies, en waarom

De **browserversie** in `demo/` is één HTML-bestand dat opent zonder installatie. Hij
verkoopt en hij bewijst: een prospect kan hem openen zonder dat er iets geregeld hoeft te
worden. Hij is geen prototype dat weggegooid wordt, maar ook geen product.

De **serverversie** in `server/` is het echte product. Python en PostgreSQL. Daar komt
alles uiteindelijk terecht.

Zolang ze naast elkaar bestaan geldt één regel boven alle andere: **ze moeten hetzelfde
zeggen.** De verwachte uitkomsten in de Python-tests zijn daarom afgelezen uit de
draaiende browserversie en niet bedacht. Wijkt er iets af, dan verander je eerst
`spec/rekenkern.html` en daarna pas allebei de versies — anders heb je twee systemen die
langzaam uit elkaar lopen.

---

## Alles testen

```bash
# serverversie, alles in één keer (Mac/Linux):
cd server && bash opzetten.sh

# en daarna de schermen bekijken op http://127.0.0.1:8000/
# (de eerste keer vraagt hij om een beheerder aan te maken)
cd server && pip install -r requirements.txt && python3 -m vakto.web

# browserversie:
cd demo && python3 bouw.py
cd test && node test3.mjs && node test-import.mjs && node test-paden.mjs && node rooktest.mjs
```

De browsertests hebben `playwright` nodig: `npm install playwright` in `demo/test/`.

---

## Wat dit systeem anders doet

Twee ideeën waar alles op staat, en waar je bij elke keuze op terug kunt vallen:

1. **Benutting in plaats van "past het".** Een locatie krijgt punten voor hoe goed de
   ruimte benut wordt, met een strafterm als het vak veel te ruim is. Veertig schroefsets
   horen niet in een palletplaats, ook al passen ze er.
2. **Artikelafmetingen zijn een tijdlijn, geen veld.** Wordt een doos groter, dan zoekt
   het systeem zélf uit op welke locaties er nu te veel ligt, en schrijft dat op:
   *"Past niet meer op: 01-01-1 (ligt 30, past nog 27)."*

Verder maakt het systeem zijn eigen werk aan en sluit het zijn eigen meldingen. De enige
menselijke keuzes die overblijven zijn "meld dit artikel niet meer" en "deze aanvuldrempel
is akkoord".

---

## Waar het staat

De serverversie is af: alle negen stappen uit hoofdstuk 16 van de specificatie. Schema,
rekenkern, boeken, meten, uitgaand, zelfcontrole, import, schermen, scanmodus, inloggen
en back-up — met 434 Python-tests en 244 SQL-controles eronder.
