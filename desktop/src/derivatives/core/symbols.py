from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from derivatives.core.models import BrokerRoute


MONTH_CODES = {
    "F": 1,
    "G": 2,
    "H": 3,
    "J": 4,
    "K": 5,
    "M": 6,
    "N": 7,
    "Q": 8,
    "U": 9,
    "V": 10,
    "X": 11,
    "Z": 12,
}

COIN_QUOTES = ("USDT", "USDC", "BUSD", "USD", "DAI","BTC", "ETH", "EUR")
ROOT_ALIASES = {"BIT": "BTC", "XBT": "BTC"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _upper(value: Any) -> str:
    return _text(value).upper()


def _alias_root(value: Any) -> str:
    return ROOT_ALIASES.get(_upper(value), _upper(value))


def _iso_date(value: Any) -> str | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).date().isoformat()
    except ValueError:
        return None


def _parse_month_code(symbol: str) -> str | None:
    match = re.fullmatch(r"([A-Z]+)([FGHJKMNQUVXZ])(\d{1,2})", symbol)
    if not match:
        return None
    root, month_code, year_code = match.groups()
    month = MONTH_CODES.get(month_code)
    if month is None:
        return None
    year = 2000 + int(year_code)
    return f"{_alias_root(root)}/USD:{year:04d}-{month:02d}"


def _split_compact_quote(symbol: str) -> tuple[str, str] | None:
    text = _upper(symbol)
    for quote in COIN_QUOTES:
        if text.endswith(quote) and len(text) > len(quote):
            return _alias_root(text[: -len(quote)]), quote
    return None


def normalize_symbol(exchange: str, raw_symbol: str, market: Mapping[str, Any] | None = None) -> str:
    exchange_code = _upper(exchange)
    symbol = _upper(raw_symbol)
    market = dict(market or {})

    base = _alias_root(market.get("base") or market.get("base_currency") or market.get("base_currency_id"))
    quote = _upper(market.get("quote") or market.get("quote_currency") or market.get("quote_currency_id"))
    settle = _upper(market.get("settle") or market.get("settlement_currency_id")) or quote or "USD"
    expiry_date = _iso_date(market.get("expiryDatetime") or market.get("expiration_time") or market.get("expiry"))

    if exchange_code in {"COINBASE", "COINBASE_FUTURES"}:
        product_id = _upper(market.get("product_id") or symbol)
        details = market.get("future_product_details") if isinstance(market.get("future_product_details"), Mapping) else {}
        expiry_type = _upper(details.get("contract_expiry_type") or market.get("contract_expiry_type"))
        if "PERP" in product_id or expiry_type == "PERPETUAL":
            root = _alias_root(base or product_id.split("-", 1)[0])
            settlement = _upper(details.get("settlement_currency_id") or settle or "USDC")
            return f"{root}/{settlement}:PERP"
        if expiry_date:
            root = _alias_root(base or product_id.split("-", 1)[0])
            return f"{root}/{quote or settle or 'USD'}:{expiry_date}"

    if market.get("swap"):
        resolved = _split_compact_quote(symbol)
        if resolved is not None:
            base, quote = resolved
        if base and (quote or settle):
            return f"{base}/{quote or settle}:PERP"

    if market.get("future") and expiry_date:
        if not base or not quote:
            resolved = _split_compact_quote(symbol.replace("_", ""))
            if resolved is not None:
                base, quote = resolved
        if base and quote:
            return f"{base}/{quote}:{expiry_date}"

    if exchange_code in {"BINANCE", "BYBIT"}:
        compact = symbol.replace("_", "")
        if re.fullmatch(r"[A-Z0-9]+_\d{6}", symbol):
            head, expiry = symbol.split("_", 1)
            resolved = _split_compact_quote(head)
            if resolved is not None:
                base, quote = resolved
                year = 2000 + int(expiry[:2])
                month = int(expiry[2:4])
                day = int(expiry[4:6])
                return f"{base}/{quote}:{year:04d}-{month:02d}-{day:02d}"
        resolved = _split_compact_quote(compact)
        if resolved is not None:
            base, quote = resolved
            return f"{base}/{quote}:PERP"

    if exchange_code in {"IBKR", "TRADOVATE"}:
        parsed = _parse_month_code(symbol)
        if parsed is not None:
            return parsed

    if "/" in symbol and ":" in symbol:
        base_quote, suffix = symbol.split(":", 1)
        left, right = base_quote.split("/", 1)
        return f"{_alias_root(left)}/{_upper(right)}:{_upper(suffix)}"

    if "/" in symbol:
        left, right = symbol.split("/", 1)
        return f"{_alias_root(left)}/{_upper(right)}:PERP"

    resolved = _split_compact_quote(symbol)
    if resolved is not None:
        base, quote = resolved
        return f"{base}/{quote}:PERP"

    parsed = _parse_month_code(symbol)
    if parsed is not None:
        return parsed

    return symbol


class SymbolRegistry:
    def __init__(self) -> None:
        self._routes_by_normalized: dict[str, list[BrokerRoute]] = defaultdict(list)
        self._routes_by_exchange_symbol: dict[tuple[str, str], BrokerRoute] = {}

    def register(
        self,
        *,
        broker_key: str,
        exchange: str,
        account_id: str | None,
        raw_symbol: str,
        market: Mapping[str, Any] | None = None,
        market_type: str = "future",
        metadata: dict[str, Any] | None = None,
    ) -> BrokerRoute:
        normalized = normalize_symbol(exchange, raw_symbol, market=market)
        route = BrokerRoute(
            broker_key=broker_key,
            exchange=_text(exchange).lower(),
            account_id=account_id,
            raw_symbol=_text(raw_symbol),
            normalized_symbol=normalized,
            market_type=_text(market_type) or "future",
            metadata={**dict(market or {}), **dict(metadata or {})},
        )
        key = (route.exchange, _upper(route.raw_symbol))
        self._routes_by_exchange_symbol[key] = route
        routes = [item for item in self._routes_by_normalized[normalized] if item.broker_key != broker_key]
        routes.append(route)
        routes.sort(key=lambda item: int(item.metadata.get("priority", 100)))
        self._routes_by_normalized[normalized] = routes
        return route

    def routes_for(self, normalized_symbol: str) -> list[BrokerRoute]:
        return list(self._routes_by_normalized.get(_text(normalized_symbol), []))

    def primary_route(
        self,
        normalized_symbol: str,
        *,
        broker_key: str | None = None,
        exchange: str | None = None,
        account_id: str | None = None,
    ) -> BrokerRoute | None:
        routes = self.routes_for(normalized_symbol)
        for route in routes:
            if broker_key and route.broker_key != broker_key:
                continue
            if exchange and route.exchange != _text(exchange).lower():
                continue
            if account_id and route.account_id != account_id:
                continue
            return route
        return routes[0] if routes else None

    def resolve_payload_route(self, exchange: str, payload: Mapping[str, Any]) -> BrokerRoute | None:
        exchange_key = _text(exchange).lower()
        candidates = [
            payload.get("raw_symbol"),
            payload.get("product_id"),
            payload.get("symbol"),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            route = self._routes_by_exchange_symbol.get((exchange_key, _upper(candidate)))
            if route is not None:
                return route
        return None
