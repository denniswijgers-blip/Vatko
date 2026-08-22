#!/bin/bash
cd "$(dirname "$0")" || exit 1
bash opzetten.sh
echo ""
read -r -p "Druk op enter om dit venster te sluiten." _
