"""Enumerations for authoritative server events streamed to desktop."""

from __future__ import annotations

from enum import Enum


class ServerEventType(str, Enum):
    SESSION_VALIDATED = "session.validated"
    STATE_REHYDRATED = "state.rehydrated"
    MARKET_SNAPSHOT = "market.snapshot"
    MARKET_WATCH_SNAPSHOT = "market.watch.snapshot"
    CANDLE_UPDATE = "candle.update"
    BROKER_STATUS_UPDATED = "broker.status.updated"
    ASSETS_SNAPSHOT = "assets.snapshot"
    POSITIONS_SNAPSHOT = "positions.snapshot"
    OPEN_ORDERS_SNAPSHOT = "open_orders.snapshot"
    ORDER_HISTORY_SNAPSHOT = "order_history.snapshot"
    TRADE_HISTORY_SNAPSHOT = "trade_history.snapshot"
    MARKET_SUBSCRIPTION_UPDATED = "market.subscription.updated"
    SIGNAL_GENERATED = "signal.generated"
    DECISION_UPDATED = "decision.updated"
    REASONING_REVIEW = "reasoning.review"
    RISK_ALERT = "risk.alert"
    PORTFOLIO_UPDATED = "portfolio.updated"
    ORDER_UPDATED = "order.updated"
    FILL_RECEIVED = "fill.received"
    POSITION_UPDATED = "position.updated"
    PNL_UPDATED = "pnl.updated"
    AGENT_HEALTH_UPDATED = "agent.health.updated"
    REPORT_READY = "report.ready"
    SYSTEM_ALERT = "system.alert"
