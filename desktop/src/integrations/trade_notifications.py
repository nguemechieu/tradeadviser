from __future__ import annotations

"""
InvestPro trade notification utilities.

Features:
- Detect trade-close events.
- Build normalized trade summaries.
- Format trade summaries for plain text, HTML, SMS, Telegram, and email.
- Send email notifications through SMTP.
- Send SMS notifications through Twilio REST API.
- Optional duplicate suppression.
- Safer numeric formatting.
- HTML escaping.
- Async-compatible sending.

This module does not decide whether a trade should happen.
It only formats and sends notifications after trade/order events.
"""

import asyncio
import html
import json
import math
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Optional

import aiohttp


# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_status(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_symbol(value: Any) -> str:
    return str(value or "-").strip().upper() or "-"


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, "", "-"):
        return None

    try:
        numeric = float(value)
    except Exception:
        return None

    if not math.isfinite(numeric):
        return None

    return numeric


def _first_value(payload: dict[str, Any], *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None

    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return value

    raw = payload.get("raw")
    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)
            if value not in (None, ""):
                return value

    return None


def _first_float(payload: dict[str, Any], *keys: str) -> Optional[float]:
    value = _first_value(payload, *keys)
    return _coerce_float(value)


def _parse_recipients(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = str(value or "").replace(";", ",").split(",")

    return [str(item).strip() for item in candidates if str(item).strip()]


def _format_decimal(value: Any, *, default: str = "-", decimals: int = 6) -> str:
    numeric = _coerce_float(value)

    if numeric is None:
        return default

    text = f"{numeric:.{int(decimals)}f}".rstrip("0").rstrip(".")

    if text in {"", "-0"}:
        return "0"

    return text


def _format_pnl(value: Any) -> str:
    numeric = _coerce_float(value)

    if numeric is None:
        return "-"

    sign = "+" if numeric > 0 else ""
    return f"{sign}{_format_decimal(numeric, default='0', decimals=4)}"


def _format_percent(value: Any) -> str:
    numeric = _coerce_float(value)

    if numeric is None:
        return "-"

    sign = "+" if numeric > 0 else ""
    return f"{sign}{_format_decimal(numeric, default='0', decimals=2)}%"


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, indent=2, default=str)
    except Exception:
        return str(value)


# ---------------------------------------------------------------------
# Summary model
# ---------------------------------------------------------------------


@dataclass(slots=True)
class TradeCloseSummary:
    title: str = "Trade Closed"
    subject: str = "[InvestPro] Trade Closed"
    symbol: str = "-"
    side: str = "-"
    status: str = "CLOSED"
    strategy_name: str = "-"
    entry_price: Optional[float] = None
    entry_price_text: str = "-"
    close_price: Optional[float] = None
    close_price_text: str = "-"
    size_text: str = "-"
    pnl: Optional[float] = None
    pnl_text: str = "-"
    pnl_percent: Optional[float] = None
    pnl_percent_text: str = "-"
    order_id: str = "-"
    trade_id: str = "-"
    exchange: str = "-"
    account_id: str = "-"
    session_id: str = "-"
    timestamp: str = field(default_factory=_utc_now_iso)
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "subject": self.subject,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status,
            "strategy_name": self.strategy_name,
            "entry_price": self.entry_price,
            "entry_price_text": self.entry_price_text,
            "close_price": self.close_price,
            "close_price_text": self.close_price_text,
            "size_text": self.size_text,
            "pnl": self.pnl,
            "pnl_text": self.pnl_text,
            "pnl_percent": self.pnl_percent,
            "pnl_percent_text": self.pnl_percent_text,
            "order_id": self.order_id,
            "trade_id": self.trade_id,
            "exchange": self.exchange,
            "account_id": self.account_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------
# Trade detection / summary building
# ---------------------------------------------------------------------


def trade_notification_reason(trade: dict[str, Any]) -> str:
    """Extract the most useful trade notification reason."""
    if not isinstance(trade, dict):
        return ""

    candidates = [
        trade.get("reason"),
        trade.get("close_reason"),
        trade.get("exit_reason"),
        trade.get("message"),
        trade.get("error"),
    ]

    raw = trade.get("raw")
    if isinstance(raw, dict):
        candidates.extend(
            [
                raw.get("error"),
                raw.get("reason"),
                raw.get("message"),
                raw.get("reject_reason"),
                raw.get("status_message"),
            ]
        )

    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text

    status = _normalize_status(trade.get("status"))

    if status in {"rejected", "blocked", "skipped", "failed", "error"}:
        return "No rejection reason was supplied by the broker or safety checks."

    return ""


