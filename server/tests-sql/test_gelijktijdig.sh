#!/bin/bash
# =====================================================================
#  De test die bewijst waarom SQLite niet volstaat (R-BOEK-02).
#
#  Twee mensen pakken tegelijk de laatste vijf stuks. Precies één van de
#  twee hoort te slagen. Zonder rijvergrendeling slagen ze allebei, en
#  dan staat er 's middags een order klaar die niet gepickt kan worden.
#
#  Draaien:  ./tests-sql/test_gelijktijdig.sh
#  Vereist:  een draaiende PostgreSQL met schema.sql en boeken.sql erin.
# =====================================================================
set -u
PSQL="${PSQL:-psql}"
DB="${PGDATABASE:-vakto}"
q() { $PSQL -d "$DB" -v ON_ERROR_STOP=1 -qtAX -c "$1" 2>&1; }

echo ""
echo "  Twee pickers, vijf stuks, allebei tegelijk"
echo "  ----------------------------------------------------------"

# ---- opzet (blijft staan tot het opruimen onderaan) -----------------
q "INSERT INTO zone (id,code,naam) VALUES (901,'GLT','Gelijktijdig')
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO location (id,code,zone_id,type_id,l_mm,w_mm,h_mm,max_g)
     VALUES (910,'G-01-1',901,0,300,400,220,12000) ON CONFLICT (id) DO NOTHING;
   INSERT INTO product_group (id,naam) VALUES (901,'Gelijktijdig')
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO product (id,sku,oms,group_id) VALUES (910,'GLT-1','Testartikel',901)
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO stock (product_id,location_id,qty) VALUES (910,910,5)
     ON CONFLICT (product_id,location_id) DO UPDATE SET qty=5,res=0;" >/dev/null

# ---- picker A: begint, houdt de rij twee seconden vast --------------
( $PSQL -d "$DB" -qtAX >/tmp/vakto_a.txt 2>&1 <<SQL
BEGIN;
SELECT 'A: ' || vakto_boek(910, 5, 'PICK', 910, NULL, NULL, 'ORD-A');
SELECT pg_sleep(2);
COMMIT;
SQL
) &
PID_A=$!

sleep 0.5

# ---- picker B: wil dezelfde vijf ------------------------------------
( $PSQL -d "$DB" -qtAX >/tmp/vakto_b.txt 2>&1 <<SQL
BEGIN;
SELECT 'B: ' || vakto_boek(910, 5, 'PICK', 910, NULL, NULL, 'ORD-B');
COMMIT;
SQL
) &
PID_B=$!

wait $PID_A $PID_B

A=$(grep -c '^A: ' /tmp/vakto_a.txt || true)
B=$(grep -c '^B: ' /tmp/vakto_b.txt || true)
FOUT=$(grep -ci 'onvoldoende voorraad' /tmp/vakto_a.txt /tmp/vakto_b.txt | \
       awk -F: '{s+=$2} END {print s}')
REST=$(q "SELECT qty FROM stock WHERE product_id=910 AND location_id=910;")
REGELS=$(q "SELECT count(*) FROM journal WHERE product_id=910;")

echo "  A geslaagd:              $A"
echo "  B geslaagd:              $B"
echo "  foutmeldingen:           $FOUT"
echo "  voorraad na afloop:      $REST   (hoort 0 te zijn)"
echo "  journaalregels:          $REGELS   (hoort 1 te zijn)"
echo ""

# ---- opruimen --------------------------------------------------------
q "DELETE FROM journal WHERE product_id=910;
   DELETE FROM stock   WHERE product_id=910;
   DELETE FROM product WHERE id=910;
   DELETE FROM product_group WHERE id=901;
   DELETE FROM location WHERE id=910;
   DELETE FROM zone WHERE id=901;" >/dev/null 2>&1

if [ "$(( A + B ))" = "1" ] && [ "$FOUT" = "1" ] && [ "$REST" = "0" ] && [ "$REGELS" = "1" ]; then
  echo "  OK — precies één picker kreeg de vijf stuks."
  echo "       Dit is wat SQLite niet kan en waarom er PostgreSQL onder moet."
  exit 0
fi
echo "  GEZAKT — allebei geslaagd of allebei mislukt. Kijk naar de"
echo "           rijvergrendeling in vakto_boek (R-BOEK-02)."
echo "  --- A ---"; cat /tmp/vakto_a.txt
echo "  --- B ---"; cat /tmp/vakto_b.txt
exit 1
