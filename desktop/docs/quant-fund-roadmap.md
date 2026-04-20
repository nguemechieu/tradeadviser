# Sopotek Quant Fund Roadmap

## Purpose

This roadmap turns the current Sopotek desktop trading platform into a staged quant-fund style system. It is grounded in the existing repo structure, not an imaginary greenfield platform.

Current strongest runtime surfaces:

- `src/frontend/ui/app_controller.py`
- `src/frontend/ui/terminal.py`
- `src/core/sopotek_trading.py`
- `src/execution/execution_manager.py`
- `src/strategy/strategy.py`
- `src/strategy/strategy_registry.py`
- `src/backtesting/backtest_engine.py`
- `src/risk/trader_behavior_guard.py`

## Current State

Sopotek already has meaningful trading-platform pieces:

- broker adapters across crypto, forex, stocks, paper, and Stellar
- live charting, chart trading, detached workspaces, and operator tooling
- strategy selection and runtime signal generation
- execution management with order-state tracking
- behavioral safety controls and risk presets
- journaling, post-trade review, analytics, and Telegram/OpenAI tooling
- backtesting and optimization flows

What it does not yet have in a quant-fund sense:

- a dedicated market-data research layer
- a reusable feature engineering pipeline outside of strategies
- portfolio construction across multiple strategies
- institutional portfolio risk controls such as VaR/CVaR and correlation-aware limits
- formal research datasets, experiment tracking, and walk-forward validation
- true allocator and execution scheduling logic at fund level

## Target Architecture

```text
Market Data Store
-> Feature Pipeline
-> Signal Engine
-> Risk Approval Engine
-> Portfolio Allocator
-> Execution Engine
-> Monitoring / Analytics / Review
```

Each layer should be independently testable and replaceable.

## Phase Plan

### Phase 1: Quant Foundation

Goal:
- separate feature engineering from strategy logic
- standardize signal objects
- create a foundation for regime detection, ML research, and portfolio construction

Scope:
- add reusable feature pipeline module
- add standardized signal schema
- refactor strategy engine to consume the shared feature pipeline
- keep current UI and broker behavior working

Acceptance criteria:
- strategies still generate valid signals
- feature generation works from the shared pipeline
- signal output schema is stable and test-covered

Initial implementation:
- `src/quant/feature_pipeline.py`
- `src/quant/signal_schema.py`
- strategy integration through `src/strategy/strategy.py`

### Phase 2: Research Data Layer

Goal:
- create a proper historical and live data foundation for quant workflows

Scope:
- normalized market data snapshots and symbol metadata
- persistent historical storage by broker, symbol, timeframe
- optional macro/news/alternative data adapters
- replay-friendly interfaces for backtesting and model training

Proposed modules:
- `src/quant/data_models.py`
- `src/quant/data_hub.py`
- `src/storage/historical_market_store.py`

Acceptance criteria:
- a strategy or model can request historical datasets without touching broker adapters directly
- research datasets can be versioned by source, symbol, timeframe, and date range

### Phase 3: Regime Detection And Signal Layer

Goal:
- move from isolated strategies to a proper signal engine with ensemble support

Scope:
- add market regime classifier
- add signal normalizer and signal scoring
- allow multiple strategies or models to vote on one symbol

Proposed modules:
- `src/quant/regime_engine.py`
- `src/quant/signal_engine.py`
- `src/quant/model_registry.py`

Acceptance criteria:
- signal outputs include direction, confidence, reason, and regime context
- multiple strategies can be blended consistently

### Phase 4: Institutional Risk Layer

Goal:
- separate trader-behavior safety from portfolio-level risk management

Scope:
- keep `TraderBehaviorGuard` for operator protection
- add quant portfolio risk controls:
  - VaR
  - CVaR
  - volatility targeting
  - concentration limits
  - correlation-aware exposure limits
  - gross/net exposure controls

Proposed modules:
- `src/quant/portfolio_risk_engine.py`
- `src/quant/risk_models.py`

Acceptance criteria:
- strategies cannot route directly to execution without explicit risk approval
- portfolio-level risk can reject trades even when single-trade sizing looks valid

### Phase 5: Portfolio Allocator

Goal:
- allocate capital across strategies, not only symbols

Scope:
- strategy-level capital budgets
- risk-based weighting
- volatility scaling
- initial equal-risk and risk-parity allocators

