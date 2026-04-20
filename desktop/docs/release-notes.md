# Release Notes

## Version 1.0.0

Release date: March 31, 2026

`1.0.0` is the first publishable desktop release of Sopotek Quant System.

### Highlights

- desktop dashboard and terminal workflow for launching broker-backed or paper sessions
- MT4-style charting, detachable chart windows, order book views, depth views, and market info tabs
- manual trading ticket with broker-aware formatting, safety-aware sizing, and order feedback
- AI-assisted workflows including recommendations, Sopotek Pilot, and review-oriented runtime summaries
- Telegram remote console with menu-driven navigation, screenshots, chart captures, and confirmation-gated controls
- journaling, trade review, performance tooling, backtesting, and strategy optimization workflows
- runtime translation support for static UI labels plus dynamic summaries and rich-text views

### Release Readiness Notes

- prefer `paper`, `practice`, or `sandbox` validation before any meaningful live capital use
- validate broker login, candles, balances, positions, and manual order flow before enabling AI trading
- validate Telegram, OpenAI, and screenshot workflows only after the core trading path is healthy
- use `requirements.txt` for the full desktop runtime even though `pyproject.toml` now contains first-release package metadata

### Known Operational Constraints

- some broker capabilities remain venue-specific, so not every symbol or order type is supported across every adapter
- GUI, Telegram, OpenAI, and voice features are environment-sensitive and should be smoke-tested in the actual operator environment
- live execution remains powerful but high risk, so operator review, behavior guard, and kill-switch controls should stay part of the normal workflow

### First Release Focus

This first published version is focused on shipping a coherent operator workstation rather than maximizing breadth everywhere at once. The release priorities were:

- stable desktop startup and shutdown behavior
- realistic chart, order, and trade supervision workflows
- a usable Telegram remote console
- contributor-facing and operator-facing documentation that can support onboarding

## Runtime Extensions On April 1, 2026

The current runtime branch also adds a new adaptive AI supervision layer on top of the original `1.0.0` desktop release:

- a profile-aware `TraderAgent` that aggregates multi-agent signals and adapts decisions to investor goals and risk tolerance
- `MarketHoursEngine` support for crypto, forex, stock, and futures session gating, including NYSE holiday checks and forex liquidity windows
- `ProfitProtectionEngine` support for trailing stops, break-even logic, partial profit taking, time-based exits, volatility exits, and ML-guided exit decisions
- a production-oriented ML pipeline for feature engineering, dataset building, model training, inference, and retraining hooks
- regime detection, order-book intelligence, and reasoning output for more explainable signal generation
- normalized email and push alert delivery plus a file-backed mobile dashboard export
- `TradeJournalAIEngine` for automated post-trade analysis explaining why a trade lost, what worked, and what to improve next
- a file-backed feature store and SQL-backed quant persistence layer for research, retraining, and auditability

## Reliability Update On April 15, 2026

This update tightened a few operator-facing runtime paths that were producing noisy logs or environment-specific failures:

- `SignalAgent` now treats selector results of `None` as `HOLD` / no-entry outcomes instead of invalid signal payloads
- the `Adaptive Momentum Pullback` selector now evaluates only after feature rows and trend flags are initialized, avoiding `trend_down` local-variable crashes
- Coinbase JWT auth now loads `PyJWT` lazily and reports a clearer dependency error when the active environment is missing JWT support
- the Docker image and Compose profiles were aligned with the current script layout so `app`, `app-headless`, and `app-http` can build and start from the repo more consistently
- documentation and repo metadata were cleaned up so README, MkDocs, and troubleshooting guidance all point at the current `nguemechieu/sopotek_quant_system` repository
