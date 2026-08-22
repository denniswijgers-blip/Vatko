@echo off
title Vakto - tests
cd /d "%~dp0"
color 0B
echo.
echo   ==========================================
echo      VAKTO  -  tests van de rekenkern
echo   ==========================================
echo.

python --version >nul 2>nul
if errorlevel 1 goto geen_python

python -m unittest discover -s tests -t . -v
echo.
echo   Klaar. Staat er onderaan OK, dan geeft deze versie
echo   dezelfde antwoorden als de browserversie.
echo.
pause
goto einde

:geen_python
echo   Python is niet gevonden op deze computer.
echo.
echo     1. Ga naar  https://www.python.org/downloads/
echo     2. Klik op de gele knop "Download Python"
echo     3. BELANGRIJK: vink onderin "Add python.exe to PATH" aan
echo        voordat je op Install klikt. Zonder dat vinkje werkt dit niet.
echo     4. Start daarna dit bestand opnieuw.
echo.
pause

:einde
