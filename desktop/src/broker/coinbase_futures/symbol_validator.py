"""Coinbase derivatives symbol validation and conversion.

When working with Coinbase derivatives, all symbols must match the derivative
symbol format:
  - Perpetuals: {BASE}-PERP (e.g., BTC-PERP, ETH-PERP, SOL-PERP)
  - Expiring:   {BASE}-{EXPIRY_DATE} (e.g., BTC-20260419)

This module provides validation and conversion utilities to ensure symbols
conform to Coinbase's derivative format requirements.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Tuple


# Coinbase derivative symbol patterns
PERPETUAL_PATTERN = re.compile(r"^([A-Z0-9]{1,10})-PERP$")  # BTC-PERP
EXPIRING_PATTERN = re.compile(r"^([A-Z0-9]{1,10})-(\d{8})$")  # BTC-20260419


class CoinbaseDerivativeSymbolError(ValueError):
    """Raised when a symbol doesn't match Coinbase derivative format."""
    pass


def validate_derivative_symbol(symbol: str) -> Tuple[str, str]:
    """Validate and parse a Coinbase derivative symbol.
    
    Args:
        symbol: Symbol to validate (e.g., "BTC-PERP", "BTC-20260419")
        
    Returns:
        Tuple of (base_currency, contract_type) where contract_type is
        either "PERP" or an ISO date string (YYYYMMDD)
        
    Raises:
        CoinbaseDerivativeSymbolError: If symbol doesn't match derivative format
        
    Examples:
        >>> validate_derivative_symbol("BTC-PERP")
        ("BTC", "PERP")
        
        >>> validate_derivative_symbol("ETH-20260419")
        ("ETH", "20260419")
        
        >>> validate_derivative_symbol("BTC/USD:PERP")  # Wrong format
        CoinbaseDerivativeSymbolError: ...
    """
    symbol = str(symbol or "").strip().upper()
    
    # Try perpetual format
    perp_match = PERPETUAL_PATTERN.match(symbol)
    if perp_match:
        return perp_match.group(1), "PERP"
    
    # Try expiring format
    expiring_match = EXPIRING_PATTERN.match(symbol)
    if expiring_match:
        base = expiring_match.group(1)
        date_str = expiring_match.group(2)
        
        # Validate date format
        try:
            datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            raise CoinbaseDerivativeSymbolError(
                f"Invalid expiry date in symbol '{symbol}': {date_str} "
                "(expected YYYYMMDD format)"
            )
        
        return base, date_str
    
    raise CoinbaseDerivativeSymbolError(
        f"Symbol '{symbol}' doesn't match Coinbase derivative format. "
        f"Expected format: {{BASE}}-PERP or {{BASE}}-YYYYMMDD "
        f"(examples: BTC-PERP, ETH-20260419)"
    )


def is_derivative_symbol(symbol: str) -> bool:
    """Check if symbol is a valid Coinbase derivative symbol.
    
    Args:
        symbol: Symbol to check
        
    Returns:
        True if symbol matches derivative format, False otherwise
    """
    try:
        validate_derivative_symbol(symbol)
        return True
    except CoinbaseDerivativeSymbolError:
        return False


def construct_perpetual_symbol(base_currency: str) -> str:
    """Construct a perpetual derivative symbol.
    
    Args:
        base_currency: Base currency (e.g., "BTC", "ETH")
        
    Returns:
        Perpetual symbol (e.g., "BTC-PERP")
        
    Raises:
        ValueError: If base_currency is invalid
        
    Examples:
        >>> construct_perpetual_symbol("BTC")
        "BTC-PERP"
        
        >>> construct_perpetual_symbol("btc")  # Case-insensitive
        "BTC-PERP"
    """
    base = str(base_currency or "").strip().upper()
    
    if not base:
        raise ValueError("base_currency cannot be empty")
    
    if not re.match(r"^[A-Z0-9]{1,10}$", base):
        raise ValueError(
            f"Invalid base_currency '{base}': must be 1-10 alphanumeric characters"
        )
    
    return f"{base}-PERP"


