import asyncio
import html
import json
import os
from datetime import datetime, timezone
import re
import uuid

import aiohttp

from integrations.trade_notifications import (
    build_trade_close_summary,
    format_trade_close_html,
    trade_notification_reason,
)


class TelegramService:
    def __init__(self, controller, logger, bot_token, chat_id=None, enabled=False):
        self.controller = controller
        self.logger = logger
        self.bot_token = str(bot_token or "").strip()
        self.chat_id = str(chat_id or "").strip()
        self.enabled = bool(enabled and self.bot_token)
        self._offset = 0
        self._poll_task = None
        self._session = None
        self._running = False
        self._chat_histories = {}
        self._pending_trade_actions = {}
        self._pending_control_actions = {}

    @property
    def base_url(self):
        return f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self):
        return bool(self.bot_token)

    def can_send(self):
        return bool(self.bot_token and self.chat_id)

    @staticmethod
    def _trade_notification_reason(trade):
        return trade_notification_reason(trade)

    async def start(self):
        if not self.enabled or not self.bot_token:
            return
        if self._poll_task and not self._poll_task.done():
            return
        self._running = True
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))
        self._poll_task = asyncio.create_task(self._poll_loop(), name="telegram_poll")
        if self.can_send():
            await self.send_message(self._welcome_text(), include_keyboard=True)

    async def stop(self):
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

    async def notify_trade(self, trade):
        if not self.can_send() or not isinstance(trade, dict):
            return

        symbol = str(trade.get("symbol") or "-")
        side = str(trade.get("side") or "-").upper()
        status = str(trade.get("status") or "-").upper()
        reason = self._trade_notification_reason(trade)
        price = trade.get("price", "-")
        raw_size = trade.get("size", trade.get("amount", "-"))
        display_size = trade.get("applied_requested_mode_amount")
        display_mode = str(trade.get("requested_quantity_mode") or "").strip().lower()
        if display_size not in (None, "") and display_mode:
            size = f"{display_size} {display_mode}"
            if display_mode != "units" and raw_size not in (None, ""):
                size = f"{size} ({raw_size} units)"
        else:
            size = raw_size
        pnl = trade.get("pnl", "-")
        order_id = trade.get("order_id", trade.get("id", "-"))
        timestamp = trade.get("timestamp") or datetime.now(timezone.utc).isoformat()
        reason_line = f"Reason: <code>{html.escape(reason)}</code>\n" if reason else ""
        message = (
            "<b>Trading Activity</b>\n"
            f"Symbol: <code>{symbol}</code>\n"
            f"Side: <b>{side}</b>\n"
            f"Status: <b>{status}</b>\n"
            f"Price: <code>{price}</code>\n"
            f"Size: <code>{size}</code>\n"
            f"PnL: <code>{pnl}</code>\n"
            f"{reason_line}"
            f"Order ID: <code>{order_id}</code>\n"
            f"Time: <code>{timestamp}</code>"
        )
        await self.send_message(message, reply_markup=self._menu_markup("portfolio"))

    async def notify_trade_close(self, trade):
        if not self.can_send() or not isinstance(trade, dict):
            return
        summary = build_trade_close_summary(trade)
        message = format_trade_close_html(summary)
        await self.send_message(message, reply_markup=self._menu_markup("portfolio"))

    async def send_message(self, text, include_keyboard=False, reply_markup=None):
        if not self.can_send():
            return False
        try:
            await self._ensure_session()
            localized_text = self._localize_text(text)
            chunks = self._split_message_chunks(localized_text)
            sent_any = False
            for index, chunk in enumerate(chunks):
                payload = {
                    "chat_id": self.chat_id,
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
                async with self._session.post(
                    f"{self.base_url}/sendMessage",
                    data=payload,
                ) as response:
                    result = await response.json(content_type=None)
                    if not result.get("ok"):
                        return False
                    sent_any = True
            return sent_any
        except Exception as exc:
            self.logger.debug("Telegram send_message failed: %s", exc)
            return False

    async def send_photo(self, file_path, caption=None):
        if not self.can_send() or not file_path or not os.path.exists(file_path):
            return False
        try:
            await self._ensure_session()
            data = aiohttp.FormData()
            data.add_field("chat_id", self.chat_id)
            if caption:
                data.add_field("caption", self._localize_text(caption))
            with open(file_path, "rb") as handle:
                data.add_field(
                    "photo",
                    handle,
                    filename=os.path.basename(file_path),
                    content_type="image/png",
                )
                async with self._session.post(f"{self.base_url}/sendPhoto", data=data) as response:
                    payload = await response.json(content_type=None)
                    return bool(payload.get("ok"))
        except Exception as exc:
            self.logger.debug("Telegram send_photo failed: %s", exc)
            return False

    async def _edit_message(self, chat_id, message_id, text, reply_markup=None):
        if not self.can_send() or not message_id:
            return False
        target_chat_id = str(chat_id or self.chat_id or "").strip()
        if not target_chat_id:
            return False
        localized_text = self._localize_text(text)
        chunks = self._split_message_chunks(localized_text)
        if len(chunks) != 1:
            return False
        try:
            await self._ensure_session()
            payload = {
                "chat_id": target_chat_id,
                "message_id": int(message_id),
                "text": chunks[0],
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
            if reply_markup is not None:
                payload["reply_markup"] = json.dumps(reply_markup)
            async with self._session.post(
                f"{self.base_url}/editMessageText",
                data=payload,
            ) as response:
                result = await response.json(content_type=None)
                if result.get("ok"):
                    return True
                description = str(result.get("description") or "").lower()
                return "message is not modified" in description
        except Exception as exc:
            self.logger.debug("Telegram editMessageText failed: %s", exc)
            return False

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45))

    def _localize_text(self, text, rich=None):
        raw = str(text or "")
        translator = getattr(self.controller, "translate_runtime_text", None)
        if not callable(translator) or not raw:
            return raw
        use_rich = bool(rich) if rich is not None else ("<" in raw and ">" in raw)
        try:
            localized = translator(raw, rich=use_rich)
        except TypeError:
            localized = translator(raw)
        return str(localized or raw)

    async def _poll_loop(self):
        while self._running:
            try:
                updates = await self._get_updates()
                for update in updates:
                    await self._handle_update(update)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.debug("Telegram polling error: %s", exc)
                await asyncio.sleep(3)

    async def _get_updates(self):
        await self._ensure_session()
        params = {"timeout": 30, "offset": self._offset + 1}
        async with self._session.get(f"{self.base_url}/getUpdates", params=params) as response:
            payload = await response.json(content_type=None)
        if not payload.get("ok"):
            return []
        return payload.get("result", []) or []

    async def _handle_update(self, update):
        update_id = int(update.get("update_id", self._offset) or self._offset)
        self._offset = max(self._offset, update_id)
        callback_query = update.get("callback_query") or {}
        callback_data = str(callback_query.get("data") or "").strip()
        callback_message = callback_query.get("message", {}) or {}
        callback_chat = callback_message.get("chat", {}) or {}
        callback_chat_id = str(callback_chat.get("id") or "").strip()
        callback_id = str(callback_query.get("id") or "").strip()
        callback_message_id = callback_message.get("message_id")
        if callback_data and callback_chat_id:
            if self.chat_id and callback_chat_id != self.chat_id:
                return
            await self._handle_callback_query(
                callback_data,
                callback_chat_id,
                callback_id=callback_id,
                message_id=callback_message_id,
            )
            return

        message = update.get("message") or update.get("edited_message") or {}
        text = str(message.get("text") or "").strip()
        chat = message.get("chat") or {}
        incoming_chat_id = str(chat.get("id") or "").strip()
        if not text or not incoming_chat_id:
            return
        if self.chat_id and incoming_chat_id != self.chat_id:
            return

        normalized_command = self._keyboard_alias_to_command(text)
        if normalized_command is not None:
            text = normalized_command

        command_text = text.split(None, 1)
        command_token = str(command_text[0] or "").strip().lower()
        command = command_token.split("@", 1)[0]
        args_text = command_text[1].strip() if len(command_text) > 1 else ""

        if command == "/start":
            await self.send_message(self._welcome_text(), include_keyboard=True)
            await self._show_menu_view("overview", incoming_chat_id)
            return
        if command in {"/help", "/commands"}:
            await self.send_message(self._help_text(), include_keyboard=True)
            return
        if command in {"/menu", "/home"}:
            await self._show_menu_view("overview", incoming_chat_id)
            return
        if command == "/portfolio":
            await self._show_menu_view("portfolio", incoming_chat_id)
            return
        if command in {"/markets", "/marketintel"}:
            await self._show_menu_view("markets", incoming_chat_id)
            return
        if command == "/workspace":
            await self._show_menu_view("workspace", incoming_chat_id)
            return
        if command == "/controls":
            await self._show_menu_view("controls", incoming_chat_id)
            return
        if command == "/status":
            await self._send_section_text(await self.controller.telegram_status_text(), section="overview")
            return
        if command == "/management":
            await self._send_section_text(
                str(getattr(self.controller, "telegram_management_text", lambda: "Management summary is not available.")()),
                section="workspace",
            )
            return
        if command == "/balances":
            await self._send_section_text(await self.controller.telegram_balances_text(), section="portfolio")
            return
        if command == "/positions":
            await self._send_section_text(await self.controller.telegram_positions_text(), section="portfolio")
            return
        if command in {"/orders", "/openorders"}:
            await self._send_section_text(await self.controller.telegram_open_orders_text(), section="portfolio")
            return
        if command == "/recommendations":
            await self._send_section_text(await self.controller.telegram_recommendations_text(), section="markets")
            return
        if command == "/performance":
            await self._send_section_text(await self.controller.telegram_performance_text(), section="performance")
            return
        if command in {"/history", "/journalsummary"}:
            await self._send_section_text(
                await self._history_summary(limit=300, open_window=True),
                section="performance",
            )
            return
        if command in {"/analysis", "/positionanalysis"}:
            await self._send_section_text(
                await self.controller.telegram_position_analysis_text(open_window=True),
                section="markets",
            )
            return
        if command == "/screenshot":
            await self._send_terminal_screenshot()
            return
        if command == "/chart":
            parsed = self._parse_chart_args(args_text)
            if not parsed.get("symbol"):
                await self.send_message(
                    "Usage: /chart SYMBOL [TIMEFRAME]. Example: <code>/chart EUR/USD 1h</code>",
                    reply_markup=self._menu_markup("markets"),
                )
                return
            result = await self.controller.telegram_open_chart(parsed["symbol"], parsed.get("timeframe"))
            await self._send_section_text(result.get("message") or "Chart request processed.", section="markets")
            return
        if command in {"/chartshot", "/chartphoto", "/sendchart"}:
            parsed = self._parse_chart_args(args_text)
            await self._send_chart_screenshot(parsed.get("symbol"), parsed.get("timeframe"))
            return
        rich_action_answer = await self._handle_rich_action_command(command, incoming_chat_id)
        if rich_action_answer is not None:
            await self._send_section_text(rich_action_answer, section="workspace")
            return
        action_commands = self._slash_action_commands()
        action_text = action_commands.get(command)
        if action_text:
            answer = await self._handle_direct_action(action_text, incoming_chat_id)
            await self._send_section_text(answer, section="controls")
            return
        if command in {"/ask", "/chat"}:
            question = args_text
            if not question:
                await self.send_message(
                    "Send a question after /ask or /chat.",
                    reply_markup=self._menu_markup("help"),
                )
                return
            answer = await self._ask_controller(question, incoming_chat_id)
            await self._send_section_text(answer, section="overview")
            return
        if command in {"/trade", "/buy", "/sell"}:
            action_text = self._build_trade_action_text(command, args_text)
            if not action_text:
                await self.send_message(
                    "Usage: <code>/trade buy EUR/USD amount 1000 confirm</code> or "
                    "<code>/buy EUR/USD amount 0.01 type market confirm</code>",
                    reply_markup=self._menu_markup("controls"),
                )
                return
            if "confirm" in action_text.lower():
                answer = await self._handle_direct_action(action_text, incoming_chat_id)
                await self._send_section_text(answer, section="controls")
                return
            preview = await self._handle_direct_action(action_text, incoming_chat_id)
            token = self._register_pending_trade_action(incoming_chat_id, action_text)
            await self.send_message(
                preview,
                reply_markup=self._trade_confirmation_markup(token),
            )
            return

        if command.startswith("/"):
            await self.send_message(self._help_text(), include_keyboard=True)
            return

        answer = await self._ask_controller(text, incoming_chat_id)
        await self._send_section_text(answer, section="overview")

    def _welcome_text(self):
        return (
            "<b>Sopotek Pilot Remote Console</b>\n"
            "Telegram is connected to the desktop workspace.\n"
            "Use the persistent keyboard for quick sections, or open <code>/menu</code> for the live control panel."
        )

    def _help_text(self):
        return (
            "<b>Sopotek Telegram Console</b>\n"
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
            "/chartshot - capture the current chart and send it here\n"
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
            "/killswitch - activate the emergency kill switch\n"
            "/resume - resume trading after a stop\n"
            "/ask &lt;question&gt; - ask Sopotek Pilot about the app or current market context\n"
            "/help - show this message\n\n"
            "Setup tips:\n"
            "Telegram: talk to BotFather, send <code>/newbot</code>, copy the bot token, message your bot once, then open "
            "<code>https://api.telegram.org/bot&lt;token&gt;/getUpdates</code> and copy <code>chat.id</code> into Settings -> Integrations.\n"
            "OpenAI: create a key at <code>platform.openai.com/api-keys</code>, copy it once, then paste it into Settings -> Integrations -> OpenAI API key and use Test OpenAI.\n"
            "Keep both secrets private."
        )

    def _command_keyboard_markup(self):
        return {
            "keyboard": [
                [{"text": "Overview"}, {"text": "Portfolio"}, {"text": "Market Intel"}],
                [{"text": "Performance"}, {"text": "Workspace"}, {"text": "Controls"}],
                [{"text": "Journal"}, {"text": "Screenshot"}, {"text": "Help"}],
                [{"text": "Quick Brief"}],
            ],
            "resize_keyboard": True,
            "is_persistent": True,
            "one_time_keyboard": False,
            "input_field_placeholder": "Open a section or ask Sopotek Pilot a question",
        }

    def _menu_markup(self, section):
        button = self._menu_button
        normalized = str(section or "overview").strip().lower()
        if normalized == "portfolio":
            rows = [
                [button("Refresh Portfolio", "view:portfolio"), button("Performance", "view:performance")],
                [button("Markets", "view:markets"), button("Controls", "view:controls")],
                [button("Home", "view:overview"), button("Help", "view:help")],
            ]
        elif normalized == "markets":
            rows = [
                [button("Refresh Intel", "view:markets"), button("Chart Shot", "shot:chart")],
                [button("Portfolio", "view:portfolio"), button("Performance", "view:performance")],
                [button("Controls", "view:controls"), button("Home", "view:overview")],
            ]
        elif normalized == "performance":
            rows = [
                [button("Refresh Performance", "view:performance"), button("Journal", "rich:journal")],
                [button("Review", "rich:review"), button("Portfolio", "view:portfolio")],
                [button("Controls", "view:controls"), button("Home", "view:overview")],
            ]
        elif normalized == "workspace":
            rows = [
                [button("Settings", "rich:settings"), button("Health", "rich:health")],
                [button("Quant PM", "rich:quantpm"), button("Logs", "rich:logs")],
                [button("Review", "rich:review"), button("Home", "view:overview")],
            ]
        elif normalized == "controls":
            rows = [
                [button("Refresh Markets", "action:refreshmarkets"), button("Reload Balances", "action:reloadbalances")],
                [button("Refresh Chart", "action:refreshchart"), button("Refresh Orderbook", "action:refreshorderbook")],
                [button("AI On", "control:prompt:autotradeon"), button("AI Off", "control:prompt:autotradeoff")],
                [button("Kill Switch", "control:prompt:killswitch"), button("Resume", "control:prompt:resume")],
                [button("Workspace", "view:workspace"), button("Home", "view:overview")],
            ]
        elif normalized == "help":
            rows = [
                [button("Overview", "view:overview"), button("Portfolio", "view:portfolio")],
                [button("Markets", "view:markets"), button("Controls", "view:controls")],
                [button("Screenshot", "shot:terminal"), button("Quick Brief", "action:quickbrief")],
            ]
        else:
            rows = [
                [button("Portfolio", "view:portfolio"), button("Markets", "view:markets")],
                [button("Performance", "view:performance"), button("Workspace", "view:workspace")],
                [button("Controls", "view:controls"), button("Screenshot", "shot:terminal")],
                [button("Help", "view:help"), button("Quick Brief", "action:quickbrief")],
            ]
        return {"inline_keyboard": rows}

    @staticmethod
    def _menu_button(text, callback_data):
        return {"text": str(text or "").strip(), "callback_data": str(callback_data or "").strip()[:64]}

    def _keyboard_alias_to_command(self, text):
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

    def _slash_action_commands(self):
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

    def _control_action_specs(self):
        return {
            "autotradeon": {
                "label": "Enable AI Trading",
                "action_text": "start ai trading",
                "prompt": "Send a remote request to enable AI trading with the desktop workspace's current broker, scope, and safeguards?",
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

    def _trade_confirmation_markup(self, token):
        return {
            "inline_keyboard": [
                [
                    {"text": "Confirm Trade", "callback_data": f"trade_confirm:{token}"},
                    {"text": "Cancel Trade", "callback_data": f"trade_cancel:{token}"},
                ]
            ]
        }

    def _control_confirmation_markup(self, token):
        return {
            "inline_keyboard": [
                [
                    {"text": "Confirm", "callback_data": f"control:confirm:{token}"},
                    {"text": "Cancel", "callback_data": f"control:cancel:{token}"},
                ]
            ]
        }

    def _parse_chart_args(self, text):
        raw = str(text or "").strip()
        if not raw:
            return {"symbol": "", "timeframe": ""}
        parts = [part for part in re.split(r"\s+", raw) if part]
        if not parts:
            return {"symbol": "", "timeframe": ""}
        symbol = parts[0].upper()
        timeframe = parts[1] if len(parts) > 1 else ""
        return {"symbol": symbol, "timeframe": timeframe}

    def _build_trade_action_text(self, command, args_text):
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

    def _register_pending_trade_action(self, chat_id, action_text):
        token = uuid.uuid4().hex[:12]
        self._pending_trade_actions[token] = {
            "chat_id": str(chat_id or "").strip(),
            "action_text": str(action_text or "").strip(),
        }
        return token

    def _register_pending_control_action(self, chat_id, action_key):
        token = uuid.uuid4().hex[:12]
        self._pending_control_actions[token] = {
            "chat_id": str(chat_id or "").strip(),
            "action_key": str(action_key or "").strip(),
        }
        return token

    async def _handle_callback_query(self, data, chat_id, callback_id="", message_id=None):
        payload = str(data or "").strip()
        if not payload:
            await self._answer_callback_query(callback_id, "Unknown action.")
            return

        if payload.startswith("trade_confirm:") or payload.startswith("trade_cancel:"):
            action, token = payload.split(":", 1)
            pending = self._pending_trade_actions.get(token)
            if not pending or pending.get("chat_id") != str(chat_id or "").strip():
                await self._answer_callback_query(callback_id, "This trade request is no longer available.")
                return

            if action == "trade_cancel":
                self._pending_trade_actions.pop(token, None)
                await self._answer_callback_query(callback_id, "Trade request canceled.")
                await self.send_message("Trade request canceled.", reply_markup=self._menu_markup("controls"))
                return

            self._pending_trade_actions.pop(token, None)
            action_text = str(pending.get("action_text") or "").strip()
            if "confirm" not in action_text.lower():
                action_text = f"{action_text} confirm"
            result = await self._handle_direct_action(action_text, chat_id)
            await self._answer_callback_query(callback_id, "Trade submitted.")
            await self.send_message(result, reply_markup=self._menu_markup("controls"))
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
                await self._send_terminal_screenshot()
                await self._answer_callback_query(callback_id, "Screenshot requested.")
                return
            if target == "chart":
                await self._send_chart_screenshot(symbol=None, timeframe="")
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

    async def _answer_callback_query(self, callback_id, text=""):
        if not callback_id:
            return False
        try:
            await self._ensure_session()
            async with self._session.post(
                f"{self.base_url}/answerCallbackQuery",
                data={"callback_query_id": callback_id, "text": str(text or "")[:200]},
            ) as response:
                payload = await response.json(content_type=None)
                return bool(payload.get("ok"))
        except Exception as exc:
            self.logger.debug("Telegram answerCallbackQuery failed: %s", exc)
            return False

    async def _handle_direct_action(self, action_text, chat_id):
        handler = getattr(self.controller, "handle_market_chat_action", None)
        if callable(handler):
            try:
                result = await handler(action_text)
            except TypeError:
                result = None
            if result:
                return str(result)
        return await self._ask_controller(action_text, chat_id)

    async def _handle_rich_action_command(self, command, chat_id):
        command_map = {
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

    async def _handle_rich_action_button(self, key, chat_id):
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

    async def _handle_action_button(self, key, chat_id):
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

    async def _show_control_confirmation(self, action_key, chat_id, message_id, callback_id):
        spec = self._control_action_specs().get(str(action_key or "").strip().lower())
        if spec is None:
            await self._answer_callback_query(callback_id, "Action is not available.")
            return
        token = self._register_pending_control_action(chat_id, action_key)
        text = (
            "<b>Confirm Remote Control</b>\n"
            f"Action: <b>{spec.get('label')}</b>\n"
            f"{spec.get('prompt')}\n\n"
            "Use Confirm to send the request to the desktop workspace."
        )
        await self._edit_or_send_message(
            chat_id,
            message_id,
            text,
            reply_markup=self._control_confirmation_markup(token),
        )
        await self._answer_callback_query(callback_id, "Confirm or cancel.")

    async def _confirm_control_action(self, token, chat_id, message_id, callback_id):
        pending = self._pending_control_actions.get(token)
        if not pending or pending.get("chat_id") != str(chat_id or "").strip():
            await self._answer_callback_query(callback_id, "This control request is no longer available.")
            return
        self._pending_control_actions.pop(token, None)
        action_key = str(pending.get("action_key") or "").strip().lower()
        spec = self._control_action_specs().get(action_key)
        if spec is None:
            await self._answer_callback_query(callback_id, "Action is not available.")
            return
        result = await self._handle_direct_action(spec.get("action_text"), chat_id)
        await self._edit_or_send_message(
            chat_id,
            message_id,
            result,
            reply_markup=self._menu_markup("controls"),
        )
        await self._answer_callback_query(callback_id, str(spec.get("notice") or "Request sent."))

    async def _call_controller_text_method(self, method_name, **kwargs):
        method = getattr(self.controller, str(method_name or "").strip(), None)
        if not callable(method):
            return None
        try:
            result = method(**kwargs)
        except TypeError:
            result = method()
        if asyncio.iscoroutine(result):
            result = await result
        if result is None:
            return None
        if isinstance(result, dict):
            message = result.get("message")
            if message not in (None, ""):
                return str(message)
        return str(result)

    async def _ask_controller(self, question, chat_id):
        history = list(self._chat_histories.get(chat_id, []) or [])
        try:
            answer = await self.controller.ask_openai_about_app(question, conversation=history)
        except TypeError:
            answer = await self.controller.ask_openai_about_app(question)
        answer_text = str(answer or "").strip() or "No response returned."
        updated_history = history + [
            {"role": "user", "content": str(question or "").strip()},
            {"role": "assistant", "content": answer_text},
        ]
        self._chat_histories[chat_id] = updated_history[-12:]
        return answer_text

    async def _send_terminal_screenshot(self):
        screenshot_path = await self.controller.capture_telegram_screenshot()
        if screenshot_path:
            sent = await self.send_photo(screenshot_path, caption="Sopotek terminal screenshot")
            if not sent:
                await self.send_message(
                    f"Screenshot captured but could not be uploaded: <code>{screenshot_path}</code>",
                    reply_markup=self._menu_markup("overview"),
                )
        else:
            await self.send_message(
                "Unable to capture a screenshot right now.",
                reply_markup=self._menu_markup("overview"),
            )

    async def _send_chart_screenshot(self, symbol=None, timeframe=None):
        screenshot_path = await self.controller.capture_chart_screenshot(
            str(symbol or "").strip().upper() or None,
            timeframe,
            prefix="telegram_chart",
        )
        if screenshot_path:
            symbol_text = str(symbol or "").strip().upper() or "current chart"
            timeframe_text = str(timeframe or getattr(self.controller, "time_frame", "1h") or "1h").strip() or "1h"
            caption = f"Sopotek chart {symbol_text} ({timeframe_text})"
            sent = await self.send_photo(screenshot_path, caption=caption)
            if not sent:
                await self.send_message(
                    f"Chart captured but could not be uploaded: <code>{screenshot_path}</code>",
                    reply_markup=self._menu_markup("markets"),
                )
        else:
            await self.send_message(
                "Unable to open or capture that chart right now.",
                reply_markup=self._menu_markup("markets"),
            )

    async def _send_section_text(self, text, section):
        await self.send_message(str(text or ""), reply_markup=self._menu_markup(section))

    async def _edit_or_send_message(self, chat_id, message_id, text, reply_markup=None, include_keyboard=False):
        if message_id not in (None, ""):
            edited = await self._edit_message(chat_id, message_id, text, reply_markup=reply_markup)
            if edited:
                return True
        return await self.send_message(text, include_keyboard=include_keyboard, reply_markup=reply_markup)

    async def _show_menu_view(self, section, chat_id, message_id=None):
        text = await self._menu_text(section)
        return await self._edit_or_send_message(
            chat_id,
            message_id,
            text,
            reply_markup=self._menu_markup(section),
        )

    async def _menu_text(self, section):
        normalized = str(section or "overview").strip().lower()
        if normalized == "portfolio":
            return self._join_blocks(
                "<b>Portfolio Console</b>\nReview balances, live exposure, and working orders from Telegram.",
                await self.controller.telegram_balances_text(),
                await self.controller.telegram_positions_text(),
                await self.controller.telegram_open_orders_text(),
            )
        if normalized == "markets":
            return self._join_blocks(
                "<b>Market Intel</b>\nFollow active trade ideas, position analysis, and chart capture shortcuts.",
                await self.controller.telegram_recommendations_text(),
                await self.controller.telegram_position_analysis_text(open_window=False),
            )
        if normalized == "performance":
            return self._join_blocks(
                "<b>Performance Console</b>\nTrack outcomes before changing risk or enabling automation.",
                await self.controller.telegram_performance_text(),
                await self._history_summary(limit=120, open_window=False),
            )
        if normalized == "workspace":
            management_text = str(
                getattr(self.controller, "telegram_management_text", lambda: "Management summary is not available.")()
            )
            return self._join_blocks(
                "<b>Workspace Console</b>\nJump into settings, health, research, and review surfaces without leaving Telegram.",
                management_text,
                await self._call_controller_text_method("telegram_settings_text", open_window=False),
                await self._call_controller_text_method("telegram_health_text", open_window=False),
            )
        if normalized == "controls":
            management_text = str(
                getattr(self.controller, "telegram_management_text", lambda: "Management summary is not available.")()
            )
            return self._join_blocks(
                "<b>Remote Controls</b>\nUse refresh actions freely. State-changing trading controls stay confirmation-gated.",
                management_text,
            )
        if normalized == "help":
            return self._join_blocks(
                self._help_text(),
                "Tip: the keyboard buttons are aliases, so you can tap sections or type a natural-language question at any time.",
            )
        return self._join_blocks(
            "<b>Sopotek Pilot Remote Console</b>\nUse the inline panels below to navigate the live desktop workspace.",
            await self.controller.telegram_status_text(),
            "Tip: ask a plain-English question at any time and Sopotek Pilot will answer with current app context.",
        )

    async def _history_summary(self, limit=300, open_window=True):
        summary_builder = getattr(self.controller, "market_chat_trade_history_summary", None)
        if not callable(summary_builder):
            return "Trade history summary is not available right now."
        try:
            result = summary_builder(limit=limit, open_window=open_window)
        except TypeError:
            result = summary_builder(limit=limit)
        if asyncio.iscoroutine(result):
            result = await result
        return str(result or "Trade history summary is not available right now.")

    @staticmethod
    def _join_blocks(*blocks):
        parts = [str(block).strip() for block in blocks if str(block or "").strip()]
        return "\n\n".join(parts)

    def _split_message_chunks(self, text, max_length=3500):
        raw = str(text or "")
        if not raw:
            return [""]
        if len(raw) <= max_length:
            return [raw]

        chunks = []
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
