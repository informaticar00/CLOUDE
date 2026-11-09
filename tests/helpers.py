from datetime import datetime, timedelta, timezone

from goldbot.models import Candle, Quote


def make_candles(closes, start=None, step_min=15, spread=1.0):
    start = start or datetime(2026, 1, 5, tzinfo=timezone.utc)
    return [
        Candle(start + timedelta(minutes=step_min * i), c, c + spread, c - spread, c, True)
        for i, c in enumerate(closes)
    ]


class FakeFeed:
    name = "fake"

    def __init__(self, closes=None, price=2000.0):
        self.candles = make_candles(closes or [2000.0] * 60)
        self.price = price

    async def get_candles(self, timeframe, count):
        return self.candles[-count:]

    async def get_quote(self):
        return Quote(self.price, self.price)