def is_trade_close_event(trade: dict[str, Any]) -> bool:
    """Return True when the payload looks like a closed/exit trade event."""
    if not isinstance(trade, dict):
        return False

    status = _normalize_status(trade.get("status"))

    if status in {
        "closed",
        "close",
        "exited",
        "exit",
        "flattened",
        "filled_close",
        "position_closed",
    }:
        return True

    if any(
        trade.get(key) not in (None, "")
        for key in (
            "exit_price",
            "close_price",
            "closing_price",
            "realized_pnl",
            "realized_pl",
            "profit",
            "profit_loss",
        )
    ):
        return True

    # PnL alone can be used by your app as a closed-trade event.
    return trade.get("pnl") not in (None, "")


def trade_close_cache_key(trade: dict[str, Any]) -> str:
    """Build a stable key to suppress duplicate close alerts."""
    if not isinstance(trade, dict):
        return ""

    symbol = _normalize_symbol(trade.get("symbol"))
    strategy_name = str(trade.get("strategy_name") or "").strip()
    session_id = str(trade.get("session_id") or "").strip()
    exchange = str(trade.get("exchange") or trade.get(
        "broker") or "").strip().lower()
    order_id = str(trade.get("order_id") or trade.get(
        "id") or trade.get("trade_id") or "").strip()
    timestamp = str(trade.get("timestamp") or "").strip()

    if symbol == "-":
        return ""

    return "|".join([exchange, session_id, symbol, strategy_name, order_id, timestamp])


def trade_display_size(trade: dict[str, Any]) -> str:
    """Return a human-friendly trade size."""
    if not isinstance(trade, dict):
        return "-"

    raw_size = trade.get("filled_size", trade.get(
        "filled", trade.get("size", trade.get("amount", "-"))))
    display_size = trade.get("applied_requested_mode_amount")
    display_mode = str(trade.get("requested_quantity_mode")
                       or "").strip().lower()

    if display_size not in (None, "") and display_mode:
        size = f"{display_size} {display_mode}"
        if display_mode != "units" and raw_size not in (None, ""):
            size = f"{size} ({raw_size} units)"
        return size

    return _format_decimal(raw_size, default=str(raw_size or "-"), decimals=8)


def build_trade_close_summary(trade: dict[str, Any], *, app_name: str = "InvestPro") -> dict[str, Any]:
    """Build a normalized summary dictionary for a closed trade."""
    if not isinstance(trade, dict):
        return {}

    symbol = _normalize_symbol(trade.get("symbol"))

    side = str(
        trade.get("side")
        or trade.get("position_side")
        or trade.get("trade_side")
        or "-"
    ).strip().upper() or "-"

    status = str(trade.get("status") or "closed").strip().upper() or "CLOSED"
    strategy_name = str(trade.get("strategy_name")
                        or trade.get("strategy") or "-").strip() or "-"

    entry_price = _first_float(
        trade,
        "entry_price",
        "avg_entry_price",
        "average_entry_price",
        "open_price",
        "opening_price",
    )

    close_price = _first_float(
        trade,
        "exit_price",
        "close_price",
        "closing_price",
        "price",
        "avg_price",
        "average",
    )

    pnl = _first_float(
        trade,
        "pnl",
        "realized_pnl",
        "realized_pl",
        "profit",
        "profit_loss",
    )

    pnl_percent = _first_float(
        trade,
        "pnl_percent",
        "return_percent",
        "return_pct",
        "roi",
    )

    reason = trade_notification_reason(trade)

    order_id = str(trade.get("order_id") or trade.get(
        "id") or "-").strip() or "-"
    trade_id = str(trade.get("trade_id") or trade.get(
        "position_id") or order_id or "-").strip() or "-"
    exchange = str(trade.get("exchange") or trade.get(
        "broker") or "-").strip() or "-"
    account_id = str(trade.get("account_id") or "-").strip() or "-"
    session_id = str(trade.get("session_id") or "-").strip() or "-"
    timestamp = str(trade.get("timestamp") or _utc_now_iso()).strip()

    size_text = trade_display_size(trade)
    pnl_text = _format_pnl(pnl)
    pnl_percent_text = _format_percent(pnl_percent)
    entry_text = _format_decimal(entry_price)
    close_text = _format_decimal(close_price)

    title = "Trade Closed"
    subject_pnl = pnl_text if pnl_text != "-" else status
    subject = f"[{app_name}] {title}: {symbol} {subject_pnl}"

    summary = TradeCloseSummary(
        title=title,
        subject=subject,
        symbol=symbol,
        side=side,
        status=status,
        strategy_name=strategy_name,
        entry_price=entry_price,
        entry_price_text=entry_text,
        close_price=close_price,
        close_price_text=close_text,
        size_text=size_text,
        pnl=pnl,
        pnl_text=pnl_text,
        pnl_percent=pnl_percent,
        pnl_percent_text=pnl_percent_text,
        order_id=order_id,
        trade_id=trade_id,
        exchange=exchange,
        account_id=account_id,
        session_id=session_id,
        timestamp=timestamp,
        reason=reason,
        metadata={
            "cache_key": trade_close_cache_key(trade),
            "raw_status": trade.get("status"),
        },
    )

    return summary.to_dict()


