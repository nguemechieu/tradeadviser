# Risk Management: Modifying TP/SL and Trailing Stops

## Overview

When you have **open orders or positions**, you can now dynamically modify their **Take Profit (TP)** and **Stop Loss (SL)** levels without closing the position. You can also activate a **trailing stop** to protect profits automatically.

---

## Features

### 1. **Modify Take Profit (TP)**
- **What**: Adjust the profit-taking price on an open position
- **When**: Anytime the position is open
- **How**: 
  - Right-click on the position in the positions list
  - Select **"Modify Take Profit"**
  - Enter the new TP price
  - Confirm

**Validation**:
- For **long positions**: New TP must be **above** current price
- For **short positions**: New TP must be **below** current price
- Minimum distance: 0.1% from current price

### 2. **Modify Stop Loss (SL)**
- **What**: Adjust the loss-limiting price on an open position
- **When**: Anytime the position is open
- **How**:
  - Right-click on the position in the positions list
  - Select **"Modify Stop Loss"**
  - Enter the new SL price
  - Confirm

**Validation**:
- For **long positions**: New SL must be **below** current price
- For **short positions**: New SL must be **above** current price
- Minimum distance: 0.1% from current price

### 3. **Activate Trailing Stop**
- **What**: Automatically adjust your SL upward (for long) or downward (for short) as price moves in your favor
- **When**: Anytime after establishing the position
- **How**:
  - Right-click on the position in the positions list
  - Select **"Enable Trailing Stop"**
  - Choose trailing method:
    - **Distance**: Fixed price distance (e.g., $100 trailing distance)
    - **Percentage**: Percentage-based distance (e.g., 2.5% trailing)
  - Confirm

**How it works**:
- When price moves favorably, the trailing SL automatically moves with it
- The SL **never** moves closer to breakeven
- Once price reverses and hits the trailing SL, the position closes automatically
- Helps lock in profits while staying in winning trades

---

## Examples

### Example 1: Long Position with Trailing Stop

```
Current State:
- Entry: BTC @ $45,000
- Current Price: $46,500
- Position: +0.5 BTC

Action: Activate 2% Trailing Stop
- Trailing SL: $45,570 (2% below $46,500)

Price Movement Scenarios:
1. Price rises to $48,000
   → Trailing SL moves to $47,040 (2% below new price)
   
2. Price rises to $49,000
   → Trailing SL moves to $48,020 (2% below new price)
   
3. Price falls back to $48,000
   → Trailing SL stays at $48,020 (never moves closer)
   
4. Price drops below $48,020
   → Position automatically closes with ~6.7% profit
```

### Example 2: Modify TP on Short Position

```
Current State:
- Entry: ETH short @ $2,500
- Current Price: $2,480
- Position: -2 ETH

Action: Modify Take Profit to $2,200
- TP previously: $2,100 (too aggressive)
- TP now: $2,200 (allows for more profit)
- Change: +$100 more risk, but position still profitable

The position will auto-close if price falls to $2,200
```

---

## Status Display

In the **Positions Table**, you'll see risk management info displayed as:

```
SL: 44,500 | TP: 48,000 | Trail: ±1,000
```

Or if using percentage:
```
SL: 44,500 | TP: 48,000 | Trail: ±2.5%
```

Symbols:
- **SL**: Stop Loss price
- **TP**: Take Profit price
- **Trail**: Active trailing stop (±distance or ±percent)

---

## Broker Support

**Note**: Not all brokers support TP/SL modification and trailing stops. 

**Full support**:
- ✅ **Coinbase** (with advanced orders)
- ✅ **IBKR** (Interactive Brokers)
- ✅ **Binance**

**Limited support**:
- ⚠️ **Alpaca** (SL/TP via dedicated orders)
- ⚠️ **Oanda** (manual SL/TP)

**Not supported**:
- ❌ **Paper** (simulated only)
- ❌ **Stellar** (no derivatives)

If your broker doesn't support it, you'll see an error message.

---

## Safety Features

### Validation Checks
✓ Stop Loss must be **away** from entry (not overlapping TP)
✓ Take Profit must be **profitable** (opposite side of SL)
✓ Trailing distance must be **reasonable** (0.1% - 50%)
✓ Distance from current price is **verified** before sending

### Audit Trail
- Every modification is **logged**
- UI shows confirmation of success/failure
- Previous values are **stored** in metadata

---

## Programmatic Usage

### From Python Code

```python
from execution.risk_management import RiskManagementEngine
from contracts.execution import ModifyOrderTakeProfitCommand
from contracts.enums import VenueKind

# Initialize
engine = RiskManagementEngine(broker=my_broker)

# Create modification command
command = ModifyOrderTakeProfitCommand(
    order_id="ORDER_123",
    symbol="BTC/USDT",
    venue=VenueKind.COINBASE,
    new_take_profit_price=50000,
    reason="Manual adjustment"
)

# Apply modification (current price = 46,000)
result = await engine.modify_position_take_profit(command, current_price=46000)

# Result:
# {
#     "success": True,
#     "message": "Take profit modified to 50000",
#     "position_id": "ORDER_123",
#     "new_take_profit": 50000
# }
```

### UI Integration

```python
from ui.components.risk_management_ui import RiskManagementUI

ui = RiskManagementUI(risk_manager=engine, controller=self.controller)

# User modifies TP
result = await ui.modify_take_profit(
    order_id="ORDER_123",
    symbol="BTC/USDT",
    venue=VenueKind.COINBASE,
    new_tp=50000,
    current_price=46000
)

# Validate trailing stop input
is_valid, error = ui.validate_modification_input(
    current_price=46000,
    new_price=45000,
    modification_type="sl",
    side="buy"
)

# Display risk info
risk_info = ui.get_position_risk_info(position)
display_text = ui.format_risk_level_display(position)
print(display_text)  # "SL: 44,500 | TP: 48,000 | Trail: ±2.5%"
```

---

## Best Practices

1. **Set SL First**: Always set stop loss before taking profit to limit downside
2. **Use Trailing Stops**: For trending markets, trailing stops help maximize wins
3. **Avoid Overlaps**: SL and TP should never be on the same side of entry
4. **Monitor Distance**: Keep at least 0.5% distance from current price for SL
5. **Test Broker**: Verify your broker supports modifications before live trading

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Broker not initialized" | Engine missing broker reference | Ensure broker is passed to RiskManagementEngine |
| "Broker does not support..." | Broker SDK doesn't have the method | Check supported brokers list above |
| "Stop loss too close" | Distance < 0.1% from current | Increase distance to 1%+ |
| "Position price validation failed" | SL/TP on wrong side | Long SL below price, TP above price |
| Modification succeeds but doesn't apply | Broker requires explicit order | Check broker API docs for order syntax |

---

## Contract Structure

### PositionSnapshot (Portfolio)
```python
class PositionSnapshot:
    position_id: str
    symbol: str
    quantity: float
    # Risk management fields:
    stop_loss: float | None
    take_profit: float | None
    trailing_stop_enabled: bool
    trailing_stop_distance: float | None
    trailing_stop_percent: float | None
```

### Commands
- `ModifyPositionStopLossCommand` - Update SL
- `ModifyPositionTakeProfitCommand` - Update TP
- `EnableTrailingStopCommand` - Activate trailing

---

## See Also

- [Execution Management](../execution/README.md)
- [Portfolio Management](../portfolio/README.md)
- [Broker Adapters](../broker/README.md)
