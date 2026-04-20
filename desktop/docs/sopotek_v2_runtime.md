# Sopotek v2 Runtime

This repository now includes a modular v2 runtime under `src/sopotek/`.

## Layout

```text
src/sopotek/
├── agents/
├── broker/
├── core/
│   └── event_bus/
└── engines/
```

## What Changed

- `src/sopotek/core/event_bus/`
  - Async event bus with priority delivery, optional persistence, replay support, and structured event envelopes.
- `src/sopotek/engines/market_data.py`
  - `LiveFeedManager`, `CandleAggregator`, `OrderBookEngine`, and `MarketDataEngine`.
- `src/sopotek/engines/strategy.py`
  - `BaseStrategy`, `StrategyRegistry`, and `StrategyEngine`.
- `src/sopotek/engines/risk.py`
  - Pre-trade review flow with volatility-aware sizing, exposure limits, drawdown protection, and kill-switch support.
- `src/sopotek/engines/execution.py`
  - Smart execution path with retries, order states, latency tracking, and slippage measurement.
- `src/sopotek/engines/portfolio.py`
  - Real-time position, cash, exposure, and equity snapshots.
- `src/sopotek/agents/`
  - Market analyst, strategy selector, risk manager, and execution monitor agents.
- `src/sopotek/core/orchestrator.py`
  - `SopotekRuntime` composes the system into a single event-driven runtime.

## Compatibility

The legacy `src/event_bus/` package now forwards to the upgraded v2 bus so the current desktop application can keep its existing imports while benefiting from the stronger event infrastructure.

## Next Integration Step

Wire `AppController` and `SopotekTrading` to instantiate `SopotekRuntime` directly for selected live-trading flows, while keeping the legacy path available as a fallback during migration.
