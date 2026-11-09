"""Telegram interfejs. Sve se može raditi dodirom dugmadi (prilagođeno telefonu),
a komande s kucanjem i dalje rade."""

from __future__ import annotations

import functools
import html
import logging

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from . import fmt
from .broker import BrokerError
from .config import ConfigError, Settings
from .data import DataError
from .engine import TradingEngine
from .models import BUY, SELL
from .overrides import OPTIONS, OverrideStore, apply, get_value

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------- meni

BTN_PRICE = "💰 Cijena"
BTN_SIGNAL = "📊 Signal"
BTN_STATUS = "📋 Status"
BTN_POSITIONS = "📂 Pozicije"
BTN_BUY = "🟢 Kupi"
BTN_SELL = "🔴 Prodaj"
BTN_AUTO = "🤖 Auto-trading"
BTN_SETTINGS = "⚙️ Postavke"
BTN_HISTORY = "📜 Historija"
BTN_HELP = "❓ Pomoć"

MAIN_MENU = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_PRICE), KeyboardButton(BTN_SIGNAL)],
        [KeyboardButton(BTN_BUY), KeyboardButton(BTN_SELL)],
        [KeyboardButton(BTN_POSITIONS), KeyboardButton(BTN_STATUS)],
        [KeyboardButton(BTN_AUTO), KeyboardButton(BTN_SETTINGS)],
        [KeyboardButton(BTN_HISTORY), KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
    is_persistent=True,
)

HELP = """<b>🥇 Gold Bot — XAU/USD</b>

Sve radiš preko <b>dugmadi ispod</b>:
💰 <b>Cijena</b> — trenutni bid/ask
📊 <b>Signal</b> — analiza tržišta
🟢 <b>Kupi</b> / 🔴 <b>Prodaj</b> — izabereš veličinu, pa potvrdiš
📂 <b>Pozicije</b> — otvorene pozicije, zatvaranje jednim dodirom
📋 <b>Status</b> — saldo, equity, dnevni gubitak
🤖 <b>Auto-trading</b> — uključi/isključi automatsko trgovanje
⚙️ <b>Postavke</b> — rizik, timeframe, SL/TP... (čuvaju se trajno)
📜 <b>Historija</b> — zadnji trejdovi

Komande s kucanjem i dalje rade:
/kupi 2 · /prodaj 2 · /zatvori ID · /auto on|off
/postavi rizik 0.7 — bilo koja vrijednost
/postavke_reset — vrati postavke iz .env fajla"""

COMMANDS = [
    BotCommand("meni", "Prikaži dugmad"),
    BotCommand("cijena", "Trenutna cijena zlata"),
    BotCommand("signal", "Analiza i signal"),
    BotCommand("status", "Stanje računa"),
    BotCommand("pozicije", "Otvorene pozicije"),
    BotCommand("kupi", "Kupi zlato"),
    BotCommand("prodaj", "Prodaj zlato"),
    BotCommand("auto", "Auto-trading"),
    BotCommand("postavke", "Postavke"),
    BotCommand("postavi", "Postavi vrijednost: /postavi rizik 0.5"),
    BotCommand("historija", "Zadnji trejdovi"),
    BotCommand("pomoc", "Pomoć"),
]

STRATEGY_KEYS = {"timeframe", "ema_brza", "ema_spora", "ema_trend", "rsi_gore", "rsi_dolje"}


def _engine(context: ContextTypes.DEFAULT_TYPE) -> TradingEngine:
    return context.application.bot_data["engine"]


def _store(context: ContextTypes.DEFAULT_TYPE) -> OverrideStore:
    return context.application.bot_data["store"]


def authorized(func):
    """Dozvoli samo chat ID-eve iz ALLOWED_CHAT_IDS i pretvori greške u poruke."""

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
        except (DataError, BrokerError, ConfigError) as exc:
            await _send(update, f"⚠️ {html.escape(str(exc))}")
        return None

    return wrapper


