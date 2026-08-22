-- =====================================================================
--  VAKTO — schema voor PostgreSQL
--  Hoort bij de specificatie "De rekenkern, uitgeschreven", hoofdstuk 2.
--
--  Regels die hier in het schema zijn afgedwongen in plaats van in de
--  code, omdat een database beter onthoudt dan een programmeur:
--
--    R-BASIS-01  journaal is append-only (trigger)
--    R-BASIS-02  afgeleide waarden zijn views, geen kolommen
--    R-BASIS-04  gedrag staat in tabellen: location_type, size_class_rule,
--                weging en setting
--    R-UIT-01    res kan nooit groter zijn dan qty (CHECK)
--
--  Draaien:  psql -d vakto -f schema.sql
-- =====================================================================

BEGIN;

DROP VIEW  IF EXISTS v_available, v_location_load, v_location_size, v_product_current CASCADE;
DROP TABLE IF EXISTS allocation, order_line, customer_order, alert, task,
                     event_log, journal, stock, measurement, product,
                     product_group, location, zone, location_type,
                     size_class_rule, weging, setting CASCADE;

-- ---------------------------------------------------------------- config
CREATE TABLE setting (
  sleutel   text PRIMARY KEY,
  waarde    text        NOT NULL,
  groep     text        NOT NULL DEFAULT 'Overig',
  uitleg    text        NOT NULL DEFAULT ''
);
COMMENT ON TABLE setting IS
  'R-BASIS-04. Alles wat per klant verschilt. Waarde altijd als tekst; bij lezen omzetten.';

CREATE TABLE weging (
  sleutel   text PRIMARY KEY,
  punten    integer     NOT NULL,
  uitleg    text        NOT NULL DEFAULT ''
);
COMMENT ON TABLE weging IS 'R-INS-04. De punten van het inslagvoorstel.';

CREATE TABLE size_class_rule (
  code      text PRIMARY KEY,
  naam      text        NOT NULL,
  min_cm3   numeric     NOT NULL,
  max_cm3   numeric     NOT NULL,
  volgorde  integer     NOT NULL,
  CHECK (min_cm3 < max_cm3)
);
COMMENT ON TABLE size_class_rule IS 'R-AFG-02. Grenzen zijn min <= cm3 < max.';

CREATE TABLE location_type (
  id        smallint PRIMARY KEY,
  code      text UNIQUE NOT NULL,
  naam      text        NOT NULL,
  pick      boolean     NOT NULL DEFAULT false,
  bulk      boolean     NOT NULL DEFAULT false,
  mix       boolean     NOT NULL DEFAULT false,
  blok      boolean     NOT NULL DEFAULT false,
  doel      boolean     NOT NULL DEFAULT false
);
COMMENT ON COLUMN location_type.doel IS 'false = komt nooit in een inslagvoorstel (R-INS-01)';
COMMENT ON COLUMN location_type.blok IS 'true  = telt niet mee als beschikbaar (R-AFG-03)';
COMMENT ON COLUMN location_type.mix  IS 'false = één artikelsoort per vak (R-INS-02)';

-- ------------------------------------------------------------- magazijn
CREATE TABLE zone (
  id        serial PRIMARY KEY,
  code      text UNIQUE NOT NULL,
  naam      text        NOT NULL
);

CREATE TABLE location (
  id          serial PRIMARY KEY,
  code        text UNIQUE NOT NULL,
  zone_id     integer  NOT NULL REFERENCES zone(id),
  type_id     smallint NOT NULL REFERENCES location_type(id),
  aisle       integer  NOT NULL DEFAULT 0,
  bay         integer  NOT NULL DEFAULT 0,
  level       integer  NOT NULL DEFAULT 0,
  seq         bigint   NOT NULL DEFAULT 0,
  l_mm        integer  NOT NULL CHECK (l_mm  > 0),
  w_mm        integer  NOT NULL CHECK (w_mm  > 0),
  h_mm        integer  NOT NULL CHECK (h_mm  > 0),
  max_g       bigint   NOT NULL CHECK (max_g > 0),
  actief      boolean  NOT NULL DEFAULT true,
  geteld_op   timestamptz
);
COMMENT ON COLUMN location.seq IS
  'R-UIT-03. gang*1000000 + vakpositie*100 + niveau*10, slangroute in even gangen.';
