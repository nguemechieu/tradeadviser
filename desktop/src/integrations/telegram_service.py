from __future__ import annotations

"""
InvestPro Telegram Service

A Telegram remote console for a desktop/server trading workspace.

Features:
- Start/stop lifecycle.
- Telegram long polling.
- Secure single-chat authorization.
- HTML-safe message sending.
- Long message chunking.
- Photo/screenshot upload.
- Persistent keyboard.
- Inline menu panels.
- Portfolio/market/performance/workspace/control views.
- Confirmation-gated trading actions.
- Confirmation-gated critical controls.
- Chat history for /ask.
- Controller compatibility helpers.
- Graceful failure when optional controller methods are missing.

Important:
This service should not make trading decisions by itself.
It only forwards commands to the controller, which should enforce:
- account permissions
- risk limits
- kill switch
- confirmation requirements
- audit logging
"""

import asyncio
import html
import inspect
import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp

try:
    from integrations.trade_notifications import (
        build_trade_close_summary,
        format_trade_close_html,
        trade_notification_reason,
    )
except Exception:  # pragma: no cover - keeps module importable during refactors
    def trade_notification_reason(trade: dict[str, Any]) -> str:
        return str(trade.get("reason") or trade.get("close_reason") or "")

    def build_trade_close_summary(trade: dict[str, Any]) -> dict[str, Any]:
        return dict(trade or {})

    def format_trade_close_html(summary: dict[str, Any]) -> str:
        symbol = html.escape(str(summary.get("symbol") or "-"))
        pnl = html.escape(str(summary.get("pnl") or "-"))
        return f"<b>Trade Closed</b>\nSymbol: <code>{symbol}</code>\nPnL: <code>{pnl}</code>"


MAX_TELEGRAM_TEXT_LENGTH = 4096
SAFE_CHUNK_LENGTH = 3500
MAX_CALLBACK_DATA_LENGTH = 64
DEFAULT_POLL_TIMEOUT_SECONDS = 30
DEFAULT_HTTP_TIMEOUT_SECONDS = 45
DEFAULT_PENDING_TTL_SECONDS = 180
DEFAULT_HISTORY_MESSAGES = 12


@dataclass(slots=True)
class PendingAction:
    chat_id: str
    action_text: str = ""
    action_key: str = ""
    created_at: float = field(default_factory=time.time)

    def expired(self, ttl_seconds: float) -> bool:
        return (time.time() - self.created_at) > ttl_seconds


