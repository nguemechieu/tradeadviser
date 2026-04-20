# Coinbase Derivatives Symbol Format - Quick Reference

## TL;DR - Critical Requirement

**ALL symbols for Coinbase derivatives MUST match this format:**

```
Perpetuals:  {BASE}-PERP       Example: BTC-PERP, ETH-PERP, SOL-PERP
Expiring:    {BASE}-YYYYMMDD   Example: BTC-20260419, ETH-20250321
```

## Quick Examples

### ✅ CORRECT Formats
```
BTC-PERP
ETH-PERP
SOL-PERP
AAPL-PERP
GLD-PERP
BTC-20260419
ETH-20250321
SOL-20260630
```

### ❌ WRONG Formats (Will Fail)
```
BTC              # Missing -PERP
BTC/USD:PERP     # Internal format, not for API
BTCPERP          # Missing hyphen
BTC-PERPETUAL    # Wrong suffix
BTC-2026419      # Wrong date format
BTC-20260413     # Date format must be YYYYMMDD
```

## Usage Patterns

### Validate a Symbol
```python
from sqs_desktop.src.broker.coinbase_futures import validate_derivative_symbol

try:
    base, contract_type = validate_derivative_symbol("BTC-PERP")
    print(f"✓ Valid: {base} - {contract_type}")
except Exception as e:
    print(f"✗ Invalid: {e}")
```

### Construct a Symbol
```python
from sqs_desktop.src.broker.coinbase_futures import (
    construct_perpetual_symbol,
    construct_expiring_symbol,
)

# Perpetual
symbol = construct_perpetual_symbol("BTC")  # BTC-PERP

# Expiring
from datetime import datetime
symbol = construct_expiring_symbol("ETH", datetime(2026, 4, 19))  # ETH-20260419
symbol = construct_expiring_symbol("SOL", "20250321")  # SOL-20250321
```

### Convert Between Formats

**When getting symbol from internal system:**
```python
from sqs_desktop.src.broker.coinbase_futures import convert_from_normalized_symbol

# Internal format (from other systems)
internal = "BTC/USD:PERP"

# Convert for Coinbase API
api_symbol = convert_from_normalized_symbol(internal)  # BTC-PERP
await client.create_order(symbol=api_symbol)
```

**When storing symbol internally:**
```python
from sqs_desktop.src.broker.coinbase_futures import convert_to_normalized_symbol

# Coinbase format (from API)
api_symbol = "BTC-PERP"

# Convert for internal storage
internal = convert_to_normalized_symbol(api_symbol)  # BTC/USD:PERP
```

### Check if Valid
```python
from sqs_desktop.src.broker.coinbase_futures import is_derivative_symbol

if is_derivative_symbol(user_input):
    print("✓ Valid symbol")
else:
    print("✗ Invalid symbol")
```

### Validate Multiple Symbols
```python
from sqs_desktop.src.broker.coinbase_futures import validate_symbols_list

results = validate_symbols_list(["BTC-PERP", "ETH-20260419", "INVALID"])
print(f"Valid: {results['valid']}")
print(f"Invalid: {results['invalid']}")
# Valid: ['BTC-PERP', 'ETH-20260419']
# Invalid: ['INVALID']
```

## Where This Applies

### ✅ Must Use Correct Format
- Creating orders with Coinbase API
- Fetching ticker data
- Subscribing to WebSocket streams
- Risk management checks
- Portfolio tracking
- API responses from Coinbase

### ℹ️  Internal Storage (Can Use Either Format)
- Database storage (convert to one standard format)
- Logging and debugging
- UI display (show user-friendly format)
- Configuration files

## Common Errors & Fixes

### Error: "Invalid symbol: BTC"
```python
# ❌ Wrong
symbol = "BTC"

# ✅ Correct
symbol = construct_perpetual_symbol("BTC")  # BTC-PERP
```

### Error: "Unknown Coinbase futures symbol: BTC/USD:PERP"
```python
# ❌ Wrong
symbol = "BTC/USD:PERP"  # Internal format

# ✅ Correct
symbol = convert_from_normalized_symbol("BTC/USD:PERP")  # BTC-PERP
```

### Error: "Date error in symbol"
```python
# ❌ Wrong
symbol = "BTC-20260419"  # Wrong format

# ✅ Correct
from datetime import datetime
symbol = construct_expiring_symbol("BTC", datetime(2026, 4, 19))  # BTC-20260419
```

## All Available Functions

```python
from sqs_desktop.src.broker.coinbase_futures import (
    # Validation
    validate_derivative_symbol,        # Returns (base, contract_type)
    is_derivative_symbol,              # Returns bool
    validate_symbols_list,             # Returns dict with valid/invalid
    
    # Construction
    construct_perpetual_symbol,        # BTC -> BTC-PERP
    construct_expiring_symbol,         # (ETH, date) -> ETH-20260419
    
    # Extraction
    extract_base_currency,             # BTC-PERP -> BTC
    extract_contract_type,             # BTC-PERP -> PERP
    
    # Conversion
    convert_from_normalized_symbol,    # BTC/USD:PERP -> BTC-PERP
    convert_to_normalized_symbol,      # BTC-PERP -> BTC/USD:PERP
    convert_symbols_list,              # Batch conversion
    
    # Exceptions
    CoinbaseDerivativeSymbolError,     # Error type
)
```

## Testing Your Symbols

```bash
# Run tests
pytest src/broker/coinbase_futures/test_symbol_validator.py -v

# Test specific functionality
pytest src/broker/coinbase_futures/test_symbol_validator.py::TestValidateDerivativeSymbol -v
```

## Reference

- **Full Documentation**: [SYMBOL_REQUIREMENTS.md](./SYMBOL_REQUIREMENTS.md)
- **Validator Module**: [symbol_validator.py](./symbol_validator.py)
- **Tests**: [test_symbol_validator.py](./test_symbol_validator.py)
- **Coinbase API Docs**: https://docs.cdp.coinbase.com/advanced-trade/docs/welcome

## Checklist

Before sending symbols to Coinbase API:
- [ ] Symbol format is `{BASE}-PERP` or `{BASE}-YYYYMMDD`
- [ ] Used `validate_derivative_symbol()` or `is_derivative_symbol()`
- [ ] Converted from internal format if needed using `convert_from_normalized_symbol()`
- [ ] Base currency is 1-10 alphanumeric characters
- [ ] No special characters except hyphen between base and type
- [ ] Date (if expiring) is valid calendar date in YYYYMMDD format

**Remember: Symbol format is critical for API communication. Always validate!**
