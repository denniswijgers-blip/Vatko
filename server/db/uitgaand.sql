-- =====================================================================
--  VAKTO — uitgaand (R-UIT)
--
--  Van order tot verzending. Waarom staat dit in de database?
--
--  Om dezelfde reden als boeken (R-BOEK-03): reserveren raakt voorraad
--  aan. Het verhoogt stock.res en dat mag nooit boven qty uitkomen, ook
--  niet als twee pickers precies tegelijk de laatste vijf stuks pakken.
--  Een greedy lus in Python die eerst leest en daarna schrijft, kan dat
--  niet garanderen — tussen lezen en schrijven zit een gat waar een
--  tweede sessie doorheen loopt. Met SELECT … FOR UPDATE hier zit dat
--  gat er niet, en geldt de regel ook voor wie hem met psql aanroept.
--
--  Wat hier NIET gebeurt is rekenen. Het aantal colli (R-UIT-07) en de
--  looproutewaarde (R-UIT-03) komen uit vakto/uitgaand.py, want daar is
--  niets te vergrendelen en alles zonder database te testen.
--
--  Vijf functies:
--    vakto_reserveer()   R-UIT-01, R-UIT-02  order → voorraad vasthouden
--    vakto_geef_vrij()   R-UIT-03            werk de vloer op
--    vakto_pick()        R-UIT-04, R-UIT-05  afmelden, inclusief manco
--    vakto_pak_in()      R-UIT-07            colli en gewicht vastleggen
--    vakto_verzend()     R-UIT-06            de laatste overgang
--
--  Draaien:  psql -d vakto -f uitgaand.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_order(text, text, jsonb, integer, text);
DROP FUNCTION IF EXISTS vakto_reserveer(bigint, text);
DROP FUNCTION IF EXISTS vakto_geef_vrij(bigint);
DROP FUNCTION IF EXISTS vakto_pick(bigint, integer, text, text);
DROP FUNCTION IF EXISTS vakto_pak_in(bigint, integer, bigint);
DROP FUNCTION IF EXISTS vakto_verzend(bigint, text);


-- ---------------------------------------------------------------------
--  Een order aanmaken
--
--  In het echt komt een order uit het ERP of uit de webshop; dit is de
--  deur waardoor hij binnenkomt. Er zit met opzet geen rekenwerk in:
--  een order is niets meer dan een klant met regels, en alles wat er
--  daarna mee gebeurt staat in R-UIT-01 en verder.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_order(
  p_nummer text,
  p_klant  text,
  p_regels jsonb,                -- [{sku, besteld}]
  p_prio   integer DEFAULT 3,
  p_soort  text    DEFAULT NULL
) RETURNS bigint AS $$
DECLARE
  v_order bigint;
  v_r     record;
  v_idx   integer := 0;
  v_pid   integer;
BEGIN
  IF p_regels IS NULL OR jsonb_array_length(p_regels) = 0 THEN
    RAISE EXCEPTION 'Een order zonder regels bestaat niet'
      USING ERRCODE = 'check_violation';
  END IF;

  INSERT INTO customer_order (nummer, klant, prio, soort)
       VALUES (p_nummer, p_klant, p_prio, p_soort)
    RETURNING id INTO v_order;

  FOR v_r IN
    SELECT * FROM jsonb_to_recordset(p_regels) AS x(sku text, besteld integer)
  LOOP
    SELECT id INTO v_pid FROM product WHERE upper(sku) = upper(v_r.sku);
    IF v_pid IS NULL THEN
      RAISE EXCEPTION 'Order % noemt artikel %, en dat bestaat niet',
        p_nummer, v_r.sku USING ERRCODE = 'no_data_found';
    END IF;
    IF v_r.besteld IS NULL OR v_r.besteld <= 0 THEN CONTINUE; END IF;

    INSERT INTO order_line (order_id, idx, product_id, besteld)
         VALUES (v_order, v_idx, v_pid, v_r.besteld);
    v_idx := v_idx + 1;
  END LOOP;

  IF v_idx = 0 THEN
    RAISE EXCEPTION 'Order % had geen bruikbare regels', p_nummer
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN v_order;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_order IS
  'De deur waardoor een order binnenkomt. Geen rekenwerk: dat begint bij R-UIT-01.';


-- ---------------------------------------------------------------------
--  R-UIT-01 en R-UIT-02 — reserveren
--
--  Reserveren verplaatst niets. Het legt vast welke voorraad op welke
--  locatie voor deze order bestemd is: qty blijft staan, res gaat omhoog
--  en er komt een allocation-rij bij. Vrije voorraad is altijd qty - res.
--
--  Volgorde van kandidaten: picklocatie eerst, daarna location.seq
--  oplopend. Dat is geen smaak maar looproute — zie R-UIT-03.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_reserveer(
  p_order     bigint,
  p_gebruiker text DEFAULT NULL
) RETURNS text AS $$
DECLARE
  v_order    customer_order%ROWTYPE;
  v_regel    record;
  v_kandidaat record;
  v_nodig    integer;
  v_neem     integer;
  v_compleet boolean := true;
