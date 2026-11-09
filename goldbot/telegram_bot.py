"""Telegram interfejs za bota."""

from __future__ import annotations

import functools
import html
import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from . import fmt
from .broker import BrokerError
from .data import DataError
from .engine import TradingEngine
from .models import BUY, SELL

log = logging.getLogger(__name__)

HELP = """<b>🥇 Gold Bot — XAU/USD</b>

<b>Tržište</b>
/cijena — trenutna cijena zlata
/signal — analiza i trenutni signal

<b>Račun</b>
/status — saldo, način rada, auto-trading
/pozicije — otvorene pozicije
/historija — zadnji zatvoreni trejdovi (paper)

<b>Trgovanje</b>
/kupi [unce] — kupi (SL/TP automatski po ATR-u)
/prodaj [unce] — prodaj
/zatvori [ID] — zatvori poziciju (bez ID-a: sve)
/auto on|off — uključi/isključi automatsko trgovanje

<b>Postavke</b>
/postavke — prikaz postavki strategije i rizika
/rizik 1.0 — promijeni % rizika po trejdu

Bez [unce] veličina se računa iz % rizika."""

COMMANDS = [
    BotCommand("cijena", "Trenutna cijena zlata"),
    BotCommand("signal", "Analiza i signal"),
    BotCommand("status", "Stanje računa"),
    BotCommand("pozicije", "Otvorene pozicije"),
    BotCommand("kupi", "Kupi zlato"),
    BotCommand("prodaj", "Prodaj zlato"),
    BotCommand("zatvori", "Zatvori poziciju"),
    BotCommand("auto", "Auto-trading on/off"),
    BotCommand("historija", "Zadnji trejdovi"),
    BotCommand("postavke", "Postavke"),
    BotCommand("rizik", "Promijeni rizik %"),
    BotCommand("pomoc", "Pomoć"),
]


def _engine(context: ContextTypes.DEFAULT_TYPE) -> TradingEngine:
    return context.application.bot_data["engine"]


