"""Shared utility functions for the TradeAdviser system."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float with default fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value or default
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int with default fallback.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Int value or default
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def normalized_text(*values: Any) -> str:
    """Get first non-empty normalized string from values.
    
    Args:
        *values: Values to check
        
    Returns:
        First non-empty trimmed string or empty string
    """
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value between min and max bounds.
    
    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        Clamped value
    """
    return max(min_val, min(max_val, value))


def normalize_fraction(value: Any, default: float = 0.0) -> float:
    """Normalize fraction/percentage to 0-1 range.
    
    Args:
        value: Value to normalize (0-1 or 0-100)
        default: Default if conversion fails
        
    Returns:
        Normalized value in 0-1 range
    """
    normalized = safe_float(value, default)
    normalized = clamp(normalized, 0.0, 5.0)
    if normalized > 1.0:
        normalized = normalized / 100.0
    return clamp(normalized, 0.0, 1.0)


def normalize_exposure_limit(value: Any, default: float = 1.0) -> float:
    """Normalize exposure limit (0-500%).
    
    Args:
        value: Exposure limit value
        default: Default if conversion fails
        
    Returns:
        Normalized exposure limit
    """
    normalized = safe_float(value, default)
    if normalized < 0:
        return 0.0
    if normalized > 5.0:
        normalized = normalized / 100.0
    return normalized


def is_native_contract_symbol(symbol: Any) -> bool:
    """Check if symbol looks like a native futures contract symbol.
    
    Args:
        symbol: Symbol to check
        
    Returns:
        True if symbol matches contract patterns
    """
    text = str(symbol or "").strip().upper()
    if not text or "/" in text or "_" in text:
        return False
    if "PERP" in text:
        return True
    return bool(
        re.fullmatch(r"[A-Z0-9]+-\d{2}[A-Z]{3}\d{2}-[A-Z0-9]+", text)
        or re.fullmatch(r"[A-Z0-9]+-[A-Z0-9]+-\d{8}", text)
    )


def normalize_symbol_text(symbol: Any) -> str:
    """Normalize symbol to standard format.
    
    Args:
        symbol: Symbol to normalize
        
    Returns:
        Normalized symbol
    """
    text = str(symbol or "").strip().upper()
    if is_native_contract_symbol(text):
        return text
    return text.replace("_", "/").replace("-", "/")


def normalize_symbol_sequence(symbols: Any) -> list[str]:
    """Normalize sequence of symbols to unique list.
    
    Args:
        symbols: String, dict, iterable of symbols
        
    Returns:
        List of normalized unique symbols
    """
    if symbols is None:
        return []
    if isinstance(symbols, str):
        raw_values = [item.strip() for item in symbols.split(",") if item.strip()]
    elif isinstance(symbols, Mapping):
        raw_values = list(symbols.keys())
    else:
        raw_values = list(symbols or [])

    normalized = []
    for symbol in raw_values:
        value = normalize_symbol_text(symbol)
        if value and value not in normalized:
            normalized.append(value)
    return normalized


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length with suffix.
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format value as percentage string.
    
    Args:
        value: Value to format (0-1)
        decimals: Decimal places
        
    Returns:
        Formatted percentage string
    """
    return f"{value * 100:.{decimals}f}%"


def format_currency(value: float, currency: str = "$", decimals: int = 2) -> str:
    """Format value as currency string.
    
    Args:
        value: Value to format
        currency: Currency symbol
        decimals: Decimal places
        
    Returns:
        Formatted currency string
    """
    return f"{currency}{value:,.{decimals}f}"


def merge_dicts(*dicts: dict[str, Any]) -> dict[str, Any]:
    """Merge multiple dictionaries, later ones override earlier ones.
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result


def get_nested(obj: Any, path: str, default: Any = None) -> Any:
    """Get nested value from object using dot notation.
    
    Args:
        obj: Object to get value from
        path: Dot-separated path (e.g., 'a.b.c')
        default: Default value if not found
        
    Returns:
        Value at path or default
    """
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return default
    return current


def set_nested(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set nested value in dictionary using dot notation.
    
    Args:
        obj: Dictionary to set value in
        path: Dot-separated path (e.g., 'a.b.c')
        value: Value to set
    """
    parts = path.split(".")
    current = obj
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value
