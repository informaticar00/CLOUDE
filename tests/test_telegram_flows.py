"""Simulira dodire dugmadi u Telegramu bez stvarne veze."""

import asyncio
import json
from types import SimpleNamespace as NS

from goldbot import telegram_bot as tb
from goldbot.broker import PaperBroker
from goldbot.config import Settings, StrategyParams
from goldbot.engine import TradingEngine
from goldbot.overrides import OverrideStore

from .helpers import FakeFeed

CHAT = 42


class Recorder:
    def __init__(self):
        self.sent = []  # (tekst, markup)

    async def reply_text(self, text, **kw):
        self.sent.append((text, kw.get("reply_markup")))

    async def edit_message_text(self, text, **kw):
        self.sent.append((text, kw.get("reply_markup")))

    async def answer(self, *a, **kw):
        pass


def buttons(markup):
    return {b.text: b.callback_data for row in markup.inline_keyboard for b in row}


class Harness:
    def __init__(self, tmp_path):
        feed = FakeFeed([2010 - i for i in range(20)] + [2005.0], price=2000.0)
        self.broker = PaperBroker(feed, 10_000, 0.0, None)
        s = Settings(
            telegram_token="x",
            allowed_chat_ids={CHAT},
            strategy=StrategyParams(ema_fast=3, ema_slow=6, ema_trend=0, rsi_period=5, atr_period=5),
        )
        self.engine = TradingEngine(s, feed, self.broker)
        self.store_path = tmp_path / "postavke.json"
        self.jobs = []
        job_queue = NS(run_repeating=lambda fn, interval, first: self.jobs.append(interval) or NS(schedule_removal=lambda: None))
        self.app = NS(bot_data={"engine": self.engine, "store": OverrideStore(str(self.store_path))}, job_queue=job_queue)
        self.rec = Recorder()

    def ctx(self, args=None):
        return NS(application=self.app, args=args or [])

    def text(self, text, chat=CHAT):
        upd = NS(effective_chat=NS(id=chat), effective_message=NS(text=text, reply_text=self.rec.reply_text), callback_query=None)
        asyncio.run(tb.on_menu_button(upd, self.ctx()))
        return self.rec.sent[-1]

    def command(self, fn, args=None):
        upd = NS(effective_chat=NS(id=CHAT), effective_message=NS(text="", reply_text=self.rec.reply_text), callback_query=None)
        asyncio.run(fn(upd, self.ctx(args)))
        return self.rec.sent[-1]

    def tap(self, data):
        q = NS(data=data, answer=self.rec.answer, edit_message_text=self.rec.edit_message_text)
        upd = NS(effective_chat=NS(id=CHAT), effective_message=NS(reply_text=self.rec.reply_text), callback_query=q)
        asyncio.run(tb.on_callback(upd, self.ctx()))
        return self.rec.sent[-1]


def run(coro):
    return asyncio.run(coro)


def test_unauthorized_chat_is_rejected(tmp_path):
    h = Harness(tmp_path)
    text, _ = h.text(tb.BTN_PRICE, chat=999)
    assert "Nemaš pristup" in text and "999" in text


def test_buy_flow_with_buttons(tmp_path):
    h = Harness(tmp_path)
    text, markup = h.text(tb.BTN_BUY)
    assert "KUPI" in text
    text, markup = h.tap(buttons(markup)["2 oz"])
    assert "Potvrdi nalog" in text and "2 oz" in text
    text, markup = h.tap(buttons(markup)["✅ Potvrdi"])
    assert "Ručni nalog" in text
    positions = run(h.broker.positions())
    assert len(positions) == 1 and positions[0].units == 2

    # zatvaranje iz liste pozicija: dodir -> potvrda -> zatvoreno
    text, markup = h.text(tb.BTN_POSITIONS)
    pid = positions[0].id
    text, markup = h.tap(buttons(markup)[f"❌ Zatvori #{pid}"])
    assert "Zatvoriti" in text
    text, _ = h.tap(buttons(markup)["✅ Da, zatvori"])
    assert "Zatvoreno" in text
    assert run(h.broker.positions()) == []


def test_auto_size_and_cancel(tmp_path):
    h = Harness(tmp_path)
    _, markup = h.text(tb.BTN_SELL)
    auto_btn = next(k for k in buttons(markup) if k.startswith("⚖️"))
    text, markup = h.tap(buttons(markup)[auto_btn])
    assert "PRODAJ" in text
    text, _ = h.tap(buttons(markup)["❌ Odustani"])
    assert "Otkazano" in text
    assert run(h.broker.positions()) == []


def test_auto_trading_toggle_needs_confirmation_and_persists(tmp_path):
    h = Harness(tmp_path)
    _, markup = h.text(tb.BTN_AUTO)
    text, markup = h.tap(buttons(markup)["✅ Uključi"])
    assert "Uključiti" in text and not h.engine.auto_enabled
    text, _ = h.tap(buttons(markup)["✅ Da, uključi"])
    assert h.engine.auto_enabled and "UKLJUČEN" in text
    assert json.loads(h.store_path.read_text())["auto"] is True


def test_settings_change_via_buttons_persists_and_reloads(tmp_path):
    h = Harness(tmp_path)
    _, markup = h.text(tb.BTN_SETTINGS)
    risk_btn = next(k for k in buttons(markup) if k.startswith("Rizik"))
    text, markup = h.tap(buttons(markup)[risk_btn])
    assert "Trenutno: <b>1</b>" in text
    text, markup = h.tap(buttons(markup)["0.5"])
    assert h.engine.settings.risk_pct == 0.5 and "✅ 0.5" in buttons(markup)

    h.engine.last_bar_time = "x"
    _, markup = h.tap("opt:timeframe")
    h.tap(buttons(markup)["H1"])
    assert h.engine.settings.timeframe == "H1"
    assert h.engine.last_bar_time is None  # stari signal se ne izvršava

    h.command(tb.cmd_set, ["interval", "300"])
    assert h.jobs[-1] == 300

    # nova instanca učitava sačuvano
    fresh = Settings(telegram_token="x", allowed_chat_ids={1})
    OverrideStore(str(h.store_path)).load_into(fresh)
    assert (fresh.risk_pct, fresh.timeframe, fresh.check_interval) == (0.5, "H1", 300)


def test_invalid_setting_is_rejected(tmp_path):
    h = Harness(tmp_path)
    text, _ = h.command(tb.cmd_set, ["rizik", "50"])
    assert "⚠️" in text and h.engine.settings.risk_pct == 1.0
    text, _ = h.command(tb.cmd_set, ["ema_brza", "100"])  # mora biti < spora
    assert "⚠️" in text
    text, _ = h.command(tb.cmd_set, ["nepostoji", "1"])
    assert "Nepoznata" in text


def test_info_views(tmp_path):
    h = Harness(tmp_path)
    assert "XAU/USD" in h.text(tb.BTN_PRICE)[0]
    assert "Analiza" in h.text(tb.BTN_SIGNAL)[0]
    assert "Saldo" in h.text(tb.BTN_STATUS)[0]
    assert "trejdova" in h.text(tb.BTN_HISTORY)[0]
    text, markup = h.text(tb.BTN_HELP)
    assert markup is tb.MAIN_MENU
    assert "Koristi dugmad" in h.text("bla bla")[0]
