import math
import re
from datetime import datetime, timezone


def coerce_utc_datetime(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        numeric = float(value)
    except Exception:
        numeric = None
    if numeric is not None:
        try:
            if abs(numeric) > 1e11:
                return datetime.fromtimestamp(numeric / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
        except Exception:
            return None
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def age_seconds(value, *, now=None):
    parsed = coerce_utc_datetime(value)
    if parsed is None:
        return None
    reference_now = coerce_utc_datetime(now) or datetime.now(timezone.utc)
    delta = (reference_now - parsed).total_seconds()
    if not math.isfinite(delta):
        return None
    return max(0.0, float(delta))


def timeframe_seconds(timeframe, default=60):
    text = str(timeframe or "").strip().lower()
    match = re.fullmatch(r"(\d+)([smhdw])", text)
    if not match:
        return int(default)
    value = max(1, int(match.group(1)))
    unit = match.group(2)
    multiplier = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 604800,
    }.get(unit, 60)
    return value * multiplier


def format_age_label(seconds):
    if seconds is None:
        return "unknown"
    numeric = max(0.0, float(seconds))
    if numeric < 1:
        return "<1s"
    if numeric < 60:
        return f"{numeric:.1f}s"
    if numeric < 3600:
        return f"{numeric / 60.0:.1f}m"
    if numeric < 86400:
        return f"{numeric / 3600.0:.1f}h"
    return f"{numeric / 86400.0:.1f}d"


def _review_status_line(label, item):
    if not isinstance(item, dict):
        return f"{label}: unavailable"
    supported = item.get("supported", True)
    if supported is False:
        return f"{label}: unsupported"
    state = "fresh" if item.get("fresh") else "stale"
    age_label = str(item.get("age_label") or "unknown")
    threshold_label = str(item.get("threshold_label") or "").strip()
    suffix = f" (age {age_label}" + (f", limit {threshold_label}" if threshold_label else "") + ")"
    return f"{label}: {state}{suffix}"


def compose_live_trade_review_message(
    *,
    symbol,
    side,
    order_type,
    requested_amount,
    display_mode,
    exchange_name,
    account_label,
    preflight,
):
    normalized_symbol = str(symbol or "").strip().upper()
    normalized_side = str(side or "").strip().upper()
    normalized_type = str(order_type or "market").strip().upper()
    exchange_label = str(exchange_name or "broker").strip().upper() or "BROKER"
    amount_label = f"{requested_amount} {display_mode}".strip()
    venue = str((preflight or {}).get("resolved_venue") or "spot").strip().lower() or "spot"
    reference_price = (preflight or {}).get("reference_price")
    sizing_summary = str((preflight or {}).get("sizing_summary") or "").strip()
    sizing_notes = [str(note).strip() for note in ((preflight or {}).get("sizing_notes") or []) if str(note).strip()]
    eligibility = (preflight or {}).get("eligibility_check") or {}
    guard = (preflight or {}).get("market_data_guard") or {}

    lines = [
        f"Submit this live order?",
        "",
        f"Broker: {exchange_label}",
        f"Account: {account_label}",
        f"Venue: {venue.title()}",
        f"Order: {normalized_side} {amount_label} {normalized_symbol}",
        f"Type: {normalized_type}",
    ]
    if reference_price not in (None, ""):
        lines.append(f"Reference Price: {reference_price}")
    if sizing_summary:
        lines.append(f"Sizing: {sizing_summary}")
    if sizing_notes:
        lines.append("Notes:")
        lines.extend(f"- {note}" for note in sizing_notes[:4])

    lines.extend(
        [
            "",
            "Market Data Checks:",
            f"- {_review_status_line('Quote', guard.get('quote'))}",
            f"- {_review_status_line('Candles', guard.get('candles'))}",
            f"- {_review_status_line('Orderbook', guard.get('orderbook'))}",
        ]
    )

    warnings = [str(item).strip() for item in (eligibility.get("warnings") or []) if str(item).strip()]
    if warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {item}" for item in warnings[:4])

    lines.extend(
        [
            "",
            "Select Yes to send the live order now.",
        ]
    )
    return "\n".join(lines)
