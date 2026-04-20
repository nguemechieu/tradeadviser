# Missing Features: Implementation Ideas

## 1. ALERT SYSTEM (Priority #1)

### Architecture

```
Alert Engine
├── Alert Rules Storage (JSON/DB)
├── Condition Evaluator
├── Notification Dispatcher
└── UI Components
    ├── Alert Manager Panel
    ├── Create Alert Dialog
    ├── Active Alerts Table
    └── Notification Center
```

### Implementation Approach

**Phase 1: Core Engine**
```python
# src/alerts/alert_engine.py
class AlertEngine:
    def create_alert(self, rule_config):
        # Store alert rule
        pass
    
    def evaluate_all_alerts(self, market_data):
        # Check each alert condition
        # If triggered, send notification
        pass

class AlertRule:
    type: str  # "price", "percentage", "volume", "indicator", "system"
    symbol: str
    condition: Dict  # {operator: "gt", value: 100}
    active: bool
    enabled_channels: List  # ["in-app", "sound", "email"]
    created_at: datetime
```

**Phase 2: UI Components**
```python
# src/ui/components/panels/alerts_panel.py
class AlertsPanel:
    def __init__(self):
        self.alerts_table = QTableWidget()
        self.create_alert_button = QPushButton("New Alert")
        
    def refresh_alerts(self):
        # Populate active alerts table
        pass

# src/ui/components/dialogs/create_alert_dialog.py
class CreateAlertDialog:
    def __init__(self):
        self.alert_type_combo = QComboBox()  # price, %, volume, indicator
        self.symbol_input = QLineEdit()
        self.condition_combo = QComboBox()  # >, <, =, cross above, cross below
        self.value_input = QDoubleSpinBox()
        self.channel_checkboxes = [...]  # in-app, sound, email
```

**Phase 3: Notification Center**
```python
# src/ui/components/notification_center.py
class NotificationCenter(QWidget):
    def __init__(self):
        self.notification_queue = []
        self.notification_list = QListWidget()
        
    def add_notification(self, alert):
        # Show in-app notification
        # Play sound if enabled
        # Send email if enabled
        pass
```

### UI Mockup

```
┌─ Alerts Panel ─────────────────────────────────┐
│ [New Alert] [Dismiss All] [Settings]           │
├────────────────────────────────────────────────┤
│ Symbol    Type      Condition    Status   Last │
├────────────────────────────────────────────────┤
│ BTC/USDT  Price    > $100,000   🟢 Active 2h  │
│ ETH/USDT  Percent   Down 10%    🔴 Inactive   │
│ SPY       Volume   > 10M shares 🟢 Active 30m │
├────────────────────────────────────────────────┤
│ 🔔 Notification: BTC above 100k (triggered!)   │
│ 🔔 Volume spike on AAPL (98M shares)           │
└────────────────────────────────────────────────┘
```

### Data Storage

```json
{
  "alerts": [
    {
      "id": "alert_001",
      "symbol": "BTC/USDT",
      "type": "price",
      "condition": "cross_above",
      "value": 100000,
      "active": true,
      "channels": ["in-app", "sound", "email"],
      "email": "user@example.com",
      "created_at": "2026-04-19T10:00:00Z",
      "last_triggered": "2026-04-19T12:30:00Z"
    }
  ]
}
```

---

## 2. WATCHLISTS (Priority #2)

### Architecture

```
Watchlist System
├── Watchlist Storage (JSON/DB)
├── Watchlist Manager
└── UI Components
    ├── Watchlist Panel
    ├── Watchlist Selector
    └── Symbol Context Menu
```

### Implementation

**Phase 1: Core**
```python
# src/watchlists/watchlist_manager.py
class WatchlistManager:
    def create_watchlist(self, name):
        pass
    
    def add_symbol(self, watchlist_id, symbol):
        pass
    
    def remove_symbol(self, watchlist_id, symbol):
        pass
    
    def get_watchlist_data(self, watchlist_id):
        # Return list with live prices, change %, volume
        pass

class Watchlist:
    id: str
    name: str
    symbols: List[str]
    columns: List[str]  # ["symbol", "price", "change%", "volume"]
    created_at: datetime
```

