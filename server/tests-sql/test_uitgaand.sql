-- =====================================================================
--  VAKTO — uitgaand (R-UIT). Testgevallen T-14 en T-15 uit hoofdstuk 14,
--  plus de regels eromheen die alleen in de database te bewijzen zijn.
--
--  Waarom hier en niet in Python: reserveren en picken vergrendelen
--  rijen en boeken voorraad. Wat je hier test is dus precies de reden
--  dat die logica in de database staat en niet in de applicatie.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_uitgaand.sql
--  Alles wat het doet wordt aan het eind teruggedraaid.
-- =====================================================================
\set ON_ERROR_STOP on
\pset pager off
BEGIN;

-- --------------------------------------------------------------- opzet
--  Eén artikel op vier plekken: een picklocatie vooraan, twee bulkvakken
--  op verschillende afstand, en een keuringsvak dat nooit mag meetellen.
INSERT INTO zone (id, code, naam) VALUES (910,'TST','Testzone uitgaand');
INSERT INTO location (id, code, zone_id, type_id, aisle, bay, level, seq,
                      l_mm, w_mm, h_mm, max_g) VALUES
  (910,'U-01-1',910,0,1,1,1,1000110, 300, 400, 220,  12000),  -- picklocatie
  (911,'U-03-1',910,1,3,1,1,3000110,1200, 800,1500, 900000),  -- bulk, verweg
  (912,'U-02-1',910,1,2,1,1,2000110,1200, 800,1500, 900000),  -- bulk, dichterbij
  (913,'U-QC-1',910,3,9,1,1,9000110,1200, 800,1000, 600000),  -- keuring, blok=1
  (914,'U-04-1',910,0,4,1,1,4000110, 300, 400, 220,  12000);  -- tweede picklocatie
INSERT INTO product_group (id, naam, telinterval) VALUES (910,'Testgroep U',180);
INSERT INTO product (id, sku, oms, group_id) VALUES
  (910,'UIT-1','Testartikel uitgaand',910),
  (911,'UIT-2','Tweede testartikel',910);
INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g) VALUES
  (910,'RECEIPT',120,90,45,180),
  (911,'RECEIPT',120,90,45,180);

CREATE OR REPLACE FUNCTION zeg(txt text) RETURNS void AS
  $$ BEGIN RAISE NOTICE '  %', txt; END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION eis(voorwaarde boolean, wat text) RETURNS void AS $$
BEGIN
  IF voorwaarde THEN RAISE NOTICE '  OK    %', wat;
  ELSE RAISE EXCEPTION 'GEZAKT: %', wat; END IF;
END $$ LANGUAGE plpgsql;

-- Voorraad: 10 op de picklocatie, 20 op elk bulkvak, 50 in de keuring.
-- Vrij beschikbaar is dus 50, niet 100: de keuring telt niet mee.
SELECT vakto_boek(910, 10, 'RECEIPT', NULL, 910);
SELECT vakto_boek(910, 20, 'RECEIPT', NULL, 911);
SELECT vakto_boek(910, 20, 'RECEIPT', NULL, 912);
SELECT vakto_boek(910, 50, 'RECEIPT', NULL, 913);

SELECT zeg('');
SELECT zeg('R-UIT-01 en R-UIT-02  reserveren');

-- ---------------------------------------------------------------------
--  Volgorde van kandidaten: picklocatie eerst, daarna seq oplopend.
--  35 stuks = 10 van de picklocatie, 20 van het dichtstbijzijnde bulkvak
--  en de laatste 5 van het verste.
-- ---------------------------------------------------------------------
INSERT INTO customer_order (id, nummer, klant, prio) VALUES
  (910,'ORD-910','Installatiebedrijf Van Loon',3);
INSERT INTO order_line (order_id, idx, product_id, besteld) VALUES
  (910, 0, 910, 35);

SELECT eis(vakto_reserveer(910) = 'GERESERVEERD',
           'een order die past wordt GERESERVEERD');
SELECT eis((SELECT count(*) FROM allocation WHERE order_id=910) = 3,
           'de 35 stuks worden over drie locaties verdeeld');
SELECT eis((SELECT qty FROM allocation WHERE order_id=910 AND location_id=910) = 10,
           'de picklocatie gaat voor: die wordt als eerste leeggehaald');
SELECT eis((SELECT qty FROM allocation WHERE order_id=910 AND location_id=912) = 20,
           'daarna het bulkvak met de laagste seq (U-02-1 vóór U-03-1)');
SELECT eis((SELECT qty FROM allocation WHERE order_id=910 AND location_id=911) = 5,
           'de rest komt van het verste vak');
