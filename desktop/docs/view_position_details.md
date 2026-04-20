# View Position Details Feature

## Overview

When you have **open positions**, you can now click the **"View"** button to see detailed position information in a comprehensive dialog, similar to Coinbase's position viewer. This gives you quick access to all position metrics and close options in one place.

---

## Features

### 1. **Position Details Display**
Click the **"View"** button on any position to see:

**Basic Information**
- **Symbol**: Trading pair (e.g., BTC/USDT)
- **Side**: LONG or SHORT
- **Amount**: Quantity of the position
- **Venue**: Exchange where position is held
- **Notional Value**: Total position value at current price

**Entry & Market Price**
- **Avg Entry**: Average entry price
- **Current Price**: Live market price (Mark price)

**Profit & Loss**
- **Unrealized P&L**: Current profit or loss (green/red)
- **Funding**: Accumulated funding costs (for perpetuals)

**Risk Information** (if applicable)
- **Intraday Liquidation Price**: Estimated liquidation level for day traders
- **Overnight Liquidation Price**: Estimated overnight liquidation level
- **Expiry**: Position expiration date (if applicable)

**Risk Management** (if configured)
- **Take Profit**: Current TP level (if set)
- **Stop Loss**: Current SL level (if set)
- **Trailing Stop**: Trailing stop configuration (if enabled)

---

## User Interface

### Positions Table

The **Positions** tab now shows two action buttons per position:

```
┌─────────┬──────┬────────┬────────┬────────┬───────┬──────┬────────┬───────┐
│ Symbol  │ Side │ Amount │ Entry  │ Mark   │ Value │ P/L  │ View   │ Close │
├─────────┼──────┼────────┼────────┼────────┼───────┼──────┼────────┼───────┤
│ BTC/USD │ LONG │ 1      │ 75,845 │ 76,015 │ 76015 │ 1.70 │ [View] │ [→]   │
│ ETH/USD │ SHORT│ 5      │ 2,500  │ 2,480  │ 12400 │ 100  │ [View] │ [→]   │
└─────────┴──────┴────────┴────────┴────────┴───────┴──────┴────────┴───────┘
```

- **View Button**: Opens detailed position dialog
- **Close Button** (→): Quick close (market order)

### Position Details Dialog

When you click "View", a dialog appears with:

1. **Header** showing symbol and side
2. **Comprehensive Details** in organized sections
3. **Risk Management Info** (if configured)
4. **Action Buttons** at the bottom

---

## Example: Viewing a Position

### Step 1: Click View Button
Open the Positions tab, find your position, click the "View" button.

### Step 2: Position Details Dialog Opens

```
┌──────────────────────────────────────────────────┐
│ Position Details - BTC/PERP                      │
├──────────────────────────────────────────────────┤
│ BTC/PERP                            [LONG]       │
│                                                  │
│ Position Details                                 │
│ ─────────────────────────────────────────────────│
│ Side:                     LONG (1)                │
│ Amount:                   1.00                    │
│ Venue:                    COINBASE                │
│ Notional Value:           $76,015.00             │
│ Avg Entry:                $75,845.00             │
│ Current Price:            $76,015.00             │
│ Unrealized P&L:           $1.70  (↑)             │
│ Funding:                  -$0.03                 │
│                                                  │
│ Liquidation Prices                              │
│ ─────────────────────────────────────────────────│
│ Intraday (est.):          $44,114.00            │
│ Overnight (est.):         $55,445.00            │
│ Expiry:                   12/20/30               │
│                                                  │
│ Risk Management                                  │
│ ─────────────────────────────────────────────────│
│ Take Profit:              $80,000.00             │
│ Stop Loss:                $74,000.00             │
│ Trailing Stop:            ±2.5%                  │
│                                                  │
│ [Close Position] [Close All] [Done]             │
└──────────────────────────────────────────────────┘
```

### Step 3: Take Action

From the dialog, you can:

**Close This Position**
- Click "Close Position" to market close only this position
- You'll be asked to confirm
- A market order will be placed

**Close All Positions**
- Click "Close All Positions" to close all open positions
- You'll be asked to confirm
- Market orders for all positions will be placed

**Close Dialog**
- Click "Done" to close the dialog without taking action

---

## Position Details Explained

### Notional Value
= Amount × Current Price

**Example**: 1 BTC × $76,015 = $76,015 notional value

### Unrealized P&L
= (Current Price - Entry Price) × Amount × Direction

**For LONG**:
```
= ($76,015 - $75,845) × 1 × (+1) = +$170
```

**For SHORT**:
```
= ($76,015 - $75,845) × 1 × (-1) = -$170
```