**Phase 2: UI**
```python
# src/ui/components/panels/watchlist_panel.py
class WatchlistPanel:
    def __init__(self):
        self.watchlist_selector = QComboBox()  # [Favorites] [Tech] [Crypto]
        self.watchlist_table = QTableWidget()
        self.add_symbol_button = QPushButton("Add Symbol")
        
    def refresh_watchlist_data(self):
        # Populate table with live prices
        pass
```

### UI Mockup

```
┌─ Watchlist Panel ─────────────────────────────┐
│ Watchlist: [Favorites ▼] [+] [-] [Settings]   │
├───────────────────────────────────────────────┤
│ Symbol    Price      Change   Volume   Action │
├───────────────────────────────────────────────┤
│ BTC/USDT  $75,845   +0.22%   $2.1B    [×]    │
│ ETH/USDT  $2,500    -1.50%   $1.2B    [×]    │
│ SOL/USDT  $180.50   +5.20%   $450M    [×]    │
│ XRP/USDT  $0.52     -2.10%   $280M    [×]    │
└───────────────────────────────────────────────┘
```

### Data Storage

```json
{
  "watchlists": [
    {
      "id": "wl_001",
      "name": "Favorites",
      "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
      "columns": ["symbol", "price", "change_pct", "volume"],
      "sort_column": "change_pct",
      "sort_order": "desc",
      "created_at": "2026-04-19T10:00:00Z"
    }
  ]
}
```

---

## 3. DRAWING TOOLS (Priority #3)

### Architecture

```
Drawing System
├── Drawing Layer (PyQtGraph)
├── Drawing Tools
│   ├── TrendLine
│   ├── Channel
│   ├── Fibonacci
│   └── Text
└── Drawing Toolbar
```

### Implementation

**Phase 1: Drawing Toolbar**
```python
# src/ui/components/chart/drawing_toolbar.py
class DrawingToolbar(QToolBar):
    def __init__(self):
        self.trend_line_action = QAction("Trend Line")
        self.channel_action = QAction("Channel")
        self.fibonacci_action = QAction("Fibonacci")
        self.text_action = QAction("Text")
        self.clear_drawings_action = QAction("Clear All")
        
        self.addAction(self.trend_line_action)
        # ... add other tools
```

**Phase 2: Drawing Tools**
```python
# src/ui/components/chart/drawing_tools.py
class TrendLine(QObject):
    def __init__(self, start_point, end_point):
        self.start = start_point
        self.end = end_point
        
    def draw(self, painter, scale_transform):
        # Draw line on chart
        pass
    
    def to_dict(self):
        # For persistence
        return {
            "type": "trend_line",
            "start": self.start,
            "end": self.end,
            "color": self.color,
            "width": self.width
        }

class Fibonacci(QObject):
    def __init__(self, start_price, end_price):
        self.levels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
        # Calculate retracement levels
        pass
```

**Phase 3: Integration**
```python
# Update ChartWidget to support drawings
class ChartWidget:
    def __init__(self):
        self.drawing_toolbar = DrawingToolbar()
        self.drawings = []
        
    def _on_drawing_tool_selected(self, tool_type):
        # Enter drawing mode
        pass
    
    def _on_chart_clicked(self, pos):
        # Record drawing points
        pass
    
    def save_drawing(self):
        # Persist drawing to JSON
        pass
```

### UI Mockup

```
┌─ Chart ────────────────────────────────────┐
│ [Line] [Channel] [Fib] [Text] [Clear] [...]│
│                                             │
│   $80,000 ├─────────────────── ← Trend    │
│   $75,000 │ BTC/USDT (4H)      ╱          │
│   $70,000 ├──────────────────╱─ ← Channel│
│   $65,000 │                 ╱  ╲         │
│   $60,000 ├────────────────╱────╲        │
│           │               ╱      ╲       │
│           │              ╱        ╲      │
│   └──────────────────────────────────┘    │
│      Apr 10  Apr 15  Apr 18  Apr 19       │
└─────────────────────────────────────────────┘
```

