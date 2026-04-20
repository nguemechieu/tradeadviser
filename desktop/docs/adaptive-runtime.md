# Adaptive Runtime Guide

Sopotek now includes an event-driven AI runtime layer on top of the desktop workstation. This runtime is designed to behave more like a supervised quant stack than a simple signal bot: it can filter when trading is allowed, aggregate strategy votes, manage exits, persist live features, explain decisions, generate alerts, and learn from closed trades.

## Core Runtime Services

| Component | Main role | Key behaviors |
| --- | --- | --- |
| `TraderAgent` | Profile-aware final decision maker | Aggregates `Trend`, `Mean Reversion`, `Breakout`, and `ML` signals, applies investor profile constraints, sizes trades by confidence and ML probability bands, and emits explainable final decisions |
| `InvestorProfile` | Personalized trading policy | Stores `risk_level`, `goal`, `max_drawdown`, `trade_frequency`, `preferred_assets`, and `time_horizon` so the system can behave differently for conservative versus aggressive users |
| `MarketHoursEngine` | Session and market gate | Supports `crypto`, `forex`, `stocks`, and `futures`, enforces open or closed windows, detects forex sessions, flags high-liquidity windows, and respects NYSE holidays |
| `ProfitProtectionEngine` | Live exit protection | Uses trailing stops, break-even promotion, partial profit tiers, time-based exits, volatility exits, and ML-guided reduce or exit actions so profitable trades do not drift back into losses |
| `TradeOutcomeTrainingPipeline` and `sopotek.ml.*` | Outcome-learning pipeline | Builds features, constructs datasets, trains classifiers, stores model artifacts, and produces inference scores used by the live runtime |
| `RegimeEngine` | Regime classification | Labels live context using clustering when available and heuristic fallback logic when not, so strategy selection and risk filters can adapt to changing market conditions |
| `FeatureEngine` and order-book features | Live feature extraction | Produces RSI, EMA, volatility, return, bid or ask imbalance, spread, depth, and liquidity context for trading, filtering, and journaling |
| `ReasoningAgent` | Explainability layer | Publishes human-readable rationales that combine trend, RSI, volatility, regime, and order-book context into operator-facing reasons |
| `TradeJournalAIEngine` | Post-trade coaching | Converts closed trades into structured journal entries that answer why a trade lost, what worked, and what to improve, then builds rolling summaries |
| `AlertingEngine` | Operational alert dispatch | Normalizes execution, risk, ML rejection, and profit-protection events into alerts and can send them through email or push channels in addition to Telegram-oriented workflows |
| `MobileDashboardService` | Mobile-friendly snapshot export | Writes live snapshots and summaries to disk so a lightweight mobile or web client can consume current state without loading the full desktop app |
| `FeatureStore` | File-backed runtime telemetry | Writes JSONL streams for feature vectors, model scores, reasoning, trader decisions, alerts, dashboard updates, and trade-journal events under `data/feature_store` |

## Event-Driven Flow

The runtime is centered around the event bus:

1. `MARKET_DATA_EVENT`, candles, and order-book updates feed the feature and analysis layers.
2. Strategy agents emit `SIGNAL` and `SIGNAL_EVENT`.
3. `TraderAgent` aggregates those signals, applies investor profile rules, market-hours checks, and ML confidence filters, then emits `DECISION_EVENT` and order intents.
4. `RiskEngine`, `ExecutionEngine`, and `ProfitProtectionEngine` manage approval, placement, and live position protection.
5. `TradeFeedbackEngine` closes the loop by publishing `TRADE_FEEDBACK`.
6. `TradeJournalAIEngine` turns that feedback into `TRADE_JOURNAL_ENTRY` and `TRADE_JOURNAL_SUMMARY`.
7. `AlertingEngine`, `FeatureStore`, and `MobileDashboardService` persist or distribute the resulting telemetry.

## Example Runtime Configuration

```python
from sopotek.agents import InvestorProfile
from sopotek.core.orchestrator import SopotekRuntime

runtime = SopotekRuntime(
    broker=broker,
    enable_default_agents=True,
    enable_ml_filter=True,
    enable_trader_agent=True,
    enable_market_hours=True,
    enable_profit_protection=True,
    enable_feature_store=True,
    enable_alerting=True,
    enable_mobile_dashboard=True,
    enable_trade_journal_ai=True,
    trader_profiles={
        "growth": InvestorProfile(
            risk_level="medium",
            goal="growth",
            max_drawdown=0.10,
            trade_frequency="medium",
            preferred_assets=["BTC/USDT", "ETH/USDT"],
            time_horizon="medium",
        )
    },
    active_trader_profile="growth",
    profit_protection_kwargs={
        "trailing_stop_mode": "hybrid",
        "trailing_stop_pct": 0.045,
        "break_even_profit_pct": 0.01,
        "partial_profit_levels": [(0.02, 0.5)],
    },
    trade_journal_kwargs={
        "summary_window": 50,
        "publish_summary_every": 1,
    },
    alerting_kwargs={
        "email_config": {
            "host": "smtp.example.com",
            "port": 587,
            "username": "alerts@example.com",
            "password": "secret",
            "from_addr": "alerts@example.com",
            "to_addrs": ["operator@example.com"],
        },
        "push_config": {
            "endpoint_url": "https://push-gateway.example.com/alerts",
            "auth_token": "push-token",
        },
    },
)
```

## Persisted Outputs

### Feature Store

By default the runtime writes JSONL streams to `data/feature_store`. Common files include:

- `feature_vectors.jsonl`
- `order_book.jsonl`
- `model_scores.jsonl`
- `regime.jsonl`
- `reasoning.jsonl`
- `trader_decisions.jsonl`
- `alerts.jsonl`
- `mobile_dashboard.jsonl`
- `trade_journal_entries.jsonl`
- `trade_journal_summaries.jsonl`

These streams are useful for retraining, operator review, debugging, and later analytics work.

### Mobile Dashboard

By default the mobile dashboard writes to `data/mobile_dashboard`:

- `snapshot.json` for the full current view
- `summary.json` for a compact status snapshot
- `alerts.jsonl` for the recent alert feed

The snapshot includes equity, realized and unrealized PnL, drawdown, open positions, the latest trader decision, the latest execution report, and the latest trade-journal summary.

### Quant Persistence

The SQL-backed quant repository stores feature vectors, model scores, performance metrics, trade feedback, trade-journal entries, and trade-journal summaries so the runtime can be audited and replayed after the fact.

## Operational Guidance

- Start with `paper`, `practice`, or `sandbox` when enabling the adaptive runtime for the first time.
- Verify that `data/feature_store` and `data/mobile_dashboard` are being populated before trusting downstream automation.
- Use `MarketHoursEngine` and `ProfitProtectionEngine` together if you want professional-style session gating plus live profit defense.
- Configure email or push channels only after broker connectivity, execution, and logging are already stable.
- Review trade-journal summaries regularly; they are meant to tighten the strategy loop, not just archive trades.

## Related Docs

- [Architecture](architecture.md)
- [Internal API Notes](api.md)
- [Testing And Operations](testing-and-operations.md)
- [Release Notes](release-notes.md)
