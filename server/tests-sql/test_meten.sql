-- =====================================================================
--  Meten en afwijking — wat alleen de database kan bewijzen (R-MEET).
--
--  De rekenkant staat in tests/test_meten.py. Hier gaat het om de
--  dingen waar Python niets over te zeggen heeft: append-only, meting
--  en melding in één transactie, één open melding per artikel, en de
--  meetlijst als view.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_meten.sql
--  Alles wat het doet wordt aan het eind teruggedraaid.
-- =====================================================================
\set ON_ERROR_STOP on
\pset pager off
BEGIN;

-- --------------------------------------------------------------- opzet
INSERT INTO zone (id, code, naam) VALUES (910,'TST2','Testzone meten');
INSERT INTO location (id, code, zone_id, type_id, aisle, bay, level, seq,
                      l_mm, w_mm, h_mm, max_g) VALUES
  (910,'M-01-1',910,0,1,1,1,1000110, 300, 400, 220, 12000);
INSERT INTO product_group (id, naam, telinterval) VALUES (910,'Testgroep meten',180);
INSERT INTO product (id, sku, oms, group_id) VALUES
  (910,'MEET-1','Artikel met historie',910),
  (911,'MEET-2','Nooit gemeten',910),
  (912,'MEET-3','Opgave leverancier',910),
  (913,'MEET-4','Lang geleden gemeten',910);

INSERT INTO measurement (product_id, at, bron, l_mm, w_mm, h_mm, g) VALUES
  (910, now() - interval '40 days',  'RECEIPT',  120, 90, 45, 180),
  (912, now() - interval '2 days',   'SUPPLIER', 100,100,100, 500),
  (913, now() - interval '400 days', 'RECEIPT',  100,100,100, 500);

CREATE OR REPLACE FUNCTION eis(voorwaarde boolean, wat text) RETURNS void AS $$
BEGIN
  IF voorwaarde THEN RAISE NOTICE '  OK    %', wat;
  ELSE RAISE EXCEPTION 'GEZAKT: %', wat; END IF;
END $$ LANGUAGE plpgsql;

-- ----------------------------------------------- R-MEET-01 append-only
SELECT eis((SELECT count(*) FROM measurement WHERE product_id=910) = 1,
           'het artikel begint met een meting');

DO $$ BEGIN
  BEGIN
    UPDATE measurement SET l_mm = 999 WHERE product_id = 910;
    RAISE EXCEPTION 'GEZAKT: een meting bijwerken werd toegestaan';
  EXCEPTION WHEN raise_exception THEN
    IF POSITION('append-only' IN SQLERRM) = 0 THEN RAISE; END IF;
    RAISE NOTICE '  OK    een meting bijwerken wordt geweigerd (R-MEET-01)';
  END;
END $$;

DO $$ BEGIN
  BEGIN
    DELETE FROM measurement WHERE product_id = 910;
    RAISE EXCEPTION 'GEZAKT: een meting verwijderen werd toegestaan';
  EXCEPTION WHEN raise_exception THEN
    IF POSITION('append-only' IN SQLERRM) = 0 THEN RAISE; END IF;
    RAISE NOTICE '  OK    een meting verwijderen wordt geweigerd (R-MEET-01)';
  END;
END $$;

-- ------------------------------------------- meting zonder afwijking
SELECT vakto_meting(910, 124, 92, 46, 186, 'CONTROL', 'jaarlijkse controle');
SELECT eis((SELECT count(*) FROM measurement WHERE product_id=910) = 2,
           'een meting zonder afwijking wordt gewoon vastgelegd');
SELECT eis((SELECT count(*) FROM alert WHERE product_id=910) = 0,
           'een meting zonder afwijking geeft geen melding');
SELECT eis((SELECT l_mm FROM v_product_current WHERE product_id=910) = 124,
           'de nieuwste meting is de actuele maat (R-AFG-01)');

-- ---------------------------------------------- meting MET afwijking
INSERT INTO stock (product_id, location_id, qty) VALUES (910, 910, 30);
SELECT vakto_meting(910, 140, 100, 50, 210, 'RECEIPT', NULL,
                    44.0, 16.7, 'Past niet meer op: M-01-1 (ligt 30, past nog 27)');
SELECT eis((SELECT count(*) FROM measurement WHERE product_id=910) = 3,
           'de afwijkende meting staat in de tijdlijn');
SELECT eis((SELECT count(*) FROM alert WHERE product_id=910 AND status='OPEN') = 1,
           'de afwijkende meting geeft precies een melding');
