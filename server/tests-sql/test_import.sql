-- =====================================================================
--  VAKTO — import (R-IMP), de schrijfkant.
--
--  Het lezen, raden en controleren staat in Python en wordt daar getest
--  (tests/test_inlezen.py, met de echte oefenbestanden erbij). Wat hier
--  bewezen wordt is wat er met een gecontroleerd rapport gebeurt: zones
--  en groepen die uit de gegevens ontstaan, een maat die een meting
--  wordt en geen veld, en beginvoorraad die net als elke andere mutatie
--  door vakto_boek() gaat.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_import.sql
--  Alles wat het doet wordt aan het eind teruggedraaid.
-- =====================================================================
\set ON_ERROR_STOP on
\pset pager off
BEGIN;

CREATE OR REPLACE FUNCTION zeg(txt text) RETURNS void AS
  $$ BEGIN RAISE NOTICE '  %', txt; END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION eis(voorwaarde boolean, wat text) RETURNS void AS $$
BEGIN
  IF voorwaarde THEN RAISE NOTICE '  OK    %', wat;
  ELSE RAISE EXCEPTION 'GEZAKT: %', wat; END IF;
END $$ LANGUAGE plpgsql;

SELECT zeg('');
SELECT zeg('R-IMP-07  een import is een nulmeting');

-- ---------------------------------------------------------------------
--  Weigeren zolang er een journaal staat
-- ---------------------------------------------------------------------
INSERT INTO zone (id, code, naam) VALUES (930,'TST','Testzone import');
INSERT INTO location (id, code, zone_id, type_id, l_mm, w_mm, h_mm, max_g)
  VALUES (930,'I-01-1',930,0,300,400,220,12000);
INSERT INTO product_group (id, naam) VALUES (930,'Testgroep I');
INSERT INTO product (id, sku, oms, group_id) VALUES (930,'IMP-0','Bestaand',930);
SELECT vakto_boek(930, 1, 'RECEIPT', NULL, 930);

DO $$
BEGIN
  PERFORM vakto_import('[]'::jsonb, '[]'::jsonb, '[]'::jsonb);
  RAISE EXCEPTION 'GEZAKT: er werd geïmporteerd op een draaiend magazijn';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    een import op een magazijn met journaal wordt geweigerd';
END $$;

-- Vanaf hier doen we alsof de database vers is. TRUNCATE mag hier omdat
-- alles aan het eind wordt teruggedraaid; met de hand journaalregels
-- verwijderen kan niet, en dat hoort ook zo (R-BASIS-01).
TRUNCATE journal, stock, measurement, allocation, order_line, customer_order,
         task, alert, event_log, product, product_group, location, zone CASCADE;

SELECT zeg('');
SELECT zeg('zones en artikelgroepen ontstaan uit de gegevens');

-- ---------------------------------------------------------------------
--  vakto_zone en vakto_artikelgroep
-- ---------------------------------------------------------------------
CREATE TEMP TABLE z AS SELECT
  vakto_zone('Stelling A')  AS a,
  vakto_zone('STELLING A')  AS b,
  vakto_zone('Stellage B')  AS c,
  vakto_zone(NULL)          AS d;

SELECT eis((SELECT a FROM z) = (SELECT b FROM z),
           'EXPEDITIE en Expeditie zijn dezelfde zone');
SELECT eis((SELECT c FROM z) <> (SELECT a FROM z),
           'een andere naam is een andere zone');
SELECT eis((SELECT naam FROM zone WHERE id = (SELECT d FROM z)) = 'Magazijn',
           'een lege zonenaam wordt "Magazijn"');
SELECT eis((SELECT count(DISTINCT code) FROM zone) = (SELECT count(*) FROM zone),
           'twee zones die op dezelfde drie letters beginnen botsen niet');
SELECT eis((SELECT code FROM zone WHERE id=(SELECT a FROM z)) = 'STE'
       AND (SELECT code FROM zone WHERE id=(SELECT c FROM z)) = 'ST2',
           'de tweede krijgt een nummer achter zijn afkorting');

SELECT eis(vakto_artikelgroep('Bevestiging') = vakto_artikelgroep('Bevestiging'),
           'dezelfde groep levert hetzelfde nummer');

-- In twee stappen: een query ziet de rij niet die een functie er tijdens
-- diezelfde query in zet. Dat is geen bug maar de momentopname van
-- PostgreSQL, en het kost je een half uur als je het niet weet.
CREATE TEMP TABLE g AS SELECT vakto_artikelgroep('') AS leeg;
SELECT eis((SELECT naam FROM product_group WHERE id = (SELECT leeg FROM g))
             = 'Overig',
           'een lege groepsnaam wordt "Overig"');

TRUNCATE product_group, zone CASCADE;

-- ---------------------------------------------------------------------
--  Een echte import
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('overnemen');