COMMENT ON COLUMN location.l_mm IS 'Binnenmaat, niet buitenmaat.';
CREATE INDEX location_seq_idx ON location(seq);
CREATE INDEX location_type_idx ON location(type_id) WHERE actief;

-- ------------------------------------------------------------- artikelen
CREATE TABLE product_group (
  id          serial PRIMARY KEY,
  naam        text UNIQUE NOT NULL,
  telinterval integer NOT NULL DEFAULT 180 CHECK (telinterval > 0)
);
COMMENT ON COLUMN product_group.telinterval IS 'R-OPT-04, in dagen.';

CREATE TABLE product (
  id          serial PRIMARY KEY,
  sku         text UNIQUE NOT NULL,
  oms         text     NOT NULL DEFAULT '',
  group_id    integer  NOT NULL REFERENCES product_group(id),
  min_qty     integer  CHECK (min_qty IS NULL OR min_qty > 0),
  max_qty     integer  CHECK (max_qty IS NULL OR max_qty > 0),
  stapelbaar  boolean  NOT NULL DEFAULT true,
  barcode     text,
  drempel_akkoord boolean NOT NULL DEFAULT false,
  CHECK (max_qty IS NULL OR min_qty IS NULL OR max_qty >= min_qty)
);
COMMENT ON TABLE product IS
  'Géén afmetingen. Die zijn een tijdlijn en staan in measurement (R-AFG-01).';
CREATE INDEX product_barcode_idx ON product(barcode) WHERE barcode IS NOT NULL;

CREATE TABLE measurement (
  id          bigserial PRIMARY KEY,
  product_id  integer     NOT NULL REFERENCES product(id),
  at          timestamptz NOT NULL DEFAULT now(),
  bron        text        NOT NULL CHECK (bron IN ('SUPPLIER','RECEIPT','PACKING','CONTROL')),
  l_mm        integer     NOT NULL CHECK (l_mm > 0),
  w_mm        integer     NOT NULL CHECK (w_mm > 0),
  h_mm        integer     NOT NULL CHECK (h_mm > 0),
  g           integer     NOT NULL CHECK (g    > 0),
  notitie     text
);
COMMENT ON TABLE measurement IS 'Append-only. Nooit een rij bijwerken (R-MEET-01).';
CREATE INDEX measurement_actueel_idx ON measurement(product_id, at DESC);

-- --------------------------------------------------------------- voorraad
CREATE TABLE stock (
  product_id  integer NOT NULL REFERENCES product(id),
  location_id integer NOT NULL REFERENCES location(id),
  qty         integer NOT NULL DEFAULT 0 CHECK (qty >= 0),
  res         integer NOT NULL DEFAULT 0 CHECK (res >= 0),
  PRIMARY KEY (product_id, location_id),
  CONSTRAINT res_niet_meer_dan_qty CHECK (res <= qty)
);
COMMENT ON CONSTRAINT res_niet_meer_dan_qty ON stock IS
  'R-UIT-01. Dubbel verkopen wordt hier tegengehouden, niet in de code.';
CREATE INDEX stock_locatie_idx ON stock(location_id) WHERE qty > 0;

CREATE TABLE journal (
  id          bigserial PRIMARY KEY,
  at          timestamptz NOT NULL DEFAULT now(),
  soort       text        NOT NULL CHECK (soort IN
                ('RECEIPT','PUTAWAY','PICK','MOVE','ADJUST','COUNT','IMPORT')),
  product_id  integer     NOT NULL REFERENCES product(id),
  van         integer     REFERENCES location(id),
  naar        integer     REFERENCES location(id),
  qty         integer     NOT NULL CHECK (qty > 0),
  reden       text,
  ref         text,
  gebruiker   text,
  CONSTRAINT van_of_naar CHECK (van IS NOT NULL OR naar IS NOT NULL)
);
COMMENT ON TABLE journal IS
  'R-BASIS-01. Append-only bewijsstuk. Elke voorraadwijziging heeft hier een regel.';
CREATE INDEX journal_product_idx ON journal(product_id, at DESC);
CREATE INDEX journal_soort_idx   ON journal(soort, at DESC);

-- Append-only afdwingen. Een journaal dat je kunt bijwerken is geen journaal.
CREATE OR REPLACE FUNCTION alleen_toevoegen() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% is append-only: %  mag niet (R-BASIS-01)', TG_TABLE_NAME, TG_OP;
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER journal_append_only     BEFORE UPDATE OR DELETE ON journal
  FOR EACH ROW EXECUTE FUNCTION alleen_toevoegen();
