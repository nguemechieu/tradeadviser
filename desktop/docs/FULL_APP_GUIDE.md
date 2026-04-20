# Full App Guide

## Overview

Sopotek Quant System is a desktop workstation that combines:

- broker connection and session setup
- live candles, orderbook views, and indicator studies
- chart-linked manual trading and AI-assisted execution
- risk, behavior, and session-safety tooling
- backtesting, optimization, journaling, and trade review
- Telegram notifications, command control, screenshots, and Sopotek Pilot-assisted workflows

## Main Screens

## Dashboard

The dashboard is the launch surface for:

- broker type and exchange selection
- mode selection (`paper`, `practice`, `sandbox`, `live`)
- credentials and account details
- strategy selection
- profile save/load behavior
- venue preference such as spot or option where supported
- live safety interlock and licensing checks

## Terminal

The terminal is the main operator workspace. Evidence in `src/frontend/ui/terminal.py` shows support for:

- market watch and watchlist-scoped symbol selection
- chart tabs plus detached/floating chart windows
- order book ladder plus a `Recent Trades` market feed for the active symbol
- timeframe controls and utility buttons
- screenshot capture and chart-focused actions
- manual trade ticket and chart trading interactions
- trade log, open orders, positions, closed journal, and trade review
- AI signal monitor, recommendations, strategy scorecard, and behavior guard status
- risk heatmap, system status, system health, and performance analytics
- Sopotek Pilot, separate `Settings` and `Risk` menus, documentation, and licensing windows

## Charts

The chart engine in `src/frontend/ui/chart/chart_widget.py` supports:

- candlestick rendering with MT4-style body and wick handling
- orderbook heatmap updates
- dedicated `Depth Chart` and `Market Info` tabs alongside the candlestick workspace
- live bid/ask and last-price line updates
- lower indicator panes and overlays
- Fibonacci retracement overlay
- news markers and news detail labels drawn on the chart
- detachable single-chart windows
- tiled and cascaded detached charts
- restored detached chart layouts through settings
- chart-driven manual trade interactions including entry, SL, and TP context actions

### Market Data Tabs
- `Candlestick`: the main chart, indicators, overlays, and order book heatmap
- `Depth Chart`: cumulative bid/ask depth built from the live order book for the symbol in view
- `Market Info`: a compact market summary with spread, best bid/ask, visible range, visible volume, and depth bias

## Chart Trading

The chart workflow now supports a more MT4-like interaction model:

- double-click a chart price level to open a manual trade ticket
- right-click chart levels for `Buy Limit Here`, `Sell Limit Here`, `Set Entry Here`, `Set Stop Loss Here`, and `Set Take Profit Here`
- drag chart trade levels when the trade ticket is open
- use broker-aware formatting for amount, SL, TP, and entry values
- receive suggested SL/TP automatically while still being able to adjust them manually
- refresh stale quotes during live preflight when a fresh quote can be fetched before submission
- cap requested size from available balance, free margin, or equity before a live broker sees the order
- use account buying capacity for leveraged FX sizing instead of spot-style quote-inventory checks
- retry one time with a smaller safe amount after an insufficient-funds or insufficient-margin rejection and report the reason back to the operator

## Indicators

Repo evidence shows support for a broad MT4-style indicator set plus some extra overlays.

### Overlays
- `Moving Average`, `EMA`, `SMMA`, `LWMA`
- `VWAP`
- `Bollinger Bands`, `Envelopes`, `Donchian`, `Keltner`
- `Ichimoku`, `Alligator`, `Parabolic SAR`, `Fractals`, `ZigZag`
- `Fibonacci Retracement`
- `Volumes`

### Lower-Pane Indicators
- `ADX`, `ATR`, `StdDev`
- `Accumulation Distribution`, `MFI`, `OBV`
- `Momentum`, `Bulls Power`, `Bears Power`, `Force Index`
- `AC`, `AO`, `OsMA`, `Gator`, `Market Facilitation Index`
- `CCI`, `DeMarker`, `MACD`, `RSI`, `RVI`, `Stochastic`, `Williams %R`

## Strategies

The runtime registry now includes more than the original small preset list. Repo evidence supports presets such as:

- `Trend Following`
- `Mean Reversion`
- `Breakout`
- `AI Hybrid`
- `EMA Cross`
- `Momentum Continuation`
- `Pullback Trend`
- `Volatility Breakout`
- `MACD Trend`
- `Range Fade`

The settings-backed parameter set includes:

- RSI period
- EMA fast / slow
- ATR period
- oversold / overbought thresholds
- breakout lookback
- minimum confidence
- signal amount

## Auto-Trading Scope

The controller persists and applies AI scope settings for:

- `All Symbols`
- `Selected Symbol`
- `Watchlist`

