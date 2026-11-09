import asyncio

import pytest

from goldbot.broker import BrokerError
from goldbot.config import ConfigError, Settings
from goldbot.data import DataError
from goldbot.engine import TradingEngine
from goldbot.models import BUY, SELL
from goldbot.mt5 import Mt5Broker, Mt5Client, Mt5Feed

from .fake_mt5 import FakeMT5, NS


def setup(magic=20260):
    fake = FakeMT5()
    client = Mt5Client(login=123456, password="pw", server="Demo-Server", module=fake)
    feed = Mt5Feed(client, "XAUUSD")
    return fake, feed, Mt5Broker(client, feed, "XAUUSD", magic=magic)


def run(coro):
    return asyncio.run(coro)


def test_connects_with_credentials_and_reads_candles():
    fake, feed, _ = setup()
    candles = run(feed.get_candles("M15", 50))
    assert fake.init_kwargs == {"login": 123456, "password": "pw", "server": "Demo-Server"}
    assert len(candles) == 50
    assert all(c.complete for c in candles[:-1]) and not candles[-1].complete
    q = run(feed.get_quote())
    assert (q.bid, q.ask) == (2000.0, 2000.3)


def test_unknown_symbol_gives_helpful_error():
    fake = FakeMT5()
    feed = Mt5Feed(Mt5Client(module=fake), "GOLDX")
    with pytest.raises(DataError, match="MT5_SYMBOL"):
        run(feed.get_quote())


def test_units_to_lots_rounding():
    _, _, broker = setup()
    assert run(broker.normalize_units(7.89)) == 7.0  # 0.0789 lot -> 0.07 lot = 7 oz
    assert run(broker.normalize_units(0.5)) == 0.0  # ispod 0.01 lota
    assert run(broker.normalize_units(10_000)) == 5000.0  # volume_max 50 lota


def test_open_sends_correct_request_and_close():
    fake, _, broker = setup()
    pos = run(broker.open(BUY, 12.0, 1990.123, 2020.0))
    req = fake.requests[-1]
    assert req["volume"] == 0.12 and req["type"] == fake.ORDER_TYPE_BUY
    assert req["price"] == 2000.3 and req["sl"] == 1990.12 and req["tp"] == 2020.0
    assert req["type_filling"] == fake.ORDER_FILLING_IOC
    assert pos.units == 12.0 and pos.side == BUY
    assert broker.name == "MetaTrader 5 DEMO #123456"

    positions = run(broker.positions())
    assert [(p.id, p.side, p.units, p.stop_loss) for p in positions] == [(pos.id, BUY, 12.0, 1990.12)]

    fake.bid = 2010.0
    trade = run(broker.close(pos.id))
    # (2010 - 2000.3) * 0.12 lota * 100 = 116.4, minus provizija 3.5
    assert trade.pnl == pytest.approx(112.9)
    assert run(broker.positions()) == []


def test_ignores_positions_with_other_magic():
    fake, _, broker = setup()
    fake.positions.append(NS(ticket=1, type=0, volume=1.0, price_open=1900, sl=0.0, tp=0.0, time=0, profit=0.0, magic=0))
    assert run(broker.positions()) == []
    with pytest.raises(BrokerError):
        run(broker.close("1"))


def test_rejected_order_has_hint():
    fake, _, broker = setup()
    fake.reject_code = 10027
    with pytest.raises(BrokerError, match="Algo Trading"):
        run(broker.open(SELL, 5, 2010, 1980))


def test_sync_detects_stop_loss():
    fake, _, broker = setup()
    assert run(broker.sync()) == []
    pos = run(broker.open(SELL, 10, 2010.0, 1980.0))
    fake.hit_stop_loss(int(pos.id))
    closed = run(broker.sync())
    assert len(closed) == 1
    t = closed[0]
    assert t.reason == "Stop loss" and t.side == SELL and t.exit_price == 2010.0
    assert t.pnl == pytest.approx((2000.0 - 2010.0) * 0.1 * 100 - 3.5)


def test_engine_with_mt5_sizes_in_lots():
    fake, feed, broker = setup()
    s = Settings(telegram_token="x", allowed_chat_ids={1}, mode="mt5", data_source="mt5", risk_pct=1.0)
    eng = TradingEngine(s, feed, broker)
    plan = run(eng.plan(BUY))
    # units mora biti cijeli broj koraka od 0.01 lota (1 oz)
    assert plan.units == int(plan.units) and plan.units > 0
    assert plan.risk_usd <= 5000 * 0.01 + 1e-6


def test_config_mt5_validation():
    Settings(telegram_token="x", allowed_chat_ids={1}, mode="mt5", data_source="mt5").validate()
    with pytest.raises(ConfigError):
        Settings(telegram_token="x", allowed_chat_ids={1}, mode="mt5", data_source="yahoo").validate()
    with pytest.raises(ConfigError):
        Settings(telegram_token="x", allowed_chat_ids={1}, mode="mt5", data_source="mt5", mt5_login=1).validate()
    Settings(mode="paper").validate(require_telegram=False)