CREATE TRIGGER measurement_append_only BEFORE UPDATE OR DELETE ON measurement
  FOR EACH ROW EXECUTE FUNCTION alleen_toevoegen();

-- ------------------------------------------------------------------ werk
CREATE TABLE task (
  id          bigserial PRIMARY KEY,
  soort       text        NOT NULL CHECK (soort IN
                ('REPLENISH','OVERLOOP','SAMENVOEG','CYCLE_COUNT','PICKPLEK','MOVE')),
  naam        text        NOT NULL,
  prio        integer     NOT NULL DEFAULT 50,
  status      text        NOT NULL DEFAULT 'TODO'
                CHECK (status IN ('TODO','DONE','VERVALLEN')),
  product_id  integer     NOT NULL REFERENCES product(id),
  van         integer     REFERENCES location(id),
  naar        integer     REFERENCES location(id),
  qty         integer     NOT NULL CHECK (qty > 0),
  aanleiding  text,
  reden       text        NOT NULL DEFAULT '',
  automatisch boolean     NOT NULL DEFAULT true,
  at          timestamptz NOT NULL DEFAULT now(),
  vervallen_op     timestamptz,
  vervallen_reden  text
);
COMMENT ON TABLE task IS
  'Eén tabel voor alle soorten werk. Vervallen taken blijven staan (R-ZC-03).';
CREATE INDEX task_open_idx ON task(status, prio) WHERE status = 'TODO';
CREATE UNIQUE INDEX task_geen_dubbele_aanvul ON task(product_id, naar)
  WHERE status = 'TODO' AND soort = 'REPLENISH';

CREATE TABLE alert (
  id          bigserial PRIMARY KEY,
  product_id  integer     NOT NULL REFERENCES product(id),
  at          timestamptz NOT NULL DEFAULT now(),
  d_vol       numeric(6,1) NOT NULL,
  d_gew       numeric(6,1) NOT NULL,
  status      text        NOT NULL DEFAULT 'OPEN'
                CHECK (status IN ('OPEN','OPGELOST','DISMISSED')),
  gevolg      text        NOT NULL DEFAULT '',
  opgelost_op timestamptz
);
COMMENT ON TABLE alert IS
  'R-ZC-01. OPGELOST zet het systeem zelf; DISMISSED is de enige menselijke keuze.';
CREATE INDEX alert_open_idx ON alert(product_id) WHERE status = 'OPEN';

-- ------------------------------------------------------------- uitgaand
CREATE TABLE customer_order (
  id          bigserial PRIMARY KEY,
  nummer      text UNIQUE NOT NULL,
  klant       text        NOT NULL,
  plaats      text,
  land        text,
  vervoerder  text,
  soort       text,
  prio        integer     NOT NULL DEFAULT 3,
  status      text        NOT NULL DEFAULT 'NIEUW' CHECK (status IN
                ('NIEUW','GERESERVEERD','WACHT_OP_VOORRAAD','VRIJGEGEVEN',
                 'PICKEN','GEPICKT','INGEPAKT','VERZONDEN')),
  at          timestamptz NOT NULL DEFAULT now(),
  colli       integer, gewicht_g bigint, track text
);
CREATE INDEX co_open_idx ON customer_order(status) WHERE status <> 'VERZONDEN';

CREATE TABLE order_line (
  order_id      bigint  NOT NULL REFERENCES customer_order(id) ON DELETE CASCADE,
  idx           integer NOT NULL,
  product_id    integer NOT NULL REFERENCES product(id),
  besteld       integer NOT NULL CHECK (besteld > 0),
  gereserveerd  integer NOT NULL DEFAULT 0 CHECK (gereserveerd >= 0),
  gepickt       integer NOT NULL DEFAULT 0 CHECK (gepickt >= 0),
  manco         integer NOT NULL DEFAULT 0 CHECK (manco >= 0),
  PRIMARY KEY (order_id, idx)
);

