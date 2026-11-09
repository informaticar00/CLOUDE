# 🥇 Gold Bot — Telegram bot za trgovanje zlatom (XAU/USD)

Bot prati cijenu zlata, računa signale i (ako želiš) sam otvara i zatvara pozicije.
Njime upravljaš preko Telegrama.

> ⚠️ **Upozorenje:** trgovanje zlatom s polugom je rizično i možeš izgubiti novac.
> Ova strategija nije garancija zarade. Bot se zato podrazumijevano pokreće u
> **paper** načinu (simulacija bez pravog novca). Testiraj ga sedmicama prije
> nego što ga spojiš na pravi račun.

## Šta zna

- **Cijene**: Yahoo Finance (besplatno, bez ključa) ili OANDA.
- **Strategija**: presjek EMA 9/21 + RSI filter + EMA 200 trend filter, računa se samo na zatvorenim svijećama.
- **Stop loss / Take profit**: SL = 1.5 × ATR, TP = 2 × udaljenost SL-a (omjer rizika i zarade 1:2).
- **Upravljanje rizikom**:
  - veličina pozicije se računa tako da gubitak na SL-u bude ~1% salda,
  - ograničenje maksimalne veličine i broja pozicija,
  - dnevni limit gubitka (3%): kad se dostigne, auto-trading se pauzira do ponoći (UTC).
- **Načini rada**:
  - `paper`: simulirani račun, a stanje se čuva u `paper_state.json`,
  - `oanda`: OANDA demo (`practice`) ili pravi (`live`) račun. SL/TP se postavljaju kod brokera, pa rade i kad bot ne radi.
- **Sigurnost**: botom mogu upravljati samo chat ID-evi iz `ALLOWED_CHAT_IDS`, a svaki ručni nalog traži potvrdu dugmetom.

## Telegram komande

| Komanda | Opis |
|---|---|
| `/cijena` | trenutna cijena (bid/ask) |
| `/signal` | analiza: EMA, RSI, ATR i trenutni signal |
| `/status` | saldo, equity, auto-trading, dnevni gubitak |
| `/pozicije` | otvorene pozicije s P/L |
| `/kupi [unce]` | kupovina; bez broja se veličina računa iz % rizika |
| `/prodaj [unce]` | prodaja |
| `/zatvori [ID]` | zatvara jednu poziciju, a bez ID-a sve |
| `/auto on` / `/auto off` | uključuje/isključuje automatsko trgovanje |
| `/historija` | zadnji trejdovi i ukupni P/L (paper) |
| `/postavke` | prikaz postavki |
| `/rizik 0.5` | mijenja % rizika po trejdu |

Kad je auto-trading isključen, bot ti i dalje šalje poruku za svaki novi signal,
pa ga možeš koristiti i samo za signale.

## Instalacija

1. **Napravi bota**: u Telegramu otvori [@BotFather](https://t.me/BotFather), pošalji `/newbot` i kopiraj token.
2. **Saznaj svoj chat ID**: pošalji poruku [@userinfobot](https://t.me/userinfobot).
3. **Instaliraj** (potreban je Python 3.10+):

   ```bash
   git clone <ovaj-repo>
   cd CLOUDE
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   ```

4. U `.env` upiši barem `TELEGRAM_TOKEN` i `ALLOWED_CHAT_IDS`.
5. **Pokreni**:

   ```bash
   python -m goldbot
   ```

   Bot će ti poslati poruku da je pokrenut. Pošalji mu `/pomoc`.

## Spajanje na OANDA

1. Otvori besplatan demo račun na [oanda.com](https://www.oanda.com/) i u postavkama generiši API token.
2. U `.env` postavi:

   ```ini
   MODE=oanda
   DATA_SOURCE=oanda
   OANDA_API_KEY=tvoj_token
   OANDA_ACCOUNT_ID=101-004-1234567-001
   OANDA_ENV=practice
   ```

3. Tek kad si zadovoljan rezultatima na demo računu, promijeni `OANDA_ENV=live`.

Napomene:
- Na OANDA-i se XAU_USD trguje u cijelim uncama, pa se veličina pozicije zaokružuje naniže.
- Dostupnost XAU_USD zavisi od zemlje i tipa računa.

## Postavke

Sve postavke su u `.env.example`, s objašnjenjima. Najvažnije su:

| Varijabla | Podrazumijevano | Značenje |
|---|---|---|
| `TIMEFRAME` | `M15` | M1, M5, M15, M30, H1, D |
| `RISK_PCT` | `1.0` | % salda koji se rizikuje po trejdu |
| `MAX_UNITS` | `50` | maksimalna pozicija (unce) |
| `DAILY_LOSS_LIMIT_PCT` | `3.0` | dnevni limit gubitka |
| `ATR_SL_MULT` / `RISK_REWARD` | `1.5` / `2.0` | udaljenost SL-a i TP-a |
| `AUTO_TRADE_ON_START` | `false` | da li je auto-trading uključen pri pokretanju |

## Ograničenja

- Yahoo `GC=F` je cijena futures ugovora, koja se malo razlikuje od spot XAU/USD. Za signale i paper trgovanje to je dovoljno, a za pravo trgovanje koristi OANDA kao izvor cijena.
- U paper načinu se SL/TP provjeravaju svakih `CHECK_INTERVAL` sekundi (60), pa nagli skok između dvije provjere može dati lošije izvršenje.
- Bot mora stalno raditi (npr. na VPS-u ili Raspberry Pi-ju). Na OANDA-i SL/TP ostaju aktivni i kad je bot ugašen.
- Promjene preko `/rizik` i `/auto` traju do restarta. Trajne promjene upisuj u `.env`.

## Struktura

```
goldbot/
  __main__.py      pokretanje
  config.py        postavke iz .env
  data.py          izvori cijena (Yahoo, OANDA)
  indicators.py    EMA, RSI, ATR
  strategy.py      pravila za signale
  risk.py          veličina pozicije, dnevni limit
  broker.py        PaperBroker i OandaBroker
  engine.py        glavna logika (tick, nalozi)
  telegram_bot.py  Telegram komande
tests/             testovi (pytest)
```

Testovi se pokreću ovako:

```bash
pip install -r requirements-dev.txt
pytest
```
