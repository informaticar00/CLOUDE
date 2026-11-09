"""cTrader Open API: izvor cijena i broker.

Bot se spaja direktno na cTrader servere preko interneta (WebSocket + JSON, port 5036),
bez ikakvog programa na računaru i bez Windowsa.

Potrebno (jednom):
  1. cTrader ID i račun (demo ili pravi) kod nekog cTrader brokera.
  2. Aplikacija na https://openapi.ctrader.com -> Client ID i Client Secret.
  3. `python -m goldbot --ctrader-login` -> pristupni token (čuva se u ctrader_token.json
     i automatski se obnavlja).

Jedinice: bot računa u uncama; cTrader volumen je u 0.01 jedinice (1 oz = 100).
Cijene u porukama su cijeli brojevi u 1/100000 (osim polja tipa double).
Bot upravlja samo pozicijama sa svojom oznakom (label), ručne pozicije ne dira.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import logging
import math
import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from .broker import BrokerError
from .data import TIMEFRAME_SECONDS, DataError
from .models import BUY, SELL, Candle, ClosedTrade, Position, Quote, utcnow

log = logging.getLogger(__name__)

HOSTS = {True: "wss://live.ctraderapi.com:5036", False: "wss://demo.ctraderapi.com:5036"}
AUTH_URL = "https://id.ctrader.com/my/settings/openapi/grantingaccess/"
TOKEN_URL = "https://openapi.ctrader.com/apps/token"

# Tipovi poruka (OpenApiModelMessages.proto / OpenApiCommonModelMessages.proto)
ERROR_RES = 50
HEARTBEAT = 51
APP_AUTH_REQ, APP_AUTH_RES = 2100, 2101
ACCOUNT_AUTH_REQ, ACCOUNT_AUTH_RES = 2102, 2103
NEW_ORDER_REQ = 2106
CLOSE_POSITION_REQ = 2111
SYMBOLS_LIST_REQ, SYMBOLS_LIST_RES = 2114, 2115
SYMBOL_BY_ID_REQ, SYMBOL_BY_ID_RES = 2116, 2117
TRADER_REQ, TRADER_RES = 2121, 2122
RECONCILE_REQ, RECONCILE_RES = 2124, 2125
EXECUTION_EVENT = 2126
SUBSCRIBE_SPOTS_REQ, SUBSCRIBE_SPOTS_RES = 2127, 2128
SPOT_EVENT = 2131
ORDER_ERROR_EVENT = 2132
GET_TRENDBARS_REQ, GET_TRENDBARS_RES = 2137, 2138
OA_ERROR_RES = 2142
TOKEN_INVALIDATED_EVENT = 2147
CLIENT_DISCONNECT_EVENT = 2148
ACCOUNTS_BY_TOKEN_REQ, ACCOUNTS_BY_TOKEN_RES = 2149, 2150
REFRESH_TOKEN_REQ, REFRESH_TOKEN_RES = 2173, 2174
DEALS_BY_POSITION_REQ, DEALS_BY_POSITION_RES = 2179, 2180

SIDE_TO_CT = {BUY: 1, SELL: 2}
CT_TO_SIDE = {1: BUY, 2: SELL}
MARKET = 1
EXEC_FILLED, EXEC_REJECTED = 3, 7
PERIODS = {"M1": 1, "M5": 5, "M15": 7, "M30": 8, "H1": 9, "D": 12}
# Maksimalni raspon jednog zahtjeva za svijeće (ms), po cTrader ograničenjima
MAX_RANGE_MS = {"M1": 302_400_000, "M5": 302_400_000, "M15": 21_168_000_000, "M30": 21_168_000_000,
                "H1": 21_168_000_000, "D": 31_622_400_000}
PRICE_SCALE = 100_000

ERROR_HINTS = {
    "CH_ACCESS_TOKEN_INVALID": "token je istekao ili je pogrešan - pokreni ctrader-login.bat",
    "CH_CLIENT_AUTH_FAILURE": "pogrešan CTRADER_CLIENT_ID ili CTRADER_CLIENT_SECRET",
    "CH_CLIENT_NOT_AUTHENTICATED": "aplikacija nije prijavljena",
    "ACCOUNT_NOT_AUTHORIZED": "token nema pristup ovom računu - ponovo pokreni ctrader-login.bat",
    "MARKET_CLOSED": "tržište je zatvoreno (vikend ili praznik)",
    "NOT_ENOUGH_MONEY": "nema dovoljno margine na računu",
    "TRADING_BAD_VOLUME": "neispravna količina za ovaj simbol",
    "TRADING_BAD_STOPS": "SL/TP preblizu cijeni - povećaj sl_atr u postavkama",
    "TRADING_DISABLED": "trgovanje je onemogućeno za ovaj račun ili simbol",
}


class CTraderError(DataError):
    def __init__(self, code: str, description: str = "") -> None:
        self.code = code
        hint = ERROR_HINTS.get(code, "")
        text = f"cTrader greška {code}"
        if description:
            text += f": {description}"
        if hint:
            text += f" ({hint})"
        super().__init__(text)


# --------------------------------------------------------------------------- token


class TokenStore:
    """Čuva access/refresh token u JSON fajlu (obnavlja se automatski)."""

    def __init__(self, path: str, access_token: str = "", refresh_token: str = "") -> None:
        self.path = path
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = 0.0
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                self.access_token = d.get("accessToken", "") or self.access_token
                self.refresh_token = d.get("refreshToken", "") or self.refresh_token
                self.expires_at = float(d.get("expiresAt", 0))
            except (OSError, ValueError) as exc:
                log.error("Ne mogu učitati %s: %s", path, exc)

    def update(self, access_token: str, refresh_token: str, expires_in: float) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token or self.refresh_token
        self.expires_at = time.time() + float(expires_in or 0)
        if not self.path:
            return
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                {"accessToken": self.access_token, "refreshToken": self.refresh_token, "expiresAt": self.expires_at},
                f,
                indent=2,
            )
        os.replace(tmp, self.path)

    def needs_refresh(self) -> bool:
        # Obnovi ako je nepoznato kad ističe ili ističe za manje od 7 dana
        return bool(self.refresh_token) and (self.expires_at == 0 or self.expires_at - time.time() < 7 * 86400)


def auth_url(client_id: str, redirect_uri: str) -> str:
    from urllib.parse import urlencode

    return AUTH_URL + "?" + urlencode(
        {"client_id": client_id, "redirect_uri": redirect_uri, "scope": "trading", "product": "web"}
    )


async def exchange_code(http: Any, client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict:
    """Zamijeni autorizacijski kod za token (OAuth2)."""
    r = await http.get(
        TOKEN_URL,
        params={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    try:
        data = r.json()
    except ValueError as exc:
        raise DataError(f"cTrader token: neočekivan odgovor ({r.status_code})") from exc
    if r.status_code >= 400 or not data.get("accessToken"):
        raise DataError(f"cTrader token greška: {data.get('description') or data.get('errorCode') or r.text[:200]}")
    return data


# --------------------------------------------------------------------------- konekcija


async def _ws_connect(url: str) -> Any:
    from websockets.asyncio.client import connect

    return await connect(url, open_timeout=20, ping_interval=None, max_size=16 * 1024 * 1024)


class CTraderClient:
    """Jedna trajna WebSocket konekcija, automatski reconnect, uparivanje odgovora po clientMsgId."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tokens: TokenStore,
        account_login: int | None = None,
        connector: Callable[[str], Awaitable[Any]] = _ws_connect,
        request_timeout: float = 20.0,
        heartbeat_interval: float = 10.0,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tokens = tokens
        self.account_login = account_login
        self.connector = connector
        self.request_timeout = request_timeout
        self.heartbeat_interval = heartbeat_interval

        self.account_id: int | None = None
        self.is_live: bool | None = None
        self.trader_login: int | None = None
        self.broker_name = ""

        self._ws: Any = None
        self._reader: asyncio.Task | None = None
        self._heartbeat: asyncio.Task | None = None
        self._pending: dict[str, asyncio.Queue] = {}
        self._ids = itertools.count(1)
        self._lock = asyncio.Lock()
        self._spot_symbols: set[int] = set()
        self.spots: dict[int, tuple[float | None, float | None]] = {}
        self.spot_event = asyncio.Event()

    # ---- niski nivo
    @property
    def connected(self) -> bool:
        return self._ws is not None and self._reader is not None and not self._reader.done()

    async def _open(self, live: bool) -> None:
        await self._close()
        try:
            self._ws = await self.connector(HOSTS[live])
        except Exception as exc:  # noqa: BLE001
            raise DataError(f"Ne mogu se spojiti na cTrader: {exc}") from exc
        self._reader = asyncio.create_task(self._read_loop())
        self._heartbeat = asyncio.create_task(self._heartbeat_loop())

    async def _close(self) -> None:
        for task in (self._reader, self._heartbeat):
            if task and not task.done():
                task.cancel()
        self._reader = self._heartbeat = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                pass
        self._ws = None
        self._spot_symbols.clear()
        self.spots.clear()
        for q in self._pending.values():
            q.put_nowait(None)  # probudi one koji čekaju
        self._pending.clear()

    async def _read_loop(self) -> None:
        ws = self._ws  # svaki čitač pripada samo svojoj konekciji
        try:
            while True:
                raw = await ws.recv()
                try:
                    msg = json.loads(raw)
                except ValueError:
                    log.warning("cTrader: neispravna poruka %r", raw[:200])
                    continue
                self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - veza pukla
            log.warning("cTrader veza prekinuta: %s", exc)
        finally:
            if self._ws is ws:  # ne diraj zahtjeve nove konekcije nakon reconnecta
                for q in self._pending.values():
                    q.put_nowait(None)

    def _dispatch(self, msg: dict) -> None:
        ptype = msg.get("payloadType")
        payload = msg.get("payload") or {}
        if ptype == HEARTBEAT:
            return
        if ptype == SPOT_EVENT:
            sid = int(payload.get("symbolId", 0))
            old_bid, old_ask = self.spots.get(sid, (None, None))
            bid = payload.get("bid")
            ask = payload.get("ask")
            self.spots[sid] = (
                int(bid) / PRICE_SCALE if bid is not None else old_bid,
                int(ask) / PRICE_SCALE if ask is not None else old_ask,
            )
            self.spot_event.set()
            return
        if ptype in (TOKEN_INVALIDATED_EVENT, CLIENT_DISCONNECT_EVENT):
            log.warning("cTrader je prekinuo sesiju (%s): %s", ptype, payload)
            asyncio.get_running_loop().create_task(self._close())
            return
        q = self._pending.get(msg.get("clientMsgId", ""))
        if q is not None:
            q.put_nowait(msg)

    async def _heartbeat_loop(self) -> None:
        ws = self._ws
        while True:
            await asyncio.sleep(self.heartbeat_interval)
            try:
                await ws.send(json.dumps({"payloadType": HEARTBEAT, "payload": {}}))
            except Exception:  # noqa: BLE001
                return

    async def _send(self, ptype: int, payload: dict) -> tuple[str, asyncio.Queue]:
        if self._ws is None:
            raise DataError("cTrader nije spojen")
        msg_id = f"gb{next(self._ids)}"
        q: asyncio.Queue = asyncio.Queue()
        self._pending[msg_id] = q
        try:
            await self._ws.send(json.dumps({"clientMsgId": msg_id, "payloadType": ptype, "payload": payload}))
        except Exception as exc:  # noqa: BLE001
            self._pending.pop(msg_id, None)
            raise DataError(f"cTrader slanje nije uspjelo: {exc}") from exc
        return msg_id, q

    @staticmethod
    def _raise_if_error(msg: dict) -> None:
        ptype = msg.get("payloadType")
        p = msg.get("payload") or {}
        if ptype in (OA_ERROR_RES, ERROR_RES, ORDER_ERROR_EVENT):
            raise CTraderError(str(p.get("errorCode", "UNKNOWN")), str(p.get("description", "")))

    async def _raw_request(
        self, ptype: int, payload: dict, done: Callable[[dict], bool], timeout: float | None = None
    ) -> dict:
        msg_id, q = await self._send(ptype, payload)
        try:
            deadline = time.monotonic() + (timeout or self.request_timeout)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise DataError("cTrader nije odgovorio na vrijeme")
                try:
                    msg = await asyncio.wait_for(q.get(), remaining)
                except asyncio.TimeoutError as exc:
                    raise DataError("cTrader nije odgovorio na vrijeme") from exc
                if msg is None:
                    raise DataError("cTrader veza je prekinuta")
                self._raise_if_error(msg)
                if done(msg):
                    return msg["payload"]
        finally:
            self._pending.pop(msg_id, None)

    async def _expect(self, ptype: int, payload: dict, res_type: int) -> dict:
        return await self._raw_request(ptype, payload, lambda m: m.get("payloadType") == res_type)

    # ---- prijava
    async def _login(self) -> None:
        if not self.tokens.access_token:
            raise DataError("Nema cTrader tokena. Pokreni ctrader-login.bat (python -m goldbot --ctrader-login)")
        # 1) spoji se bilo gdje da saznaš koji je račun demo/live
        await self._open(live=bool(self.is_live))
        await self._expect(APP_AUTH_REQ, {"clientId": self.client_id, "clientSecret": self.client_secret}, APP_AUTH_RES)
        if self.tokens.needs_refresh():
            try:
                r = await self._expect(REFRESH_TOKEN_REQ, {"refreshToken": self.tokens.refresh_token}, REFRESH_TOKEN_RES)
                self.tokens.update(r["accessToken"], r.get("refreshToken", ""), r.get("expiresIn", 0))
                log.info("cTrader token obnovljen")
            except CTraderError as exc:
                log.warning("Obnova tokena nije uspjela: %s", exc)
        if self.account_id is None:
            res = await self._expect(ACCOUNTS_BY_TOKEN_REQ, {"accessToken": self.tokens.access_token}, ACCOUNTS_BY_TOKEN_RES)
            acc = self.pick_account(res.get("ctidTraderAccount") or [], self.account_login)
            self.account_id = int(acc["ctidTraderAccountId"])
            self.is_live = bool(acc.get("isLive", False))
            self.trader_login = int(acc.get("traderLogin", 0)) or None
            self.broker_name = acc.get("brokerTitleShort", "") or ""
            # 2) live i demo računi su na različitim serverima
            await self._open(live=self.is_live)
            await self._expect(APP_AUTH_REQ, {"clientId": self.client_id, "clientSecret": self.client_secret}, APP_AUTH_RES)
        await self._expect(
            ACCOUNT_AUTH_REQ,
            {"ctidTraderAccountId": self.account_id, "accessToken": self.tokens.access_token},
            ACCOUNT_AUTH_RES,
        )
        log.info("cTrader spojen: račun %s (%s)", self.trader_login, "LIVE" if self.is_live else "DEMO")

    @staticmethod
    def pick_account(accounts: list[dict], login: int | None) -> dict:
        if not accounts:
            raise DataError("Token nema pristup nijednom cTrader računu. Ponovo pokreni ctrader-login.bat")
        if login:
            for a in accounts:
                if int(a.get("traderLogin", 0)) == int(login):
                    return a
            raise DataError(
                f"Račun {login} nije pronađen. Dostupni: "
                + ", ".join(f"{a.get('traderLogin')} ({'LIVE' if a.get('isLive') else 'DEMO'})" for a in accounts)
            )
        if len(accounts) > 1:
            raise DataError(
                "Token ima pristup više računa - upiši jedan u CTRADER_ACCOUNT. Dostupni: "
                + ", ".join(f"{a.get('traderLogin')} ({'LIVE' if a.get('isLive') else 'DEMO'})" for a in accounts)
            )
        return accounts[0]

    async def ensure(self) -> None:
        async with self._lock:
            if not self.connected:
                try:
                    await self._login()
                except BaseException:
                    await self._close()
                    raise

    # ---- javni API
    async def request(self, ptype: int, payload: dict, res_type: int) -> dict:
        await self.ensure()
        payload = {"ctidTraderAccountId": self.account_id, **payload}
        return await self._expect(ptype, payload, res_type)

    async def execute(self, ptype: int, payload: dict, timeout: float = 30.0) -> dict:
        """Pošalji nalog i čekaj ORDER_FILLED (ili grešku)."""
        await self.ensure()
        payload = {"ctidTraderAccountId": self.account_id, **payload}

        def done(m: dict) -> bool:
            if m.get("payloadType") != EXECUTION_EVENT:
                return False
            p = m.get("payload") or {}
            et = p.get("executionType")
            if et == EXEC_REJECTED:
                raise CTraderError(str(p.get("errorCode", "ORDER_REJECTED")), "nalog odbijen")
            return et == EXEC_FILLED

        return await self._raw_request(ptype, payload, done, timeout)

    async def subscribe_spots(self, symbol_id: int) -> None:
        await self.ensure()
        if symbol_id in self._spot_symbols:
            return
        await self.request(SUBSCRIBE_SPOTS_REQ, {"symbolId": [symbol_id]}, SUBSCRIBE_SPOTS_RES)
        self._spot_symbols.add(symbol_id)

    async def close(self) -> None:
        await self._close()


