@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Katire — Diagnostico PC cliente
echo.
echo  Diagnostico Katire en esta PC
echo  =============================
echo.

echo  [Python]
where python 2>nul
if errorlevel 1 (echo  FALTA Python en PATH) else (python --version)
echo.

echo  [Carpeta]
echo  %CD%
if exist app\main.py (echo  app\main.py OK) else (echo  FALTA app\main.py — carpeta incompleta)
if exist web\login.html (echo  web\login.html OK) else (echo  FALTA web\login.html)
if exist requirements.txt (echo  requirements.txt OK) else (echo  FALTA requirements.txt)
echo.

echo  [Entorno]
if exist .venv\Scripts\python.exe (echo  .venv OK) else (echo  Sin .venv — ejecute INSTALAR-Y-ABRIR-KATIRE.bat)
echo.

echo  [Puerto 8096]
netstat -ano | findstr :8096 | findstr LISTENING
if errorlevel 1 (echo  Nadie escucha en 8096 — el servidor NO esta corriendo)
echo.

echo  [Local health]
powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:8096/api/health -TimeoutSec 3 | ConvertTo-Json -Compress } catch { 'LOCAL CAIDO: ' + $_.Exception.Message }"
echo.

echo  [Nube https://katire.onrender.com ]
powershell -NoProfile -Command "try { Invoke-RestMethod https://katire.onrender.com/api/health -TimeoutSec 60 | ConvertTo-Json -Compress } catch { 'NUBE: ' + $_.Exception.Message }"
echo.

echo  Claves correctas:
echo    admin   / DuenoKatire2026
echo    cliente / VerKatire2026
echo  (NO use admin123 — esa clave es falsa)
echo.
pause