async def _send(update: Update, text: str, markup=None, edit: bool = False) -> None:
    """Pošalji novu poruku, ili (edit=True, kod dugmeta) izmijeni postojeću."""
    query = update.callback_query
    if edit and query:
        try:
            await query.edit_message_text(
                text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True
            )
        except BadRequest as exc:
            if "not modified" not in str(exc).lower():
                raise
        return
    msg = update.effective_message
    if msg:
        await msg.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup, disable_web_page_preview=True)


def _kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(t, callback_data=d) for t, d in row] for row in rows])


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


# ---------------------------------------------------------------------- prikazi


async def show_price(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    q = await _engine(context).broker.quote()
    await _send(
        update,
        f"🥇 <b>XAU/USD</b>\nBid: <b>{fmt.money(q.bid)}</b>\nAsk: <b>{fmt.money(q.ask)}</b>\nSpread: {q.spread:.2f}",
        _kb([("🔄 Osvježi", "v:price")]),
        edit,
    )


async def show_signal(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    eng = _engine(context)
    sig = await eng.analyze()
    await _send(
        update,
        f"📊 <b>Analiza {eng.settings.timeframe}</b>\n" + fmt.signal(sig),
        _kb([("🔄 Osvježi", "v:signal")], [("🟢 Kupi", "buy:BUY"), ("🔴 Prodaj", "buy:SELL")]),
        edit,
    )


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    eng = _engine(context)
    s = eng.settings
    balance = await eng.broker.balance()
    equity = await eng.broker.equity()
    positions = await eng.broker.positions()
    lines = [
        "📋 <b>Status</b>",
        f"Račun: <b>{html.escape(eng.broker.name)}</b>",
        f"Saldo: {fmt.money(balance)} | Equity: <b>{fmt.money(equity)}</b>",
        f"Otvorene pozicije: {len(positions)}",
        f"Auto-trading: {'✅ UKLJUČEN' if eng.auto_enabled else '⏸ ISKLJUČEN'}",
        f"Dnevni gubitak: {eng.daily_loss(equity):.2f}% / limit {s.daily_loss_limit_pct:g}%"
        + (" 🛑 pauzirano" if eng.halted_today else ""),
        f"Timeframe: {s.timeframe} | Rizik: {s.risk_pct:g}%",
    ]
    if eng.last_signal:
        lines.append(f"Zadnji signal: {eng.last_signal.action} ({eng.last_signal.candle_time:%d.%m. %H:%M})")
    if eng.last_error:
        lines.append(f"⚠️ Zadnja greška: {html.escape(eng.last_error)}")
    await _send(update, "\n".join(lines), _kb([("🔄 Osvježi", "v:status"), ("📂 Pozicije", "v:pos")]), edit)


async def show_positions(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    positions = await _engine(context).broker.positions()
    if not positions:
        await _send(update, "Nema otvorenih pozicija.", _kb([("🔄 Osvježi", "v:pos")]), edit)
        return
    rows = [[(f"❌ Zatvori #{p.id}", f"cq:{p.id}")] for p in positions]
    if len(positions) > 1:
        rows.append([("❌ Zatvori SVE", "cq:all")])
    rows.append([("🔄 Osvježi", "v:pos")])
    total = sum(p.unrealized_pl for p in positions)
    text = (
        "📂 <b>Otvorene pozicije</b>\n\n"
        + "\n\n".join(fmt.position(p) for p in positions)
        + f"\n\nUkupno P/L: <b>{'+' if total >= 0 else ''}{fmt.money(total)}</b>"
    )
    await _send(update, text, _kb(*rows), edit)


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history = getattr(_engine(context).broker, "history", None)
    if history is None:
        await _send(update, "Historija je dostupna u aplikaciji brokera (MT5 / OANDA na iPhoneu).")
        return
    if not history:
        await _send(update, "Još nema zatvorenih trejdova.")
        return
    total = sum(t.pnl for t in history)
    wins = sum(1 for t in history if t.pnl > 0)
    await _send(
        update,
        "📜 <b>Zadnji trejdovi</b>\n\n"
        + "\n\n".join(fmt.closed(t) for t in reversed(history[-10:]))
        + f"\n\nUkupno: {len(history)} trejdova, {wins} dobitnih, P/L <b>{fmt.money(total)}</b>",
    )


async def show_auto(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    eng = _engine(context)
    if eng.auto_enabled:
        text = f"🤖 Auto-trading je <b>✅ UKLJUČEN</b> na računu <b>{html.escape(eng.broker.name)}</b>."
        markup = _kb([("⏸ Isključi", "auto:off")])
    else:
        text = "🤖 Auto-trading je <b>⏸ ISKLJUČEN</b>. Signale ti i dalje javljam."
        markup = _kb([("✅ Uključi", "auto:ask")])
    await _send(update, text, markup, edit)


async def show_buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, side: str, edit: bool = False) -> None:
    eng = _engine(context)
    title = "🟢 <b>KUPI</b>" if side == BUY else "🔴 <b>PRODAJ</b>"
    await _send(
        update,
        f"{title} zlato — izaberi veličinu:\n<i>Auto = po riziku od {eng.settings.risk_pct:g}% salda</i>",
        _kb(
            [(f"⚖️ Auto ({eng.settings.risk_pct:g}%)", f"sz:{side}:auto")],
            [("1 oz", f"sz:{side}:1"), ("2 oz", f"sz:{side}:2"), ("5 oz", f"sz:{side}:5"), ("10 oz", f"sz:{side}:10")],
            [("❌ Odustani", "cancel")],
        ),
        edit,
    )


async def show_order_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE, side: str, units: float | None, edit: bool = False
) -> None:
    eng = _engine(context)
    plan = await eng.plan(side, units)
    side_txt = "🟢 KUPI" if side == BUY else "🔴 PRODAJ"
    text = (
        f"<b>Potvrdi nalog</b> ({html.escape(eng.broker.name)})\n"
        f"{side_txt} <b>{plan.units:g} oz</b> XAU/USD @ ~{fmt.money(plan.entry)}\n"
        f"SL: {fmt.money(plan.stop_loss)} | TP: {fmt.money(plan.take_profit)}\n"
        f"Rizik: ~<b>{fmt.money(plan.risk_usd)}</b>"
    )
    if plan.close_ids:
        text += f"\n⚠️ Prvo se zatvaraju suprotne pozicije: {', '.join('#' + i for i in plan.close_ids)}"
    if eng.halted_today:
        text += "\n⚠️ Dnevni limit gubitka je već dostignut!"
    await _send(update, text, _kb([("✅ Potvrdi", f"ord:{side}:{plan.units}"), ("❌ Odustani", "cancel")]), edit)


def _fmt_value(value) -> str:
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False) -> None:
    s = _engine(context).settings
    rows = []
    pair: list[tuple[str, str]] = []
    for key, opt in OPTIONS.items():
        pair.append((f"{opt.label}: {_fmt_value(get_value(s, opt.attr))}", f"opt:{key}"))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([("♻️ Vrati na .env", "reset:ask")])
    await _send(
        update,
        "⚙️ <b>Postavke</b>\nDodirni postavku da je promijeniš. Promjene se čuvaju i nakon restarta.\n"
        "<i>Bilo koja vrijednost: /postavi rizik 0.7</i>",
        _kb(*rows),
        edit,
    )


async def show_option(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str) -> None:
    opt = OPTIONS[key]
    current = _fmt_value(get_value(_engine(context).settings, opt.attr))
    presets = [(("✅ " if p == current else "") + p, f"set:{key}:{p}") for p in opt.presets]
    await _send(
        update,
        f"⚙️ <b>{opt.label}</b>\nTrenutno: <b>{current}</b>\n\n"
        f"Izaberi vrijednost ili pošalji:\n<code>/postavi {key} VRIJEDNOST</code>",
        _kb(presets, [("↩️ Nazad", "v:settings")]),
        edit=True,
    )


async def change_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str, raw: str) -> str:
    eng = _engine(context)
    value = apply(eng.settings, key, raw)
    _store(context).set_setting(key, value)
    if key in STRATEGY_KEYS:
        eng.reset_bar_tracking()
    if key == "interval":
        _schedule(context.application, eng.settings.check_interval)
    return f"✅ {OPTIONS[key].label}: <b>{_fmt_value(value)}</b>"


