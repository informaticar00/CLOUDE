"""Backtest the strategy on historical candles (public data, no API key needed).

Usage: python backtest.py [days]   (default 60)
Uses SYMBOL, TIMEFRAME, EXCHANGE, MAX_CAPITAL, STOP_LOSS_PCT, TAKE_PROFIT_PCT from .env.
"""

import os
import sys

import ccxt
from dotenv import load_dotenv

from strategy import signal

load_dotenv()
EXCHANGE = os.getenv("EXCHANGE", "binance")
SYMBOL = os.getenv("SYMBOL", "BTC/USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "15m")
CAPITAL = float(os.getenv("MAX_CAPITAL", "60"))
SL = float(os.getenv("STOP_LOSS_PCT", "2")) / 100
TP = float(os.getenv("TAKE_PROFIT_PCT", "4")) / 100
FEE = 0.001


def fetch(ex, days):
    tf_ms = ex.parse_timeframe(TIMEFRAME) * 1000
    since = ex.milliseconds() - days * 86_400_000
    out = []
    while since < ex.milliseconds() - tf_ms:
        batch = ex.fetch_ohlcv(SYMBOL, TIMEFRAME, since=since, limit=1000)
        if not batch:
            break
        out += batch
        since = batch[-1][0] + tf_ms
    return out


def run(candles):
    cash, pos, trades, wins = CAPITAL, None, 0, 0
    closes = []
    for _, _, high, low, close, _ in candles:
        if pos:
            stop, target = pos["entry"] * (1 - SL), pos["entry"] * (1 + TP)
            exit_price = stop if low <= stop else target if high >= target else None
            if exit_price:
                cash += pos["amount"] * exit_price * (1 - FEE)
                wins += exit_price > pos["entry"]
                trades += 1
                pos = None
        closes.append(close)
        sig = signal(closes[-200:])
        if pos and sig == "sell":
            cash += pos["amount"] * close * (1 - FEE)
            wins += close > pos["entry"]
            trades += 1
            pos = None
        elif not pos and sig == "buy":
            pos = {"amount": cash * (1 - FEE) / close, "entry": close}
            cash = 0.0
    if pos:
        cash += pos["amount"] * closes[-1] * (1 - FEE)
    return cash, trades, wins


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    ex = getattr(ccxt, EXCHANGE)({"enableRateLimit": True})
    candles = fetch(ex, days)
    if len(candles) < 50:
        sys.exit("Premalo podataka.")
    final, trades, wins = run(candles)
    hold = CAPITAL * candles[-1][4] / candles[0][4]
    print(f"{SYMBOL} {TIMEFRAME}, {days} dana, {len(candles)} sveća")
    print(f"Početni kapital:   {CAPITAL:.2f}")
    print(f"Strategija kraj:   {final:.2f} ({(final / CAPITAL - 1) * 100:+.2f}%)")
    print(f"Samo kupi i drži:  {hold:.2f} ({(hold / CAPITAL - 1) * 100:+.2f}%)")
    print(f"Trejdova: {trades}, dobitnih: {wins}" + (f" ({wins / trades * 100:.0f}%)" if trades else ""))


if __name__ == "__main__":
    main()
