@echo off
rem Cree un raccourci "S&P 500 Backtester" sur le Bureau de l'utilisateur,
rem pointant vers "Lancer Backtester.bat". A executer une seule fois.
setlocal
set "TARGET=%~dp0Lancer Backtester.bat"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'S&P 500 Backtester.lnk'));" ^
  "$s.TargetPath='%TARGET%';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%%SystemRoot%%\System32\imageres.dll,165';" ^
  "$s.Description='S&P 500 Macro Bias Backtester';" ^
  "$s.Save()"
if errorlevel 1 (
  echo [ERREUR] Impossible de creer le raccourci.
) else (
  echo Raccourci "S&P 500 Backtester" cree sur le Bureau.
)
pause
