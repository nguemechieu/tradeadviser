"""Coinbase futures symbol normalization and validation.

IMPORTANT: When working with Coinbase derivatives, all symbols must match
the Coinbase derivative format:
  - Perpetuals: {BASE}-PERP (e.g., BTC-PERP, ETH-PERP, SOL-PERP)
  - Expiring:   {BASE}-{YYYYMMDD} (e.g., BTC-20260419)

While internally we normalize symbols to formats like BTC/USD:PERP for
consistency, when communicating with Coinbase API, symbols must be converted
to the {BASE}-PERP format.

See symbol_validator.py for conversion utilities between formats.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


ROOT_ALIASES = {
    "BIT": "BTC",
    "XBT": "BTC",
}

MONTH_CODES = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

PERPETUAL_MARKERS = {"PERP", "PERPETUAL"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _root_alias(value: Any) -> str:
    text = _text(value).upper()
    return ROOT_ALIASES.get(text, text)


def _extract_future_details(product: Mapping[str, Any]) -> Mapping[str, Any]:
    details = product.get("future_product_details")
    return details if isinstance(details, Mapping) else {}


def extract_product_id(product: Mapping[str, Any]) -> str:
    return _text(product.get("product_id") or product.get("id")).upper()


def extract_base_currency(product: Mapping[str, Any]) -> str:
    product_id = extract_product_id(product)
    details = _extract_future_details(product)
    for candidate in (
        product.get("base_currency_id"),
        product.get("base_currency"),
        details.get("base_currency_id"),
        details.get("base_currency"),
    ):
        text = _root_alias(candidate)
        if text:
            return text
    if product_id:
        return _root_alias(product_id.split("-", 1)[0])
    return ""


def extract_quote_currency(product: Mapping[str, Any]) -> str:
    details = _extract_future_details(product)
    for candidate in (
        product.get("quote_currency_id"),
        product.get("quote_currency"),
        details.get("quote_currency_id"),
        details.get("quote_currency"),
        product.get("settlement_currency_id"),
    ):
        text = _text(candidate).upper()
        if text:
            return text
    return ""


def extract_settlement_currency(product: Mapping[str, Any]) -> str:
    details = _extract_future_details(product)
    for candidate in (
        product.get("settlement_currency_id"),
        details.get("settlement_currency_id"),
        extract_quote_currency(product),
    ):
        text = _text(candidate).upper()
        if text:
            return text
    return "USD"


def extract_contract_expiry_type(product: Mapping[str, Any]) -> str:
    details = _extract_future_details(product)
    product_id = extract_product_id(product)
    for candidate in (
        details.get("contract_expiry_type"),
        product.get("contract_expiry_type"),
    ):
        text = _text(candidate).upper()
        if text:
            return text
    if any(marker in product_id for marker in PERPETUAL_MARKERS):
        return "PERPETUAL"
    return "EXPIRING"


def _parse_yyyymmdd(value: str) -> datetime | None:
    text = _text(value)
    if not re.fullmatch(r"\d{8}", text):
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_ddmonyy(value: str) -> datetime | None:
    match = re.fullmatch(r"(\d{2})([A-Z]{3})(\d{2})", _text(value).upper())
    if not match:
        return None
    day = int(match.group(1))
    month = MONTH_CODES.get(match.group(2))
    year = 2000 + int(match.group(3))
    if month is None:
        return None
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_expiry_datetime(product: Mapping[str, Any]) -> datetime | None:
    details = _extract_future_details(product)
    for candidate in (
        details.get("expiration_time"),
        product.get("expiration_time"),
        product.get("expiry_time"),
    ):
        text = _text(candidate)
        if not text:
            continue
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            continue

    product_id = extract_product_id(product)
    for token in product_id.split("-"):
        parsed = _parse_yyyymmdd(token) or _parse_ddmonyy(token)
        if parsed is not None:
            return parsed
    return None


def normalize_symbol(product: Mapping[str, Any]) -> str:
    product_id = extract_product_id(product)
    base = extract_base_currency(product)
    settlement_currency = extract_settlement_currency(product)
    expiry_type = extract_contract_expiry_type(product)

    if expiry_type == "PERPETUAL" or any(marker in product_id for marker in PERPETUAL_MARKERS):
        quote = settlement_currency or extract_quote_currency(product) or "USDC"
        return f"{base}/{quote}:PERP"

    expiry = extract_expiry_datetime(product)
    quote = extract_quote_currency(product) or settlement_currency or "USD"
    if expiry is not None:
        return f"{base}/{quote}:{expiry.date().isoformat()}"
    if product_id:
        return f"{base}/{quote}:{product_id}"
    return f"{base}/{quote}:UNKNOWN"


def normalize_lookup_symbol(symbol: Any) -> str:
    text = _text(symbol).upper()
    if not text:
        return ""
    return text.replace("_", "/")


def symbol_aliases(product: Mapping[str, Any], normalized_symbol: str | None = None) -> set[str]:
    normalized = normalize_lookup_symbol(normalized_symbol or normalize_symbol(product))
    product_id = extract_product_id(product)
    aliases = {alias for alias in {normalized, product_id, _text(product.get("display_name")).upper()} if alias}
    base = extract_base_currency(product)
    quote = extract_quote_currency(product) or extract_settlement_currency(product)
    if base and quote:
        aliases.add(f"{base}/{quote}")
    return {normalize_lookup_symbol(alias) for alias in aliases if alias}


def product_map_aliases(products: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    alias_map: dict[str, Mapping[str, Any]] = {}
    for product in products:
        normalized = normalize_symbol(product)
        for alias in symbol_aliases(product, normalized):
            alias_map[alias] = product
    return alias_map


__all__ = [
    "extract_base_currency",
    "extract_contract_expiry_type",
    "extract_expiry_datetime",
    "extract_product_id",
    "extract_quote_currency",
    "extract_settlement_currency",
    "normalize_lookup_symbol",
    "normalize_symbol",
    "product_map_aliases",
    "symbol_aliases",
]
