"""Brokeri: PaperBroker (simulacija) i OandaBroker (pravi/demo OANDA račun)."""

from __future__ import annotations

import json
import logging
import math
import os
import tempfile
from typing import Protocol

from .data import DataError, OandaClient, PriceFeed, parse_oanda_time
from .models import BUY, SELL, ClosedTrade, Position, Quote, utcnow

log = logging.getLogger(__name__)


class BrokerError(RuntimeError):
    pass


class Broker(Protocol):
    name: str
    units_precision: int

    async def quote(self) -> Quote: ...

    async def balance(self) -> float: ...

    async def equity(self) -> float: ...

    async def positions(self) -> list[Position]: ...

    async def normalize_units(self, units: float) -> float:
        """Zaokruži količinu (unce) NANIŽE na ono što broker prihvata."""
        ...

    async def open(self, side: str, units: float, stop_loss: float | None, take_profit: float | None) -> Position: ...

    async def close(self, position_id: str, reason: str = "Ručno zatvaranje") -> ClosedTrade: ...

    async def sync(self) -> list[ClosedTrade]:
        """Provjeri SL/TP i vrati pozicije zatvorene od zadnje provjere."""
        ...


def _floor(units: float, precision: int) -> float:
    factor = 10**precision
    return math.floor(units * factor + 1e-9) / factor


def _direction(side: str) -> int:
    if side == BUY:
        return 1
    if side == SELL:
        return -1
    raise BrokerError(f"Nepoznata strana: {side}")


# --------------------------------------------------------------------------- Paper


class PaperBroker:
    """Simulirani račun. Stanje se čuva u JSON fajlu da preživi restart."""

    name = "Paper (simulacija)"
    units_precision = 2

    def __init__(self, feed: PriceFeed, start_balance: float, spread: float, state_file: str | None) -> None:
        self.feed = feed
        self.spread = spread
        self.state_file = state_file
        self._balance = start_balance
        self._positions: dict[str, Position] = {}
        self.history: list[ClosedTrade] = []
        self._next_id = 1
        self._load()

    # ---- perzistencija
    def _load(self) -> None:
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, encoding="utf-8") as f:
                data = json.load(f)
            self._balance = float(data["balance"])
            self._next_id = int(data.get("next_id", 1))
            self._positions = {p["id"]: Position.from_dict(p) for p in data.get("positions", [])}
            self.history = [ClosedTrade.from_dict(t) for t in data.get("history", [])]
            log.info("Učitano paper stanje: saldo %.2f, %d pozicija", self._balance, len(self._positions))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.error("Ne mogu učitati %s: %s - krećem iz početka", self.state_file, exc)

    def _save(self) -> None:
        if not self.state_file:
            return
        data = {
            "balance": self._balance,
            "next_id": self._next_id,
            "positions": [p.to_dict() for p in self._positions.values()],
            "history": [t.to_dict() for t in self.history[-500:]],
        }
        directory = os.path.dirname(os.path.abspath(self.state_file))
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.state_file)

    # ---- cijene
    async def quote(self) -> Quote:
        q = await self.feed.get_quote()
        mid = q.mid
        return Quote(bid=round(mid - self.spread / 2, 3), ask=round(mid + self.spread / 2, 3), time=q.time)

    def _mark(self, q: Quote) -> None:
        for p in self._positions.values():
            exit_price = q.bid if p.side == BUY else q.ask
            p.unrealized_pl = round((exit_price - p.entry_price) * p.units * _direction(p.side), 2)

    # ---- račun
    async def balance(self) -> float:
        return round(self._balance, 2)

    async def equity(self) -> float:
        if self._positions:
            self._mark(await self.quote())
        return round(self._balance + sum(p.unrealized_pl for p in self._positions.values()), 2)

    async def positions(self) -> list[Position]:
        if self._positions:
            self._mark(await self.quote())
        return list(self._positions.values())

    async def normalize_units(self, units: float) -> float:
        return _floor(units, self.units_precision)

    # ---- nalozi
    async def open(self, side: str, units: float, stop_loss: float | None, take_profit: float | None) -> Position:
        _direction(side)
        if units <= 0:
            raise BrokerError("Količina mora biti veća od 0")
        q = await self.quote()
        entry = q.ask if side == BUY else q.bid
        pos = Position(
            id=f"P{self._next_id}",
            side=side,
            units=units,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=utcnow(),
        )
        self._next_id += 1
        self._positions[pos.id] = pos
        self._save()
        return pos

    def _close_at(self, pos: Position, exit_price: float, reason: str) -> ClosedTrade:
        pnl = round((exit_price - pos.entry_price) * pos.units * _direction(pos.side), 2)
        self._balance += pnl
        trade = ClosedTrade(
            id=pos.id,
            side=pos.side,
            units=pos.units,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            pnl=pnl,
            reason=reason,
            opened_at=pos.opened_at,
            closed_at=utcnow(),
        )
        del self._positions[pos.id]
        self.history.append(trade)
        self._save()
        return trade

    async def close(self, position_id: str, reason: str = "Ručno zatvaranje") -> ClosedTrade:
        pos = self._positions.get(position_id)
        if pos is None:
            raise BrokerError(f"Pozicija {position_id} ne postoji")
        q = await self.quote()
        return self._close_at(pos, q.bid if pos.side == BUY else q.ask, reason)

    async def sync(self) -> list[ClosedTrade]:
        if not self._positions:
            return []
        return self.check_stops(await self.quote())

    def check_stops(self, q: Quote) -> list[ClosedTrade]:
        """Zatvori pozicije kojima je cijena dotakla SL ili TP."""
        closed = []
        for pos in list(self._positions.values()):
            if pos.side == BUY:
                px = q.bid
                if pos.stop_loss is not None and px <= pos.stop_loss:
                    closed.append(self._close_at(pos, min(px, pos.stop_loss), "Stop loss"))
                elif pos.take_profit is not None and px >= pos.take_profit:
                    closed.append(self._close_at(pos, pos.take_profit, "Take profit"))
            else:
                px = q.ask
                if pos.stop_loss is not None and px >= pos.stop_loss:
                    closed.append(self._close_at(pos, max(px, pos.stop_loss), "Stop loss"))
                elif pos.take_profit is not None and px <= pos.take_profit:
                    closed.append(self._close_at(pos, pos.take_profit, "Take profit"))
        self._mark(q)
        return closed


