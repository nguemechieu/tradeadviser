"""Shared trading-context contracts for Sopotek desktop and server."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from shared.contracts.base import AgentContext, BrokerIdentifier, SharedModel, SymbolIdentifier, utc_now
from shared.enums.common import AlertSeverity, DecisionAction, ExecutionStatus, OrderSide, OrderType


class StrategySignal(SharedModel):
    """One strategy agent opinion owned by the server strategy layer."""

    signal_id: str
    identifier: SymbolIdentifier
    strategy_name: str
    side: OrderSide
    confidence: float
    reasons: list[str] = Field(default_factory=list)
    stop_loss: float | None = None
    take_profit: float | None = None
    holding_time_seconds: int | None = None
    created_at: datetime = Field(default_factory=utc_now)


class SignalBundle(SharedModel):
    """Collection of strategy signals for one symbol and decision window."""

    bundle_id: str
    identifier: SymbolIdentifier
    signals: list[StrategySignal] = Field(default_factory=list)
    regime: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class DecisionIntent(SharedModel):
    """Final tactical intent produced by server-side signal fusion."""

    intent_id: str
    identifier: SymbolIdentifier
    action: DecisionAction
    confidence: float
    selected_strategy: str
    supporting_agents: list[str] = Field(default_factory=list)
    rejected_agents: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ReasoningReview(SharedModel):
    """Supervisory reasoning review attached to one decision intent."""

    intent_id: str
    approved: bool
    override_action: DecisionAction | None = None
    confidence_adjustment: float = 0.0
    notes: list[str] = Field(default_factory=list)
    context: AgentContext
    reviewed_at: datetime = Field(default_factory=utc_now)


class RiskDecision(SharedModel):
    """Deterministic risk evaluation result owned by the server risk engine."""

    intent_id: str
    approved: bool
    position_size: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None
    notes: list[str] = Field(default_factory=list)


class PortfolioDecision(SharedModel):
    """Portfolio-level approval or reduction decision."""

    intent_id: str
    approved: bool
    reason: str
    suggested_action: str | None = None
    size_multiplier: float = 1.0


class ExecutionRequest(SharedModel):
    """Server-authoritative execution request handed to broker infrastructure."""

    client_order_id: str
    broker: BrokerIdentifier
    identifier: SymbolIdentifier
    side: OrderSide
    order_type: OrderType
    quantity: float
    limit_price: float | None = None
    stop_price: float | None = None
    reduce_only: bool = False
    correlation_id: str | None = None


class ExecutionResult(SharedModel):
    """Execution acknowledgement or fill state returned by server execution."""

    order_id: str
    status: ExecutionStatus
    client_order_id: str
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    broker_order_id: str | None = None
    message: str = ""
    timestamp: datetime = Field(default_factory=utc_now)


class PositionSnapshot(SharedModel):
    """Server-authoritative position snapshot for desktop rendering."""

    position_id: str
    identifier: SymbolIdentifier
    quantity: float
    average_price: float
    mark_price: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    updated_at: datetime = Field(default_factory=utc_now)


class TradeLifecycleEvent(SharedModel):
    """Typed lifecycle event for order and trade state transitions."""

    event_id: str
    order_id: str
    event_type: str
    status: ExecutionStatus
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class MonitoringAlert(SharedModel):
    """Monitoring or risk alert surfaced to desktop and reporting channels."""

    alert_id: str
    severity: AlertSeverity
    source: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=utc_now)


class LearningFeedback(SharedModel):
    """Trade-outcome feedback for learning and journal pipelines."""

    feedback_id: str
    trade_id: str
    identifier: SymbolIdentifier
    reward_score: float
    outcome: str
    notes: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=utc_now)


class AgentHealthStatus(SharedModel):
    """Health snapshot for one server-side trading agent or subsystem."""

    agent_name: str
    status: str
    latency_ms: float = 0.0
    last_error: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)

