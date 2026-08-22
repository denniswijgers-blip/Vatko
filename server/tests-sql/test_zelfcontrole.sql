-- =====================================================================
--  VAKTO — zelfcontrole en optimalisatie (R-ZC, R-OPT), de schrijfkant.
--
--  Het rekenwerk van hoofdstuk 9 en 10 staat in Python en wordt daar
--  getest (tests/test_zelfcontrole.py en test_optimalisatie.py). Wat
--  hier bewezen wordt is wat er met die uitkomst gebeurt: een taak die
--  vervalt houdt zijn reden, een taak die uitgevoerd wordt boekt via
--  vakto_boek() en nergens anders langs, en een telling zet het stempel
--  dat R-ZC-03 en R-OPT-04 nodig hebben.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_zelfcontrole.sql
--  Alles wat het doet wordt aan het eind teruggedraaid.
-- =====================================================================
\set ON_ERROR_STOP on
\pset pager off
BEGIN;

-- --------------------------------------------------------------- opzet
INSERT INTO zone (id, code, naam) VALUES (920,'TST','Testzone zelfcontrole');
INSERT INTO location (id, code, zone_id, type_id, aisle, bay, level, seq,
                      l_mm, w_mm, h_mm, max_g) VALUES
  (920,'Z-01-1',920,0,1,1,1,1000110, 300, 400, 220,  12000),  -- picklocatie
  (921,'Z-02-1',920,1,2,1,1,2999810,1200, 800,1500, 900000),  -- bulk
  (922,'Z-03-1',920,1,3,1,1,3000110,1200, 800,1500, 900000);  -- bulk
INSERT INTO product_group (id, naam, telinterval) VALUES (920,'Testgroep Z',30);
INSERT INTO product (id, sku, oms, group_id, min_qty, max_qty) VALUES
  (920,'ZC-1','Testartikel zelfcontrole',920,20,40);
INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g) VALUES
  (920,'RECEIPT',120,90,45,180);

CREATE OR REPLACE FUNCTION zeg(txt text) RETURNS void AS
  $$ BEGIN RAISE NOTICE '  %', txt; END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION eis(voorwaarde boolean, wat text) RETURNS void AS $$
BEGIN
  IF voorwaarde THEN RAISE NOTICE '  OK    %', wat;
  ELSE RAISE EXCEPTION 'GEZAKT: %', wat; END IF;
END $$ LANGUAGE plpgsql;

SELECT vakto_boek(920, 5,   'RECEIPT', NULL, 920);   -- picklocatie, onder drempel
SELECT vakto_boek(920, 500, 'RECEIPT', NULL, 921);   -- bulk

SELECT zeg('');
SELECT zeg('werk klaarzetten');

-- ---------------------------------------------------------------------
--  vakto_taak
-- ---------------------------------------------------------------------
CREATE TEMP TABLE t AS SELECT vakto_taak(
  'REPLENISH','Picklocatie aanvullen',25,920,921,920,25,
  'drempel','Picklocatie Z-01-1 onder drempel (5/20)') AS aanvul;

SELECT eis((SELECT aanvul FROM t) IS NOT NULL, 'een taak krijgt een nummer');
SELECT eis((SELECT status FROM task WHERE id=(SELECT aanvul FROM t)) = 'TODO',
           'en staat op TODO');
SELECT eis((SELECT reden FROM task WHERE id=(SELECT aanvul FROM t))
             = 'Picklocatie Z-01-1 onder drempel (5/20)',
           'de reden staat erbij, zodat de picker weet waarom hij loopt');

-- R-OPT-03: nooit twee loopjes naar hetzelfde vak.
SELECT eis(vakto_taak('REPLENISH','Picklocatie aanvullen',10,920,921,920,30,
                      'ordervraag','30 st gevraagd') IS NULL,
           'R-OPT-03: een tweede aanvultaak voor hetzelfde vak wordt geweigerd');
SELECT eis((SELECT count(*) FROM task
             WHERE soort='REPLENISH' AND product_id=920 AND status='TODO') = 1,
           'er ligt er precies één');

-- Bijwerken mag wel: hoogste aantal, laagste prioriteitsnummer.
SELECT eis(vakto_taak_bijwerken((SELECT aanvul FROM t), 30, 10,
                                'ordervraag','30 st gevraagd'),
           'bijwerken lukt');
SELECT eis((SELECT qty FROM task WHERE id=(SELECT aanvul FROM t)) = 30
       AND (SELECT prio FROM task WHERE id=(SELECT aanvul FROM t)) = 10
       AND (SELECT aanleiding FROM task WHERE id=(SELECT aanvul FROM t)) = 'ordervraag',
           'R-OPT-03: hoogste aantal, laagste prioriteitsnummer, zwaarste aanleiding');
