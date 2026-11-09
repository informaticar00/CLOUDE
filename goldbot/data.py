"""Izvori cijena: Yahoo Finance (besplatno) i OANDA."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

import httpx

from .models import Candle, Quote, utcnow

TIMEFRAME_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "D": 86400}


class DataError(RuntimeError):
    pass


class PriceFeed(Protocol):
    name: str

    async def get_candles(self, timeframe: str, count: int) -> list[Candle]: ...

    async def get_quote(self) -> Quote: ...


# --------------------------------------------------------------------------- Yahoo


class YahooFeed:
    """Zlato preko Yahoo Finance (GC=F - COMEX gold futures). Bez API ključa.

    Napomena: futures cijena se malo razlikuje od spot XAU/USD; za papirno
    trgovanje i signale je to dovoljno dobro.
    """

    name = "Yahoo Finance (GC=F)"
    URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    _INTERVALS = {
        "M1": ("1m", "5d"),
        "M5": ("5m", "1mo"),
        "M15": ("15m", "1mo"),
        "M30": ("30m", "1mo"),
        "H1": ("60m", "3mo"),
        "D": ("1d", "2y"),
    }

    def __init__(self, client: httpx.AsyncClient, symbol: str = "GC=F") -> None:
        self.client = client
        self.symbol = symbol

    async def _fetch(self, interval: str, rng: str) -> dict:
        try:
            r = await self.client.get(
                self.URL.format(symbol=self.symbol),
                params={"interval": interval, "range": rng},
                headers={"User-Agent": "Mozilla/5.0 (goldbot)"},
                timeout=20,
            )
            r.raise_for_status()
            result = r.json()["chart"]["result"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise DataError(f"Yahoo greška: {exc}") from exc
        if not result:
            raise DataError("Yahoo nije vratio podatke")
        return result[0]

    async def get_candles(self, timeframe: str, count: int) -> list[Candle]:
        interval, rng = self._INTERVALS[timeframe]
        res = await self._fetch(interval, rng)
        stamps = res.get("timestamp") or []
        q = res["indicators"]["quote"][0]
        step = TIMEFRAME_SECONDS[timeframe]
        now = utcnow()
        candles: list[Candle] = []
        for i, ts in enumerate(stamps):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            if None in (o, h, l, c):
                continue
            t = datetime.fromtimestamp(ts, tz=timezone.utc)
            candles.append(
                Candle(t, float(o), float(h), float(l), float(c), complete=t + timedelta(seconds=step) <= now)
            )
        return candles[-count:]

    async def get_quote(self) -> Quote:
        res = await self._fetch("1m", "1d")
        price = res.get("meta", {}).get("regularMarketPrice")
        if price is None:
            raise DataError("Yahoo nije vratio trenutnu cijenu")
        price = float(price)
        return Quote(bid=price, ask=price)


# --------------------------------------------------------------------------- OANDA


class OandaClient:
    """Minimalni klijent za OANDA v20 REST API."""

    URLS = {
        "practice": "https://api-fxpractice.oanda.com/v3",
        "live": "https://api-fxtrade.oanda.com/v3",
    }

    def __init__(self, client: httpx.AsyncClient, api_key: str, account_id: str, env: str = "practice") -> None:
        self.client = client
        self.base = self.URLS[env]
        self.account_id = account_id
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept-Datetime-Format": "RFC3339",
        }

    async def request(self, method: str, path: str, **kwargs) -> dict:
        try:
            r = await self.client.request(method, self.base + path, headers=self.headers, timeout=20, **kwargs)
        except httpx.HTTPError as exc:
            raise DataError(f"OANDA mrežna greška: {exc}") from exc
        if r.status_code >= 400:
            try:
                msg = r.json().get("errorMessage", r.text)
            except ValueError:
                msg = r.text
            raise DataError(f"OANDA greška {r.status_code}: {msg}")
        return r.json()

    def account_path(self, suffix: str = "") -> str:
        return f"/accounts/{self.account_id}{suffix}"


def parse_oanda_time(value: str) -> datetime:
    # OANDA vraća nanosekunde: 2024-01-01T00:00:00.000000000Z
    value = value.rstrip("Z")
    if "." in value:
        head, frac = value.split(".", 1)
        value = f"{head}.{frac[:6]}"
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


class OandaFeed:
    name = "OANDA (XAU_USD)"

    def __init__(self, api: OandaClient, instrument: str = "XAU_USD") -> None:
        self.api = api
        self.instrument = instrument

    async def get_candles(self, timeframe: str, count: int) -> list[Candle]:
        data = await self.api.request(
            "GET",
            f"/instruments/{self.instrument}/candles",
            params={"granularity": timeframe, "count": min(count, 5000), "price": "M"},
        )
        out = []
        for c in data.get("candles", []):
            m = c["mid"]
            out.append(
                Candle(
                    parse_oanda_time(c["time"]),
                    float(m["o"]),
                    float(m["h"]),
                    float(m["l"]),
                    float(m["c"]),
                    complete=bool(c.get("complete", True)),
                )
            )
        return out

    async def get_quote(self) -> Quote:
        data = await self.api.request(
            "GET", self.api.account_path("/pricing"), params={"instruments": self.instrument}
        )
        prices = data.get("prices") or []
        if not prices:
            raise DataError("OANDA nije vratio cijenu")
        p = prices[0]
        return Quote(bid=float(p["bids"][0]["price"]), ask=float(p["asks"][0]["price"]))
