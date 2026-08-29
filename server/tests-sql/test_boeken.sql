-- =====================================================================
--  Testgevallen die alleen in de database te bewijzen zijn.
--  T-13 uit hoofdstuk 14, plus de checks uit het schema.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_boeken.sql
--  Alles wat het doet wordt aan het eind teruggedraaid.
-- =====================================================================
\set ON_ERROR_STOP on
\pset pager off
BEGIN;

-- --------------------------------------------------------------- opzet
INSERT INTO zone (id, code, naam) VALUES (900,'TST','Testzone');
INSERT INTO location (id, code, zone_id, type_id, aisle, bay, level, seq,
                      l_mm, w_mm, h_mm, max_g) VALUES
  (900,'T-01-1',900,0,1,1,1,1000110, 300, 400, 220,  12000),
  (901,'T-02-1',900,1,1,2,1,1000210,1200, 800,1500, 900000);
INSERT INTO product_group (id, naam, telinterval) VALUES (900,'Testgroep',180);
INSERT INTO product (id, sku, oms, group_id, min_qty, max_qty) VALUES
  (900,'TEST-1','Testartikel',900,10,40);
INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g) VALUES
  (900,'RECEIPT',120,90,45,180);

CREATE OR REPLACE FUNCTION zeg(txt text) RETURNS void AS
  $$ BEGIN RAISE NOTICE '  %', txt; END $$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION eis(voorwaarde boolean, wat text) RETURNS void AS $$
BEGIN
  IF voorwaarde THEN RAISE NOTICE '  OK    %', wat;
  ELSE RAISE EXCEPTION 'GEZAKT: %', wat; END IF;
END $$ LANGUAGE plpgsql;

-- ------------------------------------------------------- ontvangst
SELECT vakto_boek(900, 100, 'RECEIPT', NULL, 901, NULL, 'PO-1');
SELECT eis((SELECT qty FROM stock WHERE product_id=900 AND location_id=901) = 100,
           'ontvangst maakt een voorraadrij aan');
SELECT eis((SELECT count(*) FROM journal WHERE product_id=900) = 1,
           'ontvangst schrijft precies een journaalregel');

-- ------------------------------------------------------- verplaatsen
SELECT vakto_boek(900, 30, 'MOVE', 901, 900, NULL, 'taak-1');
SELECT eis((SELECT qty FROM stock WHERE product_id=900 AND location_id=901) = 70,
           'verplaatsen haalt van de bron af');
SELECT eis((SELECT qty FROM stock WHERE product_id=900 AND location_id=900) = 30,
           'verplaatsen zet op de bestemming');

-- ------------------------------------------------------- T-13
DO $$
DECLARE gelukt boolean := false; regels bigint; voor integer;
BEGIN
  SELECT count(*) INTO regels FROM journal WHERE product_id = 900;
  SELECT qty INTO voor FROM stock WHERE product_id=900 AND location_id=900;
  BEGIN
    PERFORM vakto_boek(900, 999, 'PICK', 900, NULL, NULL, 'ORD-1');
    gelukt := true;
  EXCEPTION WHEN check_violation THEN
    PERFORM zeg('foutmelding: ' || SQLERRM);
  END;
  PERFORM eis(NOT gelukt, 'T-13 meer picken dan er ligt wordt geweigerd');
  PERFORM eis((SELECT count(*) FROM journal WHERE product_id=900) = regels,
              'T-13 geen journaalregel bij een geweigerde boeking');
  PERFORM eis((SELECT qty FROM stock WHERE product_id=900 AND location_id=900) = voor,
              'T-13 voorraad blijft ongewijzigd');
END $$;

-- ------------------------------------------------------- randgevallen
DO $$
DECLARE gelukt boolean := false;
BEGIN
  BEGIN PERFORM vakto_boek(900, 0, 'PICK', 900, NULL); gelukt := true;
  EXCEPTION WHEN check_violation THEN NULL; END;
  PERFORM eis(NOT gelukt, 'aantal nul wordt geweigerd');

  gelukt := false;
  BEGIN PERFORM vakto_boek(900, 5, 'PICK', NULL, NULL); gelukt := true;
  EXCEPTION WHEN check_violation THEN NULL; END;
  PERFORM eis(NOT gelukt, 'boeking zonder bron en zonder bestemming wordt geweigerd');
END $$;