SELECT eis(vakto_taak_bijwerken((SELECT aanvul FROM t), 5, 40, 'drempel','minder'),
           'een lichtere aanleiding maakt de taak niet kleiner');
SELECT eis((SELECT qty FROM task WHERE id=(SELECT aanvul FROM t)) = 30
       AND (SELECT prio FROM task WHERE id=(SELECT aanvul FROM t)) = 10,
           'aantal en prioriteit blijven staan');

SELECT eis((SELECT count(*) FROM v_werklijst WHERE product_id=920) = 1,
           'de werklijst laat het openstaande werk zien');

-- Een taak van nul stuks bestaat niet.
DO $$
BEGIN
  PERFORM vakto_taak('OVERLOOP','Overloop',15,920,920,921,0);
  RAISE EXCEPTION 'GEZAKT: een taak van 0 stuks werd geaccepteerd';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    een taak van 0 stuks bestaat niet';
END $$;

-- ---------------------------------------------------------------------
--  R-ZC-03  vervallen, niet verwijderen
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-ZC-03  taken vervallen, ze verdwijnen niet');

SELECT eis(vakto_taak_vervallen((SELECT aanvul FROM t),
                                'picklocatie is weer op peil'),
           'T-17: de aanvultaak vervalt');
SELECT eis((SELECT status FROM task WHERE id=(SELECT aanvul FROM t)) = 'VERVALLEN',
           'T-17: status VERVALLEN');
SELECT eis((SELECT vervallen_reden FROM task WHERE id=(SELECT aanvul FROM t))
             = 'picklocatie is weer op peil',
           'T-17: met de reden erbij, precies zoals de browserversie hem schrijft');
SELECT eis((SELECT vervallen_op FROM task WHERE id=(SELECT aanvul FROM t)) IS NOT NULL,
           'en met het tijdstip erbij');
SELECT eis((SELECT count(*) FROM task WHERE id=(SELECT aanvul FROM t)) = 1,
           'de taak staat er nog: verwijderen mag niet');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='zelfcontrole'
               AND bericht='ZC-1: taak vervallen — picklocatie is weer op peil') = 1,
           'T-17: er staat een regel in het log');
SELECT eis(NOT vakto_taak_vervallen((SELECT aanvul FROM t), 'nog een keer'),
           'twee keer laten vervallen doet niets');
SELECT eis(NOT EXISTS (SELECT 1 FROM v_werklijst
                        WHERE id=(SELECT aanvul FROM t)),
           'een vervallen taak staat niet meer op de werklijst');

-- Na het vervallen mag er wél weer een nieuwe komen.
SELECT eis(vakto_taak('REPLENISH','Picklocatie aanvullen',25,920,921,920,25,
                      'drempel','opnieuw onder de drempel') IS NOT NULL,
           'na het vervallen kan er weer een aanvultaak bij');

-- ---------------------------------------------------------------------
--  Een taak uitvoeren — via vakto_boek en nergens anders langs
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('een taak uitvoeren boekt via vakto_boek');

CREATE TEMP TABLE u AS
SELECT id AS aanvul FROM task
 WHERE soort='REPLENISH' AND product_id=920 AND status='TODO';

SELECT eis(vakto_taak_uitvoeren((SELECT aanvul FROM u), 10) IS NOT NULL,
           'deels afmelden geeft een journaalnummer terug');
SELECT eis((SELECT qty FROM stock WHERE product_id=920 AND location_id=920) = 15,
           'de voorraad is echt verplaatst');
SELECT eis((SELECT qty FROM stock WHERE product_id=920 AND location_id=921) = 490,
           'en van de bulklocatie afgehaald');
SELECT eis((SELECT count(*) FROM journal
             WHERE product_id=920 AND soort='MOVE'
               AND ref='Taak ' || (SELECT aanvul FROM u)) = 1,
           'precies één MOVE-journaalregel, met het taaknummer erbij');
SELECT eis((SELECT status FROM task WHERE id=(SELECT aanvul FROM u)) = 'TODO'
       AND (SELECT qty FROM task WHERE id=(SELECT aanvul FROM u)) = 15,
           'deels afgemeld blijft openstaan voor de rest');

SELECT eis(vakto_taak_uitvoeren((SELECT aanvul FROM u)) IS NOT NULL,
           'de rest afmelden lukt zonder aantal');
SELECT eis((SELECT status FROM task WHERE id=(SELECT aanvul FROM u)) = 'DONE',
           'en dan is de taak DONE');

