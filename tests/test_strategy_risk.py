import pytest

from goldbot.config import StrategyParams
from goldbot.models import BUY, HOLD, SELL
from goldbot.risk import daily_loss_pct, position_size
from goldbot.strategy import analyze, stops_for

from .helpers import make_candles

P = StrategyParams(ema_fast=3, ema_slow=6, ema_trend=0, rsi_period=5, atr_period=5,
                   rsi_overbought=101, rsi_oversold=-1)


def test_not_enough_data():
    sig = analyze(make_candles([2000.0] * 5), P)
    assert sig.action == HOLD and "Premalo" in sig.reason


def test_buy_on_cross_up():
    closes = [2010 - i for i in range(20)] + [2005.0]
    sig = analyze(make_candles(closes), P)
    assert sig.action == BUY
    assert sig.stop_loss < sig.price < sig.take_profit


def test_sell_on_cross_down():
    closes = [1990 + i for i in range(20)] + [1995.0 - 10]
    sig = analyze(make_candles(closes), P)
    assert sig.action == SELL
    assert sig.take_profit < sig.price < sig.stop_loss


def test_rsi_filter_blocks_buy():
    p = StrategyParams(**{**P.__dict__, "rsi_overbought": 10})
    closes = [2010 - i for i in range(20)] + [2005.0]
    assert analyze(make_candles(closes), p).action == HOLD


def test_trend_filter_blocks_buy_below_trend():
    p = StrategyParams(**{**P.__dict__, "ema_trend": 30})
    closes = [2050 - i for i in range(40)] + [2020.0]
    assert analyze(make_candles(closes), P).action == BUY  # bez filtera bi kupio
    sig = analyze(make_candles(closes), p)
    assert sig.action == HOLD and "trend" in sig.reason


def test_incomplete_candle_ignored():
    closes = [2010 - i for i in range(20)] + [2005.0]
    candles = make_candles(closes + [1900.0])
    candles[-1].complete = False
    assert analyze(candles, P).action == BUY


def test_stops_for():
    sl, tp = stops_for(BUY, 2000, 4, StrategyParams(atr_sl_mult=1.5, risk_reward=2))
    assert (sl, tp) == (1994.0, 2012.0)
    sl, tp = stops_for(SELL, 2000, 4, StrategyParams(atr_sl_mult=1.5, risk_reward=2))
    assert (sl, tp) == (2006.0, 1988.0)


def test_position_size():
    # 1% od 10000 = 100 USD, stop 10 USD -> 10 unci
    assert position_size(10_000, 1.0, 2000, 1990, 50) == 10.0
    assert position_size(10_000, 1.0, 2000, 1990, 5) == 5.0  # maks
    assert position_size(10_000, 1.0, 2000, 1997, 50, precision=0) == 33  # zaokruženo naniže
    assert position_size(10_000, 1.0, 2000, 2000, 50) == 0.0
    assert position_size(0, 1.0, 2000, 1990, 50) == 0.0


def test_daily_loss_pct():
    assert daily_loss_pct(10_000, 9_700) == pytest.approx(3.0)
    assert daily_loss_pct(10_000, 10_100) == pytest.approx(-1.0)