---

## 4. LEVEL 2 DOM ENHANCEMENT (Priority #4)

### Current State
```
┌─ Orderbook ────────────────────┐
│ BID              ASK            │
│ 100,000  1.5    100,100  2.0   │
│ 100,050  2.2    100,150  1.8   │
│ 100,100  3.1    100,200  2.5   │
└────────────────────────────────┘
```

### Enhanced Version

```
┌─ Level 2 DOM ──────────────────────────────┐
│ 🔵 BID              ASK        🔴 ASK      │
│   Volume  Price  │  Price  Volume           │
│   ████ 5.2 99,950 │ 100,050 ████ 3.1      │
│   ████ 4.8 100,000│ 100,100 █████ 5.2     │
│   █████ 3.1 100,050│ 100,150 ████ 4.5     │
│   ███ 2.2 100,100│ 100,200 ███ 2.8       │
│   ██ 1.5 100,150│ 100,250 ██ 1.2        │
│                                            │
│ Spread: $100 | Mid: $100,050 | Imbalance  │
└────────────────────────────────────────────┘
```

### Implementation

```python
# src/ui/components/panels/enhanced_orderbook_panel.py
class EnhancedOrderbookPanel:
    def __init__(self):
        self.bid_bars = []  # List of bar charts
        self.ask_bars = []
        
    def update_orderbook(self, bids, asks):
        # Find max volume for scaling
        max_volume = max([v for _, v in bids + asks])
        
        # Draw scaled bar charts
        for price, volume in bids:
            bar_width = (volume / max_volume) * 100
            self._draw_bid_bar(price, volume, bar_width)
```

---

## 5. ECONOMIC CALENDAR (Priority #5)

### Architecture

```
Economic Calendar System
├── Data Provider (API)
├── Calendar Manager
└── UI Components
    ├── Calendar Widget
    └── Event Details Dialog
```

### Implementation

```python
# src/data/economic_calendar.py
class EconomicCalendarProvider:
    async def fetch_events(self, date_range, countries=None):
        # Fetch from TradingEconomics or similar API
        pass

class EconomicEvent:
    country: str
    event_name: str
    impact: str  # "High", "Medium", "Low"
    scheduled_time: datetime
    previous: float
    forecast: float
    actual: float = None
    consensus: float = None
```

### UI Component

```python
# src/ui/components/panels/economic_calendar_panel.py
class EconomicCalendarPanel:
    def __init__(self):
        self.calendar = QCalendarWidget()
        self.events_list = QListWidget()
        
    def select_date(self, date):
        # Show events for that date
        pass
    
    def highlight_impact_level(self, event):
        # Color code: High=Red, Medium=Yellow, Low=Gray
        pass
```

### UI Mockup