BEGIN
  SELECT * INTO v_order FROM customer_order WHERE id = p_order FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Order % bestaat niet', p_order USING ERRCODE = 'no_data_found';
  END IF;

  -- Alleen vanuit deze twee statussen. Een order die al vrijgegeven is
  -- opnieuw reserveren zou voorraad vasthouden waar niemand meer naar kijkt.
  IF v_order.status NOT IN ('NIEUW', 'WACHT_OP_VOORRAAD') THEN
    RETURN v_order.status;
  END IF;

  FOR v_regel IN
    SELECT idx, product_id, besteld, gereserveerd
      FROM order_line
     WHERE order_id = p_order
     ORDER BY idx
  LOOP
    v_nodig := v_regel.besteld - v_regel.gereserveerd;
    IF v_nodig <= 0 THEN CONTINUE; END IF;

    -- Eerst vergrendelen, dan pas lezen — en vergrendelen in dezelfde
    -- volgorde als vakto_boek dat doet: oplopend op location_id
    -- (R-BOEK-02). Zou je hier op seq vergrendelen en daar op
    -- location_id, dan zetten een picker en een reservering elkaar
    -- vroeg of laat klem op precies twee vakken.
    PERFORM 1 FROM stock
     WHERE product_id = v_regel.product_id
     ORDER BY location_id
       FOR UPDATE;

    -- Pas hierna de volgorde van R-UIT-02: picklocatie eerst, daarna seq.
    FOR v_kandidaat IN
      SELECT s.location_id, s.qty - s.res AS vrij
        FROM stock s
        JOIN location      l ON l.id = s.location_id
        JOIN location_type t ON t.id = l.type_id
       WHERE s.product_id = v_regel.product_id
         AND s.qty - s.res > 0
         AND NOT t.blok
         AND l.actief
       ORDER BY t.pick DESC, l.seq, s.location_id
    LOOP
      EXIT WHEN v_nodig <= 0;
      v_neem := LEAST(v_nodig, v_kandidaat.vrij);

      UPDATE stock SET res = res + v_neem
       WHERE product_id = v_regel.product_id
         AND location_id = v_kandidaat.location_id;

      INSERT INTO allocation (order_id, regel, product_id, location_id, qty)
           VALUES (p_order, v_regel.idx, v_regel.product_id,
                   v_kandidaat.location_id, v_neem);

      UPDATE order_line SET gereserveerd = gereserveerd + v_neem
       WHERE order_id = p_order AND idx = v_regel.idx;

      v_nodig := v_nodig - v_neem;
    END LOOP;

    IF v_nodig > 0 THEN v_compleet := false; END IF;
  END LOOP;

  -- R-UIT-02: één waarschuwing, niet bij elke poging opnieuw. Dat de
  -- order al op WACHT_OP_VOORRAAD stond is precies het bewijs dat het
  -- tekort al gemeld is; daar is geen apart vlaggetje voor nodig.
  IF NOT v_compleet AND v_order.status <> 'WACHT_OP_VOORRAAD' THEN
    INSERT INTO event_log (niveau, bron, bericht, ref)
         VALUES ('WARN', 'reservering',
                 format('Order %s kan niet volledig gereserveerd worden',
                        v_order.nummer),
                 v_order.nummer);
  END IF;

  UPDATE customer_order
     SET status = CASE WHEN v_compleet THEN 'GERESERVEERD'
                                       ELSE 'WACHT_OP_VOORRAAD' END
   WHERE id = p_order;

  RETURN CASE WHEN v_compleet THEN 'GERESERVEERD' ELSE 'WACHT_OP_VOORRAAD' END;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_reserveer IS
  'R-UIT-01, R-UIT-02. Reserveren verplaatst niets: res omhoog, allocation erbij. '
  'Vergrendelt de kandidaten, zodat res nooit boven qty uitkomt.';


-- ---------------------------------------------------------------------
--  R-UIT-03 — vrijgeven
--
--  Pas hier gaat er werk de vloer op. De pickregels bestaan al (het zijn
--  de allocation-rijen); vrijgeven zet alleen de order op VRIJGEGEVEN.
--  De volgorde waarin de picker ze ziet komt uit v_picklijst, op seq —
--  niet op ordervolgorde. Dat is het hele verschil tussen één keer door
--  de gang lopen en heen en weer sjouwen.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_geef_vrij(p_order bigint) RETURNS integer AS $$
DECLARE
  v_status text;
  v_open   integer;
