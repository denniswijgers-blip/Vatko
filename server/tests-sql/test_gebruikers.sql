-- =====================================================================
--  VAKTO — gebruikers, rollen en sessies (R-GEB), de databasekant.
--
--  Het rekenwerk staat in Python en wordt daar getest
--  (tests/test_toegang.py): welke rol wat mag, en een wachtwoord tot een
--  afdruk maken en die toetsen. Wat hier bewezen wordt is wat de
--  database zelf bewaakt — dat er geen gebruiker kan bestaan waar
--  niemand mee naar binnen kan, dat een verlopen sessie niet meer telt,
--  dat iemand die uit dienst gaat er meteen uit is, en dat het slot op
--  mislukte pogingen doet wat het moet doen.
--
--  Draaien:  psql -d vakto -v ON_ERROR_STOP=1 -f tests-sql/test_gebruikers.sql
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

-- Een afdruk zoals gebruikers.py hem maakt. De inhoud doet er hier niet
-- toe: de database toetst geen wachtwoorden, die bewaart ze alleen.
\set afdruk '''scrypt$16384$8$1$00112233445566778899aabbccddeeff$00112233'''

SELECT zeg('');
SELECT zeg('gebruikers aanmaken en bijwerken');

-- ---------------------------------------------------------------------
--  vakto_gebruiker
-- ---------------------------------------------------------------------
CREATE TEMP TABLE g AS
  SELECT vakto_gebruiker('proef.dennis','Dennis Proef','ADMIN',
                          :afdruk,'PROEF-1001') AS baas;

SELECT eis((SELECT baas FROM g) IS NOT NULL, 'een gebruiker krijgt een nummer');
SELECT eis((SELECT rol FROM app_user WHERE id=(SELECT baas FROM g)) = 'ADMIN',
           'en de rol die is meegegeven');
SELECT eis((SELECT gebruikersnaam FROM app_user WHERE id=(SELECT baas FROM g))
           = 'proef.dennis', 'de gebruikersnaam gaat naar kleine letters');

-- Hoofdletters en spaties mogen geen tweede gebruiker opleveren.
SELECT vakto_gebruiker('  PROEF.Dennis ','Dennis Proef','SUPERVISOR');
SELECT eis((SELECT count(*) FROM app_user WHERE gebruikersnaam='proef.dennis') = 1,
           'dezelfde naam met hoofdletters is dezelfde gebruiker');
SELECT eis((SELECT rol FROM app_user WHERE id=(SELECT baas FROM g)) = 'SUPERVISOR',
           'bijwerken verandert de rol');
SELECT eis((SELECT wachtwoord FROM app_user WHERE id=(SELECT baas FROM g))
           IS NOT NULL,
           'maar wist het wachtwoord niet — een lege afdruk is "laat staan"');
SELECT eis((SELECT badge FROM app_user WHERE id=(SELECT baas FROM g))
           = 'PROEF-1001', 'en de badge blijft ook staan');

SELECT zeg('');
SELECT zeg('wat de database niet toelaat');

-- ---------------------------------------------------------------------
--  De checks. Wat hier wordt tegengehouden hoeft de programmeur niet te
--  onthouden — ook niet met psql om elf uur 's avonds.
-- ---------------------------------------------------------------------
DO $$
BEGIN
  BEGIN
    INSERT INTO app_user (gebruikersnaam, naam, rol)
         VALUES ('proef.leeg','Zonder alles','OPERATOR');
    RAISE EXCEPTION 'GEZAKT: een gebruiker zonder wachtwoord én zonder badge';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE '  OK    zonder wachtwoord én zonder badge kan niet';
  END;

  BEGIN
    INSERT INTO app_user (gebruikersnaam, naam, rol, wachtwoord)
         VALUES ('proef.plat','Plat wachtwoord','OPERATOR','geheim123456');
    RAISE EXCEPTION 'GEZAKT: een leesbaar wachtwoord werd geaccepteerd';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE '  OK    een wachtwoord dat geen scrypt-afdruk is kan niet';
  END;

  BEGIN
    INSERT INTO app_user (gebruikersnaam, naam, rol, wachtwoord)
         VALUES ('proef.kok','Hoofdkok','HOOFDKOK','scrypt$x');
    RAISE EXCEPTION 'GEZAKT: een verzonnen rol werd geaccepteerd';
  EXCEPTION WHEN check_violation THEN
    RAISE NOTICE '  OK    een rol buiten de drie kan niet';
  END;
END $$;

SELECT zeg('');
SELECT zeg('sessies');

-- ---------------------------------------------------------------------
--  vakto_sessie_start / vakto_sessie / vakto_sessie_eind
-- ---------------------------------------------------------------------
CREATE TEMP TABLE s AS SELECT vakto_sessie_start(
  (SELECT baas FROM g), 'afdruk-een', 12, false, '127.0.0.1') AS tot;

SELECT eis((SELECT tot FROM s) > now(), 'een sessie krijgt een vervaltijd');
SELECT eis((SELECT count(*) FROM vakto_sessie('afdruk-een')) = 1,
           'en is daarmee terug te vinden');
SELECT eis((SELECT rol FROM vakto_sessie('afdruk-een')) = 'SUPERVISOR',
           'met de rol die er nú bij hoort, niet die van bij het inloggen');
SELECT eis((SELECT count(*) FROM vakto_sessie('verzonnen')) = 0,
           'een verzonnen afdruk geeft niemand');

