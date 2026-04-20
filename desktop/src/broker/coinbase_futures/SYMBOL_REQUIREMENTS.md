# Coinbase Derivatives Symbol Format Requirements

## Overview

When working with Coinbase derivatives (futures), **all symbols must match the Coinbase derivative symbol format**. This is a critical requirement to ensure proper communication with Coinbase API and data consistency.

### Coinbase Derivative Symbol Format

```
Perpetuals:  {BASE}-PERP       (e.g., BTC-PERP, ETH-PERP, SOL-PERP)
Expiring:    {BASE}-YYYYMMDD   (e.g., BTC-20260419, ETH-20250321)
```

Examples:
- ✅ Valid: `BTC-PERP`, `ETH-PERP`, `SOL-PERP`, `BTC-20260419`
- ❌ Invalid: `BTC/USD:PERP`, `BTC`, `BTCPERP`, `BTC_PERP`

## Why This Matters

1. **API Compliance** - Coinbase API expects symbols in this exact format
2. **Order Execution** - Orders will fail if symbols don't match expected format
3. **Data Consistency** - Risk management and monitoring require consistent symbol format
4. **Integration** - All downstream systems depend on correct symbol format

## Internal vs Coinbase Format

The system uses two symbol formats for different purposes:

| Context | Format | Example | Purpose |
|---------|--------|---------|---------|
| Internal/Normalized | `{BASE}/{QUOTE}:TYPE` | `BTC/USD:PERP` | Consistency across brokers |
| Coinbase API | `{BASE}-TYPE` | `BTC-PERP` | Coinbase API communication |

### Conversion Between Formats

```python
# Internal to Coinbase
"BTC/USD:PERP" → "BTC-PERP"
"ETH/USDC:20260419" → "ETH-20260419"

# Coinbase to Internal
"BTC-PERP" → "BTC/USD:PERP"
"SOL-20250321" → "SOL/USD:20250321"
```

## Symbol Validator Module

The `symbol_validator.py` module provides utilities for symbol validation and conversion.

### Validation

```python
from sqs_desktop.src.broker.coinbase_futures import (
    validate_derivative_symbol,
    is_derivative_symbol,
)

# Validate a symbol
try:
    base, contract_type = validate_derivative_symbol("BTC-PERP")
    print(f"✓ Valid: base={base}, type={contract_type}")
    # Output: ✓ Valid: base=BTC, type=PERP
except CoinbaseDerivativeSymbolError as e:
    print(f"✗ Invalid: {e}")

# Check if valid
if is_derivative_symbol("BTC-PERP"):
    print("✓ Valid symbol")
else:
    print("✗ Invalid symbol")

# Validate multiple symbols
results = validate_symbols_list(["BTC-PERP", "ETH-20260419", "INVALID"])
print(results)
# {
#   "valid": ["BTC-PERP", "ETH-20260419"],
#   "invalid": ["INVALID"],
#   "errors": {"INVALID": "Symbol 'INVALID' doesn't match..."}
# }
```

### Construction

```python
from sqs_desktop.src.broker.coinbase_futures import (
    construct_perpetual_symbol,
    construct_expiring_symbol,
)

# Construct perpetual symbol
symbol = construct_perpetual_symbol("BTC")
print(symbol)  # BTC-PERP

# Construct expiring symbol
from datetime import datetime
symbol = construct_expiring_symbol("ETH", datetime(2026, 4, 19))
print(symbol)  # ETH-20260419

# From date string
symbol = construct_expiring_symbol("SOL", "20250321")
print(symbol)  # SOL-20250321
```

### Extraction

```python
from sqs_desktop.src.broker.coinbase_futures import (
    extract_base_currency,
    extract_contract_type,
)

# Extract components
base = extract_base_currency("BTC-PERP")
print(base)  # BTC

contract = extract_contract_type("ETH-20260419")
print(contract)  # 20260419
```

### Format Conversion

```python
from sqs_desktop.src.broker.coinbase_futures import (
    convert_from_normalized_symbol,
    convert_to_normalized_symbol,
)

# Internal format to Coinbase format
coinbase_symbol = convert_from_normalized_symbol("BTC/USD:PERP")
print(coinbase_symbol)  # BTC-PERP

# Coinbase format to internal format
internal_symbol = convert_to_normalized_symbol("ETH-PERP", quote_currency="USDC")
print(internal_symbol)  # ETH/USDC:PERP

# Batch conversion
results = convert_symbols_list(
    ["BTC/USD:PERP", "ETH/USDC:20260419"],
    from_format="normalized"
)
print(results)
# {
#   "converted": ["BTC-PERP", "ETH-20260419"],
#   "failed": [],
#   "errors": {}
# }
```

## Usage Guidelines

### ✅ DO

1. **Validate symbols before sending to Coinbase API**
   ```python
   symbol = user_input.strip().upper()
   try:
       validate_derivative_symbol(symbol)
       # Send to Coinbase API
   except CoinbaseDerivativeSymbolError:
       # Handle invalid symbol
   ```

2. **Use conversion functions for format changes**
   ```python
   # When converting from internal format
   api_symbol = convert_from_normalized_symbol(internal_symbol)
   await client.create_order(symbol=api_symbol)
   ```

3. **Use constructors for building symbols**
   ```python
   symbol = construct_perpetual_symbol("BTC")  # BTC-PERP
   ```

### ❌ DON'T

1. **Don't assume symbol format** - Always validate
   ```python
   # Bad
   api.create_order(symbol="BTC")  # Might not be valid
   
   # Good
   symbol = construct_perpetual_symbol("BTC")
   api.create_order(symbol=symbol)
   ```

