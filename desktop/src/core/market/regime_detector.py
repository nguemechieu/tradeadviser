from __future__ import annotations

"""
InvestPro Market Regime Detector

Detects high-level market regime from OHLCV candles.

Regimes:
- UNKNOWN
- TRENDING_UP
- TRENDING_DOWN
- RANGING
- VOLATILE
- BREAKOUT

The detector uses:
- return volatility
- trend slope
- linear-regression R²
- price range compression/expansion
- ATR percentage
- breakout detection
- optional volume expansion

This is designed to feed:
- DecisionEngine
- TradeFilter
- RiskEngine
- Strategy selection
- ML/AI reasoning layer
"""

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import numpy as np

try:
    from ...models.candle import Candle
except Exception:  # Keeps module importable during refactors/tests
    Candle = Any  # type: ignore


@dataclass(slots=True)
class MarketRegime:
    """Represents the current market regime and confidence level."""

    name: str
    confidence: float
    trend_strength: float = 0.0
    volatility: float = 0.0
    atr_pct: float = 0.0
    slope: float = 0.0
    r_squared: float = 0.0
    breakout_score: float = 0.0
    direction: str = "neutral"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": self.confidence,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "atr_pct": self.atr_pct,
            "slope": self.slope,
            "r_squared": self.r_squared,
            "breakout_score": self.breakout_score,
            "direction": self.direction,
            "metadata": dict(self.metadata),
        }


