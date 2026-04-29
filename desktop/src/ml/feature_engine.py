from __future__ import annotations

"""
InvestPro FeatureEngine

Shared feature generation for live trading, backtesting, paper trading,
and ML Research Lab consistency.

Goals:
- same features in live and backtest
- deterministic feature names
- safe handling of short candle histories
- no pandas dependency required
- JSON-safe output
- useful technical indicators for ML/reasoning/strategy filters
"""

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

try:
    from ..models.candle import Candle
except Exception:  # pragma: no cover
    try:
        from models.candle import Candle
    except Exception:
        Candle = Any  # type: ignore


@dataclass(slots=True)
class FeatureFrame:
    """Container for feature values and metadata associated with a symbol/timeframe."""

    symbol: str
    timeframe: str
    values: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "values": dict(self.values or {}),
            "metadata": self._json_safe(dict(self.metadata or {})),
        }

    def vector(self, feature_names: list[str] | tuple[str, ...] | None = None) -> list[float]:
        """Return a deterministic numeric vector."""
        names = list(feature_names or sorted(self.values))
        return [float(self.values.get(name, 0.0) or 0.0) for name in names]

    def get(self, name: str, default: float = 0.0) -> float:
        return float(self.values.get(name, default) or default)

    @staticmethod
    def _json_safe(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (str, int, bool)):
            return value
        if isinstance(value, float):
            return value if math.isfinite(value) else None
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): FeatureFrame._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [FeatureFrame._json_safe(item) for item in value]
        return str(value)


