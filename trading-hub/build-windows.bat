@echo off
REM ============================================================
REM  Construit un executable autonome TradingHub.exe (Windows)
REM  Prerequis : Python 3.11+ et Node (pour (re)construire l'UI).
REM  Resultat  : backend\dist\TradingHub.exe
REM ============================================================
setlocal
cd /d "%~dp0"

if not exist "backend\.venv\Scripts\python.exe" (
  py -3 -m venv "backend\.venv"
)
call "backend\.venv\Scripts\activate.bat"
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r "backend\requirements.txt"
python -m pip install --quiet pywebview pyinstaller MetaTrader5

REM (Re)construire l'interface
if exist "frontend\package.json" (
  where npm >nul 2>nul && (
    pushd frontend & call npm install & call npm run build & popd
  )
)

cd backend
pyinstaller --noconfirm trading-hub.spec
echo.
echo ============================================================
echo  Termine : backend\dist\TradingHub.exe
echo ============================================================
