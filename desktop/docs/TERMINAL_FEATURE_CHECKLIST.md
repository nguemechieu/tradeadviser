# Terminal Features Checklist

## Quick Reference: What's Implemented vs Missing

### CORE TRADING FEATURES
- ✅ Paper/Live trading mode toggle
- ✅ Manual order entry & management
- ✅ Position management with view details
- ✅ Close all positions
- ✅ Cancel all orders
- ✅ Emergency kill switch
- ✅ Stop Loss / Take Profit modification
- ✅ Trailing stops
- ❌ Advanced order types (OCO, Iceberg, Bracket)
- ❌ Reduce-only orders UI
- ❌ Time-in-Force options UI

### CHARTS & TECHNICAL ANALYSIS
- ✅ Multi-timeframe support (1m, 5m, 15m, 1h, 4h, 1d, etc.)
- ✅ Technical indicators & studies
- ✅ Volume visualization
- ✅ Bid/Ask lines
- ✅ Multiple chart windows (detach/tile/cascade)
- ✅ Chart style customization
- ✅ Chart settings panel
- ❌ Drawing tools (trend lines, Fibonacci, channels)
- ❌ Drawing tool persistence
- ❌ Text annotations on charts

### MARKET DATA & OVERVIEW
- ✅ Order book / Depth of Market (basic)
- ✅ Market trades / Tape (real-time)
- ✅ Market data refresh controls
- ❌ Level 2 DOM visualization (heatmap)
- ❌ Cumulative delta
- ❌ Time & Sales window (enhanced)
- ❌ Watchlists
- ❌ Symbol search & filter
- ❌ Market screener
- ❌ Heat maps (sector, asset class)
- ❌ Market overview dashboard

### ALERTS & NOTIFICATIONS
- ❌ Price alerts (cross above/below)
- ❌ Percentage change alerts
- ❌ Volume spike alerts
- ❌ Indicator alerts (RSI, MACD, etc.)
- ❌ Order filled notifications
- ❌ Position liquidation warnings
- ❌ Margin warning alerts
- ❌ Email/SMS alerts
- ❌ Webhook notifications

### STRATEGY MANAGEMENT
- ✅ Strategy assignment
- ✅ Strategy optimization
- ✅ Strategy scorecard
- ✅ Strategy debug panel
- ✅ Backtesting engine
- ✅ Strategy performance tracking
- ❌ Strategy repository/library
- ❌ Public strategy templates

### ANALYSIS & REPORTING
- ✅ Trade journal
- ✅ Closed journal (completed trades)
- ✅ Trade checklist
- ✅ Trade review dashboard
- ✅ Performance analytics
- ✅ Report generation (PDF)
- ✅ Trade export (CSV)
- ⚠️ Equity curve visualization (partial in performance)
- ❌ Drawdown analysis (underwater plot)
- ❌ Tax report generation
- ❌ Account statements
- ❌ Profit/loss breakdown by strategy
- ❌ Win/loss ratio analysis

### RISK MANAGEMENT
- ✅ Risk settings panel
- ✅ Portfolio exposure view
- ✅ Position analysis window
- ✅ Stop Loss / Take Profit management
- ✅ Trailing stop configuration
- ❌ Value at Risk (VaR) calculation
- ❌ Stress testing / Scenario analysis
- ❌ Liquidation price calculations UI
- ❌ Margin requirements projection
- ❌ Correlation matrix
- ❌ Leverage/margin UI management

### ACCOUNT & CONNECTION
- ✅ Paper mode indicator
- ✅ Live mode indicator
- ✅ Session badge (mode + broker + venue)
- ✅ System health monitoring
- ⚠️ System status dashboard (partial)
- ❌ API connection status indicator (persistent)
- ❌ Ping/latency display
- ❌ Data feed quality indicator
- ❌ Multi-account switching UI
- ❌ Account statements
- ❌ Account history & deposits/withdrawals

### AI & RESEARCH FEATURES
- ✅ Sopotek Pilot (AI chat)
- ✅ ML Monitor
- ✅ ML Research Lab
- ✅ Recommendations engine
- ✅ Quant PM tools
- ⚠️ Trader TV (video/education)
- ❌ Sentiment analysis integration
- ❌ News feed with sentiment
- ❌ Social media sentiment tracking
- ❌ Economic calendar
- ❌ Corporate earnings calendar

### USER EXPERIENCE
- ✅ Multi-language support
- ✅ Dark mode / theming
- ✅ Customizable layouts
- ✅ Dockable panels
- ✅ Keyboard shortcuts (Ctrl+T, Ctrl+B, etc.)
- ✅ System console
- ✅ Diagnostics export
- ❌ Keyboard shortcuts reference window
- ❌ UI customization (color scheme editor)
- ❌ Saved workspace layouts
- ❌ Drag-and-drop panel reorganization

### INTEGRATIONS
- ✅ Multiple brokers (Coinbase, IBKR, Binance, Alpaca, etc.)
- ✅ Stellar blockchain integration
- ❌ TradingView integration / charts
- ❌ News API integration
- ❌ Economic calendar API
- ❌ Webhook support (receive external signals)
- ❌ API documentation portal

### SPECIALIZED FEATURES
- ⚠️ Options support (depends on broker)
- ❌ Options chains display
- ❌ Greeks calculator & display
- ❌ IV Rank & volatility surface
- ⚠️ Futures support
- ❌ Crypto derivatives heat maps
- ⚠️ Forex support

---

## By Category Priority

### 🚨 CRITICAL MISSING (High Impact)
1. **Alerts** - Real-time notifications for traders
2. **Watchlists** - Essential market scanning
3. **Drawing Tools** - Technical analysis must-have
4. **Level 2 DOM Visualization** - Professional standard
5. **Economic Calendar** - Market event tracking

### 🟠 IMPORTANT MISSING (Medium Impact)
6. News Feed
7. Symbol Search/Filter
8. Connection Status Display
9. Advanced Order Types UI
10. Keyboard Shortcuts Reference

### 🔵 NICE-TO-HAVE MISSING (Lower Impact)
11. Market Heat Maps
12. Correlation Matrix
13. Drawdown Analysis
14. Multi-Account Support
15. Stress Testing

---

## Feature Completeness Score

| Category | Score | Status |
|----------|-------|--------|
| Trading | 80/100 | Strong |
| Charts | 75/100 | Good |
| Analysis | 85/100 | Strong |
| Alerts | 0/100 | ❌ Missing |
| Watchlists | 0/100 | ❌ Missing |
| Market Overview | 40/100 | Weak |
| Risk Management | 70/100 | Adequate |
| AI/ML | 95/100 | Excellent |
| Account | 50/100 | Weak |
| **OVERALL** | **62/100** | Good but needs alerts & watchlists |

---

## Recommended Implementation Order

1. **Alerts System** → 2 weeks
2. **Watchlists** → 1.5 weeks
3. **Drawing Tools** → 2 weeks
4. **Enhanced Level 2 DOM** → 1 week
5. **Economic Calendar** → 1.5 weeks

**Total**: ~8 weeks to reach professional parity

---

## See Also

- [TERMINAL_FEATURE_GAP_ANALYSIS.md](TERMINAL_FEATURE_GAP_ANALYSIS.md) - Detailed analysis
- [Terminal Menus & Navigation](../src/ui/components/terminal.py) - Current implementation
- [Trading Actions](../src/ui/components/actions/trading_actions.py) - Available actions