# ---------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------


def format_trade_close_text(summary: dict[str, Any]) -> str:
    if not summary:
        return "Trade closed."

    lines = [
        summary.get("title") or "Trade Closed",
        f"Symbol: {summary.get('symbol', '-')}",
        f"Strategy: {summary.get('strategy_name', '-')}",
        f"Side: {summary.get('side', '-')}",
        f"Entry price: {summary.get('entry_price_text', '-')}",
        f"Close price: {summary.get('close_price_text', '-')}",
        f"Size: {summary.get('size_text', '-')}",
        f"PnL: {summary.get('pnl_text', '-')}",
        f"PnL %: {summary.get('pnl_percent_text', '-')}",
        f"Status: {summary.get('status', '-')}",
        f"Exchange: {summary.get('exchange', '-')}",
        f"Account: {summary.get('account_id', '-')}",
        f"Order ID: {summary.get('order_id', '-')}",
        f"Trade ID: {summary.get('trade_id', '-')}",
        f"Time: {summary.get('timestamp', '-')}",
    ]

    reason = str(summary.get("reason") or "").strip()
    if reason:
        lines.append(f"Reason: {reason}")

    return "\n".join(lines)


def format_trade_close_html(summary: dict[str, Any]) -> str:
    if not summary:
        return "<b>Trade Closed</b>"

    reason = str(summary.get("reason") or "").strip()
    reason_line = f"Reason: <code>{html.escape(reason)}</code>\n" if reason else ""

    return (
        "<b>Trade Closed</b>\n"
        f"Symbol: <code>{html.escape(str(summary.get('symbol', '-')))}</code>\n"
        f"Strategy: <code>{html.escape(str(summary.get('strategy_name', '-')))}</code>\n"
        f"Side: <b>{html.escape(str(summary.get('side', '-')))}</b>\n"
        f"Entry price: <code>{html.escape(str(summary.get('entry_price_text', '-')))}</code>\n"
        f"Close price: <code>{html.escape(str(summary.get('close_price_text', '-')))}</code>\n"
        f"Size: <code>{html.escape(str(summary.get('size_text', '-')))}</code>\n"
        f"PnL: <code>{html.escape(str(summary.get('pnl_text', '-')))}</code>\n"
        f"PnL %: <code>{html.escape(str(summary.get('pnl_percent_text', '-')))}</code>\n"
        f"Status: <b>{html.escape(str(summary.get('status', '-')))}</b>\n"
        f"Exchange: <code>{html.escape(str(summary.get('exchange', '-')))}</code>\n"
        f"Account: <code>{html.escape(str(summary.get('account_id', '-')))}</code>\n"
        f"Order ID: <code>{html.escape(str(summary.get('order_id', '-')))}</code>\n"
        f"Trade ID: <code>{html.escape(str(summary.get('trade_id', '-')))}</code>\n"
        f"Time: <code>{html.escape(str(summary.get('timestamp', '-')))}</code>\n"
        f"{reason_line}"
    ).rstrip()


