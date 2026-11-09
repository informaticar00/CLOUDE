"""Lažni MetaTrader5 modul za testove (pravi radi samo na Windowsu)."""

from types import SimpleNamespace as NS


class FakeMT5:
    TIMEFRAME_M1, TIMEFRAME_M5, TIMEFRAME_M15, TIMEFRAME_M30, TIMEFRAME_H1, TIMEFRAME_D1 = 1, 5, 15, 30, 16385, 16408
    TRADE_ACTION_DEAL = 1
    ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
    POSITION_TYPE_BUY, POSITION_TYPE_SELL = 0, 1
    DEAL_TYPE_BUY, DEAL_TYPE_SELL = 0, 1
    ORDER_TIME_GTC = 0
    ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN = 0, 1, 2
    TRADE_RETCODE_DONE = 10009
    DEAL_ENTRY_IN, DEAL_ENTRY_OUT = 0, 1
    DEAL_REASON_CLIENT, DEAL_REASON_SL, DEAL_REASON_TP = 0, 4, 5

    def __init__(self):
        self.initialized = False
        self.init_kwargs = None
        self.bid, self.ask = 2000.0, 2000.3
        self.positions = []
        self.deals = []
        self.requests = []
        self.next_ticket = 1000
        self.balance = 5000.0
        self.reject_code = None
        self.info = NS(trade_contract_size=100.0, volume_min=0.01, volume_max=50.0, volume_step=0.01,
                       digits=2, filling_mode=2)

    # veza
    def initialize(self, **kw):
        self.init_kwargs = kw
        self.initialized = True
        return True

    def shutdown(self):
        self.initialized = False

    def terminal_info(self):
        return NS(connected=True) if self.initialized else None

    def last_error(self):
        return (1, "fake error")

    # podaci
    def symbol_select(self, symbol, enable):
        return symbol == "XAUUSD"

    def symbol_info(self, symbol):
        return self.info

    def symbol_info_tick(self, symbol):
        return NS(bid=self.bid, ask=self.ask, time=0)

    def copy_rates_from_pos(self, symbol, tf, start, count):
        rows = [{"time": 1_767_600_000 + 900 * i, "open": 2000.0 + i, "high": 2001.0 + i,
                 "low": 1999.0 + i, "close": 2000.5 + i} for i in range(300)]
        return rows[-count:]

    def account_info(self):
        equity = self.balance + sum(p.profit for p in self.positions)
        return NS(balance=self.balance, equity=equity, trade_mode=0, login=123456)

    # trgovanje
    def positions_get(self, symbol=None, ticket=None):
        return tuple(self.positions)

    def order_send(self, req):
        self.requests.append(req)
        if self.reject_code:
            return NS(retcode=self.reject_code, comment="rejected", order=0, price=0)
        self.next_ticket += 1
        t = self.next_ticket
        if "position" in req:  # zatvaranje
            pos = next(p for p in self.positions if p.ticket == req["position"])
            sign = 1 if pos.type == self.POSITION_TYPE_BUY else -1
            profit = (req["price"] - pos.price_open) * pos.volume * 100 * sign
            self.positions.remove(pos)
            self.balance += profit
            self.deals.append(NS(position_id=pos.ticket, entry=self.DEAL_ENTRY_OUT, reason=self.DEAL_REASON_CLIENT,
                                 price=req["price"], profit=profit, commission=0.0, swap=0.0,
                                 type=req["type"], volume=req["volume"], time=1_767_700_000))
            return NS(retcode=self.TRADE_RETCODE_DONE, comment="done", order=t, price=req["price"])
        pos = NS(ticket=t, type=req["type"], volume=req["volume"], price_open=req["price"],
                 sl=req.get("sl", 0.0), tp=req.get("tp", 0.0), time=1_767_600_000, profit=0.0, magic=req["magic"])
        self.positions.append(pos)
        self.deals.append(NS(position_id=t, entry=self.DEAL_ENTRY_IN, reason=0, price=req["price"], profit=0.0,
                             commission=-3.5, swap=0.0, type=req["type"], volume=req["volume"], time=1_767_600_000))
        return NS(retcode=self.TRADE_RETCODE_DONE, comment="done", order=t, price=req["price"])

    def history_deals_get(self, position=None):
        return tuple(d for d in self.deals if d.position_id == position)

    # pomoć za test: broker zatvori poziciju na SL
    def hit_stop_loss(self, ticket):
        pos = next(p for p in self.positions if p.ticket == ticket)
        sign = 1 if pos.type == self.POSITION_TYPE_BUY else -1
        profit = (pos.sl - pos.price_open) * pos.volume * 100 * sign
        self.positions.remove(pos)
        self.balance += profit
        self.deals.append(NS(position_id=ticket, entry=self.DEAL_ENTRY_OUT, reason=self.DEAL_REASON_SL,
                             price=pos.sl, profit=profit, commission=0.0, swap=0.0, type=1 - pos.type,
                             volume=pos.volume, time=1_767_700_000))