class MarketRegimeDetector:
    """Detect current market regime from recent candles."""

    def __init__(
        self,
        window: int = 50,
        *,
        min_candles: int = 20,
        volatility_threshold: float = 0.025,
        atr_pct_threshold: float = 0.035,
        trend_strength_threshold: float = 0.55,
        r_squared_threshold: float = 0.35,
        breakout_threshold: float = 0.70,
        range_threshold: float = 0.35,
    ) -> None:
        self.window = max(10, int(window or 50))
        self.min_candles = max(5, int(min_candles or 20))

        self.volatility_threshold = float(volatility_threshold)
        self.atr_pct_threshold = float(atr_pct_threshold)
        self.trend_strength_threshold = float(trend_strength_threshold)
        self.r_squared_threshold = float(r_squared_threshold)
        self.breakout_threshold = float(breakout_threshold)
        self.range_threshold = float(range_threshold)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, candles: list[Candle] | Iterable[Any]) -> MarketRegime:
        """Detect the current regime from OHLCV candle data."""
        prepared = self._prepare_candles(candles)

        if len(prepared["close"]) < self.min_candles:
            return MarketRegime(
                name="UNKNOWN",
                confidence=0.0,
                metadata={
                    "reason": "Not enough candles",
                    "required": self.min_candles,
                    "received": len(prepared["close"]),
                },
            )

        close = prepared["close"][-self.window:]
        high = prepared["high"][-self.window:]
        low = prepared["low"][-self.window:]
        volume = prepared["volume"][-self.window:]

        if len(close) < self.min_candles or np.any(close <= 0):
            return MarketRegime(
                name="UNKNOWN",
                confidence=0.0,
                metadata={"reason": "Invalid close prices"},
            )

        returns = self._safe_returns(close)
        volatility = float(np.std(returns)) if len(returns) else 0.0

        trend = self._trend_metrics(close)
        atr_pct = self._atr_percent(high, low, close)
        breakout_score = self._breakout_score(close, high, low, volume)
        range_score = self._range_score(close, high, low)

        direction = "up" if trend["slope"] > 0 else "down" if trend["slope"] < 0 else "neutral"

        metadata = {
            "window": len(close),
            "volatility_threshold": self.volatility_threshold,
            "atr_pct_threshold": self.atr_pct_threshold,
            "trend_strength_threshold": self.trend_strength_threshold,
            "r_squared_threshold": self.r_squared_threshold,
            "breakout_threshold": self.breakout_threshold,
            "range_threshold": self.range_threshold,
            "range_score": range_score,
            "last_close": float(close[-1]),
            "mean_close": float(np.mean(close)),
        }

        # 1. Breakout has priority if price expands out of recent range.
        if breakout_score >= self.breakout_threshold:
            confidence = self._clamp(
                0.50 * breakout_score
                + 0.25 * trend["trend_strength"]
                + 0.25 *
                min(atr_pct / max(self.atr_pct_threshold, 1e-12), 1.0),
                0.0,
                1.0,
            )
            return MarketRegime(
                name="BREAKOUT",
                confidence=confidence,
                trend_strength=trend["trend_strength"],
                volatility=volatility,
                atr_pct=atr_pct,
                slope=trend["slope"],
                r_squared=trend["r_squared"],
                breakout_score=breakout_score,
                direction=direction,
                metadata=metadata,
            )

        # 2. High volatility regime.
        if volatility >= self.volatility_threshold or atr_pct >= self.atr_pct_threshold:
            confidence = self._clamp(
                max(
                    volatility / max(self.volatility_threshold, 1e-12),
                    atr_pct / max(self.atr_pct_threshold, 1e-12),
                )
                / 2.0,
                0.0,
                1.0,
            )
            return MarketRegime(
                name="VOLATILE",
                confidence=confidence,
                trend_strength=trend["trend_strength"],
                volatility=volatility,
                atr_pct=atr_pct,
                slope=trend["slope"],
                r_squared=trend["r_squared"],
                breakout_score=breakout_score,
                direction=direction,
                metadata=metadata,
            )

        # 3. Trending regime requires trend strength and regression quality.
        is_trending = (
            trend["trend_strength"] >= self.trend_strength_threshold
            and trend["r_squared"] >= self.r_squared_threshold
        )

        if is_trending:
            name = "TRENDING_UP" if trend["slope"] >= 0 else "TRENDING_DOWN"
            confidence = self._clamp(
                0.60 * trend["trend_strength"]
                + 0.40 * trend["r_squared"],
                0.0,
                1.0,
            )
            return MarketRegime(
                name=name,
                confidence=confidence,
                trend_strength=trend["trend_strength"],
                volatility=volatility,
                atr_pct=atr_pct,
                slope=trend["slope"],
                r_squared=trend["r_squared"],
                breakout_score=breakout_score,
                direction=direction,
                metadata=metadata,
            )

        # 4. Ranging/choppy market.
        confidence = self._clamp(
            0.55 * range_score
            + 0.25 * (1.0 - trend["trend_strength"])
            + 0.20 * (1.0 - min(volatility /
                      max(self.volatility_threshold, 1e-12), 1.0)),
            0.0,
            1.0,
        )

        return MarketRegime(
            name="RANGING",
            confidence=confidence,
            trend_strength=trend["trend_strength"],
            volatility=volatility,
            atr_pct=atr_pct,
            slope=trend["slope"],
            r_squared=trend["r_squared"],
            breakout_score=breakout_score,
            direction="neutral",
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # Data prep
    # ------------------------------------------------------------------

    def _prepare_candles(self, candles: list[Candle] | Iterable[Any]) -> dict[str, np.ndarray]:
        rows = list(candles or [])

        close: list[float] = []
        high: list[float] = []
        low: list[float] = []
        volume: list[float] = []

        for candle in rows:
            c = self._field(candle, "close", None)
            h = self._field(candle, "high", c)
            l = self._field(candle, "low", c)
            v = self._field(candle, "volume", 0.0)

            c_float = self._safe_float(c, default=np.nan)
            h_float = self._safe_float(h, default=c_float)
            l_float = self._safe_float(l, default=c_float)
            v_float = self._safe_float(v, default=0.0)

            if not np.isfinite(c_float) or c_float <= 0:
                continue

            if not np.isfinite(h_float) or h_float <= 0:
                h_float = c_float

            if not np.isfinite(l_float) or l_float <= 0:
                l_float = c_float

            if h_float < l_float:
                h_float, l_float = l_float, h_float

            close.append(c_float)
            high.append(h_float)
            low.append(l_float)
            volume.append(max(v_float, 0.0))

        return {
            "close": np.asarray(close, dtype=float),
            "high": np.asarray(high, dtype=float),
            "low": np.asarray(low, dtype=float),
            "volume": np.asarray(volume, dtype=float),
        }

    def _field(self, candle: Any, name: str, default: Any = None) -> Any:
        if isinstance(candle, dict):
            return candle.get(name, default)

        return getattr(candle, name, default)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _safe_returns(self, prices: np.ndarray) -> np.ndarray:
        prices = np.asarray(prices, dtype=float)

        if len(prices) < 2:
            return np.asarray([], dtype=float)

        prev = prices[:-1]
        current = prices[1:]
        valid = prev > 0

        if not np.any(valid):
            return np.asarray([], dtype=float)

        returns = np.zeros_like(current)
        returns[valid] = (current[valid] - prev[valid]) / prev[valid]
        returns = returns[np.isfinite(returns)]

        return returns

    def _trend_metrics(self, prices: np.ndarray) -> dict[str, float]:
        prices = np.asarray(prices, dtype=float)

        if len(prices) < 3:
            return {"slope": 0.0, "r_squared": 0.0, "trend_strength": 0.0}

        x = np.arange(len(prices), dtype=float)

        try:
            slope, intercept = np.polyfit(x, prices, 1)
        except Exception:
            return {"slope": 0.0, "r_squared": 0.0, "trend_strength": 0.0}

        predicted = slope * x + intercept
        residual = prices - predicted

        ss_res = float(np.sum(residual ** 2))
        ss_tot = float(np.sum((prices - np.mean(prices)) ** 2))

        r_squared = 0.0 if ss_tot <= 1e-12 else 1.0 - (ss_res / ss_tot)
        r_squared = self._clamp(r_squared, 0.0, 1.0)

        mean_price = float(np.mean(prices))
        normalized_slope = abs(float(slope)) / max(abs(mean_price), 1e-12)

        # Scale slope into 0-1. Higher means stronger directional drift.
        slope_strength = self._clamp(
            normalized_slope * len(prices) * 10.0, 0.0, 1.0)

        trend_strength = self._clamp(
            0.65 * slope_strength + 0.35 * r_squared,
            0.0,
            1.0,
        )

        return {
            "slope": float(slope),
            "r_squared": float(r_squared),
            "trend_strength": float(trend_strength),
        }

    def _atr_percent(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> float:
        if len(close) < 2:
            return 0.0

        high = np.asarray(high, dtype=float)
        low = np.asarray(low, dtype=float)
        close = np.asarray(close, dtype=float)

        prev_close = close[:-1]
        current_high = high[1:]
        current_low = low[1:]

        tr1 = current_high - current_low
        tr2 = np.abs(current_high - prev_close)
        tr3 = np.abs(current_low - prev_close)

        true_range = np.maximum(tr1, np.maximum(tr2, tr3))
        true_range = true_range[np.isfinite(true_range)]

        if len(true_range) == 0:
            return 0.0

        atr = float(np.mean(true_range))
        mean_close = float(np.mean(close))

        if mean_close <= 0:
            return 0.0

        return float(atr / mean_close)

    def _breakout_score(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        volume: np.ndarray,
    ) -> float:
        if len(close) < 10:
            return 0.0

        lookback = max(5, min(20, len(close) - 1))
        previous_high = float(np.max(high[-lookback - 1:-1]))
        previous_low = float(np.min(low[-lookback - 1:-1]))
        last_close = float(close[-1])

        price_range = max(previous_high - previous_low, 1e-12)

        upside_break = max(0.0, last_close - previous_high) / price_range
        downside_break = max(0.0, previous_low - last_close) / price_range

        price_break_score = self._clamp(
            max(upside_break, downside_break) * 2.0, 0.0, 1.0)

        volume_score = 0.0
        if len(volume) >= lookback + 1:
            recent_volume = float(volume[-1])
            avg_volume = float(np.mean(volume[-lookback - 1:-1]))
            if avg_volume > 0:
                volume_score = self._clamp(
                    (recent_volume / avg_volume - 1.0) / 2.0, 0.0, 1.0)

        return self._clamp(0.75 * price_break_score + 0.25 * volume_score, 0.0, 1.0)

    def _range_score(self, close: np.ndarray, high: np.ndarray, low: np.ndarray) -> float:
        if len(close) < 5:
            return 0.0

        recent_high = float(np.max(high))
        recent_low = float(np.min(low))
        mean_close = float(np.mean(close))

        if mean_close <= 0:
            return 0.0

        range_pct = (recent_high - recent_low) / mean_close
        returns = self._safe_returns(close)
        volatility = float(np.std(returns)) if len(returns) else 0.0

        # Lower range and lower volatility generally indicate ranging/compression.
        range_component = 1.0 - self._clamp(range_pct / 0.08, 0.0, 1.0)
        volatility_component = 1.0 - \
            self._clamp(
                volatility / max(self.volatility_threshold, 1e-12), 0.0, 1.0)

        return self._clamp(0.55 * range_component + 0.45 * volatility_component, 0.0, 1.0)

    # ------------------------------------------------------------------
    # Compatibility helper
    # ------------------------------------------------------------------

    def _trend_strength(self, prices: np.ndarray) -> float:
        """Backward-compatible trend strength method."""
        return self._trend_metrics(prices)["trend_strength"]

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            number = float(value)
        except Exception:
            return float(default)

        if not np.isfinite(number):
            return float(default)

        return number

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))
