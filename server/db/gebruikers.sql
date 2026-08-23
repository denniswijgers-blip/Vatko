-- =====================================================================
--  VAKTO — gebruikers, rollen en sessies (R-GEB)
--
--  De verdeling is dezelfde als overal: het rekenwerk staat in Python
--  (vakto/gebruikers.py — welke rol wat mag, een wachtwoord tot een
--  afdruk maken en die toetsen), en hier staat wat de database moet
--  bewaken.
--
--  Waarom een sessie hier hoort en niet in het geheugen van de
--  webserver (R-GEB-05): een herstart logt dan niemand uit, twee mensen
--  kunnen tegelijk werken zonder elkaars stand te zien, en een sessie is
--  in te trekken. Iemand die uit dienst gaat is er dan ook echt uit, en
--  niet pas als de server toevallig herstart.
--
--    vakto_gebruiker()        aanmaken of bijwerken
--    vakto_sessie_start()     inloggen: een rij met een vervaltijd
--    vakto_sessie()           wie is dit, en mag hij er nog in?
--    vakto_sessie_eind()      uitloggen: de rij weg, niet alleen het koekje
--    vakto_sessies_van()      alle sessies van één gebruiker intrekken
--    vakto_inlogpoging()      tellen en op slot doen (R-GEB-07)
--    vakto_op_slot()          staat deze naam op slot?
--
--  Draaien:  psql -d vakto -f gebruikers.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_gebruiker(text,text,text,text,text);
DROP FUNCTION IF EXISTS vakto_sessie_start(integer,text,integer,boolean,text);
DROP FUNCTION IF EXISTS vakto_sessie(text);
DROP FUNCTION IF EXISTS vakto_sessie_eind(text);
DROP FUNCTION IF EXISTS vakto_sessies_van(integer);
DROP FUNCTION IF EXISTS vakto_inlogpoging(text,boolean,text);
DROP FUNCTION IF EXISTS vakto_op_slot(text,integer,integer);
DROP FUNCTION IF EXISTS vakto_gebruiker_uit(integer);

-- ---------------------------------------------------------------------
--  De gebruikers zelf
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_user (
  id             serial PRIMARY KEY,
  naam           text NOT NULL,
  gebruikersnaam text UNIQUE NOT NULL,
  badge          text UNIQUE,
  rol            text NOT NULL DEFAULT 'OPERATOR'
                   CHECK (rol IN ('OPERATOR','SUPERVISOR','ADMIN')),
  -- R-GEB-04. Nooit het wachtwoord zelf: "scrypt$n$r$p$<zout>$<afdruk>".
  -- Leeg mag: dan komt die medewerker alleen met zijn badge de
  -- scanmodus in, en verder nergens.
  wachtwoord     text,
  actief         boolean NOT NULL DEFAULT true,
  at             timestamptz NOT NULL DEFAULT now(),
  CHECK (wachtwoord IS NULL OR wachtwoord LIKE 'scrypt$%'),
  CHECK (wachtwoord IS NOT NULL OR badge IS NOT NULL)
);
COMMENT ON TABLE  app_user IS 'R-GEB-01. Drie rollen met een rang; de rang staat in Python.';
COMMENT ON COLUMN app_user.badge IS
  'R-GEB-03. Geen wachtwoord: een badge ligt op tafel. Alleen de scanmodus.';
CREATE INDEX IF NOT EXISTS app_user_badge_idx ON app_user(badge)
  WHERE badge IS NOT NULL AND actief;

-- ---------------------------------------------------------------------
--  Sessies (R-GEB-05)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app_session (
  -- De sha256 van het koekje, niet het koekje zelf. Anders levert een
  -- gestolen back-up meteen een stapel geldige sessies op — en een
  -- back-up staat per definitie ergens anders dan de database.
  afdruk         text PRIMARY KEY,
  user_id        integer NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  at             timestamptz NOT NULL DEFAULT now(),
  tot            timestamptz NOT NULL,
  -- Aangemeld met een badge: alleen de scanmodus, en nooit een hogere
  -- rang dan de rol van die gebruiker toestaat.
  alleen_scanner boolean NOT NULL DEFAULT false,
  vanaf          text,
  CHECK (tot > at)
);
CREATE INDEX IF NOT EXISTS app_session_user_idx ON app_session(user_id);
CREATE INDEX IF NOT EXISTS app_session_tot_idx  ON app_session(tot);

