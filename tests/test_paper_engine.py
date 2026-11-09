import asyncio
from dataclasses import replace

import pytest

from goldbot.broker import BrokerError, PaperBroker
from goldbot.config import Settings, StrategyParams
from goldbot.engine import TradingEngine
from goldbot.models import BUY, SELL

from .helpers import FakeFeed, make_candles


def run(coro):
    return asyncio.run(coro)


def test_paper_open_close_pnl(tmp_path):
    feed = FakeFeed(price=2000.0)
    b = PaperBroker(feed, 10_000, spread=0.0, state_file=str(tmp_path / "s.json"))
    pos = run(b.open(BUY, 2, 1990, 2020))
    feed.price = 2005.0
    assert run(b.equity()) == 10_010.0
    t = run(b.close(pos.id))
    assert t.pnl == 10.0
    assert run(b.balance()) == 10_010.0

    # stanje preživi restart
    b2 = PaperBroker(feed, 10_000, spread=0.0, state_file=str(tmp_path / "s.json"))
    assert run(b2.balance()) == 10_010.0 and len(b2.history) == 1


def test_paper_spread_costs_money():
    feed = FakeFeed(price=2000.0)
    b = PaperBroker(feed, 10_000, spread=0.5, state_file=None)
    pos = run(b.open(BUY, 10, None, None))
    assert pos.entry_price == 2000.25
    assert run(b.close(pos.id)).pnl == -5.0


def test_paper_stop_loss_and_take_profit():
    feed = FakeFeed(price=2000.0)
    b = PaperBroker(feed, 10_000, spread=0.0, state_file=None)
    run(b.open(BUY, 1, 1990, 2020))
    run(b.open(SELL, 1, 2010, 1980))
    feed.price = 1985.0  # BUY pogađa SL (gap -> 1985), SELL ne još
    closed = run(b.sync())
    assert [(t.side, t.reason, t.exit_price) for t in closed] == [(BUY, "Stop loss", 1985.0)]
    feed.price = 1979.0
    closed = run(b.sync())
    assert [(t.side, t.reason, t.exit_price) for t in closed] == [(SELL, "Take profit", 1980.0)]
    assert run(b.balance()) == 10_000 - 15 + 20


def test_close_unknown_position():
    b = PaperBroker(FakeFeed(), 10_000, 0.0, None)
    with pytest.raises(BrokerError):
        run(b.close("P99"))


def _settings(**kw):
    s = Settings(
        telegram_token="x",
        allowed_chat_ids={1},
        strategy=StrategyParams(ema_fast=3, ema_slow=6, ema_trend=0, rsi_period=5, atr_period=5,
                                rsi_overbought=101, rsi_oversold=-1),
        risk_pct=1.0,
        max_units=50,
    )
    return replace(s, **kw)


def test_engine_auto_trades_on_new_signal_only():
    flat = [2000.0] * 20
    feed = FakeFeed(flat, price=2000.0)
    broker = PaperBroker(feed, 10_000, 0.0, None)
    eng = TradingEngine(_settings(auto_trade_on_start=True), feed, broker)

    assert run(eng.tick()) == []  # prvi prolaz samo pamti svijeću

    # nova svijeća sa BUY presjekom
    closes = [2010 - i for i in range(20)] + [2005.0]
    feed.candles = make_candles(closes)
    feed.price = 1995.0
    msgs = run(eng.tick())
    assert any("Auto-trade" in m for m in msgs)
    positions = run(broker.positions())
    assert len(positions) == 1 and positions[0].side == BUY
    # ista svijeća -> nema novog naloga
    assert run(eng.tick()) == []
    assert len(run(broker.positions())) == 1

    # suprotan signal zatvara BUY i otvara SELL
    feed.candles = make_candles([1990 + i for i in range(20)] + [1995.0 - 10], start=feed.candles[-1].time)
    msgs = run(eng.tick())
    positions = run(broker.positions())
    assert len(positions) == 1 and positions[0].side == SELL
    assert any("Suprotan signal" in m for m in msgs)


def test_engine_signal_only_when_auto_off():
    feed = FakeFeed([2000.0] * 20)
    broker = PaperBroker(feed, 10_000, 0.0, None)
    eng = TradingEngine(_settings(auto_trade_on_start=False), feed, broker)
    run(eng.tick())
    feed.candles = make_candles([2010 - i for i in range(20)] + [2005.0])
    msgs = run(eng.tick())
    assert any("ISKLJUČEN" in m for m in msgs)
    assert run(broker.positions()) == []


def test_engine_daily_loss_limit_halts():
    feed = FakeFeed([2000.0] * 20, price=2000.0)
    broker = PaperBroker(feed, 10_000, 0.0, None)
    eng = TradingEngine(_settings(daily_loss_limit_pct=3.0), feed, broker)
    run(eng.tick())
    run(broker.open(BUY, 10, None, None))
    feed.price = 1960.0  # -400 USD = -4%
    msgs = run(eng.tick())
    assert eng.halted_today and any("limit" in m for m in msgs)


def test_engine_manual_plan_respects_max_positions():
    feed = FakeFeed([2010 - i for i in range(20)] + [2005.0], price=2000.0)
    broker = PaperBroker(feed, 10_000, 0.0, None)
    eng = TradingEngine(_settings(), feed, broker)
    msgs = run(eng.execute(BUY))
    assert "Ručni nalog" in msgs[0]
    with pytest.raises(BrokerError):
        run(eng.plan(BUY))
    plan = run(eng.plan(SELL, units=3))
    assert plan.units == 3 and plan.close_ids == [run(broker.positions())[0].id]
