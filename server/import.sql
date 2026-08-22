-- =====================================================================
--  VAKTO — import van klantbestanden (R-IMP)
--
--  Het lezen, raden en controleren gebeurt in vakto/inlezen.py. Dat is
--  rekenwerk en het moet zonder database te draaien zijn: je wilt een
--  klantbestand kunnen nakijken en het rapport laten zien vóórdat er
--  ook maar iets is weggeschreven.
--
--  Wat hier gebeurt is het wegschrijven, in één transactie. Dat is geen
--  detail: een import die halverwege stukloopt laat je achter met
--  locaties zonder artikelen, of artikelen zonder de voorraad die
--  erbij hoort. Alles of niets.
--
--  Twee dingen om op te letten:
--
--    * Beginvoorraad gaat door vakto_boek() heen, net als elke andere
--      mutatie (R-BASIS-01). Een magazijn dat opeens vol staat zonder
--      dat er iets geboekt is, valt bij de eerste telling door de mand.
--    * Een aangeleverde maat wordt een METING met bron SUPPLIER en geen
--      veld op het artikel (R-AFG-01). Zo staat er vanaf dag één dat het
--      een opgave is en geen weging, en komt het artikel vanzelf op de
--      meetlijst (R-MEET-04).
--
--  Draaien:  psql -d vakto -f import.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_import(jsonb, jsonb, jsonb, text);
DROP FUNCTION IF EXISTS vakto_zone(text);
DROP FUNCTION IF EXISTS vakto_artikelgroep(text);


-- ---------------------------------------------------------------------
--  Zones en artikelgroepen ontstaan uit wat er in het bestand staat.
--
--  Zoeken op naam en niet op code: EXPEDITIE en Expeditie zijn dezelfde
--  zone, en een klant die beide schrijfwijzen door elkaar gebruikt hoort
--  daar geen twee zones aan over te houden. De code is een afkorting
--  voor op het scherm; botst hij, dan komt er een nummer achter.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_zone(p_naam text) RETURNS integer AS $$
DECLARE
  v_naam text := COALESCE(NULLIF(btrim(p_naam), ''), 'Magazijn');
  v_code text;
  v_id   integer;
  v_n    integer := 1;
BEGIN
  SELECT id INTO v_id FROM zone WHERE upper(naam) = upper(v_naam);
  IF FOUND THEN RETURN v_id; END IF;

  v_code := upper(left(regexp_replace(v_naam, '[^A-Za-z0-9]', '', 'g'), 3));
  IF v_code = '' THEN v_code := 'ZON'; END IF;
  WHILE EXISTS (SELECT 1 FROM zone WHERE code = v_code) LOOP
    v_n := v_n + 1;
    v_code := left(v_code, 2) || v_n::text;
  END LOOP;

  INSERT INTO zone (code, naam) VALUES (v_code, v_naam) RETURNING id INTO v_id;
  RETURN v_id;
END;
$$ LANGUAGE plpgsql;


CREATE FUNCTION vakto_artikelgroep(p_naam text) RETURNS integer AS $$
DECLARE
  v_naam text := COALESCE(NULLIF(btrim(p_naam), ''), 'Overig');
  v_id   integer;
BEGIN
  SELECT id INTO v_id FROM product_group WHERE naam = v_naam;
  IF FOUND THEN RETURN v_id; END IF;
  INSERT INTO product_group (naam) VALUES (v_naam) RETURNING id INTO v_id;
  RETURN v_id;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION vakto_import(
  p_locaties  jsonb,
  p_artikelen jsonb,
  p_voorraad  jsonb,
  p_gebruiker text DEFAULT NULL
) RETURNS jsonb AS $$
DECLARE
  v_r          record;
  v_zone       integer;
  v_groep      integer;
  v_product    integer;
  v_locatie    integer;
  v_zones      integer := 0;
  v_groepen    integer := 0;
  v_locaties   integer := 0;
  v_artikelen  integer := 0;
  v_metingen   integer := 0;
  v_voorraad   integer := 0;
  v_extra      integer := 0;