def construct_expiring_symbol(base_currency: str, expiry_date: datetime | str) -> str:
    """Construct an expiring derivative symbol.
    
    Args:
        base_currency: Base currency (e.g., "BTC", "ETH")
        expiry_date: Expiry date as datetime or YYYYMMDD string
        
    Returns:
        Expiring symbol (e.g., "BTC-20260419")
        
    Raises:
        ValueError: If base_currency or expiry_date is invalid
        
    Examples:
        >>> construct_expiring_symbol("BTC", "20260419")
        "BTC-20260419"
        
        >>> from datetime import datetime
        >>> construct_expiring_symbol("ETH", datetime(2026, 4, 19))
        "ETH-20260419"
    """
    base = str(base_currency or "").strip().upper()
    
    if not base:
        raise ValueError("base_currency cannot be empty")
    
    if not re.match(r"^[A-Z0-9]{1,10}$", base):
        raise ValueError(
            f"Invalid base_currency '{base}': must be 1-10 alphanumeric characters"
        )
    
    if isinstance(expiry_date, datetime):
        date_str = expiry_date.strftime("%Y%m%d")
    else:
        date_str = str(expiry_date or "").strip()
    
    if not re.match(r"^\d{8}$", date_str):
        raise ValueError(
            f"Invalid expiry_date '{date_str}': must be YYYYMMDD format"
        )
    
    # Validate it's a valid date
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        raise ValueError(
            f"Invalid expiry_date '{date_str}': not a valid calendar date"
        )
    
    return f"{base}-{date_str}"


def extract_base_currency(symbol: str) -> str:
    """Extract base currency from derivative symbol.
    
    Args:
        symbol: Derivative symbol (e.g., "BTC-PERP", "ETH-20260419")
        
    Returns:
        Base currency (e.g., "BTC", "ETH")
        
    Raises:
        CoinbaseDerivativeSymbolError: If symbol is invalid
        
    Examples:
        >>> extract_base_currency("BTC-PERP")
        "BTC"
        
        >>> extract_base_currency("ETH-20260419")
        "ETH"
    """
    base, _ = validate_derivative_symbol(symbol)
    return base


def extract_contract_type(symbol: str) -> str:
    """Extract contract type from derivative symbol.
    
    Args:
        symbol: Derivative symbol (e.g., "BTC-PERP", "ETH-20260419")
        
    Returns:
        "PERP" for perpetuals, or YYYYMMDD expiry date for expiring contracts
        
    Raises:
        CoinbaseDerivativeSymbolError: If symbol is invalid
        
    Examples:
        >>> extract_contract_type("BTC-PERP")
        "PERP"
        
        >>> extract_contract_type("ETH-20260419")
        "20260419"
    """
    _, contract_type = validate_derivative_symbol(symbol)
    return contract_type


def convert_from_normalized_symbol(normalized_symbol: str) -> str:
    """Convert from internal normalized format to Coinbase derivative format.
    
    Internal format: BTC/USD:PERP or BTC/USD:20260419
    Coinbase format: BTC-PERP or BTC-20260419
    
    Args:
        normalized_symbol: Symbol in internal normalized format
        
    Returns:
        Symbol in Coinbase derivative format
        
    Raises:
        ValueError: If symbol cannot be converted
        
    Examples:
        >>> convert_from_normalized_symbol("BTC/USD:PERP")
        "BTC-PERP"
        
        >>> convert_from_normalized_symbol("ETH/USDC:20260419")
        "ETH-20260419"
    """
    normalized = str(normalized_symbol or "").strip().upper()
    
    # Match pattern: {BASE}/{QUOTE}:{CONTRACT_TYPE}
    match = re.match(r"^([A-Z0-9]+)/[A-Z]+:(.+)$", normalized)
    if not match:
        raise ValueError(
            f"Cannot convert '{normalized}' from normalized format. "
            f"Expected format: {{BASE}}/{{QUOTE}}:{{TYPE}} (example: BTC/USD:PERP)"
        )
    
    base = match.group(1)
    contract_type = match.group(2)
    
    if contract_type == "PERP":
        return construct_perpetual_symbol(base)
    elif re.match(r"^\d{8}$", contract_type):
        return construct_expiring_symbol(base, contract_type)
    else:
        raise ValueError(
            f"Unknown contract type '{contract_type}' in symbol '{normalized}'"
        )