# --------------------------------------------------------------------------- OANDA


class OandaBroker:
    """OANDA v20. SL/TP se postavljaju na serveru brokera (rade i kad bot ne radi)."""

    units_precision = 0  # XAU_USD na OANDA: cijele unce

    def __init__(self, api: OandaClient, feed: PriceFeed, instrument: str = "XAU_USD") -> None:
        self.api = api
        self.feed = feed
        self.instrument = instrument
        env = "LIVE" if "fxtrade" in api.base else "DEMO"
        self.name = f"OANDA {env}"
        self._known_trade_ids: set[str] | None = None

    async def quote(self) -> Quote:
        return await self.feed.get_quote()

    async def _summary(self) -> dict:
        return (await self.api.request("GET", self.api.account_path("/summary")))["account"]

    async def balance(self) -> float:
        return round(float((await self._summary())["balance"]), 2)

    async def equity(self) -> float:
        return round(float((await self._summary())["NAV"]), 2)

    async def positions(self) -> list[Position]:
        data = await self.api.request("GET", self.api.account_path("/openTrades"))
        out = []
        for t in data.get("trades", []):
            if t.get("instrument") != self.instrument:
                continue
            units = float(t["currentUnits"])
            out.append(
                Position(
                    id=str(t["id"]),
                    side=BUY if units > 0 else SELL,
                    units=abs(units),
                    entry_price=float(t["price"]),
                    stop_loss=float(t["stopLossOrder"]["price"]) if t.get("stopLossOrder") else None,
                    take_profit=float(t["takeProfitOrder"]["price"]) if t.get("takeProfitOrder") else None,
                    opened_at=parse_oanda_time(t["openTime"]),
                    unrealized_pl=float(t.get("unrealizedPL", 0.0)),
                )
            )
        return out

    async def normalize_units(self, units: float) -> float:
        return _floor(units, self.units_precision)

    async def open(self, side: str, units: float, stop_loss: float | None, take_profit: float | None) -> Position:
        units_int = int(units)
        if units_int < 1:
            raise BrokerError("OANDA zahtijeva barem 1 uncu")
        order: dict = {
            "type": "MARKET",
            "instrument": self.instrument,
            "units": str(units_int * _direction(side)),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
        }
        if stop_loss is not None:
            order["stopLossOnFill"] = {"price": f"{stop_loss:.2f}", "timeInForce": "GTC"}
        if take_profit is not None:
            order["takeProfitOnFill"] = {"price": f"{take_profit:.2f}", "timeInForce": "GTC"}
        try:
            data = await self.api.request("POST", self.api.account_path("/orders"), json={"order": order})
        except DataError as exc:
            raise BrokerError(str(exc)) from exc
        if "orderCancelTransaction" in data:
            raise BrokerError(f"Nalog odbijen: {data['orderCancelTransaction'].get('reason')}")
        fill = data.get("orderFillTransaction") or {}
        opened = fill.get("tradeOpened")
        if not opened:
            raise BrokerError(f"Nalog nije otvorio poziciju: {json.dumps(fill)[:300]}")
        pos = Position(
            id=str(opened["tradeID"]),
            side=side,
            units=abs(float(opened["units"])),
            entry_price=float(opened.get("price", fill.get("price"))),
            stop_loss=stop_loss,
            take_profit=take_profit,
            opened_at=utcnow(),
        )
        if self._known_trade_ids is not None:
            self._known_trade_ids.add(pos.id)
        return pos

    async def close(self, position_id: str, reason: str = "Ručno zatvaranje") -> ClosedTrade:
        positions = {p.id: p for p in await self.positions()}
        pos = positions.get(position_id)
        if pos is None:
            raise BrokerError(f"Pozicija {position_id} ne postoji")
        try:
            data = await self.api.request("PUT", self.api.account_path(f"/trades/{position_id}/close"))
        except DataError as exc:
            raise BrokerError(str(exc)) from exc
        fill = data.get("orderFillTransaction") or {}
        if self._known_trade_ids is not None:
            self._known_trade_ids.discard(position_id)
        return ClosedTrade(
            id=pos.id,
            side=pos.side,
            units=pos.units,
            entry_price=pos.entry_price,
            exit_price=float(fill.get("price", 0.0)),
            pnl=round(float(fill.get("pl", 0.0)), 2),
            reason=reason,
            opened_at=pos.opened_at,
            closed_at=utcnow(),
        )

    async def sync(self) -> list[ClosedTrade]:
        """Otkrij trejdove koje je OANDA zatvorila (SL/TP) od zadnje provjere."""
        current = {p.id for p in await self.positions()}
        if self._known_trade_ids is None:
            self._known_trade_ids = current
            return []
        gone = self._known_trade_ids - current
        self._known_trade_ids = current
        closed = []
        for trade_id in gone:
            try:
                t = (await self.api.request("GET", self.api.account_path(f"/trades/{trade_id}")))["trade"]
            except (DataError, KeyError) as exc:
                log.warning("Ne mogu dohvatiti zatvoreni trade %s: %s", trade_id, exc)
                continue
            units = float(t["initialUnits"])
            reason = "Zatvoreno na brokeru"
            if t.get("stopLossOrder", {}).get("state") == "FILLED":
                reason = "Stop loss"
            elif t.get("takeProfitOrder", {}).get("state") == "FILLED":
                reason = "Take profit"
            closed.append(
                ClosedTrade(
                    id=trade_id,
                    side=BUY if units > 0 else SELL,
                    units=abs(units),
                    entry_price=float(t["price"]),
                    exit_price=float(t.get("averageClosePrice", 0.0)),
                    pnl=round(float(t.get("realizedPL", 0.0)), 2),
                    reason=reason,
                    opened_at=parse_oanda_time(t["openTime"]),
                    closed_at=parse_oanda_time(t["closeTime"]) if t.get("closeTime") else utcnow(),
                )
            )
        return closed