BEGIN
  -- R-IMP-07. Een import is een nulmeting en geen bijwerking. Staat er
  -- al een journaal, dan draait dit magazijn en overschrijf je het met
  -- een bestand van vorige week -- wat je pas merkt als de picker voor
  -- een leeg vak staat.
  IF EXISTS (SELECT 1 FROM journal) THEN
    RAISE EXCEPTION 'Er staat al een journaal: dit magazijn draait. Een import '
                    'is een nulmeting en overschrijft niets'
      USING ERRCODE = 'check_violation';
  END IF;

  -- ---------------------------------------------------------------
  --  Locaties, met hun zone
  -- ---------------------------------------------------------------
  FOR v_r IN
    SELECT * FROM jsonb_to_recordset(COALESCE(p_locaties, '[]'::jsonb))
      AS x(code text, zone text, type_id integer, gang integer, vak integer,
           niveau integer, seq bigint, l_mm integer, w_mm integer,
           h_mm integer, max_g bigint)
  LOOP
    v_zone := vakto_zone(v_r.zone);
    IF v_zone IS NULL THEN CONTINUE; END IF;

    INSERT INTO location (code, zone_id, type_id, aisle, bay, level, seq,
                          l_mm, w_mm, h_mm, max_g)
         VALUES (v_r.code, v_zone, v_r.type_id, v_r.gang, v_r.vak, v_r.niveau,
                 v_r.seq, v_r.l_mm, v_r.w_mm, v_r.h_mm, v_r.max_g)
    ON CONFLICT (code) DO NOTHING;
  END LOOP;

  -- Zonder ontvangst- en expeditielocatie kun je niets ontvangen en
  -- niets verzenden. Ontbreken ze in het bestand, dan maken we ze.
  v_zone := vakto_zone('Expeditie');
  FOR v_r IN
    SELECT * FROM (VALUES
      (2, 'ONTVANGST', 8000, 4000, 2500, 4000000::bigint),
      (3, 'QC-01',     1200,  800, 1000,  600000::bigint),
      (4, 'SCHADE',    1200,  800, 1000,  600000::bigint),
      (5, 'EXP-01',    4000, 2000, 2000, 2000000::bigint)
    ) AS x(type_id, code, l_mm, w_mm, h_mm, max_g)
  LOOP
    IF NOT EXISTS (SELECT 1 FROM location WHERE type_id = v_r.type_id) THEN
      INSERT INTO location (code, zone_id, type_id, aisle, bay, level, seq,
                            l_mm, w_mm, h_mm, max_g)
           VALUES (v_r.code, v_zone, v_r.type_id, 0, 0, 0, 0,
                   v_r.l_mm, v_r.w_mm, v_r.h_mm, v_r.max_g)
      ON CONFLICT (code) DO NOTHING;
      v_extra := v_extra + 1;
    END IF;
  END LOOP;
  SELECT count(*) INTO v_locaties FROM location;

  -- ---------------------------------------------------------------
  --  Artikelen, met hun groep en hun aangeleverde maat
  -- ---------------------------------------------------------------
  FOR v_r IN
    SELECT * FROM jsonb_to_recordset(COALESCE(p_artikelen, '[]'::jsonb))
      AS x(sku text, oms text, groep text, l_mm integer, w_mm integer,
           h_mm integer, g integer, barcode text, min_qty integer,
           max_qty integer)
  LOOP
    v_groep := vakto_artikelgroep(v_r.groep);

    INSERT INTO product (sku, oms, group_id, min_qty, max_qty, barcode)
         VALUES (v_r.sku, COALESCE(NULLIF(v_r.oms, ''), v_r.sku), v_groep,
                 v_r.min_qty,
                 COALESCE(v_r.max_qty, v_r.min_qty * 4),
                 COALESCE(NULLIF(v_r.barcode, ''), v_r.sku))
    ON CONFLICT (sku) DO NOTHING
      RETURNING id INTO v_product;
    IF v_product IS NULL THEN CONTINUE; END IF;

    -- R-AFG-01. De maat is een meting, geen veld. Bron SUPPLIER, want
    -- dit is een opgave van de klant en niet iets wat iemand gewogen
    -- heeft -- daarom komt het artikel ook meteen op de meetlijst.
    IF v_r.l_mm > 0 AND v_r.w_mm > 0 AND v_r.h_mm > 0 AND v_r.g > 0 THEN
      INSERT INTO measurement (product_id, bron, l_mm, w_mm, h_mm, g, notitie)
           VALUES (v_product, 'SUPPLIER', v_r.l_mm, v_r.w_mm, v_r.h_mm, v_r.g,
                   'Overgenomen uit het aangeleverde bestand');
      v_metingen := v_metingen + 1;
    END IF;
  END LOOP;
  SELECT count(*) INTO v_artikelen FROM product;

  -- ---------------------------------------------------------------
  --  Beginvoorraad -- met journaalregel, want dit is ook een mutatie
  -- ---------------------------------------------------------------
  FOR v_r IN
    SELECT * FROM jsonb_to_recordset(COALESCE(p_voorraad, '[]'::jsonb))
      AS x(sku text, locatie text, qty integer)
  LOOP
    SELECT id INTO v_product FROM product  WHERE upper(sku)  = upper(v_r.sku);
    SELECT id INTO v_locatie FROM location WHERE upper(code) = upper(v_r.locatie);
    IF v_product IS NULL OR v_locatie IS NULL OR v_r.qty <= 0 THEN CONTINUE; END IF;

    PERFORM vakto_boek(v_product, v_r.qty, 'IMPORT', NULL, v_locatie,
                       'Beginvoorraad', 'IMPORT', p_gebruiker);
    v_voorraad := v_voorraad + 1;
  END LOOP;

  SELECT count(*) INTO v_zones   FROM zone;
  SELECT count(*) INTO v_groepen FROM product_group;

  PERFORM vakto_log('import',
    format('Ingelezen: %s locaties, %s artikelen, %s voorraadregels',
           v_locaties, v_artikelen, v_voorraad), 'INFO');

  RETURN jsonb_build_object(
    'locaties',  v_locaties,  'aangemaakt', v_extra,
    'artikelen', v_artikelen, 'metingen',   v_metingen,
    'voorraad',  v_voorraad,  'zones',      v_zones,
    'groepen',   v_groepen);
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_import IS
  'R-IMP-07. Neemt een gecontroleerd rapport over in één transactie. Weigert '
  'zodra er al een journaal staat: een import is een nulmeting.';

COMMIT;