SELECT eis((SELECT d_vol FROM alert WHERE product_id=910) = 44.0,
           'het volumepercentage staat in de melding');
SELECT eis((SELECT gevolg FROM alert WHERE product_id=910)
           = 'Past niet meer op: M-01-1 (ligt 30, past nog 27)',
           'de gevolg-tekst komt uit Python en gaat er ongewijzigd in (R-BOEK-03)');

-- ------------------------------------ een open melding per artikel
SELECT vakto_meting(910, 160, 110, 55, 240, 'RECEIPT', NULL,
                    38.3, 14.3, 'Past niet meer op: M-01-1 (ligt 30, past nog 17)');
SELECT eis((SELECT count(*) FROM alert WHERE product_id=910 AND status='OPEN') = 1,
           'een tweede afwijking maakt geen tweede open melding');
SELECT eis((SELECT gevolg FROM alert WHERE product_id=910 AND status='OPEN')
           LIKE '%past nog 17%',
           'de bestaande melding krijgt de nieuwe tekst');
SELECT eis((SELECT count(*) FROM measurement WHERE product_id=910) = 4,
           'de metingen zelf stapelen wel gewoon door');

-- ---------------------------------------------------- melding sluiten
SELECT eis(vakto_melding_sluiten(
             (SELECT id FROM alert WHERE product_id=910 AND status='OPEN')),
           'een open melding laat zich sluiten');
SELECT eis((SELECT status FROM alert WHERE product_id=910) = 'OPGELOST',
           'de melding staat op OPGELOST');
SELECT eis((SELECT opgelost_op FROM alert WHERE product_id=910) IS NOT NULL,
           'het tijdstip van oplossen wordt vastgelegd');
SELECT eis(NOT vakto_melding_sluiten(
             (SELECT id FROM alert WHERE product_id=910)),
           'twee keer sluiten verandert niets meer');

DO $$ BEGIN
  BEGIN
    PERFORM vakto_melding_sluiten((SELECT id FROM alert WHERE product_id=910), 'WEG');
    RAISE EXCEPTION 'GEZAKT: een onbekende status werd toegestaan';
  EXCEPTION WHEN raise_exception THEN
    IF POSITION('OPGELOST of DISMISSED' IN SQLERRM) = 0 THEN RAISE; END IF;
    RAISE NOTICE '  OK    alleen OPGELOST of DISMISSED mag';
  END;
END $$;

-- na het sluiten mag er weer een nieuwe komen
SELECT vakto_meting(910, 200, 130, 60, 300, 'RECEIPT', NULL, 39.5, 25.0, 'Iets anders');
SELECT eis((SELECT count(*) FROM alert WHERE product_id=910) = 2,
           'na oplossen kan er wel een nieuwe melding komen');

-- --------------------------------------------------- onvolledige maat
DO $$ BEGIN
  BEGIN
    PERFORM vakto_meting(910, 140, 100, NULL, 210);
    RAISE EXCEPTION 'GEZAKT: een halve maat werd toegestaan';
  EXCEPTION WHEN raise_exception THEN
    IF POSITION('complete maat' IN SQLERRM) = 0 THEN RAISE; END IF;
    RAISE NOTICE '  OK    een meting zonder complete maat wordt geweigerd';
  END;
END $$;

DO $$ BEGIN
  BEGIN
    PERFORM vakto_meting(910, 140, 100, 50, 0);
    RAISE EXCEPTION 'GEZAKT: een gewicht van 0 werd toegestaan';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE '  OK    een gewicht van nul wordt door het schema tegengehouden';
  END;
END $$;

-- ------------------------------------------------- R-MEET-04 meetlijst
SELECT eis((SELECT count(*) FROM v_te_meten WHERE product_id=911) = 1,
           'een nooit gemeten artikel staat op de meetlijst');
SELECT eis((SELECT reden FROM v_te_meten WHERE product_id=912) = 'OPGAVE_LEVERANCIER',
           'een opgegeven maat is geen gemeten maat');
SELECT eis((SELECT reden FROM v_te_meten WHERE product_id=913) = 'TE_OUD',
           'een meting van 400 dagen oud moet opnieuw');
SELECT eis((SELECT count(*) FROM v_te_meten WHERE product_id=910) = 0,
           'een vers gemeten artikel staat er niet op');
SELECT eis((SELECT product_id FROM v_te_meten
             WHERE product_id IN (910,911,912,913) LIMIT 1) = 911,
           'nooit gemeten staat bovenaan');

ROLLBACK;
\echo '  ---- meten: alles groen ----'
