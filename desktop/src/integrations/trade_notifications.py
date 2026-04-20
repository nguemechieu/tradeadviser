import asyncio
import html
import math
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

import aiohttp


def _normalize_status(value):
    return str(value or "").strip().lower().replace("-", "_")


def _normalize_symbol(value):
    return str(value or "-").strip().upper() or "-"


def _coerce_float(value):
    if value in (None, "", "-"):
        return None
    try:
        numeric = float(value)
    except Exception:
        return None
    if not math.isfinite(numeric):
        return None
    return numeric


def _first_float(payload, *keys):
    if not isinstance(payload, dict):
        return None
    for key in keys:
        numeric = _coerce_float(payload.get(key))
        if numeric is not None:
            return numeric
    raw = payload.get("raw")
    if isinstance(raw, dict):
        for key in keys:
            numeric = _coerce_float(raw.get(key))
            if numeric is not None:
                return numeric
    return None


def _parse_recipients(value):
    if isinstance(value, (list, tuple, set)):
        candidates = value
    else:
        candidates = str(value or "").replace(";", ",").split(",")
    return [str(item).strip() for item in candidates if str(item).strip()]


def _format_decimal(value, *, default="-", decimals=6):
    numeric = _coerce_float(value)
    if numeric is None:
        return default
    text = f"{numeric:.{decimals}f}".rstrip("0").rstrip(".")
    if text in {"", "-0"}:
        return "0"
    return text


def _format_pnl(value):
    numeric = _coerce_float(value)
    if numeric is None:
        return "-"
    sign = "+" if numeric > 0 else ""
    return f"{sign}{_format_decimal(numeric, default='0', decimals=4)}"


def trade_notification_reason(trade):
    if not isinstance(trade, dict):
        return ""

    candidates = [
        trade.get("reason"),
        trade.get("message"),
    ]
    raw = trade.get("raw")
    if isinstance(raw, dict):
        candidates.extend([raw.get("error"), raw.get("reason"), raw.get("message")])

    for candidate in candidates:
        text = str(candidate or "").strip()
        if text:
            return text

    status = _normalize_status(trade.get("status"))
    if status in {"rejected", "blocked", "skipped", "failed", "error"}:
        return "No rejection reason was supplied by the broker or safety checks."
    return ""


def is_trade_close_event(trade):
    if not isinstance(trade, dict):
        return False
    status = _normalize_status(trade.get("status"))
    if status in {"closed", "close", "exited", "exit", "flattened"}:
        return True
    if any(
        trade.get(key) not in (None, "")
        for key in ("exit_price", "close_price", "closing_price", "realized_pnl", "realized_pl")
    ):
        return True
    return trade.get("pnl") not in (None, "")


def trade_close_cache_key(trade):
    if not isinstance(trade, dict):
        return ""
    symbol = _normalize_symbol(trade.get("symbol"))
    strategy_name = str(trade.get("strategy_name") or "").strip()
    session_id = str(trade.get("session_id") or "").strip()
    exchange = str(trade.get("exchange") or "").strip().lower()
    if symbol == "-":
        return ""
    return "|".join([exchange, session_id, symbol, strategy_name])


def trade_display_size(trade):
    if not isinstance(trade, dict):
        return "-"
    raw_size = trade.get("filled_size", trade.get("size", trade.get("amount", "-")))
    display_size = trade.get("applied_requested_mode_amount")
    display_mode = str(trade.get("requested_quantity_mode") or "").strip().lower()
    if display_size not in (None, "") and display_mode:
        size = f"{display_size} {display_mode}"
        if display_mode != "units" and raw_size not in (None, ""):
            size = f"{size} ({raw_size} units)"
        return size
    return _format_decimal(raw_size, default=str(raw_size or "-"), decimals=6)