def format_trade_close_email_html(summary: dict[str, Any], *, app_name: str = "InvestPro") -> str:
    """HTML email version with simple table formatting."""
    if not summary:
        return "<html><body><h2>Trade Closed</h2></body></html>"

    def row(label: str, value: Any) -> str:
        return (
            "<tr>"
            f"<td style='padding:6px 10px;font-weight:bold;border-bottom:1px solid #eee'>{html.escape(label)}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'><code>{html.escape(str(value))}</code></td>"
            "</tr>"
        )

    reason = str(summary.get("reason") or "").strip()

    rows = [
        row("Symbol", summary.get("symbol", "-")),
        row("Strategy", summary.get("strategy_name", "-")),
        row("Side", summary.get("side", "-")),
        row("Entry price", summary.get("entry_price_text", "-")),
        row("Close price", summary.get("close_price_text", "-")),
        row("Size", summary.get("size_text", "-")),
        row("PnL", summary.get("pnl_text", "-")),
        row("PnL %", summary.get("pnl_percent_text", "-")),
        row("Status", summary.get("status", "-")),
        row("Exchange", summary.get("exchange", "-")),
        row("Account", summary.get("account_id", "-")),
        row("Order ID", summary.get("order_id", "-")),
        row("Trade ID", summary.get("trade_id", "-")),
        row("Time", summary.get("timestamp", "-")),
    ]

    if reason:
        rows.append(row("Reason", reason))

    return (
        "<html>"
        "<body style='font-family:Arial,sans-serif;color:#111'>"
        f"<h2>{html.escape(app_name)} - Trade Closed</h2>"
        "<table style='border-collapse:collapse'>"
        f"{''.join(rows)}"
        "</table>"
        "<p style='font-size:12px;color:#666'>This is an automated trading notification.</p>"
        "</body>"
        "</html>"
    )


def format_trade_close_sms(summary: dict[str, Any]) -> str:
    if not summary:
        return "Trade closed."

    text = (
        f"Trade closed {summary.get('symbol', '-')}"
        f" | Strategy {summary.get('strategy_name', '-')}"
        f" | Side {summary.get('side', '-')}"
        f" | Entry {summary.get('entry_price_text', '-')}"
        f" | Close {summary.get('close_price_text', '-')}"
        f" | PnL {summary.get('pnl_text', '-')}"
    )

    pnl_percent = str(summary.get("pnl_percent_text") or "-")
    if pnl_percent != "-":
        text += f" ({pnl_percent})"

    return text[:1500]


def format_trade_event_text(trade: dict[str, Any], *, app_name: str = "InvestPro") -> str:
    """Generic non-close trade event text."""
    if not isinstance(trade, dict):
        return "Trade event received."

    symbol = _normalize_symbol(trade.get("symbol"))
    side = str(trade.get("side") or "-").upper()
    status = str(trade.get("status") or "-").upper()
    price = _format_decimal(
        trade.get("price"), default=str(trade.get("price", "-")))
    amount = trade_display_size(trade)
    reason = trade_notification_reason(trade)
    order_id = str(trade.get("order_id") or trade.get("id") or "-")
    timestamp = str(trade.get("timestamp") or _utc_now_iso())

    lines = [
        f"{app_name} Trade Event",
        f"Symbol: {symbol}",
        f"Side: {side}",
        f"Status: {status}",
        f"Price: {price}",
        f"Size: {amount}",
        f"Order ID: {order_id}",
        f"Time: {timestamp}",
    ]

    if reason:
        lines.append(f"Reason: {reason}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Duplicate suppression
# ---------------------------------------------------------------------


class NotificationDeduper:
    """Small in-memory notification deduper."""

    def __init__(self, ttl_seconds: float = 600.0, max_items: int = 1000) -> None:
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self.max_items = max(10, int(max_items))
        self._seen: dict[str, float] = {}

    def seen_recently(self, key: str) -> bool:
        if not key:
            return False

        self._purge()
        created_at = self._seen.get(key)

        if created_at is None:
            self._seen[key] = time.time()
            return False

        if (time.time() - created_at) <= self.ttl_seconds:
            return True

        self._seen[key] = time.time()
        return False

    def _purge(self) -> None:
        now = time.time()

        expired = [
            key for key, created_at in self._seen.items()
            if (now - created_at) > self.ttl_seconds
        ]

        for key in expired:
            self._seen.pop(key, None)

        if len(self._seen) <= self.max_items:
            return

        sorted_items = sorted(self._seen.items(), key=lambda item: item[1])
        for key, _ in sorted_items[: len(self._seen) - self.max_items]:
            self._seen.pop(key, None)


# ---------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------


class EmailTradeNotificationService:
    def __init__(
        self,
        *,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        from_addr: str = "",
        to_addrs: Any = None,
        use_starttls: bool = True,
        use_ssl: bool = False,
        timeout: float = 15.0,
        app_name: str = "InvestPro",
        dedupe: Optional[NotificationDeduper] = None,
    ) -> None:
        self.host = str(host or "").strip()
        self.port = int(port or 587)
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.from_addr = str(from_addr or "").strip()
        self.to_addrs = _parse_recipients(to_addrs)
        self.use_starttls = bool(use_starttls)
        self.use_ssl = bool(use_ssl)
        self.timeout = float(timeout)
        self.app_name = str(app_name or "InvestPro")
        self.deduper = dedupe or NotificationDeduper()

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.from_addr and self.to_addrs)

    async def send_trade_close(self, trade: dict[str, Any]) -> bool:
        if not self.enabled or not is_trade_close_event(trade):
            return False

        key = trade_close_cache_key(trade)
        if self.deduper.seen_recently(f"email:{key}"):
            return False

        summary = build_trade_close_summary(trade, app_name=self.app_name)
        await asyncio.to_thread(self._send_sync, summary)
        return True

    def _send_sync(self, summary: dict[str, Any]) -> None:
        message = EmailMessage()
        message["Subject"] = summary.get(
            "subject") or f"[{self.app_name}] Trade Closed"
        message["From"] = self.from_addr
        message["To"] = ", ".join(self.to_addrs)

        message.set_content(format_trade_close_text(summary))
        message.add_alternative(
            format_trade_close_email_html(summary, app_name=self.app_name),
            subtype="html",
        )

        if self.use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context) as smtp:
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
            return

        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            if self.use_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