CREATE TEMP TABLE r AS SELECT vakto_import(
  -- locaties: een picklocatie, een bulkvak en een keuringsvak
  '[{"code":"01-01-1","zone":"Stelling A","type_id":0,"gang":1,"vak":1,
     "niveau":1,"seq":1000110,"l_mm":300,"w_mm":400,"h_mm":220,"max_g":12000},
    {"code":"02-01-1","zone":"Stelling A","type_id":1,"gang":2,"vak":1,
     "niveau":1,"seq":2999810,"l_mm":1200,"w_mm":800,"h_mm":1500,"max_g":900000},
    {"code":"QC-01","zone":"EXPEDITIE","type_id":3,"gang":9,"vak":1,
     "niveau":1,"seq":9000110,"l_mm":1200,"w_mm":800,"h_mm":1000,"max_g":600000}]'::jsonb,
  -- artikelen: een met maat, een zonder
  '[{"sku":"IMP-1","oms":"Testartikel","groep":"Bevestiging","l_mm":120,
     "w_mm":90,"h_mm":45,"g":180,"barcode":"8710000000017","min_qty":20,
     "max_qty":40},
    {"sku":"IMP-2","oms":"","groep":"","l_mm":null,"w_mm":null,"h_mm":null,
     "g":null,"barcode":null,"min_qty":5,"max_qty":null}]'::jsonb,
  -- voorraad
  '[{"sku":"IMP-1","locatie":"01-01-1","qty":30},
    {"sku":"IMP-1","locatie":"02-01-1","qty":500},
    {"sku":"IMP-2","locatie":"02-01-1","qty":12}]'::jsonb,
  'dennis') AS uit;

SELECT eis((SELECT uit->>'artikelen' FROM r) = '2', 'twee artikelen');
SELECT eis((SELECT uit->>'voorraad'  FROM r) = '3', 'drie voorraadregels');
SELECT eis((SELECT uit->>'metingen'  FROM r) = '1',
           'één meting: alleen het artikel met een complete maat');
SELECT eis((SELECT uit->>'zones' FROM r) = '2', 'twee zones');

-- R-IMP-07: de doorloopplekken die ontbraken zijn aangemaakt.
SELECT eis((SELECT uit->>'aangemaakt' FROM r) = '3',
           'ontvangst, schade en expeditie ontbraken en zijn aangemaakt');
SELECT eis((SELECT uit->>'locaties' FROM r) = '6',
           'drie uit het bestand plus drie doorloopplekken');
SELECT eis((SELECT count(*) FROM location WHERE type_id = 2) = 1
       AND (SELECT count(*) FROM location WHERE type_id = 5) = 1,
           'er is precies één ontvangst- en één expeditielocatie');
SELECT eis((SELECT count(*) FROM location WHERE type_id = 3) = 1,
           'het keuringsvak uit het bestand is niet verdubbeld');

-- ---------------------------------------------------------------------
--  R-AFG-01  de maat is een meting, geen veld
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-AFG-01  een aangeleverde maat is een meting');

SELECT eis((SELECT bron FROM measurement m JOIN product p ON p.id=m.product_id
             WHERE p.sku='IMP-1') = 'SUPPLIER',
           'bron SUPPLIER: dit is een opgave, geen weging');
SELECT eis((SELECT l_mm FROM v_product_current c JOIN product p ON p.id=c.product_id
             WHERE p.sku='IMP-1') = 120,
           'de actuele maat komt gewoon uit de view');
SELECT eis((SELECT reden FROM v_te_meten WHERE sku='IMP-1') = 'OPGAVE_LEVERANCIER',
           'R-MEET-04: een opgave van de leverancier komt op de meetlijst');
SELECT eis((SELECT reden FROM v_te_meten WHERE sku='IMP-2') = 'NOOIT_GEMETEN',
           'een artikel zonder maat staat er bovenaan');

SELECT eis((SELECT max_qty FROM product WHERE sku='IMP-2') = 20,
           'zonder maximum wordt het vier keer het minimum');
SELECT eis((SELECT barcode FROM product WHERE sku='IMP-2') = 'IMP-2',
           'zonder barcode wordt het artikelnummer de barcode');
SELECT eis((SELECT oms FROM product WHERE sku='IMP-2') = 'IMP-2',
           'zonder omschrijving ook');

-- ---------------------------------------------------------------------
--  R-BASIS-01  beginvoorraad is ook een mutatie
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-BASIS-01  beginvoorraad krijgt een journaalregel');

SELECT eis((SELECT count(*) FROM journal WHERE soort='IMPORT') = 3,
           'drie IMPORT-journaalregels, één per voorraadregel');
SELECT eis((SELECT count(*) FROM journal) = (SELECT count(*) FROM stock),
           'evenveel journaalregels als voorraadregels');
SELECT eis((SELECT reden FROM journal WHERE soort='IMPORT' LIMIT 1) = 'Beginvoorraad',
           'met een reden erbij');
SELECT eis((SELECT gebruiker FROM journal WHERE soort='IMPORT' LIMIT 1) = 'dennis',
           'en met de naam van wie het gedaan heeft');
SELECT eis((SELECT qty FROM stock s JOIN product p ON p.id=s.product_id
             JOIN location l ON l.id=s.location_id
             WHERE p.sku='IMP-1' AND l.code='01-01-1') = 30,
           'de voorraad staat waar hij hoort');
SELECT eis((SELECT count(*) FROM event_log WHERE bron='import') = 1,
           'en er staat een regel in het log');

-- Vanaf hier is er geen verschil meer met een magazijn dat al draaide.
SELECT eis((SELECT beschikbaar FROM v_available a JOIN product p ON p.id=a.product_id
             WHERE p.sku='IMP-1') = 530,
           'de afgeleide waarden werken meteen: 530 beschikbaar');

-- Een tweede import op hetzelfde magazijn wordt nu geweigerd.
DO $$
BEGIN
  PERFORM vakto_import('[]'::jsonb, '[]'::jsonb, '[]'::jsonb);
  RAISE EXCEPTION 'GEZAKT: een tweede import werd toegelaten';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    na de eerste import weigert de tweede';
END $$;

-- --------------------------------------------------------------- einde
SELECT zeg('');
SELECT zeg('alles teruggedraaid, de database is weer zoals hij was');
ROLLBACK;
