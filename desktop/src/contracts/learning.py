"""Learning bounded-context contracts shared by desktop and server.

Learning and research services own these payloads. They capture post-trade
outcomes and model lifecycle state without coupling to ML frameworks.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import LearningOutcome


class LearningCommandName(str, Enum):
    RECORD_TRADE_OUTCOME_V1 = "learning.trade_outcome.record.v1"
    PROMOTE_MODEL_V1 = "learning.model.promote.v1"


class LearningEventName(str, Enum):
    TRADE_OUTCOME_RECORDED_V1 = "learning.trade_outcome.recorded.v1"
    LEARNING_FEEDBACK_READY_V1 = "learning.feedback.ready.v1"
    MODEL_PROMOTED_V1 = "learning.model.promoted.v1"


class TradeOutcome(ContractModel):
    """Closed-trade outcome owned by the learning feedback loop."""

    trade_id: str = Field(min_length=1)
    intent_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    strategy_name: str = Field(min_length=1)
    regime: str | None = None
    outcome: LearningOutcome
    pnl: float
    pnl_pct: float
    holding_duration_seconds: int
    closed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningFeedback(ContractModel):
    """Learning-ready feedback derived from actual trade outcomes."""

    feedback_id: str = Field(min_length=1)
    trade_outcome: TradeOutcome
    reward_score: float
    prediction_error: float | None = None
    feature_vector_id: str | None = None
    notes: list[str] = Field(default_factory=list)
    recorded_at: datetime = Field(default_factory=utc_now)


class StrategyWeightUpdate(ContractModel):
    """Weight adjustment proposal for regime-aware strategy selection."""

    strategy_name: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    previous_weight: float
    new_weight: float
    reason: str = Field(min_length=1)
    effective_at: datetime = Field(default_factory=utc_now)


class ModelPromotion(ContractModel):
    """Model lifecycle event independent from any concrete ML toolkit."""

    model_id: str = Field(min_length=1)
    model_name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    promoted_by: str = Field(min_length=1)
    promoted_at: datetime = Field(default_factory=utc_now)
    metrics: dict[str, float] = Field(default_factory=dict)


class RecordTradeOutcomeCommand(ContractModel):
    """Command payload requesting a new learning record."""

    trade_outcome: TradeOutcome


class PromoteModelCommand(ContractModel):
    """Command payload requesting model promotion metadata publication."""

    promotion: ModelPromotion

