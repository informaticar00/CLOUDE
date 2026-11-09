"""Trading engine: spaja izvor cijena, strategiju, rizik i brokera."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime

from . import fmt
from .broker import Broker, BrokerError
from .config import Settings
from .data import PriceFeed
from .models import BUY, HOLD, SELL, utcnow
from .risk import daily_loss_pct, position_size
from .strategy import Signal, analyze, stops_for

log = logging.getLogger(__name__)


@dataclass
class OrderPlan:
    side: str
    units: float
    entry: float
    stop_loss: float
    take_profit: float
    risk_usd: float
    close_ids: list[str]


class TradingEngine:
    def __init__(self, settings: Settings, feed: PriceFeed, broker: Broker) -> None:
        self.settings = settings
        self.feed = feed
        self.broker = broker
        self.auto_enabled = settings.auto_trade_on_start
        self.last_signal: Signal | None = None
        self.last_bar_time: datetime | None = None
        self.last_error: str | None = None
        self._day: date | None = None
        self._day_start_equity: float | None = None
        self.halted_today = False
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ analiza
    async def analyze(self) -> Signal:
        count = self.settings.strategy.min_candles() + 100
        candles = await self.feed.get_candles(self.settings.timeframe, count)
        return analyze(candles, self.settings.strategy)

    # ------------------------------------------------------------------ dnevni limit
    async def _check_daily_limit(self) -> list[str]:
        today = utcnow().date()
        equity = await self.broker.equity()
        if self._day != today:
            self._day = today
            self._day_start_equity = equity
            if self.halted_today:
                self.halted_today = False
                return ["🔄 Novi dan - dnevni limit gubitka resetovan."]
            return []
        loss = daily_loss_pct(self._day_start_equity or equity, equity)
        if not self.halted_today and loss >= self.settings.daily_loss_limit_pct:
            self.halted_today = True
            return [
                f"🛑 <b>Dnevni limit gubitka dostignut</b> ({loss:.2f}% ≥ "
                f"{self.settings.daily_loss_limit_pct:.2f}%). Auto-trading pauziran do sutra (UTC)."
            ]
        return []

    def reset_bar_tracking(self) -> None:
        """Pozovi nakon promjene strategije/timeframea da se stari signal ne izvrši."""
        self.last_bar_time = None

    def daily_loss(self, equity: float) -> float:
        if self._day_start_equity is None:
            return 0.0
        return daily_loss_pct(self._day_start_equity, equity)

    # ------------------------------------------------------------------ glavna petlja
    async def tick(self) -> list[str]:
        """Pozove se periodično. Vraća poruke za slanje korisniku."""
        async with self._lock:
            msgs: list[str] = []
            for trade in await self.broker.sync():
                msgs.append(fmt.closed(trade))
            msgs += await self._check_daily_limit()

            sig = await self.analyze()
            if sig.candle_time == self.last_bar_time:
                return msgs
            first_run = self.last_bar_time is None
            self.last_bar_time = sig.candle_time
            self.last_signal = sig
            if first_run or sig.action == HOLD:
                return msgs

            if not self.auto_enabled:
                msgs.append("📣 <b>Novi signal</b> (auto-trading je ISKLJUČEN)\n" + fmt.signal(sig))
            elif self.halted_today:
                msgs.append("📣 Signal ignorisan - dnevni limit gubitka.\n" + fmt.signal(sig))
            else:
                msgs.append("📣 <b>Novi signal</b>\n" + fmt.signal(sig))
                msgs += await self._execute_locked(sig.action, sig=sig, auto=True)
            return msgs

    # ------------------------------------------------------------------ nalozi
    async def plan(self, side: str, units: float | None = None, sig: Signal | None = None) -> OrderPlan:
        if side not in (BUY, SELL):
            raise BrokerError(f"Nepoznata strana: {side}")
        sig = sig or await self.analyze()
        if sig.atr is None:
            raise BrokerError("Nema dovoljno podataka za ATR - ne mogu izračunati stop loss")
        quote = await self.broker.quote()
        entry = quote.ask if side == BUY else quote.bid
        sl, tp = stops_for(side, entry, sig.atr, self.settings.strategy)

        positions = await self.broker.positions()
        close_ids = [p.id for p in positions if p.side != side]
        remaining = len(positions) - len(close_ids)
        if remaining >= self.settings.max_open_positions:
            raise BrokerError(
                f"Već imaš {remaining} otvorenu poziciju u istom smjeru "
                f"(maks. {self.settings.max_open_positions})."
            )

        if units is None:
            balance = await self.broker.balance()
            units = position_size(balance, self.settings.risk_pct, entry, sl, self.settings.max_units, 4)
        else:
            units = min(units, self.settings.max_units)
        units = await self.broker.normalize_units(units)
        if units <= 0:
            raise BrokerError(
                "Količina je 0 nakon zaokruživanja (premali saldo, prevelik stop "
                "ili ispod minimalne veličine kod brokera)."
            )
        return OrderPlan(side, units, entry, sl, tp, round(abs(entry - sl) * units, 2), close_ids)

    async def _execute_locked(
        self, side: str, units: float | None = None, sig: Signal | None = None, auto: bool = False
    ) -> list[str]:
        msgs: list[str] = []
        try:
            plan = await self.plan(side, units, sig)
        except BrokerError as exc:
            return [f"⚠️ Nalog nije poslan: {exc}"]
        for pid in plan.close_ids:
            try:
                msgs.append(fmt.closed(await self.broker.close(pid, "Suprotan signal")))
            except BrokerError as exc:
                return msgs + [f"⚠️ Ne mogu zatvoriti #{pid}: {exc}"]
        try:
            pos = await self.broker.open(plan.side, plan.units, plan.stop_loss, plan.take_profit)
        except BrokerError as exc:
            return msgs + [f"⚠️ Nalog odbijen: {exc}"]
        log.info("Otvorena pozicija %s", pos)
        msgs.append(fmt.opened(pos, "Auto-trade" if auto else "Ručni nalog") + f"\nRizik: ~{plan.risk_usd:,.2f} USD")
        return msgs

    async def execute(self, side: str, units: float | None = None) -> list[str]:
        async with self._lock:
            return await self._execute_locked(side, units)

    async def close(self, position_id: str | None = None) -> list[str]:
        """Zatvori jednu ili (ako je position_id None) sve pozicije."""
        async with self._lock:
            ids = [position_id] if position_id else [p.id for p in await self.broker.positions()]
            if not ids:
                return ["Nema otvorenih pozicija."]
            msgs = []
            for pid in ids:
                try:
                    msgs.append(fmt.closed(await self.broker.close(pid)))
                except BrokerError as exc:
                    msgs.append(f"⚠️ #{pid}: {exc}")
            return msgs
