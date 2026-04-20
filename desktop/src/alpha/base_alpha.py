from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

import pandas as pd


@dataclass(slots=True)
class MarketRegime:
    primary: str = "MEAN_REVERTING"
    active_regimes: tuple[str, ...] = ("MEAN_REVERTING",)
    adx: float = 0.0
    atr_pct: float = 0.0
    realized_volatility: float = 0.0
    liquidity_score: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary": self.primary,
            "active_regimes": list(self.active_regimes),
            "adx": self.adx,
            "atr_pct": self.atr_pct,
            "realized_volatility": self.realized_volatility,
            "liquidity_score": self.liquidity_score,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AlphaContext:
    symbol: str
    timeframe: str = "1h"
    frame: pd.DataFrame | None = None
    feature_frame: pd.DataFrame | None = None
    candles: list[Any] = field(default_factory=list)
    order_book: Mapping[str, Any] | None = None
    cross_sectional_frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    regime: MarketRegime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def latest_price(self) -> float:
        frame = self.feature_frame if self.feature_frame is not None and not self.feature_frame.empty else self.frame
        if frame is None or frame.empty:
            return 0.0
        try:
            return float(frame.iloc[-1].get("close") or 0.0)
        except Exception:
            return 0.0


@dataclass(slots=True)
class AlphaSignal:
    symbol: str
    expected_return: float
    confidence: float
    horizon: str
    risk_estimate: float
    side: str
    model_name: str
    score: float
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "expected_return": self.expected_return,
            "confidence": self.confidence,
            "horizon": self.horizon,
            "risk_estimate": self.risk_estimate,
            "side": self.side,
            "model_name": self.model_name,
            "score": self.score,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


@dataclass(slots=True)
class AggregatedAlphaOpportunity:
    symbol: str
    side: str
    expected_return: float
    confidence: float
    horizon: str
    risk_estimate: float
    alpha_score: float
    regime: MarketRegime
    selected_models: list[str] = field(default_factory=list)
    reason: str = ""
    components: list[AlphaSignal] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "expected_return": self.expected_return,
            "confidence": self.confidence,
            "horizon": self.horizon,
            "risk_estimate": self.risk_estimate,
            "alpha_score": self.alpha_score,
            "regime": self.regime.to_dict(),
            "selected_models": list(self.selected_models),
            "reason": self.reason,
            "components": [component.to_dict() for component in self.components],
            "metadata": dict(self.metadata),
        }


class BaseAlphaModel(ABC):
    name = "base_alpha"
    supported_regimes = frozenset({"TRENDING", "MEAN_REVERTING", "HIGH_VOLATILITY", "LOW_LIQUIDITY"})
    minimum_history = 40

    def is_active(self, regime: MarketRegime | None) -> bool:
        if regime is None:
            return True
        return bool(set(regime.active_regimes) & set(self.supported_regimes))

    def _feature_frame(self, context: AlphaContext) -> pd.DataFrame | None:
        if context.feature_frame is not None and not context.feature_frame.empty:
            return context.feature_frame
        if context.frame is not None and not context.frame.empty:
            return context.frame
        return None

    def _row(self, context: AlphaContext):
        frame = self._feature_frame(context)
        if frame is None or frame.empty or len(frame) < self.minimum_history:
            return None, frame
        return frame.iloc[-1], frame

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _signal(
        self,
        context: AlphaContext,
        *,
        expected_return: float,
        confidence: float,
        horizon: str,
        risk_estimate: float,
        reason: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> AlphaSignal | None:
        expected = self._safe_float(expected_return, 0.0)
        confidence_value = max(0.0, min(1.0, self._safe_float(confidence, 0.0)))
        risk_value = max(1e-6, self._safe_float(risk_estimate, 0.0))
        if abs(expected) <= 1e-9 or confidence_value <= 0:
            return None
        side = "buy" if expected > 0 else "sell"
        score = (abs(expected) / risk_value) * confidence_value
        return AlphaSignal(
            symbol=context.symbol,
            expected_return=expected,
            confidence=confidence_value,
            horizon=str(horizon or "intraday"),
            risk_estimate=risk_value,
            side=side,
            model_name=self.name,
            score=score,
            reason=str(reason or "").strip(),
            metadata=dict(metadata or {}),
        )

    @abstractmethod
    def generate(self, context: AlphaContext) -> AlphaSignal | None:
        raise NotImplementedError
