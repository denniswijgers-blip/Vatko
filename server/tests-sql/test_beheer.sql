-- =====================================================================
--  VAKTO — instellingen wijzigen (R-INST-01), de databasekant.
--
--  Of een waarde ergens op slaat is rekenwerk en staat in
--  vakto/instellingen.py (tests/test_beheer.py). Wat hier bewezen wordt
--  is wat de database zelf bewaakt: alleen bestaande sleutels, en elke
--  wijziging navraagbaar met de oude waarde erbij.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_beheer.sql
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
SELECT zeg('een instelling wijzigen');

-- De stand van vóór deze test. Het log kan al regels bevatten van een
-- eerdere sessie; we tellen alleen wat er hier bij komt.
CREATE TEMP TABLE voor AS
  SELECT (SELECT waarde FROM setting WHERE sleutel = 'putaway.fill_factor')
           AS waarde,
         (SELECT coalesce(max(id), 0) FROM event_log) AS laatste_log;

SELECT eis(vakto_instelling('putaway.fill_factor', '0.60', 'proef'),
           'wijzigen geeft true terug');
SELECT eis((SELECT waarde FROM setting WHERE sleutel='putaway.fill_factor')
           = '0.60', 'en de waarde staat er');

SELECT eis(NOT vakto_instelling('putaway.fill_factor', '0.60', 'proef'),
           'dezelfde waarde nog eens is geen wijziging');

SELECT zeg('');
SELECT zeg('navraagbaarheid (R-INST-01)');

SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='instellingen'
               AND id > (SELECT laatste_log FROM voor)) = 1,
           'er staat precies één regel in het log');
SELECT eis((SELECT bericht FROM event_log WHERE bron='instellingen'
             ORDER BY id DESC LIMIT 1) LIKE '%' || (SELECT waarde FROM voor) || '%',
           'met de oude waarde erbij — anders weet je over drie maanden niet wat hij was');
SELECT eis((SELECT bericht FROM event_log WHERE bron='instellingen'
             ORDER BY id DESC LIMIT 1) LIKE '%proef%',
           'en met wie het deed');
SELECT eis((SELECT niveau FROM event_log WHERE bron='instellingen'
             ORDER BY id DESC LIMIT 1) = 'WARN',
           'als waarschuwing: een gewijzigde instelling verandert het rekenwerk');

SELECT zeg('');
SELECT zeg('wat er niet mag');

DO $$
BEGIN
  BEGIN
    PERFORM vakto_instelling('putaway.fill_factor_nieuw', '1', 'proef');
    RAISE EXCEPTION 'GEZAKT: een verzonnen sleutel werd aangemaakt';
  EXCEPTION WHEN no_data_found THEN
    RAISE NOTICE '  OK    een sleutel die niet bestaat wordt geweigerd';
  END;
END $$;

SELECT eis((SELECT count(*) FROM setting
             WHERE sleutel='putaway.fill_factor_nieuw') = 0,
           'en er is niets bijgekomen');

-- De rekenkern moet de nieuwe waarde meteen zien; dat is het hele punt
-- van een instellingentabel (R-BASIS-04).
SELECT eis((SELECT waarde::numeric FROM setting
             WHERE sleutel='putaway.fill_factor') = 0.60,
           'de nieuwe waarde is gewoon uit de tabel te lezen');

SELECT zeg('');
SELECT zeg('klaar — alles wordt teruggedraaid');
ROLLBACK;
