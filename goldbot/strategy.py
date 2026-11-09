"""Strategija: EMA crossover + RSI filter + EMA trend filter, SL/TP na osnovu ATR-a.

Pravila (računa se samo na ZATVORENIM svijećama):
  KUPI  - brza EMA presiječe sporu EMA odozdo, RSI < overbought,
          i (ako je trend filter uključen) cijena je iznad trend EMA.
  PRODAJ - brza EMA presiječe sporu EMA odozgo, RSI > oversold,
          i (ako je trend filter uključen) cijena je ispod trend EMA.
  SL = ATR * atr_sl_mult od ulazne cijene, TP = SL udaljenost * risk_reward.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .config import StrategyParams
from .indicators import atr, ema, rsi
from .models import BUY, HOLD, SELL, Candle


@dataclass
class Signal:
    action: str
    price: float
    candle_time: datetime
    reason: str
    stop_loss: float | None = None
    take_profit: float | None = None
    ema_fast: float | None = None
    ema_slow: float | None = None
    ema_trend: float | None = None
    rsi: float | None = None
    atr: float | None = None


def stops_for(side: str, entry: float, atr_value: float, params: StrategyParams) -> tuple[float, float]:
    """Vrati (stop_loss, take_profit) za datu stranu i ulaznu cijenu."""
    dist = atr_value * params.atr_sl_mult
    if side == BUY:
        return round(entry - dist, 2), round(entry + dist * params.risk_reward, 2)
    if side == SELL:
        return round(entry + dist, 2), round(entry - dist * params.risk_reward, 2)
    raise ValueError(f"Nepoznata strana: {side}")


def analyze(candles: Sequence[Candle], params: StrategyParams) -> Signal:
    closed = [c for c in candles if c.complete]
    if len(closed) < params.min_candles():
        last = closed[-1] if closed else (candles[-1] if candles else None)
        if last is None:
            raise ValueError("Nema svijeća za analizu")
        return Signal(
            HOLD,
            last.close,
            last.time,
            f"Premalo podataka ({len(closed)}/{params.min_candles()} svijeća)",
        )

    closes = [c.close for c in closed]
    highs = [c.high for c in closed]
    lows = [c.low for c in closed]

    fast = ema(closes, params.ema_fast)
    slow = ema(closes, params.ema_slow)
    trend = ema(closes, params.ema_trend) if params.ema_trend > 0 else [None] * len(closes)
    rsi_v = rsi(closes, params.rsi_period)
    atr_v = atr(highs, lows, closes, params.atr_period)

    f_now, f_prev = fast[-1], fast[-2]
    s_now, s_prev = slow[-1], slow[-2]
    r_now, a_now, t_now = rsi_v[-1], atr_v[-1], trend[-1]
    last = closed[-1]
    price = last.close

    base = dict(
        price=price,
        candle_time=last.time,
        ema_fast=f_now,
        ema_slow=s_now,
        ema_trend=t_now,
        rsi=r_now,
        atr=a_now,
    )
    assert None not in (f_now, f_prev, s_now, s_prev, r_now, a_now)

    crossed_up = f_prev <= s_prev and f_now > s_now
    crossed_down = f_prev >= s_prev and f_now < s_now

    if crossed_up:
        if r_now >= params.rsi_overbought:
            return Signal(HOLD, reason=f"EMA presjek gore, ali RSI {r_now:.1f} je prekupljen", **base)
        if t_now is not None and price <= t_now:
            return Signal(HOLD, reason="EMA presjek gore, ali cijena je ispod trend EMA", **base)
        sl, tp = stops_for(BUY, price, a_now, params)
        return Signal(BUY, reason="Brza EMA presjekla sporu odozdo", stop_loss=sl, take_profit=tp, **base)

    if crossed_down:
        if r_now <= params.rsi_oversold:
            return Signal(HOLD, reason=f"EMA presjek dolje, ali RSI {r_now:.1f} je preprodan", **base)
        if t_now is not None and price >= t_now:
            return Signal(HOLD, reason="EMA presjek dolje, ali cijena je iznad trend EMA", **base)
        sl, tp = stops_for(SELL, price, a_now, params)
        return Signal(SELL, reason="Brza EMA presjekla sporu odozgo", stop_loss=sl, take_profit=tp, **base)

    trend_txt = "rastući" if f_now > s_now else "padajući"
    return Signal(HOLD, reason=f"Nema novog presjeka (kratkoročni trend {trend_txt})", **base)