# ---------------------------------------------------------------------
# Twilio SMS
# ---------------------------------------------------------------------


class TwilioSmsTradeNotificationService:
    def __init__(
        self,
        *,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
        to_number: str = "",
        timeout: float = 15.0,
        app_name: str = "InvestPro",
        dedupe: Optional[NotificationDeduper] = None,
    ) -> None:
        self.account_sid = str(account_sid or "").strip()
        self.auth_token = str(auth_token or "").strip()
        self.from_number = str(from_number or "").strip()
        self.to_number = str(to_number or "").strip()
        self.timeout = float(timeout)
        self.app_name = str(app_name or "InvestPro")
        self.deduper = dedupe or NotificationDeduper()
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def enabled(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number and self.to_number)

    async def send_trade_close(self, trade: dict[str, Any]) -> bool:
        if not self.enabled or not is_trade_close_event(trade):
            return False

        key = trade_close_cache_key(trade)
        if self.deduper.seen_recently(f"sms:{key}"):
            return False

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout))

        summary = build_trade_close_summary(trade, app_name=self.app_name)

        payload = {
            "From": self.from_number,
            "To": self.to_number,
            "Body": format_trade_close_sms(summary),
        }

        url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

        async with self._session.post(
            url,
            data=payload,
            auth=aiohttp.BasicAuth(self.account_sid, self.auth_token),
        ) as response:
            if 200 <= response.status < 300:
                return True

            try:
                error_payload = await response.json(content_type=None)
            except Exception:
                error_payload = await response.text()

            raise RuntimeError(
                f"Twilio SMS failed with status {response.status}: {_safe_json(error_payload)}")

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None




class TradeNotificationManager:
    """Fan-out trade notifications to multiple services."""

    def __init__(
        self,
        *,
        email_service: Optional[EmailTradeNotificationService] = None,
        sms_service: Optional[TwilioSmsTradeNotificationService] = None,
        telegram_service: Any = None,
        logger: Any = None,
    ) -> None:
        self.email_service = email_service
        self.sms_service = sms_service
        self.telegram_service = telegram_service
        self.logger = logger

    async def notify_trade_close(self, trade: dict[str, Any]) -> dict[str, bool]:
        """Send close notification to all configured channels."""
        results = {
            "email": False,
            "sms": False,
            "telegram": False,
        }

        if not is_trade_close_event(trade):
            return results

        if self.email_service is not None:
            try:
                results["email"] = await self.email_service.send_trade_close(trade)
            except Exception as exc:
                self._log_debug(
                    "Email trade close notification failed: %s", exc)

        if self.sms_service is not None:
            try:
                results["sms"] = await self.sms_service.send_trade_close(trade)
            except Exception as exc:
                self._log_debug("SMS trade close notification failed: %s", exc)

        if self.telegram_service is not None:
            try:
                notifier = getattr(self.telegram_service,
                                   "notify_trade_close", None)
                if callable(notifier):
                    result = notifier(trade)
                    if asyncio.iscoroutine(result):
                        await result
                    results["telegram"] = True
            except Exception as exc:
                self._log_debug(
                    "Telegram trade close notification failed: %s", exc)

        return results

    async def close(self) -> None:
        if self.sms_service is not None:
            close = getattr(self.sms_service, "close", None)
            if callable(close):
                result = close()
                if asyncio.iscoroutine(result):
                    await result

    def _log_debug(self, message: str, *args: Any) -> None:
        if self.logger is not None and hasattr(self.logger, "debug"):
            self.logger.debug(message, *args)
