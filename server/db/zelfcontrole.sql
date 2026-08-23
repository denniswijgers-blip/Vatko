-- =====================================================================
--  VAKTO — zelfcontrole en optimalisatie (R-ZC, R-OPT)
--
--  Hier staat opvallend weinig, en dat is het punt.
--
--  Hoofdstuk 9 en 10 zijn bijna helemaal rekenwerk: uit de huidige
--  toestand afleiden welk werk er zou moeten liggen, welke meldingen niet
--  meer kloppen en welke taken overbodig zijn geworden. Dat is precies
--  wat R-BOEK-03 aan Python toewijst — passen, benutting, scoren,
--  optimaliseren. Het staat in vakto/zelfcontrole.py en
--  vakto/optimalisatie.py, en het is daar te testen zonder dat er een
--  database draait.
--
--  Wat overblijft voor de database is het wegschrijven, en één ding dat
--  écht hier hoort: een taak uitvoeren. Dat is een voorraadmutatie, dus
--  gaat het door vakto_boek() heen en nergens anders langs.
--
--    vakto_taak()             een taak klaarzetten
--    vakto_taak_bijwerken()   R-OPT-03: één taak, niet drie loopjes
--    vakto_taak_vervallen()   R-ZC-03: vervallen, niet verwijderen
--    vakto_taak_uitvoeren()   afmelden en boeken, in één transactie
--    vakto_tellen()           een telling met verschil
--    vakto_log()              wat het systeem zelf besloten heeft
--
--  Draaien:  psql -d vakto -f zelfcontrole.sql
-- =====================================================================

BEGIN;

DROP FUNCTION IF EXISTS vakto_taak(text,text,integer,integer,integer,integer,integer,text,text,boolean);
DROP FUNCTION IF EXISTS vakto_taak_bijwerken(bigint,integer,integer,text,text);
DROP FUNCTION IF EXISTS vakto_taak_vervallen(bigint,text);
DROP FUNCTION IF EXISTS vakto_taak_uitvoeren(bigint,integer,text);
DROP FUNCTION IF EXISTS vakto_tellen(integer,integer,integer,text);
DROP FUNCTION IF EXISTS vakto_tellen(integer,integer,integer,text,text,text);
DROP FUNCTION IF EXISTS vakto_log(text,text,text,text);
DROP FUNCTION IF EXISTS vakto_melding_bijwerken(bigint,text);


-- ---------------------------------------------------------------------
--  Het log. Eén functie, zodat een aanroeper de niveaus niet hoeft te
--  kennen en er nooit een losse INSERT langs de zijkant komt.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_log(
  p_bron    text,
  p_bericht text,
  p_niveau  text DEFAULT 'INFO',
  p_ref     text DEFAULT NULL
) RETURNS bigint AS $$
DECLARE v_id bigint;
BEGIN
  INSERT INTO event_log (niveau, bron, bericht, ref)
       VALUES (COALESCE(p_niveau, 'INFO'), p_bron, p_bericht, p_ref)
    RETURNING id INTO v_id;
  RETURN v_id;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  Een taak klaarzetten
--
--  Geeft het taaknummer terug, of NULL als er al een openstaande
--  aanvultaak voor dezelfde combinatie van artikel en doellocatie is.
--  Die uniciteit staat als index in het schema en niet als IF hier: dan
--  geldt hij ook voor wie de tabel rechtstreeks vult.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_taak(
  p_soort       text,
  p_naam        text,
  p_prio        integer,
  p_product     integer,
  p_van         integer,
  p_naar        integer,
  p_qty         integer,
  p_aanleiding  text    DEFAULT NULL,
  p_reden       text    DEFAULT '',
  p_automatisch boolean DEFAULT true
) RETURNS bigint AS $$
DECLARE v_id bigint;
BEGIN
  IF p_qty IS NULL OR p_qty <= 0 THEN
    RAISE EXCEPTION 'Een taak van % stuks bestaat niet', p_qty
      USING ERRCODE = 'check_violation';
  END IF;

  INSERT INTO task (soort, naam, prio, product_id, van, naar, qty,
                    aanleiding, reden, automatisch)
       VALUES (p_soort, p_naam, p_prio, p_product, p_van, p_naar, p_qty,
               p_aanleiding, COALESCE(p_reden, ''), p_automatisch)
  ON CONFLICT DO NOTHING
    RETURNING id INTO v_id;

  RETURN v_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_taak IS
  'Zet werk klaar. NULL betekent: er lag al een openstaande aanvultaak voor '
  'ditzelfde vak (R-OPT-03).';