Proposed modules:
- `src/quant/portfolio_allocator.py`
- `src/quant/allocation_models.py`

Acceptance criteria:
- multiple strategies can run under a shared capital budget
- portfolio weights are transparent and reviewable

### Phase 6: Smart Execution

Goal:
- reduce slippage and prepare for larger capital deployment

Scope:
- TWAP
- VWAP
- partial-fill scheduling
- execution quality benchmarking
- venue-aware routing where broker support exists

Proposed modules:
- extend `src/execution/smart_execution.py`
- add execution scheduling policy layer

Acceptance criteria:
- execution strategies can be selected independently from signal generation
- post-trade analytics can measure execution drag by route and algorithm

### Phase 7: Research And Validation Stack

Goal:
- make backtesting a real research environment

Scope:
- walk-forward testing
- commission and slippage modeling
- strategy experiment tracking
- parameter sweeps tied to datasets and regimes

Proposed modules:
- extend `src/backtesting/`
- add experiment metadata and evaluation summaries

Acceptance criteria:
- backtests are reproducible
- research outputs can be compared across symbols, periods, and regimes

### Phase 8: Quant PM And Monitoring Views

Goal:
- give the UI a portfolio-manager view, not only an operator terminal

Scope:
- strategy allocation dashboard
- exposure dashboard
- correlation heatmap
- capital-at-risk panel
- regime panel
- allocator and risk approval transparency

Acceptance criteria:
- the operator can see what capital is deployed, why, and under which risk model

### Phase 9: ML Research Stack

Goal:
- add a trainable ML layer that uses the shared quant features and can be deployed back into the signal engine

Scope:
- feature-to-label dataset builder
- lightweight trainable classifier models
- model registry with metadata
- experiment-linked ML training and evaluation
- deployment path from research model to live `ML Model` strategy

Proposed modules:
- `src/quant/ml_dataset.py`
- `src/quant/ml_models.py`
- `src/quant/ml_research.py`

Acceptance criteria:
- a model can be trained from historical candles using the shared feature pipeline
- the trained model can be evaluated and recorded as an experiment
- the trained model can be deployed into the strategy registry and generate live-compatible signals

## Priority Order

Recommended build order:

1. Phase 1: Quant Foundation
2. Phase 4: Institutional Risk Layer
3. Phase 5: Portfolio Allocator
4. Phase 2: Research Data Layer
5. Phase 3: Regime Detection And Signal Layer
6. Phase 6: Smart Execution
7. Phase 7: Research And Validation Stack
8. Phase 8: Quant PM And Monitoring Views
9. Phase 9: ML Research Stack

Reason:
- feature extraction and signal standardization are prerequisites
- institutional risk and allocation are what most clearly separate a trading app from a quant platform
- research data and regime logic become much cleaner after that foundation exists

## Repo Mapping

### Existing Files To Evolve

- `src/strategy/strategy.py`
  Keep strategy behavior, but remove direct ownership of complex feature engineering over time.

- `src/core/sopotek_trading.py`
  Evolve into coordinator of signal, risk, allocation, and execution layers.

- `src/execution/execution_manager.py`
  Keep as execution gate and state tracker, then extend it with execution policies.

- `src/engines/risk_engine.py`
  Keep for simple sizing checks in the short term; eventually supersede with a portfolio-level risk engine.

- `src/backtesting/backtest_engine.py`
  Expand toward research orchestration and reproducible validation.

### New Quant Namespace

The recommended namespace for new quant-fund primitives is:

- `src/quant/`

This keeps the evolution clear without destabilizing the existing UI- and broker-oriented module layout.

## Done Definition For The Quant Transition

Sopotek should be considered a quant-fund style platform when it can do all of the following:

- ingest normalized historical and live datasets
- compute reusable features outside strategy code
- run multiple strategies and/or ML models under one allocator
- enforce institutional portfolio risk before execution
- track execution quality beyond fill/no-fill
- evaluate strategies with reproducible research workflows
- expose portfolio, risk, regime, and strategy diagnostics clearly in the UI

## Immediate Next Step

Start with Phase 1.

That means:

- reusable feature pipeline
- standardized signal schema
- strategy refactor to consume the shared pipeline
- focused tests proving the foundation is stable
