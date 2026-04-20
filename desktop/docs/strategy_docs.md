# Strategies

## Built-In Runtime Presets

Repo evidence supports these built-in strategies:

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

## Strategy Engine

Primary implementation files:
- `src/strategy/strategy.py`
- `src/strategy/strategy_registry.py`

The strategy engine computes features from candle data and emits signal metadata such as action, confidence, and reason.

### Inputs
- OHLCV candles
- indicator calculations
- strategy parameters from settings
- optional news bias context

### Computed Features
Repo evidence shows feature use such as:
- RSI
- EMA fast / slow
- ATR
- momentum
- MACD line / signal / histogram
- volatility ratios
- trend strength
- band or pullback positioning

## Parameter Set

Settings-backed strategy parameters include:

- RSI period
- EMA fast
- EMA slow
- ATR period
- oversold threshold
- overbought threshold
- breakout lookback
- minimum confidence
- signal amount

## Preset Behavior

### Trend Following
Favors aligned directional movement and trend confirmation.

### Mean Reversion
Looks for exhaustion or oversold / overbought conditions.

### Breakout
Focuses on breakout windows, lookback context, and follow-through.

### AI Hybrid
Blends model or AI-style confidence with strategy filtering and runtime context.

### EMA Cross / MACD / Momentum / Pullback / Range Variants
These presets expand the original set into more specialized directional, continuation, fade, and breakout behaviors.

## Strategy Selection In The App

Strategies can be selected from:
- the dashboard before launch
- the settings window inside the terminal
- backtesting and optimization workspaces

## Strategy Review Loop

A practical repo-backed workflow is:

1. choose the strategy in the dashboard or settings
2. backtest the symbol and timeframe you plan to trade
3. validate manual execution and order-state handling
4. review the strategy in `Recommendations`, `Strategy Scorecard`, `Closed Journal`, and `Journal Review`
5. only then allow AI trading to run that strategy on real broker data

## Backtesting And Comparison

The repo now supports backtesting and optimization selection for:
- symbol
- strategy
- timeframe

Strategy analytics also show up in the UI through recommendation, scorecard, or performance-style views.

## Operational Guidance

1. Validate strategies on paper or practice first.
2. Separate signal quality from execution quality.
3. Confirm rejected-order handling as well as successful fills.
4. Review performance by strategy, not only overall PnL.
5. Use the journal and trade checklist to understand why a setup worked or failed.
