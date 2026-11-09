"""Zajedničke strukture podataka."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

BUY = "BUY"
SELL = "SELL"
HOLD = "HOLD"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Candle:
    time: datetime  # vrijeme otvaranja svijeće (UTC)
    open: float
    high: float
    low: float
    close: float
    complete: bool = True


@dataclass
class Quote:
    bid: float
    ask: float
    time: datetime = field(default_factory=utcnow)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass
class Position:
    id: str
    side: str  # BUY ili SELL
    units: float
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
    unrealized_pl: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["opened_at"] = self.opened_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        d = dict(d)
        d["opened_at"] = datetime.fromisoformat(d["opened_at"])
        return cls(**d)


@dataclass
class ClosedTrade:
    id: str
    side: str
    units: float
    entry_price: float
    exit_price: float
    pnl: float
    reason: str
    opened_at: datetime
    closed_at: datetime

    def to_dict(self) -> dict:
        d = asdict(self)
        d["opened_at"] = self.opened_at.isoformat()
        d["closed_at"] = self.closed_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ClosedTrade":
        d = dict(d)
        d["opened_at"] = datetime.fromisoformat(d["opened_at"])
        d["closed_at"] = datetime.fromisoformat(d["closed_at"])
        return cls(**d)
