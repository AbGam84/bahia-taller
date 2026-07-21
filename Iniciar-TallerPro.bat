@echo off
cd /d "%~dp0"
title Katire
echo.
echo  Katire — http://127.0.0.1:8096/login
echo  admin / DuenoKatire2026
echo  cliente / VerKatire2026
echo.
echo  Si es la primera vez en esta PC, use INSTALAR-Y-ABRIR-KATIRE.bat
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo  ERROR: no hay Python. Ejecute INSTALAR-Y-ABRIR-KATIRE.bat
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  Falta instalacion. Ejecutando instalador...
  call "%~dp0INSTALAR-Y-ABRIR-KATIRE.bat"
  exit /b %ERRORLEVEL%
)

call .venv\Scripts\activate.bat
pip install -r requirements.txt -q
start "" "http://127.0.0.1:8096/login"
uvicorn app.main:app --host 127.0.0.1 --port 8096
pause
