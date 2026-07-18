@echo off
cd /d "%~dp0"
title bahia - base limpia
echo.
echo  Esto borra TODOS los datos del taller y deja planillas vacias.
echo  Solo queda el usuario admin inicial.
echo.
pause
if exist "data\tallerpro.db" del /f /q "data\tallerpro.db"
if exist "data\uploads" rd /s /q "data\uploads"
mkdir data\uploads 2>nul
echo.
echo  Base limpia. Ahora ejecute Iniciar-TallerPro.bat
echo.
pause