# --------------------------------------------------------------------------- simbol


class CTraderSymbol:
    def __init__(self, client: CTraderClient, name: str) -> None:
        self.client = client
        self.name = name
        self.id: int | None = None
        self.info: dict = {}
        self._account_id: int | None = None

    async def load(self) -> None:
        await self.client.ensure()
        if self.id is not None and self._account_id == self.client.account_id:
            return
        res = await self.client.request(SYMBOLS_LIST_REQ, {}, SYMBOLS_LIST_RES)
        symbols = res.get("symbol") or []
        wanted = self.name.upper()
        match = next((s for s in symbols if str(s.get("symbolName", "")).upper() == wanted), None)
        if match is None:
            gold = [s.get("symbolName") for s in symbols if "XAU" in str(s.get("symbolName", "")).upper()
                    or "GOLD" in str(s.get("symbolName", "")).upper()]
            raise DataError(
                f"Simbol {self.name} ne postoji kod ovog brokera. Postavi CTRADER_SYMBOL"
                + (f" (ponuđeno: {', '.join(gold[:10])})" if gold else "")
            )
        self.id = int(match["symbolId"])
        info = await self.client.request(SYMBOL_BY_ID_REQ, {"symbolId": [self.id]}, SYMBOL_BY_ID_RES)
        self.info = (info.get("symbol") or [{}])[0]
        self._account_id = self.client.account_id

    @property
    def digits(self) -> int:
        return int(self.info.get("digits", 2))

    def to_volume(self, units: float) -> int:
        """Unce -> cTrader volumen (0.01 jedinice), zaokruženo NANIŽE na korak. 0 ako je ispod minimuma."""
        step = int(self.info.get("stepVolume") or 1)
        vol = math.floor(units * 100 / step + 1e-9) * step
        max_vol = self.info.get("maxVolume")
        if max_vol:
            vol = min(vol, int(max_vol))
        return int(vol) if vol >= int(self.info.get("minVolume") or 1) else 0

    def relative(self, distance: float) -> int:
        """Udaljenost cijene -> relativni SL/TP u 1/100000, zaokruženo na preciznost simbola."""
        step = 10 ** max(0, 5 - self.digits)
        return max(step, int(round(distance * PRICE_SCALE / step)) * step)


