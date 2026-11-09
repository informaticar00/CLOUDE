# 🥇 Gold Bot — Telegram bot za trgovanje zlatom (XAU/USD)

Bot prati cijenu zlata, računa signale i, ako to uključiš, sam otvara i zatvara pozicije.
Njime upravljaš preko Telegrama. Radi s **MetaTrader 5**, s **OANDA**-om ili kao **simulacija** (paper).

> ⚠️ **Upozorenje:** trgovanje zlatom s polugom je rizično i možeš izgubiti novac.
> Ova strategija nije garancija zarade i nije testirana na historijskim podacima.
> Bot se zato podrazumijevano pokreće u **paper** načinu (bez pravog novca), a
> auto-trading je isključen. Prije pravog novca testiraj ga sedmicama na **demo** računu.

---

## 📥 Instalacija (Windows, korak po korak)

MetaTrader 5 Python paket radi **samo na Windowsu**, pa je ovo preporučeni način.

### Korak 1: Instaliraj Python

1. Otvori <https://www.python.org/downloads/> i skini Python 3.12 (ili noviji).
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

| Komanda | Opis |
|---|---|
| `/cijena` | trenutna cijena (bid/ask) |
| `/signal` | analiza: EMA, RSI, ATR i trenutni signal |
| `/status` | račun, saldo, equity, auto-trading, dnevni gubitak |
| `/pozicije` | otvorene pozicije s P/L |
| `/kupi [unce]` | kupovina; bez broja se veličina računa iz % rizika |
| `/prodaj [unce]` | prodaja |
| `/zatvori [ID]` | zatvara jednu poziciju, a bez ID-a sve |
| `/auto on` / `/auto off` | uključuje/isključuje automatsko trgovanje |
| `/historija` | zadnji trejdovi (paper) |
| `/postavke` | prikaz postavki |
| `/rizik 0.5` | mijenja % rizika po trejdu |

Svaki ručni nalog traži potvrdu dugmetom ✅. Botom mogu upravljati samo chat ID-evi iz `ALLOWED_CHAT_IDS`.
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

Sve postavke su u `.env.example`, s objašnjenjima.

---

## 🖥️ Da bot radi 24/7

- **Na svom računaru:** bot radi dok je računar upaljen. Isključi *Sleep* u Windows postavkama napajanja.
- **Na Windows VPS-u (preporučeno):** iznajmi Windows VPS (mnogi brokeri nude besplatan MT5 VPS), ponovi instalaciju i ostavi MT5 i `start.bat` da rade.
- **Automatski start:** stavi prečicu do `start.bat` u folder koji se otvara sa `Win+R` → `shell:startup`.

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
  indicators.py    EMA, RSI, ATR
  strategy.py      pravila za signale
  risk.py          veličina pozicije, dnevni limit
  broker.py        PaperBroker i OandaBroker
  engine.py        glavna logika (tick, nalozi)
  telegram_bot.py  Telegram komande
install.bat / provjera.bat / start.bat   Windows skripte
```
