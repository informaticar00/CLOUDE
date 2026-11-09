"""MetaTrader 5: izvor cijena i broker.

Koristi zvanični Python paket `MetaTrader5`, koji radi SAMO na Windowsu i
zahtijeva da je MT5 terminal instaliran (i po mogućnosti pokrenut i prijavljen).

Bot interno računa u UNCAMA, a MT5 trguje u LOTOVIMA. Pretvaranje radi preko
`trade_contract_size` simbola (kod većine brokera 1 lot XAUUSD = 100 unci).
Bot upravlja samo pozicijama sa svojim MAGIC brojem; tvoje ručne pozicije
otvorene u terminalu ne dira.
"""

from __future__ import annotations

import asyncio
import functools
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable

from .broker import BrokerError
from .data import DataError
from .models import BUY, SELL, Candle, ClosedTrade, Position, Quote, utcnow

TIMEFRAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "D": "TIMEFRAME_D1",
}
ACCOUNT_MODES = {0: "DEMO", 1: "CONTEST", 2: "REAL"}


def _ts(value: int | float) -> datetime:
    # MT5 vraća vrijeme servera brokera kao unix sekunde
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


class Mt5Client:
    """Drži vezu s terminalom. Svi MT5 pozivi idu kroz JEDAN pozadinski thread,
    jer MetaTrader5 paket nije thread-safe, a ne smije blokirati Telegram petlju."""

    def __init__(
        self,
        login: int | None = None,
        password: str = "",
        server: str = "",
        path: str = "",
        module: Any = None,
    ) -> None:
        if module is None:
            try:
                import MetaTrader5 as module  # type: ignore[no-redef]
            except ImportError as exc:
                raise DataError(
                    "Paket MetaTrader5 nije instaliran. Radi samo na Windowsu: pip install MetaTrader5"
                ) from exc
        self.mt5 = module
        self.login = login
        self.password = password
        self.server = server
        self.path = path
        self._connected = False
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mt5")

    def _ensure_connected(self) -> None:
        if self._connected and self.mt5.terminal_info() is not None:
            return
        kwargs: dict[str, Any] = {}
        if self.path:
            kwargs["path"] = self.path
        if self.login:
            kwargs.update(login=int(self.login), password=self.password, server=self.server)
        if not self.mt5.initialize(**kwargs):
            err = self.mt5.last_error()
            self.mt5.shutdown()
            raise DataError(f"Ne mogu se spojiti na MT5 terminal: {err}")
        self._connected = True

    def _run_sync(self, func: Callable[[Any], Any]) -> Any:
        self._ensure_connected()
        return func(self.mt5)

    async def run(self, func: Callable[[Any], Any]) -> Any:
        loop = asyncio.get_running_loop()
        try:
            return await loop.run_in_executor(self._executor, functools.partial(self._run_sync, func))
        except (DataError, BrokerError):
            raise
        except Exception as exc:  # noqa: BLE001 - MT5 baca razne greške
            self._connected = False
            raise DataError(f"MT5 greška: {exc}") from exc


def _symbol_info(mt5: Any, symbol: str) -> Any:
    if not mt5.symbol_select(symbol, True):
        raise DataError(
            f"Simbol {symbol} ne postoji kod brokera ({mt5.last_error()}). "
            "Provjeri tačan naziv u Market Watch (npr. XAUUSD, XAUUSD.m, GOLD) i postavi MT5_SYMBOL."
        )
    info = mt5.symbol_info(symbol)
    if info is None:
        raise DataError(f"Nema podataka za simbol {symbol}: {mt5.last_error()}")
    return info


class Mt5Feed:
    def __init__(self, client: Mt5Client, symbol: str = "XAUUSD") -> None:
        self.client = client
        self.symbol = symbol
        self.name = f"MetaTrader 5 ({symbol})"

    async def get_candles(self, timeframe: str, count: int) -> list[Candle]:
        def fetch(mt5: Any) -> list[tuple]:
            _symbol_info(mt5, self.symbol)
            rates = mt5.copy_rates_from_pos(self.symbol, getattr(mt5, TIMEFRAMES[timeframe]), 0, count)
            if rates is None:
                raise DataError(f"MT5 nije vratio svijeće: {mt5.last_error()}")
            return [(r["time"], r["open"], r["high"], r["low"], r["close"]) for r in rates]

        rows = await self.client.run(fetch)
        candles = [Candle(_ts(t), float(o), float(h), float(l), float(c), True) for t, o, h, l, c in rows]
        if candles:
            candles[-1].complete = False  # pozicija 0 = svijeća koja se još formira
        return candles

    async def get_quote(self) -> Quote:
        def fetch(mt5: Any) -> Quote:
            _symbol_info(mt5, self.symbol)
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                raise DataError(f"MT5 nema cijenu za {self.symbol}: {mt5.last_error()}")
            return Quote(bid=float(tick.bid), ask=float(tick.ask))

        return await self.client.run(fetch)


