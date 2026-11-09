"""Pokretanje: python -m goldbot"""

from __future__ import annotations

import logging
import sys

import httpx

from .broker import OandaBroker, PaperBroker
from .config import ConfigError, Settings
from .data import OandaClient, OandaFeed, YahooFeed
from .engine import TradingEngine
from .telegram_bot import build_application


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        settings = Settings.from_env()
    except ConfigError as exc:
        print(f"Greška u konfiguraciji: {exc}\nPogledaj .env.example", file=sys.stderr)
        return 1

    http = httpx.AsyncClient()
    oanda = None
    if settings.mode == "oanda" or settings.data_source == "oanda":
        oanda = OandaClient(http, settings.oanda_api_key, settings.oanda_account_id, settings.oanda_env)

    feed = OandaFeed(oanda) if settings.data_source == "oanda" else YahooFeed(http)
    if settings.mode == "oanda":
        broker = OandaBroker(oanda, feed)
        if settings.oanda_env == "live":
            logging.warning("⚠️  PRAVI NOVAC: OANDA LIVE račun je aktivan!")
    else:
        broker = PaperBroker(feed, settings.paper_start_balance, settings.paper_spread, settings.paper_state_file)

    engine = TradingEngine(settings, feed, broker)
    app = build_application(settings.telegram_token, engine)
    logging.info("Pokrećem bota: %s, izvor %s, TF %s", broker.name, feed.name, settings.timeframe)
    app.run_polling(allowed_updates=["message", "callback_query"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
