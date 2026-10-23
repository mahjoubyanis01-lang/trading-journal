@echo off
rem Lanceur Windows de l'application locale Trading Journal + Options GEX
cd /d "%~dp0"
title Trading Journal - Options GEX

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 local_app.py
    goto :fin
)
where python >nul 2>nul
if %errorlevel%==0 (
    python local_app.py
    goto :fin
)
echo.
echo Python n'est pas installe sur ce PC.
echo Telechargez-le sur https://www.python.org/downloads/
echo et cochez "Add Python to PATH" pendant l'installation,
echo puis relancez ce fichier.
echo.
pause
:fin