DO $$
BEGIN
  PERFORM vakto_taak_uitvoeren((SELECT aanvul FROM u));
  RAISE EXCEPTION 'GEZAKT: een afgehandelde taak liet zich opnieuw uitvoeren';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    een afgehandelde taak laat zich niet opnieuw uitvoeren';
END $$;

-- Meer verplaatsen dan er ligt houdt vakto_boek tegen, niet deze functie.
DO $$
DECLARE v_id bigint;
BEGIN
  v_id := vakto_taak('OVERLOOP','Overloop verplaatsen',15,920,922,921,5,
                     'afwijking','test');
  PERFORM vakto_taak_uitvoeren(v_id);
  RAISE EXCEPTION 'GEZAKT: er werd verplaatst wat er niet lag';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    verplaatsen van een leeg vak wordt door vakto_boek geweigerd';
END $$;

-- ---------------------------------------------------------------------
--  T-16  een OVERLOOP-taak uitvoeren
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('T-16  een overlooptaak uitvoeren');

CREATE TEMP TABLE o AS SELECT vakto_taak(
  'OVERLOOP','Overloop verplaatsen',15,920,920,921,3,
  'afwijking','Z-01-1 zit 3 st over de nieuwe maat') AS over;

INSERT INTO alert (id, product_id, d_vol, d_gew, gevolg) VALUES
  (920, 920, 44.0, 16.7, 'Past niet meer op: Z-01-1 (ligt 30, past nog 27)');

SELECT eis(vakto_taak_uitvoeren((SELECT over FROM o)) IS NOT NULL,
           'T-16: de overlooptaak wordt uitgevoerd');
SELECT eis((SELECT qty FROM stock WHERE product_id=920 AND location_id=920) = 27,
           'T-16: er liggen er nog 27 op de picklocatie');
SELECT eis((SELECT status FROM task WHERE id=(SELECT over FROM o)) = 'DONE',
           'T-16: de taak is afgemeld');

-- Het sluiten van de melding is de beslissing van de zelfcontrole (Python).
-- Wat de database moet kunnen is hem sluiten met een log-regel erbij.
SELECT eis(vakto_melding_sluiten(920, 'OPGELOST'),
           'T-16: de melding gaat dicht');
SELECT eis((SELECT status FROM alert WHERE id=920) = 'OPGELOST',
           'T-16: status OPGELOST');
SELECT eis((SELECT opgelost_op FROM alert WHERE id=920) IS NOT NULL,
           'T-16: met het tijdstip erbij');
SELECT vakto_log('zelfcontrole',
                 'ZC-1: afwijking vanzelf gesloten, de voorraad past weer');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bericht LIKE 'ZC-1: afwijking vanzelf gesloten%') = 1,
           'T-16: met een regel in het log');
SELECT eis(NOT vakto_melding_sluiten(920, 'OPGELOST'),
           'twee keer sluiten doet niets');

-- Zolang de melding open staat, mag de tekst bijgewerkt worden (R-ZC-01).
INSERT INTO alert (id, product_id, d_vol, d_gew, gevolg) VALUES
  (921, 920, 44.0, 16.7, 'oude tekst');
SELECT eis(vakto_melding_bijwerken(921, 'nieuwe tekst'),
           'R-ZC-01: de gevolg-tekst wordt bijgewerkt');
SELECT eis((SELECT gevolg FROM alert WHERE id=921) = 'nieuwe tekst',
           'en staat er ook echt');
SELECT eis(NOT vakto_melding_bijwerken(921, 'nieuwe tekst'),
           'dezelfde tekst nog een keer schrijven doet niets');
SELECT eis((SELECT d_vol FROM alert WHERE id=921) = 44.0,
           'de percentages blijven staan: die horen bij de meting');

-- ---------------------------------------------------------------------
--  R-OPT-04  tellen
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-OPT-04  tellen');

-- Een teltaak afmelden zonder verschil: alleen het stempel.
CREATE TEMP TABLE c AS SELECT vakto_taak(
  'CYCLE_COUNT','Locatie tellen',45,920,922,922,10,
  'telinterval','100 dag(en) over het telinterval van 30 dagen') AS tel;

SELECT vakto_boek(920, 10, 'RECEIPT', NULL, 922);
SELECT eis(vakto_taak_uitvoeren((SELECT tel FROM c)) IS NULL,
           'tellen boekt niets: het legt vast dát er gekeken is');
SELECT eis((SELECT geteld_op FROM location WHERE id=922) IS NOT NULL,
           'maar het telstempel gaat wel');
SELECT eis((SELECT status FROM task WHERE id=(SELECT tel FROM c)) = 'DONE',
           'en de teltaak is afgemeld');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='tellen' AND bericht='Z-03-1 geteld, geen verschil') = 1,
           'met een regel in het log');

