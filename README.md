# 🥇 Gold Bot — Telegram bot za trgovanje zlatom (XAU/USD)

Bot prati cijenu zlata, računa signale i, ako to uključiš, sam otvara i zatvara pozicije.
Njime upravljaš preko Telegrama. Radi s **MetaTrader 5**, s **OANDA**-om ili kao **simulacija** (paper).

> ⚠️ **Upozorenje:** trgovanje zlatom s polugom je rizično i možeš izgubiti novac.
> Ova strategija nije garancija zarade i nije testirana na historijskim podacima.
> Bot se zato podrazumijevano pokreće u **paper** načinu (bez pravog novca), a
> auto-trading je isključen. Prije pravog novca testiraj ga sedmicama na **demo** računu.

---

## 📱 Upravljanje s iPhonea

Bot radi na računaru ili serveru, a ti njime upravljaš s iPhonea preko Telegrama:

```
 iPhone (Telegram)  ⇄  Gold Bot (Windows PC / VPS)  ⇄  MetaTrader 5  ⇄  broker
 iPhone (MT5 app)   ←─────────────────────────────────  isti račun
```

- **Dugmad:** u Telegramu imaš meni s dugmadima, pa ništa ne moraš kucati: 💰 Cijena · 📊 Signal · 🟢 Kupi · 🔴 Prodaj · 📂 Pozicije · 📋 Status · 🤖 Auto-trading · ⚙️ Postavke.
- **Nalog:** dodirneš 🟢 Kupi, izabereš veličinu (Auto po riziku, 1, 2, 5 ili 10 oz) i potvrdiš ✅.
- **Zatvaranje:** u 📂 Pozicije svaka pozicija ima dugme ❌ Zatvori.
- **Postavke:** u ⚙️ Postavke se rizik, timeframe, SL/TP, EMA, dnevni limit i ostalo mijenjaju dodirom. Promjene se **čuvaju trajno** (u `postavke.json`), pa ne moraš dirati `.env`.
- **Obavijesti:** novi signali, otvorene i zatvorene pozicije (SL/TP) i greške stižu kao push notifikacije.
- **MetaTrader 5 za iOS** (App Store): prijavi se na isti račun da vidiš grafikone i pozicije koje bot otvara.

### Bot 24/7 bez računara: Windows VPS (sve s iPhonea)

VPS je iznajmljeni Windows računar u cloudu koji radi stalno. Ti se na njega spajaš s iPhonea.

**1. Iznajmi VPS**
- Prvo pitaj svog MT5 brokera: mnogi daju **besplatan VPS** ako imaš određeni depozit ili obim trgovanja.
- Inače ga nudi bilo koji hosting koji ima **Windows Server**.
- Preporučena konfiguracija:
  - **2 vCPU, 4 GB RAM-a i 40 GB diska** (s 2 GB RAM-a Windows i MT5 rade sporo),
  - **lokacija** blizu servera brokera (najčešće London, Frankfurt, Amsterdam ili New York).
- Nakon kupovine dobiješ **IP adresu, korisničko ime** (obično `Administrator`) **i lozinku**.

**2. Spoji se s iPhonea**
1. Iz App Storea instaliraj **Windows App** (Microsoft).
2. Dodirni **+ → Add PC**. U *PC name* upiši IP adresu VPS-a, a pod *Credentials* korisničko ime i lozinku.
3. Dodirni VPS i prihvati upozorenje o certifikatu. Vidiš Windows desktop.
4. Na iPhoneu je ekran mali. Okreni telefon vodoravno, a prstom pomjeraš miš. Na iPadu ili s tastaturom je lakše.

**3. Instaliraj bota na VPS-u**

**Najbrže, jednom komandom.** Na VPS-u desni klik na Start → **Windows PowerShell (Admin)**, zalijepi ovo i pritisni Enter:

```powershell
irm https://raw.githubusercontent.com/informaticar00/CLOUDE/refs/heads/claude/determined-wright-ul7bdj/vps-setup.ps1 | iex
```

