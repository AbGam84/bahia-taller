@echo off
cd /d "%~dp0"
title TallerPro Guanacaste
echo.
echo  ========================================
echo   TallerPro Guanacaste
echo   http://127.0.0.1:8096
echo  ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo Creando entorno virtual...
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
echo.
echo Abriendo el sistema...
start "" "http://127.0.0.1:8096/login"
uvicorn app.main:app --host 127.0.0.1 --port 8096 --reload
pause