### Funding (Perpetuals Only)
Accumulated funding fees paid:
- **Positive**: You've collected fees (good for shorts during bull markets)
- **Negative**: You've paid fees (common for longs in bull markets)

### Liquidation Prices
- **Intraday**: Where position liquidates if you're a day trader (higher margin)
- **Overnight**: Where position liquidates with standard overnight margin (lower margin)

**Intraday > Overnight** (for long positions) because intraday has looser requirements

### Expiry
When the position contract expires (mostly for structured products or calendar spreads)

---

## Features in Development

Future enhancements will include:
- [ ] Modify TP/SL directly from the dialog
- [ ] Enable/configure trailing stops
- [ ] Partial close options
- [ ] Position modification history
- [ ] Export position details

---

## Technical Architecture

### File Structure

```
src/ui/components/
├── dialogs/
│   ├── __init__.py
│   └── position_details_dialog.py    (New)
├── panels/
│   ├── trading_panels.py             (Updated)
│   └── trading_updates.py            (Updated)
└── terminal.py                       (Updated)
```

### Key Classes

**PositionDetailsDialog**
```python
class PositionDetailsDialog(QDialog):
    def __init__(self, parent, position, terminal=None, 
                 on_close_position=None, on_close_all=None)
    
    def _setup_ui(self)                 # Build dialog layout
    def _build_risk_management_section() # Show TP/SL/trailing
    def _format_side()                  # Format side label
    def _format_notional()              # Calculate notional value
    def _on_close_position_clicked()   # Handle close action
    def _on_close_all_clicked()        # Handle close all action
```

### Integration Points

1. **Terminal.py** - Added `_show_position_details()` method
2. **trading_updates.py** - Updated `populate_positions_table()` to add View button
3. **trading_panels.py** - Headers now include separate View/Close columns

---

## Usage from Python

### Display Position Details from Code

```python
from ui.components.dialogs.position_details_dialog import PositionDetailsDialog

# Build enriched position data
position_data = {
    "symbol": "BTC/USDT",
    "side": "long",
    "amount": 1.0,
    "entry_price": 75845.00,
    "mark_price": 76015.00,
    "pnl": 170.00,
    "value": 76015.00,
    "financing": -0.03,
    "venue": "COINBASE",
    "intraday_liquidation_price": 44114.00,
    "overnight_liquidation_price": 55445.00,
    "expiry": "12/20/30",
}

# Open dialog
dialog = PositionDetailsDialog(
    parent=self,
    position=position_data,
    terminal=self,
    on_close_position=self._confirm_close_position,
    on_close_all=self._close_all_positions,
)
dialog.exec()
```

### Data Structure

The position data dict should include:

```python
{
    # Required fields
    "symbol": str,           # Trading pair (e.g., "BTC/USDT")
    "side": str,            # "long" or "short"
    "amount": float,        # Position size
    "entry_price": float,   # Entry price
    "mark_price": float,    # Current market price
    "pnl": float,          # Unrealized P&L
    "value": float,        # Notional value
    
    # Optional fields
    "venue": str,          # Exchange name
    "financing": float,    # Funding fees (perpetuals)
    "expiry": str,        # Expiration date
    "intraday_liquidation_price": float,  # Intraday liquidation
    "overnight_liquidation_price": float, # Overnight liquidation
    "take_profit": float,  # TP price (if set)
    "stop_loss": float,    # SL price (if set)
    "trailing_stop_enabled": bool,
    "trailing_stop_distance": float,
    "trailing_stop_percent": float,
}
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "View" button doesn't appear | Old positions table version | Refresh positions (press F5) |
| Dialog won't open | Position data is invalid | Check position data structure |
| "Close Position" button grayed out | Broker not initialized | Connect to broker first |
| Liquidation prices show "N/A" | Broker doesn't support them | Not all brokers provide this |
| Position details incomplete | Missing enrichment data | Check terminal enrichment logic |

---

## Best Practices

1. **Check Liquidation Price Before Scaling Up**: Review liquidation prices before adding to a position
2. **Monitor Funding**: For perpetuals, track cumulative funding costs
3. **Review P&L Regularly**: Use the view dialog to quickly check all positions
4. **Consider Notional Value**: Ensure notional value fits your risk allocation
5. **Use Close All Cautiously**: Only click "Close All" when you want to liquidate entire portfolio

---

## See Also

- [Position Management](../portfolio/README.md)
- [Risk Management - TP/SL/Trailing Stops](risk_management_tp_sl_trailing.md)
- [Trading Panels](../components/panels/trading_panels.py)
- [Terminal UI](../components/terminal.py)
