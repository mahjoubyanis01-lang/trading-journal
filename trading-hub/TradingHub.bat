@echo off
REM ============================================================
REM  Trading Hub - lanceur Windows (double-cliquez ce fichier)
REM  1re fois : installe tout automatiquement. Ensuite : s'ouvre direct.
REM  Seul prerequis : Python 3.11+ installe (https://python.org).
REM ============================================================
setlocal
cd /d "%~dp0"

where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")

if not exist "backend\.venv\Scripts\python.exe" (
  echo [Trading Hub] Premiere installation, patientez...
  %PY% -m venv "backend\.venv"
)
call "backend\.venv\Scripts\activate.bat"

python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "backend\requirements.txt"
python -m pip install --quiet pywebview

REM Reconstruire l'interface seulement si absente ET que Node est present.
if not exist "frontend\dist\index.html" (
  where npm >nul 2>nul && (
    echo [Trading Hub] Construction de l'interface...
    pushd frontend
    call npm install
    call npm run build
    popd
  )
)

cd backend
python -m app.desktop