-- ---------------------------------------------------------------------
--  Inlogpogingen (R-GEB-07)
--
--  Alleen de gebruikersnaam en of het lukte. Geen wachtwoord, ook niet
--  het foute: dat is meestal het goede wachtwoord van een ander systeem.
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS inlogpoging (
  id             bigserial PRIMARY KEY,
  gebruikersnaam text NOT NULL,
  at             timestamptz NOT NULL DEFAULT now(),
  gelukt         boolean NOT NULL,
  vanaf          text
);
CREATE INDEX IF NOT EXISTS inlogpoging_idx
  ON inlogpoging(lower(gebruikersnaam), at DESC);


-- ---------------------------------------------------------------------
--  Aanmaken of bijwerken. Het wachtwoord komt er als afdruk in; deze
--  functie ziet nooit een wachtwoord in leesbare vorm.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_gebruiker(
  p_gebruikersnaam text,
  p_naam           text,
  p_rol            text DEFAULT 'OPERATOR',
  p_afdruk         text DEFAULT NULL,
  p_badge          text DEFAULT NULL
) RETURNS integer AS $$
DECLARE
  v_id integer;
BEGIN
  -- Eerst bijwerken, dan pas invoegen. Met ON CONFLICT zou de CHECK
  -- "wachtwoord of badge" al slaan op de rij die we voorstellen, en die
  -- heeft geen van beide als je alleen de rol aanpast — terwijl de rij
  -- die er straks staat ze allebei nog heeft.
  UPDATE app_user
     SET naam       = p_naam,
         rol        = p_rol,
         -- Een lege afdruk betekent "laat staan", niet "wis het".
         wachtwoord = COALESCE(p_afdruk, wachtwoord),
         badge      = COALESCE(nullif(trim(coalesce(p_badge, '')), ''), badge),
         actief     = true
   WHERE gebruikersnaam = lower(trim(p_gebruikersnaam))
  RETURNING id INTO v_id;

  IF v_id IS NULL THEN
    INSERT INTO app_user (gebruikersnaam, naam, rol, wachtwoord, badge)
         VALUES (lower(trim(p_gebruikersnaam)), p_naam, p_rol, p_afdruk,
                 nullif(trim(coalesce(p_badge, '')), ''))
      RETURNING id INTO v_id;
  END IF;
  RETURN v_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_gebruiker IS
  'R-GEB-01. Aanmaken of bijwerken; het wachtwoord komt er al versleuteld in.';


-- ---------------------------------------------------------------------
--  Inloggen: een rij met een vervaltijd.
--
--  Meteen ook opruimen wat verlopen is. Dat kost niets — er staan er
--  hooguit een paar honderd — en het scheelt een taak die iemand moet
--  onthouden.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_sessie_start(
  p_user           integer,
  p_afdruk         text,
  p_uren           integer DEFAULT 12,
  p_alleen_scanner boolean DEFAULT false,
  p_vanaf          text    DEFAULT NULL
) RETURNS timestamptz AS $$
DECLARE
  v_tot  timestamptz;
  v_naam text;
  v_rol  text;
BEGIN
  SELECT naam, rol INTO v_naam, v_rol
    FROM app_user WHERE id = p_user AND actief;
  IF v_naam IS NULL THEN
    RAISE EXCEPTION 'Deze gebruiker bestaat niet of staat uit'
      USING ERRCODE = 'no_data_found';
  END IF;

  DELETE FROM app_session WHERE tot < now();

  v_tot := now() + (greatest(1, p_uren) || ' hours')::interval;
  INSERT INTO app_session (afdruk, user_id, tot, alleen_scanner, vanaf)
       VALUES (p_afdruk, p_user, v_tot, p_alleen_scanner, p_vanaf);

  -- R-GEB-06. Inloggen hoort navraagbaar te zijn.
  PERFORM vakto_log('inloggen',
    format('%s ingelogd%s', v_naam,
           CASE WHEN p_alleen_scanner THEN ' met badge (scanmodus)' ELSE '' END),
    'INFO', v_rol);
  RETURN v_tot;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  Wie is dit? Geeft niets terug als de sessie niet bestaat, verlopen is
--  of bij een gebruiker hoort die inmiddels uitstaat.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_sessie(p_afdruk text)
RETURNS TABLE (
  user_id integer, naam text, gebruikersnaam text, rol text, badge text,
  alleen_scanner boolean, tot timestamptz
) AS $$
  SELECT u.id, u.naam, u.gebruikersnaam, u.rol, u.badge,
         s.alleen_scanner, s.tot
    FROM app_session s
    JOIN app_user    u ON u.id = s.user_id
   WHERE s.afdruk = p_afdruk
     AND s.tot > now()
     AND u.actief;
