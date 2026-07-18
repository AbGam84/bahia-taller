@echo off
cd /d "%~dp0"
title bahia - publicar en la nube
echo.
echo  ================================================
echo   bahia fuera de su PC  (Render / Railway)
echo  ================================================
echo.
echo  1) Se sube el codigo a GitHub
echo  2) Usted conecta Render (gratis) en 2 clics
echo  3) El taller queda online 24/7 sin su computadora
echo.
pause

where git >nul 2>&1
if errorlevel 1 (
  echo Instale Git primero.
  pause
  exit /b 1
)

if not exist ".git" git init
git add -A
git status
echo.
echo Si pide commit, se creara uno automatico...
git commit -m "bahia lista para nube" 2>nul

echo.
echo Creando/actualizando repo en GitHub...
git remote add origin https://github.com/AbGam84/bahia-taller.git 2>nul
git branch -M main
git push -u origin main

echo.
echo Codigo: https://github.com/AbGam84/bahia-taller
echo Abriendo Render Blueprint para desplegar...
start "" "https://dashboard.render.com/blueprints/new?repo=https://github.com/AbGam84/bahia-taller"
echo.
echo  En Render:
echo   - Conecte GitHub si pide
echo   - Aplique el blueprint "bahia-taller"
echo   - Copie la URL https://....onrender.com
echo.
echo  Usuario inicial: admin
echo  Clave: la que Render genero en BAHIA_ADMIN_PASSWORD
echo  ^(Environment ^> BAHIA_ADMIN_PASSWORD^)
echo.
pause
