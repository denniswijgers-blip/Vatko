-- =====================================================================
--  VAKTO — de configuratietabellen vullen
--  Dit is geen demodata: dit zijn de regels waarmee het systeem rekent.
--  Per klant pas je waarden aan, niet de code (R-BASIS-04).
--
--  Draaien:  psql -d vakto -f seed_config.sql
-- =====================================================================
BEGIN;

-- Soorten locatie — gedrag als vlaggen, niet als if in de code
INSERT INTO location_type (id, code, naam, pick, bulk, mix, blok, doel) VALUES
  (0,'PL', 'Picklocatie',   true,  false, false, false, true ),
  (1,'BL', 'Bulklocatie',   false, true,  false, false, true ),
  (2,'INC','Ontvangst',     false, false, true,  false, false),
  (3,'QC', 'Keuring',       false, false, true,  true,  false),
  (4,'DM', 'Schade',        false, false, true,  true,  false),
  (5,'EXP','Verzendgereed', false, false, true,  true,  false);

-- Maatklassen (R-AFG-02). Grenzen in cm3: min <= cm3 < max.
INSERT INTO size_class_rule (code, naam, min_cm3, max_cm3, volgorde) VALUES
  ('XS','Bak',                 0,      8000, 1),
  ('S', 'Klein vak',        8000,     50000, 2),
  ('M', 'Middelvak',       50000,    200000, 3),
  ('L', 'Groot vak',      200000,    900000, 4),
  ('XL','Palletplaats',   900000,  99000000, 5);

-- Wegingen van het inslagvoorstel (R-INS-04).
-- te_ruim_straf moet zwaarder wegen dan zelfde_artikel + hele_partij_past
-- bij elkaar, anders wint een half lege palletplaats het alsnog.
INSERT INTO weging (sleutel, punten, uitleg) VALUES
  ('benutting',           500, 'Vermenigvuldigd met de benutting, gemaximeerd op 1.'),
  ('zelfde_artikel',      400, 'Vermenigvuldigd met min(1, vrij/gevraagd).'),
  ('picklocatie_aanvul',  600, 'Vast bedrag als de picklocatie onder de drempel zit.'),
  ('hele_partij_past',    200, 'Vast bedrag als alles in één keer past.'),
  ('deelvulling_max',     150, 'Vermenigvuldigd met vrij/gevraagd.'),
  ('te_ruim_straf',      -550, 'Vermenigvuldigd met (1 - benutting/0,20). Alleen onder 20%.');

-- Instellingen (hoofdstuk 11)
INSERT INTO setting (sleutel, waarde, groep, uitleg) VALUES
  ('putaway.fill_factor','0.85','Inslag',
   'Je krijgt een schap nooit 100% vol. Verlagen bij onregelmatige verpakkingen.'),
  ('putaway.prefer_smallest_fit','true','Inslag',
   'Zet de strafterm voor veel te ruime locaties aan.'),
  ('putaway.te_ruim_onder','0.20','Inslag',
   'Onder welke benutting de strafterm gaat gelden.'),
  ('drift.alert_threshold_pct','15','Artikelbeheer',
   'Bij hoeveel procent verschil tussen twee metingen slaat het systeem alarm.'),
  ('drift.remeasure_after_days','180','Artikelbeheer',
   'Na hoeveel dagen een artikel opnieuw op de meetlijst komt.'),
  ('opt.samenvoegen','true','Optimalisatie',
   'Samenvoegtaken automatisch aanmaken.'),
  ('opt.dekking_dagen','3','Optimalisatie',
   'Hoeveel dagen verbruik er minimaal op een picklocatie moet liggen.'),
  ('opt.hardloper_per_dag','6','Optimalisatie',
   'Vanaf hoeveel stuks per dag geldt een artikel als hardloper. Stem af op het echte volume.'),
  ('opt.venster_dagen','30','Optimalisatie',
   'Over hoeveel dagen de vraagsnelheid wordt gemeten.'),
  ('opt.max_open_teltaken','12','Optimalisatie',
   'Plafond op openstaande teltaken uit het telplan.'),
  ('opt.drempel_afwijking_pct','60','Optimalisatie',
   'Vanaf welk verschil er advies over de aanvuldrempel komt.'),
  ('opstart.onbekend_aanmaken','false','Opstarten',
   'Alleen tijdens een nulmeting: onbekende gescande code wordt een nieuw artikel.'),
  ('ui.rows_per_page','60','Weergave',
   'Maximaal aantal rijen per scherm. Nooit onbeperkt.');

COMMIT;
