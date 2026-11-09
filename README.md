# Trading bot

Bot za spot trgovanje (bez poluge, samo kupovina pa prodaja) na kripto berzama.
Radi sa **pravim novcem** (`MODE=live`). Koristi biblioteku [ccxt](https://github.com/ccxt/ccxt),
pa radi sa Binance, Kraken, Bybit, KuCoin, OKX i drugim berzama.

> ⚠️ **Rizik:** bot može izgubiti novac. Ne garantuje zaradu. Ulaži samo novac
> bez kog možeš da živiš.

## Strategija
- **Kupi** kad brzi EMA(9) pređe iznad sporog EMA(21), a RSI(14) je ispod 70
- **Prodaj** kad EMA(9) padne ispod EMA(21), ili na stop-loss, ili na take-profit
- Signali se računaju samo na zatvorenim svećama (podrazumevano 15 min)

## Zaštite
| Podešavanje | Podrazumevano | Šta radi |
|---|---|---|
| `MAX_CAPITAL` | 60 | Najviše USDT koje bot sme da koristi |
| `STOP_LOSS_PCT` | 2 | Prodaje ako cena padne 2% ispod kupovne |
| `TAKE_PROFIT_PCT` | 4 | Prodaje ako cena poraste 4% |
| `DAILY_LOSS_LIMIT` | 5 | Posle 5 USDT gubitka u danu, nema novih kupovina do sutra |

## Pokretanje

### 1. Račun na berzi
1. Napravi račun na berzi (npr. Binance) i završi verifikaciju (lična karta).
2. Uplati novac i kupi **USDT** (npr. ~70 USDT za 130 KM).
3. Napravi **API ključ**:
   - uključi samo **Enable Spot Trading**
   - **NIKAKO ne uključuj Withdrawals (isplate)**
   - po mogućnosti ograniči ključ na IP adresu računara na kom bot radi

### 2. Instalacija
```bash
pip install -r requirements.txt
cp .env.example .env
```
Otvori `.env` i upiši `API_KEY` i `API_SECRET`. **Nikome ne šalji `.env` fajl.**

### 3. (Preporuka) Proveri strategiju na istoriji
```bash
python backtest.py 90
```
Pokazuje kako bi strategija prošla u zadnjih 90 dana, uz poređenje sa „samo kupi i drži“.

### 4. Pokreni
```bash
python bot.py
```
Bot proverava cenu na svakih 30 sekundi i ispisuje svaku kupovinu i prodaju.
Svi trejdovi se upisuju u `trades.csv`.

**Zaustavljanje:** `Ctrl+C`. Otvorena pozicija se **ne prodaje** automatski.
Ostaje na berzi, a bot je nastavlja kad ga ponovo pokreneš. Ako želiš sve da prodaš,
uradi to ručno na berzi.

Za simulaciju bez pravog novca postavi `MODE=paper` u `.env`.

## Bot mora stalno da radi
Bot trguje samo dok je računar uključen i program pokrenut. Ako ugasiš računar,
otvorena pozicija ostaje bez stop-lossa. Za rad 24/7 koristi računar koji je
stalno upaljen ili jeftin VPS.
