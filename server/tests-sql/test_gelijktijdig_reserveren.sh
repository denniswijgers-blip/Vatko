#!/bin/bash
# =====================================================================
#  T-14 onder gelijktijdigheid (R-UIT-01, R-UIT-02).
#
#  De variant uit hoofdstuk 12 doet twee orders na elkaar. Dat bewijst
#  dat het rekenwerk klopt, maar niet dat het veilig is: de vraag is wat
#  er gebeurt als twee verkopers op hetzelfde moment op "reserveren"
#  drukken voor de laatste tien stuks.
#
#  Zonder rijvergrendeling reserveren ze allebei tien en staat er res=20
#  op een rij met qty=10 — twee klanten die dezelfde doos gekocht hebben.
#  Met vergrendeling wacht de tweede tot de eerste klaar is, ziet dan dat
#  er niets meer vrij is, en krijgt netjes WACHT_OP_VOORRAAD.
#
#  Draaien:  ./tests-sql/test_gelijktijdig_reserveren.sh
#  Vereist:  een draaiende PostgreSQL met schema.sql, boeken.sql en
#            uitgaand.sql erin.
# =====================================================================
set -u
PSQL="${PSQL:-psql}"
DB="${PGDATABASE:-vakto}"
q() { $PSQL -d "$DB" -v ON_ERROR_STOP=1 -qtAX -c "$1" 2>&1; }

echo ""
echo "  Twee verkopers, tien stuks, allebei tegelijk"
echo "  ----------------------------------------------------------"

# ---- opzet -----------------------------------------------------------
q "INSERT INTO zone (id,code,naam) VALUES (902,'GLR','Gelijktijdig res')
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO location (id,code,zone_id,type_id,l_mm,w_mm,h_mm,max_g,seq)
     VALUES (920,'R-01-1',902,0,300,400,220,12000,1000110)
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO product_group (id,naam) VALUES (902,'Gelijktijdig res')
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO product (id,sku,oms,group_id) VALUES (920,'GLR-1','Testartikel',902)
     ON CONFLICT (id) DO NOTHING;
   INSERT INTO stock (product_id,location_id,qty) VALUES (920,920,10)
     ON CONFLICT (product_id,location_id) DO UPDATE SET qty=10,res=0;
   DELETE FROM allocation WHERE order_id IN (920,921);
   DELETE FROM order_line WHERE order_id IN (920,921);
   DELETE FROM customer_order WHERE id IN (920,921);
   INSERT INTO customer_order (id,nummer,klant) VALUES
     (920,'ORD-R-A','Klant A'), (921,'ORD-R-B','Klant B');
   INSERT INTO order_line (order_id,idx,product_id,besteld) VALUES
     (920,0,920,10), (921,0,920,10);" >/dev/null

# ---- verkoper A: reserveert en houdt de rij twee seconden vast -------
( $PSQL -d "$DB" -qtAX >/tmp/vakto_ra.txt 2>&1 <<SQL
BEGIN;
SELECT 'A: ' || vakto_reserveer(920);
SELECT pg_sleep(2);
COMMIT;
SQL
) &
PID_A=$!

sleep 0.5

# ---- verkoper B: wil dezelfde tien ----------------------------------
( $PSQL -d "$DB" -qtAX >/tmp/vakto_rb.txt 2>&1 <<SQL
BEGIN;
SELECT 'B: ' || vakto_reserveer(921);
COMMIT;
SQL
) &
PID_B=$!

wait $PID_A $PID_B

A=$(grep -c '^A: GERESERVEERD' /tmp/vakto_ra.txt || true)
B=$(grep -c '^B: GERESERVEERD' /tmp/vakto_rb.txt || true)
WACHT=$(grep -ch 'WACHT_OP_VOORRAAD' /tmp/vakto_ra.txt /tmp/vakto_rb.txt | \
        awk '{s+=$1} END {print s+0}')
RES=$(q "SELECT res FROM stock WHERE product_id=920 AND location_id=920;")
SCHEEF=$(q "SELECT count(*) FROM stock WHERE res > qty;")
ALLOC=$(q "SELECT coalesce(sum(qty),0) FROM allocation WHERE product_id=920;")

echo "  A gereserveerd:          $A"
echo "  B gereserveerd:          $B"
echo "  wacht op voorraad:       $WACHT"
echo "  res na afloop:           $RES   (hoort 10 te zijn)"
echo "  rijen met res > qty:     $SCHEEF   (hoort 0 te zijn)"
echo "  samen gereserveerd:      $ALLOC   (hoort 10 te zijn)"
echo ""

# ---- opruimen --------------------------------------------------------
q "DELETE FROM allocation WHERE product_id=920;
   DELETE FROM order_line WHERE order_id IN (920,921);
   DELETE FROM customer_order WHERE id IN (920,921);
   DELETE FROM stock   WHERE product_id=920;
   DELETE FROM product WHERE id=920;
   DELETE FROM product_group WHERE id=902;
   DELETE FROM location WHERE id=920;
   DELETE FROM zone WHERE id=902;" >/dev/null 2>&1

if [ "$(( A + B ))" = "1" ] && [ "$WACHT" = "1" ] && [ "$RES" = "10" ] \
   && [ "$SCHEEF" = "0" ] && [ "$ALLOC" = "10" ]; then
  echo "  OK — precies één verkoper kreeg de tien stuks."
  echo "       De ander wacht op voorraad in plaats van hem dubbel te verkopen."
  exit 0
fi
echo "  GEZAKT — allebei gereserveerd, of samen meer dan er ligt. Kijk"
echo "           naar de vergrendeling in vakto_reserveer (R-BOEK-02)."
echo "  --- A ---"; cat /tmp/vakto_ra.txt
echo "  --- B ---"; cat /tmp/vakto_rb.txt
exit 1
