"""Signal bounded-context contracts shared by desktop and server.

Strategy and feature services own these payloads. Desktop may render them, but
it should not redefine their shape.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from contracts.base import ContractModel, utc_now
from contracts.enums import TradeSide, VenueKind


class SignalCommandName(str, Enum):
    COMPUTE_FEATURE_VECTOR_V1 = "signal.features.compute.v1"
    EVALUATE_SIGNALS_V1 = "signal.evaluate.v1"
    FUSE_SIGNALS_V1 = "signal.fuse.v1"


class SignalEventName(str, Enum):
    FEATURE_VECTOR_READY_V1 = "signal.features.ready.v1"
    SIGNAL_GENERATED_V1 = "signal.generated.v1"
    SIGNAL_BUNDLE_READY_V1 = "signal.bundle.ready.v1"


class FeatureVector(ContractModel):
    """Feature engineering output owned by the analysis layer."""

    feature_vector_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    timeframe: str = Field(min_length=1)
    feature_set: str = Field(min_length=1)
    values: dict[str, float] = Field(default_factory=dict)
    computed_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalReason(ContractModel):
    """Structured explanation attached to a generated signal."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    weight: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StrategySignal(ContractModel):
    """Single strategy opinion produced by one signal-generating worker."""

    signal_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    strategy_name: str = Field(min_length=1)
    side: TradeSide
    confidence: float
    score: float = 0.0
    timeframe: str = Field(min_length=1)
    suggested_entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    holding_period_seconds: int | None = None
    feature_vector_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    reasons: list[SignalReason] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalBundle(ContractModel):
    """Grouped strategy outputs for one symbol and evaluation window."""

    bundle_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    venue: VenueKind
    timeframe: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    regime: str | None = None
    stale_after_seconds: int = 60
    signals: list[StrategySignal] = Field(default_factory=list)


class ComputeFeatureVectorCommand(ContractModel):
    """Request for deterministic feature computation from market inputs."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    timeframe: str = Field(min_length=1)
    feature_set: str = Field(min_length=1)


class EvaluateSignalsCommand(ContractModel):
    """Request for strategy services to emit fresh signal opinions."""

    symbol: str = Field(min_length=1)
    venue: VenueKind
    timeframe: str = Field(min_length=1)
    feature_vector_id: str | None = None


class FuseSignalsCommand(ContractModel):
    """Request for the decision layer to consolidate a signal bundle."""

    bundle_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    timeframe: str = Field(min_length=1)

