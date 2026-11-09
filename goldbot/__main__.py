"""Pokretanje:
    python -m goldbot           pokreni Telegram bota
    python -m goldbot --check   samo provjeri vezu (cijena, račun, signal) bez Telegrama
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
    oanda = mt5_client = None
    if "oanda" in (settings.mode, settings.data_source):
        oanda = OandaClient(http, settings.oanda_api_key, settings.oanda_account_id, settings.oanda_env)
    if "mt5" in (settings.mode, settings.data_source):
        from .mt5 import Mt5Client

        mt5_client = Mt5Client(
            settings.mt5_login, settings.mt5_password, settings.mt5_server, settings.mt5_path
        )

    if settings.data_source == "oanda":
        feed = OandaFeed(oanda)
    elif settings.data_source == "mt5":
        from .mt5 import Mt5Feed

        feed = Mt5Feed(mt5_client, settings.mt5_symbol)
    else:
        feed = YahooFeed(http)

    if settings.mode == "oanda":
        broker = OandaBroker(oanda, feed)
        if settings.oanda_env == "live":
            logging.warning("PRAVI NOVAC: OANDA LIVE račun je aktivan!")
    elif settings.mode == "mt5":
        from .mt5 import Mt5Broker

        broker = Mt5Broker(mt5_client, feed, settings.mt5_symbol, settings.mt5_magic, settings.mt5_deviation)
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


def main() -> int:
    parser = argparse.ArgumentParser(prog="goldbot", description="Telegram bot za trgovanje zlatom")
    parser.add_argument("--check", action="store_true", help="provjeri vezu s brokerom/cijenama bez Telegrama")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings.from_env(require_telegram=not args.check)
    except ConfigError as exc:
        print(f"Greška u konfiguraciji: {exc}\nPogledaj .env.example", file=sys.stderr)
        return 1

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
