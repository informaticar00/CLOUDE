# Gold Bot - automatska instalacija na Windows VPS.
# Pokretanje (PowerShell):
#   irm https://raw.githubusercontent.com/informaticar00/CLOUDE/refs/heads/claude/determined-wright-ul7bdj/vps-setup.ps1 | iex
# Ponovno pokretanje = AZURIRANJE bota (.env, postavke i paper stanje ostaju sacuvani).

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo   = 'informaticar00/CLOUDE'
$Branch = 'claude/determined-wright-ul7bdj'
$Dir    = 'C:\GoldBot'
$PyVer  = '3.12.10'
$Py     = 'C:\Program Files\Python312\python.exe'

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

try {
    # 1) Python 3.12 (MetaTrader5 paket ne podrzava uvijek najnoviji Python)
    Step "Python $PyVer"
    if (Test-Path $Py) {
        Write-Host 'Vec instaliran.'
    } else {
        $exe = Join-Path $env:TEMP "python-$PyVer-amd64.exe"
        Write-Host 'Skidam Python...'
        Invoke-WebRequest "https://www.python.org/ftp/python/$PyVer/python-$PyVer-amd64.exe" -OutFile $exe -UseBasicParsing
        Write-Host 'Instaliram (traje 1-2 minute)...'
        Start-Process $exe -ArgumentList '/quiet', 'InstallAllUsers=1', 'PrependPath=1', 'Include_test=0' -Wait
        if (-not (Test-Path $Py)) { throw 'Python se nije instalirao.' }
    }

    # 2) Bot
    Step 'Skidam Gold Bot sa GitHuba'
    $running = Get-CimInstance Win32_Process |
        Where-Object { ($_.Name -eq 'cmd.exe' -and $_.CommandLine -like '*start.bat*') -or
                       ($_.Name -eq 'python.exe' -and $_.CommandLine -like '*goldbot*') }
    if ($running) {
        Write-Host 'Bot trenutno radi - gasim ga zbog azuriranja...' -ForegroundColor Yellow
        $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Start-Sleep -Seconds 2
    }
    $zip = Join-Path $env:TEMP 'goldbot.zip'
    $tmp = Join-Path $env:TEMP 'goldbot-src'
    Invoke-WebRequest "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip -UseBasicParsing
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp -Force
    $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force $Dir | Out-Null
    # .env, postavke.json i paper_state.json nisu u ZIP-u, pa ostaju netaknuti
    Copy-Item (Join-Path $src.FullName '*') $Dir -Recurse -Force
    Write-Host "Bot je u $Dir"

    # 3) Paketi
    Step 'Instaliram pakete (Telegram, MetaTrader5...)'
    Set-Location $Dir
    if (-not (Test-Path '.venv\Scripts\python.exe')) { & $Py -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet --disable-pip-version-check
    & .\.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { throw 'Instalacija paketa nije uspjela.' }

    # 4) .env
    $newEnv = $false
    if (-not (Test-Path '.env')) {
        Copy-Item '.env.example' '.env'
        $newEnv = $true
    }

    # 5) Autostart nakon prijave u Windows
    Step 'Podesavam automatsko pokretanje'
    $lnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'GoldBot.lnk'
    $sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
    $sc.TargetPath = Join-Path $Dir 'start.bat'
    $sc.WorkingDirectory = $Dir
    $sc.Save()
    Write-Host 'Bot ce se pokretati automatski kad se prijavis u Windows.'

    # 6) MetaTrader 5
    Step 'Provjeravam MetaTrader 5'
    $mt5 = Get-ChildItem 'C:\Program Files', 'C:\Program Files (x86)' -Filter terminal64.exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($mt5) {
        Write-Host "Pronadjen: $($mt5.FullName)"
    } else {
        Write-Host 'MetaTrader 5 NIJE instaliran. Skini ga sa stranice SVOG BROKERA i instaliraj.' -ForegroundColor Yellow
    }

    Step 'GOTOVO'
    Write-Host @"
Sljedeci koraci:
  1. Popuni C:\GoldBot\.env (otvara se sada u Notepadu) i snimi.
  2. Pokreni C:\GoldBot\provjera.bat  -> mora pisati 'Sve radi'.
  3. Pokreni C:\GoldBot\start.bat     -> bot ti se javi na Telegram.
  4. Ukljuci Autologon (vidi README) da bot radi i nakon restarta VPS-a.
"@
    if ($newEnv) { Start-Process notepad.exe (Join-Path $Dir '.env') }
}
catch {
    Write-Host "`nGRESKA: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Posalji ovu poruku da ti pomognem.'
}
