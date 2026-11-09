@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Gold Bot - instalacija ===

where python >nul 2>nul
if errorlevel 1 (
  echo Python nije instaliran. Skini ga sa https://www.python.org/downloads/
  echo i pri instalaciji OBAVEZNO oznaci "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist .venv (
  echo Pravim virtualno okruzenje...
  python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
  echo Instalacija paketa nije uspjela.
  pause
  exit /b 1
)

if not exist .env (
  copy .env.example .env >nul
  echo Napravljen je fajl .env - sada ce se otvoriti u Notepadu.
)
echo.
echo Upisi TELEGRAM_TOKEN, ALLOWED_CHAT_IDS i (za MT5) MT5 podatke, pa snimi fajl.
echo Zatim pokreni provjera.bat, pa start.bat
notepad .env
pause
