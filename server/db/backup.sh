#!/bin/bash
# =====================================================================
#  VAKTO — back-up maken, en bewijzen dat hij terug te zetten is
#
#  Een back-up die nooit is teruggezet is geen back-up. Dit bestand doet
#  daarom allebei: het schrijft een dump weg, en met `--proef` zet het
#  die meteen terug in een wegwerpdatabase en telt na of alles er nog is.
#  Draai dat één keer per maand; het kost twee minuten en het is het
#  enige moment waarop je erachter kunt komen dat het níét werkt.
#
#    bash db/backup.sh                       een back-up maken
#    bash db/backup.sh --proef               maken én terugzetten toetsen
#    bash db/backup.sh --terugzetten <bestand> <database>
#
#  In een cron, elke nacht om drie uur:
#    0 3 * * *  cd /srv/vakto/server && bash db/backup.sh >> /var/log/vakto-backup.log 2>&1
#
#  WAAR DE DUMP HEEN MOET: niet op dezelfde schijf als de database. Een
#  schijf die stukgaat neemt allebei mee, en dat is precies het geval
#  waarvoor je een back-up hebt. Zet er een regel achter die hem naar een
#  andere machine kopieert (rsync, rclone, wat je ook hebt).
# =====================================================================
set -u
cd "$(dirname "$0")/.." || exit 1

DB="${PGDATABASE:-vakto}"
MAP="${VAKTO_BACKUP:-./backups}"
BEWAAR_DAGEN="${VAKTO_BACKUP_DAGEN:-30}"

groen=$'\033[32m'; rood=$'\033[31m'; geel=$'\033[33m'; dik=$'\033[1m'; uit=$'\033[0m'
ok()   { printf '  %s✓%s %s\n' "$groen" "$uit" "$1"; }
fout() { printf '  %s✗%s %s\n' "$rood" "$uit" "$1"; }
let_() { printf '  %s!%s %s\n' "$geel" "$uit" "$1"; }
stop() { printf '\n%s%s%s\n\n' "$rood" "$1" "$uit"; exit 1; }

command -v pg_dump >/dev/null 2>&1 || stop "pg_dump niet gevonden.
  Die hoort bij PostgreSQL. Op een Mac met Postgres.app staat hij in
  /Applications/Postgres.app/Contents/Versions/*/bin — zet die map in je PATH."

# ------------------------------------------------------------ terugzetten
if [ "${1:-}" = "--terugzetten" ]; then
  BESTAND="${2:?geef het bestand op}"
  DOEL="${3:?geef de database op waar het in moet}"
  printf '\n%s  Terugzetten van %s in %s%s\n\n' "$dik" "$BESTAND" "$DOEL" "$uit"
  let_ "ALLES wat er nu in '$DOEL' staat gaat weg."
  if [ -t 0 ]; then
    printf '  Doorgaan? (j/n) '; read -r antwoord
    case "$antwoord" in [jJyY]*) ;; *) printf '  Afgebroken.\n\n'; exit 0;; esac
  fi
  dropdb --if-exists "$DOEL"    || stop "Weggooien van '$DOEL' is mislukt."
  createdb "$DOEL"              || stop "Aanmaken van '$DOEL' is mislukt."
  pg_restore --no-owner --no-privileges -d "$DOEL" "$BESTAND" \
    || stop "Terugzetten is mislukt."
  ok "teruggezet in '$DOEL'"
  exit 0
fi

# ----------------------------------------------------------------- maken
printf '\n%s  VAKTO — back-up van database "%s"%s\n\n' "$dik" "$DB" "$uit"
mkdir -p "$MAP" || stop "Kan de map '$MAP' niet aanmaken."

STEMPEL="$(date +%Y-%m-%d_%H%M)"
BESTAND="$MAP/vakto-$STEMPEL.dump"

# Het aangepaste formaat (-Fc): kleiner, en je kunt er losse tabellen uit
# terugzetten. Een platte .sql lijkt handiger tot het moment dat je één
# tabel terug wilt en de rest niet.
pg_dump -Fc -f "$BESTAND" "$DB" || stop "pg_dump is mislukt."
GROOTTE="$(du -h "$BESTAND" | cut -f1)"
ok "$BESTAND ($GROOTTE)"

# --------------------------------------------------------------- opruimen
OUD="$(find "$MAP" -name 'vakto-*.dump' -mtime "+$BEWAAR_DAGEN" 2>/dev/null | wc -l | tr -d ' ')"
if [ "${OUD:-0}" -gt 0 ]; then
  find "$MAP" -name 'vakto-*.dump' -mtime "+$BEWAAR_DAGEN" -delete
  ok "$OUD dump(s) ouder dan $BEWAAR_DAGEN dagen opgeruimd"
fi

# ------------------------------------------------------------------ proef
if [ "${1:-}" = "--proef" ]; then
  PROEF="${DB}_proef_$$"
  printf '\n%s  Terugzetten toetsen%s\n\n' "$dik" "$uit"
  createdb "$PROEF" || stop "Aanmaken van de proefdatabase is mislukt."
  # Altijd opruimen, ook als er iets misgaat.
  trap 'dropdb --if-exists "$PROEF" >/dev/null 2>&1' EXIT

  if pg_restore --no-owner --no-privileges -d "$PROEF" "$BESTAND" \
       >/tmp/vakto_restore.log 2>&1; then
    ok "teruggezet in een wegwerpdatabase"
  else
    cat /tmp/vakto_restore.log; stop "Terugzetten is mislukt."
  fi

  # Natellen. Niet "hij deed het zonder foutmelding" maar "de rijen zijn
  # er nog" — dat is een ander soort zekerheid.
  gezakt=0
  for tabel in location product journal stock app_user setting; do
    a="$(psql -d "$DB"    -qtAX -c "SELECT count(*) FROM $tabel" 2>/dev/null || echo x)"
    b="$(psql -d "$PROEF" -qtAX -c "SELECT count(*) FROM $tabel" 2>/dev/null || echo y)"
    if [ "$a" = "$b" ]; then
      ok "$tabel: $a rijen, allebei"
    else
      fout "$tabel: $a in de database, $b in de back-up"; gezakt=1
    fi
  done

  # De functies horen er ook in te zitten. Een dump zonder vakto_boek()
  # is een dump waar je de dag na een storing niets mee kunt.
  n="$(psql -d "$PROEF" -qtAX -c \
      "SELECT count(*) FROM pg_proc WHERE proname LIKE 'vakto\_%'" 2>/dev/null)"
  if [ "${n:-0}" -gt 10 ]; then
    ok "$n vakto-functies staan erin"
  else
    fout "maar $n vakto-functies gevonden"; gezakt=1
  fi

  [ "$gezakt" -eq 0 ] || stop "De back-up is NIET betrouwbaar."
  printf '\n%s  De back-up is teruggezet en nageteld.%s\n\n' "$groen$dik" "$uit"
else
  printf '\n  Toets één keer per maand of hij ook terug te zetten is:\n'
  printf '      bash db/backup.sh --proef\n\n'
fi
