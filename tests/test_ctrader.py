"""cTrader protokol protiv lažnog servera (JSON preko WebSocketa)."""

import asyncio
import json

import pytest

from goldbot.broker import BrokerError
from goldbot.ctrader import (
    CTraderBroker, CTraderClient, CTraderFeed, CTraderSymbol, DataError, TokenStore,
)
from goldbot.models import BUY, SELL


class FakeServer:
    def __init__(self, live=False, accounts=None):
        self.live = live
        self.accounts = accounts or [{"ctidTraderAccountId": 77, "isLive": live, "traderLogin": 5551, "brokerTitleShort": "TestFX"}]
        self.urls, self.sent = [], []
        self.balance = 1_000_000  # 10000.00 uz moneyDigits 2
        self.positions = {}
        self.deals = {}
        self.next_id = 100
        self.bid, self.ask = 2000.10, 2000.40
        self.fail_order = None

    async def connect(self, url):
        self.urls.append(url)
        return FakeWS(self)

    def handle(self, ws, msg):
        t, p, mid = msg["payloadType"], msg.get("payload", {}), msg.get("clientMsgId")
        self.sent.append(msg)
        out = lambda pt, pl, m=mid: ws.q.put_nowait(json.dumps({"payloadType": pt, "payload": pl, **({"clientMsgId": m} if m else {})}))
        if t == 51:
            return
        if t == 2100:
            out(2101, {})
        elif t == 2173:
            out(2174, {"accessToken": "new-acc", "tokenType": "bearer", "expiresIn": 2628000, "refreshToken": "new-ref"})
        elif t == 2149:
            out(2150, {"accessToken": p["accessToken"], "ctidTraderAccount": self.accounts})
        elif t == 2102:
            out(2103, {"ctidTraderAccountId": p["ctidTraderAccountId"]})
        elif t == 2114:
            out(2115, {"symbol": [{"symbolId": 1, "symbolName": "EURUSD"}, {"symbolId": 41, "symbolName": "XAUUSD"}]})
        elif t == 2116:
            out(2117, {"symbol": [{"symbolId": 41, "digits": 2, "pipPosition": 1, "minVolume": 100, "stepVolume": 100, "maxVolume": 1000000}]})
        elif t == 2121:
            out(2122, {"trader": {"ctidTraderAccountId": 77, "balance": self.balance, "moneyDigits": 2}})
        elif t == 2127:
            out(2128, {})
            out(2131, {"symbolId": 41, "bid": int(self.bid * 1e5), "ask": int(self.ask * 1e5)}, None)
        elif t == 2137:
            bars = [{"low": 200000000 + i * 10000, "deltaOpen": 5000, "deltaHigh": 20000, "deltaClose": 15000,
                     "utcTimestampInMinutes": 29_000_000 + i * 15, "volume": 1} for i in range(p["count"])]
            out(2138, {"trendbar": bars})
        elif t == 2124:
            out(2125, {"position": list(self.positions.values())})
        elif t == 2106:
            if self.fail_order:
                out(2132, {"errorCode": self.fail_order, "description": "nope"})
                return
            self.next_id += 1
            side = p["tradeSide"]
            price = self.ask if side == 1 else self.bid
            sign = 1 if side == 1 else -1
            pos = {"positionId": self.next_id, "price": price, "swap": 0, "commission": -70, "moneyDigits": 2,
                   "tradeData": {"symbolId": p["symbolId"], "volume": p["volume"], "tradeSide": side,
                                 "openTimestamp": 1_767_600_000_000, "label": p.get("label")},
                   "stopLoss": round(price - sign * p["relativeStopLoss"] / 1e5, 2),
                   "takeProfit": round(price + sign * p["relativeTakeProfit"] / 1e5, 2)}
            self.positions[self.next_id] = pos
            out(2126, {"executionType": 2, "order": {}})
            out(2126, {"executionType": 3, "position": pos, "deal": {"positionId": self.next_id, "executionPrice": price}})
        elif t == 2111:
            pos = self.positions.pop(p["positionId"])
            side = pos["tradeData"]["tradeSide"]
            exit_p = self.bid if side == 1 else self.ask
            gross = round((exit_p - pos["price"]) * p["volume"] / 100 * (1 if side == 1 else -1) * 100)
            deal = {"positionId": p["positionId"], "executionPrice": exit_p,
                    "closePositionDetail": {"grossProfit": gross, "swap": 0, "commission": -70, "moneyDigits": 2}}
            self.deals[p["positionId"]] = [deal]
            out(2126, {"executionType": 3, "deal": deal})
        elif t == 2179:
            out(2180, {"deal": self.deals.get(p["positionId"], []), "hasMore": False})
        else:
            out(2142, {"errorCode": "UNKNOWN_REQ"})

    def hit_sl(self, pid):
        pos = self.positions.pop(pid)
        sl = pos["stopLoss"]
        sign = 1 if pos["tradeData"]["tradeSide"] == 1 else -1
        gross = round((sl - pos["price"]) * pos["tradeData"]["volume"] / 100 * sign * 100)
        self.deals[pid] = [{"positionId": pid, "executionPrice": sl, "executionTimestamp": 1_767_700_000_000,
                            "closePositionDetail": {"grossProfit": gross, "swap": 0, "commission": -70, "moneyDigits": 2}}]


