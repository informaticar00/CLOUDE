"""Spot trading bot (long only, no leverage) for any ccxt-supported exchange.

Runs with REAL money by default (MODE=live). Safety limits from .env:
  MAX_CAPITAL       - max quote currency (e.g. USDT) the bot may use
  STOP_LOSS_PCT     - sell if price falls this % below entry
  TAKE_PROFIT_PCT   - sell if price rises this % above entry
  DAILY_LOSS_LIMIT  - stop opening new trades for the day after this loss

Stop with Ctrl+C. An open position is NOT sold automatically on stop;
the state is saved and resumed on next start.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

import ccxt
from dotenv import load_dotenv

from strategy import signal

load_dotenv()

MODE = os.getenv("MODE", "live").lower()  # live | paper
EXCHANGE = os.getenv("EXCHANGE", "binance")
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")
SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "15m")
MAX_CAPITAL = float(os.getenv("MAX_CAPITAL", "60"))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "2"))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "4"))
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", "5"))
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "30"))
PAPER_FEE = 0.001  # 0.1% simulated fee in paper mode

STATE_FILE = "state.json"
TRADES_FILE = "trades.csv"


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def today():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"position": None, "day": today(), "day_pnl": 0.0, "paper_cash": MAX_CAPITAL}


def save_state(state):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def record_trade(side, amount, price, pnl, reason):
    new = not os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time_utc", "mode", "symbol", "side", "amount", "price", "pnl", "reason"])
        w.writerow([datetime.now(timezone.utc).isoformat(), MODE, SYMBOL, side,
                    f"{amount:.8f}", f"{price:.8f}", f"{pnl:.4f}", reason])


def make_exchange():
    cls = getattr(ccxt, EXCHANGE, None)
    if cls is None:
        sys.exit(f"Nepoznata berza '{EXCHANGE}'. Pogledaj listu: python -c 'import ccxt; print(ccxt.exchanges)'")
    params = {"enableRateLimit": True, "options": {"defaultType": "spot"}}
    if MODE == "live":
        params.update({"apiKey": API_KEY, "secret": API_SECRET})
    ex = cls(params)
    ex.load_markets()
    if SYMBOL not in ex.markets:
        sys.exit(f"Par {SYMBOL} ne postoji na {EXCHANGE}.")
    return ex


def closed_closes(ex):
    candles = ex.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=200)
    return [c[4] for c in candles[:-1]]  # drop the still-forming candle


def buy(ex, state, price):
    base, quote = SYMBOL.split("/")
    if MODE == "paper":
        spend = min(MAX_CAPITAL, state["paper_cash"])
        amount = spend * (1 - PAPER_FEE) / price
        state["paper_cash"] -= spend
        state["position"] = {"amount": amount, "entry": price, "cost": spend}
        return amount, price

    free_quote = ex.fetch_balance()["free"].get(quote, 0) or 0
    spend = min(MAX_CAPITAL, free_quote * 0.99)
    min_cost = (ex.markets[SYMBOL].get("limits", {}).get("cost") or {}).get("min") or 0
    if spend <= 0 or spend < min_cost:
        log(f"Premalo {quote} za kupovinu (slobodno {free_quote:.2f}, minimum {min_cost}).")
        return None
    amount = float(ex.amount_to_precision(SYMBOL, spend / price))
    order = ex.create_market_buy_order(SYMBOL, amount)
    order = ex.fetch_order(order["id"], SYMBOL) if not order.get("filled") else order
    filled = order.get("filled") or amount
    avg = order.get("average") or price
    cost = order.get("cost") or filled * avg
    state["position"] = {"amount": filled, "entry": avg, "cost": cost}
    return filled, avg


def sell(ex, state, price):
    base, _ = SYMBOL.split("/")
    pos = state["position"]
    if MODE == "paper":
        proceeds = pos["amount"] * price * (1 - PAPER_FEE)
        state["paper_cash"] += proceeds
        return pos["amount"], price, proceeds - pos["cost"]

    free_base = ex.fetch_balance()["free"].get(base, 0) or 0
    amount = float(ex.amount_to_precision(SYMBOL, min(pos["amount"], free_base)))
    if amount <= 0:
        log(f"Nema {base} za prodaju — pozicija obrisana.")
        return 0, price, 0.0
    order = ex.create_market_sell_order(SYMBOL, amount)
    order = ex.fetch_order(order["id"], SYMBOL) if not order.get("filled") else order
    avg = order.get("average") or price
    proceeds = order.get("cost") or amount * avg
    fee = (order.get("fee") or {}).get("cost") or 0
    return amount, avg, proceeds - fee - pos["cost"]


def close_position(ex, state, price, reason):
    amount, avg, pnl = sell(ex, state, price)
    state["position"] = None
    state["day_pnl"] += pnl
    record_trade("sell", amount, avg, pnl, reason)
    log(f"PRODAJA {amount:.8f} @ {avg:.2f} ({reason}) | P/L: {pnl:+.2f} | danas: {state['day_pnl']:+.2f}")


def step(ex, state):
    if state["day"] != today():
        state["day"], state["day_pnl"] = today(), 0.0

    price = ex.fetch_ticker(SYMBOL)["last"]
    pos = state["position"]

    if pos:
        if price <= pos["entry"] * (1 - STOP_LOSS_PCT / 100):
            return close_position(ex, state, price, "stop-loss")
        if price >= pos["entry"] * (1 + TAKE_PROFIT_PCT / 100):
            return close_position(ex, state, price, "take-profit")

    sig = signal(closed_closes(ex))
    if pos and sig == "sell":
        return close_position(ex, state, price, "signal")
    if not pos and sig == "buy":
        if state["day_pnl"] <= -DAILY_LOSS_LIMIT:
            log(f"Dnevni limit gubitka dostignut ({state['day_pnl']:.2f}). Nema novih kupovina do sutra.")
            return
        res = buy(ex, state, price)
        if res:
            amount, avg = res
            record_trade("buy", amount, avg, 0.0, "signal")
            log(f"KUPOVINA {amount:.8f} @ {avg:.2f}")


def main():
    if MODE not in ("live", "paper"):
        sys.exit("MODE mora biti 'live' ili 'paper'.")
    if MODE == "live" and (not API_KEY or not API_SECRET):
        sys.exit("Za MODE=live upiši API_KEY i API_SECRET u .env fajl.")

    ex = make_exchange()
    state = load_state()

    if MODE == "live":
        quote = SYMBOL.split("/")[1]
        bal = ex.fetch_balance()["free"].get(quote, 0)
        log("!!! PRAVI NOVAC !!!")
        log(f"Slobodno {quote}: {bal}")
    log(f"Mod={MODE} berza={EXCHANGE} par={SYMBOL} tf={TIMEFRAME} max={MAX_CAPITAL} "
        f"SL={STOP_LOSS_PCT}% TP={TAKE_PROFIT_PCT}% dnevni_limit={DAILY_LOSS_LIMIT}")
    if state["position"]:
        log(f"Nastavljam otvorenu poziciju: {state['position']}")

    while True:
        try:
            step(ex, state)
            save_state(state)
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            log(f"Mrežna greška, pokušavam ponovo: {e}")
        except ccxt.AuthenticationError as e:
            sys.exit(f"Greška sa API ključem: {e}")
        except ccxt.InsufficientFunds as e:
            log(f"Nedovoljno sredstava: {e}")
        except Exception as e:  # keep running on unexpected errors
            log(f"Greška: {type(e).__name__}: {e}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Zaustavljeno. Otvorena pozicija (ako postoji) NIJE prodata.")