def convert_to_normalized_symbol(
    derivative_symbol: str,
    quote_currency: str = "USD"
) -> str:
    """Convert from Coinbase derivative format to internal normalized format.
    
    Coinbase format: BTC-PERP or BTC-20260419
    Internal format: BTC/USD:PERP or BTC/USD:20260419
    
    Args:
        derivative_symbol: Symbol in Coinbase derivative format
        quote_currency: Quote currency to use in normalized format (default: USD)
        
    Returns:
        Symbol in internal normalized format
        
    Raises:
        CoinbaseDerivativeSymbolError: If symbol is invalid
        
    Examples:
        >>> convert_to_normalized_symbol("BTC-PERP")
        "BTC/USD:PERP"
        
        >>> convert_to_normalized_symbol("ETH-20260419", quote_currency="USDC")
        "ETH/USDC:20260419"
    """
    base, contract_type = validate_derivative_symbol(derivative_symbol)
    quote = str(quote_currency or "USD").strip().upper()
    
    return f"{base}/{quote}:{contract_type}"


# ============================================================================
# Batch operations
# ============================================================================

def validate_symbols_list(symbols: list[str]) -> dict[str, Any]:
    """Validate a list of derivative symbols.
    
    Args:
        symbols: List of symbols to validate
        
    Returns:
        Dictionary with validation results:
        {
            "valid": list[str],      # Valid symbols
            "invalid": list[str],    # Invalid symbols
            "errors": dict[str, str], # Error messages for invalid symbols
        }
        
    Examples:
        >>> validate_symbols_list(["BTC-PERP", "ETH-20260419", "INVALID"])
        {
            "valid": ["BTC-PERP", "ETH-20260419"],
            "invalid": ["INVALID"],
            "errors": {"INVALID": "Symbol 'INVALID' doesn't match ..."}
        }
    """
    results = {
        "valid": [],
        "invalid": [],
        "errors": {},
    }
    
    for symbol in symbols:
        try:
            validate_derivative_symbol(symbol)
            results["valid"].append(symbol)
        except CoinbaseDerivativeSymbolError as e:
            results["invalid"].append(symbol)
            results["errors"][symbol] = str(e)
    
    return results


def convert_symbols_list(
    symbols: list[str],
    from_format: str = "normalized",
    quote_currency: str = "USD"
) -> dict[str, Any]:
    """Convert a list of symbols between formats.
    
    Args:
        symbols: List of symbols to convert
        from_format: "normalized" or "derivative"
        quote_currency: Quote currency (only used if from_format="derivative")
        
    Returns:
        Dictionary with conversion results:
        {
            "converted": list[str],   # Successfully converted symbols
            "failed": list[str],      # Failed to convert
            "errors": dict[str, str], # Error messages for failed conversions
        }
    """
    results = {
        "converted": [],
        "failed": [],
        "errors": {},
    }
    
    converter = (
        convert_from_normalized_symbol
        if from_format.lower() == "normalized"
        else convert_to_normalized_symbol
    )
    
    for symbol in symbols:
        try:
            if from_format.lower() == "derivative":
                converted = converter(symbol, quote_currency=quote_currency)
            else:
                converted = converter(symbol)
            results["converted"].append(converted)
        except (ValueError, CoinbaseDerivativeSymbolError) as e:
            results["failed"].append(symbol)
            results["errors"][symbol] = str(e)
    
    return results
