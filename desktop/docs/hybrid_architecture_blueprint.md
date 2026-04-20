# Sopotek Hybrid Architecture Blueprint

## 1. Proposed Target Architecture

Sopotek Quant System should become a clean hybrid platform with three explicit runtime layers:

1. Desktop operator console
   The desktop remains the professional workstation. It owns operator interaction, charting, session UX, manual controls, local credential mediation, and visualization of authoritative server state.

2. Server trading core
   The server becomes the always-on trading brain. It owns market ingestion, signal generation, reasoning supervision, risk, portfolio, execution, monitoring, learning, persistence, reporting, and automation.

3. Shared context and contracts layer
   The shared layer becomes the canonical source of truth for transport models, event schemas, command schemas, identifiers, and context definitions. Desktop and server must speak only through this layer.

### Runtime shape

```text
PySide6 Desktop Console
  -> REST API Client
  -> WebSocket Stream Client
  -> Secure Local Credential Provider

Server Core
  -> FastAPI Command/API Surface
  -> WebSocket Streaming Hub
  -> Internal Event Bus
  -> Market / Strategy / Decision / Risk / Portfolio / Execution / Monitoring / Learning / Reporting services
  -> DB / Audit / Notifications / Broker Infrastructure

Shared Layer
  -> Contracts
  -> Commands
  -> Events
  -> Enums
  -> Validation models
  -> Session and correlation context
```

### Architectural intent

- Desktop-first UX is preserved.
- Server becomes authoritative for orders, positions, risk, automation, and trading state.
- Desktop remains resilient when the server is degraded by showing stale-state banners, reconnect status, and last known snapshots.
- The split is based on bounded contexts, not widget files or old modules.

## 2. Bounded Contexts And Ownership Table

| Context | Desktop owns | Server owns | Shared models | Transport |
| --- | --- | --- | --- | --- |
| IdentityContext | Login UI, register/reset hooks, local auth prompts | Auth validation, token issuing, password reset workflows, entitlement checks | `UserContext`, `SessionState`, response envelopes, error models | REST |
| SessionContext | Window routing, reconnect UX, local session cache, layout state | Session admission, heartbeat validation, stale-session handling, resumable state snapshots | `SessionContext`, `BrokerSessionSummary`, heartbeat models | REST + WebSocket |
| MarketContext | Charts, watchlists, local subscriptions, viewport state | Market feeds, normalization, candle aggregation, market snapshots | `SymbolSnapshot`, `CandleSnapshot`, `FeatureSnapshot` | WebSocket + REST snapshot |
| StrategyContext | Strategy status panels, enable or disable commands, explainability display | Strategy agents, feature pipelines, regime detection, signal generation | `StrategySignal`, `SignalBundle`, agent health models | REST commands + WebSocket events |
| DecisionContext | Decision review panels, operator acknowledgement, override requests | Signal fusion, tactical decision intent, reasoning supervision | `DecisionIntent`, `ReasoningReview`, decision events | WebSocket + REST |
| RiskContext | Risk status panels, risk-setting forms, degraded banners | Risk rules, drawdown checks, kill switch, cooldowns, approval or rejection | `RiskDecision`, risk settings commands, alert models | REST + WebSocket |
| PortfolioContext | Exposure displays, PnL views, account selector UI | Portfolio valuation, concentration checks, correlated exposure, holdings authority | `PortfolioDecision`, `PositionSnapshot`, portfolio summaries | WebSocket + REST snapshot |
| ExecutionContext | Manual order ticket, cancel/close actions, execution acknowledgements view | Idempotent order submission, broker routing, duplicate protection, fill handling | `ExecutionRequest`, `ExecutionResult`, lifecycle events | REST command + WebSocket events |
| MonitoringContext | Alerts view, banners, notification center, screenshot trigger UI | Health checks, broker-state monitoring, stale position logic, emergency actions | `MonitoringAlert`, `AgentHealthStatus`, monitoring context models | WebSocket |
| LearningContext | Journal/review UI, performance drill-downs | Trade journal, learning feedback, model promotion, reward scoring | `LearningFeedback`, outcome models, report contracts | REST + WebSocket |
| ReportingContext | Report trigger buttons, report browser, Telegram/report delivery status view | Report generation, Telegram/email delivery, audit-friendly summaries | report DTOs, notification DTOs | REST + WebSocket |
| UIContext | Window state, dock layout, local interaction state, chart preferences | none | UI-local only except explicit command DTOs | Local-only |

