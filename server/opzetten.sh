#!/bin/bash
# =====================================================================
#  VAKTO — database opzetten en alles testen
#
#  Eén bestand dat het hele karwei doet: PostgreSQL opzoeken, de
#  database aanmaken, het schema erin zetten en alle tests draaien.
#
#  Mac / Linux:  bash opzetten.sh
#  Of dubbelklik "Zet database op (Mac).command"
# =====================================================================
set -u
cd "$(dirname "$0")" || exit 1

DB="${PGDATABASE:-vakto}"
groen=$'\033[32m'; rood=$'\033[31m'; geel=$'\033[33m'; dik=$'\033[1m'; uit=$'\033[0m'

kop()  { printf '\n%s%s%s\n' "$dik" "$1" "$uit"; printf '  %s\n' "------------------------------------------------------------"; }
ok()   { printf '  %s✓%s %s\n' "$groen" "$uit" "$1"; }
fout() { printf '  %s✗%s %s\n' "$rood" "$uit" "$1"; }
let_() { printf '  %s!%s %s\n' "$geel" "$uit" "$1"; }
stop() { printf '\n%s%s%s\n\n' "$rood" "$1" "$uit"; exit 1; }

printf '\n%s  VAKTO — database opzetten%s\n' "$dik" "$uit"

# ---------------------------------------------------------------- psql
kop "1. PostgreSQL zoeken"
PSQL="$(command -v psql 2>/dev/null || true)"
if [ -z "$PSQL" ]; then
  for kandidaat in \
      /Applications/Postgres.app/Contents/Versions/*/bin/psql \
      /Library/PostgreSQL/*/bin/psql \
      /opt/homebrew/bin/psql /usr/local/bin/psql \
      /opt/homebrew/opt/postgresql*/bin/psql /usr/local/opt/postgresql*/bin/psql; do
    [ -x "$kandidaat" ] && { PSQL="$kandidaat"; break; }
  done
fi
[ -z "$PSQL" ] && stop "PostgreSQL niet gevonden.
  Op een Mac is Postgres.app het makkelijkst: https://postgresapp.com
  Sleep hem naar Programma's, start hem, en klik op Initialize.
  Draai daarna dit bestand opnieuw."
ok "gevonden: $PSQL"
BIN="$(dirname "$PSQL")"
ok "$("$PSQL" --version)"

# ------------------------------------------------------------ verbinden
kop "2. Verbinding maken"
GEBRUIKER=""
for u in "$(id -un)" postgres vakto; do
  if "$PSQL" -U "$u" -d postgres -qtAX -c "SELECT 1" >/dev/null 2>&1; then
    GEBRUIKER="$u"; break
  fi
done
[ -z "$GEBRUIKER" ] && stop "Kan geen verbinding maken met PostgreSQL.
  Draait de server? Bij Postgres.app zie je een olifantje in de menubalk;
  staat daar 'Not running', klik dan op Start.
  Bij de installer van EDB heb je een wachtwoord opgegeven; probeer dan:
      PGPASSWORD=jouwwachtwoord bash opzetten.sh"
ok "ingelogd als gebruiker '$GEBRUIKER'"
P() { "$PSQL" -U "$GEBRUIKER" "$@"; }

# -------------------------------------------------------------- database
kop "3. Database '$DB'"
if P -d postgres -qtAX -c "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1; then
  AANTAL=$(P -d "$DB" -qtAX -c \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>/dev/null || echo 0)
  if [ "${AANTAL:-0}" -gt 0 ]; then
    let_ "database bestaat al met $AANTAL tabellen"
    let_ "het schema wordt opnieuw opgezet — ALLE gegevens erin gaan weg"
    if [ -t 0 ]; then
      printf '\n  Doorgaan? (j/n) '
      read -r antwoord
      case "$antwoord" in [jJyY]*) ;; *) printf '\n  Afgebroken, er is niets gewijzigd.\n\n'; exit 0;; esac
    else
      let_ "geen toetsenbord beschikbaar, ik ga door"
    fi
  fi
else
  "$BIN/createdb" -U "$GEBRUIKER" "$DB" || stop "Aanmaken van de database is mislukt."
  ok "database aangemaakt"
fi

# ---------------------------------------------------------------- schema
kop "4. Schema en configuratie"
for bestand in db/schema.sql db/seed_config.sql db/boeken.sql db/meten.sql \
                db/uitgaand.sql db/zelfcontrole.sql db/import.sql; do
  [ -f "$bestand" ] || stop "Bestand $bestand ontbreekt. Zit je wel in de juiste map?"
  if P -d "$DB" -v ON_ERROR_STOP=1 -q -f "$bestand" >/tmp/vakto_sql.log 2>&1; then
    ok "$bestand geladen"
  else
    printf '\n'; cat /tmp/vakto_sql.log; stop "Laden van $bestand is mislukt."
  fi