SELECT eis(NOT EXISTS (SELECT 1 FROM allocation WHERE order_id=910 AND location_id=913),
           'een geblokkeerde locatie komt nooit in een reservering (blok=1)');

-- R-UIT-01: reserveren verplaatst niets.
SELECT eis((SELECT qty FROM stock WHERE product_id=910 AND location_id=910) = 10,
           'reserveren verplaatst niets: qty blijft staan');
SELECT eis((SELECT res FROM stock WHERE product_id=910 AND location_id=910) = 10,
           'reserveren verhoogt res');
SELECT eis((SELECT gereserveerd FROM order_line WHERE order_id=910 AND idx=0) = 35,
           'de orderregel telt mee wat er vastligt');
SELECT eis((SELECT count(*) FROM journal WHERE product_id=910) = 4,
           'reserveren schrijft geen journaalregel — er is niets geboekt');

-- ---------------------------------------------------------------------
--  T-14  Twee orders die samen meer vragen dan er is
--        Er is nog 15 vrij (50 min de 35 hierboven). Deze vraagt er 40.
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('T-14  twee orders die samen meer vragen dan er is');

INSERT INTO customer_order (id, nummer, klant, prio) VALUES
  (911,'ORD-911','Machinefabriek Kessels',3);
INSERT INTO order_line (order_id, idx, product_id, besteld) VALUES
  (911, 0, 910, 40);

SELECT eis(vakto_reserveer(911) = 'WACHT_OP_VOORRAAD',
           'T-14: de tweede order krijgt WACHT_OP_VOORRAAD');
SELECT eis((SELECT gereserveerd FROM order_line WHERE order_id=911 AND idx=0) = 15,
           'T-14: wat er wél was is vastgelegd — 15 van de 40');
SELECT eis(NOT EXISTS (SELECT 1 FROM stock WHERE res > qty),
           'T-14: nergens res > qty');
SELECT eis((SELECT sum(res) FROM stock WHERE product_id=910) = 50,
           'T-14: samen precies de vrije voorraad, geen stuk dubbel verkocht');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='reservering' AND ref='ORD-911') = 1,
           'T-14: één waarschuwing in het log');

-- Nog een keer proberen mag, maar levert geen tweede waarschuwing op.
SELECT eis(vakto_reserveer(911) = 'WACHT_OP_VOORRAAD',
           'opnieuw reserveren mag vanuit WACHT_OP_VOORRAAD');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='reservering' AND ref='ORD-911') = 1,
           'R-UIT-02: één waarschuwing, niet bij elke poging opnieuw');
SELECT eis((SELECT gereserveerd FROM order_line WHERE order_id=911 AND idx=0) = 15,
           'een tweede poging reserveert niet nog eens hetzelfde');

-- De CHECK op stock is de laatste verdedigingslinie, niet de code.
SELECT zeg('');
SELECT zeg('de database houdt dubbel verkopen zelf tegen');
DO $$
BEGIN
  UPDATE stock SET res = res + 1 WHERE product_id=910 AND location_id=910;
  RAISE EXCEPTION 'GEZAKT: res mocht boven qty uitkomen';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    res > qty wordt door de CHECK geweigerd, niet door de code';
END $$;

-- ---------------------------------------------------------------------
--  R-UIT-03  vrijgeven en de picklijst op looproute
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-UIT-03  vrijgeven en looproute');

SELECT eis(vakto_geef_vrij(911) = 0,
           'een order die op WACHT_OP_VOORRAAD staat geef je niet vrij');
SELECT eis(vakto_geef_vrij(910) = 3, 'vrijgeven levert drie pickregels op');
SELECT eis((SELECT status FROM customer_order WHERE id=910) = 'VRIJGEGEVEN',
           'de order staat op VRIJGEGEVEN');
SELECT eis(vakto_geef_vrij(910) = 0, 'twee keer vrijgeven doet niets');

-- De reservering liep picklocatie-eerst (U-01-1, U-02-1, U-03-1); de
-- picklijst loopt puur op seq. Dat die twee hier hetzelfde uitkomen is
-- geen toeval maar het punt: de volgorde ís de looproute.
SELECT eis((SELECT array_agg(locatie ORDER BY seq) FROM v_picklijst WHERE order_id=910)
             = ARRAY['U-01-1','U-02-1','U-03-1'],
           'R-UIT-03: de picklijst loopt op seq, niet op ordervolgorde');
SELECT eis(NOT EXISTS (SELECT 1 FROM v_picklijst WHERE order_id=911),
           'een order die niet is vrijgegeven staat niet op de picklijst');

-- ---------------------------------------------------------------------
--  R-UIT-04  picken
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-UIT-04  picken');

