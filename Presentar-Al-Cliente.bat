@echo off
cd /d "%~dp0"
start "" "http://127.0.0.1:8096/login"
echo.
echo  TallerPro ya debe estar corriendo.
echo  Si no abre, ejecute primero Iniciar-TallerPro.bat
echo.
echo  Usuario demo: admin
echo  Clave demo:   admin123
echo.
pause
