import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrations.telegram_service import TelegramService


class DummyLogger:
    def debug(self, *args, **kwargs):
        return None


class DummyController:
    def __init__(self):
        self.open_chart_calls = []
        self.chart_capture_calls = []
        self.ask_calls = []
        self.direct_actions = []

    async def telegram_status_text(self):
        return "status"

    def telegram_management_text(self):
        return "management"

    async def telegram_balances_text(self):
        return "balances"

    async def telegram_positions_text(self):
        return "positions"

    async def telegram_open_orders_text(self):
        return "orders"

    async def telegram_recommendations_text(self):
        return "recommendations"

    async def telegram_performance_text(self):
        return "performance"

    async def market_chat_trade_history_summary(self, limit=300, open_window=True):
        return f"history:{limit}:{open_window}"

    async def telegram_settings_text(self, open_window=True):
        return f"settings:{open_window}"

    async def telegram_health_text(self, open_window=True):
        return f"health:{open_window}"

    async def telegram_quant_pm_text(self, open_window=True):
        return f"quantpm:{open_window}"

    async def telegram_journal_text(self, open_window=True):
        return f"journal:{open_window}"

    async def telegram_journal_review_text(self, open_window=True):
        return f"review:{open_window}"

    async def telegram_logs_text(self, open_window=True):
        return f"logs:{open_window}"

    async def telegram_position_analysis_text(self, open_window=True):
        return f"analysis:{open_window}"

    async def capture_telegram_screenshot(self):
        return None

    async def ask_openai_about_app(self, question, conversation=None):
        self.ask_calls.append((question, list(conversation or [])))
        return f"answer:{question}"

    async def handle_market_chat_action(self, question):
        self.direct_actions.append(question)
        return f"direct:{question}"

    async def telegram_open_chart(self, symbol, timeframe=None):
        self.open_chart_calls.append((symbol, timeframe))
        return {"ok": True, "message": f"opened {symbol} {timeframe or ''}".strip()}

    async def capture_chart_screenshot(self, symbol=None, timeframe=None, prefix="chart"):
        self.chart_capture_calls.append((symbol, timeframe, prefix))
        return "output/screenshots/chart.png"


class RecordingTelegramService(TelegramService):
    def __init__(self, controller):
        super().__init__(controller=controller, logger=DummyLogger(), bot_token="token", chat_id="1", enabled=True)
        self.messages = []
        self.edited_messages = []
        self.photos = []
        self.callback_answers = []

    async def send_message(self, text, include_keyboard=False, reply_markup=None):
        self.messages.append((self._localize_text(text), bool(include_keyboard), reply_markup))
        return True

    async def _edit_message(self, chat_id, message_id, text, reply_markup=None):
        self.edited_messages.append((str(chat_id), message_id, self._localize_text(text), reply_markup))
        return True

    async def send_photo(self, file_path, caption=None):
        self.photos.append((file_path, self._localize_text(caption)))
        return True

    async def _answer_callback_query(self, callback_id, text=""):
        self.callback_answers.append((callback_id, text))
        return True


def build_update(text):
    return {
        "update_id": 1,
        "message": {
            "text": text,
            "chat": {"id": "1"},
        },
    }


def build_callback_update(data, callback_id="cb-1", message_id=99):
    return {
        "update_id": 2,
        "callback_query": {
            "id": callback_id,
            "data": data,
            "message": {
                "message_id": message_id,
                "chat": {"id": "1"},
            },
        },
    }


def test_parse_chart_args_supports_symbol_and_timeframe():
    service = RecordingTelegramService(DummyController())
    parsed = service._parse_chart_args("EUR/USD 1h")

    assert parsed["symbol"] == "EUR/USD"
    assert parsed["timeframe"] == "1h"


def test_chart_command_opens_chart():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/chart BTC/USDT 15m")))

    assert controller.open_chart_calls == [("BTC/USDT", "15m")]
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "opened BTC/USDT 15m"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("markets")


def test_chartshot_command_captures_and_sends_photo():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/chartshot EUR/USD 1h")))

    assert controller.chart_capture_calls == [("EUR/USD", "1h", "telegram_chart")]
    assert service.photos == [("output/screenshots/chart.png", "Sopotek chart EUR/USD (1h)")]


def test_chartshot_command_without_symbol_uses_current_chart_context():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/chartshot")))

    assert controller.chart_capture_calls == [(None, "", "telegram_chart")]
    assert service.photos == [("output/screenshots/chart.png", "Sopotek chart current chart (1h)")]