- **Šta radi:** instalira Python 3.12, skida bota u `C:\GoldBot`, instalira pakete, podesi autostart i otvori `.env` u Notepadu.
- **Kopiranje s iPhonea:** kopiraj komandu na iPhoneu, pa je u PowerShellu na VPS-u zalijepi desnim klikom (dugi pritisak). Windows App prenosi clipboard.
- **Ažuriranje:** istu komandu pokreneš kasnije da ažuriraš bota. `.env` i postavke ostaju.

Nakon skripte ti ostaje: instaliraj MT5 od brokera, popuni `.env`, pa pokreni `provjera.bat` i `start.bat`.

**Ručno, korak po korak:**

Na VPS-u otvori **Edge** i uradi isto kao na običnom računaru:
1. **Python:** <https://www.python.org/downloads/> i označi **„Add python.exe to PATH“**.
2. **Bot:** prijavi se na GitHub i skini ZIP grane `claude/determined-wright-ul7bdj`. Raspakuj ga u `C:\GoldBot`.
3. **MT5:** instaliraj MetaTrader 5 od svog brokera, prijavi se i uključi **Algo Trading** (pogledaj poglavlje *MetaTrader 5*).
4. **Instalacija i postavke:** pokreni `install.bat` i popuni `.env`.
   - Token i chat ID najlakše kopiraš ako na VPS-u otvoriš <https://web.telegram.org>.
   - Prijavu na Telegram Web potvrdiš s iPhonea.
5. **Provjera:** pokreni `provjera.bat` i dočekaj „Sve radi ✅“.
6. **Start:** pokreni `start.bat`. Ako se bot sruši, ova skripta ga sama ponovo pokrene za 30 sekundi.

**4. Neka se bot sam pokreće**
1. **Autostart:** pokreni **`autostart.bat`**. On napravi prečicu, pa se bot pokrene čim se prijaviš u Windows. MT5 terminal bot pokreće sam.
2. **Automatska prijava:** Windows ponekad restartuje VPS zbog ažuriranja, a nakon restarta niko nije prijavljen. Zato uključi automatsku prijavu:
   - skini **Autologon** sa <https://learn.microsoft.com/sysinternals/downloads/autologon> (zvanični Microsoftov alat),
   - pokreni `Autologon64.exe`, upiši lozinku VPS-a i klikni **Enable**.
3. **Test:** restartuj VPS (*Start → Power → Restart*). Za 1–2 minute u Telegramu treba stići poruka *„Gold Bot pokrenut“*.

**5. Odspajanje**
- **Ispravno:** samo zatvori Windows App ili dodirni **Disconnect**, i bot radi dalje.
- **Pogrešno:** nikad ne biraj **Sign out / Odjava**, jer to gasi bota i MT5.

**Sigurnost**
- Za VPS koristi dugu, jedinstvenu lozinku i nikome je ne daj. Ko ima VPS, ima i tvoj trading račun.
- `.env` sadrži Telegram token i MT5 lozinku, pa ga ne šalji nikome i ne stavljaj na GitHub. Ionako je u `.gitignore`.

---

## 📥 Instalacija (Windows, korak po korak)

MetaTrader 5 Python paket radi **samo na Windowsu**, pa je ovo preporučeni način.

### Korak 1: Instaliraj Python

1. Otvori <https://www.python.org/downloads/> i skini **Python 3.12** (ne noviji, jer MetaTrader5 paket ne podržava uvijek najnoviju verziju).
2. Pokreni instalaciju i **obavezno označi kvadratić „Add python.exe to PATH“** na prvom ekranu.
3. Klikni *Install Now*.

### Korak 2: Skini bota

- **Najlakše:** na GitHubu otvori ovaj repozitorij i izaberi granu `claude/determined-wright-ul7bdj`. Klikni zeleno dugme **Code → Download ZIP** i raspakuj ga, npr. u `C:\GoldBot`.
- **Ili preko gita:**
  ```bat
  git clone -b claude/determined-wright-ul7bdj https://github.com/informaticar00/cloude.git C:\GoldBot
  ```

### Korak 3: Napravi Telegram bota