2. **Don't mix format conventions** - Stick to one format per context
   ```python
   # Bad - mixing internal and Coinbase formats
   symbols = ["BTC-PERP", "ETH/USD:20260419"]
   
   # Good - consistent format
   symbols = ["BTC-PERP", "ETH-20260419"]  # All Coinbase format
   ```

3. **Don't manually concatenate symbols** - Use provided functions
   ```python
   # Bad
   symbol = f"{base}-PERP"  # Assumes correct format
   
   # Good
   symbol = construct_perpetual_symbol(base)  # Validated construction
   ```

## Symbol Matching Requirement

### In Execution Module

```python
# sqs_desktop/src/broker/coinbase_futures/execution.py

async def place_order(self, symbol: str, size: float, price: float):
    """Place an order with validated symbol."""
    
    # ✅ REQUIRED: Validate symbol format
    base, contract_type = validate_derivative_symbol(symbol)
    
    # Convert to Coinbase format if needed
    if "/" in symbol:
        symbol = convert_from_normalized_symbol(symbol)
    
    # Now safe to use with API
    product = await self.products.resolve_product(symbol)
    await self.client.place_order(
        product_id=product.product_id,
        symbol=symbol
    )
```

### In Product Resolution

```python
# sqs_desktop/src/broker/coinbase_futures/products.py

async def resolve_product(self, symbol: str):
    """Resolve product with symbol format validation."""
    
    # Ensure symbol is in correct format
    if "/" in symbol:
        symbol = convert_from_normalized_symbol(symbol)
    
    # Validate
    try:
        validate_derivative_symbol(symbol)
    except CoinbaseDerivativeSymbolError as e:
        raise KeyError(f"Invalid symbol format: {e}")
    
    # Proceed with resolution
    return await self._resolve(symbol)
```

## Error Handling

```python
from sqs_desktop.src.broker.coinbase_futures import (
    validate_derivative_symbol,
    CoinbaseDerivativeSymbolError,
)

def handle_symbol_input(user_symbol: str) -> str:
    """Process and validate user symbol input."""
    
    symbol = str(user_symbol or "").strip().upper()
    
    try:
        # This validates AND returns parsed components
        base, contract_type = validate_derivative_symbol(symbol)
        return symbol
        
    except CoinbaseDerivativeSymbolError as e:
        # Log and re-raise with context
        logger.error(f"Invalid symbol '{user_symbol}': {e}")
        raise ValueError(
            f"Invalid derivative symbol. Expected BTC-PERP or BTC-20260419, got '{symbol}'"
        )
```

## Common Symbol Examples

### Perpetuals
- `BTC-PERP` - Bitcoin perpetual
- `ETH-PERP` - Ethereum perpetual
- `SOL-PERP` - Solana perpetual
- `AAPL-PERP` - Apple perpetual (if available)
- `GLD-PERP` - Gold perpetual (if available)

### Expiring Contracts (Example dates in 2026)
- `BTC-20260419` - Bitcoin expiring April 19, 2026
- `ETH-20250321` - Ethereum expiring March 21, 2025
- `SOL-20260630` - Solana expiring June 30, 2026

## Checklist for Implementation

- [ ] Import symbol validator functions
- [ ] Validate all user-provided symbols before API calls
- [ ] Convert internal format symbols to Coinbase format before API calls
- [ ] Use constructors to build symbols instead of string concatenation
- [ ] Add error handling for invalid symbols
- [ ] Document symbol format in code comments
- [ ] Add unit tests for symbol validation
- [ ] Update existing code that handles symbols
- [ ] Review risk management code for symbol format assumptions
- [ ] Add monitoring/alerts for invalid symbol formats

## Testing

```python
# Test validation
from sqs_desktop.src.broker.coinbase_futures.symbol_validator import (
    validate_derivative_symbol,
    CoinbaseDerivativeSymbolError,
)

def test_perpetual_symbols():
    assert validate_derivative_symbol("BTC-PERP") == ("BTC", "PERP")
    assert validate_derivative_symbol("ETH-PERP") == ("ETH", "PERP")

def test_expiring_symbols():
    assert validate_derivative_symbol("BTC-20260419") == ("BTC", "20260419")
    assert validate_derivative_symbol("SOL-20250321") == ("SOL", "20250321")

def test_invalid_symbols():
    with pytest.raises(CoinbaseDerivativeSymbolError):
        validate_derivative_symbol("BTC")  # Missing -PERP
    with pytest.raises(CoinbaseDerivativeSymbolError):
        validate_derivative_symbol("BTC-PERP-USD")  # Extra component
    with pytest.raises(CoinbaseDerivativeSymbolError):
        validate_derivative_symbol("BTC/USD:PERP")  # Wrong format
```

## References

- [Coinbase Advanced Trade API Docs](https://docs.cdp.coinbase.com/advanced-trade/docs/welcome)
- [Symbol Validator Module](./symbol_validator.py)
- [Normalizer Module](./normalizer.py)
- Execution Module: `./execution.py`
- Products Module: `./products.py`

## Summary

**Critical Rule**: When working with Coinbase derivatives, **all symbols must match the format `{BASE}-PERP` for perpetuals or `{BASE}-YYYYMMDD` for expiring contracts**.

Use the provided `symbol_validator` module to:
1. ✅ Validate symbols
2. ✅ Convert between formats
3. ✅ Construct symbols safely
4. ✅ Extract symbol components

This ensures compliance with Coinbase API and maintains data consistency across the system.