class FeatureEngine:
    """Shared feature generation for live trading and backtesting consistency."""

    DEFAULT_FEATURE_NAMES = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "mean_close",
        "median_close",
        "return_1",
        "return_3",
        "return_5",
        "return_10",
        "momentum_1",
        "momentum_3",
        "momentum_5",
        "momentum_10",
        "log_return_1",
        "realized_volatility",
        "realized_volatility_5",
        "realized_volatility_10",
        "high_low_range",
        "candle_range_pct",
        "body_pct",
        "upper_wick_pct",
        "lower_wick_pct",
        "average_volume",
        "volume_ratio",
        "volume_change",
        "sma_5",
        "sma_10",
        "sma_20",
        "ema_fast",
        "ema_slow",
        "ema_diff",
        "ema_diff_pct",
        "rsi",
        "atr",
        "atr_pct",
        "macd",
        "macd_signal",
        "macd_hist",
        "trend_strength",
        "band_position",
        "zscore_close_20",
        "drawdown_from_high",
        "distance_from_low",
    ]

    def __init__(
        self,
        *,
        fast_ema: int = 12,
        slow_ema: int = 26,
        rsi_period: int = 14,
        atr_period: int = 14,
        volatility_window: int = 20,
        fill_missing: bool = True,
    ) -> None:
        self.fast_ema = max(2, int(fast_ema or 12))
        self.slow_ema = max(self.fast_ema + 1, int(slow_ema or 26))
        self.rsi_period = max(2, int(rsi_period or 14))
        self.atr_period = max(2, int(atr_period or 14))
        self.volatility_window = max(2, int(volatility_window or 20))
        self.fill_missing = bool(fill_missing)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_from_candles(
        self,
        candles: list[Candle] | list[Any],
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
    ) -> FeatureFrame:
        series = list(candles or [])

        normalized_symbol = str(symbol or "").strip().upper()
        normalized_timeframe = str(timeframe or "1m").strip() or "1m"

        if not series:
            return FeatureFrame(
                symbol=normalized_symbol,
                timeframe=normalized_timeframe,
                values=self._empty_values(),
                metadata={
                    "bars": 0,
                    "warning": "No candles supplied.",
                    "created_at": self._utc_now(),
                },
            )

        opens = [self._safe_float(self._field(item, "open"), 0.0)
                 for item in series]
        highs = [self._safe_float(self._field(item, "high"), 0.0)
                 for item in series]
        lows = [self._safe_float(self._field(item, "low"), 0.0)
                for item in series]
        closes = [self._safe_float(self._field(item, "close"), 0.0)
                  for item in series]
        volumes = [self._safe_float(self._field(
            item, "volume"), 0.0) for item in series]

        latest_candle = series[-1]
        normalized_symbol = normalized_symbol or str(
            self._field(latest_candle, "symbol", "") or "").strip().upper()
        normalized_timeframe = normalized_timeframe or str(
            self._field(latest_candle, "timeframe", "1m") or "1m")

        values = self._build_values(
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
        )

        if self.fill_missing:
            values = {
                name: self._safe_float(values.get(name), 0.0)
                for name in self.DEFAULT_FEATURE_NAMES
            }

        timestamp = self._field(latest_candle, "timestamp", None)

        return FeatureFrame(
            symbol=normalized_symbol,
            timeframe=normalized_timeframe,
            values=values,
            metadata={
                "bars": len(series),
                "created_at": self._utc_now(),
                "latest_timestamp": self._string_time(timestamp),
                "feature_count": len(values),
                "feature_names": list(values.keys()),
                "settings": {
                    "fast_ema": self.fast_ema,
                    "slow_ema": self.slow_ema,
                    "rsi_period": self.rsi_period,
                    "atr_period": self.atr_period,
                    "volatility_window": self.volatility_window,
                },
            },
        )

    def build_many(
        self,
        candles_by_symbol: dict[str, list[Candle] | list[Any]],
        *,
        timeframe: str | None = None,
    ) -> dict[str, FeatureFrame]:
        return {
            str(symbol).strip().upper(): self.build_from_candles(
                candles,
                symbol=str(symbol).strip().upper(),
                timeframe=timeframe,
            )
            for symbol, candles in dict(candles_by_symbol or {}).items()
        }

    def feature_names(self) -> list[str]:
        return list(self.DEFAULT_FEATURE_NAMES)

    # ------------------------------------------------------------------
    # Feature calculations
    # ------------------------------------------------------------------

    def _build_values(
        self,
        *,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> dict[str, float]:
        latest_open = opens[-1]
        latest_high = highs[-1]
        latest_low = lows[-1]
        latest_close = closes[-1]
        latest_volume = volumes[-1]

        returns = self._returns(closes)
        log_returns = self._log_returns(closes)

        sma_5 = self._sma(closes, 5)
        sma_10 = self._sma(closes, 10)
        sma_20 = self._sma(closes, 20)

        ema_fast_series = self._ema_series(closes, self.fast_ema)
        ema_slow_series = self._ema_series(closes, self.slow_ema)
        ema_fast = ema_fast_series[-1] if ema_fast_series else latest_close
        ema_slow = ema_slow_series[-1] if ema_slow_series else latest_close

        macd_series = [
            fast - slow
            for fast, slow in zip(
                self._align_tail(ema_fast_series, ema_slow_series),
                self._align_tail(ema_slow_series, ema_fast_series),
            )
        ]
        macd = macd_series[-1] if macd_series else 0.0
        macd_signal_series = self._ema_series(
            macd_series, 9) if macd_series else []
        macd_signal = macd_signal_series[-1] if macd_signal_series else 0.0
        macd_hist = macd - macd_signal

        atr = self._atr(highs, lows, closes, self.atr_period)
        atr_pct = self._safe_div(atr, latest_close)

        mean_close = self._mean(closes)
        median_close = self._median(closes)

        high_low_range = self._safe_div(max(highs) - min(lows), latest_close)
        candle_range_pct = self._safe_div(
            latest_high - latest_low, latest_close)
        candle_body_pct = self._safe_div(
            abs(latest_close - latest_open), latest_close)
        upper_wick_pct = self._safe_div(
            latest_high - max(latest_open, latest_close), latest_close)
        lower_wick_pct = self._safe_div(
            min(latest_open, latest_close) - latest_low, latest_close)

        average_volume = self._mean(volumes)
        recent_average_volume = self._mean(volumes[-20:])
        volume_ratio = self._safe_div(latest_volume, recent_average_volume)
        volume_change = self._safe_div(
            latest_volume - volumes[-2], volumes[-2]) if len(volumes) >= 2 else 0.0

        rolling_high = max(highs[-20:]) if highs else latest_high
        rolling_low = min(lows[-20:]) if lows else latest_low
        band_position = self._safe_div(
            latest_close - rolling_low, rolling_high - rolling_low, default=0.5)

        zscore_close_20 = self._zscore_latest(closes, 20)

        drawdown_from_high = self._safe_div(
            latest_close - rolling_high, rolling_high)
        distance_from_low = self._safe_div(
            latest_close - rolling_low, rolling_low)

        trend_strength = abs(self._linear_slope(
            closes[-min(len(closes), 50):])) / max(abs(latest_close), 1e-12)
        trend_strength = min(1.0, trend_strength * 100.0)

        values = {
            "open": latest_open,
            "high": latest_high,
            "low": latest_low,
            "close": latest_close,
            "volume": latest_volume,
            "mean_close": mean_close,
            "median_close": median_close,
            "return_1": self._tail_sum(returns, 1),
            "return_3": self._tail_sum(returns, 3),
            "return_5": self._tail_sum(returns, 5),
            "return_10": self._tail_sum(returns, 10),
            "momentum_1": self._tail_sum(returns, 1),
            "momentum_3": self._tail_sum(returns, 3),
            "momentum_5": self._tail_sum(returns, 5),
            "momentum_10": self._tail_sum(returns, 10),
            "log_return_1": log_returns[-1] if log_returns else 0.0,
            "realized_volatility": self._std(returns[-self.volatility_window:]),
            "realized_volatility_5": self._std(returns[-5:]),
            "realized_volatility_10": self._std(returns[-10:]),
            "high_low_range": high_low_range,
            "candle_range_pct": candle_range_pct,
            "body_pct": candle_body_pct,
            "upper_wick_pct": upper_wick_pct,
            "lower_wick_pct": lower_wick_pct,
            "average_volume": average_volume,
            "volume_ratio": volume_ratio,
            "volume_change": volume_change,
            "sma_5": sma_5,
            "sma_10": sma_10,
            "sma_20": sma_20,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema_diff": ema_fast - ema_slow,
            "ema_diff_pct": self._safe_div(ema_fast - ema_slow, latest_close),
            "rsi": self._rsi(closes, self.rsi_period),
            "atr": atr,
            "atr_pct": atr_pct,
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
            "trend_strength": trend_strength,
            "band_position": band_position,
            "zscore_close_20": zscore_close_20,
            "drawdown_from_high": drawdown_from_high,
            "distance_from_low": distance_from_low,
        }

        return {key: self._safe_float(value, 0.0) for key, value in values.items()}

    def _empty_values(self) -> dict[str, float]:
        return {name: 0.0 for name in self.DEFAULT_FEATURE_NAMES}

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------

    def _returns(self, values: list[float]) -> list[float]:
        if not values:
            return []
        output = [0.0]
        for index in range(1, len(values)):
            prior = values[index - 1]
            current = values[index]
            output.append(self._safe_div(current - prior, prior))
        return output

    def _log_returns(self, values: list[float]) -> list[float]:
        if not values:
            return []
        output = [0.0]
        for index in range(1, len(values)):
            prior = values[index - 1]
            current = values[index]
            if prior <= 0 or current <= 0:
                output.append(0.0)
            else:
                output.append(math.log(current / prior))
        return output

    def _sma(self, values: list[float], window: int) -> float:
        if not values:
            return 0.0
        return self._mean(values[-max(1, int(window)):])

    def _ema_series(self, values: list[float], period: int) -> list[float]:
        if not values:
            return []
        period = max(1, int(period))
        alpha = 2.0 / (period + 1.0)
        output = [float(values[0])]
        for value in values[1:]:
            output.append((alpha * float(value)) +
                          ((1.0 - alpha) * output[-1]))
        return output

    def _rsi(self, closes: list[float], period: int) -> float:
        if len(closes) < 2:
            return 50.0

        changes = [closes[index] - closes[index - 1]
                   for index in range(1, len(closes))]
        recent = changes[-max(1, int(period)):]

        gains = [change for change in recent if change > 0]
        losses = [-change for change in recent if change < 0]

        avg_gain = self._mean(gains) if gains else 0.0
        avg_loss = self._mean(losses) if losses else 0.0

        if avg_loss <= 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _atr(self, highs: list[float], lows: list[float], closes: list[float], period: int) -> float:
        if not highs or not lows or not closes:
            return 0.0

        true_ranges: list[float] = []

        for index in range(len(closes)):
            high = highs[index]
            low = lows[index]

            if index == 0:
                true_ranges.append(max(0.0, high - low))
            else:
                previous_close = closes[index - 1]
                true_ranges.append(
                    max(
                        high - low,
                        abs(high - previous_close),
                        abs(low - previous_close),
                    )
                )

        return self._mean(true_ranges[-max(1, int(period)):])

    # ------------------------------------------------------------------
    # Math helpers
    # ------------------------------------------------------------------

    def _mean(self, values: Iterable[float]) -> float:
        rows = [self._safe_float(value, 0.0) for value in values]
        return sum(rows) / len(rows) if rows else 0.0

    def _median(self, values: list[float]) -> float:
        if not values:
            return 0.0
        rows = sorted(values)
        mid = len(rows) // 2
        if len(rows) % 2:
            return rows[mid]
        return (rows[mid - 1] + rows[mid]) / 2.0

    def _std(self, values: list[float]) -> float:
        if not values:
            return 0.0
        mean = self._mean(values)
        variance = sum((item - mean) ** 2 for item in values) / len(values)
        return math.sqrt(max(variance, 0.0))

    def _zscore_latest(self, values: list[float], window: int) -> float:
        rows = values[-max(1, int(window)):]
        if not rows:
            return 0.0
        mean = self._mean(rows)
        std = self._std(rows)
        if std <= 0:
            return 0.0
        return (rows[-1] - mean) / std

    def _linear_slope(self, values: list[float]) -> float:
        n = len(values)
        if n < 2:
            return 0.0

        x_mean = (n - 1) / 2.0
        y_mean = self._mean(values)

        numerator = sum((index - x_mean) * (value - y_mean)
                        for index, value in enumerate(values))
        denominator = sum((index - x_mean) ** 2 for index in range(n))

        if denominator <= 0:
            return 0.0

        return numerator / denominator

    def _tail_sum(self, values: list[float], count: int) -> float:
        return sum(values[-max(1, int(count)):]) if values else 0.0

    def _align_tail(self, left: list[float], right: list[float]) -> list[float]:
        if not left or not right:
            return []
        size = min(len(left), len(right))
        return left[-size:]

    def _safe_div(self, numerator: float, denominator: float, default: float = 0.0) -> float:
        denominator = self._safe_float(denominator, 0.0)
        if abs(denominator) <= 1e-12:
            return default
        return self._safe_float(numerator, 0.0) / denominator

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        if value in (None, ""):
            return float(default)
        try:
            number = float(value)
        except Exception:
            return float(default)
        if not math.isfinite(number):
            return float(default)
        return number

    def _field(self, obj: Any, name: str, default: Any = None) -> Any:
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def _string_time(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        return str(value)

    def _utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