-- R-GEB-03. Een badge-sessie is als zodanig herkenbaar.
SELECT vakto_sessie_start((SELECT baas FROM g), 'afdruk-badge', 12, true);
SELECT eis((SELECT alleen_scanner FROM vakto_sessie('afdruk-badge')),
           'een badge-sessie draagt dat bij zich');

-- Verlopen telt niet meer.
UPDATE app_session SET at  = now() - interval '13 hours',
                       tot = now() - interval '1 hour'
 WHERE afdruk = 'afdruk-badge';
SELECT eis((SELECT count(*) FROM vakto_sessie('afdruk-badge')) = 0,
           'een verlopen sessie geeft niemand');

SELECT eis(vakto_sessie_eind('afdruk-een'), 'uitloggen lukt');
SELECT eis((SELECT count(*) FROM vakto_sessie('afdruk-een')) = 0,
           'en daarna is de rij weg — niet alleen het koekje');
SELECT eis(NOT vakto_sessie_eind('afdruk-een'),
           'twee keer uitloggen is geen fout, maar levert niets op');

SELECT zeg('');
SELECT zeg('uit dienst');

-- ---------------------------------------------------------------------
--  R-GEB-05. Iemand die uit dienst gaat is er meteen uit, en zijn naam
--  blijft in het journaal staan.
-- ---------------------------------------------------------------------
CREATE TEMP TABLE k AS
  SELECT vakto_gebruiker('proef.kevin','Kevin Proef','OPERATOR',
                          :afdruk) AS picker;
SELECT vakto_sessie_start((SELECT picker FROM k), 'afdruk-kevin');
SELECT vakto_sessie_start((SELECT picker FROM k), 'afdruk-kevin-2');
SELECT eis((SELECT count(*) FROM app_session
             WHERE user_id=(SELECT picker FROM k)) = 2,
           'twee apparaten, twee sessies');

SELECT eis(vakto_gebruiker_uit((SELECT picker FROM k)) = 'Kevin Proef',
           'uit dienst zetten geeft de naam terug');
SELECT eis((SELECT count(*) FROM app_session
             WHERE user_id=(SELECT picker FROM k)) = 0,
           'en trekt al zijn sessies in');
SELECT eis((SELECT count(*) FROM vakto_sessie('afdruk-kevin')) = 0,
           'zijn koekje werkt niet meer');
SELECT eis((SELECT count(*) FROM app_user
             WHERE id=(SELECT picker FROM k)) = 1,
           'maar de rij blijft bestaan: zijn naam staat in het journaal');
SELECT eis(vakto_gebruiker_uit(999999) IS NULL,
           'iemand die niet bestaat uit dienst zetten doet niets');

SELECT zeg('');
SELECT zeg('mislukte pogingen (R-GEB-07)');

-- ---------------------------------------------------------------------
--  Het slot
-- ---------------------------------------------------------------------
SELECT eis(NOT vakto_op_slot('proef.dennis', 10, 15),
           'zonder pogingen staat er niets op slot');

SELECT vakto_inlogpoging('proef.dennis', false) FROM generate_series(1, 9);
SELECT eis(NOT vakto_op_slot('proef.dennis', 10, 15),
           'negen mislukte pogingen is nog geen slot');

SELECT vakto_inlogpoging('proef.dennis', false);
SELECT eis(vakto_op_slot('proef.dennis', 10, 15),
           'de tiende doet de deur op slot');
SELECT eis(NOT vakto_op_slot('proef.kevin', 10, 15),
           'en een ander is er niet de dupe van');

-- Ouder dan een kwartier telt niet meer mee.
UPDATE inlogpoging SET at = now() - interval '20 minutes'
 WHERE lower(gebruikersnaam) = 'proef.dennis';
SELECT eis(NOT vakto_op_slot('proef.dennis', 10, 15),
           'na een kwartier gaat het slot vanzelf open');

-- Een gelukte poging wist de teller.
SELECT vakto_inlogpoging('proef.dennis', false) FROM generate_series(1, 5);
SELECT vakto_inlogpoging('proef.dennis', true);
SELECT eis((SELECT count(*) FROM inlogpoging
             WHERE lower(gebruikersnaam)='proef.dennis' AND NOT gelukt) = 0,
           'een gelukte poging wist de teller');

SELECT zeg('');
SELECT zeg('herleidbaarheid (R-GEB-06)');

SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='inloggen' AND bericht LIKE 'Dennis Proef ingelogd%') > 0,
           'inloggen staat in het log');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='inloggen' AND bericht LIKE '%uitgelogd%') > 0,
           'uitloggen ook');
SELECT eis((SELECT count(*) FROM event_log
             WHERE bron='inloggen' AND niveau='WARN') > 0,
           'en een mislukte poging als waarschuwing');

SELECT zeg('');
SELECT zeg('het beheerscherm');

-- ---------------------------------------------------------------------
--  De view mag nooit een wachtwoordkolom laten zien.
-- ---------------------------------------------------------------------
SELECT eis((SELECT count(*) FROM information_schema.columns
             WHERE table_name='v_gebruikers' AND column_name='wachtwoord') = 0,
           'v_gebruikers heeft geen wachtwoordkolom');
SELECT eis((SELECT heeft_wachtwoord FROM v_gebruikers
             WHERE gebruikersnaam='proef.dennis'),
           'maar wel of er een is');

SELECT zeg('');
SELECT zeg('klaar — alles wordt teruggedraaid');
ROLLBACK;