1. U Telegramu otvori **@BotFather**, pošalji `/newbot` i prati upute.
2. Kopiraj **token** koji dobiješ (izgleda kao `7123456789:AAH...`).
3. Otvori **@userinfobot** i pošalji mu bilo šta. On ti vrati tvoj **chat ID** (broj, npr. `123456789`).

### Korak 4: Pokreni `install.bat`

U folderu bota dvaput klikni na **`install.bat`**. On će:
- napraviti virtualno okruženje (`.venv`),
- instalirati sve potrebne pakete (uključujući `MetaTrader5`),
- napraviti fajl `.env` i otvoriti ga u Notepadu.

### Korak 5: Popuni `.env`

Ovo je minimum za početak. Paper način je simulacija s besplatnim cijenama:

```ini
TELEGRAM_TOKEN=7123456789:AAH...tvoj_token
ALLOWED_CHAT_IDS=123456789
MODE=paper
DATA_SOURCE=yahoo
```

Snimi fajl (Ctrl+S). Za MetaTrader 5 pogledaj sljedeće poglavlje.

### Korak 6: Provjeri i pokreni

1. Dvaput klikni **`provjera.bat`**. Trebao bi ispisati cijenu, saldo i signal te na kraju `Sve radi. ✅`.
2. Dvaput klikni **`start.bat`**. Bot ti šalje poruku *„Gold Bot pokrenut“* na Telegram.
3. U Telegramu mu pošalji `/pomoc`.

Bot radi dok je prozor `start.bat` otvoren i računar uključen.

---

## 💵 Pravi novac

Bot **neće otvoriti nijednu poziciju na REAL računu** dok u `.env` ne postaviš `ALLOW_REAL_MONEY=true`. To je zaštita da ne trguješ pravim novcem slučajno. Demo računi rade i bez toga.

**Preporučeni redoslijed:**
1. **Demo:** 2–4 sedmice na **demo** računu, na istom VPS-u i s istim postavkama. Prati `/historija` i P/L.
2. **Pravi račun, mali rizik:** tek ako su rezultati dobri, prebaci se na pravi račun s **malim rizikom**:
   ```ini
   MODE=mt5
   DATA_SOURCE=mt5
   MT5_LOGIN=broj_pravog_racuna
   MT5_PASSWORD=lozinka
   MT5_SERVER=Broker-Live        # tačan naziv REAL servera
   ALLOW_REAL_MONEY=true
   RISK_PCT=0.5                  # 0.5% salda po trejdu
   MAX_UNITS=10                  # najviše 0.10 lota
   MAX_OPEN_POSITIONS=1
   DAILY_LOSS_LIMIT_PCT=2
   AUTO_TRADE_ON_START=false     # auto-trading uključiš ručno iz Telegrama
   ```
3. **Provjera:** pokreni `provjera.bat`. Mora pisati `Račun: MetaTrader 5 REAL #...`.
4. **Ručni nalog:** pokreni `start.bat`. U Telegramu prvo napravi **jedan ručni nalog od 1 oz** i provjeri u MT5 aplikaciji na iPhoneu da su SL i TP postavljeni. Zatim ga zatvori.
5. **Auto-trading:** tek onda uključi 🤖 Auto-trading.

> Ne ulaži novac koji ne smiješ izgubiti. Bot nije testiran na historijskim podacima i nema garancije zarade.

## 📈 MetaTrader 5

### Priprema terminala

1. Instaliraj **MetaTrader 5** sa stranice svog brokera, ili sa <https://www.metatrader5.com/>.
2. Otvori **demo račun** (*File → Open an Account*) ili se prijavi na postojeći.
3. U **Market Watch** (Ctrl+M) nađi simbol za zlato i zapamti **tačan naziv**: `XAUUSD`, `XAUUSD.m`, `XAUUSD+`, `GOLD`... Ako ga ne vidiš, desni klik → *Symbols* → potraži „XAU“ → *Show*.
4. Uključi algoritamsko trgovanje:
   - *Tools → Options → Expert Advisors* → označi **„Allow algorithmic trading“**,
   - u gornjoj traci klikni dugme **„Algo Trading“** da bude zeleno ▶️.