class FakeWS:
    def __init__(self, server):
        self.server, self.q = server, asyncio.Queue()

    async def send(self, raw):
        self.server.handle(self, json.loads(raw))

    async def recv(self):
        return await self.q.get()

    async def close(self):
        pass


def build(tmp_path, live=False, allow=False, accounts=None, login=None):
    srv = FakeServer(live, accounts)
    tokens = TokenStore(str(tmp_path / "tok.json"), "acc", "ref")
    client = CTraderClient("cid", "secret", tokens, login, connector=srv.connect)
    feed = CTraderFeed(client, CTraderSymbol(client, "XAUUSD"))
    return srv, tokens, client, feed, CTraderBroker(client, feed, allow_real_money=allow)


def run(coro):
    return asyncio.run(coro)


def test_login_refresh_and_data(tmp_path):
    async def go():
        srv, tokens, client, feed, broker = build(tmp_path)
        candles = await feed.get_candles("M15", 50)
        q = await feed.get_quote()
        bal = await broker.balance()
        await client.close()
        return srv, tokens, broker, candles, q, bal
    srv, tokens, broker, candles, q, bal = run(go())
    assert srv.urls == ["wss://demo.ctraderapi.com:5036", "wss://demo.ctraderapi.com:5036"]
    assert tokens.access_token == "new-acc" and json.loads((tmp_path / "tok.json").read_text())["refreshToken"] == "new-ref"
    auth = next(m for m in srv.sent if m["payloadType"] == 2102)
    assert auth["payload"] == {"ctidTraderAccountId": 77, "accessToken": "new-acc"}
    assert len(candles) == 50 and candles[0].low == 2000.0 and candles[0].close == 2000.15
    assert (q.bid, q.ask) == (2000.10, 2000.40)
    assert bal == 10000.0
    assert broker.name == "cTrader TestFX DEMO #5551"


def test_live_account_uses_live_host(tmp_path):
    async def go():
        srv, _, client, _, broker = build(tmp_path, live=True)
        await broker.balance()
        await client.close()
        return srv
    assert run(go()).urls[-1] == "wss://live.ctraderapi.com:5036"


def test_open_close_and_sl_detection(tmp_path):
    async def go():
        srv, _, client, _, broker = build(tmp_path)
        assert await broker.normalize_units(7.89) == 7.0
        assert await broker.normalize_units(0.5) == 0.0
        assert await broker.sync() == []
        pos = await broker.open(BUY, 3, 1990.40, 2020.40)
        order = next(m for m in srv.sent if m["payloadType"] == 2106)["payload"]
        positions = await broker.positions()
        srv.bid = 2010.10
        trade = await broker.close(pos.id)
        pos2 = await broker.open(SELL, 2, 2010.10, 1980.10)
        srv.hit_sl(int(pos2.id))
        closed = await broker.sync()
        await client.close()
        return order, pos, positions, trade, closed
    order, pos, positions, trade, closed = run(go())
    assert order["volume"] == 300 and order["tradeSide"] == 1 and order["orderType"] == 1
    assert order["relativeStopLoss"] == 1_000_000 and order["relativeTakeProfit"] == 2_000_000
    assert "stopLoss" not in order  # market nalog: samo relativni SL/TP
    assert (pos.entry_price, pos.stop_loss, pos.take_profit, pos.units) == (2000.40, 1990.40, 2020.40, 3)
    assert positions[0].id == pos.id and positions[0].side == BUY
    assert trade.pnl == pytest.approx((2010.10 - 2000.40) * 3 - 0.70)
    assert len(closed) == 1 and closed[0].reason == "Stop loss" and closed[0].side == SELL
    assert closed[0].pnl == pytest.approx((2000.10 - 2010.10) * 2 - 0.70)


def test_real_money_guard_and_errors(tmp_path):
    async def go():
        srv, _, client, _, broker = build(tmp_path, live=True)
        with pytest.raises(BrokerError, match="ALLOW_REAL_MONEY"):
            await broker.open(BUY, 1, 1990, 2020)
        broker.allow_real_money = True
        srv.fail_order = "MARKET_CLOSED"
        with pytest.raises(BrokerError, match="zatvoreno"):
            await broker.open(BUY, 1, 1990, 2020)
        await client.close()
        return srv
    srv = run(go())
    assert sum(1 for m in srv.sent if m["payloadType"] == 2106) == 1


def test_account_selection(tmp_path):
    accs = [{"ctidTraderAccountId": 1, "isLive": False, "traderLogin": 10},
            {"ctidTraderAccountId": 2, "isLive": True, "traderLogin": 20}]
    async def go(login):
        srv, _, client, _, broker = build(tmp_path, accounts=accs, login=login)
        try:
            await broker.balance()
            return client.account_id, client.is_live
        finally:
            await client.close()
    with pytest.raises(DataError, match="CTRADER_ACCOUNT"):
        run(go(None))
    assert run(go(20)) == (2, True)
