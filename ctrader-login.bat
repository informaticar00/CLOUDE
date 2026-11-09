@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Prvo pokreni install.bat
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python -m goldbot --ctrader-login
pause
