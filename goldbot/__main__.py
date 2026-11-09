"""Pokretanje:
    python -m goldbot           pokreni Telegram bota
    python -m goldbot --check   samo provjeri vezu (cijena, račun, signal) bez Telegrama
    python -m goldbot --ctrader-login   jednokratna prijava na cTrader (dobija token)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from . import fmt
from .broker import BrokerError, OandaBroker, PaperBroker
from .config import ConfigError, Settings
from .data import DataError, OandaClient, OandaFeed, YahooFeed
from .engine import TradingEngine
from .overrides import OverrideStore


def build_engine(settings: Settings, http: httpx.AsyncClient) -> TradingEngine:
    oanda = mt5_client = ct_client = None
    if "oanda" in (settings.mode, settings.data_source):
        oanda = OandaClient(http, settings.oanda_api_key, settings.oanda_account_id, settings.oanda_env)
    if "mt5" in (settings.mode, settings.data_source):
        from .mt5 import Mt5Client

        mt5_client = Mt5Client(
            settings.mt5_login, settings.mt5_password, settings.mt5_server, settings.mt5_path
        )

    if "ctrader" in (settings.mode, settings.data_source):
        from .ctrader import CTraderClient, CTraderFeed, CTraderSymbol, TokenStore

        tokens = TokenStore(
            settings.ctrader_token_file, settings.ctrader_access_token, settings.ctrader_refresh_token
        )
        ct_client = CTraderClient(
            settings.ctrader_client_id, settings.ctrader_client_secret, tokens, settings.ctrader_account
        )

    if settings.data_source == "oanda":
        feed = OandaFeed(oanda)
    elif settings.data_source == "ctrader":
        feed = CTraderFeed(ct_client, CTraderSymbol(ct_client, settings.ctrader_symbol))
    elif settings.data_source == "mt5":
        from .mt5 import Mt5Feed

        feed = Mt5Feed(mt5_client, settings.mt5_symbol)
    else:
        feed = YahooFeed(http)

    if settings.mode == "oanda":
        broker = OandaBroker(oanda, feed)
        if settings.oanda_env == "live":
            logging.warning("PRAVI NOVAC: OANDA LIVE račun je aktivan!")
    elif settings.mode == "ctrader":
        from .ctrader import CTraderBroker

        broker = CTraderBroker(ct_client, feed, allow_real_money=settings.allow_real_money)
    elif settings.mode == "mt5":
        from .mt5 import Mt5Broker

        broker = Mt5Broker(mt5_client, feed, settings.mt5_symbol, settings.mt5_magic, settings.mt5_deviation,
                           settings.allow_real_money)
    else:
        broker = PaperBroker(feed, settings.paper_start_balance, settings.paper_spread, settings.paper_state_file)
    return TradingEngine(settings, feed, broker)


async def check(settings: Settings) -> int:
    async with httpx.AsyncClient() as http:
        try:
            engine = build_engine(settings, http)
            print(f"Izvor cijena: {engine.feed.name}")
            q = await engine.broker.quote()
            print(f"Cijena:       bid {q.bid:.2f} / ask {q.ask:.2f}")
            print(f"Saldo:        {await engine.broker.balance():,.2f} | equity {await engine.broker.equity():,.2f}")
            print(f"Račun:        {engine.broker.name}")
            print(f"Pozicije:     {len(await engine.broker.positions())}")
            sig = await engine.analyze()
            text = fmt.signal(sig).replace("<b>", "").replace("</b>", "")
            print(f"Signal ({settings.timeframe}):\n  " + text.replace("\n", "\n  "))
        except (DataError, BrokerError) as exc:
            print(f"\nGREŠKA: {exc}", file=sys.stderr)
            return 1
    print("\nSve radi. ✅")
    return 0


async def ctrader_login(settings: Settings) -> int:
    """Jednokratna OAuth prijava: korisnik otvori link, odobri pristup i zalijepi URL nazad."""
    from urllib.parse import parse_qs, urlparse

    from .ctrader import CTraderClient, TokenStore, auth_url, exchange_code

    if not (settings.ctrader_client_id and settings.ctrader_client_secret):
        print("Prvo u .env upiši CTRADER_CLIENT_ID i CTRADER_CLIENT_SECRET (sa openapi.ctrader.com).")
        return 1
    url = auth_url(settings.ctrader_client_id, settings.ctrader_redirect_uri)
    print("\n1) Otvori ovaj link u pregledniku i prijavi se svojim cTrader ID-om:\n")
    print("   " + url + "\n")
    print("2) Označi račun(e) kojima bot smije pristupiti i klikni Allow / Dozvoli.")
    print("3) Preglednik će otići na stranicu koja se možda neće učitati - to je u redu.")
    print("   Kopiraj CIJELU adresu iz adresne trake (sadrži ?code=...) i zalijepi je ovdje.\n")
    try:
        import webbrowser

        webbrowser.open(url)
    except Exception:  # noqa: BLE001
        pass
    pasted = input("Zalijepi adresu (ili samo kod) pa Enter: ").strip()
    code = parse_qs(urlparse(pasted).query).get("code", [pasted])[0].strip()
    if not code:
        print("Nije pronađen kod.")
        return 1
    tokens = TokenStore(settings.ctrader_token_file)
    async with httpx.AsyncClient() as http:
        try:
            data = await exchange_code(
                http, settings.ctrader_client_id, settings.ctrader_client_secret, settings.ctrader_redirect_uri, code
            )
        except DataError as exc:
            print(f"\nGREŠKA: {exc}", file=sys.stderr)
            return 1
    tokens.update(data["accessToken"], data.get("refreshToken", ""), data.get("expiresIn", 0))
    print(f"\nToken sačuvan u {settings.ctrader_token_file}. Provjeravam račune...")

    from .ctrader import ACCOUNTS_BY_TOKEN_REQ, ACCOUNTS_BY_TOKEN_RES, APP_AUTH_REQ, APP_AUTH_RES

    client = CTraderClient(settings.ctrader_client_id, settings.ctrader_client_secret, tokens)
    try:
        await client._open(live=False)
        await client._expect(
            APP_AUTH_REQ,
            {"clientId": settings.ctrader_client_id, "clientSecret": settings.ctrader_client_secret},
            APP_AUTH_RES,
        )
        res = await client._expect(ACCOUNTS_BY_TOKEN_REQ, {"accessToken": tokens.access_token}, ACCOUNTS_BY_TOKEN_RES)
    except DataError as exc:
        print(f"Token je sačuvan, ali provjera računa nije uspjela: {exc}", file=sys.stderr)
        return 1
    finally:
        await client.close()
    accounts = res.get("ctidTraderAccount") or []
    print("\nRačuni dostupni botu:")
    for a in accounts:
        kind = "LIVE (pravi novac)" if a.get("isLive") else "DEMO"
        print(f"  {a.get('traderLogin')}  {a.get('brokerTitleShort', '')}  {kind}")
    if len(accounts) > 1:
        print("\nImaš više računa: upiši željeni broj u .env kao CTRADER_ACCOUNT=...")
    print("\nGotovo. Sada pokreni provjera.bat")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="goldbot", description="Telegram bot za trgovanje zlatom")
    parser.add_argument("--check", action="store_true", help="provjeri vezu s brokerom/cijenama bez Telegrama")
    parser.add_argument("--ctrader-login", action="store_true", help="jednokratna prijava na cTrader")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings.from_env(require_telegram=not (args.check or args.ctrader_login))
    except ConfigError as exc:
        print(f"Greška u konfiguraciji: {exc}\nPogledaj .env.example", file=sys.stderr)
        return 1

    if args.ctrader_login:
        return asyncio.run(ctrader_login(settings))
    if args.check:
        return asyncio.run(check(settings))

    from .telegram_bot import build_application

    store = OverrideStore(settings.settings_file)
    saved_auto = store.load_into(settings)
    try:
        engine = build_engine(settings, httpx.AsyncClient())
    except DataError as exc:
        print(f"Greška: {exc}", file=sys.stderr)
        return 1
    if saved_auto is not None:
        engine.auto_enabled = saved_auto
    app = build_application(settings.telegram_token, engine, store)
    logging.info("Pokrećem bota: %s, izvor %s, TF %s", engine.broker.name, engine.feed.name, settings.timeframe)
    app.run_polling(allowed_updates=["message", "callback_query"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