def authorized(func):
    """Dozvoli samo chat ID-eve iz ALLOWED_CHAT_IDS."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        allowed = _engine(context).settings.allowed_chat_ids
        chat = update.effective_chat
        if chat is None or chat.id not in allowed:
            log.warning("Neovlašten pristup iz chata %s", chat.id if chat else "?")
            if update.callback_query:
                await update.callback_query.answer("Nemaš pristup.", show_alert=True)
            elif update.effective_message:
                await update.effective_message.reply_text(
                    f"⛔ Nemaš pristup ovom botu. Tvoj chat ID: {chat.id if chat else '?'}"
                )
            return None
        try:
            return await func(update, context)
        except (DataError, BrokerError) as exc:
            await _reply(update, f"⚠️ {html.escape(str(exc))}")
        return None

    return wrapper


async def _reply(update: Update, text: str, **kwargs) -> None:
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, **kwargs)


def _parse_units(args: list[str]) -> float | None:
    if not args:
        return None
    try:
        units = float(args[0].replace(",", "."))
    except ValueError as exc:
        raise BrokerError("Količina mora biti broj, npr. /kupi 2") from exc
    if units <= 0:
        raise BrokerError("Količina mora biti veća od 0")
    return units


# ---------------------------------------------------------------------- komande


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    await _reply(update, HELP + f"\n\nNačin rada: <b>{eng.broker.name}</b> | Izvor: {eng.feed.name}")


@authorized
async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = await _engine(context).broker.quote()
    await _reply(
        update,
        f"🥇 <b>XAU/USD</b>\nBid: {fmt.money(q.bid)}\nAsk: {fmt.money(q.ask)}\nSpread: {q.spread:.2f}",
    )


@authorized
async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    sig = await eng.analyze()
    await _reply(update, f"📊 <b>Analiza {eng.settings.timeframe}</b>\n" + fmt.signal(sig))


@authorized
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    s = eng.settings
    balance = await eng.broker.balance()
    equity = await eng.broker.equity()
    positions = await eng.broker.positions()
    lines = [
        "📋 <b>Status</b>",
        f"Račun: <b>{eng.broker.name}</b>",
        f"Saldo: {fmt.money(balance)} USD | Equity: {fmt.money(equity)} USD",
        f"Otvorene pozicije: {len(positions)}",
        f"Auto-trading: {'✅ UKLJUČEN' if eng.auto_enabled else '⏸ ISKLJUČEN'}",
        f"Dnevni gubitak: {eng.daily_loss(equity):.2f}% / limit {s.daily_loss_limit_pct:.2f}%"
        + (" 🛑 (pauzirano)" if eng.halted_today else ""),
    ]
    if eng.last_signal:
        lines.append(f"Zadnji signal: {eng.last_signal.action} ({eng.last_signal.candle_time:%d.%m. %H:%M} UTC)")
    if eng.last_error:
        lines.append(f"Zadnja greška: {html.escape(eng.last_error)}")
    await _reply(update, "\n".join(lines))


@authorized
async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    positions = await _engine(context).broker.positions()
    if not positions:
        await _reply(update, "Nema otvorenih pozicija.")
        return
    await _reply(update, "📂 <b>Otvorene pozicije</b>\n\n" + "\n\n".join(fmt.position(p) for p in positions))


@authorized
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history = getattr(_engine(context).broker, "history", None)
    if history is None:
        await _reply(update, "Historija je dostupna u platformi brokera (OANDA / MT5).")
        return
    if not history:
        await _reply(update, "Još nema zatvorenih trejdova.")
        return
    last = history[-10:]
    total = sum(t.pnl for t in history)
    wins = sum(1 for t in history if t.pnl > 0)
    await _reply(
        update,
        "📜 <b>Zadnji trejdovi</b>\n\n"
        + "\n\n".join(fmt.closed(t) for t in reversed(last))
        + f"\n\nUkupno: {len(history)} trejdova, {wins} dobitnih, P/L {fmt.money(total)} USD",
    )


async def _order_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, side: str) -> None:
    eng = _engine(context)
    units = _parse_units(context.args or [])
    plan = await eng.plan(side, units)
    side_txt = "🟢 KUPI" if side == BUY else "🔴 PRODAJ"
    text = (
        f"<b>Potvrdi nalog</b> ({eng.broker.name})\n"
        f"{side_txt} {plan.units:g} oz XAU/USD @ ~{fmt.money(plan.entry)}\n"
        f"SL: {fmt.money(plan.stop_loss)} | TP: {fmt.money(plan.take_profit)}\n"
        f"Rizik: ~{fmt.money(plan.risk_usd)} USD"
    )
    if plan.close_ids:
        text += f"\n⚠️ Prvo će se zatvoriti suprotne pozicije: {', '.join('#' + i for i in plan.close_ids)}"
    if eng.halted_today:
        text += "\n⚠️ Dnevni limit gubitka je već dostignut!"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Potvrdi", callback_data=f"order:{side}:{plan.units}"),
                InlineKeyboardButton("❌ Odustani", callback_data="cancel"),
            ]
        ]
    )
    await _reply(update, text, reply_markup=keyboard)


@authorized
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _order_prompt(update, context, BUY)


@authorized
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _order_prompt(update, context, SELL)


@authorized
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data or ""
    if data == "cancel":
        await query.edit_message_text("❌ Nalog otkazan.")
        return
    if data.startswith("order:"):
        _, side, units = data.split(":")
        await query.edit_message_text("⏳ Šaljem nalog...")
        msgs = await _engine(context).execute(side, float(units))
        await query.edit_message_text("\n\n".join(msgs), parse_mode=ParseMode.HTML)
    elif data.startswith("closeall"):
        await query.edit_message_text("⏳ Zatvaram...")
        msgs = await _engine(context).close(None)
        await query.edit_message_text("\n\n".join(msgs), parse_mode=ParseMode.HTML)


@authorized
async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    if context.args:
        pid = context.args[0].lstrip("#")
        await _reply(update, "\n\n".join(await eng.close(pid)))
        return
    positions = await eng.broker.positions()
    if not positions:
        await _reply(update, "Nema otvorenih pozicija.")
        return
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Zatvori sve", callback_data="closeall"), InlineKeyboardButton("❌ Ne", callback_data="cancel")]]
    )
    await _reply(update, f"Zatvoriti svih {len(positions)} pozicija?", reply_markup=keyboard)


@authorized
async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    arg = (context.args[0].lower() if context.args else "")
    if arg in ("on", "uklj", "da", "1"):
        eng.auto_enabled = True
        await _reply(update, f"✅ Auto-trading UKLJUČEN na računu <b>{eng.broker.name}</b>.")
    elif arg in ("off", "isklj", "ne", "0"):
        eng.auto_enabled = False
        await _reply(update, "⏸ Auto-trading ISKLJUČEN. Signale ću i dalje javljati.")
    else:
        state = "UKLJUČEN" if eng.auto_enabled else "ISKLJUČEN"
        await _reply(update, f"Auto-trading je {state}. Koristi /auto on ili /auto off.")


@authorized
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = _engine(context).settings
    p = s.strategy
    await _reply(
        update,
        "⚙️ <b>Postavke</b>\n"
        f"Timeframe: {s.timeframe} | provjera svakih {s.check_interval}s\n"
        f"EMA {p.ema_fast}/{p.ema_slow}, trend EMA {p.ema_trend or 'isključen'}\n"
        f"RSI {p.rsi_period} ({p.rsi_oversold:g}/{p.rsi_overbought:g})\n"
        f"SL = {p.atr_sl_mult:g}×ATR({p.atr_period}), TP = {p.risk_reward:g}×SL\n"
        f"Rizik po trejdu: {s.risk_pct:g}% | maks. {s.max_units:g} oz | maks. pozicija {s.max_open_positions}\n"
        f"Dnevni limit gubitka: {s.daily_loss_limit_pct:g}%",
    )


@authorized
async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    s = _engine(context).settings
    if not context.args:
        await _reply(update, f"Trenutni rizik: {s.risk_pct:g}% po trejdu. Primjer: /rizik 0.5")
        return
    try:
        value = float(context.args[0].replace(",", "."))
    except ValueError:
        await _reply(update, "Unesi broj, npr. /rizik 0.5")
        return
    if not 0 < value <= 5:
        await _reply(update, "Rizik mora biti između 0 i 5%.")
        return
    s.risk_pct = value
    await _reply(update, f"✅ Rizik postavljen na {value:g}% po trejdu (do restarta bota).")


# ---------------------------------------------------------------------- petlja


async def _broadcast(app: Application, text: str) -> None:
    engine: TradingEngine = app.bot_data["engine"]
    for chat_id in engine.settings.allowed_chat_ids:
        try:
            await app.bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)
        except Exception as exc:  # noqa: BLE001 - ne smije srušiti petlju
            log.error("Slanje poruke u %s nije uspjelo: %s", chat_id, exc)


async def market_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    engine: TradingEngine = context.application.bot_data["engine"]
    try:
        msgs = await engine.tick()
        if engine.last_error:
            log.info("Veza ponovo radi")
        engine.last_error = None
    except (DataError, BrokerError) as exc:
        log.warning("Greška u petlji: %s", exc)
        if engine.last_error is None:  # javi samo prvi put, ne spamaj
            await _broadcast(context.application, f"⚠️ Problem s podacima/brokerom: {html.escape(str(exc))}")
        engine.last_error = str(exc)
        return
    except Exception:  # noqa: BLE001
        log.exception("Neočekivana greška u petlji")
        return
    for m in msgs:
        await _broadcast(context.application, m)


async def _post_init(app: Application) -> None:
    engine: TradingEngine = app.bot_data["engine"]
    await app.bot.set_my_commands(COMMANDS)
    state = "UKLJUČEN" if engine.auto_enabled else "ISKLJUČEN"
    await _broadcast(
        app,
        f"🤖 Gold Bot pokrenut.\nRačun: <b>{engine.broker.name}</b> | Izvor: {engine.feed.name}\n"
        f"Auto-trading: {state}. /pomoc za komande.",
    )


def build_application(token: str, engine: TradingEngine) -> Application:
    app = Application.builder().token(token).post_init(_post_init).build()
    app.bot_data["engine"] = engine

    handlers = {
        ("start", "pomoc", "help"): cmd_start,
        ("cijena", "price"): cmd_price,
        ("signal",): cmd_signal,
        ("status",): cmd_status,
        ("pozicije", "positions"): cmd_positions,
        ("historija", "history"): cmd_history,
        ("kupi", "buy"): cmd_buy,
        ("prodaj", "sell"): cmd_sell,
        ("zatvori", "close"): cmd_close,
        ("auto",): cmd_auto,
        ("postavke", "settings"): cmd_settings,
        ("rizik", "risk"): cmd_risk,
    }
    for names, fn in handlers.items():
        app.add_handler(CommandHandler(list(names), fn))
    app.add_handler(CallbackQueryHandler(on_callback))

    app.job_queue.run_repeating(market_job, interval=engine.settings.check_interval, first=5)
    return app
