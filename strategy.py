"""Trading strategy: EMA crossover with an RSI filter.

Pure functions only (no network), so the live bot and the backtest use
exactly the same logic.
"""


def ema(values, period):
    """Exponential moving average. Returns a list the same length as values."""
    if not values:
        return []
    k = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values, period=14):
    """Wilder's RSI. Returns a list the same length as values (first entries 50)."""
    if len(values) <= period:
        return [50.0] * len(values)
    gains, losses = [], []
    for i in range(1, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = [50.0] * (period + 1)

    def calc(g, l):
        if l == 0:
            return 100.0
        return 100 - 100 / (1 + g / l)

    out[-1] = calc(avg_gain, avg_loss)
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(calc(avg_gain, avg_loss))
    return out


def signal(closes, fast=9, slow=21, rsi_period=14, rsi_max=70):
    """Return 'buy', 'sell' or None based on the last two CLOSED candles.

    buy  -> fast EMA crosses above slow EMA and RSI is below rsi_max
    sell -> fast EMA crosses below slow EMA
    """
    if len(closes) < slow + 2:
        return None
    f = ema(closes, fast)
    s = ema(closes, slow)
    r = rsi(closes, rsi_period)
    crossed_up = f[-2] <= s[-2] and f[-1] > s[-1]
    crossed_down = f[-2] >= s[-2] and f[-1] < s[-1]
    if crossed_up and r[-1] < rsi_max:
        return "buy"
    if crossed_down:
        return "sell"
    return None
