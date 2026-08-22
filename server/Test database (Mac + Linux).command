#!/bin/bash
# Draait de tests die een echte PostgreSQL nodig hebben.
cd "$(dirname "$0")" || exit 1
DB="${PGDATABASE:-vakto}"
echo ""
echo "  =========================================="
echo "     VAKTO  -  tests tegen de database"
echo "  =========================================="
echo ""
if ! command -v psql >/dev/null 2>&1; then
  echo "  psql is niet gevonden. Installeer PostgreSQL — zie LEESMIJ.md."
  echo ""; read -r -p "  Druk op enter om te sluiten." _; exit 1
fi
if ! psql -d "$DB" -c "SELECT 1" >/dev/null 2>&1; then
  echo "  Kan geen verbinding maken met database '$DB'."
  echo "  Zet hem op:   createdb $DB"
  echo "                psql -d $DB -f schema.sql"
  echo "                psql -d $DB -f seed_config.sql"
  echo "                psql -d $DB -f boeken.sql"
  echo "                psql -d $DB -f meten.sql"
  echo ""; read -r -p "  Druk op enter om te sluiten." _; exit 1
fi
echo "  1. Boeken, checks, triggers en views"
psql -d "$DB" -v ON_ERROR_STOP=1 -f tests-sql/test_boeken.sql 2>&1 | grep -E "OK|GEZAKT|geslaagd|ERROR"
psql -d "$DB" -v ON_ERROR_STOP=1 -f tests-sql/test_meten.sql  2>&1 | grep -E "OK|GEZAKT|geslaagd|ERROR"
echo ""
echo "  2. Twee pickers tegelijk"
./tests-sql/test_gelijktijdig.sh
echo ""
echo "  3. Elke query van de vertaallaag langs het schema"
python3 -m unittest tests.test_opslag -v 2>&1 | tail -5
echo ""
read -r -p "  Druk op enter om te sluiten." _
