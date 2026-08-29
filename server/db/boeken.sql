-- =====================================================================
--  VAKTO — boeken (R-BOEK)
--
--  Waarom staat dit in de database en niet in Python?
--
--  R-BASIS-01 zegt: voorraad en journaal gaan altijd samen, in dezelfde
--  transactie. Zet je dat in de applicatie, dan geldt het alleen zolang
--  iedereen die route gebruikt. Eén import-scriptje dat "even snel" een
--  UPDATE doet, en je journaal klopt niet meer.
--
--  Zet je het hier, dan geldt het voor iedereen: de webapplicatie, een
--  achtergrondtaak, een collega met psql. Er is geen omweg.
--
--  De grens die we aanhouden:
--     de database  bewaakt integriteit   (boeken, vergrendelen, checks)
--     Python       doet de berekeningen  (passen, benutting, scoren)
--
--  Draaien:  psql -d vakto -f boeken.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_boek(integer,integer,text,integer,integer,text,text,text);

CREATE FUNCTION vakto_boek(
  p_product   integer,
  p_qty       integer,
  p_soort     text,
  p_van       integer DEFAULT NULL,
  p_naar      integer DEFAULT NULL,
  p_reden     text    DEFAULT NULL,
  p_ref       text    DEFAULT NULL,
  p_gebruiker text    DEFAULT NULL
) RETURNS bigint AS $$
DECLARE
  v_aanwezig integer;
  v_code     text;
  v_journaal bigint;
BEGIN
  -- R-BOEK-01 stap 1
  IF p_qty IS NULL OR p_qty <= 0 THEN
    RAISE EXCEPTION 'Aantal moet groter dan 0 zijn (gekregen: %)', p_qty
      USING ERRCODE = 'check_violation';
  END IF;
  IF p_van IS NULL AND p_naar IS NULL THEN
    RAISE EXCEPTION 'Een boeking zonder bron én zonder bestemming bestaat niet'
      USING ERRCODE = 'check_violation';
  END IF;

  -- Vergrendelen in een vaste volgorde (laagste location_id eerst).
  -- Zonder die volgorde loopt A→B tegelijk met B→A vast in een deadlock,
  -- en dat gebeurt in een magazijn vaker dan je denkt: twee mensen die
  -- tegelijk tussen dezelfde twee vakken verplaatsen.
  PERFORM 1 FROM stock
   WHERE product_id = p_product
     AND location_id IN (p_van, p_naar)
   ORDER BY location_id
     FOR UPDATE;

  -- R-BOEK-01 stap 2: eraf halen
  IF p_van IS NOT NULL THEN
    SELECT qty INTO v_aanwezig FROM stock
      WHERE product_id = p_product AND location_id = p_van;

    IF v_aanwezig IS NULL OR v_aanwezig < p_qty THEN
      SELECT code INTO v_code FROM location WHERE id = p_van;
      RAISE EXCEPTION
        'Onvoldoende voorraad op bronlocatie % (aanwezig %, gevraagd %)',
        COALESCE(v_code, p_van::text), COALESCE(v_aanwezig, 0), p_qty
        USING ERRCODE = 'check_violation';
    END IF;

    UPDATE stock SET qty = qty - p_qty
      WHERE product_id = p_product AND location_id = p_van;
  END IF;

  -- R-BOEK-01 stap 3: erbij zetten
  IF p_naar IS NOT NULL THEN
    INSERT INTO stock (product_id, location_id, qty)
         VALUES (p_product, p_naar, p_qty)
    ON CONFLICT (product_id, location_id)
      DO UPDATE SET qty = stock.qty + EXCLUDED.qty;
  END IF;

  -- R-BOEK-01 stap 4: journaal. Zonder deze regel geen boeking.
  INSERT INTO journal (soort, product_id, van, naar, qty, reden, ref, gebruiker)
       VALUES (p_soort, p_product, p_van, p_naar, p_qty, p_reden, p_ref, p_gebruiker)
    RETURNING id INTO v_journaal;

  RETURN v_journaal;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_boek IS
  'R-BOEK-01. De enige route waarlangs voorraad verandert. Voorraad en '
  'journaal in één transactie, met rijvergrendeling in vaste volgorde.';

-- Een lege stock-rij opruimen heeft geen zin (dan verlies je de historie
-- van welk artikel waar heeft gelegen), maar een rij met qty 0 mag geen
-- reservering meer hebben. Dat bewaakt de CHECK res <= qty al.

COMMIT;