def build_trade_close_summary(trade):
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
    strategy_name = str(trade.get("strategy_name") or "-").strip() or "-"
    entry_price = _first_float(
        trade,
        "entry_price",
        "avg_entry_price",
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
    pnl = _first_float(trade, "pnl", "realized_pnl", "realized_pl", "profit", "profit_loss")
    reason = trade_notification_reason(trade)
    order_id = str(trade.get("order_id") or trade.get("id") or "-").strip() or "-"
    timestamp = str(trade.get("timestamp") or datetime.now(timezone.utc).isoformat()).strip()
    size_text = trade_display_size(trade)
    pnl_text = _format_pnl(pnl)
    entry_text = _format_decimal(entry_price)
    close_text = _format_decimal(close_price)
    title = "Trade Closed"
    subject_pnl = pnl_text if pnl_text != "-" else status
    subject = f"[Sopotek] {title}: {symbol} {subject_pnl}"
    return {
        "title": title,
        "subject": subject,
        "symbol": symbol,
        "side": side,
        "status": status,
        "strategy_name": strategy_name,
        "entry_price": entry_price,
        "entry_price_text": entry_text,
        "close_price": close_price,
        "close_price_text": close_text,
        "size_text": size_text,
        "pnl": pnl,
        "pnl_text": pnl_text,
        "order_id": order_id,
        "timestamp": timestamp,
        "reason": reason,
    }


def format_trade_close_text(summary):
    if not summary:
        return "Trade closed"
    lines = [
        summary.get("title") or "Trade Closed",
        f"Symbol: {summary.get('symbol', '-')}",
        f"Strategy: {summary.get('strategy_name', '-')}",
        f"Side: {summary.get('side', '-')}",
        f"Entry price: {summary.get('entry_price_text', '-')}",
        f"Close price: {summary.get('close_price_text', '-')}",
        f"Size: {summary.get('size_text', '-')}",
        f"PnL: {summary.get('pnl_text', '-')}",
        f"Status: {summary.get('status', '-')}",
        f"Order ID: {summary.get('order_id', '-')}",
        f"Time: {summary.get('timestamp', '-')}",
    ]
    reason = str(summary.get("reason") or "").strip()
    if reason:
        lines.append(f"Reason: {reason}")
    return "\n".join(lines)


def format_trade_close_html(summary):
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
        f"Status: <b>{html.escape(str(summary.get('status', '-')))}</b>\n"
        f"Order ID: <code>{html.escape(str(summary.get('order_id', '-')))}</code>\n"
        f"Time: <code>{html.escape(str(summary.get('timestamp', '-')))}</code>\n"
        f"{reason_line}"
    ).rstrip()


def format_trade_close_sms(summary):
    if not summary:
        return "Trade closed."
    return (
        f"Trade closed {summary.get('symbol', '-')}"
        f" | Strategy {summary.get('strategy_name', '-')}"
        f" | Side {summary.get('side', '-')}"
        f" | Entry {summary.get('entry_price_text', '-')}"
        f" | Close {summary.get('close_price_text', '-')}"
        f" | PnL {summary.get('pnl_text', '-')}"
    )


class EmailTradeNotificationService:
    def __init__(
        self,
        *,
        host="",
        port=587,
        username="",
        password="",
        from_addr="",
        to_addrs=None,
        use_starttls=True,
        timeout=15.0,
    ):
        self.host = str(host or "").strip()
        self.port = int(port or 587)
        self.username = str(username or "").strip()
        self.password = str(password or "")
        self.from_addr = str(from_addr or "").strip()
        self.to_addrs = _parse_recipients(to_addrs)
        self.use_starttls = bool(use_starttls)
        self.timeout = float(timeout)

    @property
    def enabled(self):
        return bool(self.host and self.from_addr and self.to_addrs)

    async def send_trade_close(self, trade):
        if not self.enabled or not is_trade_close_event(trade):
            return False
        summary = build_trade_close_summary(trade)
        await asyncio.to_thread(self._send_sync, summary)
        return True

    def _send_sync(self, summary):
        message = EmailMessage()
        message["Subject"] = summary.get("subject") or "[Sopotek] Trade Closed"
        message["From"] = self.from_addr
        message["To"] = ", ".join(self.to_addrs)
        message.set_content(format_trade_close_text(summary))
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            if self.use_starttls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(message)


class TwilioSmsTradeNotificationService:
    def __init__(
        self,
        *,
        account_sid="",
        auth_token="",
        from_number="",
        to_number="",
        timeout=15.0,
    ):
        self.account_sid = str(account_sid or "").strip()
        self.auth_token = str(auth_token or "").strip()
        self.from_number = str(from_number or "").strip()
        self.to_number = str(to_number or "").strip()
        self.timeout = float(timeout)
        self._session = None

    @property
    def enabled(self):
        return bool(self.account_sid and self.auth_token and self.from_number and self.to_number)

    async def send_trade_close(self, trade):
        if not self.enabled or not is_trade_close_event(trade):
            return False
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        summary = build_trade_close_summary(trade)
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
            return 200 <= response.status < 300

    async def close(self):
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None
