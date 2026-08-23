-- =====================================================================
--  VAKTO — meten en afwijking (R-MEET)
--
--  Twee functies, en een duidelijke taakverdeling.
--
--  vakto_meting()   schrijft de meting weg en, als Python er een
--                   afwijking in zag, de melding erbij — in één
--                   transactie. Half schrijven mag niet: een meting
--                   zonder melding is een gemiste waarschuwing, een
--                   melding zonder meting is niet te verklaren.
--
--  vakto_melding_sluiten()  zet een melding op OPGELOST (R-ZC-01).
--
--  Wat hier NIET gebeurt is rekenen. Het percentage en de gevolg-tekst
--  komen kant-en-klaar uit vakto/meten.py. Dat is R-BOEK-03: de database
--  bewaakt integriteit, Python doet de berekeningen. Zou je de pas-
--  berekening hier in PL/pgSQL herhalen, dan heb je hem op twee plekken
--  staan en lopen ze binnen een half jaar uit elkaar.
--
--  Draaien:  psql -d vakto -f meten.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_meting(integer,integer,integer,integer,integer,text,text,numeric,numeric,text);
DROP FUNCTION IF EXISTS vakto_melding_sluiten(bigint,text);

CREATE FUNCTION vakto_meting(
  p_product   integer,
  p_l         integer,
  p_w         integer,
  p_h         integer,
  p_g         integer,
  p_bron      text    DEFAULT 'RECEIPT',
  p_notitie   text    DEFAULT NULL,
  -- Onderstaande drie horen bij elkaar: alle drie gevuld = melding
  -- aanmaken, alle drie leeg = geen melding. Python bepaalt dat.
  p_d_vol     numeric DEFAULT NULL,
  p_d_gew     numeric DEFAULT NULL,
  p_gevolg    text    DEFAULT NULL
) RETURNS TABLE (meting_id bigint, melding_id bigint) AS $$
DECLARE
  v_meting  bigint;
  v_melding bigint := NULL;
BEGIN
  IF p_l IS NULL OR p_w IS NULL OR p_h IS NULL OR p_g IS NULL THEN
    RAISE EXCEPTION 'een meting zonder complete maat is geen meting (R-MEET-01)';
  END IF;

  -- R-MEET-01. Toevoegen, nooit bijwerken. De trigger measurement_append_only
  -- houdt dat ook tegen als iemand het toch probeert.
  INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g, notitie)
       VALUES (p_product, p_bron, p_l, p_w, p_h, p_g, p_notitie)
    RETURNING id INTO v_meting;

  IF p_d_vol IS NOT NULL AND p_d_gew IS NOT NULL THEN
    -- Eén open melding per artikel. Een melding is een uitspraak over de
    -- huidige toestand, geen regel op een takenlijst; twee open uitspraken
    -- over hetzelfde artikel spreken elkaar tegen. Ligt er al een, dan
    -- vervangen we de inhoud en laten we de melding staan — inclusief het
    -- oorspronkelijke tijdstip, zodat je ziet hoe lang dit al speelt.
    UPDATE alert
       SET d_vol = p_d_vol, d_gew = p_d_gew, gevolg = COALESCE(p_gevolg, '')
     WHERE product_id = p_product AND status = 'OPEN'
    RETURNING id INTO v_melding;

    IF v_melding IS NULL THEN
      INSERT INTO alert (product_id, d_vol, d_gew, gevolg)
           VALUES (p_product, p_d_vol, p_d_gew, COALESCE(p_gevolg, ''))
        RETURNING id INTO v_melding;
    END IF;
  END IF;

  RETURN QUERY SELECT v_meting, v_melding;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_meting IS
  'R-MEET-01 t/m R-MEET-03. Meting en melding in één transactie. '
  'Rekenen gebeurt in vakto/meten.py, niet hier (R-BOEK-03).';


CREATE FUNCTION vakto_melding_sluiten(
  p_melding bigint,
  p_status  text DEFAULT 'OPGELOST'
) RETURNS boolean AS $$
DECLARE
  v_raak integer;
BEGIN
  IF p_status NOT IN ('OPGELOST', 'DISMISSED') THEN
    RAISE EXCEPTION 'een melding sluiten kan alleen als OPGELOST of DISMISSED, niet als %', p_status;
  END IF;

  UPDATE alert
     SET status = p_status, opgelost_op = now()
   WHERE id = p_melding AND status = 'OPEN';
  GET DIAGNOSTICS v_raak = ROW_COUNT;
  RETURN v_raak > 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_melding_sluiten IS
  'R-ZC-01. OPGELOST zet het systeem zelf, DISMISSED is de enige menselijke keuze.';


-- R-MEET-04, als view: wat moet er (opnieuw) op de weegschaal?
-- Als view en niet als functie, zodat je er gewoon op kunt filteren en
-- sorteren vanuit een scherm.
CREATE OR REPLACE VIEW v_te_meten AS
SELECT p.id                AS product_id,
       p.sku,
       p.oms,
       c.gemeten_op,
       c.bron,
       CASE WHEN c.product_id IS NULL       THEN 'NOOIT_GEMETEN'
            WHEN c.bron = 'SUPPLIER'        THEN 'OPGAVE_LEVERANCIER'
            ELSE                                 'TE_OUD'
       END AS reden
FROM   product p
LEFT   JOIN v_product_current c ON c.product_id = p.id
WHERE  c.product_id IS NULL
   OR  c.bron = 'SUPPLIER'
   OR  c.gemeten_op < now() - (
         (SELECT waarde FROM setting WHERE sleutel = 'drift.remeasure_after_days')
         || ' days')::interval
ORDER  BY (c.product_id IS NOT NULL), c.gemeten_op, p.id;

COMMENT ON VIEW v_te_meten IS
  'R-MEET-04. Nooit gemeten bovenaan, daarna oudste eerst.';

COMMIT;