class TelegramService:
    def __init__(
        self,
        controller: Any,
        logger: Optional[logging.Logger],
        bot_token: str,
        chat_id: Optional[str] = None,
        enabled: bool = False,
        *,
        app_name: str = "InvestPro",
        pending_ttl_seconds: float = DEFAULT_PENDING_TTL_SECONDS,
        history_messages: int = DEFAULT_HISTORY_MESSAGES,
        http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
        poll_timeout_seconds: int = DEFAULT_POLL_TIMEOUT_SECONDS,
    ) -> None:
        self.controller = controller
        self.logger = logger or logging.getLogger(__name__)
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.enabled = bool(enabled and self.bot_token)

        self.app_name = str(app_name or "InvestPro").strip() or "InvestPro"
        self.pending_ttl_seconds = max(15.0, float(pending_ttl_seconds))
        self.history_messages = max(
            2, int(history_messages or DEFAULT_HISTORY_MESSAGES))
        self.http_timeout_seconds = max(5.0, float(http_timeout_seconds))
        self.poll_timeout_seconds = max(1, int(poll_timeout_seconds))

        self._offset = 0
        self._poll_task: Optional[asyncio.Task[Any]] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._running = False

        self._chat_histories: dict[str, list[dict[str, str]]] = {}
        self._pending_trade_actions: dict[str, PendingAction] = {}
        self._pending_control_actions: dict[str, PendingAction] = {}

    # ------------------------------------------------------------------
    # Basic properties
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token)

    def can_send(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def is_running(self) -> bool:
        return bool(self._running and self._poll_task and not self._poll_task.done())

    @staticmethod
    def _trade_notification_reason(trade: dict[str, Any]) -> str:
        return trade_notification_reason(trade)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        if not self.enabled or not self.bot_token:
            return

        if self._poll_task and not self._poll_task.done():
            return

        self._running = True
        await self._ensure_session()

        self._poll_task = asyncio.create_task(
            self._poll_loop(), name="telegram_poll")

        if self.can_send():
            await self.send_message(self._welcome_text(), include_keyboard=True)

    async def stop(self) -> None:
        self._running = False

        if self._poll_task and not self._poll_task.done():
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        self._poll_task = None

        if self._session is not None and not self._session.closed:
            await self._session.close()

        self._session = None

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.http_timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)

    # ------------------------------------------------------------------
    # Telegram API helpers
    # ------------------------------------------------------------------

    async def _api_get(self, method: str, *, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        await self._ensure_session()
        assert self._session is not None

        async with self._session.get(f"{self.base_url}/{method}", params=params or {}) as response:
            return await response.json(content_type=None)

    async def _api_post(
        self,
        method: str,
        *,
        data: Optional[Any] = None,
    ) -> dict[str, Any]:
        await self._ensure_session()
        assert self._session is not None

        async with self._session.post(f"{self.base_url}/{method}", data=data or {}) as response:
            return await response.json(content_type=None)

    async def _maybe_await(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return await value
        return value

    # ------------------------------------------------------------------
    # Send methods
    # ------------------------------------------------------------------

    async def send_message(
        self,
        text: Any,
        include_keyboard: bool = False,
        reply_markup: Optional[dict[str, Any]] = None,
        *,
        chat_id: Optional[str] = None,
    ) -> bool:
        target_chat_id = str(chat_id or self.chat_id or "").strip()
        if not self.bot_token or not target_chat_id:
            return False

        try:
            localized_text = self._localize_text(str(text or ""))
            chunks = self._split_message_chunks(localized_text)
            sent_any = False

            for index, chunk in enumerate(chunks):
                payload: dict[str, Any] = {
                    "chat_id": target_chat_id,
                    "text": chunk,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": "true",
                }

                markup_payload = None
                if index == len(chunks) - 1:
                    if reply_markup is not None:
                        markup_payload = reply_markup
                    elif include_keyboard:
                        markup_payload = self._command_keyboard_markup()

                if markup_payload is not None:
                    payload["reply_markup"] = json.dumps(markup_payload)

                result = await self._api_post("sendMessage", data=payload)
                if not result.get("ok"):
                    self.logger.debug(
                        "Telegram sendMessage failed: %s", result)
                    return False

                sent_any = True

            return sent_any

        except Exception as exc:
            self.logger.debug("Telegram send_message failed: %s", exc)
            return False

    async def send_photo(
        self,
        file_path: str,
        caption: Optional[str] = None,
        *,
        chat_id: Optional[str] = None,
    ) -> bool:
        target_chat_id = str(chat_id or self.chat_id or "").strip()

        if not self.bot_token or not target_chat_id or not file_path or not os.path.exists(file_path):
            return False

        try:
            await self._ensure_session()
            assert self._session is not None

            data = aiohttp.FormData()
            data.add_field("chat_id", target_chat_id)

            if caption:
                data.add_field("caption", self._localize_text(str(caption)))
                data.add_field("parse_mode", "HTML")

            with open(file_path, "rb") as handle:
                data.add_field(
                    "photo",
                    handle,
                    filename=os.path.basename(file_path),
                    content_type="image/png",
                )
                async with self._session.post(f"{self.base_url}/sendPhoto", data=data) as response:
                    payload = await response.json(content_type=None)
                    if not payload.get("ok"):
                        self.logger.debug(
                            "Telegram sendPhoto failed: %s", payload)
                    return bool(payload.get("ok"))

        except Exception as exc:
            self.logger.debug("Telegram send_photo failed: %s", exc)
            return False

    async def _edit_message(
        self,
        chat_id: Any,
        message_id: Any,
        text: Any,
        reply_markup: Optional[dict[str, Any]] = None,
    ) -> bool:
        target_chat_id = str(chat_id or self.chat_id or "").strip()
        if not self.bot_token or not target_chat_id or message_id in (None, ""):
            return False

        localized_text = self._localize_text(str(text or ""))
        chunks = self._split_message_chunks(localized_text)

        if len(chunks) != 1:
            return False

        try:
            payload: dict[str, Any] = {
                "chat_id": target_chat_id,
                "message_id": int(message_id),
                "text": chunks[0],
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }

            if reply_markup is not None:
                payload["reply_markup"] = json.dumps(reply_markup)

            result = await self._api_post("editMessageText", data=payload)

            if result.get("ok"):
                return True

            description = str(result.get("description") or "").lower()
            return "message is not modified" in description

        except Exception as exc:
            self.logger.debug("Telegram editMessageText failed: %s", exc)
            return False

    async def _answer_callback_query(self, callback_id: str, text: str = "") -> bool:
        if not callback_id:
            return False

        try:
            result = await self._api_post(
                "answerCallbackQuery",
                data={
                    "callback_query_id": callback_id,
                    "text": str(text or "")[:200],
                },
            )
            return bool(result.get("ok"))

        except Exception as exc:
            self.logger.debug("Telegram answerCallbackQuery failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def notify_trade(self, trade: dict[str, Any]) -> None:
        if not self.can_send() or not isinstance(trade, dict):
            return

        symbol = html.escape(str(trade.get("symbol") or "-"))
        side = html.escape(str(trade.get("side") or "-").upper())
        status = html.escape(str(trade.get("status") or "-").upper())
        reason = html.escape(self._trade_notification_reason(trade))
        price = html.escape(str(trade.get("price", "-")))

        raw_size = trade.get("size", trade.get("amount", "-"))
        display_size = trade.get("applied_requested_mode_amount")
        display_mode = str(
            trade.get("requested_quantity_mode") or "").strip().lower()

        if display_size not in (None, "") and display_mode:
            size = f"{display_size} {display_mode}"
            if display_mode != "units" and raw_size not in (None, ""):
                size = f"{size} ({raw_size} units)"
        else:
            size = raw_size

        size_text = html.escape(str(size))
        pnl = html.escape(str(trade.get("pnl", "-")))
        order_id = html.escape(
            str(trade.get("order_id", trade.get("id", "-"))))
        timestamp = html.escape(
            str(trade.get("timestamp") or datetime.now(timezone.utc).isoformat()))

        reason_line = f"Reason: <code>{reason}</code>\n" if reason else ""

        message = (
            "<b>Trading Activity</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Side: <b>{side}</b>\n"
            f"Status: <b>{status}</b>\n"
            f"Price: <code>{price}</code>\n"
            f"Size: <code>{size_text}</code>\n"
            f"PnL: <code>{pnl}</code>\n"
            f"{reason_line}"
            f"Order ID: <code>{order_id}</code>\n"
            f"Time: <code>{timestamp}</code>"
        )

        await self.send_message(message, reply_markup=self._menu_markup("portfolio"))

    async def notify_trade_close(self, trade: dict[str, Any]) -> None:
        if not self.can_send() or not isinstance(trade, dict):
            return

        summary = build_trade_close_summary(trade)
        message = format_trade_close_html(summary)
        await self.send_message(message, reply_markup=self._menu_markup("portfolio"))

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_loop(self) -> None:
        backoff_seconds = 1.0

        while self._running:
            try:
                self._purge_expired_pending_actions()
                updates = await self._get_updates()

                for update in updates:
                    await self._handle_update(update)

                backoff_seconds = 1.0

            except asyncio.CancelledError:
                break

            except Exception as exc:
                self.logger.debug("Telegram polling error: %s", exc)
                await asyncio.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 1.5, 15.0)

    async def _get_updates(self) -> list[dict[str, Any]]:
        params = {
            "timeout": self.poll_timeout_seconds,
            "offset": self._offset + 1,
            "allowed_updates": json.dumps(["message", "edited_message", "callback_query"]),
        }

        payload = await self._api_get("getUpdates", params=params)

        if not payload.get("ok"):
            self.logger.debug("Telegram getUpdates failed: %s", payload)
            return []

        return payload.get("result", []) or []

    async def _handle_update(self, update: dict[str, Any]) -> None:
        update_id = int(update.get("update_id", self._offset) or self._offset)
        self._offset = max(self._offset, update_id)

        callback_query = update.get("callback_query") or {}
        callback_data = str(callback_query.get("data") or "").strip()

        if callback_data:
            await self._handle_callback_update(callback_query, callback_data)
            return

        message = update.get("message") or update.get("edited_message") or {}
        await self._handle_message_update(message)

    async def _handle_callback_update(self, callback_query: dict[str, Any], callback_data: str) -> None:
        callback_message = callback_query.get("message", {}) or {}
        callback_chat = callback_message.get("chat", {}) or {}
        callback_chat_id = str(callback_chat.get("id") or "").strip()
        callback_id = str(callback_query.get("id") or "").strip()
        callback_message_id = callback_message.get("message_id")

        if not callback_chat_id:
            await self._answer_callback_query(callback_id, "Unknown chat.")
            return

        if not self._is_authorized_chat(callback_chat_id):
            await self._answer_callback_query(callback_id, "Unauthorized.")
            return

        await self._handle_callback_query(
            callback_data,
            callback_chat_id,
            callback_id=callback_id,
            message_id=callback_message_id,
        )

    async def _handle_message_update(self, message: dict[str, Any]) -> None:
        text = str(message.get("text") or "").strip()
        chat = message.get("chat") or {}
        incoming_chat_id = str(chat.get("id") or "").strip()

        if not text or not incoming_chat_id:
            return

        if not self._is_authorized_chat(incoming_chat_id):
            return

        normalized_command = self._keyboard_alias_to_command(text)
        if normalized_command is not None:
            text = normalized_command

        command_text = text.split(None, 1)
        command_token = str(command_text[0] or "").strip().lower()
        command = command_token.split("@", 1)[0]
        args_text = command_text[1].strip() if len(command_text) > 1 else ""

        await self._dispatch_command(command, args_text, text, incoming_chat_id)

    def _is_authorized_chat(self, chat_id: Any) -> bool:
        incoming = str(chat_id or "").strip()

        if not incoming:
            return False

        # If no chat_id configured, allow the first chat to interact but do not
        # set it automatically. This helps setup commands without silently
        # trusting a random chat.
        if not self.chat_id:
            return True

        return incoming == self.chat_id

    # ------------------------------------------------------------------
    # Command dispatch
    # ------------------------------------------------------------------

    async def _dispatch_command(
        self,
        command: str,
        args_text: str,
        original_text: str,
        chat_id: str,
    ) -> None:
        if command == "/start":
            await self.send_message(self._welcome_text(), include_keyboard=True, chat_id=chat_id)
            await self._show_menu_view("overview", chat_id)
            return

        if command in {"/help", "/commands"}:
            await self.send_message(self._help_text(), include_keyboard=True, chat_id=chat_id)
            return

        if command in {"/menu", "/home"}:
            await self._show_menu_view("overview", chat_id)
            return

        if command == "/portfolio":
            await self._show_menu_view("portfolio", chat_id)
            return

        if command in {"/markets", "/marketintel"}:
            await self._show_menu_view("markets", chat_id)
            return

        if command == "/workspace":
            await self._show_menu_view("workspace", chat_id)
            return

        if command == "/controls":
            await self._show_menu_view("controls", chat_id)
            return

        if command == "/status":
            await self._send_section_text(await self._controller_text("telegram_status_text"), "overview", chat_id)
            return

        if command == "/management":
            await self._send_section_text(await self._controller_text("telegram_management_text"), "workspace", chat_id)
            return

        if command == "/balances":
            await self._send_section_text(await self._controller_text("telegram_balances_text"), "portfolio", chat_id)
            return

        if command == "/positions":
            await self._send_section_text(await self._controller_text("telegram_positions_text"), "portfolio", chat_id)
            return

        if command in {"/orders", "/openorders"}:
            await self._send_section_text(await self._controller_text("telegram_open_orders_text"), "portfolio", chat_id)
            return

        if command == "/recommendations":
            await self._send_section_text(await self._controller_text("telegram_recommendations_text"), "markets", chat_id)
            return

        if command == "/performance":
            await self._send_section_text(await self._controller_text("telegram_performance_text"), "performance", chat_id)
            return

        if command in {"/history", "/journalsummary"}:
            await self._send_section_text(await self._history_summary(limit=300, open_window=True), "performance", chat_id)
            return

        if command in {"/analysis", "/positionanalysis"}:
            await self._send_section_text(
                await self._controller_text("telegram_position_analysis_text", open_window=True),
                "markets",
                chat_id,
            )
            return

        if command == "/screenshot":
            await self._send_terminal_screenshot(chat_id=chat_id)
            return

        if command == "/chart":
            parsed = self._parse_chart_args(args_text)
            if not parsed.get("symbol"):
                await self.send_message(
                    "Usage: /chart SYMBOL [TIMEFRAME]. Example: <code>/chart EUR/USD 1h</code>",
                    reply_markup=self._menu_markup("markets"),
                    chat_id=chat_id,
                )
                return

            result = await self._call_controller_method(
                "telegram_open_chart",
                parsed["symbol"],
                parsed.get("timeframe"),
            )
            message = result.get("message") if isinstance(
                result, dict) else result
            await self._send_section_text(message or "Chart request processed.", "markets", chat_id)
            return

        if command in {"/chartshot", "/chartphoto", "/sendchart"}:
            parsed = self._parse_chart_args(args_text)
            await self._send_chart_screenshot(parsed.get("symbol"), parsed.get("timeframe"), chat_id=chat_id)
            return

        rich_action_answer = await self._handle_rich_action_command(command, chat_id)
        if rich_action_answer is not None:
            await self._send_section_text(rich_action_answer, "workspace", chat_id)
            return

        action_text = self._slash_action_commands().get(command)
        if action_text:
            answer = await self._handle_direct_action(action_text, chat_id)
            await self._send_section_text(answer, "controls", chat_id)
            return

        if command in {"/ask", "/chat"}:
            question = args_text
            if not question:
                await self.send_message(
                    "Send a question after /ask or /chat.",
                    reply_markup=self._menu_markup("help"),
                    chat_id=chat_id,
                )
                return

            answer = await self._ask_controller(question, chat_id)
            await self._send_section_text(answer, "overview", chat_id)
            return

        if command in {"/trade", "/buy", "/sell"}:
            await self._handle_trade_command(command, args_text, chat_id)
            return

        if command.startswith("/"):
            await self.send_message(self._help_text(), include_keyboard=True, chat_id=chat_id)
            return

        answer = await self._ask_controller(original_text, chat_id)
        await self._send_section_text(answer, "overview", chat_id)

    async def _handle_trade_command(self, command: str, args_text: str, chat_id: str) -> None:
        action_text = self._build_trade_action_text(command, args_text)

        if not action_text:
            await self.send_message(
                "Usage: <code>/trade buy EUR/USD amount 1000 confirm</code> or "
                "<code>/buy EUR/USD amount 0.01 type market confirm</code>",
                reply_markup=self._menu_markup("controls"),
                chat_id=chat_id,
            )
            return

        if "confirm" in action_text.lower():
            answer = await self._handle_direct_action(action_text, chat_id)
            await self._send_section_text(answer, "controls", chat_id)
            return

        preview = await self._handle_direct_action(action_text, chat_id)
        token = self._register_pending_trade_action(chat_id, action_text)

        await self.send_message(
            preview,
            reply_markup=self._trade_confirmation_markup(token),
            chat_id=chat_id,
        )

    # ------------------------------------------------------------------
    # Text / keyboard UI
    # ------------------------------------------------------------------

    def _welcome_text(self) -> str:
        app = html.escape(self.app_name)
        return (
            f"<b>{app} Remote Console</b>\n"
            "Telegram is connected to the trading workspace.\n"
            "Use the keyboard for quick sections, or open <code>/menu</code> for the live control panel."
        )

    def _help_text(self) -> str:
        app = html.escape(self.app_name)
        return (
            f"<b>{app} Telegram Console</b>\n"
            "Keyboard sections:\n"
            "Overview, Portfolio, Market Intel, Performance, Workspace, Controls, Journal, Screenshot, Help, Quick Brief\n\n"
            "Core commands:\n"
            "/menu - open the live remote console\n"
            "/portfolio - balances, positions, and open orders\n"
            "/markets - recommendations and position analysis\n"
            "/workspace - management, settings, and health panels\n"
            "/controls - remote refresh and trading controls\n"
            "/status - trading status and AI scope\n"
            "/management - broker, AI, and Telegram management summary\n"
            "/balances - account balances\n"
            "/positions - open positions\n"
            "/orders - open exchange orders\n"
            "/recommendations - top trade recommendations\n"
            "/performance - performance snapshot\n"
            "/history - closed trade history summary\n"
            "/analysis - broker position analysis summary\n"
            "/screenshot - terminal screenshot\n"
            "/chart SYMBOL [TIMEFRAME] - open a chart in the app\n"
            "/chartshot SYMBOL [TIMEFRAME] - capture a chart and send it here\n"
            "/settings - open settings in the app\n"
            "/health - open system health\n"
            "/quantpm - open Quant PM\n"
            "/journal - open closed journal\n"
            "/review - open journal review\n"
            "/logs - open logs\n"
            "/refreshmarkets - refresh markets\n"
            "/reloadbalances - reload balances\n"
            "/refreshchart - refresh the active chart\n"
            "/refreshorderbook - refresh the active order book\n"
            "/autotradeon - enable AI trading\n"
            "/autotradeoff - stop AI trading\n"
            "/killswitch - activate emergency kill switch\n"
            "/resume - resume trading after a stop\n"
            "/ask &lt;question&gt; - ask the assistant about the app or market context\n"
            "/help - show this message\n\n"
            "Security tip: keep your Telegram bot token, broker keys, and OpenAI key private."
        )

    def _command_keyboard_markup(self) -> dict[str, Any]:
        return {
            "keyboard": [
                [{"text": "Overview"}, {"text": "Portfolio"},
                    {"text": "Market Intel"}],
                [{"text": "Performance"}, {"text": "Workspace"}, {"text": "Controls"}],
                [{"text": "Journal"}, {"text": "Screenshot"}, {"text": "Help"}],
                [{"text": "Quick Brief"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "one_time_keyboard": False,
            "input_field_placeholder": f"Open a section or ask {self.app_name} a question",
        }

    def _menu_markup(self, section: str) -> dict[str, Any]:
        button = self._menu_button
        normalized = str(section or "overview").strip().lower()

        if normalized == "portfolio":
            rows = [
                [button("Refresh Portfolio", "view:portfolio"),
                 button("Performance", "view:performance")],
                [button("Markets", "view:markets"), button(
                    "Controls", "view:controls")],
                [button("Home", "view:overview"), button("Help", "view:help")],
            ]

        elif normalized == "markets":
            rows = [
                [button("Refresh Intel", "view:markets"),
                 button("Chart Shot", "shot:chart")],
                [button("Portfolio", "view:portfolio"), button(
                    "Performance", "view:performance")],
                [button("Controls", "view:controls"),
                 button("Home", "view:overview")],
            ]

        elif normalized == "performance":
            rows = [
                [button("Refresh Performance", "view:performance"),
                 button("Journal", "rich:journal")],
                [button("Review", "rich:review"), button(
                    "Portfolio", "view:portfolio")],
                [button("Controls", "view:controls"),
                 button("Home", "view:overview")],
            ]

        elif normalized == "workspace":
            rows = [
                [button("Settings", "rich:settings"),
                 button("Health", "rich:health")],
                [button("Quant PM", "rich:quantpm"),
                 button("Logs", "rich:logs")],
                [button("Review", "rich:review"),
                 button("Home", "view:overview")],
            ]

        elif normalized == "controls":
            rows = [
                [button("Refresh Markets", "action:refreshmarkets"),
                 button("Reload Balances", "action:reloadbalances")],
                [button("Refresh Chart", "action:refreshchart"), button(
                    "Refresh Orderbook", "action:refreshorderbook")],
                [button("AI On", "control:prompt:autotradeon"), button(
                    "AI Off", "control:prompt:autotradeoff")],
                [button("Kill Switch", "control:prompt:killswitch"),
                 button("Resume", "control:prompt:resume")],
                [button("Workspace", "view:workspace"),
                 button("Home", "view:overview")],
            ]

        elif normalized == "help":
            rows = [
                [button("Overview", "view:overview"), button(
                    "Portfolio", "view:portfolio")],
                [button("Markets", "view:markets"), button(
                    "Controls", "view:controls")],
                [button("Screenshot", "shot:terminal"), button(
                    "Quick Brief", "action:quickbrief")],
            ]

        else:
            rows = [
                [button("Portfolio", "view:portfolio"),
                 button("Markets", "view:markets")],
                [button("Performance", "view:performance"),
                 button("Workspace", "view:workspace")],
                [button("Controls", "view:controls"), button(
                    "Screenshot", "shot:terminal")],
                [button("Help", "view:help"), button(
                    "Quick Brief", "action:quickbrief")],
            ]

        return {"inline_keyboard": rows}

    @staticmethod
    def _menu_button(text: Any, callback_data: Any) -> dict[str, str]:
        return {
            "text": str(text or "").strip(),
            "callback_data": str(callback_data or "").strip()[:MAX_CALLBACK_DATA_LENGTH],
        }

    def _keyboard_alias_to_command(self, text: Any) -> Optional[str]:
        normalized = " ".join(str(text or "").strip().lower().split())
        if not normalized:
            return None

        return {
            "overview": "/menu",
            "portfolio": "/portfolio",
            "market intel": "/markets",
            "performance": "/performance",
            "workspace": "/workspace",
            "controls": "/controls",
            "journal": "/history",
            "screenshot": "/screenshot",
            "help": "/help",
            "quick brief": "/ask Give me a concise market, account, and risk summary.",
        }.get(normalized)

    # ------------------------------------------------------------------
    # Callback handling
    # ------------------------------------------------------------------

    async def _handle_callback_query(
        self,
        data: str,
        chat_id: str,
        callback_id: str = "",
        message_id: Any = None,
    ) -> None:
        payload = str(data or "").strip()

        if not payload:
            await self._answer_callback_query(callback_id, "Unknown action.")
            return

        if payload.startswith("trade_confirm:") or payload.startswith("trade_cancel:"):
            await self._handle_trade_callback(payload, chat_id, callback_id)
            return

        parts = payload.split(":")
        kind = parts[0]

        if kind == "view" and len(parts) >= 2:
            await self._show_menu_view(parts[1], chat_id, message_id=message_id)
            await self._answer_callback_query(callback_id, "Updated.")
            return

        if kind == "shot" and len(parts) >= 2:
            target = parts[1]

            if target == "terminal":
                await self._send_terminal_screenshot(chat_id=chat_id)
                await self._answer_callback_query(callback_id, "Screenshot requested.")
                return

            if target == "chart":
                await self._send_chart_screenshot(symbol=None, timeframe="", chat_id=chat_id)
                await self._answer_callback_query(callback_id, "Chart shot requested.")
                return

        if kind == "rich" and len(parts) >= 2:
            result = await self._handle_rich_action_button(parts[1], chat_id)

            if result is None:
                await self._answer_callback_query(callback_id, "Action is not available.")
                return

            await self._edit_or_send_message(
                chat_id,
                message_id,
                result,
                reply_markup=self._menu_markup("workspace"),
            )
            await self._answer_callback_query(callback_id, "Workspace updated.")
            return

        if kind == "action" and len(parts) >= 2:
            result = await self._handle_action_button(parts[1], chat_id)
            await self._edit_or_send_message(
                chat_id,
                message_id,
                result,
                reply_markup=self._menu_markup("controls"),
            )
            await self._answer_callback_query(callback_id, "Request sent.")
            return

        if kind == "control" and len(parts) >= 3:
            phase = parts[1]
            token_or_key = parts[2]

            if phase == "prompt":
                await self._show_control_confirmation(token_or_key, chat_id, message_id, callback_id)
                return

            if phase == "confirm":
                await self._confirm_control_action(token_or_key, chat_id, message_id, callback_id)
                return

            if phase == "cancel":
                self._pending_control_actions.pop(token_or_key, None)
                await self._show_menu_view("controls", chat_id, message_id=message_id)
                await self._answer_callback_query(callback_id, "Canceled.")
                return

        await self._answer_callback_query(callback_id, "Unknown action.")

    async def _handle_trade_callback(self, payload: str, chat_id: str, callback_id: str) -> None:
        action, token = payload.split(":", 1)
        pending = self._pending_trade_actions.get(token)

        if not pending or pending.chat_id != str(chat_id or "").strip() or pending.expired(self.pending_ttl_seconds):
            self._pending_trade_actions.pop(token, None)
            await self._answer_callback_query(callback_id, "This trade request is no longer available.")
            return

        if action == "trade_cancel":
            self._pending_trade_actions.pop(token, None)
            await self._answer_callback_query(callback_id, "Trade request canceled.")
            await self.send_message("Trade request canceled.", reply_markup=self._menu_markup("controls"), chat_id=chat_id)
            return

        self._pending_trade_actions.pop(token, None)

        action_text = pending.action_text
        if "confirm" not in action_text.lower():
            action_text = f"{action_text} confirm"

        result = await self._handle_direct_action(action_text, chat_id)
        await self._answer_callback_query(callback_id, "Trade submitted.")
        await self.send_message(result, reply_markup=self._menu_markup("controls"), chat_id=chat_id)

    # ------------------------------------------------------------------
    # Action registration / confirmation
    # ------------------------------------------------------------------

    def _purge_expired_pending_actions(self) -> None:
        expired_trade_tokens = [
            token for token, action in self._pending_trade_actions.items()
            if action.expired(self.pending_ttl_seconds)
        ]

        for token in expired_trade_tokens:
            self._pending_trade_actions.pop(token, None)

        expired_control_tokens = [
            token for token, action in self._pending_control_actions.items()
            if action.expired(self.pending_ttl_seconds)
        ]

        for token in expired_control_tokens:
            self._pending_control_actions.pop(token, None)

    def _register_pending_trade_action(self, chat_id: str, action_text: str) -> str:
        self._purge_expired_pending_actions()
        token = uuid.uuid4().hex[:12]
        self._pending_trade_actions[token] = PendingAction(
            chat_id=str(chat_id or "").strip(),
            action_text=str(action_text or "").strip(),
        )
        return token

    def _register_pending_control_action(self, chat_id: str, action_key: str) -> str:
        self._purge_expired_pending_actions()
        token = uuid.uuid4().hex[:12]
        self._pending_control_actions[token] = PendingAction(
            chat_id=str(chat_id or "").strip(),
            action_key=str(action_key or "").strip(),
        )
        return token

    def _trade_confirmation_markup(self, token: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "Confirm Trade",
                        "callback_data": f"trade_confirm:{token}"},
                    {"text": "Cancel Trade", "callback_data": f"trade_cancel:{token}"},
                ]
            ]
        }

    def _control_confirmation_markup(self, token: str) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "Confirm", "callback_data": f"control:confirm:{token}"},
                    {"text": "Cancel", "callback_data": f"control:cancel:{token}"},
                ]
            ]
        }

    def _control_action_specs(self) -> dict[str, dict[str, str]]:
        return {
            "autotradeon": {
                "label": "Enable AI Trading",
                "action_text": "start ai trading",
                "prompt": "Send a remote request to enable AI trading with the workspace's current broker, scope, and safeguards?",
                "notice": "AI trading enable request sent.",
            },
            "autotradeoff": {
                "label": "Disable AI Trading",
                "action_text": "stop ai trading",
                "prompt": "Send a remote request to stop AI trading?",
                "notice": "AI trading stop request sent.",
            },
            "killswitch": {
                "label": "Activate Kill Switch",
                "action_text": "activate kill switch",
                "prompt": "Trigger the emergency kill switch from Telegram?",
                "notice": "Kill switch request sent.",
            },
            "resume": {
                "label": "Resume Trading",
                "action_text": "resume trading",
                "prompt": "Resume trading after the current stop condition?",
                "notice": "Resume request sent.",
            },
        }

    async def _show_control_confirmation(
        self,
        action_key: str,
        chat_id: str,
        message_id: Any,
        callback_id: str,
    ) -> None:
        spec = self._control_action_specs().get(str(action_key or "").strip().lower())

        if spec is None:
            await self._answer_callback_query(callback_id, "Action is not available.")
            return

        token = self._register_pending_control_action(chat_id, action_key)

        text = (
            "<b>Confirm Remote Control</b>\n"
            f"Action: <b>{html.escape(spec.get('label', ''))}</b>\n"
            f"{html.escape(spec.get('prompt', ''))}\n\n"
            "Use Confirm to send the request to the workspace."
        )

        await self._edit_or_send_message(
            chat_id,
            message_id,
            text,
            reply_markup=self._control_confirmation_markup(token),
        )

        await self._answer_callback_query(callback_id, "Confirm or cancel.")

    async def _confirm_control_action(
        self,
        token: str,
        chat_id: str,
        message_id: Any,
        callback_id: str,
    ) -> None:
        pending = self._pending_control_actions.get(token)

        if not pending or pending.chat_id != str(chat_id or "").strip() or pending.expired(self.pending_ttl_seconds):
            self._pending_control_actions.pop(token, None)
            await self._answer_callback_query(callback_id, "This control request is no longer available.")
            return

        self._pending_control_actions.pop(token, None)
        action_key = pending.action_key
        spec = self._control_action_specs().get(action_key)

        if spec is None:
            await self._answer_callback_query(callback_id, "Action is not available.")
            return

        result = await self._handle_direct_action(spec.get("action_text", ""), chat_id)

        await self._edit_or_send_message(
            chat_id,
            message_id,
            result,
            reply_markup=self._menu_markup("controls"),
        )

        await self._answer_callback_query(callback_id, str(spec.get("notice") or "Request sent."))

    # ------------------------------------------------------------------
    # Controller calls
    # ------------------------------------------------------------------

    async def _call_controller_method(self, method_name: str, *args: Any, **kwargs: Any) -> Any:
        method = getattr(self.controller, str(method_name or "").strip(), None)

        if not callable(method):
            return None

        try:
            result = method(*args, **kwargs)
        except TypeError:
            try:
                result = method(*args)
            except TypeError:
                result = method()

        return await self._maybe_await(result)

    async def _controller_text(self, method_name: str, default: str = "Information is not available right now.", **kwargs: Any) -> str:
        result = await self._call_controller_method(method_name, **kwargs)

        if result is None:
            return default

        if isinstance(result, dict):
            message = result.get("message")
            if message not in (None, ""):
                return str(message)
            return json.dumps(result, indent=2, default=str)

        return str(result)

    async def _call_controller_text_method(self, method_name: str, **kwargs: Any) -> Optional[str]:
        result = await self._call_controller_method(method_name, **kwargs)

        if result is None:
            return None

        if isinstance(result, dict):
            message = result.get("message")
            if message not in (None, ""):
                return str(message)
            return json.dumps(result, indent=2, default=str)

        return str(result)

    async def _handle_direct_action(self, action_text: Any, chat_id: str) -> str:
        handler = getattr(self.controller, "handle_market_chat_action", None)

        if callable(handler):
            try:
                result = handler(str(action_text or ""))
                result = await self._maybe_await(result)
            except TypeError:
                result = None

            if result:
                return str(result)

        return await self._ask_controller(str(action_text or ""), chat_id)

    async def _ask_controller(self, question: Any, chat_id: str) -> str:
        question_text = str(question or "").strip()

        if not question_text:
            return "Please send a question."

        history = list(self._chat_histories.get(chat_id, []) or [])

        ask_method = getattr(self.controller, "ask_openai_about_app", None)

        if not callable(ask_method):
            return "Assistant is not available from the controller right now."

        try:
            try:
                answer = ask_method(question_text, conversation=history)
            except TypeError:
                answer = ask_method(question_text)

            answer = await self._maybe_await(answer)

        except Exception as exc:
            self.logger.debug("Controller ask failed: %s", exc)
            return "I could not get an answer from the assistant right now."

        answer_text = str(answer or "").strip() or "No response returned."

        updated_history = history + [
            {"role": "user", "content": question_text},
            {"role": "assistant", "content": answer_text},
        ]

        self._chat_histories[chat_id] = updated_history[-self.history_messages:]

        return answer_text

    # ------------------------------------------------------------------
    # Rich actions / direct actions
    # ------------------------------------------------------------------

    def _slash_action_commands(self) -> dict[str, str]:
        return {
            "/settings": "open settings",
            "/health": "open system health",
            "/quantpm": "open quant pm",
            "/journal": "open closed journal",
            "/review": "open journal review",
            "/logs": "open logs",
            "/refreshmarkets": "refresh markets",
            "/reloadbalances": "reload balances",
            "/refreshchart": "refresh chart",
            "/refreshorderbook": "refresh orderbook",
            "/autotradeon": "start ai trading",
            "/autotradeoff": "stop ai trading",
            "/killswitch": "activate kill switch",
            "/resume": "resume trading",
        }

    async def _handle_rich_action_command(self, command: str, chat_id: str) -> Optional[str]:
        command_map: dict[str, tuple[str, dict[str, Any], str]] = {
            "/settings": ("telegram_settings_text", {"open_window": True}, "open settings"),
            "/health": ("telegram_health_text", {"open_window": True}, "open system health"),
            "/quantpm": ("telegram_quant_pm_text", {"open_window": True}, "open quant pm"),
            "/journal": ("telegram_journal_text", {"open_window": True}, "open closed journal"),
            "/review": ("telegram_journal_review_text", {"open_window": True}, "open journal review"),
            "/logs": ("telegram_logs_text", {"open_window": True}, "open logs"),
        }

        config = command_map.get(str(command or "").strip().lower())

        if config is None:
            return None

        method_name, kwargs, fallback_action = config
        result = await self._call_controller_text_method(method_name, **kwargs)

        if result:
            return result

        return await self._handle_direct_action(fallback_action, chat_id)

    async def _handle_rich_action_button(self, key: str, chat_id: str) -> Optional[str]:
        normalized = str(key or "").strip().lower()
        command = f"/{normalized}" if normalized else ""

        if not command:
            return None

        result = await self._handle_rich_action_command(command, chat_id)

        if result:
            return result

        action_text = self._slash_action_commands().get(command)

        if action_text:
            return await self._handle_direct_action(action_text, chat_id)

        return None

    async def _handle_action_button(self, key: str, chat_id: str) -> str:
        normalized = str(key or "").strip().lower()

        if normalized == "quickbrief":
            return await self._ask_controller(
                "Give me a concise market, account, and risk summary.",
                chat_id,
            )

        action_text = self._slash_action_commands().get(f"/{normalized}")

        if action_text:
            return await self._handle_direct_action(action_text, chat_id)

        return "Action is not available right now."

    # ------------------------------------------------------------------
    # Screenshots / charts
    # ------------------------------------------------------------------

    async def _send_terminal_screenshot(self, *, chat_id: Optional[str] = None) -> None:
        screenshot_path = await self._call_controller_method("capture_telegram_screenshot")

        if screenshot_path:
            sent = await self.send_photo(
                str(screenshot_path),
                caption=f"{html.escape(self.app_name)} terminal screenshot",
                chat_id=chat_id,
            )

            if not sent:
                await self.send_message(
                    f"Screenshot captured but could not be uploaded: <code>{html.escape(str(screenshot_path))}</code>",
                    reply_markup=self._menu_markup("overview"),
                    chat_id=chat_id,
                )
            return

        await self.send_message(
            "Unable to capture a screenshot right now.",
            reply_markup=self._menu_markup("overview"),
            chat_id=chat_id,
        )

    async def _send_chart_screenshot(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        *,
        chat_id: Optional[str] = None,
    ) -> None:
        screenshot_path = await self._call_controller_method(
            "capture_chart_screenshot",
            str(symbol or "").strip().upper() or None,
            timeframe,
            prefix="telegram_chart",
        )

        if screenshot_path:
            symbol_text = str(symbol or "").strip().upper() or "current chart"
            timeframe_text = str(
                timeframe or getattr(
                    self.controller, "time_frame", "1h") or "1h"
            ).strip() or "1h"

            caption = f"{html.escape(self.app_name)} chart {html.escape(symbol_text)} ({html.escape(timeframe_text)})"
            sent = await self.send_photo(str(screenshot_path), caption=caption, chat_id=chat_id)

            if not sent:
                await self.send_message(
                    f"Chart captured but could not be uploaded: <code>{html.escape(str(screenshot_path))}</code>",
                    reply_markup=self._menu_markup("markets"),
                    chat_id=chat_id,
                )
            return

        await self.send_message(
            "Unable to open or capture that chart right now.",
            reply_markup=self._menu_markup("markets"),
            chat_id=chat_id,
        )

    # ------------------------------------------------------------------
    # Menu views
    # ------------------------------------------------------------------

    async def _send_section_text(self, text: Any, section: str, chat_id: Optional[str] = None) -> None:
        await self.send_message(str(text or ""), reply_markup=self._menu_markup(section), chat_id=chat_id)

    async def _edit_or_send_message(
        self,
        chat_id: str,
        message_id: Any,
        text: Any,
        reply_markup: Optional[dict[str, Any]] = None,
        include_keyboard: bool = False,
    ) -> bool:
        if message_id not in (None, ""):
            edited = await self._edit_message(chat_id, message_id, text, reply_markup=reply_markup)
            if edited:
                return True

        return await self.send_message(
            text,
            include_keyboard=include_keyboard,
            reply_markup=reply_markup,
            chat_id=chat_id,
        )

    async def _show_menu_view(self, section: str, chat_id: str, message_id: Any = None) -> bool:
        text = await self._menu_text(section)

        return await self._edit_or_send_message(
            chat_id,
            message_id,
            text,
            reply_markup=self._menu_markup(section),
        )

    async def _menu_text(self, section: str) -> str:
        normalized = str(section or "overview").strip().lower()

        if normalized == "portfolio":
            return self._join_blocks(
                "<b>Portfolio Console</b>\nReview balances, live exposure, and working orders from Telegram.",
                await self._controller_text("telegram_balances_text"),
                await self._controller_text("telegram_positions_text"),
                await self._controller_text("telegram_open_orders_text"),
            )

        if normalized == "markets":
            return self._join_blocks(
                "<b>Market Intel</b>\nFollow active trade ideas, position analysis, and chart capture shortcuts.",
                await self._controller_text("telegram_recommendations_text"),
                await self._controller_text("telegram_position_analysis_text", open_window=False),
            )

        if normalized == "performance":
            return self._join_blocks(
                "<b>Performance Console</b>\nTrack outcomes before changing risk or enabling automation.",
                await self._controller_text("telegram_performance_text"),
                await self._history_summary(limit=120, open_window=False),
            )

        if normalized == "workspace":
            return self._join_blocks(
                "<b>Workspace Console</b>\nJump into settings, health, research, and review surfaces without leaving Telegram.",
                await self._controller_text("telegram_management_text", default="Management summary is not available."),
                await self._controller_text("telegram_settings_text", open_window=False),
                await self._controller_text("telegram_health_text", open_window=False),
            )

        if normalized == "controls":
            return self._join_blocks(
                "<b>Remote Controls</b>\nUse refresh actions freely. State-changing trading controls stay confirmation-gated.",
                await self._controller_text("telegram_management_text", default="Management summary is not available."),
            )

        if normalized == "help":
            return self._join_blocks(
                self._help_text(),
                "Tip: the keyboard buttons are aliases, so you can tap sections or type a natural-language question at any time.",
            )

        return self._join_blocks(
            f"<b>{html.escape(self.app_name)} Remote Console</b>\nUse the inline panels below to navigate the live workspace.",
            await self._controller_text("telegram_status_text"),
            f"Tip: ask a plain-English question at any time and {html.escape(self.app_name)} will answer with current app context.",
        )

    async def _history_summary(self, limit: int = 300, open_window: bool = True) -> str:
        summary_builder = getattr(
            self.controller, "market_chat_trade_history_summary", None)

        if not callable(summary_builder):
            return "Trade history summary is not available right now."

        try:
            result = summary_builder(limit=limit, open_window=open_window)
        except TypeError:
            result = summary_builder(limit=limit)

        result = await self._maybe_await(result)

        return str(result or "Trade history summary is not available right now.")

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_chart_args(self, text: Any) -> dict[str, str]:
        raw = str(text or "").strip()

        if not raw:
            return {"symbol": "", "timeframe": ""}

        parts = [part for part in re.split(r"\s+", raw) if part]

        if not parts:
            return {"symbol": "", "timeframe": ""}

        symbol = parts[0].upper()
        timeframe = parts[1] if len(parts) > 1 else ""

        return {"symbol": symbol, "timeframe": timeframe}

    def _build_trade_action_text(self, command: str, args_text: str) -> str:
        raw_args = str(args_text or "").strip()
        normalized_command = str(command or "").strip().lower()

        if normalized_command == "/trade":
            if not raw_args:
                return ""
            return raw_args if raw_args.lower().startswith("trade ") else f"trade {raw_args}"

        if not raw_args:
            return ""

        side = "buy" if normalized_command == "/buy" else "sell"
        return f"trade {side} {raw_args}"

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def _localize_text(self, text: Any, rich: Optional[bool] = None) -> str:
        raw = str(text or "")

        translator = getattr(self.controller, "translate_runtime_text", None)

        if not callable(translator) or not raw:
            return raw

        use_rich = bool(rich) if rich is not None else (
            "<" in raw and ">" in raw)

        try:
            localized = translator(raw, rich=use_rich)
        except TypeError:
            localized = translator(raw)
        except Exception as exc:
            self.logger.debug("Runtime text translation failed: %s", exc)
            return raw

        return str(localized or raw)

    @staticmethod
    def _join_blocks(*blocks: Any) -> str:
        parts = [str(block).strip()
                 for block in blocks if str(block or "").strip()]
        return "\n\n".join(parts)

    def _split_message_chunks(self, text: Any, max_length: int = SAFE_CHUNK_LENGTH) -> list[str]:
        raw = str(text or "")

        if not raw:
            return [""]

        max_length = min(max(500, int(max_length)),
                         MAX_TELEGRAM_TEXT_LENGTH - 100)

        if len(raw) <= max_length:
            return [raw]

        chunks: list[str] = []
        remaining = raw

        while remaining:
            if len(remaining) <= max_length:
                chunks.append(remaining)
                break

            split_at = remaining.rfind("\n", 0, max_length)

            if split_at < max_length // 3:
                split_at = remaining.rfind(" ", 0, max_length)

            if split_at < max_length // 3:
                split_at = max_length

            chunk = remaining[:split_at].rstrip()
            chunks.append(chunk)
            remaining = remaining[split_at:].lstrip()

        return chunks