SELECT eis(vakto_pick((SELECT allocation_id FROM v_picklijst
                        WHERE order_id=910 AND location_id=910), 10) = 'DONE',
           'een volledige pick zet de regel op DONE');
SELECT eis((SELECT qty FROM stock WHERE product_id=910 AND location_id=910) = 0,
           'picken haalt de voorraad er echt af');
SELECT eis((SELECT res FROM stock WHERE product_id=910 AND location_id=910) = 0,
           'de reservering is vrijgegeven, niet blijven hangen');
SELECT eis((SELECT count(*) FROM journal
             WHERE product_id=910 AND soort='PICK' AND ref='ORD-910') = 1,
           'precies één PICK-journaalregel, niet twee (nooit dubbel afboeken)');
SELECT eis((SELECT gepickt FROM order_line WHERE order_id=910 AND idx=0) = 10,
           'de orderregel telt mee wat er gepickt is');
SELECT eis((SELECT status FROM customer_order WHERE id=910) = 'PICKEN',
           'de order gaat naar PICKEN zolang er regels open staan');

-- Een regel die al afgehandeld is, pick je niet nog een keer.
DO $$
DECLARE v_id bigint;
BEGIN
  SELECT id INTO v_id FROM allocation WHERE order_id=910 AND location_id=910;
  PERFORM vakto_pick(v_id, 1);
  RAISE EXCEPTION 'GEZAKT: een afgehandelde pickregel liet zich opnieuw picken';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    een afgehandelde pickregel laat zich niet opnieuw picken';
END $$;

-- ---------------------------------------------------------------------
--  T-15  Manco — vier dingen tegelijk
--        Op U-02-1 ligt 20 en die 20 zijn gereserveerd. De picker vindt
--        er 9. Tekort 11.
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('T-15  manco: vier dingen tegelijk');

SELECT eis(vakto_pick((SELECT allocation_id FROM v_picklijst
                        WHERE order_id=910 AND location_id=912), 9) = 'MANCO',
           'T-15: minder gepickt dan gevraagd geeft status MANCO');

-- 1. reservering vrijgeven voor het tekort
SELECT eis((SELECT res FROM stock WHERE product_id=910 AND location_id=912) = 0,
           'T-15 (1): de reservering is vrijgegeven, ook voor het tekort');

-- 2. systeemaantal corrigeren met een ADJUST, reden MANCO
SELECT eis((SELECT count(*) FROM journal
             WHERE product_id=910 AND soort='ADJUST' AND reden='MANCO'
               AND ref='ORD-910' AND qty=11) = 1,
           'T-15 (2): één ADJUST-boeking van 11 (het tekort), reden MANCO');
SELECT eis((SELECT qty FROM stock WHERE product_id=910 AND location_id=912) = 0,
           'T-15 (2): 9 gepickt en 11 afgeboekt, het vak staat leeg');

-- 3. teltaak aanmaken op die locatie
SELECT eis((SELECT count(*) FROM task
             WHERE soort='CYCLE_COUNT' AND product_id=910 AND van=912
               AND status='TODO' AND qty=11) = 1,
           'T-15 (3): er staat een teltaak klaar op die locatie');
SELECT eis((SELECT reden FROM task
             WHERE soort='CYCLE_COUNT' AND product_id=910 AND van=912)
             = 'Manco bij ORD-910: 11 van 20 niet gevonden op U-02-1',
           'T-15 (3): de teltaak zegt in één zin wat er aan de hand is');

-- 4. orderregel markeren met het mancoaantal
SELECT eis((SELECT manco FROM order_line WHERE order_id=910 AND idx=0) = 11,
           'T-15 (4): de orderregel draagt het mancoaantal');
SELECT eis((SELECT gepickt FROM order_line WHERE order_id=910 AND idx=0) = 19,
           'T-15: gepickt is 10 + 9, het manco telt daar niet in mee');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='picken' AND ref='ORD-910') = 1,
           'T-15: het manco staat in het log');
SELECT eis((SELECT status FROM customer_order WHERE id=910) = 'PICKEN',
           'er staat nog één regel open, dus de order blijft op PICKEN');

-- De laatste regel afmaken: 5 stuks van het verste vak.
SELECT eis(vakto_pick((SELECT allocation_id FROM v_picklijst
                        WHERE order_id=910 AND location_id=911), 5) = 'DONE',
           'de laatste pickregel is compleet');
SELECT eis((SELECT status FROM customer_order WHERE id=910) = 'GEPICKT',
           'R-UIT-06: GEPICKT zodra geen regel meer TODO is, manco of niet');
