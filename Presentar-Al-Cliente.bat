@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Katire — Presentar al cliente
echo.
echo  ============================================================
echo   ACCESO KATIRE
echo  ============================================================
echo.
echo   NUBE (recomendado si no hay Python en la PC):
echo   https://katire.onrender.com
echo   Primera vez: espere 40-60 segundos y recargue.
echo.
echo   LOCAL (esta PC):
echo   1) Doble clic en INSTALAR-Y-ABRIR-KATIRE.bat
echo   2) Espere "LISTO"
echo   3) Entra en http://127.0.0.1:8096/login
echo.
echo   USUARIOS:
echo   Dueño:   admin    / DuenoKatire2026
echo   Cliente: cliente  / VerKatire2026
echo  ============================================================
echo.
choice /C NL /M "Abrir Nube (N) o Local (L)"
if errorlevel 2 goto local
start "" "https://katire.onrender.com/login"
goto end
:local
if not exist ".venv\Scripts\python.exe" (
  echo  No hay instalacion local. Ejecutando instalador...
  call "%~dp0INSTALAR-Y-ABRIR-KATIRE.bat"
  goto end
)
start "" "http://127.0.0.1:8096/login"
powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:8096/api/health -TimeoutSec 2 | Out-Null } catch { Write-Host 'Servidor local apagado. Ejecute INSTALAR-Y-ABRIR-KATIRE.bat' }"
:end
echo.
pause
