@echo off
title C.A.R.E - Mitgliederverwaltung (Demo)
cd /d "%~dp0"
set PY=python
set PYW=pythonw
where py >nul 2>nul && (set PY=py& set PYW=pyw)
%PY% --version >nul 2>nul || (
  echo Python wurde nicht gefunden. Bitte Python 3 von python.org installieren
  echo und dabei "Add python.exe to PATH" anhaken.
  pause
  exit /b 1
)
%PY% -c "import PyQt5, openpyxl" >nul 2>nul || (
  echo Erster Start: benoetigte Pakete werden installiert ...
  %PY% -m pip install --user -r requirements.txt || ( pause & exit /b 1 )
)
start "" %PYW% main.py --demo
