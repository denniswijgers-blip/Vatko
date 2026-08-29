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
--    vakto_drempel()      een aanvuldrempel overnemen of laten (R-OPT-05)
--
--  Draaien:  psql -d vakto -f beheer.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_instelling(text, text, text);
DROP FUNCTION IF EXISTS vakto_drempel(integer, integer, integer, boolean, text);

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

-- ---------------------------------------------------------------------
--  R-OPT-05. Het advies over een aanvuldrempel is een advies, geen taak:
--  hoeveel je op de vloer wilt hebben is een besluit over werkkapitaal
--  en ruimte, en besluiten horen bij mensen. Er zijn dus twee knoppen,
--  en allebei komen ze hier uit.
--
--    overnemen   min_qty en max_qty gaan naar wat het verbruik zegt
--    laten       drempel_akkoord aan; dit artikel wordt niet meer
--                voorgesteld, tot iemand de drempel zelf weer aanpast
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_drempel(
  p_product   integer,
  p_min       integer DEFAULT NULL,
  p_max       integer DEFAULT NULL,
  p_akkoord   boolean DEFAULT NULL,
  p_gebruiker text    DEFAULT NULL
) RETURNS boolean AS $$
DECLARE
  v_sku text;
  v_oud integer;
BEGIN
  SELECT sku, min_qty INTO v_sku, v_oud
    FROM product WHERE id = p_product FOR UPDATE;
  IF v_sku IS NULL THEN
    RAISE EXCEPTION 'Onbekend artikel %', p_product
      USING ERRCODE = 'no_data_found';
  END IF;

  UPDATE product
     SET min_qty = COALESCE(p_min, min_qty),
         max_qty = COALESCE(p_max, max_qty),
         -- Een nieuwe drempel overnemen zet het akkoord weer uit: vanaf
         -- nu mag het systeem er opnieuw iets van vinden.
         drempel_akkoord = COALESCE(p_akkoord,
                                    CASE WHEN p_min IS NULL THEN drempel_akkoord
                                         ELSE false END)
   WHERE id = p_product;

  IF p_min IS NOT NULL THEN
    PERFORM vakto_log('advies',
      format('%s: aanvuldrempel van %s naar %s%s', v_sku,
             COALESCE(v_oud::text, '—'), p_min,
             CASE WHEN p_gebruiker IS NULL THEN ''
                  ELSE ' (' || p_gebruiker || ')' END));
  ELSIF p_akkoord THEN
    PERFORM vakto_log('advies',
      format('%s: advies genegeerd, dit artikel wordt niet meer voorgesteld%s',
             v_sku, CASE WHEN p_gebruiker IS NULL THEN ''
                         ELSE ' (' || p_gebruiker || ')' END));
  END IF;
  RETURN true;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_drempel IS
  'R-OPT-05. Het advies overnemen of laten; allebei een menselijke keuze.';

COMMIT;
