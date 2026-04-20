"""Risk bounded-context contracts shared by desktop and server.

Risk services own these models because policy enforcement must stay
deterministic and independent from UI or persistence implementation details.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.decision import TradeIntent
from contracts.enums import AlertSeverity, RiskDisposition


class RiskCommandName(str, Enum):
    EVALUATE_RISK_V1 = "risk.evaluate.v1"
    UPDATE_LIMITS_V1 = "risk.limits.update.v1"


class RiskEventName(str, Enum):
    RISK_CHECKED_V1 = "risk.checked.v1"
    RISK_ALERT_CREATED_V1 = "risk.alert.created.v1"


class RiskLimits(ContractModel):
    """Authoritative risk policy snapshot applied to trading decisions."""

    limit_id: str = Field(min_length=1)
    max_risk_per_trade_pct: float
    max_daily_drawdown_pct: float
    max_portfolio_drawdown_pct: float
    max_leverage: float
    max_correlated_exposure_pct: float
    max_orders_per_minute: int
    stale_signal_seconds: int
    cooldown_after_consecutive_losses: int = 0


class PositionSizing(ContractModel):
    """Deterministic sizing output from the risk engine."""

    quantity: float
    notional_value: float
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_reward: float | None = None
    risk_amount: float | None = None
    notes: list[str] = Field(default_factory=list)


class RiskCheckRequest(ContractModel):
    """Inputs required for one pre-trade risk evaluation."""

    trade_intent: TradeIntent
    account_id: str = Field(min_length=1)
    limits: RiskLimits
    portfolio_snapshot_id: str | None = None
    market_snapshot_id: str | None = None


class RiskCheckResult(ContractModel):
    """Result of a deterministic pre-trade risk evaluation."""

    intent_id: str = Field(min_length=1)
    disposition: RiskDisposition
    approved: bool
    sizing: PositionSizing | None = None
    violations: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=utc_now)


class RiskAlert(ContractModel):
    """Transport-safe risk alert emitted by enforcement services."""

    alert_id: str = Field(min_length=1)
    severity: AlertSeverity
    category: str = Field(min_length=1)
    message: str = Field(min_length=1)
    triggered_by: str = Field(min_length=1)
    triggered_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluateRiskCommand(ContractModel):
    """Command payload for deterministic risk review."""

    request: RiskCheckRequest


class UpdateRiskLimitsCommand(ContractModel):
    """Command payload used to publish new risk policy snapshots."""

    account_id: str = Field(min_length=1)
    limits: RiskLimits

