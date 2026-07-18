@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo  Katire — verificación anti-fallos (antes de mostrar al cliente)
echo  ==============================================================
echo.
python scripts\smoke_katire.py
if errorlevel 1 (
  echo.
  echo  HAY FALLOS. No entregue al cliente hasta corregir.
  pause
  exit /b 1
)
echo.
echo  Todo OK. Puede abrir https://katire.onrender.com o Iniciar-TallerPro.bat
pause
exit /b 0