### Ownership rules

- Server-authoritative: orders, fills, positions, portfolio exposure, risk state, automation state, market subscriptions, strategy state, agent health, reports, journal outcomes.
- Desktop-authoritative: dock layout, open tabs, active chart overlays, local focus state, local credential selection, screenshot initiation, notification dismissal state.
- Shared-authoritative: protocol shape, identifiers, enums, command contracts, event schemas, response envelopes, correlation IDs.

## 3. Folder And Package Structure

The target structure is introduced under `sopotek/` as an additive refactor path:

```text
sopotek/
  apps/
    desktop/
      src/
        client/
        controllers/
    server/
      app/
        api/
          routes/
        ws/
  shared/
    commands/
    contracts/
    enums/
    events/
  services/
    decision/
    execution/
    risk/
  infrastructure/
    messaging/
    telemetry/
```

### Migration mapping from current code

- Current desktop UI under `src/ui` can migrate toward `sopotek/apps/desktop/src`.
- Current server work under `sqs_server` can migrate toward `sopotek/apps/server/app`.
- Existing engines and workers can be re-homed behind `sopotek/services/*`.
- Existing ad hoc payloads should gradually be replaced by `sopotek/shared/*`.

## 4. Shared Contract Design

The shared layer contains:

- canonical identifiers: user, session, broker, account, symbol
- transport envelopes with protocol version and correlation IDs
- command DTOs for desktop to server intent
- event DTOs for server to desktop streaming
- response envelopes for consistent REST behavior
- bounded-context models for session, market, signal, decision, risk, portfolio, execution, monitoring, learning, and reporting

### Required model examples

- `SessionState`
- `UserContext`
- `BrokerSessionSummary`
- `SymbolSnapshot`
- `FeatureSnapshot`
- `StrategySignal`
- `SignalBundle`
- `DecisionIntent`
- `ReasoningReview`
- `RiskDecision`
- `PortfolioDecision`
- `ExecutionRequest`
- `ExecutionResult`
- `PositionSnapshot`
- `TradeLifecycleEvent`
- `MonitoringAlert`
- `LearningFeedback`
- `AgentHealthStatus`
- `UICommand`
- `ServerEventEnvelope`

## 5. Event Flow Design

### Internal server flow

```text
market.ingested
-> features.computed
-> regime.updated
-> signal.generated
-> signal.bundle.ready
-> decision.intent.created
-> reasoning.review.completed
-> risk.evaluated
-> portfolio.evaluated
-> execution.requested
-> order.submitted
-> order.filled
-> position.updated
-> monitoring.alert.created
-> learning.feedback.created
-> report.generated
```

### Desktop-facing event flow

```text
session.validated
market.snapshot
candle.update
signal.generated
decision.updated
reasoning.review
risk.alert
portfolio.updated
order.updated
fill.received
position.updated
pnl.updated
agent.health.updated
report.ready
system.alert
```

## 6. API And WebSocket Design

### REST

Use REST for operator intent, commands, and request-response actions:

- `POST /api/v1/session/login`
- `POST /api/v1/session/resume`
- `POST /api/v1/trading/broker/connect`
- `POST /api/v1/trading/orders`
- `POST /api/v1/trading/orders/cancel`
- `POST /api/v1/trading/positions/close`
- `POST /api/v1/trading/automation`
- `POST /api/v1/trading/kill-switch`
- `POST /api/v1/trading/reports`

### WebSocket

Use WebSocket for:

- market snapshots and deltas
- signals and decisions
- risk and monitoring alerts
- portfolio and PnL updates
- execution acknowledgements
- agent health updates
- report readiness
- heartbeat and reconnect state

## 7. Authentication And Session Lifecycle

1. Desktop displays login screen.
2. Desktop submits credentials through REST.
3. Server validates user and returns `SessionState`.
4. Desktop opens WebSocket with session token.
5. Server begins streaming authoritative state and a session heartbeat.
6. Desktop stores local interaction state separately from server session state.
7. On reconnect, desktop resumes with session ID and last seen sequence.
8. Server rehydrates latest snapshots and resumes streaming from the authoritative state.

## 8. Failure, Reconnect, And Offline Behavior

### Required patterns

- heartbeat and ping from both sides
- explicit stale-session timeout
- sequence-aware event replay on reconnect
- idempotent `client_order_id` plus `correlation_id`
- duplicate command rejection on server
- degraded-mode banners on desktop
- global kill switch and max drawdown shutdown on server
- desktop remains usable for viewing stale snapshots and manual reporting even when automation services are degraded