SELECT eis((SELECT gepickt FROM order_line WHERE order_id=910 AND idx=0) = 24
       AND (SELECT manco   FROM order_line WHERE order_id=910 AND idx=0) = 11,
           'besteld 35 = 24 gepickt + 11 manco, de pakbon klopt');

-- ---------------------------------------------------------------------
--  Nooit meer afboeken dan het systeem denkt te hebben
--
--  Zo ontstaat dat in het echt: er is gereserveerd, daarna telt iemand
--  het vak en er blijken er minder te liggen. De reservering krimpt mee
--  met de voorraad, maar de allocation-rij zegt nog het oude aantal.
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('afboeken is nooit meer dan wat het systeem denkt te hebben');

SELECT vakto_boek(911, 10, 'RECEIPT', NULL, 914);
INSERT INTO customer_order (id, nummer, klant) VALUES
  (912,'ORD-912','Pompservice Zeeland');
INSERT INTO order_line (order_id, idx, product_id, besteld) VALUES (912, 0, 911, 5);

SELECT eis(vakto_reserveer(912) = 'GERESERVEERD', 'order 912 reserveert 5 stuks');
SELECT eis(vakto_geef_vrij(912) = 1, 'en wordt vrijgegeven');

-- De telling: er liggen er maar 2. Eerst loslaten, dan afboeken, dan
-- vasthouden wat er nog is.
UPDATE stock SET res = 0 WHERE product_id=911 AND location_id=914;
SELECT vakto_boek(911, 8, 'COUNT', 914, NULL, 'TELLING');
UPDATE stock SET res = 2 WHERE product_id=911 AND location_id=914;

SELECT eis(vakto_pick((SELECT allocation_id FROM v_picklijst WHERE order_id=912), 0)
             = 'MANCO',
           'nul picken is ook een manco');
SELECT eis((SELECT sum(qty) FROM journal
             WHERE product_id=911 AND soort='ADJUST' AND ref='ORD-912') = 2,
           'er wordt 2 afgeboekt en niet 5: min(tekort, stock.qty)');
SELECT eis((SELECT qty FROM stock WHERE product_id=911 AND location_id=914) = 0,
           'de locatie staat daarna op nul, niet op min drie');
SELECT eis((SELECT manco FROM order_line WHERE order_id=912 AND idx=0) = 5,
           'de klant krijgt te horen dat alle vijf ontbreken');
SELECT eis((SELECT status FROM customer_order WHERE id=912) = 'GEPICKT',
           'R-UIT-06: een order met alleen manco is toch GEPICKT');

-- ---------------------------------------------------------------------
--  R-UIT-06 en R-UIT-07  inpakken en verzenden
--  Colli en gewicht rekent vakto/uitgaand.py uit; hier worden ze
--  vastgelegd. 24 stuks van 180 g is 4.320 g, dus één collo.
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-UIT-06 en R-UIT-07  inpakken en verzenden');

SELECT eis(NOT vakto_pak_in(911, 1, 100),
           'inpakken kan niet vanuit een andere status dan GEPICKT');
SELECT eis(vakto_pak_in(910, 1, 4320), 'inpakken lukt vanuit GEPICKT');
SELECT eis((SELECT colli FROM customer_order WHERE id=910) = 1
       AND (SELECT gewicht_g FROM customer_order WHERE id=910) = 4320,
           'colli en gewicht worden vastgelegd');
SELECT eis(NOT vakto_pak_in(910, 1, 4320), 'twee keer inpakken doet niets');
SELECT eis(vakto_verzend(910, '3S123456NL'), 'verzenden lukt vanuit INGEPAKT');
SELECT eis((SELECT status FROM customer_order WHERE id=910) = 'VERZONDEN',
           'de order staat op VERZONDEN');
SELECT eis(NOT vakto_verzend(910, '3S123456NL'), 'twee keer verzenden doet niets');
SELECT eis(NOT EXISTS (SELECT 1 FROM allocation
                        WHERE order_id=910 AND status='TODO'),
           'een verzonden order houdt niets meer vast (T-18)');

-- ---------------------------------------------------------------------
--  Het log is een bewijsstuk, geen kladblok
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('het log is append-only');
DO $$
BEGIN
  UPDATE event_log SET bericht = 'anders' WHERE bron = 'picken';
  RAISE EXCEPTION 'GEZAKT: een logregel liet zich bijwerken';
EXCEPTION WHEN raise_exception THEN
  IF SQLERRM LIKE 'GEZAKT%' THEN RAISE; END IF;
  RAISE NOTICE '  OK    een logregel laat zich niet bijwerken';
END $$;

-- --------------------------------------------------------------- einde
SELECT zeg('');
SELECT zeg('alles teruggedraaid, de database is weer zoals hij was');
ROLLBACK;
