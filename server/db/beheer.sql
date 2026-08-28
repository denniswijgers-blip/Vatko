-- =====================================================================
--  VAKTO — beheer: instellingen wijzigen (R-INST-01)
--
--  Weinig, en met opzet. Of een waarde ergens op slaat is rekenwerk en
--  staat in vakto/instellingen.py; wat hier gebeurt is wat de database
--  moet bewaken: dat je alleen een sleutel kunt wijzigen die al bestaat,
--  en dat elke wijziging navraagbaar is.
--
--  Dat eerste is geen formaliteit. Een sleutel die de code niet kent
--  doet niets, en dan zit iemand een middag te zoeken waarom zijn
--  instelling geen effect heeft.
--
--    vakto_instelling()   één instelling wijzigen, met log
--
--  Draaien:  psql -d vakto -f beheer.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_instelling(text, text, text);

CREATE FUNCTION vakto_instelling(
  p_sleutel   text,
  p_waarde    text,
  p_gebruiker text DEFAULT NULL
) RETURNS boolean AS $$
DECLARE
  v_oud text;
BEGIN
  SELECT waarde INTO v_oud FROM setting WHERE sleutel = p_sleutel FOR UPDATE;
  IF v_oud IS NULL THEN
    RAISE EXCEPTION 'Onbekende instelling %. Nieuwe instellingen komen bij een nieuwe versie mee.',
      p_sleutel USING ERRCODE = 'no_data_found';
  END IF;

  -- Niets veranderd is geen wijziging. Anders staat het log vol met
  -- regels van iemand die op Opslaan drukte zonder iets aan te raken, en
  -- dan is het log niets meer waard.
  IF v_oud IS NOT DISTINCT FROM p_waarde THEN
    RETURN false;
  END IF;

  UPDATE setting SET waarde = p_waarde WHERE sleutel = p_sleutel;

  -- Met de oude waarde erbij. "Vulfactor gewijzigd" zegt niets als je
  -- drie maanden later wilt weten wat hij daarvoor was.
  PERFORM vakto_log('instellingen',
    format('%s: %s → %s%s', p_sleutel, v_oud, p_waarde,
           CASE WHEN p_gebruiker IS NULL THEN ''
                ELSE ' (' || p_gebruiker || ')' END),
    'WARN');
  RETURN true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_instelling IS
  'R-INST-01. Alleen bestaande sleutels, en elke wijziging met de oude waarde in het log.';

COMMIT;