### Reconnect and state rehydration

1. WebSocket disconnect occurs.
2. Desktop controller marks session as degraded.
3. Desktop keeps local chart state and command buttons disabled or reduced by policy.
4. Desktop reconnects with session token, session ID, and last seen event sequence.
5. Server responds with authoritative snapshots for session, market watch, portfolio, open orders, positions, and agent health.
6. Streaming resumes from the latest server state.

## 9. Refactor Plan In Phases

### Phase 1

- Extract shared contracts from current payloads.
- Introduce desktop REST and WebSocket client abstractions.
- Keep current logic local behind interfaces so UI stops talking directly to engines.

### Phase 2

- Move market data, broker state, risk, execution, and portfolio authority to server services.
- Desktop subscribes to authoritative state instead of owning these objects directly.

### Phase 3

- Move strategy agents, decision engine, reasoning supervision, monitoring, learning, journal, and reporting fully server-side.
- Desktop becomes the thin but rich operator console.

### Phase 4

- Add multi-user and SaaS readiness.
- Add server tenancy, workspace sharing, and web-client reuse of the same shared contracts.

## 10. Initial Code Skeleton

The initial skeleton added in this repo provides:

- server FastAPI shell and route skeletons
- desktop client abstractions for REST and WebSocket
- session controller with reconnect and credential-provider abstractions
- shared contracts, commands, and events with versioned envelopes
- service interfaces for decision, risk, and execution
- internal event bus and structured logging skeletons

## 11. Risks And Migration Notes

- Current desktop code is thick and stateful, so the first risk is partial ownership drift. Shared contracts reduce that risk.
- Manual trading workflows should migrate before autonomous strategy flows to preserve operator confidence.
- Broker credential handling must stay explicit. Desktop may broker local secrets to the server only through deliberate secure flows.
- Existing event names and payloads are mixed; migration adapters will be needed during the transition.
- The reasoning agent must remain supervisory only. Risk plus execution remain deterministic authorities.

## Example REST Request And Response

### Request

```json
POST /api/v1/trading/orders
{
  "command_type": "place_order",
  "session_id": "sess_123",
  "account_id": "acct_live_01",
  "payload": {
    "client_order_id": "cli_ord_1001",
    "symbol": "BTC/USD",
    "broker": "coinbase",
    "side": "buy",
    "order_type": "limit",
    "quantity": 0.25,
    "limit_price": 84250.0
  }
}
```

### Response

```json
{
  "success": true,
  "correlation_id": "corr_abc",
  "message": "Order accepted for execution review.",
  "data": {
    "order_id": "srv_ord_9001",
    "status": "accepted",
    "client_order_id": "cli_ord_1001"
  },
  "error": null
}
```

## Example WebSocket Event Envelope

```json
{
  "protocol_version": "1.0",
  "event_type": "portfolio.updated",
  "event_id": "evt_001",
  "correlation_id": "corr_abc",
  "causation_id": "cmd_123",
  "sequence": 144,
  "emitted_at": "2026-04-18T13:05:00Z",
  "payload": {
    "account_id": "acct_live_01",
    "equity": 150240.11,
    "cash": 42100.02,
    "gross_exposure": 0.46,
    "positions": []
  }
}
```

## Example Desktop Action Flow

1. Operator clicks `Buy` in the desktop terminal.
2. Desktop builds a typed `PlaceOrderCommand`.
3. Desktop sends the command to server REST.
4. Server validates session, deduplicates command, checks automation and kill-switch state.
5. Server routes the request through risk and execution orchestration.
6. Server emits `order.updated` and later `fill.received` over WebSocket.
7. Desktop updates the order blotter, terminal log, position panel, and alerts view.

## Example Reconnect And State Rehydration Flow

1. Desktop loses WebSocket connection.
2. Session controller marks the terminal as degraded and pauses trading actions according to policy.
3. Desktop reconnects with the last seen sequence number.
4. Server sends fresh `SessionState`, market subscriptions, orders, positions, agent health, and alert backlog.
5. Desktop redraws from authoritative snapshots and resumes live streaming.

## Example Order Placement Path

```text
Desktop order ticket
-> SessionController
-> ApiClient.place_order()
-> Server trading route
-> Execution service
-> Internal event bus
-> Broker adapter
-> ExecutionResult
-> WebSocket manager
-> Desktop WsClient
-> Terminal order/position panels
```