# --------------------------------------------------------------------------- feed


class CTraderFeed:
    def __init__(self, client: CTraderClient, symbol: CTraderSymbol) -> None:
        self.client = client
        self.symbol = symbol
        self.name = f"cTrader ({symbol.name})"

    async def get_candles(self, timeframe: str, count: int) -> list[Candle]:
        await self.symbol.load()
        now_ms = int(time.time() * 1000)
        res = await self.client.request(
            GET_TRENDBARS_REQ,
            {
                "symbolId": self.symbol.id,
                "period": PERIODS[timeframe],
                "fromTimestamp": now_ms - MAX_RANGE_MS[timeframe],
                "toTimestamp": now_ms,
                "count": count,
            },
            GET_TRENDBARS_RES,
        )
        step = TIMEFRAME_SECONDS[timeframe]
        now = utcnow()
        candles = []
        for b in res.get("trendbar") or []:
            low = int(b.get("low", 0))
            t = datetime.fromtimestamp(int(b["utcTimestampInMinutes"]) * 60, tz=timezone.utc)
            candles.append(
                Candle(
                    t,
                    (low + int(b.get("deltaOpen", 0))) / PRICE_SCALE,
                    (low + int(b.get("deltaHigh", 0))) / PRICE_SCALE,
                    low / PRICE_SCALE,
                    (low + int(b.get("deltaClose", 0))) / PRICE_SCALE,
                    complete=t + timedelta(seconds=step) <= now,
                )
            )
        candles.sort(key=lambda c: c.time)
        return candles[-count:]

    async def get_quote(self) -> Quote:
        await self.symbol.load()
        await self.client.subscribe_spots(self.symbol.id)
        deadline = time.monotonic() + 10
        while True:
            bid, ask = self.client.spots.get(self.symbol.id, (None, None))
            if bid is not None and ask is not None:
                return Quote(bid=bid, ask=ask)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise DataError("cTrader ne šalje cijenu (tržište zatvoreno?)")
            self.client.spot_event.clear()
            try:
                await asyncio.wait_for(self.client.spot_event.wait(), remaining)
            except asyncio.TimeoutError:
                pass


