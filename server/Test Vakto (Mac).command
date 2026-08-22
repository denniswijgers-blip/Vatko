#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo ""
echo "  =========================================="
echo "     VAKTO  -  tests van de rekenkern"
echo "  =========================================="
echo ""
if ! command -v python3 >/dev/null 2>&1; then
  echo "  Python 3 is niet gevonden op deze Mac."
  echo "  Ga naar https://www.python.org/downloads/ en installeer het."
  echo ""
  read -r -p "  Druk op enter om te sluiten." _
  exit 1
fi
python3 -m unittest discover -s tests -t . -v
echo ""
echo "  Klaar. Staat er onderaan OK, dan geeft deze versie"
echo "  dezelfde antwoorden als de browserversie."
echo ""
read -r -p "  Druk op enter om te sluiten." _
