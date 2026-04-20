"""Portfolio bounded-context contracts shared by desktop and server.

The portfolio service owns authoritative account-level state. Desktop consumes
these DTOs for display; server-side control layers consume them for decisions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.decision import TradeIntent
from contracts.enums import VenueKind


class PortfolioCommandName(str, Enum):
    REVALUE_PORTFOLIO_V1 = "portfolio.revalue.v1"
    EVALUATE_CONSTRAINTS_V1 = "portfolio.constraints.evaluate.v1"
    MODIFY_POSITION_SL_V1 = "portfolio.modify.stoploss.v1"
    MODIFY_POSITION_TP_V1 = "portfolio.modify.takeprofit.v1"
    ENABLE_TRAILING_STOP_V1 = "portfolio.enable.trailingstop.v1"


class PortfolioEventName(str, Enum):
    PORTFOLIO_UPDATED_V1 = "portfolio.updated.v1"
    PORTFOLIO_CONSTRAINTS_EVALUATED_V1 = "portfolio.constraints.evaluated.v1"


class PositionSnapshot(ContractModel):
    """Cross-boundary position DTO owned by the portfolio service."""

    position_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    quantity: float
    average_price: float
    last_price: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    exposure_pct: float = 0.0
    # Risk management fields
    stop_loss: float | None = None
    take_profit: float | None = None
    trailing_stop_enabled: bool = False
    trailing_stop_distance: float | None = None
    trailing_stop_percent: float | None = None
    opened_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AllocationSlice(ContractModel):
    """Portfolio allocation slice used for rebalancing or constraint checks."""

    symbol: str = Field(min_length=1)
    target_weight: float
    actual_weight: float
    risk_weight: float = 0.0


class CorrelationExposure(ContractModel):
    """Correlation-aware exposure relationship between two symbols."""

    left_symbol: str = Field(min_length=1)
    right_symbol: str = Field(min_length=1)
    correlation: float
    combined_exposure_pct: float


class PortfolioSnapshot(ContractModel):
    """Authoritative account-level snapshot for risk and reporting flows."""

    snapshot_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    base_currency: str = Field(min_length=1)
    cash: float
    equity: float
    gross_exposure: float = 0.0
    net_exposure: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    positions: list[PositionSnapshot] = Field(default_factory=list)
    allocations: list[AllocationSlice] = Field(default_factory=list)
    correlations: list[CorrelationExposure] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utc_now)


class PortfolioConstraintResult(ContractModel):
    """Result of account-level concentration and exposure checks."""

    approved: bool
    reason: str = Field(min_length=1)
    suggested_action: str | None = None
    suggested_size_multiplier: float | None = None
    notes: list[str] = Field(default_factory=list)


class RevaluePortfolioCommand(ContractModel):
    """Request a fresh portfolio snapshot from the source of truth."""

    account_id: str = Field(min_length=1)


class EvaluatePortfolioConstraintsCommand(ContractModel):
    """Request account-level validation for a pending trade intent."""

    trade_intent: TradeIntent
    portfolio_snapshot: PortfolioSnapshot


class ModifyPositionStopLossCommand(ContractModel):
    """Command to modify the stop loss price on an open position."""

    position_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    new_stop_loss_price: float
    reason: str | None = None


class ModifyPositionTakeProfitCommand(ContractModel):
    """Command to modify the take profit price on an open position."""

    position_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    new_take_profit_price: float
    reason: str | None = None


class EnableTrailingStopCommand(ContractModel):
    """Command to activate a trailing stop on an open position."""

    position_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    trailing_stop_distance: float | None = None
    trailing_stop_percent: float | None = None
    reason: str | None = None
