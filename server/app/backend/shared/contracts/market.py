"""Shared market-context contracts for Sopotek."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from shared.contracts.base import SharedModel, SymbolIdentifier, utc_now


class SymbolSnapshot(SharedModel):
    """Server-authoritative snapshot of a subscribed symbol."""

    identifier: SymbolIdentifier
    last_price: float
    bid: float | None = None
    ask: float | None = None
    volume: float = 0.0
    volatility: float | None = None
    trend: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)


class CandleSnapshot(SharedModel):
    """Shared candle snapshot used by charts and strategy services."""

    identifier: SymbolIdentifier
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    start_at: datetime
    end_at: datetime


class FeatureSnapshot(SharedModel):
    """Feature engineering output shared with strategy and decision services."""

    identifier: SymbolIdentifier
    features: dict[str, float] = Field(default_factory=dict)
    source: str = "feature_engine"
    timestamp: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)