def test_help_command_requests_keyboard():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/help")))

    assert service.messages
    assert service.messages[-1][1] is True
    assert "/menu" in service.messages[-1][0]
    assert "Keyboard sections:" in service.messages[-1][0]
    assert "BotFather" in service.messages[-1][0]
    assert "platform.openai.com/api-keys" in service.messages[-1][0]
    assert "/trade ..." not in service.messages[-1][0]
    assert "/chart SYMBOL" not in service.messages[-1][0]


def test_command_keyboard_contains_core_buttons():
    service = RecordingTelegramService(DummyController())

    keyboard = service._command_keyboard_markup()

    assert keyboard["resize_keyboard"] is True
    flat_labels = [button["text"] for row in keyboard["keyboard"] for button in row]
    assert "Overview" in flat_labels
    assert "Portfolio" in flat_labels
    assert "Market Intel" in flat_labels
    assert "Performance" in flat_labels
    assert "Workspace" in flat_labels
    assert "Controls" in flat_labels
    assert "Screenshot" in flat_labels
    assert "Quick Brief" in flat_labels
    assert all("EUR/USD" not in label for label in flat_labels)
    assert all("trade buy" not in label.lower() for label in flat_labels)


def test_menu_command_opens_overview_panel():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/menu")))

    message, include_keyboard, reply_markup = service.messages[-1]
    assert "Sopotek Pilot Remote Console" in message
    assert "status" in message
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("overview")


def test_keyboard_alias_opens_portfolio_panel():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("Portfolio")))

    message, include_keyboard, reply_markup = service.messages[-1]
    assert "Portfolio Console" in message
    assert "balances" in message
    assert "positions" in message
    assert "orders" in message
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("portfolio")


def test_management_command_returns_management_summary():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/management")))

    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "management"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_history_command_returns_trade_history_summary():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/history")))

    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "history:300:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("performance")


def test_settings_command_returns_rich_settings_response():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/settings")))

    assert controller.direct_actions == []
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "settings:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_notify_trade_includes_rejection_reason():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(
        service.notify_trade(
            {
                "symbol": "EUR/PLN",
                "side": "sell",
                "status": "rejected",
                "price": 4.29385,
                "amount": 1.35,
                "pnl": None,
                "order_id": None,
                "timestamp": "2026-03-31T11:56:49.767530+00:00",
                "reason": "Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old).",
            }
        )
    )

    text, _include_keyboard, reply_markup = service.messages[-1]
    assert "Status: <b>REJECTED</b>" in text
    assert "Reason: <code>Live trade blocked: candle data for EUR/PLN 1h is stale (unknown old).</code>" in text
    assert reply_markup == service._menu_markup("portfolio")


def test_notify_trade_close_includes_strategy_entry_close_and_pnl():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(
        service.notify_trade_close(
            {
                "symbol": "BTC/USDT",
                "side": "sell",
                "status": "closed",
                "strategy_name": "EMA Cross",
                "entry_price": 100.0,
                "exit_price": 104.5,
                "size": 0.5,
                "pnl": 2.25,
                "order_id": "close-42",
                "timestamp": "2026-04-07T14:12:00+00:00",
            }
        )
    )

    text, _include_keyboard, reply_markup = service.messages[-1]
    assert "<b>Trade Closed</b>" in text
    assert "Strategy: <code>EMA Cross</code>" in text
    assert "Entry price: <code>100</code>" in text
    assert "Close price: <code>104.5</code>" in text
    assert "PnL: <code>+2.25</code>" in text
    assert reply_markup == service._menu_markup("portfolio")


def test_health_command_returns_rich_health_response():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/health")))

    assert controller.direct_actions == []
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "health:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_quantpm_command_returns_rich_quant_summary():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/quantpm")))

    assert controller.direct_actions == []
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "quantpm:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_journal_button_returns_journal_summary():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/journal")))

    assert controller.direct_actions == []
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "journal:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_review_button_returns_review_summary():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/review")))

    assert controller.direct_actions == []
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "review:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_logs_button_returns_log_summary():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/logs")))

    assert controller.direct_actions == []
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "logs:True"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("workspace")


def test_generic_refresh_action_still_routes_to_direct_action_handler():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/refreshmarkets")))

    assert controller.direct_actions[-1] == "refresh markets"
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "direct:refresh markets"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("controls")


