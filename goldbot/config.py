"""Učitavanje postavki iz okruženja / .env fajla."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

VALID_TIMEFRAMES = ("M1", "M5", "M15", "M30", "H1", "D")


class ConfigError(ValueError):
    pass


def _get(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _float(name: str, default: float) -> float:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} mora biti broj, dobijeno: {raw!r}") from exc


def _int(name: str, default: int) -> int:
    raw = _get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} mora biti cijeli broj, dobijeno: {raw!r}") from exc


def _bool(name: str, default: bool) -> bool:
    raw = _get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "da", "on")


@dataclass
class StrategyParams:
    ema_fast: int = 9
    ema_slow: int = 21
    ema_trend: int = 200
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    atr_period: int = 14
    atr_sl_mult: float = 1.5
    risk_reward: float = 2.0

    def min_candles(self) -> int:
        return max(self.ema_slow, self.ema_trend, self.rsi_period, self.atr_period) + 2


@dataclass
class Settings:
    telegram_token: str = ""
    allowed_chat_ids: set[int] = field(default_factory=set)

    mode: str = "paper"
    data_source: str = "yahoo"

    oanda_api_key: str = ""
    oanda_account_id: str = ""
    oanda_env: str = "practice"

    mt5_login: int | None = None
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""
    mt5_symbol: str = "XAUUSD"
    mt5_magic: int = 20260
    mt5_deviation: int = 50

    timeframe: str = "M15"
    strategy: StrategyParams = field(default_factory=StrategyParams)

    risk_pct: float = 1.0
    max_units: float = 50.0
    max_open_positions: int = 1
    daily_loss_limit_pct: float = 3.0

    check_interval: int = 60
    auto_trade_on_start: bool = False
    paper_start_balance: float = 10_000.0
    paper_spread: float = 0.30
    paper_state_file: str = "paper_state.json"
    settings_file: str = "postavke.json"

    @classmethod
    def from_env(cls, env_file: str | None = ".env", require_telegram: bool = True) -> "Settings":
        if env_file:
            load_dotenv(env_file)

        chat_ids_raw = _get("ALLOWED_CHAT_IDS", "") or ""
        try:
            chat_ids = {int(x) for x in chat_ids_raw.replace(" ", "").split(",") if x}
        except ValueError as exc:
            raise ConfigError("ALLOWED_CHAT_IDS mora biti lista brojeva odvojenih zarezom") from exc

        s = cls(
            telegram_token=_get("TELEGRAM_TOKEN", "") or "",
            allowed_chat_ids=chat_ids,
            mode=(_get("MODE", "paper") or "paper").lower(),
            data_source=(_get("DATA_SOURCE", "yahoo") or "yahoo").lower(),
            oanda_api_key=_get("OANDA_API_KEY", "") or "",
            oanda_account_id=_get("OANDA_ACCOUNT_ID", "") or "",
            oanda_env=(_get("OANDA_ENV", "practice") or "practice").lower(),
            mt5_login=_int("MT5_LOGIN", 0) or None,
            mt5_password=_get("MT5_PASSWORD", "") or "",
            mt5_server=_get("MT5_SERVER", "") or "",
            mt5_path=_get("MT5_PATH", "") or "",
            mt5_symbol=_get("MT5_SYMBOL", "XAUUSD") or "XAUUSD",
            mt5_magic=_int("MT5_MAGIC", 20260),
            mt5_deviation=_int("MT5_DEVIATION", 50),
            timeframe=(_get("TIMEFRAME", "M15") or "M15").upper(),
            strategy=StrategyParams(
                ema_fast=_int("EMA_FAST", 9),
                ema_slow=_int("EMA_SLOW", 21),
                ema_trend=_int("EMA_TREND", 200),
                rsi_period=_int("RSI_PERIOD", 14),
                rsi_overbought=_float("RSI_OVERBOUGHT", 70.0),
                rsi_oversold=_float("RSI_OVERSOLD", 30.0),
                atr_period=_int("ATR_PERIOD", 14),
                atr_sl_mult=_float("ATR_SL_MULT", 1.5),
                risk_reward=_float("RISK_REWARD", 2.0),
            ),
            risk_pct=_float("RISK_PCT", 1.0),
            max_units=_float("MAX_UNITS", 50.0),
            max_open_positions=_int("MAX_OPEN_POSITIONS", 1),
            daily_loss_limit_pct=_float("DAILY_LOSS_LIMIT_PCT", 3.0),
            check_interval=_int("CHECK_INTERVAL", 60),
            auto_trade_on_start=_bool("AUTO_TRADE_ON_START", False),
            paper_start_balance=_float("PAPER_START_BALANCE", 10_000.0),
            paper_spread=_float("PAPER_SPREAD", 0.30),
            paper_state_file=_get("PAPER_STATE_FILE", "paper_state.json") or "paper_state.json",
            settings_file=_get("SETTINGS_FILE", "postavke.json") or "postavke.json",
        )
        s.validate(require_telegram)
        return s

    def validate(self, require_telegram: bool = True) -> None:
        if require_telegram:
            if not self.telegram_token:
                raise ConfigError("TELEGRAM_TOKEN nije postavljen")
            if not self.allowed_chat_ids:
                raise ConfigError("ALLOWED_CHAT_IDS nije postavljen - bot mora znati ko smije njime upravljati")
        if self.mode not in ("paper", "oanda", "mt5"):
            raise ConfigError("MODE mora biti 'paper', 'oanda' ili 'mt5'")
        if self.data_source not in ("yahoo", "oanda", "mt5"):
            raise ConfigError("DATA_SOURCE mora biti 'yahoo', 'oanda' ili 'mt5'")
        if self.mode in ("oanda", "mt5") and self.data_source != self.mode:
            raise ConfigError(f"Kad je MODE={self.mode}, DATA_SOURCE mora biti '{self.mode}'")
        if self.mt5_login and not (self.mt5_password and self.mt5_server):
            raise ConfigError("Uz MT5_LOGIN moraš postaviti i MT5_PASSWORD i MT5_SERVER")
        if (self.mode == "oanda" or self.data_source == "oanda") and not (
            self.oanda_api_key and self.oanda_account_id
        ):
            raise ConfigError("OANDA_API_KEY i OANDA_ACCOUNT_ID su obavezni za OANDA")
        if self.oanda_env not in ("practice", "live"):
            raise ConfigError("OANDA_ENV mora biti 'practice' ili 'live'")
        if self.timeframe not in VALID_TIMEFRAMES:
            raise ConfigError(f"TIMEFRAME mora biti jedan od {', '.join(VALID_TIMEFRAMES)}")
        if self.strategy.ema_fast >= self.strategy.ema_slow:
            raise ConfigError("EMA_FAST mora biti manji od EMA_SLOW")
        if not 0 < self.risk_pct <= 5:
            raise ConfigError("RISK_PCT mora biti između 0 i 5")
        if self.max_units <= 0:
            raise ConfigError("MAX_UNITS mora biti veći od 0")
        if self.check_interval < 10:
            raise ConfigError("CHECK_INTERVAL mora biti barem 10 sekundi")
        if self.max_open_positions < 1:
            raise ConfigError("MAX_OPEN_POSITIONS mora biti barem 1")
        if not 0 < self.daily_loss_limit_pct <= 100:
            raise ConfigError("DAILY_LOSS_LIMIT_PCT mora biti između 0 i 100")
        p = self.strategy
        if min(p.ema_fast, p.ema_slow, p.rsi_period, p.atr_period) < 1 or p.ema_trend < 0:
            raise ConfigError("Periodi indikatora moraju biti pozitivni")
        if not 0 <= p.rsi_oversold < p.rsi_overbought <= 100:
            raise ConfigError("RSI granice: 0 <= dolje < gore <= 100")
        if p.atr_sl_mult <= 0 or p.risk_reward <= 0:
            raise ConfigError("SL množilac i RR moraju biti veći od 0")