-- ---------------------------------------------------------------------
--  R-OPT-03. Vragen twee aanleidingen om hetzelfde vak, dan wordt het
--  één taak: hoogste aantal, laagste prioriteitsnummer, reden van de
--  zwaarste aanleiding. Nooit drie loopjes voor dezelfde locatie.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_taak_bijwerken(
  p_taak       bigint,
  p_qty        integer,
  p_prio       integer,
  p_aanleiding text,
  p_reden      text
) RETURNS boolean AS $$
DECLARE v_raak integer;
BEGIN
  UPDATE task
     SET qty        = GREATEST(qty, p_qty),
         prio       = LEAST(prio, p_prio),
         aanleiding = p_aanleiding,
         reden      = COALESCE(p_reden, reden)
   WHERE id = p_taak AND status = 'TODO';
  GET DIAGNOSTICS v_raak = ROW_COUNT;
  RETURN v_raak > 0;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  R-ZC-03. Vervallen, niet verwijderen.
--
--  Een verwijderde taak is een gat in je verhaal: als iemand volgende
--  week vraagt waarom die aanvulling nooit gedaan is, wil je kunnen
--  laten zien dat het systeem hem heeft ingetrokken en waarom.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_taak_vervallen(
  p_taak  bigint,
  p_reden text
) RETURNS boolean AS $$
DECLARE
  v_raak integer;
  v_sku  text;
BEGIN
  UPDATE task
     SET status = 'VERVALLEN', vervallen_op = now(),
         vervallen_reden = COALESCE(p_reden, '')
   WHERE id = p_taak AND status = 'TODO';
  GET DIAGNOSTICS v_raak = ROW_COUNT;

  IF v_raak > 0 THEN
    SELECT p.sku INTO v_sku
      FROM task t JOIN product p ON p.id = t.product_id
     WHERE t.id = p_taak;
    PERFORM vakto_log('zelfcontrole',
                      format('%s: taak vervallen — %s', v_sku, p_reden));
  END IF;
  RETURN v_raak > 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_taak_vervallen IS
  'R-ZC-03. Status VERVALLEN met de reden erbij. Verwijderen mag niet.';


-- ---------------------------------------------------------------------
--  Een taak uitvoeren
--
--  Dit is de enige functie in dit bestand die voorraad aanraakt, en hij
--  doet dat via vakto_boek() — niet met een eigen UPDATE. Er is geen
--  tweede route, ook niet "even snel" voor een verplaatsing.
--
--  Tellen is geen verplaatsing: dat legt alleen vast dát er gekeken is.
--  Een telling mét verschil gaat door vakto_tellen().
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_taak_uitvoeren(
  p_taak      bigint,
  p_aantal    integer DEFAULT NULL,
  p_gebruiker text    DEFAULT NULL
) RETURNS bigint AS $$
DECLARE
  v_t        task%ROWTYPE;
  v_aantal   integer;
  v_journaal bigint := NULL;
  v_code     text;
