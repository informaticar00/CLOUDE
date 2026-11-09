"""Formatiranje poruka za Telegram (HTML)."""

from __future__ import annotations

from .models import BUY, ClosedTrade, Position
from .strategy import Signal

SIDE_TXT = {BUY: "🟢 KUPI", "SELL": "🔴 PRODAJ", "HOLD": "⚪ ČEKAJ"}


def money(x: float) -> str:
    return f"{x:,.2f}"


def opt(x: float | None, digits: int = 2) -> str:
    return "—" if x is None else f"{x:,.{digits}f}"


def signal(sig: Signal) -> str:
    lines = [
        f"<b>{SIDE_TXT.get(sig.action, sig.action)}</b> — {sig.reason}",
        f"Svijeća: {sig.candle_time:%d.%m. %H:%M} UTC | Zatvaranje: {opt(sig.price)}",
        f"EMA brza/spora: {opt(sig.ema_fast)} / {opt(sig.ema_slow)}",
        f"EMA trend: {opt(sig.ema_trend)} | RSI: {opt(sig.rsi, 1)} | ATR: {opt(sig.atr)}",
    ]
    if sig.stop_loss is not None:
        lines.append(f"SL: {opt(sig.stop_loss)} | TP: {opt(sig.take_profit)}")
    return "\n".join(lines)


def position(p: Position) -> str:
    side = "🟢 BUY" if p.side == BUY else "🔴 SELL"
    sign = "+" if p.unrealized_pl >= 0 else ""
    return (
        f"<b>#{p.id}</b> {side} {p.units:g} oz @ {money(p.entry_price)}\n"
        f"   SL {opt(p.stop_loss)} | TP {opt(p.take_profit)} | P/L <b>{sign}{money(p.unrealized_pl)}</b> USD"
    )


def opened(p: Position, prefix: str = "Otvorena pozicija") -> str:
    side = "🟢 KUPLJENO" if p.side == BUY else "🔴 PRODANO"
    return (
        f"✅ <b>{prefix}</b> #{p.id}\n{side} {p.units:g} oz XAU/USD @ {money(p.entry_price)}\n"
        f"SL {opt(p.stop_loss)} | TP {opt(p.take_profit)}"
    )


def closed(t: ClosedTrade) -> str:
    icon = "💰" if t.pnl >= 0 else "🔻"
    sign = "+" if t.pnl >= 0 else ""
    return (
        f"{icon} <b>Zatvoreno #{t.id}</b> ({t.reason})\n"
        f"{t.side} {t.units:g} oz: {money(t.entry_price)} → {money(t.exit_price)}\n"
        f"Rezultat: <b>{sign}{money(t.pnl)} USD</b>"
    )