The Market Watch UI can mark symbols for watchlist-scoped trading.

## Orders And Trade State

The execution layer supports:

- order preparation and broker-aware formatting
- broker order submission
- follow-up order tracking through `fetch_order()` where supported
- terminal statuses such as `submitted`, `open`, `filled`, `canceled`, and `rejected`
- open-order refresh in the UI
- local persistence to the trade repository
- source tagging such as `manual`, `bot`, and the internal `chatgpt` source used for Sopotek Pilot actions

## Risk, Behavior, And Safety

The repo now includes several safety layers:

- risk profiles such as `Capital Preservation`, `Conservative`, `Balanced`, `Growth`, `Active Trader`, and `Aggressive`
- behavior guard limits for overtrading, size jumps, loss streaks, and drawdown locks
- kill switch and resume flow
- live safety interlock on launch
- system health checks after session initialization
- operator-facing sizing summaries when a manual order is reduced, corrected, or retried for account-safety reasons

## Settings And Risk Menus

The terminal now exposes:

- `Settings` as its own top-level menu for general runtime, integrations, strategy, and UI preferences
- `Risk` as a separate top-level menu for risk configuration and risk-focused workflows

This separation is intended to make live supervision faster and reduce the chance of digging through general settings while trying to adjust risk controls.

## Journal, Checklist, And Review

The operator workflow now includes:

- `Closed Journal`
- `Trade Review`
- `Journal Review`
- `Trade Checklist`

These windows support:

- storing journal notes
- linking reason, setup, TP/SL, outcome, and lessons
- weekly and monthly review summaries
- action items and discipline tracking
- pre-trade validation before clicking submit

## Backtesting And Optimization

The repo includes:

- backtesting engine
- simulator
- report generator
- strategy optimization workspace
- tester symbol, strategy, and timeframe selectors

These paths are operationally useful, but they should still be validated with your own datasets and symbols before using them to justify risk.

## Performance And Analytics

Performance tooling now includes:

- equity and profitability snapshotting
- drawdown-aware metrics
- strategy scorecard and symbol contribution views
- fee, spread, and slippage analytics
- trade replay / post-trade review context

## Integrations

Settings expose fields for:

- Telegram enabled / disabled
- Telegram bot token
- Telegram chat ID
- OpenAI API key
- OpenAI model
- voice recognition provider
- speech output provider and voice preferences
- news feed behavior

### Credential Setup

Telegram:
1. Open Telegram and talk to `@BotFather`.
2. Send `/newbot` and copy the returned bot token.
3. Message your bot once, then open `https://api.telegram.org/bot<token>/getUpdates`.
4. Copy `message.chat.id` into `Settings -> Integrations -> Telegram chat ID`.

OpenAI:
1. Sign in at `https://platform.openai.com/`.
2. Create a key at `https://platform.openai.com/api-keys`.
3. Paste it into `Settings -> Integrations -> OpenAI API key`.
4. Use `Test OpenAI` before depending on Sopotek Pilot or Telegram Q&A.

Telegram now supports:

- notifications
- command keyboard
- screenshots and chart screenshots
- app status and analysis requests
- normal Sopotek Pilot-style conversation, not only slash commands

Sopotek Pilot inside the app supports:

- app-aware questions
- trading and order commands with confirmation
- screenshots
- Telegram management
- position analysis
- voice input and spoken replies
- trade-history analysis and journal-aware summaries

## Command Workflows

### Telegram
Repo evidence supports commands and keyboard actions for:

- `/status`
- `/balances`
- `/positions`
- `/orders`
- `/recommendations`
- `/performance`
- `/analysis`
- `/screenshot`
- `/chart SYMBOL [TIMEFRAME]`
- `/chartshot SYMBOL [TIMEFRAME]`
- plain-text Sopotek Pilot questions

### Sopotek Pilot
Sopotek Pilot can:

- explain balances, positions, equity, profitability, and behavior guard status
- open app windows and panels
- manage Telegram state
- trade, cancel, or close positions with confirmation
- produce screenshots
- analyze trade history, news, and recommendations using live app context

## Local Persistence

Repo-backed persistence currently includes:

- local SQLite database in `data/sopotek_trading.db`
- trade repository and market data repository
- UI preferences and detached chart layouts via `QSettings`
- saved checklist state and integration settings

## Recommended Operating Practice

1. Start on paper or practice.
2. Validate a manual order.
3. Validate that preflight sizing reduces an intentionally oversized order instead of sending the full amount.
4. Validate a rejected order path and confirm the app surfaces the broker reason and any smaller retry.
5. Validate chart refresh, open orders, positions, journal, and checklist flow.
6. Validate Telegram or OpenAI features only after the base session is healthy.
7. Validate Sopotek Pilot, screenshots, and remote commands next.
8. Only then test AI trading or live execution.