done
TABELLEN=$(P -d "$DB" -qtAX -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
VIEWS=$(P -d "$DB" -qtAX -c "SELECT count(*) FROM information_schema.views WHERE table_schema='public'")
ok "$TABELLEN tabellen en $VIEWS views staan klaar"

# ----------------------------------------------------------------- tests
kop "5. Tests van de rekenkern"
PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  let_ "Python niet gevonden — deze tests worden overgeslagen."
  let_ "Installeer het via https://www.python.org/downloads/"
else
  if PSQL="$PSQL -U $GEBRUIKER" PGDATABASE="$DB" \
     "$PY" -m unittest discover -s tests -t . >/tmp/vakto_py.log 2>&1; then
    ok "$(grep -E '^Ran ' /tmp/vakto_py.log)  —  alle tests groen"
  else
    printf '\n'; tail -25 /tmp/vakto_py.log; stop "Er zijn tests gezakt."
  fi
fi

kop "6. Tests tegen de database"
: > /tmp/vakto_db.log
for t in tests-sql/test_boeken.sql tests-sql/test_meten.sql \
         tests-sql/test_uitgaand.sql tests-sql/test_zelfcontrole.sql \
         tests-sql/test_import.sql; do
  if P -d "$DB" -v ON_ERROR_STOP=1 -f "$t" >>/tmp/vakto_db.log 2>&1; then
    :
  else
    printf '\n'; grep -E 'GEZAKT|ERROR' /tmp/vakto_db.log | head -5; stop "SQL-tests gezakt ($t)."
  fi
done
GOED=$(grep -c 'OK ' /tmp/vakto_db.log)
ok "$GOED controles geslaagd (boeken, meten, uitgaand, zelfcontrole, import, views)"

kop "7. Twee mensen tegelijk"
if PSQL="$PSQL -U $GEBRUIKER" PGDATABASE="$DB" bash tests-sql/test_gelijktijdig.sh >/tmp/vakto_glt.log 2>&1; then
  grep -E 'geslaagd|voorraad|journaal' /tmp/vakto_glt.log | sed 's/^/  /'
  ok "precies één picker kreeg de laatste vijf stuks"
else
  printf '\n'; cat /tmp/vakto_glt.log; stop "De gelijktijdigheidstest is gezakt."
fi
if PSQL="$PSQL -U $GEBRUIKER" PGDATABASE="$DB" bash tests-sql/test_gelijktijdig_reserveren.sh >/tmp/vakto_glr.log 2>&1; then
  grep -E '^  (A |B |wacht|res na|samen)' /tmp/vakto_glr.log | sed 's/^/  /'
  ok "precies één verkoper kreeg de laatste tien stuks"
else
  printf '\n'; cat /tmp/vakto_glr.log; stop "De reserveringstest onder gelijktijdigheid is gezakt."
fi

kop "8. De schermen"
if [ -z "$PY" ]; then
  let_ "Python niet gevonden — overgeslagen."
elif "$PY" -c "import psycopg" >/dev/null 2>&1; then
  ok "psycopg staat klaar — de webserver kan draaien"
else
  let_ "psycopg ontbreekt; de schermen zelf zijn wel getest (die praten"
  let_ "niet rechtstreeks met de database). Voor de webserver:"
  let_ "    pip install -r requirements.txt"
fi

# ------------------------------------------------------------------ klaar
printf '\n%s  Alles staat en alles is groen.%s\n\n' "$groen$dik" "$uit"
cat <<KLAAR
  De schermen bekijken:
      $PY -m vakto.web
    en open daarna http://127.0.0.1:8000/ in je browser.

  Wat je nu hebt:
    - een database '$DB' met het volledige schema
    - de rekenkern in Python, gelijk aan de browserversie
    - boeken met transactie en rijvergrendeling
    - metingen als tijdlijn, met meldingen die zelf uitzoeken
      welke locaties door een nieuwe maat in de knel komen
    - de uitgaande stroom: reserveren, picken, manco, inpakken,
      verzenden — met de vergrendeling die dubbel verkopen tegenhoudt
    - een zelfcontrole die zijn eigen werk aanmaakt, zijn eigen taken
      laat vervallen en zijn eigen meldingen sluit
    - een import die de rommelige bestanden van een klant inleest en
      eerst laat zien wat eruit komt
    - de schermen: dashboard, taken, orders, picken, scanmodus,
      inslag, opmeten, locaties en artikelen — met dezelfde stijl
      als de browserversie

  Rondkijken in de database:
      $PSQL -U $GEBRUIKER -d $DB

    \\dt            alle tabellen
    \\d stock       hoe de voorraadtabel eruitziet
    SELECT * FROM setting;
    \\q             stoppen

  Dit bestand kun je altijd opnieuw draaien. Het zet het schema dan
  opnieuw op, dus gegevens die je zelf hebt ingevoerd gaan weg.

KLAAR