# ---------------------------------------------------------------------- komande


@authorized
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    await _send(
        update,
        HELP + f"\n\nRačun: <b>{html.escape(eng.broker.name)}</b> | Izvor: {html.escape(eng.feed.name)}",
        MAIN_MENU,
    )


@authorized
async def cmd_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_price(update, context)


@authorized
async def cmd_signal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_signal(update, context)


@authorized
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_status(update, context)


@authorized
async def cmd_positions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_positions(update, context)


@authorized
async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_history(update, context)


@authorized
async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await show_settings(update, context)


@authorized
async def cmd_buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    units = _parse_units(context.args or [])
    if units is None and not context.args:
        await show_buy_menu(update, context, BUY)
    else:
        await show_order_confirm(update, context, BUY, units)


@authorized
async def cmd_sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    units = _parse_units(context.args or [])
    if units is None and not context.args:
        await show_buy_menu(update, context, SELL)
    else:
        await show_order_confirm(update, context, SELL, units)


@authorized
async def cmd_close(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        pid = context.args[0].lstrip("#")
        await _send(update, "\n\n".join(await _engine(context).close(pid)))
    else:
        await show_positions(update, context)


@authorized
async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    arg = context.args[0].lower() if context.args else ""
    if arg in ("on", "uklj", "da", "1"):
        eng.auto_enabled = True
        _store(context).set_auto(True)
    elif arg in ("off", "isklj", "ne", "0"):
        eng.auto_enabled = False
        _store(context).set_auto(False)
    await show_auto(update, context)


@authorized
async def cmd_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []
    if len(args) != 2:
        lines = [f"<code>{k}</code> — {o.label}" for k, o in OPTIONS.items()]
        await _send(update, "Upotreba: <code>/postavi rizik 0.5</code>\n\nDostupno:\n" + "\n".join(lines))
        return
    await _send(update, await change_setting(update, context, args[0].lower(), args[1]))


@authorized
async def cmd_risk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await show_option(update, context, "rizik")
        return
    await _send(update, await change_setting(update, context, "rizik", context.args[0]))


@authorized
async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(update, "Vratiti sve postavke na vrijednosti iz .env fajla?", _kb([("✅ Da", "reset:do"), ("❌ Ne", "cancel")]))


async def _do_reset(context: ContextTypes.DEFAULT_TYPE) -> None:
    eng = _engine(context)
    _store(context).reset()
    fresh = Settings.from_env()
    for key, opt in OPTIONS.items():
        apply(eng.settings, key, str(get_value(fresh, opt.attr)))
    eng.reset_bar_tracking()
    _schedule(context.application, eng.settings.check_interval)


MENU_ACTIONS = {
    BTN_PRICE: show_price,
    BTN_SIGNAL: show_signal,
    BTN_STATUS: show_status,
    BTN_POSITIONS: show_positions,
    BTN_AUTO: show_auto,
    BTN_SETTINGS: show_settings,
    BTN_HISTORY: show_history,
}


@authorized
async def on_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip()
    if text == BTN_BUY:
        await show_buy_menu(update, context, BUY)
    elif text == BTN_SELL:
        await show_buy_menu(update, context, SELL)
    elif text == BTN_HELP:
        await _send(update, HELP, MAIN_MENU)
    elif text in MENU_ACTIONS:
        await MENU_ACTIONS[text](update, context)
    else:
        await _send(update, "Koristi dugmad ispod 👇 (ili /pomoc).", MAIN_MENU)


# ---------------------------------------------------------------------- dugmad (callback)


@authorized
async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    eng = _engine(context)
    data = query.data or ""
    kind, _, rest = data.partition(":")

    if kind == "cancel":
        await _send(update, "❌ Otkazano.", edit=True)
    elif kind == "v":
        views = {
            "price": show_price,
            "signal": show_signal,
            "status": show_status,
            "pos": show_positions,
            "settings": show_settings,
        }
        await views[rest](update, context, edit=True)
    elif kind == "buy":
        await show_buy_menu(update, context, rest, edit=True)
    elif kind == "sz":
        side, size = rest.split(":")
        await show_order_confirm(update, context, side, None if size == "auto" else float(size), edit=True)
    elif kind == "ord":
        side, units = rest.split(":")
        await _send(update, "⏳ Šaljem nalog...", edit=True)
        msgs = await eng.execute(side, float(units))
        await _send(update, "\n\n".join(msgs), _kb([("📂 Pozicije", "v:pos")]), edit=True)
    elif kind == "cq":
        what = "SVE pozicije" if rest == "all" else f"poziciju #{rest}"
        await _send(
            update,
            f"Zatvoriti {what}?",
            _kb([("✅ Da, zatvori", f"cl:{rest}"), ("❌ Ne", "v:pos")]),
            edit=True,
        )
    elif kind == "cl":
        await _send(update, "⏳ Zatvaram...", edit=True)
        msgs = await eng.close(None if rest == "all" else rest)
        await _send(update, "\n\n".join(msgs), _kb([("📂 Pozicije", "v:pos")]), edit=True)
    elif kind == "auto":
        if rest == "ask":
            await _send(
                update,
                f"⚠️ Uključiti auto-trading na računu <b>{html.escape(eng.broker.name)}</b>?\n"
                "Bot će sam otvarati i zatvarati pozicije.",
                _kb([("✅ Da, uključi", "auto:on"), ("❌ Ne", "cancel")]),
                edit=True,
            )
            return
        eng.auto_enabled = rest == "on"
        _store(context).set_auto(eng.auto_enabled)
        await show_auto(update, context, edit=True)
    elif kind == "opt":
        await show_option(update, context, rest)
    elif kind == "set":
        key, value = rest.split(":", 1)
        await change_setting(update, context, key, value)
        await show_option(update, context, key)
    elif kind == "reset":
        if rest == "ask":
            await _send(
                update,
                "Vratiti sve postavke na vrijednosti iz .env fajla?",
                _kb([("✅ Da", "reset:do"), ("❌ Ne", "v:settings")]),
                edit=True,
            )
        else:
            await _do_reset(context)
            await show_settings(update, context, edit=True)


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


def _schedule(app: Application, interval: int) -> None:
    old = app.bot_data.get("job")
    if old is not None:
        old.schedule_removal()
    app.bot_data["job"] = app.job_queue.run_repeating(market_job, interval=interval, first=5)


async def _post_init(app: Application) -> None:
    engine: TradingEngine = app.bot_data["engine"]
    await app.bot.set_my_commands(COMMANDS)
    try:
        await engine.broker.balance()  # učita naziv računa (npr. "MetaTrader 5 REAL #123")
    except Exception as exc:  # noqa: BLE001
        log.warning("Ne mogu pročitati račun pri pokretanju: %s", exc)
    state = "✅ UKLJUČEN" if engine.auto_enabled else "⏸ ISKLJUČEN"
    for chat_id in engine.settings.allowed_chat_ids:
        try:
            await app.bot.send_message(
                chat_id,
                f"🤖 <b>Gold Bot pokrenut</b>\nRačun: <b>{html.escape(engine.broker.name)}</b>\n"
                f"Izvor: {html.escape(engine.feed.name)}\nAuto-trading: {state}",
                parse_mode=ParseMode.HTML,
                reply_markup=MAIN_MENU,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Slanje poruke u %s nije uspjelo: %s", chat_id, exc)


def build_application(token: str, engine: TradingEngine, store: OverrideStore | None = None) -> Application:
    app = Application.builder().token(token).post_init(_post_init).build()
    app.bot_data["engine"] = engine
    app.bot_data["store"] = store or OverrideStore(None)

    handlers = {
        ("start", "pomoc", "help", "meni"): cmd_start,
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
        ("postavi", "set"): cmd_set,
        ("postavke_reset",): cmd_reset,
        ("rizik", "risk"): cmd_risk,
    }
    for names, fn in handlers.items():
        app.add_handler(CommandHandler(list(names), fn))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_menu_button))

    _schedule(app, engine.settings.check_interval)
    return app
