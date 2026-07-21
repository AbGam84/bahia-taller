@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Katire — Instalar y abrir (PC cliente)
color 0A

echo.
echo  ============================================================
echo   KATIRE — Instalacion y arranque en esta PC
echo   De la llave al XML.
echo  ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] No hay Python en esta PC.
  echo  Instale Python 3.11+ desde https://www.python.org/downloads/
  echo  Marque "Add python.exe to PATH" al instalar.
  echo  Luego vuelva a ejecutar este archivo.
  start https://www.python.org/downloads/
  pause
  exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if errorlevel 1 (
  echo  [ERROR] Python es muy viejo. Necesita 3.10 o superior.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  [1/4] Creando entorno virtual...
  python -m venv .venv
  if errorlevel 1 (
    echo  [ERROR] No se pudo crear .venv
    pause
    exit /b 1
  )
) else (
  echo  [1/4] Entorno virtual OK
)

call .venv\Scripts\activate.bat
echo  [2/4] Instalando dependencias (puede tardar 1-3 min)...
python -m pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt
if errorlevel 1 (
  echo  [ERROR] Fallo pip install. Revise internet / antivirus.
  pause
  exit /b 1
)

echo  [3/4] Liberando puerto 8096 si estaba ocupado...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8096 ^| findstr LISTENING') do (
  taskkill /F /PID %%a >nul 2>&1
)

echo  [4/4] Arrancando Katire...
start "Katire-Server" cmd /c "cd /d "%~dp0" && call .venv\Scripts\activate.bat && uvicorn app.main:app --host 127.0.0.1 --port 8096"

echo  Esperando que el servidor responda...
set /a n=0
:waitloop
set /a n+=1
if %n% GTR 40 goto timeout
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "try { $r=Invoke-RestMethod -Uri 'http://127.0.0.1:8096/api/health' -TimeoutSec 2; if($r.ok){exit 0}else{exit 1} } catch { exit 1 }"
if errorlevel 1 goto waitloop

echo.
echo  ============================================================
echo   LISTO — Katire esta corriendo
echo   http://127.0.0.1:8096/login
echo.
echo   DUENO:    admin   / DuenoKatire2026
echo   CLIENTE:  cliente / VerKatire2026
echo  ============================================================
echo.
start "" "http://127.0.0.1:8096/login"
echo  Deje abierta la ventana "Katire-Server". Si la cierra, el sistema se apaga.
pause
exit /b 0

:timeout
echo  [ERROR] El servidor no respondio a tiempo.
echo  Abra la ventana Katire-Server y lea el error en rojo.
pause
exit /b 1
