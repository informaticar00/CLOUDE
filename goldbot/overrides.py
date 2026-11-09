"""Postavke koje se mijenjaju iz Telegrama i čuvaju u JSON fajlu (preživljavaju restart)."""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Callable

from .config import VALID_TIMEFRAMES, ConfigError, Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Option:
    key: str
    attr: str  # npr. "risk_pct" ili "strategy.atr_sl_mult"
    cast: Callable[[str], Any]
    label: str
    presets: tuple[str, ...] = ()


def _timeframe(v: str) -> str:
    v = v.upper()
    if v not in VALID_TIMEFRAMES:
        raise ConfigError(f"Timeframe mora biti jedan od: {', '.join(VALID_TIMEFRAMES)}")
    return v


OPTIONS: dict[str, Option] = {
    o.key: o
    for o in [
        Option("rizik", "risk_pct", float, "Rizik po trejdu (%)", ("0.25", "0.5", "1", "2")),
        Option("timeframe", "timeframe", _timeframe, "Timeframe", ("M5", "M15", "M30", "H1")),
        Option("maks_unci", "max_units", float, "Maks. veličina (unce)", ("5", "10", "50", "100")),
        Option("maks_pozicija", "max_open_positions", int, "Maks. otvorenih pozicija", ("1", "2", "3")),
        Option("dnevni_limit", "daily_loss_limit_pct", float, "Dnevni limit gubitka (%)", ("2", "3", "5")),
        Option("sl_atr", "strategy.atr_sl_mult", float, "SL = x × ATR", ("1", "1.5", "2", "3")),
        Option("rr", "strategy.risk_reward", float, "TP = x × SL", ("1", "1.5", "2", "3")),
        Option("ema_brza", "strategy.ema_fast", int, "Brza EMA", ("5", "9", "12")),
        Option("ema_spora", "strategy.ema_slow", int, "Spora EMA", ("21", "26", "50")),
        Option("ema_trend", "strategy.ema_trend", int, "Trend EMA (0 = isklj.)", ("0", "100", "200")),
        Option("rsi_gore", "strategy.rsi_overbought", float, "RSI prekupljeno", ("65", "70", "80")),
        Option("rsi_dolje", "strategy.rsi_oversold", float, "RSI preprodano", ("20", "30", "35")),
        Option("interval", "check_interval", int, "Provjera svakih (s)", ("30", "60", "300")),
    ]
}


def get_value(settings: Settings, attr: str) -> Any:
    obj: Any = settings
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj


def _set_value(settings: Settings, attr: str, value: Any) -> None:
    parts = attr.split(".")
    obj: Any = settings
    for part in parts[:-1]:
        obj = getattr(obj, part)
    setattr(obj, parts[-1], value)


def apply(settings: Settings, key: str, raw: str) -> Any:
    """Postavi vrijednost ako je ispravna. Inače baci ConfigError i ništa ne mijenja."""
    opt = OPTIONS.get(key)
    if opt is None:
        raise ConfigError(f"Nepoznata postavka '{key}'. Dostupne: {', '.join(OPTIONS)}")
    try:
        value = opt.cast(str(raw).replace(",", ".").strip())
    except ValueError as exc:
        raise ConfigError(f"Neispravna vrijednost za {key}: {raw!r}") from exc
    trial = copy.deepcopy(settings)
    _set_value(trial, opt.attr, value)
    trial.validate(require_telegram=False)
    _set_value(settings, opt.attr, value)
    return value


class OverrideStore:
    """Čuva promjene napravljene iz Telegrama (postavke + auto-trading)."""

    def __init__(self, path: str | None) -> None:
        self.path = path
        self.data: dict[str, Any] = {}
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (OSError, ValueError) as exc:
                log.error("Ne mogu učitati %s: %s", path, exc)

    def load_into(self, settings: Settings) -> bool | None:
        """Primijeni sačuvane postavke. Vraća sačuvano stanje auto-tradinga (ili None)."""
        for key, raw in self.data.get("settings", {}).items():
            try:
                apply(settings, key, str(raw))
            except ConfigError as exc:
                log.warning("Preskačem sačuvanu postavku %s=%s: %s", key, raw, exc)
        auto = self.data.get("auto")
        return bool(auto) if auto is not None else None

    def set_setting(self, key: str, value: Any) -> None:
        self.data.setdefault("settings", {})[key] = value
        self._save()

    def set_auto(self, enabled: bool) -> None:
        self.data["auto"] = enabled
        self._save()

    def reset(self) -> None:
        self.data = {}
        self._save()

    def _save(self) -> None:
        if not self.path:
            return
        directory = os.path.dirname(os.path.abspath(self.path))
        fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)