def test_view_callback_edits_existing_message_into_portfolio_panel():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_callback_update("view:portfolio")))

    assert service.callback_answers[-1] == ("cb-1", "Updated.")
    assert service.edited_messages
    chat_id, message_id, text, reply_markup = service.edited_messages[-1]
    assert chat_id == "1"
    assert message_id == 99
    assert "Portfolio Console" in text
    assert reply_markup == service._menu_markup("portfolio")


def test_control_confirmation_callback_requires_confirm_before_action():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_callback_update("control:prompt:killswitch", message_id=101)))

    assert service.callback_answers[-1] == ("cb-1", "Confirm or cancel.")
    assert service.edited_messages
    _chat_id, _message_id, text, reply_markup = service.edited_messages[-1]
    assert "Confirm Remote Control" in text
    confirm_callback = reply_markup["inline_keyboard"][0][0]["callback_data"]

    asyncio.run(service._handle_update(build_callback_update(confirm_callback, callback_id="cb-2", message_id=101)))

    assert controller.direct_actions[-1] == "activate kill switch"
    assert service.callback_answers[-1] == ("cb-2", "Kill switch request sent.")
    _chat_id, _message_id, text, reply_markup = service.edited_messages[-1]
    assert text == "direct:activate kill switch"
    assert reply_markup == service._menu_markup("controls")


def test_plain_text_message_gets_sopotek_pilot_reply():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("What is my current status?")))

    assert controller.ask_calls
    assert controller.ask_calls[-1][0] == "What is my current status?"
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "answer:What is my current status?"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("overview")


def test_controller_runtime_translation_is_applied_to_outgoing_messages():
    controller = DummyController()
    controller.translate_runtime_text = lambda text, rich=False: f"fr::{text}"
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/management")))

    assert service.messages[-1][0] == "fr::management"


def test_trade_command_routes_to_direct_action_handler():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/trade buy EUR/USD amount 1000 confirm")))

    assert controller.direct_actions == ["trade buy EUR/USD amount 1000 confirm"]
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "direct:trade buy EUR/USD amount 1000 confirm"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("controls")


def test_buy_shortcut_builds_trade_command():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/buy BTC/USDT amount 0.01 type market confirm")))

    assert controller.direct_actions == ["trade buy BTC/USDT amount 0.01 type market confirm"]
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "direct:trade buy BTC/USDT amount 0.01 type market confirm"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("controls")


def test_trade_preview_includes_inline_confirmation_buttons():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/trade buy EUR/USD amount 1000")))

    assert controller.direct_actions == ["trade buy EUR/USD amount 1000"]
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "direct:trade buy EUR/USD amount 1000"
    assert include_keyboard is False
    assert reply_markup is not None
    inline_row = reply_markup["inline_keyboard"][0]
    assert inline_row[0]["text"] == "Confirm Trade"
    assert inline_row[1]["text"] == "Cancel Trade"


def test_trade_confirm_button_executes_pending_trade():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/trade buy EUR/USD amount 1000")))
    reply_markup = service.messages[-1][2]
    callback_data = reply_markup["inline_keyboard"][0][0]["callback_data"]

    asyncio.run(service._handle_update(build_callback_update(callback_data)))

    assert controller.direct_actions[-1] == "trade buy EUR/USD amount 1000 confirm"
    assert service.callback_answers[-1] == ("cb-1", "Trade submitted.")
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "direct:trade buy EUR/USD amount 1000 confirm"
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("controls")


def test_trade_cancel_button_clears_pending_trade():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("/trade buy EUR/USD amount 1000")))
    reply_markup = service.messages[-1][2]
    callback_data = reply_markup["inline_keyboard"][0][1]["callback_data"]

    asyncio.run(service._handle_update(build_callback_update(callback_data, callback_id="cb-2")))

    assert service.callback_answers[-1] == ("cb-2", "Trade request canceled.")
    message, include_keyboard, reply_markup = service.messages[-1]
    assert message == "Trade request canceled."
    assert include_keyboard is False
    assert reply_markup == service._menu_markup("controls")


def test_chat_history_is_passed_to_follow_up_messages():
    controller = DummyController()
    service = RecordingTelegramService(controller)

    asyncio.run(service._handle_update(build_update("First question")))
    asyncio.run(service._handle_update(build_update("Second question")))

    assert len(controller.ask_calls) == 2
    second_conversation = controller.ask_calls[1][1]
    assert second_conversation
    assert second_conversation[0]["role"] == "user"
    assert second_conversation[0]["content"] == "First question"