```
┌─ Economic Calendar ─────────────────────┐
│ April 2026                              │
│ ┌─────────────────────────────────────┐ │
│ │ S  M  T  W  T  F  S                │ │
│ │                    1  2  3 🔴       │ │
│ │    4  5  6  7  8  9 10 🟡🔴        │ │
│ │   11 12 13 14 15 16 17             │ │
│ │   18 19●20 21 22 23 24 🔴🟡        │ │
│ │   25 26 27 28 29 30                │ │
│ └─────────────────────────────────────┘ │
│                                          │
│ April 19, 2026                           │
│ ┌──────────────────────────────────────┐ │
│ │ 2:00 PM   ISM Manufacturing (High) 🔴 │ │
│ │           Forecast: 50.5  Prev: 49.2  │ │
│ │                                        │ │
│ │ 4:30 PM   EIA Crude Oil (Medium) 🟡  │ │
│ │           Forecast: +1.2M Prev: -0.8M │ │
│ └──────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

---

## File Structure Recommendation

```
src/
├── alerts/
│   ├── __init__.py
│   ├── alert_engine.py          (core engine)
│   ├── alert_manager.py         (persistence)
│   └── notification_dispatcher.py
├── watchlists/
│   ├── __init__.py
│   ├── watchlist_manager.py     (core logic)
│   └── watchlist_storage.py     (persistence)
├── data/
│   ├── economic_calendar.py     (API integration)
│   └── economic_calendar_storage.py
└── ui/
    └── components/
        ├── alerts/
        │   ├── alerts_panel.py
        │   ├── create_alert_dialog.py
        │   └── notification_center.py
        ├── watchlists/
        │   ├── watchlist_panel.py
        │   └── watchlist_selector.py
        ├── chart/
        │   ├── drawing_toolbar.py
        │   ├── drawing_tools.py
        │   └── drawing_storage.py
        └── panels/
            ├── enhanced_orderbook_panel.py
            └── economic_calendar_panel.py
```

---

## Quick Start Template

Want to start implementing alerts? Here's a minimal skeleton:

```python
# src/alerts/alert_engine.py
from datetime import datetime
from typing import List, Dict, Callable
import json

class AlertRule:
    def __init__(self, symbol: str, rule_type: str, condition: Dict):
        self.id = f"alert_{datetime.now().timestamp()}"
        self.symbol = symbol
        self.type = rule_type  # "price", "percentage", "volume"
        self.condition = condition  # {"operator": ">", "value": 100}
        self.active = True
        self.triggered_count = 0
        self.last_triggered = None

class AlertEngine:
    def __init__(self):
        self.alerts: List[AlertRule] = []
        self.listeners: List[Callable] = []
    
    def add_alert(self, alert: AlertRule):
        self.alerts.append(alert)
    
    def remove_alert(self, alert_id: str):
        self.alerts = [a for a in self.alerts if a.id != alert_id]
    
    def on_market_data(self, symbol: str, price: float, volume: float):
        """Called when new market data arrives"""
        for alert in self.alerts:
            if alert.symbol == symbol and alert.active:
                if self._check_condition(alert, price, volume):
                    self._trigger_alert(alert)
    
    def _check_condition(self, alert: AlertRule, price: float, volume: float) -> bool:
        if alert.type == "price":
            return self._check_price_condition(alert.condition, price)
        elif alert.type == "percentage":
            return self._check_percentage_condition(alert.condition, price)
        # ... add more types
        return False
    
    def _trigger_alert(self, alert: AlertRule):
        alert.last_triggered = datetime.now()
        alert.triggered_count += 1
        
        # Notify all listeners
        for listener in self.listeners:
            listener(alert)
    
    def subscribe(self, callback: Callable):
        """Subscribe to alert events"""
        self.listeners.append(callback)

# Usage:
# engine = AlertEngine()
# rule = AlertRule("BTC/USDT", "price", {"operator": ">", "value": 100000})
# engine.add_alert(rule)
# engine.subscribe(lambda alert: print(f"Alert triggered: {alert.symbol}"))
```

---

## Estimated Effort

| Feature | Files | Effort | Timeline |
|---------|-------|--------|----------|
| Alerts | 5-6 | 120-160 hrs | 2-3 weeks |
| Watchlists | 3-4 | 80-100 hrs | 1.5 weeks |
| Drawing Tools | 4-5 | 100-140 hrs | 2 weeks |
| Level 2 DOM | 2-3 | 40-60 hrs | 1 week |
| Economic Calendar | 3-4 | 60-80 hrs | 1.5 weeks |

**Total**: ~400-540 hours (~10-13 weeks with 1 developer)

---

## See Also

- [TERMINAL_FEATURE_GAP_ANALYSIS.md](TERMINAL_FEATURE_GAP_ANALYSIS.md)
- [TERMINAL_FEATURE_CHECKLIST.md](TERMINAL_FEATURE_CHECKLIST.md)