BEGIN
  SELECT * INTO v_t FROM task WHERE id = p_taak FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Taak % bestaat niet', p_taak USING ERRCODE = 'no_data_found';
  END IF;
  IF v_t.status <> 'TODO' THEN
    RAISE EXCEPTION 'Taak % is al afgehandeld (%)', p_taak, v_t.status
      USING ERRCODE = 'check_violation';
  END IF;

  IF v_t.soort = 'CYCLE_COUNT' THEN
    SELECT code INTO v_code FROM location WHERE id = v_t.naar;
    UPDATE location SET geteld_op = now() WHERE id = v_t.naar;
    UPDATE task SET status = 'DONE' WHERE id = p_taak;
    PERFORM vakto_log('tellen',
                      format('%s geteld, geen verschil', v_code), 'INFO');
    RETURN NULL;
  END IF;

  IF v_t.van IS NULL OR v_t.naar IS NULL THEN
    RAISE EXCEPTION 'Taak % heeft geen bron of geen bestemming', p_taak
      USING ERRCODE = 'check_violation';
  END IF;

  v_aantal := COALESCE(p_aantal, v_t.qty);
  v_journaal := vakto_boek(v_t.product_id, v_aantal, 'MOVE',
                           v_t.van, v_t.naar, NULL,
                           format('Taak %s', p_taak), p_gebruiker);

  -- Deels afgemeld blijft openstaan: er ligt dan nog werk.
  IF v_aantal >= v_t.qty THEN
    UPDATE task SET status = 'DONE' WHERE id = p_taak;
  ELSE
    UPDATE task SET qty = qty - v_aantal WHERE id = p_taak;
  END IF;

  RETURN v_journaal;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_taak_uitvoeren IS
  'Meldt een taak af en boekt de verplaatsing via vakto_boek(). Tellen boekt '
  'niets: dat legt alleen vast dat er gekeken is.';


-- ---------------------------------------------------------------------
--  Een telling met verschil
--
--  Het geteld_op-stempel gaat altijd, ook als er niets verschilt. Juist
--  dat stempel laat R-ZC-03 een teltaak vervallen en R-OPT-04 de locatie
--  weer achteraan de rij zetten.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_tellen(
  p_locatie   integer,
  p_product   integer,
  p_geteld    integer,
  p_gebruiker text DEFAULT NULL,
  -- R-SCAN-05. Een verschil heet TELVERSCHIL; bij een nulmeting heet het
  -- NULMETING, want er was nog niets vastgelegd om van af te wijken.
  -- Wie dat door elkaar haalt, ziet de eerste dag van een nieuwe klant
  -- als een dag vol telfouten.
  p_reden     text DEFAULT 'TELVERSCHIL',
  p_ref       text DEFAULT 'Cyclustelling'
) RETURNS bigint AS $$
DECLARE
  v_aanwezig integer;
  v_verschil integer;
  v_code     text;
  v_sku      text;
  v_journaal bigint := NULL;
BEGIN
  IF p_geteld IS NULL OR p_geteld < 0 THEN
    RAISE EXCEPTION 'Een telling van % kan niet', p_geteld
      USING ERRCODE = 'check_violation';
  END IF;

  SELECT code INTO v_code FROM location WHERE id = p_locatie;
  SELECT sku  INTO v_sku  FROM product  WHERE id = p_product;
  IF v_code IS NULL OR v_sku IS NULL THEN
    RAISE EXCEPTION 'Onbekende locatie of artikel bij een telling'
      USING ERRCODE = 'no_data_found';
  END IF;

  SELECT qty INTO v_aanwezig FROM stock
   WHERE product_id = p_product AND location_id = p_locatie FOR UPDATE;
  v_aanwezig := COALESCE(v_aanwezig, 0);
  v_verschil := p_geteld - v_aanwezig;

  IF v_verschil > 0 THEN
    v_journaal := vakto_boek(p_product, v_verschil, 'COUNT', NULL, p_locatie,
                             p_reden, p_ref, p_gebruiker);
  ELSIF v_verschil < 0 THEN
    v_journaal := vakto_boek(p_product, -v_verschil, 'COUNT', p_locatie, NULL,
                             p_reden, p_ref, p_gebruiker);
  END IF;

  UPDATE location SET geteld_op = now() WHERE id = p_locatie;

  -- Openstaande teltaken voor dit vak zijn hiermee gedaan. Vervallen en
  -- niet DONE: het systeem sluit ze, niet de teller (R-BASIS-03).
  UPDATE task SET status = 'DONE'
   WHERE status = 'TODO' AND soort = 'CYCLE_COUNT' AND naar = p_locatie;

  PERFORM vakto_log('tellen',
    CASE WHEN v_verschil = 0
         THEN format('%s / %s geteld, geen verschil', v_code, v_sku)
         ELSE format('%s / %s geteld: %s in plaats van %s (%s%s)',
                     v_code, v_sku, p_geteld, v_aanwezig,
                     CASE WHEN v_verschil > 0 THEN '+' ELSE '' END, v_verschil)
    END,
    CASE WHEN v_verschil = 0 THEN 'INFO' ELSE 'WARN' END);

  RETURN v_journaal;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION vakto_tellen IS
  'R-OPT-04. Zet geteld_op, boekt het verschil als COUNT en sluit de teltaak.';