class Mt5Broker:
    units_precision = 2

    def __init__(
        self,
        client: Mt5Client,
        feed: Mt5Feed,
        symbol: str = "XAUUSD",
        magic: int = 20260,
        deviation: int = 50,
        allow_real_money: bool = False,
    ) -> None:
        self.client = client
        self.feed = feed
        self.symbol = symbol
        self.magic = magic
        self.deviation = deviation
        self.allow_real_money = allow_real_money
        self.name = "MetaTrader 5"
        self._known: set[str] | None = None

    # ---- pomoćne
    @staticmethod
    def _lots(units: float, info: Any) -> float:
        """Unce -> lotovi, zaokruženo NANIŽE na volume_step. 0 ako je ispod minimuma."""
        step = info.volume_step or 0.01
        lots = math.floor(units / info.trade_contract_size / step + 1e-9) * step
        lots = round(min(lots, info.volume_max), 8)
        return lots if lots >= info.volume_min else 0.0

    @staticmethod
    def _filling(mt5: Any, info: Any) -> int:
        mode = getattr(info, "filling_mode", 0)
        if mode & 1:
            return mt5.ORDER_FILLING_FOK
        if mode & 2:
            return mt5.ORDER_FILLING_IOC
        return mt5.ORDER_FILLING_RETURN

    def _send(self, mt5: Any, request: dict) -> Any:
        result = mt5.order_send(request)
        if result is None:
            raise BrokerError(f"MT5 order_send nije uspio: {mt5.last_error()}")
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            hint = ""
            if result.retcode == 10027:
                hint = " - uključi 'Algo Trading' dugme u MT5 terminalu"
            elif result.retcode == 10016:
                hint = " - SL/TP preblizu cijeni"
            raise BrokerError(f"Nalog odbijen (kod {result.retcode}: {result.comment}){hint}")
        return result

    def _to_position(self, mt5: Any, p: Any, contract: float) -> Position:
        return Position(
            id=str(p.ticket),
            side=BUY if p.type == mt5.POSITION_TYPE_BUY else SELL,
            units=round(p.volume * contract, 4),
            entry_price=float(p.price_open),
            stop_loss=float(p.sl) or None,
            take_profit=float(p.tp) or None,
            opened_at=_ts(p.time),
            unrealized_pl=round(float(p.profit), 2),
        )

    def _my_positions(self, mt5: Any) -> list[Any]:
        return [p for p in (mt5.positions_get(symbol=self.symbol) or []) if p.magic == self.magic]

    def _account(self, mt5: Any) -> Any:
        acc = mt5.account_info()
        if acc is None:
            raise BrokerError(f"MT5 nema podataka o računu (jesi li prijavljen?): {mt5.last_error()}")
        self.name = f"MetaTrader 5 {ACCOUNT_MODES.get(acc.trade_mode, '')} #{acc.login}".strip()
        return acc

    # ---- Broker interfejs
    async def quote(self) -> Quote:
        return await self.feed.get_quote()

    async def balance(self) -> float:
        return round(float((await self.client.run(self._account)).balance), 2)

    async def equity(self) -> float:
        return round(float((await self.client.run(self._account)).equity), 2)

    async def normalize_units(self, units: float) -> float:
        def calc(mt5: Any) -> float:
            info = _symbol_info(mt5, self.symbol)
            return round(self._lots(units, info) * info.trade_contract_size, 4)

        return await self.client.run(calc)

    async def positions(self) -> list[Position]:
        def fetch(mt5: Any) -> list[Position]:
            contract = _symbol_info(mt5, self.symbol).trade_contract_size
            return [self._to_position(mt5, p, contract) for p in self._my_positions(mt5)]

        return await self.client.run(fetch)

    async def open(self, side: str, units: float, stop_loss: float | None, take_profit: float | None) -> Position:
        if side not in (BUY, SELL):
            raise BrokerError(f"Nepoznata strana: {side}")

        def send(mt5: Any) -> Position:
            acc = self._account(mt5)
            if acc.trade_mode == 2 and not self.allow_real_money:
                raise BrokerError(
                    "Ovo je PRAVI (REAL) račun, a ALLOW_REAL_MONEY nije uključen u .env. "
                    "Postavi ALLOW_REAL_MONEY=true i restartuj bota ako stvarno želiš trgovati pravim novcem."
                )
            info = _symbol_info(mt5, self.symbol)
            lots = self._lots(units, info)
            if lots <= 0:
                raise BrokerError(
                    f"Premala pozicija: minimum je {info.volume_min} lot = "
                    f"{info.volume_min * info.trade_contract_size:g} oz"
                )
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                raise BrokerError(f"Nema cijene za {self.symbol}")
            is_buy = side == BUY
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lots,
                "type": mt5.ORDER_TYPE_BUY if is_buy else mt5.ORDER_TYPE_SELL,
                "price": tick.ask if is_buy else tick.bid,
                "deviation": self.deviation,
                "magic": self.magic,
                "comment": "goldbot",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self._filling(mt5, info),
            }
            if stop_loss is not None:
                request["sl"] = round(stop_loss, info.digits)
            if take_profit is not None:
                request["tp"] = round(take_profit, info.digits)
            result = self._send(mt5, request)
            ticket = str(result.order)
            if self._known is not None:
                self._known.add(ticket)
            return Position(
                id=ticket,
                side=side,
                units=round(lots * info.trade_contract_size, 4),
                entry_price=float(result.price or request["price"]),
                stop_loss=request.get("sl"),
                take_profit=request.get("tp"),
                opened_at=utcnow(),
            )

        return await self.client.run(send)

    def _closed_trade(self, mt5: Any, ticket: str, fallback: Position | None, reason: str | None) -> ClosedTrade | None:
        deals = mt5.history_deals_get(position=int(ticket)) or []
        if not deals and fallback is None:
            return None
        ins = [d for d in deals if d.entry == mt5.DEAL_ENTRY_IN]
        outs = [d for d in deals if d.entry != mt5.DEAL_ENTRY_IN]
        pnl = sum(float(d.profit) + float(d.commission) + float(d.swap) for d in deals)
        if reason is None:
            reason = "Zatvoreno na brokeru"
            if outs and outs[-1].reason == mt5.DEAL_REASON_SL:
                reason = "Stop loss"
            elif outs and outs[-1].reason == mt5.DEAL_REASON_TP:
                reason = "Take profit"
        contract = _symbol_info(mt5, self.symbol).trade_contract_size
        first_in = ins[0] if ins else None
        side = fallback.side if fallback else (BUY if first_in and first_in.type == mt5.DEAL_TYPE_BUY else SELL)
        return ClosedTrade(
            id=ticket,
            side=side,
            units=fallback.units if fallback else round(float(first_in.volume if first_in else 0) * contract, 4),
            entry_price=fallback.entry_price if fallback else float(first_in.price if first_in else 0),
            exit_price=float(outs[-1].price) if outs else 0.0,
            pnl=round(pnl if deals else (fallback.unrealized_pl if fallback else 0.0), 2),
            reason=reason,
            opened_at=fallback.opened_at if fallback else (_ts(first_in.time) if first_in else utcnow()),
            closed_at=_ts(outs[-1].time) if outs else utcnow(),
        )

    async def close(self, position_id: str, reason: str = "Ručno zatvaranje") -> ClosedTrade:
        def send(mt5: Any) -> ClosedTrade:
            matches = [p for p in self._my_positions(mt5) if str(p.ticket) == str(position_id)]
            if not matches:
                raise BrokerError(f"Pozicija {position_id} ne postoji (ili nije otvorena od bota)")
            p = matches[0]
            info = _symbol_info(mt5, self.symbol)
            before = self._to_position(mt5, p, info.trade_contract_size)
            tick = mt5.symbol_info_tick(self.symbol)
            is_buy = p.type == mt5.POSITION_TYPE_BUY
            self._send(
                mt5,
                {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": self.symbol,
                    "volume": p.volume,
                    "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
                    "position": p.ticket,
                    "price": tick.bid if is_buy else tick.ask,
                    "deviation": self.deviation,
                    "magic": self.magic,
                    "comment": "goldbot close",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": self._filling(mt5, info),
                },
            )
            if self._known is not None:
                self._known.discard(str(position_id))
            return self._closed_trade(mt5, str(position_id), before, reason)

        return await self.client.run(send)

    async def sync(self) -> list[ClosedTrade]:
        """Otkrij pozicije koje je MT5 zatvorio (SL/TP) od zadnje provjere."""

        def check(mt5: Any) -> list[ClosedTrade]:
            current = {str(p.ticket) for p in self._my_positions(mt5)}
            if self._known is None:
                self._known = current
                return []
            gone = self._known - current
            self._known = current
            out = []
            for ticket in sorted(gone):
                trade = self._closed_trade(mt5, ticket, None, None)
                if trade:
                    out.append(trade)
            return out

        return await self.client.run(check)
