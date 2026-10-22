@echo off
rem ============================================================
rem  S&P 500 Macro Bias Backtester — lanceur Windows (un clic)
rem  Prérequis : Python 3.11+ (https://www.python.org/downloads/
rem  en cochant "Add python.exe to PATH"). Node.js n'est PAS requis :
rem  l'interface compilée (frontend\dist) est servie par le backend.
rem ============================================================
setlocal
cd /d "%~dp0backend"
title S^&P 500 Macro Bias Backtester

where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python introuvable. Installez Python 3.11+ depuis
  echo https://www.python.org/downloads/ en cochant "Add python.exe to PATH",
  echo puis relancez ce fichier.
  pause
  exit /b 1
)

if not exist .venv (
  echo Premiere utilisation : creation de l'environnement Python...
  python -m venv .venv || (echo [ERREUR] creation du venv impossible & pause & exit /b 1)
  call .venv\Scripts\activate.bat
  echo Installation des dependances (une seule fois)...
  pip install -r requirements.txt || (echo [ERREUR] installation des dependances & pause & exit /b 1)
) else (
  call .venv\Scripts\activate.bat
)

echo.
echo  Demarrage du backtester sur http://127.0.0.1:8000
echo  Laissez cette fenetre ouverte. Fermez-la pour arreter l'application.
echo.
start "" http://127.0.0.1:8000
python -m uvicorn app.main:app --port 8000
pause