BEGIN
  SELECT status INTO v_status FROM customer_order WHERE id = p_order FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Order % bestaat niet', p_order USING ERRCODE = 'no_data_found';
  END IF;
  IF v_status <> 'GERESERVEERD' THEN
    RETURN 0;
  END IF;

  SELECT count(*) INTO v_open FROM allocation
   WHERE order_id = p_order AND status = 'TODO';
  IF v_open = 0 THEN
    RETURN 0;                       -- niets te picken is niets vrij te geven
  END IF;

  UPDATE customer_order SET status = 'VRIJGEGEVEN' WHERE id = p_order;
  RETURN v_open;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_geef_vrij IS
  'R-UIT-03. Zet de order op VRIJGEGEVEN. De pickvolgorde staat in v_picklijst.';


-- ---------------------------------------------------------------------
--  R-UIT-04 en R-UIT-05 — picken en manco
--
--  De valkuil uit hoofdstuk 6 staat hier: de reservering geven we zelf
--  vrij, de voorraad laten we aan vakto_boek(). Nooit allebei, anders
--  boek je dubbel af en krijg je even later "onvoldoende voorraad op
--  bronlocatie" bij een vak waar genoeg ligt.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_pick(
  p_allocation bigint,
  p_aantal     integer,
  p_gebruiker  text DEFAULT NULL,
  p_teltaak    text DEFAULT NULL   -- de reden-tekst; Python stelt hem samen
) RETURNS text AS $$
DECLARE
  v_a        allocation%ROWTYPE;
  v_order    customer_order%ROWTYPE;
  v_aanwezig integer;
  v_te_max   integer;
  v_neem     integer;
  v_tekort   integer;
  v_afboeken integer;
  v_loc      text;
  v_sku      text;
BEGIN
  SELECT * INTO v_a FROM allocation WHERE id = p_allocation FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Pickregel % bestaat niet', p_allocation
      USING ERRCODE = 'no_data_found';
  END IF;
  IF v_a.status <> 'TODO' THEN
    RAISE EXCEPTION 'Pickregel % is al afgehandeld (%)', p_allocation, v_a.status
      USING ERRCODE = 'check_violation';
  END IF;
  IF p_aantal IS NULL OR p_aantal < 0 THEN
    RAISE EXCEPTION 'Een pick van % kan niet', p_aantal
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT * INTO v_order FROM customer_order WHERE id = v_a.order_id FOR UPDATE;

  SELECT qty INTO v_aanwezig FROM stock
   WHERE product_id = v_a.product_id AND location_id = v_a.location_id
     FOR UPDATE;

  -- R-UIT-04
  v_te_max := LEAST(v_a.qty - v_a.gepickt, COALESCE(v_aanwezig, 0));
  v_neem   := GREATEST(0, LEAST(p_aantal, v_te_max));

  IF v_neem > 0 THEN
    UPDATE stock SET res = GREATEST(0, res - v_neem)
     WHERE product_id = v_a.product_id AND location_id = v_a.location_id;

    PERFORM vakto_boek(v_a.product_id, v_neem, 'PICK', v_a.location_id,
                       NULL, NULL, v_order.nummer, p_gebruiker);

    UPDATE allocation SET gepickt = gepickt + v_neem WHERE id = p_allocation;
    UPDATE order_line SET gepickt = gepickt + v_neem
     WHERE order_id = v_a.order_id AND idx = v_a.regel;

    v_a.gepickt := v_a.gepickt + v_neem;
  END IF;

  IF v_a.gepickt >= v_a.qty THEN
    UPDATE allocation SET status = 'DONE' WHERE id = p_allocation;
  ELSE
    -- R-UIT-05. Vier dingen tegelijk, en niets minder.
    v_tekort := v_a.qty - v_a.gepickt;
    SELECT code INTO v_loc FROM location WHERE id = v_a.location_id;
    SELECT sku  INTO v_sku FROM product  WHERE id = v_a.product_id;

    UPDATE allocation SET status = 'MANCO' WHERE id = p_allocation;

    -- 1. reservering vrijgeven, zodat een ander deze voorraad kan gebruiken
    SELECT qty INTO v_aanwezig FROM stock
     WHERE product_id = v_a.product_id AND location_id = v_a.location_id;
    IF FOUND THEN
      UPDATE stock SET res = GREATEST(0, res - v_tekort)
       WHERE product_id = v_a.product_id AND location_id = v_a.location_id;

      -- 2. systeemaantal corrigeren, maar nooit meer dan er volgens het
      --    systeem ligt: afboeken = min(tekort, stock.qty)
      v_afboeken := LEAST(v_tekort, v_aanwezig);
      IF v_afboeken > 0 THEN
        PERFORM vakto_boek(v_a.product_id, v_afboeken, 'ADJUST', v_a.location_id,
                           NULL, 'MANCO', v_order.nummer, p_gebruiker);
      END IF;
    END IF;

    -- 3. teltaak: alleen een mens weet het echte aantal
    INSERT INTO task (soort, naam, prio, product_id, van, naar, qty,
                      aanleiding, reden)
         VALUES ('CYCLE_COUNT', 'Tellen na manco', 45, v_a.product_id,
                 v_a.location_id, v_a.location_id, v_tekort, 'manco',
                 COALESCE(p_teltaak,
                          format('Manco bij %s: %s van %s niet gevonden op %s',
                                 v_order.nummer, v_tekort, v_a.qty, v_loc)));

    -- 4. orderregel markeren, zodat de klant een eerlijke pakbon krijgt
    UPDATE order_line SET manco = manco + v_tekort
     WHERE order_id = v_a.order_id AND idx = v_a.regel;

    INSERT INTO event_log (niveau, bron, bericht, ref)
         VALUES ('WARN', 'picken',
                 format('Manco %sx %s op %s (%s)',
                        v_tekort, v_sku, v_loc, v_order.nummer),
                 v_order.nummer);
  END IF;

  -- R-UIT-06. GEPICKT zodra geen enkele regel meer TODO is — een manco
  -- is een afgehandelde regel, geen open regel.
  IF EXISTS (SELECT 1 FROM allocation
              WHERE order_id = v_a.order_id AND status = 'TODO') THEN
    UPDATE customer_order SET status = 'PICKEN'
     WHERE id = v_a.order_id AND status = 'VRIJGEGEVEN';
  ELSE
    UPDATE customer_order SET status = 'GEPICKT' WHERE id = v_a.order_id;
  END IF;

  RETURN (SELECT status FROM allocation WHERE id = p_allocation);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_pick IS
  'R-UIT-04, R-UIT-05. Reservering zelf vrijgeven, voorraad aan vakto_boek() laten. '
  'Bij een manco vier dingen tegelijk: vrijgeven, corrigeren, tellen, markeren.';


