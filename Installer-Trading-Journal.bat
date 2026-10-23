@echo off
rem ============================================================
rem  Installateur automatique - Trading Journal + Options GEX
rem  - Installe Python si absent (installateur officiel python.org)
rem  - Telecharge l'application et la place sur le Bureau
rem  - Cree un raccourci "Trading Journal" sur le Bureau
rem  - Lance l'application
rem ============================================================
title Installation - Trading Journal
echo.
echo  Installation de Trading Journal + Options GEX...
echo  (cela peut prendre 1 a 3 minutes)
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop';" ^
 "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
 "$tmp=Join-Path $env:TEMP 'tj-install';" ^
 "Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue;" ^
 "New-Item -ItemType Directory -Path $tmp | Out-Null;" ^
 "if (-not (Get-Command py -ErrorAction SilentlyContinue)) {" ^
 "  Write-Host '  [1/4] Python absent : installation (fenetre de progression)...';" ^
 "  iwr 'https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe' -OutFile (Join-Path $tmp 'python-setup.exe');" ^
 "  Start-Process (Join-Path $tmp 'python-setup.exe') -ArgumentList '/passive','InstallAllUsers=0','PrependPath=1','Include_launcher=1' -Wait;" ^
 "} else { Write-Host '  [1/4] Python deja present.' };" ^
 "Write-Host '  [2/4] Telechargement de l''application...';" ^
 "iwr 'https://github.com/mahjoubyanis01-lang/trading-journal/archive/refs/heads/main.zip' -OutFile (Join-Path $tmp 'tj.zip');" ^
 "Expand-Archive (Join-Path $tmp 'tj.zip') -DestinationPath $tmp -Force;" ^
 "Write-Host '  [3/4] Installation sur le Bureau...';" ^
 "$desk=[Environment]::GetFolderPath('Desktop');" ^
 "$dest=Join-Path $desk 'Trading Journal';" ^
 "New-Item -ItemType Directory -Path $dest -Force | Out-Null;" ^
 "Copy-Item (Join-Path $tmp 'trading-journal-main\*') $dest -Recurse -Force;" ^
 "$ws=New-Object -ComObject WScript.Shell;" ^
 "$lnk=$ws.CreateShortcut((Join-Path $desk 'Trading Journal.lnk'));" ^
 "$lnk.TargetPath=Join-Path $dest 'Lancer Trading Journal.bat';" ^
 "$lnk.WorkingDirectory=$dest;" ^
 "$lnk.IconLocation=(Join-Path $dest 'app.ico')+',0';" ^
 "$lnk.Description='Trading Journal + Options GEX';" ^
 "$lnk.Save();" ^
 "Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue;" ^
 "Write-Host '  [4/4] Lancement...';" ^
 "Start-Process (Join-Path $dest 'Lancer Trading Journal.bat')"

if %errorlevel%==0 (
  echo.
  echo  Installation terminee !
  echo  Un dossier et un raccourci "Trading Journal" sont sur votre Bureau.
  echo  L'application s'ouvre dans votre navigateur.
) else (
  echo.
  echo  L'installation a echoue. Verifiez votre connexion internet puis
  echo  relancez ce fichier. Si le probleme persiste, installez Python
  echo  manuellement depuis https://www.python.org/downloads/
)
echo.
pause
