@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Pravim precicu da se Gold Bot sam pokrene kad se prijavis u Windows...
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\GoldBot.lnk'); $s.TargetPath='%~dp0start.bat'; $s.WorkingDirectory='%~dp0'; $s.Save()"
if errorlevel 1 goto fail
echo Gotovo. Bot ce se pokretati automatski nakon prijave u Windows.
echo Da radi i nakon restarta VPS-a, ukljuci automatsku prijavu - Autologon, vidi README.
pause
exit /b 0
:fail
echo Nije uspjelo.
pause
exit /b 1