### Postavke u `.env`

```ini
MODE=mt5
DATA_SOURCE=mt5
MT5_SYMBOL=XAUUSD

# Ako je terminal otvoren i već prijavljen, ovo troje možeš ostaviti prazno:
MT5_LOGIN=12345678
MT5_PASSWORD=tvoja_lozinka
MT5_SERVER=ImeBrokera-Demo
```

Zatim pokreni `provjera.bat`. Trebao bi vidjeti nešto ovako:

```
Izvor cijena: MetaTrader 5 (XAUUSD)
Cijena:       bid 2650.12 / ask 2650.35
Saldo:        10,000.00 | equity 10,000.00
Račun:        MetaTrader 5 DEMO #12345678
...
Sve radi. ✅
```

### Kako bot radi s MT5

- **Veličina pozicije:** bot računa u uncama, a MT5 trguje u lotovima. Kod većine brokera je 1 lot XAUUSD = 100 unci, pa 0.01 lot = 1 unca. Bot to čita od brokera i zaokružuje **naniže**.
  - Primjer: saldo 1.000 USD, rizik 1% = 10 USD, SL 15 USD daleko. To daje 0.66 unci, što je manje od minimalnih 0.01 lota, pa bot **neće otvoriti** poziciju i javiće zašto.
  - Za MT5 zato treba veći saldo ili veći `RISK_PCT`.
- **SL i TP** se šalju zajedno s nalogom i stoje u MT5 i kad je bot ugašen.
- **Tvoje ručne pozicije:** bot upravlja samo pozicijama sa svojim brojem `MT5_MAGIC`, pa one koje otvoriš sam u terminalu ne dira.
- **Obavijesti:** kad MT5 zatvori poziciju na SL ili TP, bot ti javi rezultat na Telegram.
- **Kombinacija:** `MODE=paper` + `DATA_SOURCE=mt5` znači simulaciju na pravim cijenama tvog brokera, bez slanja naloga.
- **Valuta računa:** veličina pozicije pretpostavlja račun u USD. Ako ti je račun u EUR, stvarni rizik je malo drugačiji.

### Česti problemi

| Poruka | Rješenje |
|---|---|
| `Ne mogu se spojiti na MT5 terminal` | Otvori MT5 i prijavi se. Provjeri `MT5_SERVER` (tačan naziv iz prozora za prijavu). Ako imaš više terminala, postavi `MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe`. |
| `Simbol XAUUSD ne postoji` | Upiši tačan naziv iz Market Watcha u `MT5_SYMBOL`. |
| `kod 10027 ... Algo Trading` | Uključi dugme **Algo Trading** u terminalu. |
| `kod 10016 ... SL/TP preblizu` | Broker traži veći razmak, pa povećaj `ATR_SL_MULT`. |
| `kod 10019` | Nema dovoljno margine, pa smanji `RISK_PCT` ili `MAX_UNITS`. |
| `Premala pozicija: minimum je 0.01 lot` | Povećaj saldo ili `RISK_PCT`, ili koristi `/kupi 1` za ručnu količinu. |

---

## 🤖 Telegram komande

Sve ispod se može raditi i dugmadima. Komande su za one koji vole kucati.

| Komanda | Opis |
|---|---|
| `/meni` | prikazuje dugmad |
| `/cijena` | trenutna cijena (bid/ask) |
| `/signal` | analiza: EMA, RSI, ATR i trenutni signal |
| `/status` | račun, saldo, equity, auto-trading, dnevni gubitak |
| `/pozicije` | otvorene pozicije s P/L |
| `/kupi [unce]` | kupovina; bez broja se veličina računa iz % rizika |
| `/prodaj [unce]` | prodaja |
| `/zatvori [ID]` | zatvara jednu poziciju, a bez ID-a sve |
| `/auto on` / `/auto off` | uključuje/isključuje automatsko trgovanje |
| `/historija` | zadnji trejdovi (paper) |
| `/postavke` | postavke s dugmadima |
| `/postavi rizik 0.7` | postavlja bilo koju vrijednost (`/postavi` bez argumenata ispiše listu) |
| `/rizik 0.5` | kraće za `/postavi rizik` |
| `/postavke_reset` | vraća postavke iz `.env` |