-- ---------------------------------------------------------------------
--  R-ZC-01. De melding klopt nog, maar de tekst niet meer.
--
--  Alleen de gevolg-tekst, niet de percentages: die horen bij de meting
--  waar de melding uit voortkwam en veranderen niet doordat er voorraad
--  verschoven is. En het tijdstip blijft ook staan, zodat je ziet hoe
--  lang dit al speelt.
-- ---------------------------------------------------------------------
CREATE FUNCTION vakto_melding_bijwerken(
  p_melding bigint,
  p_gevolg  text
) RETURNS boolean AS $$
DECLARE v_raak integer;
BEGIN
  UPDATE alert SET gevolg = COALESCE(p_gevolg, '')
   WHERE id = p_melding AND status = 'OPEN' AND gevolg IS DISTINCT FROM p_gevolg;
  GET DIAGNOSTICS v_raak = ROW_COUNT;
  RETURN v_raak > 0;
END;
$$ LANGUAGE plpgsql;


-- ---------------------------------------------------------------------
--  R-OPT-03, eerste aanleiding: wat vragen de openstaande orders?
--
--  Als view, zodat de rekenkern hem gewoon kan uitlezen en een scherm
--  erop kan filteren. Ingepakte en verzonden orders tellen niet mee: die
--  staan niet meer op de picklocatie te wachten.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_ordervraag AS
SELECT ol.product_id,
       SUM(ol.besteld - ol.gepickt) AS open_vraag
FROM   order_line     ol
JOIN   customer_order o ON o.id = ol.order_id
WHERE  o.status NOT IN ('INGEPAKT', 'VERZONDEN')
  AND  ol.besteld > ol.gepickt
GROUP  BY ol.product_id;

COMMENT ON VIEW v_ordervraag IS
  'R-OPT-03. Nog te picken stuks uit orders die nog op de vloer liggen.';


-- ---------------------------------------------------------------------
--  Wat er nu aan werk ligt. Een view zodat een scherm kan pagineren
--  (R-BASIS-07) en de rekenkern niet zelf hoeft te sorteren.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW v_werklijst AS
SELECT t.id, t.soort, t.naam, t.prio, t.status, t.product_id, p.sku, p.oms,
       t.van, lv.code AS van_code, t.naar, ln.code AS naar_code,
       t.qty, t.aanleiding, t.reden, t.automatisch, t.at
FROM   task t
JOIN   product  p  ON p.id = t.product_id
LEFT   JOIN location lv ON lv.id = t.van
LEFT   JOIN location ln ON ln.id = t.naar
WHERE  t.status = 'TODO'
ORDER  BY t.prio, ln.seq NULLS LAST, t.id;

COMMENT ON VIEW v_werklijst IS
  'Openstaand werk, op prioriteit en daarna op looproute (R-UIT-03).';

COMMIT;
