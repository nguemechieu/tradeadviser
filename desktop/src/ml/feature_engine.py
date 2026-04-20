from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sopotek.core.models import Candle


@dataclass(slots=True)
class FeatureFrame:
    symbol: str
    timeframe: str
    values: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class FeatureEngine:
    """Shared feature generation for live trading and backtesting consistency."""

    def build_from_candles(self, candles: list[Candle], *, symbol: str | None = None, timeframe: str | None = None) -> FeatureFrame:
        series = list(candles or [])
        if not series:
            return FeatureFrame(symbol=str(symbol or ""), timeframe=str(timeframe or "1m"))
        closes = [float(item.close) for item in series]
        highs = [float(item.high) for item in series]
        lows = [float(item.low) for item in series]
        volumes = [float(item.volume) for item in series]
        latest = closes[-1]
        mean_close = sum(closes) / len(closes)
        returns = [0.0]
        for index in range(1, len(closes)):
            prior = closes[index - 1]
            returns.append(0.0 if prior == 0.0 else (closes[index] - prior) / prior)
        mean_return = sum(returns) / len(returns)
        variance = sum((item - mean_return) ** 2 for item in returns) / max(1, len(returns))
        volatility = variance ** 0.5
        high_low_range = 0.0 if latest == 0.0 else (max(highs) - min(lows)) / latest
        avg_volume = sum(volumes) / max(1, len(volumes))
        return FeatureFrame(
            symbol=str(symbol or series[-1].symbol),
            timeframe=str(timeframe or series[-1].timeframe),
            values={
                "close": latest,
                "mean_close": mean_close,
                "momentum_1": returns[-1],
                "momentum_5": sum(returns[-5:]),
                "realized_volatility": volatility,
                "high_low_range": high_low_range,
                "average_volume": avg_volume,
            },
            metadata={"bars": len(series)},
        )