# --------------------------------------------------------------------------- broker


class CTraderBroker:
    units_precision = 2

    def __init__(
        self,
        client: CTraderClient,
        feed: CTraderFeed,
        label: str = "goldbot",
        allow_real_money: bool = False,
    ) -> None:
        self.client = client
        self.feed = feed
        self.symbol = feed.symbol
        self.label = label
        self.allow_real_money = allow_real_money
        self._known: dict[str, Position] | None = None

    @property
    def name(self) -> str:
        if self.client.is_live is None:
            return "cTrader"
        kind = "LIVE" if self.client.is_live else "DEMO"
        broker = f" {self.client.broker_name}" if self.client.broker_name else ""
        return f"cTrader{broker} {kind} #{self.client.trader_login or self.client.account_id}"

    async def quote(self) -> Quote:
        return await self.feed.get_quote()

    async def balance(self) -> float:
        res = await self.client.request(TRADER_REQ, {}, TRADER_RES)
        t = res.get("trader") or {}
        return round(int(t.get("balance", 0)) / 10 ** int(t.get("moneyDigits", 2)), 2)

    async def equity(self) -> float:
        positions = await self.positions()
        return round(await self.balance() + sum(p.unrealized_pl for p in positions), 2)

    async def normalize_units(self, units: float) -> float:
        await self.symbol.load()
        return self.symbol.to_volume(units) / 100

    def _to_position(self, p: dict, quote: Quote | None) -> Position:
        td = p.get("tradeData") or {}
        side = CT_TO_SIDE.get(int(td.get("tradeSide", 1)), BUY)
        units = int(td.get("volume", 0)) / 100
        entry = float(p.get("price", 0.0))
        pl = 0.0
        if quote is not None:
            exit_price = quote.bid if side == BUY else quote.ask
            pl = (exit_price - entry) * units * (1 if side == BUY else -1)
            money = 10 ** int(p.get("moneyDigits", 2))
            pl += (int(p.get("swap", 0)) + int(p.get("commission", 0))) / money
        return Position(
            id=str(p["positionId"]),
            side=side,
            units=units,
            entry_price=entry,
            stop_loss=float(p["stopLoss"]) if p.get("stopLoss") else None,
            take_profit=float(p["takeProfit"]) if p.get("takeProfit") else None,
            opened_at=datetime.fromtimestamp(int(td.get("openTimestamp", 0)) / 1000, tz=timezone.utc),
            unrealized_pl=round(pl, 2),
        )

    async def _raw_positions(self) -> list[dict]:
        await self.symbol.load()
        res = await self.client.request(RECONCILE_REQ, {}, RECONCILE_RES)
        out = []
        for p in res.get("position") or []:
            td = p.get("tradeData") or {}
            if int(td.get("symbolId", 0)) == self.symbol.id and td.get("label") == self.label:
                out.append(p)
        return out

    async def positions(self) -> list[Position]:
        raw = await self._raw_positions()
        quote = await self.quote() if raw else None
        return [self._to_position(p, quote) for p in raw]

    async def open(self, side: str, units: float, stop_loss: float | None, take_profit: float | None) -> Position:
        if side not in SIDE_TO_CT:
            raise BrokerError(f"Nepoznata strana: {side}")
        await self.symbol.load()
        if self.client.is_live and not self.allow_real_money:
            raise BrokerError(
                "Ovo je PRAVI (LIVE) račun, a ALLOW_REAL_MONEY nije uključen u .env. "
                "Postavi ALLOW_REAL_MONEY=true i restartuj bota ako stvarno želiš trgovati pravim novcem."
            )
        volume = self.symbol.to_volume(units)
        if volume <= 0:
            min_oz = int(self.symbol.info.get("minVolume") or 1) / 100
            raise BrokerError(f"Premala pozicija: minimum je {min_oz:g} oz")
        q = await self.quote()
        ref = q.ask if side == BUY else q.bid
        order: dict = {
            "symbolId": self.symbol.id,
            "orderType": MARKET,
            "tradeSide": SIDE_TO_CT[side],
            "volume": volume,
            "label": self.label,
            "comment": "goldbot",
        }
        # Market nalozi ne primaju apsolutni SL/TP, samo relativnu udaljenost od cijene izvršenja
        if stop_loss is not None:
            order["relativeStopLoss"] = self.symbol.relative(abs(ref - stop_loss))
        if take_profit is not None:
            order["relativeTakeProfit"] = self.symbol.relative(abs(take_profit - ref))
        try:
            ev = await self.client.execute(NEW_ORDER_REQ, order)
        except DataError as exc:
            raise BrokerError(str(exc)) from exc
        p = ev.get("position") or {}
        deal = ev.get("deal") or {}
        entry = float(p.get("price") or deal.get("executionPrice") or ref)
        sign = 1 if side == BUY else -1
        sl = p.get("stopLoss") or (
            round(entry - sign * order["relativeStopLoss"] / PRICE_SCALE, self.symbol.digits)
            if "relativeStopLoss" in order else None)
        tp = p.get("takeProfit") or (
            round(entry + sign * order["relativeTakeProfit"] / PRICE_SCALE, self.symbol.digits)
            if "relativeTakeProfit" in order else None)
        pos = Position(
            id=str(p.get("positionId") or deal.get("positionId")),
            side=side,
            units=volume / 100,
            entry_price=entry,
            stop_loss=float(sl) if sl else None,
            take_profit=float(tp) if tp else None,
            opened_at=utcnow(),
        )
        if self._known is not None:
            self._known[pos.id] = pos
        return pos

    @staticmethod
    def _deal_pnl(deal: dict) -> float:
        d = deal.get("closePositionDetail") or {}
        money = 10 ** int(d.get("moneyDigits", deal.get("moneyDigits", 2)))
        return (int(d.get("grossProfit", 0)) + int(d.get("swap", 0)) + int(d.get("commission", 0))) / money

    async def close(self, position_id: str, reason: str = "Ručno zatvaranje") -> ClosedTrade:
        raw = {str(p["positionId"]): p for p in await self._raw_positions()}
        p = raw.get(str(position_id))
        if p is None:
            raise BrokerError(f"Pozicija {position_id} ne postoji (ili nije otvorena od bota)")
        before = self._to_position(p, None)
        try:
            ev = await self.client.execute(
                CLOSE_POSITION_REQ, {"positionId": int(position_id), "volume": int(p["tradeData"]["volume"])}
            )
        except DataError as exc:
            raise BrokerError(str(exc)) from exc
        deal = ev.get("deal") or {}
        if self._known is not None:
            self._known.pop(str(position_id), None)
        return ClosedTrade(
            id=before.id,
            side=before.side,
            units=before.units,
            entry_price=before.entry_price,
            exit_price=float(deal.get("executionPrice", 0.0)),
            pnl=round(self._deal_pnl(deal), 2),
            reason=reason,
            opened_at=before.opened_at,
            closed_at=utcnow(),
        )

    async def sync(self) -> list[ClosedTrade]:
        """Otkrij pozicije koje je cTrader zatvorio (SL/TP) od zadnje provjere."""
        current = {str(p["positionId"]): self._to_position(p, None) for p in await self._raw_positions()}
        if self._known is None:
            self._known = current
            return []
        gone = {pid: pos for pid, pos in self._known.items() if pid not in current}
        self._known = current
        out = []
        now_ms = int(time.time() * 1000)
        for pid, pos in gone.items():
            try:
                res = await self.client.request(
                    DEALS_BY_POSITION_REQ,
                    {"positionId": int(pid), "fromTimestamp": now_ms - 30 * 86400 * 1000, "toTimestamp": now_ms},
                    DEALS_BY_POSITION_RES,
                )
            except DataError as exc:
                log.warning("Ne mogu dohvatiti zatvorenu poziciju %s: %s", pid, exc)
                continue
            closing = [d for d in res.get("deal") or [] if d.get("closePositionDetail")]
            if not closing:
                continue
            exit_price = float(closing[-1].get("executionPrice", 0.0))
            reason = "Zatvoreno na brokeru"
            if pos.stop_loss and pos.take_profit:
                reason = (
                    "Stop loss"
                    if abs(exit_price - pos.stop_loss) <= abs(exit_price - pos.take_profit)
                    else "Take profit"
                )
            out.append(
                ClosedTrade(
                    id=pid,
                    side=pos.side,
                    units=pos.units,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    pnl=round(sum(self._deal_pnl(d) for d in closing), 2),
                    reason=reason,
                    opened_at=pos.opened_at,
                    closed_at=datetime.fromtimestamp(
                        int(closing[-1].get("executionTimestamp", now_ms)) / 1000, tz=timezone.utc
                    ),
                )
            )
        return out