-- ------------------------------------------------- gereserveerd blijft
UPDATE stock SET res = 25 WHERE product_id=900 AND location_id=900;   -- 30 ligt er
DO $$
DECLARE gelukt boolean := false;
BEGIN
  BEGIN PERFORM vakto_boek(900, 10, 'PICK', 900, NULL); gelukt := true;
  EXCEPTION WHEN check_violation THEN
    PERFORM zeg('foutmelding: ' || SQLERRM);
  END;
  PERFORM eis(NOT gelukt,
    'R-UIT-04 je kunt geen gereserveerde voorraad wegboeken zonder de reservering vrij te geven');
END $$;
UPDATE stock SET res = 0 WHERE product_id=900 AND location_id=900;

-- ------------------------------------------------- append-only journaal
DO $$
DECLARE gelukt boolean := false;
BEGIN
  BEGIN UPDATE journal SET qty = 1 WHERE product_id = 900; gelukt := true;
  EXCEPTION WHEN OTHERS THEN PERFORM zeg('foutmelding: ' || SQLERRM); END;
  PERFORM eis(NOT gelukt, 'R-BASIS-01 een journaalregel kan niet gewijzigd worden');

  gelukt := false;
  BEGIN DELETE FROM journal WHERE product_id = 900; gelukt := true;
  EXCEPTION WHEN OTHERS THEN NULL; END;
  PERFORM eis(NOT gelukt, 'R-BASIS-01 een journaalregel kan niet verwijderd worden');
END $$;

-- ------------------------------------------------- metingen ook
DO $$
DECLARE gelukt boolean := false;
BEGIN
  BEGIN UPDATE measurement SET g = 1 WHERE product_id = 900; gelukt := true;
  EXCEPTION WHEN OTHERS THEN NULL; END;
  PERFORM eis(NOT gelukt, 'R-MEET-01 een meting kan niet gewijzigd worden');
END $$;

-- ------------------------------------------------- views (hoofdstuk 3)
SELECT eis((SELECT maatklasse FROM v_location_size WHERE location_id=900) = 'S',
           'R-AFG-02 300x400x220 is maatklasse S');
SELECT eis((SELECT maatklasse FROM v_location_size WHERE location_id=901) = 'XL',
           'R-AFG-02 1200x800x1500 is maatklasse XL');
SELECT eis((SELECT beschikbaar FROM v_available WHERE product_id=900) = 100,
           'R-AFG-03 beschikbaar is 100');
SELECT eis((SELECT bezet_vol_mm3 FROM v_location_load WHERE location_id=900) = 30*120*90*45,
           'R-AFG-04 bezetting telt in volume, niet in stuks');

-- R-AFG-01: de actuele maat is de NIEUWSTE meting
INSERT INTO measurement (product_id, at, bron, l_mm, w_mm, h_mm, g)
     VALUES (900, now() + interval '1 minute', 'RECEIPT', 140, 100, 50, 210);
SELECT eis((SELECT l_mm FROM v_product_current WHERE product_id=900) = 140,
           'R-AFG-01 de actuele maat is de nieuwste meting');

-- ------------------------------------------------- geblokkeerde locatie
INSERT INTO location (id, code, zone_id, type_id, l_mm, w_mm, h_mm, max_g)
     VALUES (902,'T-QC-1',900,3,1200,800,1000,600000);
SELECT vakto_boek(900, 10, 'MOVE', 901, 902, NULL, 'naar keuring');
SELECT eis((SELECT beschikbaar FROM v_available WHERE product_id=900) = 90,
           'R-AFG-03 voorraad op een geblokkeerde locatie telt niet mee');
SELECT eis((SELECT aanwezig FROM v_available WHERE product_id=900) = 100,
           'R-AFG-03 maar hij is er wel');

-- ------------------------------------------------- geen dubbele aanvultaak
INSERT INTO task (soort,naam,prio,product_id,van,naar,qty,aanleiding,reden)
     VALUES ('REPLENISH','Picklocatie aanvullen',25,900,901,900,20,'drempel','test');
DO $$
DECLARE gelukt boolean := false;
BEGIN
  BEGIN
    INSERT INTO task (soort,naam,prio,product_id,van,naar,qty,aanleiding,reden)
         VALUES ('REPLENISH','Picklocatie aanvullen',10,900,901,900,30,'ordervraag','test 2');
    gelukt := true;
  EXCEPTION WHEN unique_violation THEN NULL; END;
  PERFORM eis(NOT gelukt,
    'R-ZC-04 nooit twee open aanvultaken voor hetzelfde artikel en vak');
END $$;

SELECT zeg('');
SELECT zeg('Alle SQL-testgevallen geslaagd.');

ROLLBACK;