Svaki ručni nalog, zatvaranje i uključivanje auto-tradinga traži potvrdu dugmetom ✅. Botom mogu upravljati samo chat ID-evi iz `ALLOWED_CHAT_IDS`.
Kad je auto-trading isključen, bot ti i dalje šalje poruku za svaki novi signal.

---

## 📊 Strategija i rizik

- **Signal:** presjek EMA 9/21 na zatvorenim svijećama.
  - Kupovina se preskače ako je RSI iznad 70 ili je cijena ispod EMA 200.
  - Prodaja se preskače obrnuto: RSI ispod 30 ili cijena iznad EMA 200.
- **Stop loss** = 1.5 × ATR(14), a **take profit** = 2 × udaljenost SL-a.
- **Veličina pozicije:** gubitak na SL-u je oko `RISK_PCT`% salda (podrazumijevano 1%), najviše `MAX_UNITS` unci.
- **Suprotan signal** zatvara postojeću poziciju i otvara novu.
- **Dnevni limit gubitka** (3%): auto-trading se pauzira do ponoći (UTC).

Početne postavke su u `.env.example`, s objašnjenjima. Ono što promijeniš iz Telegrama ima prednost i čuva se u `postavke.json`.

---

## 🖥️ Da bot radi 24/7

- **Na svom računaru:** bot radi dok je računar upaljen. Isključi *Sleep* u Windows postavkama napajanja.
- **Na Windows VPS-u (preporučeno):** pogledaj poglavlje *📱 Upravljanje s iPhonea* iznad.

## 🧪 cTrader (eksperimentalno)

Bot se može spojiti i na **cTrader** račun direktno preko interneta, bez MetaTradera i bez Windowsa.
Testirano je samo protiv simuliranog servera, ne protiv pravog cTradera, pa ga prvo probaj na **demo** računu.

1. Napravi cTrader ID i račun kod nekog cTrader brokera.
2. Na <https://openapi.ctrader.com> prijavi se i dodaj aplikaciju (*Applications → Add new app*).
   - U *Redirect URIs* dodaj `http://localhost`.
   - Kad je aplikacija odobrena, kopiraj **Client ID** i **Client Secret** u `.env`.
3. U `.env` postavi `MODE=ctrader` i `DATA_SOURCE=ctrader`.
4. Pokreni **`ctrader-login.bat`**, otvori link, odobri pristup i zalijepi adresu iz preglednika.
   - Token se čuva u `ctrader_token.json` i sam se obnavlja.
5. Pokreni `provjera.bat`, pa `start.bat`.

## 🐧 Linux / macOS

Na Linuxu i macOS-u rade paper i OANDA načini, ali MT5 ne radi:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # pa ga uredi
python -m goldbot --check
python -m goldbot
```

## 🔌 OANDA (alternativa za MT5)

```ini
MODE=oanda
DATA_SOURCE=oanda
OANDA_API_KEY=tvoj_token
OANDA_ACCOUNT_ID=101-004-1234567-001
OANDA_ENV=practice      # live = pravi novac
```

## 🧪 Za programere

```bash
pip install -r requirements-dev.txt
pytest
```

```
goldbot/
  __main__.py      pokretanje (--check za provjeru veze)
  config.py        postavke iz .env
  data.py          izvori cijena (Yahoo, OANDA)
  mt5.py           MetaTrader 5 izvor cijena i broker
  ctrader.py       cTrader Open API (eksperimentalno)
  indicators.py    EMA, RSI, ATR
  strategy.py      pravila za signale
  risk.py          veličina pozicije, dnevni limit
  broker.py        PaperBroker i OandaBroker
  engine.py        glavna logika (tick, nalozi)
  telegram_bot.py  Telegram meni, dugmad i komande
  overrides.py     postavke iz Telegrama (čuvaju se u postavke.json)
install.bat / provjera.bat / start.bat / autostart.bat   Windows skripte
vps-setup.ps1    instalacija/ažuriranje na VPS-u jednom komandom
```