CREATE TABLE allocation (
  id          bigserial PRIMARY KEY,
  order_id    bigint  NOT NULL REFERENCES customer_order(id) ON DELETE CASCADE,
  regel       integer NOT NULL,
  product_id  integer NOT NULL REFERENCES product(id),
  location_id integer NOT NULL REFERENCES location(id),
  qty         integer NOT NULL CHECK (qty > 0),
  gepickt     integer NOT NULL DEFAULT 0 CHECK (gepickt >= 0),
  -- R-UIT-06. De allocation-rij is ook de pickregel. Een aparte tabel met
  -- pickregels zou dezelfde gegevens nog een keer opschrijven, en dan lopen
  -- ze uit elkaar zodra iemand er een van bijwerkt.
  status      text    NOT NULL DEFAULT 'TODO'
                CHECK (status IN ('TODO','DONE','MANCO')),
  CHECK (gepickt <= qty)
);
COMMENT ON TABLE allocation IS
  'R-UIT-01. Welke voorraad op welke locatie voor welke order bestemd is.';
CREATE INDEX allocation_order_idx ON allocation(order_id);
CREATE INDEX allocation_open_idx  ON allocation(product_id) WHERE status = 'TODO';

-- ------------------------------------------------------------ systeemlog
-- Waar het systeem opschrijft wat het zelf besloten heeft. Niet de plek
-- voor foutmeldingen van de webserver: alleen beslissingen waarvan een
-- mens later moet kunnen navragen waarom ze genomen zijn.
CREATE TABLE event_log (
  id      bigserial   PRIMARY KEY,
  at      timestamptz NOT NULL DEFAULT now(),
  niveau  text        NOT NULL DEFAULT 'INFO'
            CHECK (niveau IN ('INFO','WARN','FOUT')),
  bron    text        NOT NULL,
  bericht text        NOT NULL,
  ref     text
);
COMMENT ON TABLE event_log IS
  'Append-only. R-UIT-02 (tekort bij reserveren), R-ZC-01 (melding sluit vanzelf).';
CREATE INDEX event_log_at_idx ON event_log(at DESC);

CREATE TRIGGER event_log_append_only BEFORE UPDATE OR DELETE ON event_log
  FOR EACH ROW EXECUTE FUNCTION alleen_toevoegen();

-- =====================================================================
--  VIEWS — hoofdstuk 3. Afgeleide waarden worden nooit opgeslagen.
-- =====================================================================

-- R-AFG-01  actuele artikelmaat = de nieuwste meting
CREATE VIEW v_product_current AS
SELECT DISTINCT ON (m.product_id)
       m.product_id, m.at AS gemeten_op, m.bron, m.l_mm, m.w_mm, m.h_mm, m.g
FROM   measurement m
ORDER  BY m.product_id, m.at DESC, m.id DESC;

-- R-AFG-02  maatklasse van een locatie, berekend uit het volume
CREATE VIEW v_location_size AS
SELECT l.id AS location_id,
       l.code,
       (l.l_mm::numeric * l.w_mm * l.h_mm) / 1000 AS cm3,
       (SELECT r.code FROM size_class_rule r
         WHERE (l.l_mm::numeric * l.w_mm * l.h_mm) / 1000 >= r.min_cm3
           AND (l.l_mm::numeric * l.w_mm * l.h_mm) / 1000 <  r.max_cm3
         ORDER BY r.volgorde LIMIT 1) AS maatklasse
FROM   location l;

-- R-AFG-04  bezetting van een locatie in volume en gewicht
--           Artikelen zonder maat tellen niet mee: liever onderschatten
--           dan een verzonnen getal gebruiken.
CREATE VIEW v_location_load AS
SELECT s.location_id,
       COALESCE(SUM(s.qty::numeric * c.l_mm * c.w_mm * c.h_mm), 0) AS bezet_vol_mm3,
       COALESCE(SUM(s.qty::numeric * c.g), 0)                      AS bezet_gew_g,
       COUNT(DISTINCT s.product_id)                                AS soorten
FROM   stock s
LEFT   JOIN v_product_current c ON c.product_id = s.product_id
WHERE  s.qty > 0
GROUP  BY s.location_id;

-- R-AFG-03  beschikbare voorraad per artikel
CREATE VIEW v_available AS
SELECT s.product_id,
       SUM(s.qty)                    AS aanwezig,
       SUM(s.res)                    AS gereserveerd,
       SUM(s.qty - s.res) FILTER (WHERE NOT t.blok) AS beschikbaar
FROM   stock s
JOIN   location      l ON l.id = s.location_id
JOIN   location_type t ON t.id = l.type_id
WHERE  s.qty > 0
GROUP  BY s.product_id;

COMMIT;