$$ LANGUAGE sql STABLE;


-- ---------------------------------------------------------------------
--  Uitloggen. De rij weg, niet alleen het koekje: dat laatste werkt nog
--  bij wie hem heeft opgeschreven.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_sessie_eind(p_afdruk text) RETURNS boolean AS $$
DECLARE
  v_naam text;
BEGIN
  DELETE FROM app_session s
   USING app_user u
   WHERE s.afdruk = p_afdruk AND u.id = s.user_id
  RETURNING u.naam INTO v_naam;
  IF v_naam IS NULL THEN
    RETURN false;
  END IF;
  PERFORM vakto_log('inloggen', format('%s uitgelogd', v_naam));
  RETURN true;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  Alle sessies van één gebruiker intrekken. Dit is wat je aanroept als
--  iemand uit dienst gaat, of als een telefoon kwijt is.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_sessies_van(p_user integer) RETURNS integer AS $$
DECLARE
  v_aantal integer;
BEGIN
  DELETE FROM app_session WHERE user_id = p_user;
  GET DIAGNOSTICS v_aantal = ROW_COUNT;
  RETURN v_aantal;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  R-GEB-07. Pogingen tellen, en op slot doen als het er te veel zijn.
--
--  Het slot zit op de gebruikersnaam en duurt een kwartier. Niet langer:
--  een slot dat een dag duurt is zelf een storing, en de teamleider die
--  om half zes zijn wachtwoord vergeet moet de dag nog kunnen afmaken.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_op_slot(
  p_gebruikersnaam text,
  p_max            integer DEFAULT 10,
  p_minuten        integer DEFAULT 15
) RETURNS boolean AS $$
  SELECT count(*) >= p_max
    FROM inlogpoging
   WHERE lower(gebruikersnaam) = lower(trim(p_gebruikersnaam))
     AND NOT gelukt
     AND at > now() - (p_minuten || ' minutes')::interval;
$$ LANGUAGE sql STABLE;


CREATE FUNCTION vakto_inlogpoging(
  p_gebruikersnaam text,
  p_gelukt         boolean,
  p_vanaf          text DEFAULT NULL
) RETURNS void AS $$
BEGIN
  INSERT INTO inlogpoging (gebruikersnaam, gelukt, vanaf)
       VALUES (lower(trim(p_gebruikersnaam)), p_gelukt, p_vanaf);

  IF p_gelukt THEN
    -- Gelukt wist de teller: anders loopt iemand die vanmorgen drie keer
    -- misklikte vanmiddag alsnog tegen het slot aan.
    DELETE FROM inlogpoging
     WHERE lower(gebruikersnaam) = lower(trim(p_gebruikersnaam))
       AND NOT gelukt;
  ELSE
    PERFORM vakto_log('inloggen',
      format('Mislukte poging voor %s', lower(trim(p_gebruikersnaam))), 'WARN');
  END IF;

  -- Ouder dan een dag zegt niets meer over wie er nu aan het proberen is.
  DELETE FROM inlogpoging WHERE at < now() - interval '1 day';
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  Uit dienst. Geen DELETE: zijn naam staat in het journaal, en dat mag
--  niet onleesbaar worden. Zijn sessies gaan in dezelfde beweging weg,
--  want anders loopt de tablet in de kantine gewoon door (R-GEB-05).
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_gebruiker_uit(p_user integer) RETURNS text AS $$
DECLARE
  v_naam text;
BEGIN
  UPDATE app_user SET actief = false WHERE id = p_user RETURNING naam
    INTO v_naam;
  IF v_naam IS NULL THEN
    RETURN NULL;
  END IF;
  DELETE FROM app_session WHERE user_id = p_user;
  PERFORM vakto_log('gebruikers',
    format('%s staat uit dienst; sessies ingetrokken', v_naam), 'WARN');
  RETURN v_naam;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  Wie er is, voor het beheerscherm.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_gebruikers AS
SELECT u.id, u.naam, u.gebruikersnaam, u.rol, u.badge, u.actief, u.at,
       (u.wachtwoord IS NOT NULL) AS heeft_wachtwoord,
       (SELECT count(*) FROM app_session s
         WHERE s.user_id = u.id AND s.tot > now()) AS sessies
  FROM app_user u
 ORDER BY u.actief DESC, u.naam;

COMMENT ON VIEW v_gebruikers IS
  'Nooit de wachtwoordkolom zelf: alleen of er een is.';

COMMIT;
