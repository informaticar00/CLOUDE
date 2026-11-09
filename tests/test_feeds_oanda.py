import asyncio
import json

import httpx

from goldbot.broker import OandaBroker
from goldbot.data import OandaClient, OandaFeed, YahooFeed
from goldbot.models import BUY, SELL


def run(coro):
    return asyncio.run(coro)


def test_yahoo_parsing_skips_nulls_and_marks_incomplete():
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"regularMarketPrice": 2400.5},
                    "timestamp": [1_700_000_000, 1_700_000_900, 4_000_000_000],
                    "indicators": {
                        "quote": [
                            {
                                "open": [1, None, 3],
                                "high": [2, 2, 4],
                                "low": [0.5, 1, 2],
                                "close": [1.5, 1.6, 3.5],
                            }
                        ]
                    },
                }
            ]
        }
    }
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))

    async def go():
        async with httpx.AsyncClient(transport=transport) as c:
            feed = YahooFeed(c)
            return await feed.get_candles("M15", 100), await feed.get_quote()

    candles, quote = run(go())
    assert len(candles) == 2
    assert candles[0].complete and not candles[1].complete  # budućnost = u toku
    assert quote.bid == quote.ask == 2400.5


def _oanda_handler(calls):
    def handler(req: httpx.Request):
        calls.append((req.method, req.url.path, req.content))
        p = req.url.path
        if p.endswith("/candles"):
            return httpx.Response(200, json={"candles": [
                {"time": "2026-01-05T10:00:00.000000000Z", "complete": True,
                 "mid": {"o": "2000.1", "h": "2003", "l": "1999", "c": "2002.5"}}]})
        if p.endswith("/pricing"):
            return httpx.Response(200, json={"prices": [{"bids": [{"price": "2000.10"}], "asks": [{"price": "2000.45"}]}]})
        if p.endswith("/orders"):
            return httpx.Response(201, json={"orderFillTransaction": {
                "price": "2000.45", "tradeOpened": {"tradeID": "77", "units": "-3", "price": "2000.10"}}})
        if p.endswith("/openTrades"):
            return httpx.Response(200, json={"trades": [{
                "id": "77", "instrument": "XAU_USD", "currentUnits": "-3", "price": "2000.10",
                "openTime": "2026-01-05T10:00:00.123456789Z", "unrealizedPL": "-1.5",
                "stopLossOrder": {"price": "2010.00"}, "takeProfitOrder": {"price": "1980.00"}}]})
        if p.endswith("/trades/77/close"):
            return httpx.Response(200, json={"orderFillTransaction": {"price": "1995.00", "pl": "15.30"}})
        if p.endswith("/summary"):
            return httpx.Response(200, json={"account": {"balance": "1000.00", "NAV": "998.5"}})
        return httpx.Response(404, json={"errorMessage": "nope"})
    return handler


def test_oanda_feed_and_broker():
    calls = []
    transport = httpx.MockTransport(_oanda_handler(calls))

    async def go():
        async with httpx.AsyncClient(transport=transport) as c:
            api = OandaClient(c, "key", "001-ACC", "practice")
            feed = OandaFeed(api)
            broker = OandaBroker(api, feed)
            candles = await feed.get_candles("M15", 10)
            quote = await broker.quote()
            pos = await broker.open(SELL, 3.7, 2010.0, 1980.0)
            positions = await broker.positions()
            closed = await broker.close("77")
            return broker, candles, quote, pos, positions, closed, await broker.balance(), await broker.equity()

    broker, candles, quote, pos, positions, closed, bal, eq = run(go())
    assert broker.name == "OANDA DEMO"
    assert candles[0].close == 2002.5
    assert (quote.bid, quote.ask) == (2000.10, 2000.45)
    order = json.loads([c for c in calls if c[1].endswith("/orders")][0][2])["order"]
    assert order["units"] == "-3"  # zaokruženo na cijele unce, SELL = negativno
    assert order["stopLossOnFill"]["price"] == "2010.00"
    assert pos.id == "77" and pos.side == SELL and pos.units == 3
    assert positions[0].side == SELL and positions[0].stop_loss == 2010.0
    assert closed.pnl == 15.30
    assert (bal, eq) == (1000.0, 998.5)
