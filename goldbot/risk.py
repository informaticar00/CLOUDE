"""Upravljanje rizikom: veličina pozicije i dnevni limit gubitka."""

from __future__ import annotations

import math


def position_size(
    balance: float,
    risk_pct: float,
    entry: float,
    stop_loss: float,
    max_units: float,
    precision: int = 2,
) -> float:
    """Broj jedinica (unci) tako da gubitak na SL bude ~risk_pct% salda.

    Zaokružuje NANIŽE da se nikad ne rizikuje više od zadanog.
    Vraća 0 ako pozicija ne može biti otvorena.
    """
    stop_distance = abs(entry - stop_loss)
    if balance <= 0 or stop_distance <= 0 or risk_pct <= 0:
        return 0.0
    risk_amount = balance * risk_pct / 100.0
    units = min(risk_amount / stop_distance, max_units)
    factor = 10**precision
    units = math.floor(units * factor) / factor
    return units if units > 0 else 0.0


def daily_loss_pct(day_start_equity: float, current_equity: float) -> float:
    """Dnevni gubitak u procentima (pozitivan broj = gubitak)."""
    if day_start_equity <= 0:
        return 0.0
    return (day_start_equity - current_equity) / day_start_equity * 100.0