-- Een telling mét verschil boekt wel. Op Z-02-1 ligt er nu 478: van de
-- 500 is er 25 aangevuld naar de picklocatie en 3 teruggekomen als
-- overloop. De teller vindt er twee minder.
SELECT eis((SELECT qty FROM stock WHERE product_id=920 AND location_id=921) = 478,
           'voor de telling ligt er 478');
SELECT eis(vakto_tellen(921, 920, 476) IS NOT NULL,
           'een telling met verschil geeft een journaalnummer');
SELECT eis((SELECT qty FROM stock WHERE product_id=920 AND location_id=921) = 476,
           'de voorraad staat op het getelde aantal');
SELECT eis((SELECT count(*) FROM journal
             WHERE product_id=920 AND soort='COUNT' AND reden='TELLING'
               AND van=921 AND qty=2) = 1,
           'het verschil is als COUNT geboekt, niet als correctie erlangs');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='tellen' AND bericht LIKE '%476 in plaats van 478 (-2)%') = 1,
           'het log zegt wat er geteld is en wat er stond');

-- Omhoog tellen kan ook.
SELECT eis(vakto_tellen(921, 920, 481) IS NOT NULL, 'omhoog tellen kan ook');
SELECT eis((SELECT count(*) FROM journal
             WHERE product_id=920 AND soort='COUNT' AND naar=921 AND qty=5) = 1,
           'dan gaat de boeking de andere kant op');

-- Precies goed geteld boekt niets, maar zet wel het stempel.
CREATE TEMP TABLE g AS SELECT geteld_op AS voor FROM location WHERE id=921;
SELECT eis(vakto_tellen(921, 920, 481) IS NULL,
           'precies goed geteld boekt niets');
SELECT eis((SELECT geteld_op FROM location WHERE id=921) >= (SELECT voor FROM g),
           'maar het stempel gaat wel: daar hangt R-ZC-03 op');

-- Tellen sluit een openstaande teltaak voor dat vak.
CREATE TEMP TABLE c2 AS SELECT vakto_taak(
  'CYCLE_COUNT','Locatie tellen',45,920,921,921,10,'telinterval','test') AS tel;
SELECT vakto_tellen(921, 920, 479);
SELECT eis((SELECT status FROM task WHERE id=(SELECT tel FROM c2)) = 'DONE',
           'een telling sluit de teltaak voor dat vak');

DO $$
BEGIN
  PERFORM vakto_tellen(921, 920, -1);
  RAISE EXCEPTION 'GEZAKT: een negatieve telling werd geaccepteerd';
EXCEPTION WHEN check_violation THEN
  RAISE NOTICE '  OK    een negatieve telling bestaat niet';
END $$;

-- ---------------------------------------------------------------------
--  R-OPT-03  wat vragen de openstaande orders?
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('R-OPT-03  de ordervraag');

INSERT INTO customer_order (id, nummer, klant, status) VALUES
  (920,'ORD-920','Klant A','NIEUW'),
  (921,'ORD-921','Klant B','GEPICKT'),
  (922,'ORD-922','Klant C','VERZONDEN');
INSERT INTO order_line (order_id, idx, product_id, besteld, gepickt) VALUES
  (920, 0, 920, 28, 0),
  (921, 0, 920, 10, 4),
  (922, 0, 920, 50, 50);

SELECT eis((SELECT open_vraag FROM v_ordervraag WHERE product_id=920) = 34,
           'de openstaande vraag is 28 + (10 - 4); de verzonden order telt niet mee');

UPDATE customer_order SET status='INGEPAKT' WHERE id=920;
SELECT eis((SELECT open_vraag FROM v_ordervraag WHERE product_id=920) = 6,
           'een ingepakte order staat niet meer op de picklocatie te wachten');

-- ---------------------------------------------------------------------
--  Het log is een bewijsstuk
-- ---------------------------------------------------------------------
SELECT zeg('');
SELECT zeg('het log is append-only');
DO $$
BEGIN
  DELETE FROM event_log WHERE bron = 'tellen';
  RAISE EXCEPTION 'GEZAKT: een logregel liet zich verwijderen';
EXCEPTION WHEN raise_exception THEN
  IF SQLERRM LIKE 'GEZAKT%' THEN RAISE; END IF;
  RAISE NOTICE '  OK    een logregel laat zich niet verwijderen';
END $$;

-- --------------------------------------------------------------- einde
SELECT zeg('');
SELECT zeg('alles teruggedraaid, de database is weer zoals hij was');
ROLLBACK;
