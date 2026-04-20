"""Decision bounded-context contracts shared by desktop and server.

The decision layer owns trade intents and final tactical choices. Desktop may
display or request review, but the server-side decision service remains the
source of truth once automation is enabled.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import DecisionAction, TradeSide, VenueKind


class DecisionCommandName(str, Enum):
    REVIEW_TRADE_INTENT_V1 = "decision.review.v1"
    CONFIRM_TRADE_INTENT_V1 = "decision.confirm.v1"


class DecisionEventName(str, Enum):
    TRADE_INTENT_CREATED_V1 = "decision.intent.created.v1"
    TRADE_INTENT_REVIEWED_V1 = "decision.intent.reviewed.v1"


class DecisionReason(ContractModel):
    """Structured reason emitted by fusion or reasoning services."""

    code: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    contributor: str | None = None
    confidence_delta: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TradeIntent(ContractModel):
    """Authoritative decision payload handed off to risk and portfolio layers."""

    intent_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    action: DecisionAction
    side: TradeSide
    confidence: float
    selected_strategy: str = Field(min_length=1)
    supporting_strategies: list[str] = Field(default_factory=list)
    rejected_strategies: list[str] = Field(default_factory=list)
    requested_entry: float | None = None
    max_slippage_bps: float | None = None
    timeframe: str = Field(min_length=1)
    regime: str | None = None
    bundle_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    reasons: list[DecisionReason] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionReview(ContractModel):
    """Supervisory reasoning review attached to one trade intent."""

    intent_id: str = Field(min_length=1)
    approved: bool
    override_action: DecisionAction | None = None
    confidence_adjustment: float = 0.0
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime = Field(default_factory=utc_now)
    notes: list[str] = Field(default_factory=list)


class ReviewTradeIntentCommand(ContractModel):
    """Request a reasoning or supervisory review for a trade intent."""

    trade_intent: TradeIntent
    reviewer_role: str = Field(min_length=1)
    allow_override: bool = True


class ConfirmTradeIntentCommand(ContractModel):
    """Request to confirm an intent before risk and execution handoff."""

    intent_id: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)