-- ---------------------------------------------------------------------
--  R-UIT-07 — inpakken en verzenden
--  Colli en gewicht rekent Python uit (vakto/uitgaand.py); hier worden
--  ze alleen vastgelegd, samen met de statusovergang.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_pak_in(
  p_order     bigint,
  p_colli     integer,
  p_gewicht_g bigint
) RETURNS boolean AS $$
DECLARE
  v_raak integer;
BEGIN
  UPDATE customer_order
     SET status = 'INGEPAKT', colli = p_colli, gewicht_g = p_gewicht_g
   WHERE id = p_order AND status = 'GEPICKT';
  GET DIAGNOSTICS v_raak = ROW_COUNT;
  RETURN v_raak > 0;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION vakto_verzend(
  p_order bigint,
  p_track text DEFAULT NULL
) RETURNS boolean AS $$
DECLARE
  v_raak integer;
BEGIN
  UPDATE customer_order
     SET status = 'VERZONDEN', track = p_track
   WHERE id = p_order AND status = 'INGEPAKT';
  GET DIAGNOSTICS v_raak = ROW_COUNT;

  -- Een order die verzonden is mag niets meer vasthouden. Staat hier nog
  -- een reservering open, dan is er eerder iets misgegaan en zou die
  -- voorraad voor niemand meer beschikbaar zijn (T-18).
  IF v_raak > 0 AND EXISTS (SELECT 1 FROM allocation
                             WHERE order_id = p_order AND status = 'TODO') THEN
    RAISE EXCEPTION 'Order % heeft nog open pickregels en kan niet verzonden worden',
      p_order USING ERRCODE = 'check_violation';
  END IF;
  RETURN v_raak > 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_verzend IS
  'R-UIT-06. Laatste overgang. Weigert zolang er nog een pickregel op TODO staat.';


-- ---------------------------------------------------------------------
--  R-UIT-03 — de picklijst, op looproute
--
--  Als view en niet als functie, zodat een scherm er gewoon op kan
--  filteren en pagineren (R-BASIS-07).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_picklijst AS
SELECT a.id            AS allocation_id,
       a.order_id,
       o.nummer        AS ordernummer,
       o.prio,
       a.regel,
       a.product_id,
       p.sku,
       p.oms,
       a.location_id,
       l.code          AS locatie,
       l.zone_id,
       l.seq,
       a.qty,
       a.gepickt,
       a.qty - a.gepickt AS nog_te_picken
FROM   allocation a
JOIN   customer_order o ON o.id = a.order_id
JOIN   location       l ON l.id = a.location_id
JOIN   product        p ON p.id = a.product_id
WHERE  a.status = 'TODO'
  AND  o.status IN ('VRIJGEGEVEN', 'PICKEN')
ORDER  BY o.prio, o.id, l.seq, a.id;

COMMENT ON VIEW v_picklijst IS
  'R-UIT-03. Gesorteerd op looproute (location.seq), niet op ordervolgorde.';

COMMIT;
