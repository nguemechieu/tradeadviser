# Sopotek Institutional Platform Architecture

## System Overview

Sopotek is designed as a hybrid trading platform:

- Desktop: PySide6 trading terminal with PyQtGraph charts, operator controls, and multi-exchange connectivity.
- Cloud backend: FastAPI-based control plane, institutional intelligence, orchestration, persistence, and compliance.
- Messaging backbone: Kafka is the source of truth for cross-service workflows, replay, and asynchronous coordination.

The desktop never owns strategy execution or private market intelligence. It acts as an authenticated terminal for:

- operator login and device session binding
- real-time market and portfolio visualization
- order intent entry
- strategy controls and oversight
- incident acknowledgement and manual overrides

Server-side services own execution, risk, licensing, agent reasoning, and persistence so policy enforcement cannot be bypassed from the desktop.

## Folder Structure

```text
server_app/
  backend/
    app/
      institutional/
        __init__.py
        agents.py
        blueprints.py
        brokerage.py
        config.py
        database.py
        event_bus.py
        events.py
        example_gateway.py
        risk.py
        services/
          __init__.py
          base.py
          api_gateway.py
          auth_service.py
          user_profile_service.py
          license_subscription_service.py
          trading_core_service.py
          risk_engine_service.py
          portfolio_service.py
          market_data_service.py
          ai_agent_service.py
          ml_training_pipeline.py
          notification_service.py
    tests/
      test_institutional_gateway.py
docs/
  architecture/
    institutional-platform.md
```

## Backend Services

| Service | Responsibility | Publishes | Consumes |
| --- | --- | --- | --- |
| API Gateway | Edge ingress for desktop, web, admin, and partner clients | `order.created`, `risk.alert` | `order.executed`, `portfolio.update`, `risk.alert` |
| Auth Service | JWT, OAuth, RBAC, device sessions, token rotation | `auth.session.created` | `subscription.updated` |
| User/Profile Service | Trader preferences, watchlists, broker profile metadata | `portfolio.update` | `auth.session.created` |
| License & Subscription Service | Stripe billing, entitlement checks, license validation | `subscription.updated`, `notification.dispatch` | `auth.session.created` |
| Trading Core Service | Strategy execution, order lifecycle, smart routing | `order.created`, `order.executed` | `strategy.signal`, `risk.alert` |
| Risk Engine Service | Hard limits, sizing, drawdown control, liquidation logic | `risk.alert` | `order.created`, `order.executed`, `portfolio.update` |
| Portfolio Service | Cross-venue holdings, exposure, valuation, PnL | `portfolio.update` | `order.executed`, `market.tick`, `market.candle` |
| Market Data Service | WebSocket and REST ingestion, normalization, replay | `market.tick`, `market.candle` | none |
| AI Agent Service | Master/market/strategy/risk/execution/learning agent mesh | `strategy.signal`, `risk.alert`, `notification.dispatch` | `market.tick`, `market.candle`, `portfolio.update` |
| ML Training Pipeline | Feature engineering, backtesting, retraining, promotion | `ml.model.promoted`, `notification.dispatch` | `order.executed`, `portfolio.update` |
| Notification Service | Desktop, email, SMS, push, Telegram delivery | `notification.dispatch` | `risk.alert`, `order.executed`, `subscription.updated` |

The code skeletons for these live in [server_app/backend/app/institutional/services](../../server_app/backend/app/institutional/services).

## Event-Driven Design

Required Kafka topics:

- `market.tick`: normalized best bid/ask and last price updates
- `market.candle`: OHLCV bar stream for technical features and replay
- `strategy.signal`: ranked signal candidates with confidence, regime, and rationale
- `order.created`: validated order intent routed toward a broker venue
- `order.executed`: immutable fill events from broker acknowledgements
- `risk.alert`: hard/soft limit breaches, throttles, and liquidation triggers
- `portfolio.update`: account revaluation, positions, and exposure updates

Event envelopes are defined in [server_app/backend/app/institutional/events.py](../../server_app/backend/app/institutional/events.py). Each envelope carries:

- `event_id`
- `topic`
- `event_type`
- `occurred_at`
- `producer`
- `correlation_id`
- `causation_id`
- `tenant_id`
- `user_id`
- `payload`

The example gateway exposes machine-readable schemas at `GET /v1/architecture/events`.

## Trading Core and Broker Abstraction

Broker adapters are modeled in [server_app/backend/app/institutional/brokerage.py](../../server_app/backend/app/institutional/brokerage.py).

Supported venues:

- CCXT for crypto
- OANDA for FX
- Alpaca for equities

The `SmartOrderRouter` ranks candidate venues by:

- expected latency
- venue fees
- expected slippage
- account and asset-class eligibility

Institutional expansion points:

- multi-account fanout by strategy sleeve
- internal crossing or dark routing layer
- venue health and kill switches
- TCA feedback loop into route scoring

## Institutional Risk Model

Risk primitives are implemented in [server_app/backend/app/institutional/risk.py](../../server_app/backend/app/institutional/risk.py).

Guardrails included:

- max risk per trade
- max portfolio exposure
- daily drawdown limit
- position sizing from entry/stop distance
- auto liquidation trigger when drawdown breaches a harder threshold

This keeps sizing and kill-switch decisions server-side and deterministic.

## AI Multi-Agent Flow

Agent topology is defined in [server_app/backend/app/institutional/agents.py](../../server_app/backend/app/institutional/agents.py).

Interaction flow:

1. Market Agent consumes `market.tick` and `market.candle` and extracts volatility and regime features.
2. Strategy Agent ranks candidate trades and emits `strategy.signal`.
3. Master Agent correlates signal quality, entitlements, and context across the desk.
4. Risk Agent validates exposure, drawdown, and policy boundaries.
5. Execution Agent optimizes venue selection and publishes `order.created`.
6. Trading Core submits orders and emits `order.executed`.
7. Portfolio Service revalues holdings and emits `portfolio.update`.
8. Learning Agent uses paper/live outcomes to schedule retraining and model promotion.

## ML Training Pipeline

Institutional ML responsibilities:

- feature engineering: EMA, RSI, ATR, realized volatility, microstructure drift
- model families: XGBoost for supervised alpha, HMM for regime inference
- backtesting engine with walk-forward validation and replay
- continuous retraining loop from paper trading and live execution outcomes
- model registry and promotion process backed by object storage and experiment metadata

The scaffold for this bounded context lives in [server_app/backend/app/institutional/services/ml_training_pipeline.py](../../server_app/backend/app/institutional/services/ml_training_pipeline.py).

## Database Design

Primary storage layout is defined in [server_app/backend/app/institutional/database.py](../../server_app/backend/app/institutional/database.py).

Persistence tiers:

- PostgreSQL: identities, subscriptions, broker accounts, orders, executions, portfolios, risk policies, agent decisions, ML experiments, notification logs, event journal
- Redis: sessions, market snapshots, portfolio hot paths, live risk materializations
- Object storage: model artifacts, market replay, agent traces, compliance logs

The example gateway exposes this catalog at `GET /v1/architecture/database`.

## API Surface

The endpoint catalog is defined in [server_app/backend/app/institutional/blueprints.py](../../server_app/backend/app/institutional/blueprints.py) and exposed by `GET /v1/architecture/endpoints`.

Representative operator APIs:

- `POST /v1/auth/login`
- `POST /v1/licenses/validate`
- `POST /v1/orders`
- `GET /v1/orders/{order_id}`
- `POST /v1/risk/evaluate-order`
- `GET /v1/portfolio/{account_id}`
- `WS /v1/market/stream`
- `POST /v1/agents/master/cycle`
- `POST /v1/ml/backtest`

## Desktop Terminal

The desktop terminal should remain intentionally thin:

- login screen and device registration
- dashboard and terminal workspace
- real-time charts via PyQtGraph
- strategy controls and oversight
- multi-exchange account visibility
- live alerts and notification acknowledgements

All strategy execution, sizing, and order dispatch run on the backend.

## Security

Mandatory controls:

- encrypted broker credentials using KMS/HSM-backed references
- JWT plus refresh rotation and device session binding
- OAuth support for broker-adjacent identity flows
- RBAC for admin, trader, risk, and observer roles
- server-side execution only
- Kafka replay and audit journaling
- immutable execution ledger
- feature gating tied to subscription entitlements

## Deployment

Production topology:

- Dockerized services for every bounded context
- Kubernetes deployment per service with HPA and PDB policies
- Kafka as central event bus
- PostgreSQL primary with replicas
- Redis cluster for session and hot-path caching
- object storage for models, replays, and logs
- CI/CD with build, tests, security scan, image publish, and progressive rollout

Suggested runtime topology:

```text
PySide6 Desktop
  -> API Gateway
  -> Auth / License / User services
  -> Kafka
  -> Trading Core / Risk / Portfolio / Market Data / AI Agents / ML / Notifications
  -> PostgreSQL / Redis / Object Storage
```

## Working Example Service

The runnable FastAPI reference is [server_app/backend/app/institutional/example_gateway.py](../../server_app/backend/app/institutional/example_gateway.py).

It demonstrates:

- architecture discovery endpoints
- in-memory event bus wiring
- pre-trade risk validation
- smart broker routing
- `order.created` and `order.executed` event flow
- `portfolio.update` and notification side effects

Run it from `server_app/backend` with:

```bash
uvicorn app.institutional.example_gateway:app --reload
```
