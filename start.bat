@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Prvo pokreni install.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
:loop
echo Gold Bot radi. Zatvori ovaj prozor da ga ugasis.
python -m goldbot
echo.
echo Bot je stao. Ponovo pokrecem za 30 sekundi... (zatvori prozor da prekines)
timeout /t 30 /nobreak >nul
goto loop
